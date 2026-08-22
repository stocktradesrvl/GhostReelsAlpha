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
    BG_THEMES,
    CAPTION_MAP,
    CAPTION_POSITION_MAP,
    CAPTION_POSITIONS,
    CAPTION_SIZE_MAP,
    CAPTION_SIZES,
    CAPTION_STYLES,
    MUSIC_MAP,
    MUSIC_TRACKS,
    VOICE_MAP,
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


class CreateReelRequest(BaseModel):
    title: Optional[str] = None
    input_mode: str = "topic"          # "topic" | "script"
    topic: Optional[str] = None
    script: Optional[str] = None
    seconds: int = 30
    voice_id: str = "onyx"
    caption_style: str = "signal"
    caption_position: str = "center"
    caption_size: str = "m"
    bg_theme: str = "ember"
    music_id: str = "none"
    watermark: Optional[str] = None


PUBLIC_FIELDS = {
    "id", "title", "input_mode", "topic", "script", "seconds", "voice_id",
    "caption_style", "caption_position", "caption_size", "bg_theme", "music_id",
    "watermark", "status", "progress", "stage_label", "error",
    "duration", "word_count", "has_video", "created_at", "updated_at",
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
        await pipeline.synth_voice(script, reel["voice_id"], audio_path)

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
        )

        # Stage 4: render
        await update_reel(reel_id, status="rendering", progress=72, stage_label="Rendering video",
                          duration=round(duration, 2))
        out_path = str(MEDIA_DIR / f"{reel_id}.mp4")
        thumb_path = str(MEDIA_DIR / f"{reel_id}.jpg")
        await pipeline.render_video(
            audio_path, "subs.ass", reel["bg_theme"], duration, workdir, out_path,
            music_id=reel.get("music_id", "none"),
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
        "caption_styles": CAPTION_STYLES,
        "caption_positions": CAPTION_POSITIONS,
        "caption_sizes": CAPTION_SIZES,
        "bg_themes": BG_THEMES,
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
    if req.voice_id not in VOICE_MAP:
        raise HTTPException(400, "Unknown voice")
    if req.caption_style not in CAPTION_MAP:
        raise HTTPException(400, "Unknown caption style")
    if req.caption_position not in CAPTION_POSITION_MAP:
        raise HTTPException(400, "Unknown caption position")
    if req.caption_size not in CAPTION_SIZE_MAP:
        raise HTTPException(400, "Unknown caption size")
    if req.bg_theme not in BG_MAP:
        raise HTTPException(400, "Unknown background theme")
    if req.music_id not in MUSIC_MAP:
        raise HTTPException(400, "Unknown music track")

    script = (req.script or "").strip() or None
    topic = (req.topic or "").strip() or None
    if req.input_mode == "script" and not script:
        raise HTTPException(400, "Script is required")
    if req.input_mode == "topic" and not (topic or script):
        raise HTTPException(400, "Topic is required")

    reel_id = str(uuid.uuid4())
    title = (req.title or "").strip() or (
        (script or topic or "Untitled")[:48].strip()
    )
    doc = {
        "id": reel_id,
        "title": title,
        "input_mode": req.input_mode,
        "topic": topic,
        "script": script,
        "seconds": req.seconds,
        "voice_id": req.voice_id,
        "caption_style": req.caption_style,
        "caption_position": req.caption_position,
        "caption_size": req.caption_size,
        "bg_theme": req.bg_theme,
        "music_id": req.music_id,
        "watermark": (req.watermark or "").strip()[:32] or None,
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
    await db.reels.insert_one(doc)

    import asyncio
    asyncio.create_task(run_pipeline(reel_id))
    return public_reel(doc)


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


@app.on_event("startup")
async def startup():
    try:
        await run_in_threadpool(storage_client.init_storage)
        logger.info("Object storage initialised")
    except Exception as e:  # noqa: BLE001
        logger.warning("Object storage init failed (will retry on demand): %s", e)


@app.on_event("shutdown")
async def shutdown():
    client.close()
