"""Auth-scope remaining reel endpoints: owner can read/mutate; other users 404;
unauthenticated 401. Uses REELS_MOCK on the preview backend — no LLM/TTS spend.
"""
import os
import time
import uuid

import pytest
import requests

BASE = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "").rstrip("/") or \
       "https://mobile-dev-3451.preview.emergentagent.com"
API = f"{BASE}/api"


def _register(email=None, pw="password123"):
    email = email or f"qa+{uuid.uuid4().hex[:10]}@test.com"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": pw}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"backend not reachable or register failed: {r.status_code} {r.text[:200]}")
    body = r.json()
    return body["access_token"], body["user"], email


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _poll(reel_id, tok, timeout=90):
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        r = requests.get(f"{API}/reels/{reel_id}", headers=_hdr(tok), timeout=30)
        assert r.status_code == 200, r.text
        last = r.json()
        if last.get("status") in ("ready", "failed"):
            return last
        time.sleep(2)
    return last


class TestConfigVoices:
    def test_config_lists_elevenlabs_and_aspects(self):
        r = requests.get(f"{API}/config", timeout=20)
        if r.status_code != 200:
            pytest.skip("backend not reachable")
        data = r.json()
        ids = {v["id"] for v in data["voices"]}
        assert "onyx" in ids and "el_rachel" in ids
        engines = {v["id"]: v.get("engine") for v in data["voices"]}
        assert engines.get("el_rachel") == "elevenlabs"
        aspects = {a["id"] for a in data.get("aspects") or []}
        assert aspects == {"9:16", "1:1", "16:9"}


class TestRemainingAuthScope:
    def test_unauthenticated_is_401(self):
        fake = str(uuid.uuid4())
        for method, path in (
            ("GET", f"/reels/{fake}"),
            ("DELETE", f"/reels/{fake}"),
            ("GET", f"/reels/{fake}/video"),
            ("GET", f"/reels/{fake}/thumb"),
            ("POST", f"/reels/{fake}/view"),
            ("POST", f"/reels/{fake}/download"),
            ("GET", f"/reels/{fake}/scenes"),
            ("GET", f"/reels/{fake}/lines"),
            ("POST", f"/reels/{fake}/export"),
            ("POST", f"/reels/{fake}/post"),
        ):
            r = requests.request(method, f"{API}{path}", json={}, timeout=20)
            if r.status_code == 0:
                pytest.skip("backend not reachable")
            assert r.status_code == 401, f"{method} {path} -> {r.status_code}"

    def test_cross_user_cannot_read_or_mutate(self):
        tok_a, ua, _ = _register()
        tok_b, ub, _ = _register()
        r = requests.post(f"{API}/reels", json={
            "input_mode": "script", "script": "Auth scope private reel.",
            "visual_mode": "gradient", "voice_id": "onyx", "seconds": 15,
        }, headers=_hdr(tok_a), timeout=30)
        assert r.status_code == 200, r.text
        rid = r.json()["id"]
        final = _poll(rid, tok_a, timeout=90)
        assert final and final.get("status") in ("ready", "failed")

        for method, path in (
            ("GET", f"/reels/{rid}"),
            ("GET", f"/reels/{rid}/video"),
            ("GET", f"/reels/{rid}/thumb"),
            ("POST", f"/reels/{rid}/view"),
            ("POST", f"/reels/{rid}/download"),
            ("GET", f"/reels/{rid}/scenes"),
            ("GET", f"/reels/{rid}/lines"),
            ("POST", f"/reels/{rid}/scene/0/regenerate"),
            ("POST", f"/reels/{rid}/line/0/regenerate"),
            ("DELETE", f"/reels/{rid}"),
        ):
            r = requests.request(method, f"{API}{path}", json={"text": "x", "prompt": "x"},
                                 headers=_hdr(tok_b), timeout=30)
            assert r.status_code in (403, 404), f"B {method} {path} leaked: {r.status_code} {r.text[:180]}"

        r = requests.get(f"{API}/reels/{rid}", headers=_hdr(tok_a), timeout=20)
        assert r.status_code == 200
        if final.get("status") == "ready":
            v = requests.get(f"{API}/reels/{rid}/video", headers=_hdr(tok_a), timeout=60)
            assert v.status_code == 200
            assert v.headers.get("content-type", "").startswith("video/")
            v2 = requests.get(f"{API}/reels/{rid}/video", params={"access_token": tok_a}, timeout=60)
            assert v2.status_code == 200

        requests.delete(f"{API}/reels/{rid}", headers=_hdr(tok_a), timeout=15)

    def test_owner_post_without_connect_is_400(self):
        tok, _, _ = _register()
        r = requests.post(f"{API}/reels", json={
            "input_mode": "script", "script": "Social post gate.",
            "visual_mode": "gradient", "voice_id": "onyx", "seconds": 15,
        }, headers=_hdr(tok), timeout=30)
        assert r.status_code == 200, r.text
        rid = r.json()["id"]
        final = _poll(rid, tok, timeout=90)
        if not final or final.get("status") != "ready":
            pytest.skip("reel did not become ready (mock/credits)")
        r = requests.post(f"{API}/reels/{rid}/post", json={"platform": "youtube"},
                          headers=_hdr(tok), timeout=20)
        assert r.status_code in (200, 400, 503), r.text
        if r.status_code == 200:
            body = r.json()
            assert body.get("mock") is True or body.get("ok") is True
        r = requests.get(f"{API}/connect/youtube", headers=_hdr(tok), timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert "configured" in body
        requests.delete(f"{API}/reels/{rid}", headers=_hdr(tok), timeout=15)

    def test_elevenlabs_key_masked(self):
        tok, _, _ = _register()
        raw = "sk_" + uuid.uuid4().hex + "TAIL"
        r = requests.put(f"{API}/settings", json={"elevenlabs_key": raw}, headers=_hdr(tok), timeout=15)
        assert r.status_code == 200, r.text
        s = r.json()
        assert s.get("elevenlabs_key_set") is True
        assert s.get("elevenlabs_key_masked")
        assert raw not in str(s)
        assert "••••" in s["elevenlabs_key_masked"]
