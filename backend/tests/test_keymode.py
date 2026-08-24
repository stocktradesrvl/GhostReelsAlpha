import json, urllib.request, urllib.error, time, random

BASE = "http://localhost:8001/api"

def call(method, path, body=None, token=None):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read().decode())
        except Exception: return e.code, {"detail": "?"}

# fresh throwaway user
email = f"keytest{random.randint(1000,9999)}@test.com"
st, r = call("POST", "/auth/register", {"email": email, "password": "password123"})
print("register", st)
token = r["access_token"]

# 1) default key_mode should be 'own'
st, r = call("GET", "/settings", None, token)
print("settings key_mode default:", r.get("key_mode"), "| has_own_key:", r.get("has_own_key"))

# 2) save an INVALID openai key (will be stored; test endpoint would reject but we bypass to test error attribution)
st, r = call("PUT", "/settings", {"openai_key": "sk-invalidkey-0000000000"}, token)
print("save bad key:", st, "openai_key_set:", r.get("openai_key_set"), "has_own_key:", r.get("has_own_key"))

# 3) /script should now fail attributed to OpenAI (their own key), NOT universal
st, r = call("POST", "/script", {"topic": "test topic about coffee", "seconds": 15}, token)
print("script with bad own key ->", st)
print("  message:", (r.get("detail") or "")[:200])

# 4) switch to builtin -> keys ignored -> /script should use universal (may succeed or hit universal budget)
st, r = call("PUT", "/settings", {"key_mode": "builtin"}, token)
print("switch builtin:", st, "key_mode:", r.get("key_mode"), "has_own_key:", r.get("has_own_key"))
st, r = call("POST", "/script", {"topic": "test topic about coffee", "seconds": 15}, token)
print("script in builtin mode ->", st, "| msg:", (r.get("detail") or r.get("script","OK")[:40] if isinstance(r.get("script"), str) else r.get("detail",""))[:120])

# cleanup
call("DELETE", "/auth/me", None, token)
print("DONE")
