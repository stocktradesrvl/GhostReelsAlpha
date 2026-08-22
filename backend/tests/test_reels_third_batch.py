"""Third batch follow-up feature tests:
- /api/config exposes voice_speeds catalog
- POST /api/reels validates voice_speed (invalid -> 400)
- End-to-end reel with voice_speed='fast', music_volume=0.3, hook_enabled=True
- music_volume clamping (music_volume:5 -> stored as 1.0)  (create-only, no pipeline)
"""
import time
import pytest


# -------- /api/config voice_speeds --------
def test_config_has_voice_speeds(api, base_url):
    r = api.get(f"{base_url}/api/config", timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert "voice_speeds" in data, "voice_speeds missing"
    ids = {s["id"] for s in data["voice_speeds"]}
    assert {"slow", "normal", "fast"}.issubset(ids), f"got {ids}"
    # Regression: previously added catalogs still present
    for k in ("voices", "caption_styles", "caption_positions",
              "caption_sizes", "bg_themes", "music_tracks"):
        assert k in data and isinstance(data[k], list) and data[k], f"missing {k}"


# -------- voice_speed validation --------
def test_invalid_voice_speed_400(api, base_url):
    payload = {
        "input_mode": "script",
        "script": "hello world short",
        "voice_id": "onyx",
        "voice_speed": "warp-speed",
        "caption_style": "signal",
        "caption_position": "bottom",
        "caption_size": "m",
        "bg_theme": "ember",
        "music_id": "none",
    }
    r = api.post(f"{base_url}/api/reels", json=payload, timeout=30)
    assert r.status_code == 400, r.text


# -------- music_volume clamping (create-only, immediately delete to save budget) --------
def test_music_volume_clamped_on_create(api, base_url):
    payload = {
        "input_mode": "script",
        "script": "clamp test do not render",
        "voice_id": "onyx",
        "voice_speed": "normal",
        "caption_style": "signal",
        "caption_position": "bottom",
        "caption_size": "m",
        "bg_theme": "ember",
        "music_id": "lofi",
        "music_volume": 5,  # out of range -> should clamp to 1.0
        "hook_enabled": False,
    }
    r = api.post(f"{base_url}/api/reels", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["music_volume"] == 1.0, f"expected clamped 1.0, got {body.get('music_volume')}"
    # Immediately delete to conserve pipeline work
    api.delete(f"{base_url}/api/reels/{body['id']}", timeout=30)


# -------- End-to-end reel with the new fields --------
def _poll_ready(api, base_url, reel_id, timeout=150, interval=5):
    start = time.time()
    last = None
    while time.time() - start < timeout:
        r = api.get(f"{base_url}/api/reels/{reel_id}", timeout=30)
        assert r.status_code == 200
        last = r.json()
        if last["status"] in ("ready", "failed"):
            return last
        time.sleep(interval)
    return last


def test_reel_voice_speed_music_volume_hook(api, base_url):
    payload = {
        "input_mode": "script",
        "script": "Your phone is stealing your focus. Turn off notifications for one hour. Watch what happens.",
        "voice_id": "onyx",
        "voice_speed": "fast",
        "caption_style": "signal",
        "caption_position": "bottom",
        "caption_size": "m",
        "bg_theme": "ember",
        "music_id": "cinematic",
        "music_volume": 0.3,
        "watermark": "@focus",
        "hook_enabled": True,
    }
    r = api.post(f"{base_url}/api/reels", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    reel = r.json()
    assert reel["voice_speed"] == "fast"
    assert reel["music_volume"] == 0.3
    assert reel["hook_enabled"] is True
    assert reel["watermark"] == "@focus"

    rid = reel["id"]
    final = _poll_ready(api, base_url, rid, timeout=180, interval=5)

    if final is None:
        pytest.fail("Never got a final response from GET /api/reels/{id}")

    if final["status"] == "failed":
        err = (final.get("error") or "").lower()
        if "budget" in err:
            pytest.skip(f"LLM budget exhausted (env issue, not a code bug): {final.get('error')}")
        pytest.fail(f"Pipeline failed: {final.get('error')}")

    assert final["status"] == "ready", f"status={final['status']} error={final.get('error')}"
    assert final["has_video"] is True
    assert final["voice_speed"] == "fast"
    assert final["music_volume"] == 0.3
    assert final["hook_enabled"] is True

    v = api.get(f"{base_url}/api/reels/{rid}/video", timeout=90)
    assert v.status_code == 200
    assert v.headers.get("content-type", "").startswith("video/mp4")
    assert len(v.content) > 10_000

    api.delete(f"{base_url}/api/reels/{rid}", timeout=30)
