"""
Iteration 12 — Bug fix + feature: AI engine toggle (key_mode) + error attribution.

Verifies:
 1. PUT /api/settings {key_mode:'builtin'} persists; GET returns 'builtin' + has_own_key=false.
 2. PUT {key_mode:'own'} switches back; invalid values coerced to 'own'.
 3. In 'builtin' mode a saved BYOK key is IGNORED for generation but still reported
    openai_key_set=true (masked value preserved).
 4. In 'own' mode with an invalid saved OpenAI key, POST /api/script returns 402 with a
    message that BLAMES THE USER'S OpenAI key (not the Universal Key).
 5. Switching same account to 'builtin' reroutes /api/script to the Universal key → success.

Throwaway accounts only — admin's real keys are never touched. Each throwaway account is
DELETEd via /api/auth/me at the end (or on failure via a session-fixture finaliser).
"""
import os
import random
import re
import pytest
import requests

BASE_URL = os.environ.get("EXPO_PUBLIC_BACKEND_URL", "http://localhost:8001").rstrip("/")
API = BASE_URL + "/api"


def _register_throwaway():
    email = f"TEST_keymode_{random.randint(100000, 999999)}@test.com"
    r = requests.post(f"{API}/auth/register",
                      json={"email": email, "password": "password123"}, timeout=30)
    assert r.status_code == 200, f"register failed: {r.status_code} {r.text}"
    token = r.json()["access_token"]
    return email, token


def _headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


def _cleanup(token):
    try:
        requests.delete(f"{API}/auth/me", headers=_headers(token), timeout=15)
    except Exception:
        pass


# --- key_mode persistence ---------------------------------------------------
class TestKeyModePersistence:
    def test_default_is_own_and_toggle_persists(self):
        _, token = _register_throwaway()
        try:
            # default
            r = requests.get(f"{API}/settings", headers=_headers(token), timeout=15)
            assert r.status_code == 200, r.text
            data = r.json()
            assert data.get("key_mode") == "own", f"default should be 'own', got {data.get('key_mode')}"
            assert data.get("has_own_key") is False

            # switch to builtin
            r = requests.put(f"{API}/settings", headers=_headers(token),
                             json={"key_mode": "builtin"}, timeout=15)
            assert r.status_code == 200, r.text
            assert r.json().get("key_mode") == "builtin"

            # GET reconfirms
            r = requests.get(f"{API}/settings", headers=_headers(token), timeout=15)
            assert r.status_code == 200
            body = r.json()
            assert body.get("key_mode") == "builtin"
            assert body.get("has_own_key") is False

            # switch back to own
            r = requests.put(f"{API}/settings", headers=_headers(token),
                             json={"key_mode": "own"}, timeout=15)
            assert r.status_code == 200
            assert r.json().get("key_mode") == "own"
        finally:
            _cleanup(token)

    def test_invalid_key_mode_coerced_to_own(self):
        _, token = _register_throwaway()
        try:
            r = requests.put(f"{API}/settings", headers=_headers(token),
                             json={"key_mode": "garbage"}, timeout=15)
            assert r.status_code == 200
            assert r.json().get("key_mode") == "own", f"unknown value should coerce to 'own', got {r.json().get('key_mode')}"

            r = requests.put(f"{API}/settings", headers=_headers(token),
                             json={"key_mode": ""}, timeout=15)
            assert r.status_code == 200
            assert r.json().get("key_mode") == "own"
        finally:
            _cleanup(token)


