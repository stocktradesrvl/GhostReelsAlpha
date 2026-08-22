"""Iteration 7 tests: Series CRUD, character suggestion, episode generation,
outros upload+append, and new public reel fields (error_code, series_id,
episode_number, outro_id). Runs against EXPO_PUBLIC_BACKEND_URL.

REELS_MOCK=1 is set in backend/.env, so reels reach status='ready' quickly.
"""
import io
import os
import struct
import time

import pytest
import requests

BASE = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/") or \
       "https://mobile-dev-3451.preview.emergentagent.com"
API = f"{BASE}/api"


def _poll_reel(reel_id: str, timeout: int = 120):
    """Poll until status ∈ {ready, failed} or timeout."""
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        r = requests.get(f"{API}/reels/{reel_id}", timeout=30)
        assert r.status_code == 200
        last = r.json()
        if last.get("status") in ("ready", "failed"):
            return last
        time.sleep(2)
    return last


def _make_tiny_mp4() -> bytes:
    """Build a tiny valid MP4 (ftyp+mdat) big enough for /outros validation.
    Since backend does not run ffprobe on upload, we just need something that
    reports content_type video/mp4 and passes size checks.
    """
    # ftyp box
    ftyp = b"\x00\x00\x00\x18ftypisom\x00\x00\x02\x00isomiso2mp41"
    # mdat with 32 bytes of zeros
    mdat = b"\x00\x00\x00\x28mdat" + b"\x00" * 32
    return ftyp + mdat


