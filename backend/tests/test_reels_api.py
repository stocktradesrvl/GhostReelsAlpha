"""Backend tests for Faceless AI Reels."""
import time
import pytest


# -------- Basics: config + script --------
def test_config(api, base_url):
    r = api.get(f"{base_url}/api/config", timeout=30)
    assert r.status_code == 200
    data = r.json()
    for k in ("voices", "caption_styles", "bg_themes"):
        assert k in data and isinstance(data[k], list) and len(data[k]) > 0
    voice_ids = {v["id"] for v in data["voices"]}
    assert {"onyx", "nova"}.issubset(voice_ids)


def test_script_generation(api, base_url):
    r = api.post(f"{base_url}/api/script", json={"topic": "why bees dance", "seconds": 15}, timeout=90)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "script" in data and isinstance(data["script"], str)
    assert len(data["script"].strip()) > 30, "Script should have meaningful content"
    assert data["word_count"] > 5


def test_script_empty_topic(api, base_url):
    r = api.post(f"{base_url}/api/script", json={"topic": "  ", "seconds": 15}, timeout=30)
    assert r.status_code == 400


# -------- Validation on POST /api/reels --------
def test_create_reel_empty_script_400(api, base_url):
    r = api.post(f"{base_url}/api/reels", json={
        "input_mode": "script", "script": "", "voice_id": "onyx",
        "caption_style": "signal", "bg_theme": "ember",
    }, timeout=30)
    assert r.status_code == 400


def test_create_reel_invalid_voice_400(api, base_url):
    r = api.post(f"{base_url}/api/reels", json={
        "input_mode": "script", "script": "hello world", "voice_id": "bogus",
        "caption_style": "signal", "bg_theme": "ember",
    }, timeout=30)
    assert r.status_code == 400


def test_create_reel_invalid_caption_400(api, base_url):
    r = api.post(f"{base_url}/api/reels", json={
        "input_mode": "script", "script": "hello world", "voice_id": "onyx",
        "caption_style": "bogus", "bg_theme": "ember",
    }, timeout=30)
    assert r.status_code == 400


def test_create_reel_invalid_bg_400(api, base_url):
    r = api.post(f"{base_url}/api/reels", json={
        "input_mode": "script", "script": "hello world", "voice_id": "onyx",
        "caption_style": "signal", "bg_theme": "bogus",
    }, timeout=30)
    assert r.status_code == 400


# -------- Listing & 404s --------
def test_list_reels_sorted(api, base_url):
    r = api.get(f"{base_url}/api/reels", timeout=30)
    assert r.status_code == 200
    reels = r.json()
    assert isinstance(reels, list)
    # If more than 1, verify newest-first ordering
    for i in range(len(reels) - 1):
        assert reels[i]["created_at"] >= reels[i + 1]["created_at"]


def test_get_reel_404(api, base_url):
    r = api.get(f"{base_url}/api/reels/does-not-exist", timeout=30)
    assert r.status_code == 404


def test_delete_reel_404(api, base_url):
    r = api.delete(f"{base_url}/api/reels/does-not-exist", timeout=30)
    assert r.status_code == 404


# -------- End-to-end pipeline: SCRIPT mode --------
def _poll_ready(api, base_url, reel_id, timeout=180, interval=5):
    seen_stages = set()
    start = time.time()
    last = None
    while time.time() - start < timeout:
        r = api.get(f"{base_url}/api/reels/{reel_id}", timeout=30)
        assert r.status_code == 200
        last = r.json()
        seen_stages.add(last["status"])
        if last["status"] in ("ready", "failed"):
            return last, seen_stages
        time.sleep(interval)
    return last, seen_stages


@pytest.fixture(scope="module")
def script_reel_id():
    return {"id": None}


def test_reel_script_mode_pipeline(api, base_url, script_reel_id):
    payload = {
        "input_mode": "script",
        "script": "Bees dance to talk. The waggle dance points to flowers. Its angle tells the sun's direction and its length hints at distance. Tiny insects. Precise maps.",
        "voice_id": "onyx",
        "caption_style": "signal",
        "bg_theme": "ember",
        "seconds": 15,
    }
    r = api.post(f"{base_url}/api/reels", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    reel = r.json()
    assert reel["status"] in ("queued", "scripting", "voicing", "captioning", "rendering", "uploading", "ready")
    assert reel["script"] and len(reel["script"]) > 10
    rid = reel["id"]
    script_reel_id["id"] = rid

    final, stages = _poll_ready(api, base_url, rid, timeout=180, interval=5)
    assert final["status"] == "ready", f"Reel failed: {final.get('error')}, stages={stages}"
    assert final["has_video"] is True
    assert final["duration"] and final["duration"] > 0
    assert final["progress"] == 100


def test_video_and_thumb_endpoints(api, base_url, script_reel_id):
    rid = script_reel_id["id"]
    if not rid:
        pytest.skip("script_reel not ready")

    v = api.get(f"{base_url}/api/reels/{rid}/video", timeout=60)
    assert v.status_code == 200
    assert v.headers.get("content-type", "").startswith("video/mp4")
    assert len(v.content) > 10_000

    t = api.get(f"{base_url}/api/reels/{rid}/thumb", timeout=60)
    assert t.status_code == 200
    assert t.headers.get("content-type", "").startswith("image/jpeg")
    assert len(t.content) > 1000


def test_delete_reel_and_verify_gone(api, base_url, script_reel_id):
    rid = script_reel_id["id"]
    if not rid:
        pytest.skip("script_reel not ready")
    r = api.delete(f"{base_url}/api/reels/{rid}", timeout=30)
    assert r.status_code == 200
    r2 = api.get(f"{base_url}/api/reels/{rid}", timeout=30)
    assert r2.status_code == 404


# -------- End-to-end pipeline: TOPIC mode --------
def test_reel_topic_mode_pipeline(api, base_url):
    payload = {
        "input_mode": "topic",
        "topic": "3 surprising facts about honey",
        "seconds": 15,
        "voice_id": "nova",
        "caption_style": "mono",
        "bg_theme": "midnight",
    }
    r = api.post(f"{base_url}/api/reels", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    reel = r.json()
    rid = reel["id"]

    final, stages = _poll_ready(api, base_url, rid, timeout=210, interval=5)
    assert final["status"] == "ready", f"Reel failed: {final.get('error')}, stages={stages}"
    assert final["script"] and len(final["script"].split()) > 5, "Topic mode should auto-generate script"
    assert final["has_video"] is True
    # cleanup
    api.delete(f"{base_url}/api/reels/{rid}", timeout=30)
