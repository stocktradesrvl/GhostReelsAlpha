"""Export size + YouTube/Instagram connect/post routes (loaded by lock_boot)."""
from __future__ import annotations

import logging
import os
from pathlib import Path as _Path
from typing import Optional

from fastapi import Depends, HTTPException, Query
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel
from starlette.concurrency import run_in_threadpool

import pipeline
import social
import storage_client
from reels_config import ASPECT_MAP

log = logging.getLogger("reels.lock")


def register(S, router, media_user, optional_media_user):
    class ExportRequest(BaseModel):
        aspect: str = "9:16"

    class SocialPostRequest(BaseModel):
        platform: str
        title: Optional[str] = None
        caption: Optional[str] = None
        privacy: Optional[str] = "public"

    async def _set_export(reel_id: str, aspect: str, **fields):
        reel = await S.db.reels.find_one({"id": reel_id}) or {}
        exports = dict(reel.get("exports") or {})
        cur = dict(exports.get(aspect) or {})
        cur.update(fields)
        exports[aspect] = cur
        await S.update_reel(reel_id, exports=exports)

    async def export_aspect_task(reel_id: str, aspect: str):
        spec = ASPECT_MAP.get(aspect)
        if not spec or aspect == "9:16":
            return
        w, h = int(spec["width"]), int(spec["height"])
        workdir = pipeline.new_workdir()
        try:
            reel = await S.db.reels.find_one({"id": reel_id})
            if not reel or not reel.get("audio_path"):
                await _set_export(reel_id, aspect, status="failed", error="This reel can't be re-exported.", width=w, height=h)
                return
            is_ai = reel.get("visual_mode") == "ai"
            if is_ai and not reel.get("scenes"):
                await _set_export(reel_id, aspect, status="failed", error="This reel can't be re-exported.", width=w, height=h)
                return
            await _set_export(reel_id, aspect, status="rendering", error=None, width=w, height=h)
            audio_path = os.path.join(workdir, "voice.mp3")
            content, _ = await run_in_threadpool(storage_client.get_object, reel["audio_path"])
            with open(audio_path, "wb") as f:
                f.write(content)
            words = reel.get("words") or []
            duration = float(reel.get("duration") or max(3.0, len(words) * 0.4))
            ass_path = os.path.join(workdir, "subs.ass")
            pipeline.build_ass(
                words, duration, reel["caption_style"], ass_path,
                position=reel.get("caption_position", "center"),
                size=reel.get("caption_size", "m"),
                watermark=reel.get("watermark") or "",
                hook_text=pipeline.hook_line(reel.get("script") or "") if reel.get("hook_enabled") else "",
                caption_font=reel.get("caption_font", "barlow"),
                endcard_text=reel.get("endcard_text") or "",
                caption_anim=reel.get("caption_anim", "pop"),
                width=w, height=h,
            )
            out_path = str(S.MEDIA_DIR / f"{reel_id}_{aspect.replace(':', 'x')}.mp4")
            if is_ai:
                images = []
                for i, s in enumerate(reel["scenes"]):
                    ip = os.path.join(workdir, f"scene_{i}.png")
                    content, _ = await run_in_threadpool(storage_client.get_object, s["image_path"])
                    with open(ip, "wb") as f:
                        f.write(content)
                    images.append(ip)
                await pipeline.render_video_images(
                    audio_path, "subs.ass", images, duration, workdir, out_path,
                    music_id=reel.get("music_id", "none"),
                    music_volume=reel.get("music_volume", 0.13),
                    width=w, height=h,
                )
            else:
                await pipeline.render_video(
                    audio_path, "subs.ass", reel["bg_theme"], duration, workdir, out_path,
                    music_id=reel.get("music_id", "none"),
                    music_volume=reel.get("music_volume", 0.13),
                    bg_motion=reel.get("bg_motion", "subtle"),
                    custom_colors=[reel.get("custom_c1"), reel.get("custom_c2")],
                    width=w, height=h,
                )
            with open(out_path, "rb") as f:
                video_bytes = f.read()
            vpath = f"{storage_client.APP_NAME}/reels/{reel_id}_{aspect.replace(':', 'x')}.mp4"
            await run_in_threadpool(storage_client.put_object, vpath, video_bytes, "video/mp4")
            await _set_export(reel_id, aspect, status="ready", video_path=vpath, error=None, width=w, height=h)
        except Exception as e:  # noqa: BLE001
            log.exception("Aspect export failed for %s %s", reel_id, aspect)
            _code, friendly = S.classify_error(e)
            await _set_export(reel_id, aspect, status="failed", error=friendly, width=w, height=h)
        finally:
            import shutil
            shutil.rmtree(workdir, ignore_errors=True)

    @router.post("/reels/{reel_id}/export")
    async def export_reel_aspect(reel_id: str, req: ExportRequest, user=Depends(S.current_user)):
        doc = await S.owned_reel(reel_id, user)
        aspect = (req.aspect or "").strip()
        if aspect not in ASPECT_MAP:
            raise HTTPException(400, "Unknown size. Use 9:16, 1:1 or 16:9.")
        if doc.get("status") != "ready" or not doc.get("audio_path"):
            raise HTTPException(409, "Finish generating the reel first.")
        if aspect == "9:16":
            return S.public_reel(doc)
        exp = (doc.get("exports") or {}).get(aspect) or {}
        if exp.get("status") in ("ready", "rendering") and (exp.get("status") != "ready" or exp.get("video_path")):
            return S.public_reel(doc)
        spec = ASPECT_MAP[aspect]
        await _set_export(reel_id, aspect, status="queued", error=None, width=spec["width"], height=spec["height"])
        import asyncio
        asyncio.create_task(export_aspect_task(reel_id, aspect))
        return S.public_reel(await S.db.reels.find_one({"id": reel_id}))

    def _oauth_state(uid: str, provider: str) -> str:
        from datetime import datetime, timedelta, timezone
        import jwt
        now = datetime.now(timezone.utc)
        return jwt.encode({"sub": uid, "p": provider, "iat": now, "exp": now + timedelta(minutes=15)},
                          S.JWT_SECRET, algorithm=S.JWT_ALG)

    def _read_oauth_state(state: str, provider: str) -> str:
        import jwt
        try:
            payload = jwt.decode(state, S.JWT_SECRET, algorithms=[S.JWT_ALG])
        except Exception:  # noqa: BLE001
            raise HTTPException(400, "This connect link expired. Start again from Settings.")
        if payload.get("p") != provider or not payload.get("sub"):
            raise HTTPException(400, "Invalid connect link.")
        return payload["sub"]

    DONE = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'/><meta name='viewport' content='width=device-width,initial-scale=1'/>"
        "<title>Connected — GhostReelsAlpha</title>"
        "<style>body{margin:0;background:#0A0A0A;color:#E7E5E4;font-family:-apple-system,sans-serif;display:flex;min-height:100vh;"
        "align-items:center;justify-content:center;padding:24px;text-align:center}h1{font-size:22px;margin:0 0 8px}p{color:#A8A29E}</style></head>"
        "<body><div><h1>You're connected</h1><p>Return to GhostReelsAlpha — this window can close.</p></div>"
        "<script>try{window.location='frontend://connect?ok=1';}catch(e){}</script></body></html>"
    )
    FAIL = (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'/><meta name='viewport' content='width=device-width,initial-scale=1'/>"
        "<title>Couldn't connect — GhostReelsAlpha</title>"
        "<style>body{margin:0;background:#0A0A0A;color:#E7E5E4;font-family:-apple-system,sans-serif;display:flex;min-height:100vh;"
        "align-items:center;justify-content:center;padding:24px;text-align:center}h1{font-size:22px;margin:0 0 8px}p{color:#A8A29E}</style></head>"
        "<body><div><h1>Couldn't connect</h1><p>Close this window and try again from Settings.</p></div></body></html>"
    )

    @router.get("/connect/youtube")
    async def connect_youtube_start(user=Depends(S.current_user)):
        if not social.youtube_configured():
            return {"configured": False, "url": None, "message": social._setup_message("youtube")}
        return {"configured": True, "url": social.youtube_auth_url(_oauth_state(user["id"], "youtube"))}

    @router.get("/connect/instagram")
    async def connect_instagram_start(user=Depends(S.current_user)):
        if not social.instagram_configured():
            return {"configured": False, "url": None, "message": social._setup_message("instagram")}
        return {"configured": True, "url": social.instagram_auth_url(_oauth_state(user["id"], "instagram"))}

    @router.get("/connect/youtube/callback")
    async def connect_youtube_callback(code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
        if error or not code or not state:
            return HTMLResponse(FAIL, status_code=400)
        try:
            uid = _read_oauth_state(state, "youtube")
            tokens = await social.exchange_youtube_code(code)
            access = tokens.get("access_token") or ""
            title = await social.youtube_channel_title(access) if access else ""
            packed = social.dump_tokens(tokens)
            await S.db.users.update_one({"id": uid}, {"$set": {
                "youtube_token_enc": S.enc_key(packed, uid, "youtube"),
                "youtube_channel": (title or "YouTube")[:80],
            }})
            return HTMLResponse(DONE)
        except Exception:  # noqa: BLE001
            log.exception("YouTube OAuth callback failed")
            return HTMLResponse(FAIL, status_code=400)

    @router.get("/connect/instagram/callback")
    async def connect_instagram_callback(code: Optional[str] = None, state: Optional[str] = None, error: Optional[str] = None):
        if error or not code or not state:
            return HTMLResponse(FAIL, status_code=400)
        try:
            uid = _read_oauth_state(state, "instagram")
            tokens = await social.exchange_instagram_code(code)
            access = tokens.get("access_token") or ""
            ig_uid = str(tokens.get("user_id") or "")
            uname = await social.instagram_username(access, ig_uid) if access else ""
            packed = social.dump_tokens(tokens)
            await S.db.users.update_one({"id": uid}, {"$set": {
                "instagram_token_enc": S.enc_key(packed, uid, "instagram"),
                "instagram_username": (uname or "Instagram")[:80],
            }})
            return HTMLResponse(DONE)
        except Exception:  # noqa: BLE001
            log.exception("Instagram OAuth callback failed")
            return HTMLResponse(FAIL, status_code=400)

    @router.delete("/connect/youtube")
    async def disconnect_youtube(user=Depends(S.current_user)):
        await S.db.users.update_one({"id": user["id"]}, {"$set": {"youtube_token_enc": None, "youtube_channel": ""}})
        return S.public_user(await S.db.users.find_one({"id": user["id"]}))

    @router.delete("/connect/instagram")
    async def disconnect_instagram(user=Depends(S.current_user)):
        await S.db.users.update_one({"id": user["id"]}, {"$set": {"instagram_token_enc": None, "instagram_username": ""}})
        return S.public_user(await S.db.users.find_one({"id": user["id"]}))

    async def _youtube_access(user: dict) -> str:
        if not user.get("youtube_token_enc"):
            raise HTTPException(400, "Connect YouTube in Settings first.")
        try:
            raw = S.dec_key(user["youtube_token_enc"], user["id"], "youtube")
        except Exception:  # noqa: BLE001
            raise HTTPException(400, "YouTube login expired. Reconnect in Settings.")
        tokens = social.load_tokens(raw)
        access = tokens.get("access_token") or ""
        refresh = tokens.get("refresh_token") or ""
        if not access and not refresh:
            raise HTTPException(400, "Connect YouTube in Settings first.")
        if refresh:
            try:
                fresh = await social.refresh_youtube_token(refresh)
                access = fresh.get("access_token") or access
                packed = social.dump_tokens({**tokens, **fresh, "refresh_token": fresh.get("refresh_token") or refresh})
                await S.db.users.update_one({"id": user["id"]}, {
                    "$set": {"youtube_token_enc": S.enc_key(packed, user["id"], "youtube")}
                })
            except Exception:  # noqa: BLE001
                log.warning("YouTube refresh failed for user=%s", user.get("id"))
        return access

    async def _instagram_access(user: dict) -> tuple:
        if not user.get("instagram_token_enc"):
            raise HTTPException(400, "Connect Instagram in Settings first.")
        try:
            raw = S.dec_key(user["instagram_token_enc"], user["id"], "instagram")
        except Exception:  # noqa: BLE001
            raise HTTPException(400, "Instagram login expired. Reconnect in Settings.")
        tokens = social.load_tokens(raw)
        access = tokens.get("access_token") or ""
        ig_uid = str(tokens.get("user_id") or "")
        if not access or not ig_uid:
            raise HTTPException(400, "Connect Instagram in Settings first.")
        return access, ig_uid

    @router.post("/reels/{reel_id}/post")
    async def post_reel_social(reel_id: str, req: SocialPostRequest, user=Depends(S.current_user)):
        doc = await S.owned_reel(reel_id, user)
        if doc.get("status") != "ready" or not doc.get("video_path"):
            raise HTTPException(409, "Finish generating the reel first.")
        platform = (req.platform or "").strip().lower()
        title = (req.title or doc.get("title") or "GhostReelsAlpha").strip()[:100]
        caption = (req.caption or doc.get("script") or title).strip()[:2200]
        if platform not in ("youtube", "instagram"):
            raise HTTPException(400, "platform must be youtube or instagram")
        if pipeline.MOCK:
            return {"ok": True, "platform": platform, "mock": True, "id": f"mock-{platform}"}
        local = await S._ensure_local(reel_id, "mp4", "video_path", "video/mp4")
        video_bytes = _Path(local).read_bytes()
        if platform == "youtube":
            if not social.youtube_configured():
                raise HTTPException(503, social._setup_message("youtube"))
            access = await _youtube_access(user)
            result = await social.youtube_upload(access, video_bytes, title, caption, req.privacy or "public")
            vid = result.get("id") or ""
            url = f"https://youtu.be/{vid}" if vid else None
            return {"ok": True, "platform": "youtube", "id": vid, "url": url}
        if not social.instagram_configured():
            raise HTTPException(503, social._setup_message("instagram"))
        access, ig_uid = await _instagram_access(user)
        base = social.public_base()
        if not base or "localhost" in base:
            raise HTTPException(503, (
                "Instagram needs a public https video URL. Set PUBLIC_BASE_URL to your live backend "
                "(for example https://your-api.example.com) so Instagram can fetch the reel."
            ))
        sig = S.make_media_sig(reel_id)
        video_url = f"{base}/api/reels/{reel_id}/video?media_sig={sig}"
        result = await social.instagram_publish(access, ig_uid, video_url, caption)
        return {"ok": True, "platform": "instagram", "id": result.get("id")}