# ---------- Series CRUD -------------------------------------------------------
class TestSeriesCRUD:
    created_ids = []

    def test_suggest_characters_mock(self):
        r = requests.post(f"{API}/series/suggest",
                          json={"premise": "A rogue priest hunts demons.", "tone": "horror"},
                          timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "characters" in data and isinstance(data["characters"], list)
        assert len(data["characters"]) >= 1
        for c in data["characters"]:
            assert "name" in c and "description" in c

    def test_suggest_requires_premise(self):
        r = requests.post(f"{API}/series/suggest", json={"premise": "", "tone": ""}, timeout=15)
        assert r.status_code == 400

    def test_create_list_get_delete_series(self):
        payload = {
            "title": "TEST_Series_" + str(int(time.time())),
            "premise": "A cursed detective solves ghost cases.",
            "tone": "noir horror",
            "characters": [
                {"name": "Kade", "description": "Grey trenchcoat, scar over left eye"},
            ],
            "visual_mode": "gradient",
            "image_style": "cinematic",
            "voice_id": "onyx",
            "seconds": 30,
        }
        r = requests.post(f"{API}/series", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        s = r.json()
        sid = s["id"]
        TestSeriesCRUD.created_ids.append(sid)
        assert s["title"] == payload["title"]
        assert s["episode_count"] == 0
        assert len(s["characters"]) == 1

        # LIST
        r = requests.get(f"{API}/series", timeout=30)
        assert r.status_code == 200
        assert any(x["id"] == sid for x in r.json())

        # GET
        r = requests.get(f"{API}/series/{sid}", timeout=30)
        assert r.status_code == 200
        body = r.json()
        assert "series" in body and "episodes" in body
        assert body["series"]["id"] == sid
        assert body["episodes"] == []

        # DELETE
        r = requests.delete(f"{API}/series/{sid}", timeout=30)
        assert r.status_code == 200
        r = requests.get(f"{API}/series/{sid}", timeout=15)
        assert r.status_code == 404

    def test_create_series_episode_flow_and_continuity(self):
        payload = {
            "title": "TEST_Continuity_" + str(int(time.time())),
            "premise": "Cursed detective story.",
            "tone": "noir",
            "characters": [{"name": "Kade", "description": "trenchcoat scar"}],
            "visual_mode": "gradient",
            "voice_id": "onyx",
            "seconds": 15,
        }
        r = requests.post(f"{API}/series", json=payload, timeout=30)
        assert r.status_code == 200
        sid = r.json()["id"]
        TestSeriesCRUD.created_ids.append(sid)

        # Episode 1 — no topic (AI continues)
        r1 = requests.post(f"{API}/series/{sid}/episode", json={}, timeout=30)
        assert r1.status_code == 200, r1.text
        ep1 = r1.json()
        assert ep1["series_id"] == sid
        assert ep1["episode_number"] == 1
        assert set(["error_code", "outro_id"]).issubset(set(ep1.keys()))

        # Episode 2 — with a specific topic
        r2 = requests.post(f"{API}/series/{sid}/episode",
                           json={"topic": "The library case"}, timeout=30)
        assert r2.status_code == 200, r2.text
        ep2 = r2.json()
        assert ep2["episode_number"] == 2

        # series.episode_count should be 2
        s = requests.get(f"{API}/series/{sid}", timeout=15).json()
        assert s["series"]["episode_count"] == 2
        assert len(s["episodes"]) == 2

        # Wait for both to reach ready (mock mode)
        d1 = _poll_reel(ep1["id"], timeout=90)
        d2 = _poll_reel(ep2["id"], timeout=90)
        assert d1["status"] == "ready", d1
        assert d2["status"] == "ready", d2

        # Continuity: episode 2 script mentions the topic OR differs from ep1
        assert d1["script"] and d2["script"]
        assert d1["script"] != d2["script"], "Episode 1 and 2 scripts should differ"

        # public fields present
        for f in ("error_code", "series_id", "episode_number", "outro_id"):
            assert f in d1 and f in d2

        # Cleanup episode reels
        for r_id in (ep1["id"], ep2["id"]):
            requests.delete(f"{API}/reels/{r_id}", timeout=15)

    @classmethod
    def teardown_class(cls):
        for sid in cls.created_ids:
            try:
                requests.delete(f"{API}/series/{sid}", timeout=15)
            except Exception:
                pass


# ---------- Outros ------------------------------------------------------------
class TestOutros:
    outro_ids = []
    reel_ids = []

    def test_upload_list_outro(self):
        data = _make_tiny_mp4()
        files = {"file": ("outro.mp4", data, "video/mp4")}
        r = requests.post(f"{API}/outros", files=files, data={"name": "TEST_outro"}, timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "id" in body and body["size"] == len(data)
        oid = body["id"]
        TestOutros.outro_ids.append(oid)

        r = requests.get(f"{API}/outros", timeout=15)
        assert r.status_code == 200
        assert any(o["id"] == oid for o in r.json())

    def test_upload_rejects_non_video(self):
        files = {"file": ("bad.txt", b"not a video", "text/plain")}
        r = requests.post(f"{API}/outros", files=files, timeout=15)
        assert r.status_code == 415

    def test_upload_rejects_empty(self):
        files = {"file": ("empty.mp4", b"", "video/mp4")}
        r = requests.post(f"{API}/outros", files=files, timeout=15)
        assert r.status_code == 400

    def test_reel_with_outro_public_fields(self):
        # We just verify the outro_id field flows through the create_reel API.
        # (Actual ffmpeg concat requires a real valid mp4 — the tiny synthesised
        # bytes would likely fail probe; instead we verify plumbing on public payload.)
        assert TestOutros.outro_ids, "requires prior upload"
        oid = TestOutros.outro_ids[0]
        payload = {
            "input_mode": "script",
            "script": "A short mock reel line for outro plumbing test.",
            "visual_mode": "gradient",
            "voice_id": "onyx",
            "seconds": 15,
            "outro_id": oid,
        }
        r = requests.post(f"{API}/reels", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        reel = r.json()
        TestOutros.reel_ids.append(reel["id"])
        for f in ("error_code", "series_id", "episode_number", "outro_id"):
            assert f in reel
        assert reel["outro_id"] == oid

    def test_delete_outro(self):
        assert TestOutros.outro_ids
        oid = TestOutros.outro_ids[0]
        r = requests.delete(f"{API}/outros/{oid}", timeout=15)
        assert r.status_code == 200
        # verify gone
        r = requests.get(f"{API}/outros", timeout=15)
        assert not any(o["id"] == oid for o in r.json())

    @classmethod
    def teardown_class(cls):
        for rid in cls.reel_ids:
            try:
                requests.delete(f"{API}/reels/{rid}", timeout=15)
            except Exception:
                pass


# ---------- Public reel payload fields ---------------------------------------
class TestReelPublicFields:
    def test_new_fields_present_on_plain_reel(self):
        payload = {
            "input_mode": "script",
            "script": "A tiny test line.",
            "visual_mode": "gradient",
            "voice_id": "onyx",
            "seconds": 15,
        }
        r = requests.post(f"{API}/reels", json=payload, timeout=30)
        assert r.status_code == 200
        reel = r.json()
        for f in ("error_code", "series_id", "episode_number", "outro_id"):
            assert f in reel, f"missing {f} in public reel"
        # cleanup
        requests.delete(f"{API}/reels/{reel['id']}", timeout=15)
