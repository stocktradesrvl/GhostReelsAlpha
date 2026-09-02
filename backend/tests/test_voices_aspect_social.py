"""Local tests (no live LLM/TTS spend): voice catalog, OpenAI fallback, multi-aspect
synthetic render, social helpers. Safe to run with REELS_MOCK=1.
"""
import os
from pathlib import Path

import pytest

from reels_config import ASPECT_MAP, ELEVENLABS_VOICES, VOICE_MAP, VOICES
import social


def test_catalog_includes_elevenlabs_and_openai():
    ids = {v["id"] for v in VOICES}
    assert {"onyx", "nova"}.issubset(ids)
    assert {"el_rachel", "el_josh"}.issubset(ids)
    assert VOICE_MAP["el_rachel"]["engine"] == "elevenlabs"
    assert VOICE_MAP["onyx"]["engine"] == "openai"
    assert all("el_id" in v for v in ELEVENLABS_VOICES)
    # public catalog ids, not secrets
    assert VOICE_MAP["el_rachel"]["el_id"] == "21m00Tcm4TlvDq8ikWAM"


def test_aspects_locked():
    assert set(ASPECT_MAP) == {"9:16", "1:1", "16:9"}
    assert ASPECT_MAP["9:16"]["width"] == 1080 and ASPECT_MAP["9:16"]["height"] == 1920
    assert ASPECT_MAP["1:1"]["width"] == 1080 and ASPECT_MAP["1:1"]["height"] == 1080
    assert ASPECT_MAP["16:9"]["width"] == 1920 and ASPECT_MAP["16:9"]["height"] == 1080


def test_social_token_roundtrip_never_includes_raw_in_helpers():
    packed = social.dump_tokens({
        "access_token": "ya29.secret-token",
        "refresh_token": "1//refresh",
        "expires_in": 3600,
        "user_id": "123",
        "noise": "drop-me",
    })
    data = social.load_tokens(packed)
    assert data["access_token"] == "ya29.secret-token"
    assert "noise" not in data
    assert "/api/connect/youtube/callback" in social.youtube_redirect() or os.environ.get("YOUTUBE_REDIRECT_URI")
    assert "/api/connect/instagram/callback" in social.instagram_redirect() or os.environ.get("INSTAGRAM_REDIRECT_URI")


def test_setup_messages_name_env_vars():
    yt = social._setup_message("youtube")
    ig = social._setup_message("instagram")
    assert "GOOGLE_OAUTH_CLIENT_ID" in yt and "GOOGLE_OAUTH_CLIENT_SECRET" in yt
    assert "META_APP_ID" in ig and "META_APP_SECRET" in ig


def test_elevenlabs_falls_back_to_openai_without_key():
    os.environ.setdefault("EMERGENT_LLM_KEY", "test-not-used")
    os.environ.setdefault("REELS_MOCK", "1")
    try:
        import pipeline
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"pipeline deps not installed: {e}")
    pipeline.set_user_keys("", "", "")
    v = pipeline.resolve_voice("el_rachel")
    assert v["engine"] == "openai"
    pipeline.set_user_keys("", "", "sk_test_not_real")
    v = pipeline.resolve_voice("el_rachel")
    assert v["engine"] == "elevenlabs" and v["id"] == "el_rachel"
    pipeline.set_user_keys("", "", "")


def test_synthetic_square_render_no_llm():
    """Recompose-style 1:1 render from mock audio+captions (ffmpeg only)."""
    os.environ.setdefault("EMERGENT_LLM_KEY", "test-not-used")
    os.environ["REELS_MOCK"] = "1"
    try:
        import importlib
        import pipeline
        importlib.reload(pipeline)
    except Exception as e:  # noqa: BLE001
        pytest.skip(f"pipeline deps not installed: {e}")
    if not pipeline.MOCK:
        pytest.skip("REELS_MOCK must be 1")

    import asyncio

    async def _run():
        wd = pipeline.new_workdir()
        audio = str(Path(wd) / "voice.mp3")
        await pipeline.synth_voice("Hello world. This is a size test.", "onyx", audio)
        words, dur = await pipeline.transcribe_words(audio)
        assert words and dur > 0
        ass = str(Path(wd) / "subs.ass")
        pipeline.build_ass(words, dur, "signal", ass, width=1080, height=1080)
        header = Path(ass).read_text(encoding="utf-8")
        assert "PlayResX: 1080" in header and "PlayResY: 1080" in header
        out = str(Path(wd) / "square.mp4")
        await pipeline.render_video(audio, "subs.ass", "ember", dur, wd, out, width=1080, height=1080)
        assert Path(out).exists() and Path(out).stat().st_size > 1000
        proc = await asyncio.create_subprocess_exec(
            pipeline._ffmpeg_exe(), "-i", out,
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        _, err = await proc.communicate()
        s = err.decode(errors="ignore")
        assert "1080x1080" in s

    asyncio.run(_run())
