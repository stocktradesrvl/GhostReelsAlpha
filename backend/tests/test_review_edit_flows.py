"""
Iteration 11 — Backend tests for the AI script REVIEW/EDIT flow across
Series (per-episode) and Batch generation, using the ADMIN account
(bypasses quota + batch gate).

Endpoints exercised:
  POST /api/reels/batch/scripts   -> draft scripts per topic
  POST /api/reels/batch           -> create reels; persist reviewed scripts
  POST /api/series/{id}/episode/script  -> draft next episode script (no reel, no quota)
  POST /api/series/{id}/episode         -> create episode reel; persist reviewed script
"""

import os
import time
import uuid
from pathlib import Path

import pytest
import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

BASE_URL = None
for line in Path("/app/frontend/.env").read_text().splitlines():
    if line.startswith("EXPO_PUBLIC_BACKEND_URL="):
        BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")
        break

ADMIN_EMAIL = "russngina@gmail.com"
ADMIN_PASSWORD = "1123581321$$"


# -------- fixtures --------


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD},
        timeout=20,
    )
    assert r.status_code == 200, f"admin login failed: {r.status_code} {r.text}"
    body = r.json()
    return body.get("access_token") or body.get("token")


@pytest.fixture(scope="module")
def auth_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def series_id(auth_headers):
    """Create a small series once for the whole module."""
    tag = uuid.uuid4().hex[:6]
    payload = {
        "title": f"TEST_Series_{tag}",
        "premise": "A quiet detective solves supernatural crimes in a rainy port town.",
        "tone": "moody, cinematic",
        "characters": [
            {"name": "Detective Rowan", "description": "40s, weary, kind eyes."},
            {"name": "The Nightkeeper", "description": "Silent watcher of the docks."},
        ],
        # Required ReelSettings fields — defaults from the model are fine, but the
        # endpoint expects a full ReelSettings-ish payload (SeriesCreate extends it):
        "seconds": 15,
        "voice_id": "onyx",
        "caption_font": "barlow",
        "caption_anim": "pop",
        "bg_theme": "ember",
        "bg_motion": "dynamic",
        "music_id": "none",
        "hook_enabled": False,
        "visual_mode": "theme",
    }
    r = requests.post(f"{BASE_URL}/api/series", json=payload, headers=auth_headers, timeout=20)
    assert r.status_code == 200, f"create series failed: {r.status_code} {r.text}"
    return r.json()["id"]


# -------- Batch scripts draft endpoint --------


