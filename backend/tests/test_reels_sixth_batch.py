"""Iteration 6: image_style picker + credit banner feature validation.

Tests focus on:
- /api/config exposing new image_styles list (cinematic/photoreal/anime/painterly)
- /api/reels honouring image_style in payload (echo)
- image_style omitted defaults to 'cinematic'
- No code-level 500s on /reels or /config
"""
import time
import pytest
import requests


# ---------------- /api/config -----------------
class TestConfigImageStyles:
    def test_config_returns_image_styles(self, api, base_url):
        r = api.get(f"{base_url}/api/config")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "image_styles" in data, f"image_styles missing. keys={list(data.keys())}"
        ids = [s["id"] for s in data["image_styles"]]
        for expected in ["cinematic", "photoreal", "anime", "painterly"]:
            assert expected in ids, f"expected style '{expected}' missing from {ids}"
        # Ensure each entry has name + suffix (prompt appendix)
        for s in data["image_styles"]:
            assert "name" in s and s["name"]
            assert "suffix" in s and s["suffix"]


# ---------------- /api/reels image_style echo -----------------
_created_ids = []


class TestReelImageStyleEcho:
    def test_create_reel_ai_anime_echoes(self, api, base_url):
        payload = {
            "input_mode": "script",
            "script": "A short test line.",
            "visual_mode": "ai",
            "image_style": "anime",
            "voice_id": "onyx",
        }
        r = api.post(f"{base_url}/api/reels", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["visual_mode"] == "ai"
        assert data["image_style"] == "anime"
        assert data["status"] == "queued"
        assert "id" in data and data["id"]
        _created_ids.append(data["id"])

        # verify persistence
        time.sleep(0.5)
        g = api.get(f"{base_url}/api/reels/{data['id']}")
        assert g.status_code == 200
        assert g.json()["image_style"] == "anime"

    def test_create_reel_image_style_defaults_cinematic(self, api, base_url):
        payload = {
            "input_mode": "script",
            "script": "Another short test line.",
            "visual_mode": "ai",
            "voice_id": "onyx",
        }
        r = api.post(f"{base_url}/api/reels", json=payload)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["visual_mode"] == "ai"
        assert data["image_style"] == "cinematic", f"expected default cinematic, got {data.get('image_style')}"
        assert data["status"] == "queued"
        _created_ids.append(data["id"])

    def test_create_reel_all_styles_accepted(self, api, base_url):
        for st in ["cinematic", "photoreal", "anime", "painterly"]:
            payload = {
                "input_mode": "script",
                "script": f"Style test {st}.",
                "visual_mode": "ai",
                "image_style": st,
                "voice_id": "onyx",
            }
            r = api.post(f"{base_url}/api/reels", json=payload)
            assert r.status_code == 200, f"style={st} failed: {r.text}"
            data = r.json()
            assert data["image_style"] == st
            _created_ids.append(data["id"])

    def test_create_reel_unknown_image_style_falls_back_to_cinematic(self, api, base_url):
        # server clamps to 'cinematic' if unknown (see build_reel_doc)
        payload = {
            "input_mode": "script",
            "script": "Unknown style test.",
            "visual_mode": "ai",
            "image_style": "totally-fake-style",
            "voice_id": "onyx",
        }
        r = api.post(f"{base_url}/api/reels", json=payload)
        assert r.status_code == 200, r.text
        assert r.json()["image_style"] == "cinematic"
        _created_ids.append(r.json()["id"])


# ---------------- No 500s -----------------
class TestNoServerErrors:
    def test_config_no_500(self, api, base_url):
        r = api.get(f"{base_url}/api/config")
        assert r.status_code < 500

    def test_reels_list_no_500(self, api, base_url):
        r = api.get(f"{base_url}/api/reels")
        assert r.status_code < 500

    def test_reels_post_no_500(self, api, base_url):
        r = api.post(f"{base_url}/api/reels", json={
            "input_mode": "script", "script": "no 500 please.", "visual_mode": "gradient",
        })
        assert r.status_code < 500
        if r.status_code == 200:
            _created_ids.append(r.json()["id"])


# ---------------- Credit banner backend contract -----------------
class TestCreditBannerBackend:
    """Frontend derives the banner state from list_reels() by looking for
    any reel with status='failed' and error matching /budget/i.
    Verify the list endpoint exposes those fields."""

    def test_list_reels_exposes_status_and_error(self, api, base_url):
        r = api.get(f"{base_url}/api/reels")
        assert r.status_code == 200
        reels = r.json()
        assert isinstance(reels, list)
        if reels:
            keys = set(reels[0].keys())
            assert "status" in keys
            assert "error" in keys


@pytest.fixture(scope="module", autouse=True)
def cleanup(base_url):
    yield
    s = requests.Session()
    for rid in _created_ids:
        try:
            s.delete(f"{base_url}/api/reels/{rid}", timeout=10)
        except Exception:
            pass
