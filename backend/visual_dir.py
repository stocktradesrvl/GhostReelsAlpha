"""User-controlled AI image count + visual direction (mood).

Imported by visual_boot so we do not rewrite server.py. Helpers are unit-tested
under REELS_MOCK with no LLM spend.
"""
from __future__ import annotations

from typing import Optional

from reels_config import IMAGE_COUNT_MAX, IMAGE_COUNT_MIN, IMAGE_DIRECTION_MAX, IMAGE_STYLE_MAP


def auto_scene_count(seconds: int) -> int:
    """Same formula as pipeline.scene_count: ~1 image per 10s, clamped 2–4."""
    return max(2, min(4, round((seconds or 30) / 10)))


def clamp_image_count(value) -> Optional[int]:
    """Persist a user count in 2–12, or None when omitted/invalid (means auto)."""
    if value is None or value == "":
        return None
    try:
        n = int(value)
    except (TypeError, ValueError):
        return None
    return max(IMAGE_COUNT_MIN, min(IMAGE_COUNT_MAX, n))


def resolve_scene_n(seconds: int, image_count=None) -> int:
    """Ken Burns / prompt count: user n when set, else auto from duration."""
    clamped = clamp_image_count(image_count)
    if clamped is None:
        return auto_scene_count(seconds)
    return clamped


def sanitize_direction(text) -> str:
    if not text:
        return ""
    cleaned = " ".join(str(text).split())
    return cleaned[:IMAGE_DIRECTION_MAX]


def compose_style_suffix(style_id: str = "cinematic", direction: str = "") -> str:
    base = IMAGE_STYLE_MAP.get(style_id, IMAGE_STYLE_MAP["cinematic"])["suffix"]
    d = sanitize_direction(direction)
    if d:
        return f"{base}. Visual direction: {d}"
    return base


def append_direction_to_suffix(style_suffix: str, direction: str = "") -> str:
    d = sanitize_direction(direction)
    if not d:
        return style_suffix or ""
    extra = f" Visual direction: {d}"
    current = style_suffix or ""
    if extra.lower() in current.lower() or d.lower() in current.lower():
        return current
    return f"{current}{extra}" if current else extra.strip()


def prompt_writer_instruction(n: int, direction: str = "", character_bible: str = "",
                              script: str = "") -> str:
    """The LLM ask used by generate_scene_prompts. Unit-tested for n + mood."""
    d = sanitize_direction(direction)
    look = (
        f"Mood and visual direction for EVERY prompt: {d}. Match this mood throughout. "
        if d else
        "Cinematic, photographic, dramatic lighting, "
    )
    char_note = (
        f"\n\nRecurring characters that MUST appear consistently (same face, hair, clothing "
        f"and style) whenever they are relevant to a beat:\n{character_bible}\n"
        f"When a character appears, describe them using these exact details so they look "
        f"identical across every scene."
        if character_bible else ""
    )
    return (
        f"For this short video narration, write exactly {n} vivid image-generation prompts, "
        f"one per key beat, that visually support the story. {look}vertical 9:16 composition. "
        f"Do NOT include any text/words/letters in the image. "
        f"Keep a consistent visual style across all prompts.{char_note}\n\n"
        f"Narration:\n{script}\n\n"
        f"Return ONLY a JSON array of {n} strings."
    )


def mock_scene_prompts(n: int, direction: str = "") -> list:
    d = sanitize_direction(direction)
    mood = f", mood {d}" if d else ""
    return [f"Mock cinematic vertical scene {i + 1} for the story{mood}" for i in range(n)]


async def generate_scene_prompts(script: str, n: int, character_bible: str = "",
                                 direction: str = "") -> list:
    """Drop-in replacement for pipeline.generate_scene_prompts with mood support."""
    import json
    import re

    import pipeline

    d = sanitize_direction(direction)
    n = max(IMAGE_COUNT_MIN, min(IMAGE_COUNT_MAX, int(n or 0) or auto_scene_count(30)))
    if pipeline.MOCK:
        return mock_scene_prompts(n, d)
    ask = prompt_writer_instruction(n, d, character_bible, script=script)
    raw = await pipeline._chat_text(
        f"prompts-{abs(hash(script)) % 100000}",
        "You turn video scripts into vivid cinematic image prompts.",
        ask,
    )
    prompts = []
    try:
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        prompts = json.loads(m.group(0)) if m else []
    except Exception:
        prompts = []
    prompts = [str(p).strip() for p in prompts if str(p).strip()][:n]
    while len(prompts) < n:
        extra = f" Mood: {d}." if d else ""
        prompts.append(f"Cinematic dramatic vertical scene illustrating: {script[:120]}{extra}")
    return prompts
