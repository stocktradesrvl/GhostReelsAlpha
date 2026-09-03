"""AI image count, visual direction (mood), extra styles. REELS_MOCK — no LLM spend.

Unit-tests the prompt helper (n=6 + mood in every prompt) and clamps.
Live echo against /api/reels when EXPO_PUBLIC_BACKEND_URL is set.
"""
import os

import pytest

os.environ.setdefault("EMERGENT_LLM_KEY", "test-not-used")
os.environ["REELS_MOCK"] = "1"

from reels_config import IMAGE_STYLE_MAP, IMAGE_STYLES
from visual_dir import (
    auto_scene_count,
    clamp_image_count,
    compose_style_suffix,
    generate_scene_prompts,
    mock_scene_prompts,
    prompt_writer_instruction,
    resolve_scene_n,
    sanitize_direction,
)


class TestCatalog:
    def test_keeps_original_styles_and_adds_storytelling(self):
        ids = [s["id"] for s in IMAGE_STYLES]
        for expected in ["cinematic", "photoreal", "anime", "painterly"]:
            assert expected in ids
        for expected in ["cartoon", "comic", "noir", "illustrated", "3d"]:
            assert expected in ids, ids
        assert IMAGE_STYLE_MAP["comic"]["name"] == "Comic book"
        for s in IMAGE_STYLES:
            assert s["name"] and s["suffix"]


class TestCountAndDirection:
    def test_auto_count_matches_legacy_scene_count(self):
        assert auto_scene_count(15) == 2
        assert auto_scene_count(30) == 3
        assert auto_scene_count(60) == 4
        assert resolve_scene_n(30, None) == 3
        assert resolve_scene_n(30) == 3

    def test_user_count_wins_and_clamps(self):
        assert resolve_scene_n(30, 6) == 6
        assert resolve_scene_n(15, 6) == 6
        assert clamp_image_count(6) == 6
        assert clamp_image_count(1) == 2
        assert clamp_image_count(99) == 12
        assert clamp_image_count(None) is None
        assert clamp_image_count("nope") is None
        assert resolve_scene_n(30, 1) == 2
        assert resolve_scene_n(30, 99) == 12

    def test_direction_sanitized(self):
        assert sanitize_direction("  terrifying  ") == "terrifying"
        assert sanitize_direction("") == ""
        assert sanitize_direction(None) == ""
        long = "x" * 500
        assert len(sanitize_direction(long)) == 120

    def test_style_suffix_includes_mood(self):
        s = compose_style_suffix("comic", "terrifying")
        assert "comic book" in s.lower() or "comic" in s.lower()
        assert "terrifying" in s
        assert "Visual direction" in compose_style_suffix("cinematic", "hopeful golden-hour")
        assert "Visual direction" not in compose_style_suffix("cinematic", "")


class TestPromptHelper:
    def test_instruction_uses_n_and_mood(self):
        ask = prompt_writer_instruction(6, "terrifying", script="A story about exorcisms.")
        assert "exactly 6" in ask
        assert "terrifying" in ask
        assert "exorcisms" in ask
        # empty mood keeps the original cinematic lighting line
        plain = prompt_writer_instruction(3, "", script="Octopus facts.")
        assert "Cinematic, photographic, dramatic lighting" in plain
        assert "exactly 3" in plain

    def test_mock_prompts_are_n_and_include_mood(self):
        prompts = mock_scene_prompts(6, "terrifying")
        assert len(prompts) == 6
        assert all("terrifying" in p for p in prompts)

    def test_generate_scene_prompts_mock_n6_mood(self):
        import asyncio
        os.environ["REELS_MOCK"] = "1"
        try:
            import pipeline
        except Exception as e:  # noqa: BLE001
            pytest.skip(f"pipeline deps not installed: {e}")
        pipeline.MOCK = True
        prompts = asyncio.run(generate_scene_prompts(
            "A reel about exorcisms.", 6, direction="terrifying",
        ))
        assert len(prompts) == 6
        assert all("terrifying" in p for p in prompts)


# -------- optional live API echo (skips when no backend URL) -----------------
def _base():
    url = (os.environ.get("EXPO_PUBLIC_BACKEND_URL") or "").rstrip("/")
    return url or None


@pytest.mark.skipif(not _base(), reason="no EXPO_PUBLIC_BACKEND_URL")
class TestApiEcho:
    def test_config_lists_new_styles_and_count_range(self):
        import requests
        r = requests.get(f"{_base()}/api/config", timeout=20)
        assert r.status_code == 200, r.text
        data = r.json()
        ids = [s["id"] for s in data["image_styles"]]
        assert "comic" in ids and "cartoon" in ids
        assert data.get("image_count_min") == 2
        assert data.get("image_count_max") == 12

    def test_create_reel_echoes_count_direction_comic(self):
        import requests
        payload = {
            "input_mode": "script",
            "script": "A reel about exorcisms in a haunted church.",
            "visual_mode": "ai",
            "image_count": 6,
            "image_direction": "terrifying",
            "image_style": "comic",
            "voice_id": "onyx",
            "seconds": 30,
        }
        r = requests.post(f"{_base()}/api/reels", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["visual_mode"] == "ai"
        assert data["image_count"] == 6
        assert data["image_direction"] == "terrifying"
        assert data["image_style"] == "comic"
        assert data["status"] == "queued"
        requests.delete(f"{_base()}/api/reels/{data['id']}", timeout=20)

    def test_invalid_count_clamps(self):
        import requests
        r = requests.post(f"{_base()}/api/reels", json={
            "input_mode": "script", "script": "Clamp me.", "visual_mode": "ai",
            "image_count": 99, "image_style": "comic", "voice_id": "onyx",
        }, timeout=30)
        assert r.status_code == 200, r.text
        assert r.json()["image_count"] == 12
        requests.delete(f"{_base()}/api/reels/{r.json()['id']}", timeout=20)
