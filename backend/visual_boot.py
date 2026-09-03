"""Boot hook: user-picked AI image count, mood/direction, extra styles.

Imported from storage_client (before lock_boot) so apply_lock runs, then we
add image_count/image_direction to request models and wrap the pipeline.
Does not rewrite server.py or weaken auth/quota/RevenueCat.
"""
from __future__ import annotations

import contextvars
import logging
import sys
from typing import Optional

from fastapi import Depends, FastAPI
from pydantic import Field, create_model

import pipeline
import visual_dir

log = logging.getLogger("reels.visual")

_CTX_COUNT: contextvars.ContextVar = contextvars.ContextVar("image_count", default=None)
_CTX_DIR: contextvars.ContextVar = contextvars.ContextVar("image_direction", default="")

_ORIG_INCLUDE = FastAPI.include_router
_APPLIED = False

_orig_scene_count = pipeline.scene_count
_orig_images = pipeline.generate_images


def scene_count(seconds: int) -> int:
    return visual_dir.resolve_scene_n(seconds, _CTX_COUNT.get())


async def generate_scene_prompts(script: str, n: int, character_bible: str = "",
                                 direction: str = "") -> list:
    d = direction or _CTX_DIR.get() or ""
    return await visual_dir.generate_scene_prompts(
        script, n, character_bible=character_bible, direction=d,
    )


async def generate_images(prompts: list, workdir: str, style_suffix: str = "",
                          character_bible: str = "") -> list:
    suffix = visual_dir.append_direction_to_suffix(style_suffix, _CTX_DIR.get() or "")
    return await _orig_images(prompts, workdir, style_suffix=suffix, character_bible=character_bible)


pipeline.scene_count = scene_count
pipeline.generate_scene_prompts = generate_scene_prompts
pipeline.generate_images = generate_images
pipeline.resolve_scene_n = visual_dir.resolve_scene_n
pipeline.clamp_image_count = visual_dir.clamp_image_count
pipeline.compose_style_suffix = visual_dir.compose_style_suffix
pipeline.auto_scene_count = visual_dir.auto_scene_count
pipeline._orig_scene_count = _orig_scene_count


def _drop_method(router, path: str, method: str) -> None:
    keep = []
    for r in list(router.routes):
        p = getattr(r, "path", None) or getattr(r, "path_format", "")
        methods = getattr(r, "methods", None) or set()
        if p == path and method in methods:
            continue
        keep.append(r)
    router.routes[:] = keep


def apply_visual(router) -> None:
    global _APPLIED
    if _APPLIED:
        return
    S = sys.modules.get("server")
    if S is None or router is not getattr(S, "api_router", None):
        return
    _APPLIED = True

    ExtraFields = dict(
        image_count=(Optional[int], Field(default=None)),
        image_direction=(Optional[str], Field(default="")),
    )
    ReelX = create_model("ReelSettings", __base__=S.ReelSettings, **ExtraFields)
    CreateX = create_model("CreateReelRequest", __base__=S.CreateReelRequest, **ExtraFields)
    BatchX = create_model("BatchReelRequest", __base__=S.BatchReelRequest, **ExtraFields)
    SeriesX = create_model("SeriesCreate", __base__=S.SeriesCreate, **ExtraFields)
    S.ReelSettings = ReelX
    S.CreateReelRequest = CreateX
    S.BatchReelRequest = BatchX
    S.SeriesCreate = SeriesX
    S.PUBLIC_FIELDS = set(S.PUBLIC_FIELDS) | {"image_count", "image_direction"}

    _orig_build = S.build_reel_doc

    def build_reel_doc(s, *a, **kw):
        doc = _orig_build(s, *a, **kw)
        doc["image_count"] = visual_dir.clamp_image_count(getattr(s, "image_count", None))
        doc["image_direction"] = visual_dir.sanitize_direction(getattr(s, "image_direction", "") or "")
        return doc

    S.build_reel_doc = build_reel_doc

    _orig_run = S.run_pipeline

    async def run_pipeline(reel_id: str):
        reel = await S.db.reels.find_one({"id": reel_id})
        t1 = _CTX_COUNT.set(None if not reel else reel.get("image_count"))
        t2 = _CTX_DIR.set("" if not reel else (reel.get("image_direction") or ""))
        try:
            return await _orig_run(reel_id)
        finally:
            _CTX_COUNT.reset(t1)
            _CTX_DIR.reset(t2)

    S.run_pipeline = run_pipeline

    _orig_regen = S.regenerate_scene_task

    async def regenerate_scene_task(reel_id: str, index: int, prompt: str = None):
        reel = await S.db.reels.find_one({"id": reel_id})
        t2 = _CTX_DIR.set("" if not reel else (reel.get("image_direction") or ""))
        try:
            return await _orig_regen(reel_id, index, prompt)
        finally:
            _CTX_DIR.reset(t2)

    S.regenerate_scene_task = regenerate_scene_task

    _drop_method(router, "/reels", "POST")
    _drop_method(router, "/reels/batch", "POST")
    _drop_method(router, "/series", "POST")
    _drop_method(router, "/reels/{reel_id}/scenes", "GET")

    @router.post("/reels")
    async def create_reel(req: CreateX, user=Depends(S.current_user)):
        S.moderate_text(getattr(req, "image_direction", None) or "")
        return await S.create_reel(req, user)

    @router.post("/reels/batch")
    async def create_reels_batch(req: BatchX, user=Depends(S.current_user)):
        S.moderate_text(getattr(req, "image_direction", None) or "")
        return await S.create_reels_batch(req, user)

    @router.post("/series")
    async def create_series(req: SeriesX, user=Depends(S.current_user)):
        S.moderate_text(getattr(req, "image_direction", None) or "")
        return await S.create_series(req, user)

    @router.get("/reels/{reel_id}/scenes")
    async def get_scenes(reel_id: str, user=Depends(S.current_user)):
        doc = await S.owned_reel(reel_id, user)
        scenes = doc.get("scenes") or []
        editable = bool(doc.get("visual_mode") == "ai" and doc.get("audio_path") and scenes)
        return {
            "editable": editable,
            "status": doc.get("status"),
            "image_direction": doc.get("image_direction") or "",
            "image_style": doc.get("image_style") or "cinematic",
            "scenes": [
                {"index": i, "prompt": s.get("prompt", ""),
                 "image_url": f"/api/reels/{reel_id}/scene/{i}/image"}
                for i, s in enumerate(scenes)
            ],
        }

    log.info("visual_boot: image_count + image_direction + extra styles installed")


def _include(self, router, *a, **kw):
    try:
        apply_visual(router)
    except Exception:  # noqa: BLE001
        log.exception("visual_boot.apply_visual failed")
    return _ORIG_INCLUDE(self, router, *a, **kw)


FastAPI.include_router = _include