# --- BYOK key ignored in builtin mode but still REPORTED --------------------
class TestBuiltinIgnoresSavedKey:
    def test_saved_key_reported_but_ignored_in_builtin(self):
        _, token = _register_throwaway()
        try:
            # save a (fake) openai key
            r = requests.put(f"{API}/settings", headers=_headers(token),
                             json={"openai_key": "sk-invalidkey-abcdefghij0000000000"}, timeout=15)
            assert r.status_code == 200
            body = r.json()
            assert body.get("openai_key_set") is True
            assert body.get("openai_key_masked"), "masked value should exist"
            assert body.get("key_mode") == "own"
            assert body.get("has_own_key") is True  # in 'own' mode a saved key -> True

            # flip to builtin
            r = requests.put(f"{API}/settings", headers=_headers(token),
                             json={"key_mode": "builtin"}, timeout=15)
            assert r.status_code == 200
            body = r.json()
            # In builtin mode the key is still SAVED (reported) but ignored for generation
            assert body.get("key_mode") == "builtin"
            assert body.get("openai_key_set") is True, "saved key must still be reported"
            assert body.get("openai_key_masked"), "masked value must still be shown"
            # has_own_key is a signal for 'will this account use its own key' → false in builtin
            assert body.get("has_own_key") is False
        finally:
            _cleanup(token)


# --- error attribution: /api/script with bad OWN key ------------------------
class TestErrorAttribution:
    def test_bad_own_openai_key_blames_openai_not_universal(self):
        _, token = _register_throwaway()
        try:
            # save invalid openai key, key_mode stays 'own'
            r = requests.put(f"{API}/settings", headers=_headers(token),
                             json={"openai_key": "sk-invalidkey-0000000000"}, timeout=15)
            assert r.status_code == 200
            assert r.json().get("key_mode") == "own"

            # POST /script — should fail attributed to OpenAI
            r = requests.post(f"{API}/script", headers=_headers(token),
                              json={"topic": "coffee facts", "seconds": 15}, timeout=60)
            assert r.status_code == 402, f"expected 402, got {r.status_code}: {r.text[:300]}"
            detail = (r.json().get("detail") or "").lower()
            # Message should NAME OpenAI as the user's key
            assert "openai" in detail, f"detail should mention OpenAI (user's key), got: {detail[:300]}"
            # And should NOT tell them to top up the Universal Key
            assert "top up your universal" not in detail, f"detail wrongly blames Universal key: {detail[:300]}"
            # Should offer switching to built-in
            assert ("built-in" in detail) or ("builtin" in detail), \
                f"detail should offer switching AI engine to Built-in credits, got: {detail[:300]}"
        finally:
            _cleanup(token)

    def test_switching_to_builtin_reroutes_script_to_universal(self):
        _, token = _register_throwaway()
        try:
            # save invalid openai key
            r = requests.put(f"{API}/settings", headers=_headers(token),
                             json={"openai_key": "sk-invalidkey-0000000000"}, timeout=15)
            assert r.status_code == 200

            # confirm broken in 'own' mode
            r = requests.post(f"{API}/script", headers=_headers(token),
                              json={"topic": "coffee facts", "seconds": 15}, timeout=60)
            assert r.status_code == 402

            # flip to builtin — should now use Universal key
            r = requests.put(f"{API}/settings", headers=_headers(token),
                             json={"key_mode": "builtin"}, timeout=15)
            assert r.status_code == 200
            assert r.json().get("key_mode") == "builtin"

            r = requests.post(f"{API}/script", headers=_headers(token),
                              json={"topic": "coffee facts", "seconds": 15}, timeout=90)
            # Should be 200 (Universal key works) OR 402 with a Universal-key budget msg
            # (proving the reroute happened — attribution is no longer OpenAI).
            if r.status_code == 200:
                body = r.json()
                assert isinstance(body.get("script"), str) and len(body["script"]) > 20, \
                    f"expected non-empty script, got: {body}"
            else:
                assert r.status_code == 402
                detail = (r.json().get("detail") or "").lower()
                # In builtin mode, if this fails, it should NOT blame OpenAI (user's key)
                assert "your openai key" not in detail, \
                    f"builtin-mode error must not blame the user's OpenAI key: {detail[:300]}"
                # The Universal-key budget message is the expected fallback
                assert ("universal" in detail) or ("credits" in detail), \
                    f"builtin failure should reference Universal/credits, got: {detail[:300]}"
        finally:
            _cleanup(token)
