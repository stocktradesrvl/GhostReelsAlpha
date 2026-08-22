"""Backend tests for VISUAL STYLE (visual_mode='gradient'|'ai'), validation, and analytics.

Focus (iteration 5):
- POST /api/reels with visual_mode='ai' returns 200 and echoes visual_mode='ai', status='queued'.
- POST /api/reels with visual_mode omitted defaults to 'gradient'.
- Root-cause confirmation: an 'ai' reel eventually fails ONLY due to LLM key BUDGET
  cap (env issue, not code). Error string must reference budget.
- GET /api/config returns all catalogs including music_tracks with 7 entries (incl 'none').
- Validation still enforced: invalid caption_font, invalid music_id, invalid custom hex.
- Analytics: POST /api/reels/{id}/view and /download increment counters.
"""
import time

import pytest


# -------- Feature: visual_mode field --------
def test_create_reel_ai_visual_mode_echoes_and_queued(api, base_url):
    payload = {
        "input_mode": "script",
        "script": "An exorcist enters a haunted church at midnight.",
        "visual_mode": "ai",
        "voice_id": "onyx",
    }
    r = api.post(f"{base_url}/api/reels", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    reel = r.json()
    assert reel["visual_mode"] == "ai", reel
    assert reel["status"] == "queued", reel
    # cleanup best-effort (may still be running; delete anyway)
    api.delete(f"{base_url}/api/reels/{reel['id']}", timeout=30)


def test_create_reel_default_visual_mode_is_gradient(api, base_url):
    payload = {
        "input_mode": "script",
        "script": "Three quick facts about octopuses.",
        "voice_id": "onyx",
    }
    r = api.post(f"{base_url}/api/reels", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    reel = r.json()
    assert reel["visual_mode"] == "gradient", reel
    api.delete(f"{base_url}/api/reels/{reel['id']}", timeout=30)


def test_ai_reel_failure_root_cause_is_budget(api, base_url):
    """Confirms the user-reported 'creating a video' error is the LLM budget cap,
    not a code exception. Creates an AI reel and polls until failed/ready,
    then asserts the error string references budget when failed."""
    payload = {
        "input_mode": "script",
        "script": "An exorcist enters a haunted church at midnight.",
        "visual_mode": "ai",
        "voice_id": "onyx",
        "seconds": 15,
    }
    r = api.post(f"{base_url}/api/reels", json=payload, timeout=30)
    assert r.status_code == 200, r.text
    rid = r.json()["id"]

    final = None
    for _ in range(60):  # up to ~180s
        g = api.get(f"{base_url}/api/reels/{rid}", timeout=30)
        assert g.status_code == 200
        final = g.json()
        if final["status"] in ("ready", "failed"):
            break
        time.sleep(3)

    # If pipeline actually produced a video (budget still had room), that's fine — just record.
    if final and final["status"] == "ready":
        api.delete(f"{base_url}/api/reels/{rid}", timeout=30)
        pytest.skip("AI pipeline succeeded — budget not exceeded in this run.")

    assert final is not None and final["status"] == "failed", final
    err = (final.get("error") or "").lower()
    print(f"AI failure error string: {final.get('error')!r}")
    assert ("budget" in err) or ("max budget" in err), (
        f"Expected budget-cap error; got: {final.get('error')!r}"
    )
    api.delete(f"{base_url}/api/reels/{rid}", timeout=30)


# -------- Config catalog completeness --------
def test_config_has_all_catalogs_and_music_seven(api, base_url):
    r = api.get(f"{base_url}/api/config", timeout=30)
    assert r.status_code == 200
    data = r.json()
    for k in ("voices", "caption_styles", "caption_positions", "caption_sizes",
              "caption_fonts", "caption_anims", "bg_themes", "bg_motions", "music_tracks"):
        assert k in data and isinstance(data[k], list) and len(data[k]) > 0, k
    assert len(data["music_tracks"]) == 7, data["music_tracks"]
    ids = {m["id"] for m in data["music_tracks"]}
    assert "none" in ids


# -------- Validation --------
def test_invalid_caption_font_400(api, base_url):
    r = api.post(f"{base_url}/api/reels", json={
        "input_mode": "script", "script": "hi", "voice_id": "onyx",
        "caption_style": "signal", "bg_theme": "ember", "caption_font": "comic-sans",
    }, timeout=30)
    assert r.status_code == 400


def test_invalid_music_id_400(api, base_url):
    r = api.post(f"{base_url}/api/reels", json={
        "input_mode": "script", "script": "hi", "voice_id": "onyx",
        "caption_style": "signal", "bg_theme": "ember", "music_id": "bogus",
    }, timeout=30)
    assert r.status_code == 400


def test_custom_bg_bad_hex_400(api, base_url):
    r = api.post(f"{base_url}/api/reels", json={
        "input_mode": "script", "script": "hi", "voice_id": "onyx",
        "caption_style": "signal", "bg_theme": "custom",
        "custom_c1": "zzzzzz", "custom_c2": "#123",
    }, timeout=30)
    assert r.status_code == 400


# -------- Analytics --------
def _find_ready_reel(api, base_url):
    r = api.get(f"{base_url}/api/reels", timeout=30)
    if r.status_code != 200:
        return None
    for reel in r.json():
        if reel.get("status") == "ready" and reel.get("has_video"):
            return reel
    return None


def test_view_and_download_increment(api, base_url):
    reel = _find_ready_reel(api, base_url)
    if not reel:
        pytest.skip("No ready reel available for analytics test (budget cap).")
    rid = reel["id"]
    prev_v = reel.get("views") or 0
    prev_d = reel.get("downloads") or 0

    v = api.post(f"{base_url}/api/reels/{rid}/view", timeout=30)
    assert v.status_code == 200
    assert v.json()["views"] == prev_v + 1

    d = api.post(f"{base_url}/api/reels/{rid}/download", timeout=30)
    assert d.status_code == 200
    assert d.json()["downloads"] == prev_d + 1

    # Confirm persisted via GET
    g = api.get(f"{base_url}/api/reels/{rid}", timeout=30)
    assert g.status_code == 200
    body = g.json()
    assert body["views"] == prev_v + 1
    assert body["downloads"] == prev_d + 1


def test_view_download_404_on_unknown(api, base_url):
    assert api.post(f"{base_url}/api/reels/nope-id/view", timeout=30).status_code == 404
    assert api.post(f"{base_url}/api/reels/nope-id/download", timeout=30).status_code == 404
