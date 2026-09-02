"""Lock remaining reel media behind owner auth, add export + social routes.

Imported from storage_client so it runs before FastAPI routes are registered.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import os
import sys
import time
from pathlib import Path as _Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

import pipeline
import social
import storage_client
from reels_config import ASPECT_MAP, ASPECTS, VOICE_MAP, VOICES

log = logging.getLogger("reels.lock")

_ORIG_INCLUDE = FastAPI.include_router
_APPLIED = False


def _el_key(S, user: dict) -> str:
    if not user or user.get("key_mode", "own") == "builtin":
        return ""
    blob = user.get("elevenlabs_key_enc")
    if not blob:
        return ""
    try:
        return S.dec_key(blob, user["id"], "elevenlabs")
    except Exception:  # noqa: BLE001
        return ""


def _patch_helpers(S):
    _orig_saved = S.saved_keys
    _orig_public = S.public_user
    _orig_classify = S.classify_error
    _orig_apply = S.apply_owner_keys
    _orig_enforce = S.enforce_quota
    _orig_consume = S.consume_quota
    _orig_public_reel = S.public_reel

    def public_user(u: dict) -> dict:
        out = _orig_public(u)
        el = ""
        if u.get("elevenlabs_key_enc"):
            try:
                el = S.dec_key(u["elevenlabs_key_enc"], u["id"], "elevenlabs")
            except Exception:  # noqa: BLE001
                el = ""
        out["elevenlabs_key_set"] = bool(u.get("elevenlabs_key_enc"))
        out["elevenlabs_key_masked"] = S._mask_key(el)
        oa, gk = _orig_saved(u)
        mode = u.get("key_mode", "own")
        out["has_own_key"] = bool((oa or gk or el)) and mode == "own"
        out["youtube_connected"] = bool(u.get("youtube_token_enc"))
        out["youtube_channel"] = u.get("youtube_channel") or ""
        out["instagram_connected"] = bool(u.get("instagram_token_enc"))
        out["instagram_username"] = u.get("instagram_username") or ""
        return out

    async def enforce_quota(user: dict):
        await _orig_enforce(user)
        # orig already passed; if it raised we're out. EL-only users: orig may 402.
        # Re-run: if orig would 402 but EL is set, allow.
        # Can't un-raise. Instead replace fully:
    async def enforce_quota(user: dict):
        oa, gk = S.user_keys(user)
        el = _el_key(S, user)
        if oa or gk or el or user.get("is_subscribed") or S.is_admin_user(user):
            return
        if user.get("free_used", 0) < S.FREE_LIMIT:
            return
        raise HTTPException(402, (
            f"You've used your {S.FREE_LIMIT} free reels. Add your own OpenAI, Google, or ElevenLabs key "
            f"in Settings, or subscribe, to keep generating."
        ))

    async def consume_quota(user: dict):
        oa, gk = S.user_keys(user)
        el = _el_key(S, user)
        if not (oa or gk or el) and not user.get("is_subscribed") and not S.is_admin_user(user):
            await S.db.users.update_one({"id": user["id"]}, {"$inc": {"free_used": 1}})

    async def apply_owner_keys(reel: dict):
        oa = gk = el = ""
        if reel.get("user_id"):
            owner = await S.db.users.find_one({"id": reel["user_id"]})
            if owner:
                oa, gk = S.user_keys(owner)
                el = _el_key(S, owner)
        pipeline.set_user_keys(oa, gk, el)

    def classify_error(exc) -> tuple:
        if isinstance(exc, pipeline.OwnKeyError) and getattr(exc, "provider", "") == "elevenlabs":
            msg = str(exc.original) or ""
            if __import__("re").search(r"invalid|unauthorized|permission denied|\b401\b|\b403\b", msg, __import__("re").I):
                return "key", (
                    "Your ElevenLabs key was rejected. Re-check it in Settings → AI keys, "
                    "or pick an OpenAI voice."
                )
            if __import__("re").search(r"budget|exceeded|insufficient|quota|credit|billing|rate limit|\b429\b", msg, __import__("re").I):
                return "key", (
                    "Your ElevenLabs account is out of credits or hit its rate limit "
                    "(this is YOUR key). Add billing at elevenlabs.io/app/billing, or pick an OpenAI voice."
                )
            return "generic", (f"ElevenLabs error: {msg[:220]}" or "Your key errored.")
        return _orig_classify(exc)

    def public_reel(doc: dict) -> dict:
        out = _orig_public_reel(doc)
        out["exports"] = doc.get("exports") or {}
        return out

    S.public_user = public_user
    S.enforce_quota = enforce_quota
    S.consume_quota = consume_quota
    S.apply_owner_keys = apply_owner_keys
    S.classify_error = classify_error
    S.public_reel = public_reel
    S.PUBLIC_FIELDS = set(S.PUBLIC_FIELDS) | {"exports"}

    def make_media_sig(reel_id: str, ttl: int = 2700) -> str:
        exp = int(time.time()) + int(ttl)
        sig = hmac.new(S.AES_KEY, f"{reel_id}:{exp}".encode(), hashlib.sha256).hexdigest()
        return f"{exp}.{sig}"

    def check_media_sig(reel_id: str, token: str) -> bool:
        try:
            exp_s, sig = (token or "").split(".", 1)
            exp = int(exp_s)
            if exp < int(time.time()):
                return False
            expected = hmac.new(S.AES_KEY, f"{reel_id}:{exp}".encode(), hashlib.sha256).hexdigest()
            return hmac.compare_digest(sig, expected)
        except Exception:  # noqa: BLE001
            return False

    S.make_media_sig = make_media_sig
    S.check_media_sig = check_media_sig

    async def load_user_from_token(token: str):
        if not token:
            raise HTTPException(401, "Not authenticated")
        try:
            import jwt
            payload = jwt.decode(token, S.JWT_SECRET, algorithms=[S.JWT_ALG])
            uid = payload.get("sub")
        except Exception:  # noqa: BLE001
            raise HTTPException(401, "Not authenticated")
        user = await S.db.users.find_one({"id": uid})
        if not user:
            raise HTTPException(401, "Not authenticated")
        return user

    S.load_user_from_token = load_user_from_token


def _drop_paths(router, paths):
    keep = []
    for r in list(router.routes):
        p = getattr(r, "path", None) or getattr(r, "path_format", "")
        if p in paths:
            continue
        keep.append(r)
    router.routes[:] = keep


def apply_lock(router):
    global _APPLIED
    if _APPLIED:
        return
    S = sys.modules.get("server")
    if S is None or router is not getattr(S, "api_router", None):
        return
    _APPLIED = True
    _patch_helpers(S)

    from fastapi.security import HTTPAuthorizationCredentials

    async def media_user(
        cred: HTTPAuthorizationCredentials = Depends(S.bearer),
        access_token: Optional[str] = Query(None),
    ):
        token = (cred.credentials if cred else None) or access_token
        if not token:
            raise HTTPException(401, "Not authenticated")
        return await S.load_user_from_token(token)

    async def optional_media_user(
        cred: HTTPAuthorizationCredentials = Depends(S.bearer),
        access_token: Optional[str] = Query(None),
    ):
        token = (cred.credentials if cred else None) or access_token
        if not token:
            return None
        try:
            return await S.load_user_from_token(token)
        except HTTPException:
            return None

    S.media_user = media_user
    S.optional_media_user = optional_media_user

    _drop_paths(router, {
        "/config",
        "/voices/{voice_id}/preview",
        "/reels/{reel_id}/video",
        "/reels/{reel_id}/thumb",
        "/reels/{reel_id}/view",
        "/reels/{reel_id}/download",
        "/reels/{reel_id}/scene/{index}/image",
        "/settings",
        "/settings/test",
    })

    @router.get("/config")
    async def get_config():
        from reels_config import (
            BG_MOTIONS, BG_THEMES, CAPTION_ANIMS, CAPTION_FONTS, CAPTION_POSITIONS,
            CAPTION_SIZES, CAPTION_STYLES, IMAGE_STYLES, MUSIC_TRACKS, VOICE_SPEEDS,
        )
        return {
            "voices": [{k: v.get(k) for k in ("id", "name", "tagline", "engine") if k in v} for v in VOICES],
            "voice_speeds": VOICE_SPEEDS,
            "image_styles": IMAGE_STYLES,
            "caption_styles": CAPTION_STYLES,
            "caption_positions": CAPTION_POSITIONS,
            "caption_sizes": CAPTION_SIZES,
            "caption_fonts": CAPTION_FONTS,
            "caption_anims": CAPTION_ANIMS,
            "bg_themes": BG_THEMES,
            "bg_motions": BG_MOTIONS,
            "music_tracks": MUSIC_TRACKS,
            "aspects": ASPECTS,
        }

    @router.get("/voices/{voice_id}/preview")
    async def voice_preview(voice_id: str, user=Depends(media_user)):
        if voice_id not in VOICE_MAP:
            raise HTTPException(404, "Unknown voice")
        catalog = VOICE_MAP[voice_id]
        oa, gk = S.user_keys(user)
        el = _el_key(S, user)
        pipeline.set_user_keys(oa, gk, el)
        try:
            if catalog.get("engine") == "elevenlabs" and not el and not pipeline.MOCK:
                raise HTTPException(400, "Add your ElevenLabs key in Settings to preview this voice.")
            suffix = f"{user['id'][:8]}_" if catalog.get("engine") == "elevenlabs" else ""
            local = S.MEDIA_DIR / f"voice_preview_{suffix}{voice_id}.mp3"
            if not local.exists():
                await pipeline.synth_voice_sample(voice_id, str(local))
            return FileResponse(str(local), media_type="audio/mpeg",
                                headers={"Cache-Control": "public, max-age=86400"})
        except HTTPException:
            raise
        except pipeline.OwnKeyError as e:
            code, friendly = S.classify_error(e)
            raise HTTPException(402 if code in ("budget", "key") else 500, friendly)
        finally:
            pipeline.set_user_keys("", "", "")

    @router.post("/reels/{reel_id}/view")
    async def add_view(reel_id: str, user=Depends(S.current_user)):
        await S.owned_reel(reel_id, user)
        res = await S.db.reels.update_one({"id": reel_id, "user_id": user["id"]}, {"$inc": {"views": 1}})
        if res.matched_count == 0:
            raise HTTPException(404, "Reel not found")
        doc = await S.db.reels.find_one({"id": reel_id})
        return {"views": doc.get("views", 0)}

    @router.post("/reels/{reel_id}/download")
    async def add_download(reel_id: str, user=Depends(S.current_user)):
        await S.owned_reel(reel_id, user)
        res = await S.db.reels.update_one({"id": reel_id, "user_id": user["id"]}, {"$inc": {"downloads": 1}})
        if res.matched_count == 0:
            raise HTTPException(404, "Reel not found")
        doc = await S.db.reels.find_one({"id": reel_id})
        return {"downloads": doc.get("downloads", 0)}

    @router.get("/reels/{reel_id}/video")
    async def get_video(reel_id: str, aspect: Optional[str] = Query(None),
                       media_sig: Optional[str] = Query(None),
                       user=Depends(optional_media_user)):
        if media_sig and S.check_media_sig(reel_id, media_sig):
            doc = await S.db.reels.find_one({"id": reel_id})
            if not doc:
                raise HTTPException(404, "Reel not found")
        elif user:
            doc = await S.owned_reel(reel_id, user)
        else:
            raise HTTPException(401, "Not authenticated")
        aspect_id = aspect if aspect in ASPECT_MAP else "9:16"
        if aspect_id != "9:16":
            local = S.MEDIA_DIR / f"{reel_id}_{aspect_id.replace(':', 'x')}.mp4"
            if not local.exists():
                exp = (doc.get("exports") or {}).get(aspect_id) or {}
                if not exp.get("video_path"):
                    raise HTTPException(404, "That size isn't ready yet. Tap the size to export it first.")
                content, _ = await run_in_threadpool(storage_client.get_object, exp["video_path"])
                local.write_bytes(content)
            return FileResponse(str(local), media_type="video/mp4",
                                filename=f"{reel_id}_{aspect_id.replace(':', 'x')}.mp4")
        local = await S._ensure_local(reel_id, "mp4", "video_path", "video/mp4")
        return FileResponse(str(local), media_type="video/mp4", filename=f"{reel_id}.mp4")

    @router.get("/reels/{reel_id}/thumb")
    async def get_thumb(reel_id: str, user=Depends(media_user)):
        await S.owned_reel(reel_id, user)
        local = await S._ensure_local(reel_id, "jpg", "thumb_path", "image/jpeg")
        return FileResponse(str(local), media_type="image/jpeg")

    @router.get("/reels/{reel_id}/scene/{index}/image")
    async def get_scene_image(reel_id: str, index: int, user=Depends(media_user)):
        doc = await S.owned_reel(reel_id, user)
        scenes = (doc or {}).get("scenes") or []
        if index < 0 or index >= len(scenes):
            raise HTTPException(404, "Scene not found")
        local = S.MEDIA_DIR / f"scene_{reel_id}_{index}.png"
        if not local.exists():
            content, _ = await run_in_threadpool(storage_client.get_object, scenes[index]["image_path"])
            local.write_bytes(content)
        return FileResponse(str(local), media_type="image/png", headers={"Cache-Control": "no-store"})

    class SettingsUpdate(BaseModel):
        openai_key: Optional[str] = None
        google_key: Optional[str] = None
        elevenlabs_key: Optional[str] = None
        brand_handle: Optional[str] = None
        key_mode: Optional[str] = None

    class TestKeysRequest(BaseModel):
        openai_key: Optional[str] = None
        google_key: Optional[str] = None
        elevenlabs_key: Optional[str] = None

    class ExportRequest(BaseModel):
        aspect: str = "9:16"

    class SocialPostRequest(BaseModel):
        platform: str
        title: Optional[str] = None
        caption: Optional[str] = None
        privacy: Optional[str] = "public"

    @router.get("/settings")
    async def get_settings(user=Depends(S.current_user)):
        return S.public_user(user)

    @router.put("/settings")
    async def update_settings(req: SettingsUpdate, user=Depends(S.current_user)):
        upd = {}
        if req.openai_key is not None:
            upd["openai_key_enc"] = S.enc_key(req.openai_key.strip(), user["id"], "openai") if req.openai_key.strip() else None
        if req.google_key is not None:
            upd["google_key_enc"] = S.enc_key(req.google_key.strip(), user["id"], "google") if req.google_key.strip() else None
        if req.elevenlabs_key is not None:
            upd["elevenlabs_key_enc"] = S.enc_key(req.elevenlabs_key.strip(), user["id"], "elevenlabs") if req.elevenlabs_key.strip() else None
        if req.brand_handle is not None:
            upd["brand_handle"] = req.brand_handle.strip()[:40]
        if req.key_mode is not None:
            upd["key_mode"] = "builtin" if req.key_mode == "builtin" else "own"
        if upd:
            await S.db.users.update_one({"id": user["id"]}, {"$set": upd})
        fresh = await S.db.users.find_one({"id": user["id"]})
        return S.public_user(fresh)

    @router.post("/settings/test")
    async def test_keys(req: TestKeysRequest, user=Depends(S.current_user)):
        out = {}
        if req.openai_key and req.openai_key.strip():
            try:
                await pipeline.validate_openai_key(req.openai_key.strip())
                out["openai"] = {"ok": True, "message": "Valid — ready to save"}
            except Exception:  # noqa: BLE001
                out["openai"] = {"ok": False, "message": "OpenAI rejected this key"}
        if req.google_key and req.google_key.strip():
            try:
                await run_in_threadpool(pipeline.validate_google_key, req.google_key.strip())
                out["google"] = {"ok": True, "message": "Valid — ready to save"}
            except Exception:  # noqa: BLE001
                out["google"] = {"ok": False, "message": "Google rejected this key"}
        if req.elevenlabs_key and req.elevenlabs_key.strip():
            try:
                await pipeline.validate_elevenlabs_key(req.elevenlabs_key.strip())
                out["elevenlabs"] = {"ok": True, "message": "Valid — ready to save"}
            except Exception:  # noqa: BLE001
                out["elevenlabs"] = {"ok": False, "message": "ElevenLabs rejected this key"}
        return out

    from lock_social import register as register_social
    register_social(S, router, media_user, optional_media_user)

    log.info("lock_boot: owner-scoped media, ElevenLabs, aspect export, YouTube/Instagram routes installed")


def _include(self, router, *a, **kw):
    try:
        apply_lock(router)
    except Exception:  # noqa: BLE001
        log.exception("lock_boot.apply_lock failed")
    return _ORIG_INCLUDE(self, router, *a, **kw)


FastAPI.include_router = _include
