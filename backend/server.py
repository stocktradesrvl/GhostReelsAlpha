import logging
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
from fastapi import APIRouter, FastAPI, HTTPException
from fastapi.responses import FileResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from starlette.middleware.cors import CORSMiddleware

import pipeline
import storage_client
from reels_config import (
    BG_MAP,
    BG_MOTION_MAP,
    BG_MOTIONS,
    BG_THEMES,
    CAPTION_ANIM_MAP,
    CAPTION_ANIMS,
    CAPTION_FONT_MAP,
    CAPTION_FONTS,
    CAPTION_MAP,
    CAPTION_POSITION_MAP,
    CAPTION_POSITIONS,
    CAPTION_SIZE_MAP,
    CAPTION_SIZES,
    CAPTION_STYLES,
    MUSIC_MAP,
    MUSIC_TRACKS,
    VOICE_MAP,
    VOICE_SPEED_MAP,
    VOICE_SPEEDS,
    VOICES,
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

MEDIA_DIR = ROOT_DIR / "media"
MEDIA_DIR.mkdir(exist_ok=True)

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("reels")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class ScriptRequest(BaseModel):
    topic: str
    seconds: int = 30


class ReelSettings(BaseModel):
    seconds: int = 30
    visual_mode: str = "gradient"       # "gradient" | "ai"
    voice_id: str = "onyx"
    voice_speed: str = "normal"
    caption_style: str = "signal"
    caption_position: str = "center"
    caption_size: str = "m"
    caption_font: str = "barlow"
    caption_anim: str = "pop"
    bg_theme: str = "ember"
    bg_motion: str = "subtle"
    music_id: str = "none"
    music_volume: float = 0.13
    watermark: Optional[str] = None
    hook_enabled: bool = False
    endcard_text: Optional[str] = None
    custom_c1: Optional[str] = None
    custom_c2: Optional[str] = None


class CreateReelRequest(ReelSettings):
    title: Optional[str] = None
    input_mode: str = "topic"          # "topic" | "script"
    topic: Optional[str] = None
    script: Optional[str] = None


class BatchReelRequest(ReelSettings):
    topics: List[str] = []
    scheduled_at: Optional[str] = None  # ISO time; if future, reels wait until then


PUBLIC_FIELDS = {
    "id", "title", "input_mode", "topic", "script", "seconds", "visual_mode", "voice_id", "voice_speed",
    "caption_style", "caption_position", "caption_size", "caption_font", "caption_anim",
    "bg_theme", "bg_motion", "custom_c1", "custom_c2", "music_id", "music_volume", "watermark",
    "hook_enabled", "endcard_text", "views", "downloads", "scheduled_at",
    "status", "progress", "stage_label", "error",
    "duration", "word_count", "has_video", "created_at", "updated_at",
}


def validate_settings(s: ReelSettings):
    checks = [
        (s.voice_id, VOICE_MAP, "voice"),
        (s.voice_speed, VOICE_SPEED_MAP, "voice speed"),
        (s.caption_style, CAPTION_MAP, "caption style"),
        (s.caption_position, CAPTION_POSITION_MAP, "caption position"),
        (s.caption_size, CAPTION_SIZE_MAP, "caption size"),
        (s.caption_font, CAPTION_FONT_MAP, "caption font"),
        (s.caption_anim, CAPTION_ANIM_MAP, "caption animation"),
        (s.bg_motion, BG_MOTION_MAP, "background motion"),
        (s.music_id, MUSIC_MAP, "music track"),
    ]
    for value, table, label in checks:
        if value not in table:
            raise HTTPException(400, f"Unknown {label}")
    if s.bg_theme != "custom" and s.bg_theme not in BG_MAP:
        raise HTTPException(400, "Unknown background theme")
    if s.bg_theme == "custom":
        def _ok(h):
            h = (h or "").strip().lstrip("#")
            return len(h) == 6 and all(c in "0123456789abcdefABCDEF" for c in h)
        if not (_ok(s.custom_c1) and _ok(s.custom_c2)):
            raise HTTPException(400, "Custom theme needs two hex colours")


def build_reel_doc(s: ReelSettings, input_mode: str, topic, script, title: str) -> dict:
    reel_id = str(uuid.uuid4())
    return {
        "id": reel_id,
        "title": title,
        "input_mode": input_mode,
        "topic": topic,
        "script": script,
        "seconds": s.seconds,
        "visual_mode": s.visual_mode if s.visual_mode in ("gradient", "ai") else "gradient",
        "voice_id": s.voice_id,
        "voice_speed": s.voice_speed,
        "caption_style": s.caption_style,
        "caption_position": s.caption_position,
        "caption_size": s.caption_size,
        "caption_font": s.caption_font,
        "caption_anim": s.caption_anim,
        "bg_theme": s.bg_theme,
        "bg_motion": s.bg_motion,
        "custom_c1": (s.custom_c1 or None),
        "custom_c2": (s.custom_c2 or None),
        "music_id": s.music_id,
        "music_volume": max(0.0, min(1.0, float(s.music_volume))),
        "watermark": (s.watermark or "").strip()[:32] or None,
        "hook_enabled": bool(s.hook_enabled),
        "endcard_text": (s.endcard_text or "").strip()[:40] or None,
        "views": 0,
        "downloads": 0,
        "scheduled_at": None,
        "status": "queued",
        "progress": 0,
        "stage_label": "Queued",
        "error": None,
        "duration": None,
        "word_count": len(script.split()) if script else None,
        "has_video": False,
        "video_path": None,
        "thumb_path": None,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


def public_reel(doc: dict) -> dict:
    return {k: doc.get(k) for k in PUBLIC_FIELDS}


async def update_reel(reel_id: str, **fields):
    fields["updated_at"] = now_iso()
    await db.reels.update_one({"id": reel_id}, {"$set": fields})


# ---------------------------------------------------------------------------
# Pipeline orchestrator (runs in background)
# ---------------------------------------------------------------------------
async def run_pipeline(reel_id: str):
    workdir = pipeline.new_workdir()
    try:
        reel = await db.reels.find_one({"id": reel_id})
        if not reel:
            return

        script = reel.get("script")
        # Stage 1: script (topic mode without a script yet)
        if not script:
            await update_reel(reel_id, status="scripting", progress=10, stage_label="Writing script")
            script = await pipeline.generate_script(reel["topic"], reel.get("seconds", 30))
            await update_reel(reel_id, script=script, word_count=len(script.split()))

        # Stage 2: voiceover
        await update_reel(reel_id, status="voicing", progress=30, stage_label="Recording voiceover")
        audio_path = os.path.join(workdir, "voice.mp3")
        speed = VOICE_SPEED_MAP.get(reel.get("voice_speed", "normal"), VOICE_SPEED_MAP["normal"])["speed"]
        await pipeline.synth_voice(script, reel["voice_id"], audio_path, speed=speed)

        # Stage 3: captions
        await update_reel(reel_id, status="captioning", progress=55, stage_label="Aligning captions")
        words, duration = await pipeline.transcribe_words(audio_path)
        if not duration or duration <= 0:
            duration = max(3.0, len(script.split()) / pipeline.WORDS_PER_SEC)
        ass_path = os.path.join(workdir, "subs.ass")
        pipeline.build_ass(
            words, duration, reel["caption_style"], ass_path,
            position=reel.get("caption_position", "center"),
            size=reel.get("caption_size", "m"),
            watermark=reel.get("watermark") or "",
            hook_text=pipeline.hook_line(script) if reel.get("hook_enabled") else "",
            caption_font=reel.get("caption_font", "barlow"),
            endcard_text=reel.get("endcard_text") or "",
            caption_anim=reel.get("caption_anim", "pop"),
        )

        # Stage 4: render
        out_path = str(MEDIA_DIR / f"{reel_id}.mp4")
        thumb_path = str(MEDIA_DIR / f"{reel_id}.jpg")
        if reel.get("visual_mode") == "ai":
            await update_reel(reel_id, status="rendering", progress=66,
                              stage_label="Painting visuals", duration=round(duration, 2))
            n = pipeline.scene_count(reel.get("seconds", 30))
            prompts = await pipeline.generate_scene_prompts(script, n)
            images = await pipeline.generate_images(prompts, workdir)
            await update_reel(reel_id, status="rendering", progress=82, stage_label="Rendering video")
            await pipeline.render_video_images(
                audio_path, "subs.ass", images, duration, workdir, out_path,
                music_id=reel.get("music_id", "none"),
                music_volume=reel.get("music_volume", 0.13),
            )
        else:
            await update_reel(reel_id, status="rendering", progress=72,
                              stage_label="Rendering video", duration=round(duration, 2))
            await pipeline.render_video(
                audio_path, "subs.ass", reel["bg_theme"], duration, workdir, out_path,
                music_id=reel.get("music_id", "none"),
                music_volume=reel.get("music_volume", 0.13),
                bg_motion=reel.get("bg_motion", "subtle"),
                custom_colors=[reel.get("custom_c1"), reel.get("custom_c2")],
            )
        await pipeline.extract_thumbnail(out_path, thumb_path)

        # Stage 5: upload to durable object storage
        await update_reel(reel_id, status="uploading", progress=92, stage_label="Finishing up")
        with open(out_path, "rb") as f:
            video_bytes = f.read()
        vpath = f"{storage_client.APP_NAME}/reels/{reel_id}.mp4"
        await run_in_threadpool(storage_client.put_object, vpath, video_bytes, "video/mp4")
        tpath = None
        if os.path.exists(thumb_path):
            with open(thumb_path, "rb") as f:
                tpath = f"{storage_client.APP_NAME}/reels/{reel_id}.jpg"
                await run_in_threadpool(storage_client.put_object, tpath, f.read(), "image/jpeg")

        await update_reel(
            reel_id, status="ready", progress=100, stage_label="Ready",
            has_video=True, video_path=vpath, thumb_path=tpath, error=None,
        )
        logger.info("Reel %s ready (%.1fs)", reel_id, duration)
    except Exception as e:  # noqa: BLE001
        logger.exception("Pipeline failed for %s", reel_id)
        await update_reel(reel_id, status="failed", stage_label="Generation failed", error=str(e)[:400])
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@api_router.get("/")
async def root():
    return {"message": "Faceless AI Reels API"}


@api_router.get("/config")
async def get_config():
    return {
        "voices": VOICES,
        "voice_speeds": VOICE_SPEEDS,
        "caption_styles": CAPTION_STYLES,
        "caption_positions": CAPTION_POSITIONS,
        "caption_sizes": CAPTION_SIZES,
        "caption_fonts": CAPTION_FONTS,
        "caption_anims": CAPTION_ANIMS,
        "bg_themes": BG_THEMES,
        "bg_motions": BG_MOTIONS,
        "music_tracks": MUSIC_TRACKS,
    }


@api_router.post("/script")
async def make_script(req: ScriptRequest):
    if not req.topic.strip():
        raise HTTPException(400, "Topic is required")
    script = await pipeline.generate_script(req.topic.strip(), req.seconds)
    return {"script": script, "word_count": len(script.split())}


@api_router.get("/voices/{voice_id}/preview")
async def voice_preview(voice_id: str):
    if voice_id not in VOICE_MAP:
        raise HTTPException(404, "Unknown voice")
    local = MEDIA_DIR / f"voice_preview_{voice_id}.mp3"
    if not local.exists():
        await pipeline.synth_voice_sample(voice_id, str(local))
    return FileResponse(str(local), media_type="audio/mpeg",
                        headers={"Cache-Control": "public, max-age=86400"})


@api_router.post("/reels")
async def create_reel(req: CreateReelRequest):
    validate_settings(req)
    script = (req.script or "").strip() or None
    topic = (req.topic or "").strip() or None
    if req.input_mode == "script" and not script:
        raise HTTPException(400, "Script is required")
    if req.input_mode == "topic" and not (topic or script):
        raise HTTPException(400, "Topic is required")

    title = (req.title or "").strip() or ((script or topic or "Untitled")[:48].strip())
    doc = build_reel_doc(req, req.input_mode, topic, script, title)
    await db.reels.insert_one(doc)

    import asyncio
    asyncio.create_task(run_pipeline(doc["id"]))
    return public_reel(doc)


@api_router.post("/reels/batch")
async def create_reels_batch(req: BatchReelRequest):
    validate_settings(req)
    topics = [t.strip() for t in (req.topics or []) if t.strip()]
    if not topics:
        raise HTTPException(400, "At least one topic is required")
    if len(topics) > 12:
        raise HTTPException(400, "Up to 12 topics per batch")

    # Determine scheduling.
    sched_iso = None
    now = datetime.now(timezone.utc)
    if req.scheduled_at:
        try:
            when = datetime.fromisoformat(req.scheduled_at.replace("Z", "+00:00"))
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            if when > now:
                sched_iso = when.isoformat()
        except Exception:
            sched_iso = None

    import asyncio
    created = []
    for topic in topics:
        title = topic[:48].strip()
        doc = build_reel_doc(req, "topic", topic, None, title)
        if sched_iso:
            doc["status"] = "scheduled"
            doc["scheduled_at"] = sched_iso
            doc["stage_label"] = "Scheduled"
        await db.reels.insert_one(doc)
        if not sched_iso:
            asyncio.create_task(run_pipeline(doc["id"]))
        created.append(public_reel(doc))
    return {"created": created, "count": len(created), "scheduled": bool(sched_iso)}


@api_router.post("/reels/{reel_id}/view")
async def add_view(reel_id: str):
    res = await db.reels.update_one({"id": reel_id}, {"$inc": {"views": 1}})
    if res.matched_count == 0:
        raise HTTPException(404, "Reel not found")
    doc = await db.reels.find_one({"id": reel_id})
    return {"views": doc.get("views", 0)}


@api_router.post("/reels/{reel_id}/download")
async def add_download(reel_id: str):
    res = await db.reels.update_one({"id": reel_id}, {"$inc": {"downloads": 1}})
    if res.matched_count == 0:
        raise HTTPException(404, "Reel not found")
    doc = await db.reels.find_one({"id": reel_id})
    return {"downloads": doc.get("downloads", 0)}


@api_router.get("/reels")
async def list_reels():
    docs = await db.reels.find().sort("created_at", -1).to_list(200)
    return [public_reel(d) for d in docs]


@api_router.get("/reels/{reel_id}")
async def get_reel(reel_id: str):
    doc = await db.reels.find_one({"id": reel_id})
    if not doc:
        raise HTTPException(404, "Reel not found")
    return public_reel(doc)


@api_router.delete("/reels/{reel_id}")
async def delete_reel(reel_id: str):
    doc = await db.reels.find_one({"id": reel_id})
    if not doc:
        raise HTTPException(404, "Reel not found")
    await db.reels.delete_one({"id": reel_id})
    for p in (MEDIA_DIR / f"{reel_id}.mp4", MEDIA_DIR / f"{reel_id}.jpg"):
        if p.exists():
            p.unlink(missing_ok=True)
    return {"ok": True}


async def _ensure_local(reel_id: str, ext: str, storage_field: str, content_type: str):
    local = MEDIA_DIR / f"{reel_id}.{ext}"
    if local.exists():
        return local
    doc = await db.reels.find_one({"id": reel_id})
    if not doc or not doc.get(storage_field):
        raise HTTPException(404, "File not found")
    content, _ = await run_in_threadpool(storage_client.get_object, doc[storage_field])
    local.write_bytes(content)
    return local


@api_router.get("/reels/{reel_id}/video")
async def get_video(reel_id: str):
    local = await _ensure_local(reel_id, "mp4", "video_path", "video/mp4")
    return FileResponse(str(local), media_type="video/mp4", filename=f"{reel_id}.mp4")


@api_router.get("/reels/{reel_id}/thumb")
async def get_thumb(reel_id: str):
    local = await _ensure_local(reel_id, "jpg", "thumb_path", "image/jpeg")
    return FileResponse(str(local), media_type="image/jpeg")


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def scheduler_loop():
    import asyncio
    while True:
        try:
            now = datetime.now(timezone.utc).isoformat()
            due = await db.reels.find(
                {"status": "scheduled", "scheduled_at": {"$lte": now}}
            ).to_list(50)
            for d in due:
                await update_reel(d["id"], status="queued", stage_label="Queued", progress=0)
                asyncio.create_task(run_pipeline(d["id"]))
                logger.info("Scheduled reel %s promoted to queue", d["id"])
        except Exception as e:  # noqa: BLE001
            logger.warning("scheduler error: %s", e)
        await asyncio.sleep(30)


@app.on_event("startup")
async def startup():
    import asyncio
    try:
        await run_in_threadpool(storage_client.init_storage)
        logger.info("Object storage initialised")
    except Exception as e:  # noqa: BLE001
        logger.warning("Object storage init failed (will retry on demand): %s", e)
    asyncio.create_task(scheduler_loop())


@app.on_event("shutdown")
async def shutdown():
    client.close()
