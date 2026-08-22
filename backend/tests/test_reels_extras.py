"""Tests for the follow-up features:
- /api/config exposes caption_positions, caption_sizes, music_tracks
- /api/voices/{id}/preview returns mp3 (valid) or 404 (invalid)
- POST /api/reels validates caption_position, caption_size, music_id
- End-to-end reel creation with the new fields
"""
import time
import pytest


# -------- Config exposes new catalogs --------
def test_config_has_new_catalogs(api, base_url):
    r = api.get(f"{base_url}/api/config", timeout=30)
    assert r.status_code == 200
    data = r.json()
    for k in ("caption_positions", "caption_sizes", "music_tracks",
              "voices", "caption_styles", "bg_themes"):
        assert k in data, f"missing {k} in /api/config"
        assert isinstance(data[k], list) and len(data[k]) > 0

    positions = {p["id"] for p in data["caption_positions"]}
    assert {"bottom", "center", "top"}.issubset(positions)

    sizes = {s["id"] for s in data["caption_sizes"]}
    assert {"s", "m", "l"}.issubset(sizes)

    tracks = {m["id"] for m in data["music_tracks"]}
    assert {"none", "lofi", "upbeat", "cinematic"}.issubset(tracks)


# -------- Voice preview endpoint --------
@pytest.mark.parametrize("voice_id", ["onyx", "nova"])
def test_voice_preview_valid(api, base_url, voice_id):
    r = api.get(f"{base_url}/api/voices/{voice_id}/preview", timeout=90)
    assert r.status_code == 200, r.text
    ct = r.headers.get("content-type", "")
    assert ct.startswith("audio/mpeg"), f"unexpected content-type: {ct}"
    assert len(r.content) > 1000, f"preview body too small: {len(r.content)} bytes"


def test_voice_preview_invalid_404(api, base_url):
    r = api.get(f"{base_url}/api/voices/bogus-voice/preview", timeout=30)
    assert r.status_code == 404


# -------- Validation on new params --------
def _base_payload(**over):
    p = {
        "input_mode": "script",
        "script": "hello world this is a short script",
        "voice_id": "onyx",
        "caption_style": "signal",
        "caption_position": "bottom",
        "caption_size": "m",
        "bg_theme": "ember",
        "music_id": "none",
    }
    p.update(over)
    return p


def test_invalid_caption_position_400(api, base_url):
    r = api.post(f"{base_url}/api/reels",
                 json=_base_payload(caption_position="bogus"), timeout=30)
    assert r.status_code == 400


def test_invalid_caption_size_400(api, base_url):
    r = api.post(f"{base_url}/api/reels",
                 json=_base_payload(caption_size="xxl"), timeout=30)
    assert r.status_code == 400


def test_invalid_music_id_400(api, base_url):
    r = api.post(f"{base_url}/api/reels",
                 json=_base_payload(music_id="bogus"), timeout=30)
    assert r.status_code == 400


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


def test_reel_with_all_new_fields(api, base_url):
    payload = {
        "input_mode": "script",
        "script": "Three quick tips to focus better today. Turn off notifications. Batch your tasks. Take real breaks.",
        "voice_id": "nova",
        "caption_style": "sunset",
        "caption_position": "bottom",
        "caption_size": "l",
        "bg_theme": "sunset",
        "music_id": "upbeat",
        "watermark": "@creator",
    }
    r = api.post(f"{base_url}/api/reels", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    reel = r.json()
    # New fields echoed on create
    assert reel["caption_position"] == "bottom"
    assert reel["caption_size"] == "l"
    assert reel["music_id"] == "upbeat"
    assert reel["watermark"] == "@creator"

    rid = reel["id"]
    final = _poll_ready(api, base_url, rid, timeout=150, interval=5)

    if final["status"] == "failed":
        err = (final.get("error") or "").lower()
        if "budget" in err or "max budget" in err:
            pytest.skip(f"LLM budget exhausted (env issue, not a code bug): {final.get('error')}")
        pytest.fail(f"Pipeline failed: {final.get('error')}")

    assert final["status"] == "ready", f"status={final['status']} error={final.get('error')}"
    assert final["has_video"] is True
    assert final["caption_position"] == "bottom"
    assert final["caption_size"] == "l"
    assert final["music_id"] == "upbeat"
    assert final["watermark"] == "@creator"

    # Video endpoint
    v = api.get(f"{base_url}/api/reels/{rid}/video", timeout=90)
    assert v.status_code == 200
    assert v.headers.get("content-type", "").startswith("video/mp4")
    assert len(v.content) > 10_000

    # Cleanup
    api.delete(f"{base_url}/api/reels/{rid}", timeout=30)