class TestBatchScripts:
    def test_scripts_ok_multiple_topics(self, auth_headers):
        topics = ["Why cats knock things off tables", "3 tiny habits that compound"]
        r = requests.post(
            f"{BASE_URL}/api/reels/batch/scripts",
            json={"topics": topics, "seconds": 15},
            headers=auth_headers,
            timeout=90,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        data = r.json()
        assert "scripts" in data
        assert len(data["scripts"]) == 2
        for i, item in enumerate(data["scripts"]):
            assert item["topic"] == topics[i]
            assert isinstance(item["script"], str) and item["script"].strip()
            assert isinstance(item["word_count"], int) and item["word_count"] > 0

    def test_scripts_empty_topics_400(self, auth_headers):
        r = requests.post(
            f"{BASE_URL}/api/reels/batch/scripts",
            json={"topics": [], "seconds": 15},
            headers=auth_headers,
            timeout=20,
        )
        assert r.status_code == 400
        assert "topic" in r.text.lower()

    def test_scripts_whitespace_only_topics_400(self, auth_headers):
        r = requests.post(
            f"{BASE_URL}/api/reels/batch/scripts",
            json={"topics": ["   ", "\n"], "seconds": 15},
            headers=auth_headers,
            timeout=20,
        )
        assert r.status_code == 400

    def test_scripts_too_many_topics_400(self, auth_headers):
        r = requests.post(
            f"{BASE_URL}/api/reels/batch/scripts",
            json={"topics": [f"topic {i}" for i in range(13)], "seconds": 15},
            headers=auth_headers,
            timeout=20,
        )
        assert r.status_code == 400
        assert "12" in r.text

    def test_scripts_requires_auth(self):
        r = requests.post(
            f"{BASE_URL}/api/reels/batch/scripts",
            json={"topics": ["x"], "seconds": 15},
            timeout=20,
        )
        assert r.status_code == 401


# -------- Batch create persists reviewed scripts --------


class TestBatchPersistScripts:
    def test_batch_persists_reviewed_script(self, auth_headers):
        tag = uuid.uuid4().hex[:6]
        topics = [f"TEST_batchtopic_{tag}_A", f"TEST_batchtopic_{tag}_B"]
        # Uniquely identifiable reviewed scripts; they must be persisted verbatim.
        scripts = [
            {"topic": topics[0], "script": f"REVIEWED_SCRIPT_A_{tag} — hook line one. Beat two. Beat three."},
            {"topic": topics[1], "script": f"REVIEWED_SCRIPT_B_{tag} — a totally different edited script."},
        ]
        payload = {
            "topics": topics,
            "scripts": scripts,
            "seconds": 15,
            "voice_id": "onyx",
            "caption_font": "barlow",
            "caption_anim": "pop",
            "bg_theme": "ember",
            "bg_motion": "dynamic",
            "music_id": "none",
            "hook_enabled": False,
            "visual_mode": "theme",
        }
        r = requests.post(
            f"{BASE_URL}/api/reels/batch",
            json=payload,
            headers=auth_headers,
            timeout=30,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        data = r.json()
        assert data["count"] == 2
        assert not data.get("scheduled")
        created = data["created"]

        # Verify via GET /api/reels/{id} that reel.script == the reviewed text.
        for c, sc in zip(created, scripts):
            gr = requests.get(f"{BASE_URL}/api/reels/{c['id']}", headers=auth_headers, timeout=15)
            assert gr.status_code == 200, gr.text
            reel = gr.json()
            assert reel["topic"] == sc["topic"]
            assert reel["script"] == sc["script"], (
                f"Expected persisted reviewed script, got {reel.get('script')!r}"
            )
            # topic matches
            assert reel["title"].startswith(sc["topic"][:48].strip())


# -------- Series episode script draft endpoint --------


class TestSeriesEpisodeScript:
    def test_episode_script_draft_no_reel_created(self, auth_headers, series_id):
        # Snapshot episode_count + reel list before
        before = requests.get(f"{BASE_URL}/api/series/{series_id}", headers=auth_headers, timeout=15).json()
        ep_before = before["series"]["episode_count"]
        reels_before = len(before["episodes"])

        r = requests.post(
            f"{BASE_URL}/api/series/{series_id}/episode/script",
            json={"topic": "The detective finds a locket in the tide."},
            headers=auth_headers,
            timeout=90,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        data = r.json()
        assert isinstance(data.get("script"), str) and data["script"].strip()
        assert data.get("word_count", 0) > 0
        assert data.get("episode_number") == ep_before + 1

        # Verify no reel was actually created + episode_count unchanged.
        after = requests.get(f"{BASE_URL}/api/series/{series_id}", headers=auth_headers, timeout=15).json()
        assert after["series"]["episode_count"] == ep_before, "script draft must NOT bump episode_count"
        assert len(after["episodes"]) == reels_before, "script draft must NOT create a reel"

    def test_episode_script_404_wrong_series(self, auth_headers):
        r = requests.post(
            f"{BASE_URL}/api/series/{uuid.uuid4()}/episode/script",
            json={"topic": "x"},
            headers=auth_headers,
            timeout=20,
        )
        assert r.status_code == 404

    def test_episode_script_requires_auth(self, series_id):
        r = requests.post(
            f"{BASE_URL}/api/series/{series_id}/episode/script",
            json={"topic": "x"},
            timeout=20,
        )
        assert r.status_code == 401


# -------- Series episode create persists reviewed script --------


class TestSeriesEpisodePersistScript:
    def test_episode_create_persists_reviewed_script(self, auth_headers, series_id):
        tag = uuid.uuid4().hex[:6]
        reviewed = (
            f"REVIEWED_EPISODE_SCRIPT_{tag} — Rowan traces the locket to a captain's widow. "
            "She reveals the port's oldest secret before the tide turns."
        )
        r = requests.post(
            f"{BASE_URL}/api/series/{series_id}/episode",
            json={
                "topic": f"TEST_topic_ep_{tag}",
                "script": reviewed,
            },
            headers=auth_headers,
            timeout=30,
        )
        assert r.status_code == 200, f"{r.status_code} {r.text}"
        reel = r.json()
        rid = reel["id"]
        assert reel["series_id"] == series_id
        assert reel["episode_number"] >= 1
        # status must not be stuck at an error/blank state at creation time
        assert reel["status"] in {
            "queued", "scripting", "voicing", "captioning", "rendering", "uploading", "ready", "scheduled",
        }

        # Fetch it back — script must equal the reviewed text (verbatim).
        gr = requests.get(f"{BASE_URL}/api/reels/{rid}", headers=auth_headers, timeout=15)
        assert gr.status_code == 200
        got = gr.json()
        assert got["series_id"] == series_id
        assert got["script"] == reviewed, (
            f"Expected persisted reviewed script, got {got.get('script')!r}"
        )

        # Small grace: give the background pipeline ~2s and confirm status isn't
        # stuck at None / empty / weird value.
        time.sleep(2)
        gr2 = requests.get(f"{BASE_URL}/api/reels/{rid}", headers=auth_headers, timeout=15)
        assert gr2.status_code == 200
        got2 = gr2.json()
        assert got2["status"] not in (None, "", "unknown")
        # script should NOT have been overwritten by the pipeline (it was pre-supplied)
        assert got2["script"] == reviewed, (
            f"Pipeline overwrote reviewed script; got {got2.get('script')!r}"
        )
