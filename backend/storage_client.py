"""Emergent Managed Object Storage helpers (sync requests, call via threadpool)."""
import os
import time

import requests

STORAGE_BASE = (os.environ.get("INTEGRATION_PROXY_URL") or "").strip() or "https://integrations.emergentagent.com"
STORAGE_URL = STORAGE_BASE.rstrip("/") + "/objstore/api/v1/storage"
EMERGENT_KEY = os.environ.get("EMERGENT_LLM_KEY")
APP_NAME = "faceless-ai-reels"

_storage_key = None


def init_storage():
    """Call once; idempotent. Returns a reusable storage key."""
    global _storage_key
    if _storage_key:
        return _storage_key
    resp = requests.post(f"{STORAGE_URL}/init", json={"emergent_key": EMERGENT_KEY}, timeout=30)
    resp.raise_for_status()
    _storage_key = resp.json()["storage_key"]
    return _storage_key


def _reset():
    global _storage_key
    _storage_key = None


def put_object(path: str, data: bytes, content_type: str) -> dict:
    key = init_storage()
    last = None
    for attempt in range(3):
        resp = requests.put(
            f"{STORAGE_URL}/objects/{path}",
            headers={"X-Storage-Key": key, "Content-Type": content_type},
            data=data,
            timeout=180,
        )
        if resp.status_code < 500:
            resp.raise_for_status()
            return resp.json()
        # Transient 5xx (incl. 503 stale key): reset key and back off, then retry.
        last = resp
        _reset()
        key = init_storage()
        time.sleep(0.8 * (attempt + 1))
    last.raise_for_status()
    return last.json()


def get_object(path: str):
    key = init_storage()
    resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=120)
    if resp.status_code == 503:
        _reset()
        key = init_storage()
        resp = requests.get(f"{STORAGE_URL}/objects/{path}", headers={"X-Storage-Key": key}, timeout=120)
    resp.raise_for_status()
    return resp.content, resp.headers.get("Content-Type", "application/octet-stream")

# Feature boot: ElevenLabs + owner-scoped media + export/social routes.
try:
    import pipeline_ext  # noqa: F401
    import lock_boot  # noqa: F401
except Exception:
    pass
