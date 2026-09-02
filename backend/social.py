"""YouTube + Instagram OAuth and upload helpers.

Tokens are NEVER logged. Client IDs/secrets come from env (no hardcoded secrets).
REELS_MOCK=1 short-circuits live network calls so tests don't hit Google/Meta.
"""
from __future__ import annotations

import json
import logging
import os
from typing import Optional
from urllib.parse import urlencode

import httpx

logger = logging.getLogger("reels.social")

GOOGLE_AUTH = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
YOUTUBE_UPLOAD = "https://www.googleapis.com/upload/youtube/v3/videos"
YOUTUBE_CHANNELS = "https://www.googleapis.com/youtube/v3/channels"

# Instagram Login (Instagram API with Instagram Login) — free Meta developer app.
IG_AUTH = "https://www.instagram.com/oauth/authorize"
IG_TOKEN = "https://api.instagram.com/oauth/access_token"
IG_GRAPH = "https://graph.instagram.com"
IG_GRAPH_VERSION = "v21.0"

YT_SCOPES = "https://www.googleapis.com/auth/youtube.upload https://www.googleapis.com/auth/youtube.readonly"
IG_SCOPES = "instagram_business_basic,instagram_business_content_publish"


def public_base() -> str:
    return (os.environ.get("PUBLIC_BASE_URL") or os.environ.get("EXPO_PUBLIC_BACKEND_URL") or "").rstrip("/")


