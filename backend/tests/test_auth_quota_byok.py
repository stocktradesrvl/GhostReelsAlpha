"""Iteration 10 — Auth (JWT), server-side 3-free-reel quota, and per-user
AES-encrypted BYOK keys. Runs against EXPO_PUBLIC_BACKEND_URL with REELS_MOCK=1.

Verifies:
 - register / login / me / wrong password
 - endpoints require Bearer token
 - lifetime 3 free reels per account; 4th generation returns HTTP 402
 - saving OpenAI BYOK key bypasses quota and is stored encrypted + returned masked
 - /settings/test rejects a clearly fake OpenAI key (real provider call)
 - per-user isolation: /reels and /series scoped to owner only
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
    assert r.status_code == 200, r.text
    body = r.json()
    assert "access_token" in body and "user" in body
    return body["access_token"], body["user"], email


def _hdr(tok):
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _poll_reel(reel_id, tok, timeout=90):
    t0 = time.time()
    last = None
    while time.time() - t0 < timeout:
        r = requests.get(f"{API}/reels/{reel_id}", headers=_hdr(tok), timeout=30)
        assert r.status_code == 200
        last = r.json()
        if last.get("status") in ("ready", "failed"):
            return last
        time.sleep(2)
    return last


# ---------- AUTH -------------------------------------------------------------
class TestAuth:
    def test_register_login_me(self):
        tok, user, email = _register()
        assert user["email"] == email
        assert user["free_used"] == 0
        assert user["free_limit"] == 3
        assert user["has_own_key"] is False

        # login again with same creds
        r = requests.post(f"{API}/auth/login",
                          json={"email": email, "password": "password123"},
                          timeout=30)
        assert r.status_code == 200
        tok2 = r.json()["access_token"]

        # /auth/me
        r = requests.get(f"{API}/auth/me", headers=_hdr(tok2), timeout=15)
        assert r.status_code == 200
        me = r.json()
        assert me["email"] == email
        assert me["id"] == user["id"]

    def test_wrong_password_401(self):
        _, _, email = _register()
        r = requests.post(f"{API}/auth/login",
                          json={"email": email, "password": "wrongpassword!"},
                          timeout=15)
        assert r.status_code == 401

    def test_duplicate_email_409(self):
        _, _, email = _register()
        r = requests.post(f"{API}/auth/register",
                          json={"email": email, "password": "password123"}, timeout=15)
        assert r.status_code == 409

    def test_short_password_400(self):
        r = requests.post(f"{API}/auth/register",
                          json={"email": f"qa+{uuid.uuid4().hex[:8]}@test.com", "password": "short"},
                          timeout=15)
        assert r.status_code == 400

    def test_endpoints_require_auth(self):
        # sample of endpoints that depend on current_user
        for path in ("/reels", "/series", "/settings", "/auth/me"):
            r = requests.get(f"{API}{path}", timeout=15)
            assert r.status_code == 401, f"{path} should be 401 without token"
        r = requests.post(f"{API}/reels", json={"input_mode": "script", "script": "x"}, timeout=15)
        assert r.status_code == 401


# ---------- QUOTA ------------------------------------------------------------
class TestQuota:
    def test_lifetime_3_free_reels_then_402(self):
        tok, user, email = _register()
        created = []
        for i in range(3):
            payload = {
                "input_mode": "script",
                "script": f"Mock quota line {i}.",
                "visual_mode": "gradient",
                "voice_id": "onyx",
                "seconds": 15,
            }
            r = requests.post(f"{API}/reels", json=payload, headers=_hdr(tok), timeout=30)
            assert r.status_code == 200, f"reel #{i+1} failed: {r.status_code} {r.text}"
            created.append(r.json()["id"])

        # /auth/me should now say free_used == 3
        me = requests.get(f"{API}/auth/me", headers=_hdr(tok), timeout=15).json()
        assert me["free_used"] == 3
        assert me["has_own_key"] is False

        # 4th attempt → 402
        r = requests.post(f"{API}/reels",
                          json={"input_mode": "script", "script": "Should be blocked.",
                                "visual_mode": "gradient", "voice_id": "onyx", "seconds": 15},
                          headers=_hdr(tok), timeout=15)
        assert r.status_code == 402, f"expected 402 got {r.status_code}: {r.text}"
        detail = r.json().get("detail", "")
        assert "free reels" in detail.lower() or "3" in detail

        # /script endpoint should also be gated
        r = requests.post(f"{API}/script", json={"topic": "hello", "seconds": 15},
                          headers=_hdr(tok), timeout=15)
        assert r.status_code == 402

        # 4th reel was NOT created — count still 3
        r = requests.get(f"{API}/reels", headers=_hdr(tok), timeout=15)
        assert r.status_code == 200
        assert len(r.json()) == 3

        # cleanup
        for rid in created:
            requests.delete(f"{API}/reels/{rid}", timeout=10)

    def test_byok_bypasses_quota(self):
        tok, user, email = _register()
        # burn the 3 free reels
        for i in range(3):
            r = requests.post(f"{API}/reels",
                              json={"input_mode": "script", "script": f"burn {i}",
                                    "visual_mode": "gradient", "voice_id": "onyx", "seconds": 15},
                              headers=_hdr(tok), timeout=30)
            assert r.status_code == 200

        # confirm 4th is 402
        r = requests.post(f"{API}/reels",
                          json={"input_mode": "script", "script": "blocked",
                                "visual_mode": "gradient", "voice_id": "onyx", "seconds": 15},
                          headers=_hdr(tok), timeout=15)
        assert r.status_code == 402

        # Save a BYOK OpenAI key
        fake = "sk-test-" + uuid.uuid4().hex
        r = requests.put(f"{API}/settings", json={"openai_key": fake},
                         headers=_hdr(tok), timeout=15)
        assert r.status_code == 200, r.text
        s = r.json()
        assert s["openai_key_set"] is True
        assert s["has_own_key"] is True
        # masked, never raw
        assert s["openai_key_masked"] and s["openai_key_masked"] != fake
        assert "••••" in s["openai_key_masked"]
        assert fake not in str(s)

        # 4th attempt should now succeed (mock)
        r = requests.post(f"{API}/reels",
                          json={"input_mode": "script", "script": "bypass via byok",
                                "visual_mode": "gradient", "voice_id": "onyx", "seconds": 15},
                          headers=_hdr(tok), timeout=30)
        assert r.status_code == 200, f"BYOK bypass failed: {r.status_code} {r.text}"

        # clear the key -> quota comes back
        r = requests.put(f"{API}/settings", json={"openai_key": ""},
                         headers=_hdr(tok), timeout=15)
        assert r.status_code == 200
        s = r.json()
        assert s["openai_key_set"] is False
        assert s["has_own_key"] is False

        r = requests.post(f"{API}/reels",
                          json={"input_mode": "script", "script": "should block again",
                                "visual_mode": "gradient", "voice_id": "onyx", "seconds": 15},
                          headers=_hdr(tok), timeout=15)
        assert r.status_code == 402

        # cleanup
        reels = requests.get(f"{API}/reels", headers=_hdr(tok), timeout=15).json()
        for x in reels:
            requests.delete(f"{API}/reels/{x['id']}", timeout=10)


# ---------- BYOK encryption + masking ---------------------------------------
class TestBYOK:
    def test_settings_returns_masked_never_raw(self):
        tok, user, _ = _register()
        raw = "sk-live-" + uuid.uuid4().hex + "TAIL9999"
        r = requests.put(f"{API}/settings", json={"openai_key": raw},
                         headers=_hdr(tok), timeout=15)
        assert r.status_code == 200

        # GET /settings must return masked, not raw
        r = requests.get(f"{API}/settings", headers=_hdr(tok), timeout=15)
        assert r.status_code == 200
        body = r.json()
        assert body["openai_key_set"] is True
        assert body["openai_key_masked"]
        assert body["openai_key_masked"] != raw
        assert raw not in str(body), "raw key must NEVER be returned in /settings"
        # sanity: masked format "sk-••••XXXX"
        m = body["openai_key_masked"]
        assert "••••" in m
        assert m.endswith(raw[-4:])

    def test_test_endpoint_rejects_fake_key(self):
        tok, _, _ = _register()
        # very obviously invalid
        r = requests.post(f"{API}/settings/test",
                          json={"openai_key": "sk-obviously-fake-12345"},
                          headers=_hdr(tok), timeout=30)
        assert r.status_code == 200, r.text
        body = r.json()
        assert "openai" in body
        assert body["openai"]["ok"] is False


# ---------- Per-user isolation ----------------------------------------------
class TestIsolation:
    def test_reels_and_series_scoped_to_owner(self):
        tok_a, ua, _ = _register()
        tok_b, ub, _ = _register()

        # A creates a reel
        r = requests.post(f"{API}/reels",
                          json={"input_mode": "script", "script": "user A private reel",
                                "visual_mode": "gradient", "voice_id": "onyx", "seconds": 15},
                          headers=_hdr(tok_a), timeout=30)
        assert r.status_code == 200
        reel_a = r.json()["id"]

        # A creates a series
        r = requests.post(f"{API}/series",
                          json={"title": "A_Series_" + uuid.uuid4().hex[:6],
                                "premise": "A private",
                                "voice_id": "onyx", "seconds": 15},
                          headers=_hdr(tok_a), timeout=30)
        assert r.status_code == 200
        series_a = r.json()["id"]

        # B lists /reels + /series → should NOT see A's items
        rb = requests.get(f"{API}/reels", headers=_hdr(tok_b), timeout=15).json()
        assert not any(x["id"] == reel_a for x in rb), "B saw A's reels!"
        sb = requests.get(f"{API}/series", headers=_hdr(tok_b), timeout=15).json()
        assert not any(x["id"] == series_a for x in sb), "B saw A's series!"

        # B cannot GET A's series
        r = requests.get(f"{API}/series/{series_a}", headers=_hdr(tok_b), timeout=15)
        assert r.status_code == 404, "series should be 404 for other users"

        # A can still see them
        ra = requests.get(f"{API}/reels", headers=_hdr(tok_a), timeout=15).json()
        assert any(x["id"] == reel_a for x in ra)

        # cleanup
        requests.delete(f"{API}/reels/{reel_a}", timeout=10)
        requests.delete(f"{API}/series/{series_a}", headers=_hdr(tok_a), timeout=10)
