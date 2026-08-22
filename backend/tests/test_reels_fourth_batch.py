"""Fourth batch follow-up feature tests:
- /api/config exposes caption_fonts catalog (barlow / anton / archivo)
- POST /api/reels validates caption_font (invalid -> 400)
- End-to-end reel with caption_font='archivo', endcard_text='Follow for more',
  music_id='lofi', music_volume=0.15 (music fade always-on)
"""
import time
import pytest


# -------- /api/config caption_fonts --------
def test_config_has_caption_fonts(api, base_url):
    r = api.get(f"{base_url}/api/config", timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert "caption_fonts" in data, "caption_fonts missing"
    ids = {f["id"] for f in data["caption_fonts"]}
    assert {"barlow", "anton", "archivo"}.issubset(ids), f"got {ids}"
    # Regression: prior catalogs still present
    for k in ("voices", "voice_speeds", "caption_styles", "caption_positions",
              "caption_sizes", "bg_themes", "music_tracks"):
        assert k in data and isinstance(data[k], list) and data[k], f"missing {k}"


# -------- caption_font validation --------
def test_invalid_caption_font_400(api, base_url):
    payload = {
        "input_mode": "script",
        "script": "hello world short",
        "voice_id": "onyx",
        "voice_speed": "normal",
        "caption_style": "signal",
        "caption_position": "bottom",
        "caption_size": "m",
        "caption_font": "comic-sans",
        "bg_theme": "ember",
        "music_id": "none",
    }
    r = api.post(f"{base_url}/api/reels", json=payload, timeout=30)
    assert r.status_code == 400, r.text


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


def test_reel_caption_font_and_endcard(api, base_url):
    payload = {
        "input_mode": "script",
        "script": "Three tips for better sleep. No screens before bed. Keep your room cool. Wake at the same time.",
        "voice_id": "echo",
        "caption_style": "signal",
        "caption_position": "center",
        "caption_size": "l",
        "caption_font": "archivo",
        "bg_theme": "mono",
        "music_id": "lofi",
        "music_volume": 0.15,
        "endcard_text": "Follow for more",
    }
    r = api.post(f"{base_url}/api/reels", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    reel = r.json()
    assert reel["caption_font"] == "archivo"
    assert reel["endcard_text"] == "Follow for more"
    assert reel["music_id"] == "lofi"

    rid = reel["id"]
    final = _poll_ready(api, base_url, rid, timeout=180, interval=5)

    if final is None:
        pytest.fail("Never got a final response from GET /api/reels/{id}")

    if final["status"] == "failed":
        err = (final.get("error") or "").lower()
        if "budget" in err:
            pytest.skip(f"LLM budget exhausted: {final.get('error')}")
        pytest.fail(f"Pipeline failed: {final.get('error')}")

    assert final["status"] == "ready", f"status={final['status']} error={final.get('error')}"
    assert final["has_video"] is True
    assert final["caption_font"] == "archivo"
    assert final["endcard_text"] == "Follow for more"

    v = api.get(f"{base_url}/api/reels/{rid}/video", timeout=90)
    assert v.status_code == 200
    assert v.headers.get("content-type", "").startswith("video/mp4")
    assert len(v.content) > 10_000

    api.delete(f"{base_url}/api/reels/{rid}", timeout=30)