def youtube_configured() -> bool:
    return bool(os.environ.get("GOOGLE_OAUTH_CLIENT_ID") and os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET"))


def instagram_configured() -> bool:
    return bool(os.environ.get("META_APP_ID") and os.environ.get("META_APP_SECRET"))


def youtube_redirect() -> str:
    return os.environ.get("YOUTUBE_REDIRECT_URI") or f"{public_base()}/api/connect/youtube/callback"


def instagram_redirect() -> str:
    return os.environ.get("INSTAGRAM_REDIRECT_URI") or f"{public_base()}/api/connect/instagram/callback"


def youtube_auth_url(state: str) -> str:
    q = {
        "client_id": os.environ["GOOGLE_OAUTH_CLIENT_ID"],
        "redirect_uri": youtube_redirect(),
        "response_type": "code",
        "scope": YT_SCOPES,
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true",
        "state": state,
    }
    return f"{GOOGLE_AUTH}?{urlencode(q)}"


def instagram_auth_url(state: str) -> str:
    q = {
        "client_id": os.environ["META_APP_ID"],
        "redirect_uri": instagram_redirect(),
        "response_type": "code",
        "scope": IG_SCOPES,
        "state": state,
    }
    return f"{IG_AUTH}?{urlencode(q)}"


def _setup_message(platform: str) -> str:
    if platform == "youtube":
        return (
            "YouTube posting isn't set up yet. The app owner needs to create a free Google Cloud "
            "OAuth client and paste GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET into "
            "the backend environment, plus the callback URL shown in the pull request."
        )
    return (
        "Instagram posting isn't set up yet. The app owner needs to create a free Meta app with "
        "Instagram API, then paste META_APP_ID and META_APP_SECRET into the backend environment, "
        "plus the callback URL shown in the pull request."
    )


async def exchange_youtube_code(code: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(GOOGLE_TOKEN, data={
            "code": code,
            "client_id": os.environ["GOOGLE_OAUTH_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
            "redirect_uri": youtube_redirect(),
            "grant_type": "authorization_code",
        })
        if r.status_code >= 400:
            logger.warning("YouTube token exchange failed status=%s", r.status_code)
            raise RuntimeError("Couldn't connect YouTube. Try again.")
        return r.json()


async def refresh_youtube_token(refresh_token: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(GOOGLE_TOKEN, data={
            "client_id": os.environ["GOOGLE_OAUTH_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_OAUTH_CLIENT_SECRET"],
            "refresh_token": refresh_token,
            "grant_type": "refresh_token",
        })
        if r.status_code >= 400:
            logger.warning("YouTube token refresh failed status=%s", r.status_code)
            raise RuntimeError("YouTube login expired. Reconnect in Settings.")
        data = r.json()
        data["refresh_token"] = data.get("refresh_token") or refresh_token
        return data


async def youtube_channel_title(access_token: str) -> str:
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(
            YOUTUBE_CHANNELS,
            params={"part": "snippet", "mine": "true"},
            headers={"Authorization": f"Bearer {access_token}"},
        )
        if r.status_code >= 400:
            return ""
        items = (r.json() or {}).get("items") or []
        if not items:
            return ""
        return ((items[0].get("snippet") or {}).get("title") or "").strip()


async def youtube_upload(access_token: str, video_bytes: bytes, title: str, description: str,
                         privacy: str = "public") -> dict:
    if os.environ.get("REELS_MOCK", "0") == "1":
        return {"id": "mock-youtube", "mock": True}
    privacy = privacy if privacy in ("public", "unlisted", "private") else "public"
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json; charset=UTF-8",
        "X-Upload-Content-Type": "video/mp4",
        "X-Upload-Content-Length": str(len(video_bytes)),
    }
    body = {
        "snippet": {
            "title": (title or "GhostReelsAlpha")[:100],
            "description": (description or "")[:5000],
            "categoryId": "22",
        },
        "status": {"privacyStatus": privacy, "selfDeclaredMadeForKids": False},
    }
    async with httpx.AsyncClient(timeout=180) as client:
        r = await client.post(
            f"{YOUTUBE_UPLOAD}?uploadType=resumable&part=snippet,status",
            headers=headers, json=body,
        )
        if r.status_code >= 400:
            logger.warning("YouTube resumable init failed status=%s", r.status_code)
            raise RuntimeError("YouTube didn't accept the upload. Check that the connected account can upload.")
        loc = r.headers.get("Location")
        if not loc:
            raise RuntimeError("YouTube didn't return an upload URL.")
        r2 = await client.put(
            loc,
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "video/mp4"},
            content=video_bytes,
        )
        if r2.status_code >= 400:
            logger.warning("YouTube upload put failed status=%s", r2.status_code)
            raise RuntimeError("YouTube upload failed. Try again in a moment.")
        return r2.json()


async def exchange_instagram_code(code: str) -> dict:
    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.post(IG_TOKEN, data={
            "client_id": os.environ["META_APP_ID"],
            "client_secret": os.environ["META_APP_SECRET"],
            "grant_type": "authorization_code",
            "redirect_uri": instagram_redirect(),
            "code": code,
        })
        if r.status_code >= 400:
            logger.warning("Instagram token exchange failed status=%s", r.status_code)
            raise RuntimeError("Couldn't connect Instagram. Try again.")
        data = r.json()
        short = data.get("access_token")
        user_id = str((data.get("user_id") or data.get("id") or ""))
        if short:
            r2 = await client.get(
                f"{IG_GRAPH}/access_token",
                params={
                    "grant_type": "ig_exchange_token",
                    "client_secret": os.environ["META_APP_SECRET"],
                    "access_token": short,
                },
            )
            if r2.status_code < 400:
                long_data = r2.json()
                data["access_token"] = long_data.get("access_token") or short
                data["expires_in"] = long_data.get("expires_in")
        data["user_id"] = user_id
        return data


async def instagram_username(access_token: str, user_id: str) -> str:
    if not (access_token and user_id):
        return ""
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get(
            f"{IG_GRAPH}/{IG_GRAPH_VERSION}/{user_id}",
            params={"fields": "username", "access_token": access_token},
        )
        if r.status_code >= 400:
            return ""
        return (r.json() or {}).get("username") or ""


async def instagram_publish(access_token: str, user_id: str, video_url: str, caption: str) -> dict:
    if os.environ.get("REELS_MOCK", "0") == "1":
        return {"id": "mock-instagram", "mock": True}
    async with httpx.AsyncClient(timeout=180) as client:
        r = await client.post(
            f"{IG_GRAPH}/{IG_GRAPH_VERSION}/{user_id}/media",
            data={
                "media_type": "REELS",
                "video_url": video_url,
                "caption": (caption or "")[:2200],
                "share_to_feed": "true",
                "access_token": access_token,
            },
        )
        if r.status_code >= 400:
            logger.warning("Instagram container create failed status=%s", r.status_code)
            raise RuntimeError("Instagram didn't accept the reel. The connected account must be a professional account.")
        creation_id = (r.json() or {}).get("id")
        if not creation_id:
            raise RuntimeError("Instagram didn't return a media id.")
        import asyncio
        status = ""
        for _ in range(24):
            pr = await client.get(
                f"{IG_GRAPH}/{IG_GRAPH_VERSION}/{creation_id}",
                params={"fields": "status_code", "access_token": access_token},
            )
            status = ((pr.json() or {}).get("status_code") or "").upper()
            if status in ("FINISHED", "ERROR", "EXPIRED"):
                break
            await asyncio.sleep(5)
        if status != "FINISHED":
            raise RuntimeError("Instagram is still processing, or the video URL wasn't reachable. Try again.")
        pub = await client.post(
            f"{IG_GRAPH}/{IG_GRAPH_VERSION}/{user_id}/media_publish",
            data={"creation_id": creation_id, "access_token": access_token},
        )
        if pub.status_code >= 400:
            logger.warning("Instagram publish failed status=%s", pub.status_code)
            raise RuntimeError("Instagram publish failed. Try again.")
        return pub.json()


def dump_tokens(blob: dict) -> str:
    """Serialize OAuth tokens for AES encryption. Never log the result."""
    keep = {k: blob.get(k) for k in ("access_token", "refresh_token", "expires_in", "token_type", "user_id") if blob.get(k)}
    return json.dumps(keep)


def load_tokens(raw: str) -> dict:
    try:
        return json.loads(raw) if raw else {}
    except Exception:
        return {}
