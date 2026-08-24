import logging
import os
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv
import base64

import bcrypt
import jwt
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from datetime import timedelta
from fastapi import APIRouter, Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.responses import FileResponse, HTMLResponse
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool
from starlette.middleware.cors import CORSMiddleware

import pipeline
import storage_client
from reels_config import (
    BG_MAP,
    BG_MOTION_MAP,
    BG_MOTIONS,
    BG_THEMES,
    CAPTION_ANIM_MAP,
    CAPTION_ANIMS,
    CAPTION_FONT_MAP,
    CAPTION_FONTS,
    CAPTION_MAP,
    CAPTION_POSITION_MAP,
    CAPTION_POSITIONS,
    CAPTION_SIZE_MAP,
    CAPTION_SIZES,
    CAPTION_STYLES,
    IMAGE_STYLE_MAP,
    IMAGE_STYLES,
    MUSIC_MAP,
    MUSIC_TRACKS,
    VOICE_MAP,
    VOICE_SPEED_MAP,
    VOICE_SPEEDS,
    VOICES,
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

MEDIA_DIR = ROOT_DIR / "media"
MEDIA_DIR.mkdir(exist_ok=True)

PRIVACY_POLICY_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>GhostReelsAlpha — Privacy Policy</title>
<style>
  :root { color-scheme: dark; }
  body { margin:0; background:#0A0A0A; color:#E7E5E4; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; line-height:1.6; }
  .wrap { max-width:720px; margin:0 auto; padding:32px 20px 64px; }
  h1 { font-size:26px; margin:0 0 4px; }
  h2 { font-size:18px; margin:28px 0 8px; color:#F87171; }
  p, li { font-size:15px; color:#D6D3D1; }
  a { color:#F87171; }
  .muted { color:#A8A29E; font-size:13px; }
  ul { padding-left:20px; }
  hr { border:none; border-top:1px solid #292524; margin:28px 0; }
</style>
</head>
<body>
  <div class="wrap">
    <h1>Privacy Policy</h1>
    <p class="muted">GhostReelsAlpha — Faceless AI Reels. Last updated: June 2026.</p>
    <p>This policy explains what GhostReelsAlpha ("we", "the app") collects, how we use it, and the choices you have. We keep data collection to the minimum needed to run the app.</p>

    <h2>Information we collect</h2>
    <ul>
      <li><strong>Account:</strong> your email address and a securely hashed password. We never store your password in plain text.</li>
      <li><strong>Your content:</strong> the prompts/topics you enter and the reels (video, audio, captions, images) generated from them, so you can view, edit, and manage them.</li>
      <li><strong>Optional API keys (BYOK):</strong> if you choose to add your own OpenAI or Google API key, it is encrypted at rest using AES-256 and is never shown back to you in full or shared. You can remove it at any time.</li>
      <li><strong>Subscription status:</strong> whether you have an active subscription, provided through RevenueCat and the Apple App Store / Google Play. We do <strong>not</strong> collect or store your card or payment details — those are handled entirely by Apple/Google.</li>
    </ul>

    <h2>How we use your information</h2>
    <ul>
      <li>To create an account and let you sign in.</li>
      <li>To generate, store, and let you manage your reels.</li>
      <li>To provide AI features. When you generate content, your prompt/text is sent to the AI provider (OpenAI and/or Google) solely to produce your result.</li>
      <li>To determine whether your subscription unlocks unlimited generation.</li>
    </ul>

    <h2>What we do NOT do</h2>
    <ul>
      <li>We do <strong>not</strong> sell your personal data.</li>
      <li>We do <strong>not</strong> use your prompts or content to train AI models.</li>
      <li>We do <strong>not</strong> store your payment card details.</li>
    </ul>

    <h2>Data retention &amp; deletion</h2>
    <p>You can delete your account and all associated data at any time from <strong>Settings → Delete account</strong> in the app. This permanently removes your account, your reels, and your encrypted API keys from our systems.</p>

    <h2>Children</h2>
    <p>GhostReelsAlpha is not directed at children under 13, and we do not knowingly collect personal information from children under 13.</p>

    <h2>Third-party services</h2>
    <p>We rely on service providers to operate the app, including OpenAI and Google (AI generation), RevenueCat and Apple/Google (subscriptions and payments), and our cloud hosting/storage. Your use of AI features is also subject to those providers' terms.</p>

    <h2>Contact</h2>
    <p>Questions or requests about your privacy? Email <a href="mailto:russngina@gmail.com">russngina@gmail.com</a>.</p>

    <hr/>
    <p class="muted">By using GhostReelsAlpha you agree to this Privacy Policy.</p>
  </div>
</body>
</html>"""


TERMS_OF_SERVICE_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>GhostReelsAlpha — Terms of Service</title>
<style>
  :root { color-scheme: dark; }
  body { margin:0; background:#0A0A0A; color:#E7E5E4; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; line-height:1.6; }
  .wrap { max-width:720px; margin:0 auto; padding:32px 20px 64px; }
  h1 { font-size:26px; margin:0 0 4px; }
  h2 { font-size:18px; margin:28px 0 8px; color:#F87171; }
  p, li { font-size:15px; color:#D6D3D1; }
  a { color:#F87171; }
  .muted { color:#A8A29E; font-size:13px; }
  ul { padding-left:20px; }
  hr { border:none; border-top:1px solid #292524; margin:28px 0; }
</style>
</head>
<body>
  <div class="wrap">
    <h1>Terms of Service</h1>
    <p class="muted">GhostReelsAlpha — Faceless AI Reels. Last updated: June 2026.</p>
    <p>These Terms govern your use of the GhostReelsAlpha app. By creating an account or using the app, you agree to these Terms. If you do not agree, do not use the app.</p>

    <h2>1. The service</h2>
    <p>GhostReelsAlpha turns your topics or scripts into short vertical videos using AI (voiceover, captions, visuals, and rendering). Features and availability may change over time.</p>

    <h2>2. Eligibility &amp; accounts</h2>
    <p>You must be at least 13 years old to use GhostReelsAlpha. You are responsible for keeping your login credentials secure and for all activity under your account.</p>

    <h2>3. Your content &amp; responsibility</h2>
    <ul>
      <li>You are responsible for the prompts, scripts, and any material you submit, and for the reels you generate.</li>
      <li>You must have the rights to any content you upload (for example, custom outro videos), and you must not create content that is illegal, infringing, hateful, deceptive, or that violates others' rights.</li>
      <li>AI output can be inaccurate or unexpected. You are responsible for reviewing content before publishing or sharing it, and for complying with the rules of any platform you post to.</li>
    </ul>

    <h2>4. Bring Your Own Key (BYOK)</h2>
    <p>If you add your own OpenAI or Google API key, you are responsible for your usage and any charges from those providers, and your use is subject to their terms. Your key is encrypted at rest and never shown back to you in full.</p>

    <h2>5. Subscriptions &amp; billing</h2>
    <ul>
      <li>Subscriptions are sold as in-app purchases through the Apple App Store or Google Play and managed by RevenueCat. We do not receive or store your payment card details.</li>
      <li>Subscriptions renew automatically until cancelled. Manage or cancel anytime in your App Store or Google Play account settings; deleting the app does not cancel a subscription.</li>
      <li>Free accounts include a limited number of free reels; a subscription (or your own API key) unlocks unlimited generation. Refunds are handled by Apple/Google per their policies.</li>
    </ul>

    <h2>6. Acceptable use</h2>
    <p>Do not misuse the service: no reverse engineering, no attempts to break security or quotas, no automated abuse, and no using the app to generate content that violates law or third-party rights.</p>

    <h2>7. Intellectual property</h2>
    <p>The app itself (software, design, branding) belongs to us. Subject to these Terms and applicable third-party AI provider terms, the reels you generate are yours to use.</p>

    <h2>8. Termination &amp; deletion</h2>
    <p>You can delete your account and all associated data anytime from <strong>Settings &rarr; Delete account</strong>. We may suspend or terminate accounts that violate these Terms.</p>

    <h2>9. Disclaimers &amp; limitation of liability</h2>
    <p>The service is provided "as is" without warranties of any kind. To the maximum extent permitted by law, we are not liable for indirect or consequential damages, or for content generated by the AI.</p>

    <h2>10. Changes</h2>
    <p>We may update these Terms; continued use after changes means you accept the updated Terms.</p>

    <h2>11. Contact</h2>
    <p>Questions about these Terms? Email <a href="mailto:russngina@gmail.com">russngina@gmail.com</a>.</p>

    <hr/>
    <p class="muted">By using GhostReelsAlpha you agree to these Terms of Service.</p>
  </div>
</body>
</html>"""


DELETE_ACCOUNT_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>GhostReelsAlpha — Delete Your Account</title>
<style>
  :root { color-scheme: dark; }
  body { margin:0; background:#0A0A0A; color:#E7E5E4; font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif; line-height:1.6; }
  .wrap { max-width:720px; margin:0 auto; padding:32px 20px 64px; }
  h1 { font-size:26px; margin:0 0 4px; }
  h2 { font-size:18px; margin:28px 0 8px; color:#F87171; }
  p, li { font-size:15px; color:#D6D3D1; }
  a { color:#F87171; }
  .muted { color:#A8A29E; font-size:13px; }
  ol, ul { padding-left:22px; }
  li { margin-bottom:6px; }
  hr { border:none; border-top:1px solid #292524; margin:28px 0; }
  .card { background:#141414; border:1px solid #292524; border-radius:12px; padding:16px 18px; margin-top:16px; }
</style>
</head>
<body>
  <div class="wrap">
    <h1>Delete Your Account</h1>
    <p class="muted">GhostReelsAlpha — Faceless AI Reels. Last updated: June 2026.</p>
    <p>You can permanently delete your GhostReelsAlpha account and all associated data at any time. Deletion is immediate and cannot be undone.</p>

    <h2>Delete from within the app (recommended)</h2>
    <ol>
      <li>Open the <strong>GhostReelsAlpha</strong> app and sign in.</li>
      <li>Go to the <strong>Settings</strong> tab (gear icon).</li>
      <li>Scroll to the bottom and tap <strong>Delete account</strong>.</li>
      <li>Confirm in the dialog. Your account is deleted right away and you are signed out.</li>
    </ol>

    <h2>Prefer email? Request deletion manually</h2>
    <div class="card">
      <p>If you can't access the app, email <a href="mailto:russngina@gmail.com?subject=Delete%20my%20GhostReelsAlpha%20account">russngina@gmail.com</a>
      from the address associated with your account and ask us to delete it. We will remove your account and data within 30 days and confirm by email.</p>
    </div>

    <h2>What gets deleted</h2>
    <p>Deleting your account permanently removes:</p>
    <ul>
      <li>Your account and email/login credentials</li>
      <li>All reels you created (video, audio, captions, and images)</li>
      <li>Your saved series and custom outros</li>
      <li>Any API keys you added (stored encrypted), plus your app settings</li>
    </ul>
    <p class="muted">Note: an active paid subscription is billed and managed by the Google Play Store (or Apple App Store). Deleting your account does not cancel it — cancel the subscription separately in your store account settings.</p>

    <hr/>
    <p class="muted">Questions? Contact <a href="mailto:russngina@gmail.com">russngina@gmail.com</a>.</p>
  </div>
</body>
</html>"""


mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

# ----------------------------------------------------------------------------
# Auth (email+password JWT) + per-user encrypted BYOK + free-reel quota
# ----------------------------------------------------------------------------
JWT_SECRET = os.environ["JWT_SECRET"]
JWT_ALG = "HS256"
ACCESS_MIN = 60 * 24 * 30  # 30-day mobile sessions
AES_KEY = base64.b64decode(os.environ["AES_SECRET_B64"])
DUMMY_HASH = bcrypt.hashpw(b"dummy-password", bcrypt.gensalt()).decode()
FREE_LIMIT = 3
# Owner/admin emails get durable unlimited generation (never reset by the
# RevenueCat client sync, which only touches `is_subscribed`).
ADMIN_EMAILS = {"russngina@gmail.com"}
bearer = HTTPBearer(auto_error=False)


def is_admin_user(u: dict) -> bool:
    return bool(u.get("is_admin")) or (u.get("email", "").strip().lower() in ADMIN_EMAILS)


# --- Content moderation (server-side prompt guardrail) -----------------------
# Blocks clearly-disallowed requests (explicit sexual / CSAM, graphic violence &
# self-harm, illegal-drug how-to) BEFORE any AI generation runs, so the app has a
# real content guardrail (cleaner store content rating). Phrases use word
# boundaries to avoid false positives on ordinary words.
_BLOCKED_PATTERNS = re.compile(
    r"\b("
    # explicit sexual / CSAM / sexual violence
    r"porn|pornographic|hardcore\s+sex|blowjob|handjob|deepthroat|gangbang|bukkake|creampie|"
    r"child\s*porn|childporn|\bcp\b|pedophil\w*|paedophil\w*|\bloli\b|\bcsam\b|bestiality|zoophilia|"
    r"rape|raping|molest\w*|non[-\s]?consensual|"
    # graphic violence / self-harm / weapons how-to
    r"behead\w*|dismember\w*|mutilat\w*|gore|torture\s+(?:someone|a\s+\w+)|"
    r"how\s+to\s+kill|kill\s+(?:myself|yourself|him|her|them|people)|mass\s+shooting|school\s+shooting|"
    r"suicide\s+(?:method|how|note|plan)|self[-\s]?harm|"
    r"how\s+to\s+make\s+(?:a\s+)?(?:bomb|explosive|pipe\s*bomb)|build\s+a\s+bomb|"
    # illegal-drug how-to / trade
    r"heroin|cocaine|crack\s+cocaine|\bmeth\b|methamphetamine|crystal\s*meth|fentanyl|"
    r"\bmdma\b|ecstasy|\blsd\b|how\s+to\s+(?:make|cook|synthesize)\s+(?:meth|drugs|cocaine)|"
    r"buy\s+(?:illegal\s+)?drugs|sell\s+(?:illegal\s+)?drugs"
    r")\b",
    re.IGNORECASE,
)

MODERATION_MESSAGE = (
    "This request can't be processed. It appears to reference explicit sexual, "
    "graphic violent/self-harm, or illegal-drug content, which isn't allowed. "
    "Please revise your topic or script."
)


def moderate_text(*texts: str) -> None:
    """Raise HTTP 400 if any provided text hits the disallowed-content denylist."""
    combined = " ".join(t for t in texts if t)
    if combined.strip() and _BLOCKED_PATTERNS.search(combined):
        raise HTTPException(400, MODERATION_MESSAGE)


def hash_pw(p: str) -> str:
    return bcrypt.hashpw(p.encode()[:72], bcrypt.gensalt(12)).decode()


def verify_pw(p: str, h) -> bool:
    try:
        return bcrypt.checkpw(p.encode()[:72], h.encode() if isinstance(h, str) else h)
    except Exception:  # noqa: BLE001
        return False


def make_token(uid: str) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode({"sub": uid, "iat": now, "exp": now + timedelta(minutes=ACCESS_MIN)},
                      JWT_SECRET, algorithm=JWT_ALG)


def enc_key(txt: str, uid: str, provider: str) -> str:
    nonce = os.urandom(12)
    ct = AESGCM(AES_KEY).encrypt(nonce, txt.encode(), f"{uid}:{provider}".encode())
    return base64.b64encode(nonce + ct).decode()


def dec_key(blob: str, uid: str, provider: str) -> str:
    packed = base64.b64decode(blob)
    return AESGCM(AES_KEY).decrypt(packed[:12], packed[12:], f"{uid}:{provider}".encode()).decode()


async def current_user(cred: HTTPAuthorizationCredentials = Depends(bearer)):
    unauth = HTTPException(401, "Not authenticated")
    if not cred or not cred.credentials:
        raise unauth
    try:
        payload = jwt.decode(cred.credentials, JWT_SECRET, algorithms=[JWT_ALG])
        uid = payload.get("sub")
    except Exception:  # noqa: BLE001
        raise unauth
    user = await db.users.find_one({"id": uid})
    if not user:
        raise unauth
    return user


def user_keys(user: dict) -> tuple:
    """Return decrypted (openai, google) keys for a user, or ('','')."""
    oa = gk = ""
    if user.get("openai_key_enc"):
        try:
            oa = dec_key(user["openai_key_enc"], user["id"], "openai")
        except Exception as e:  # noqa: BLE001
            oa = ""
            logger.warning("BYOK openai decrypt FAILED for user=%s (%s) — falling back to shared key. "
                           "AES secret likely changed; user must re-save their key.", user.get("id"), e)
    if user.get("google_key_enc"):
        try:
            gk = dec_key(user["google_key_enc"], user["id"], "google")
        except Exception as e:  # noqa: BLE001
            gk = ""
            logger.warning("BYOK google decrypt FAILED for user=%s (%s) — falling back to shared key. "
                           "AES secret likely changed; user must re-save their key.", user.get("id"), e)
    return oa, gk


def public_user(u: dict) -> dict:
    oa, gk = user_keys(u)
    return {
        "id": u["id"], "email": u["email"],
        "free_used": u.get("free_used", 0), "free_limit": FREE_LIMIT,
        "is_subscribed": bool(u.get("is_subscribed")),
        "is_admin": is_admin_user(u),
        "has_own_key": bool(oa or gk),
        "openai_key_set": bool(u.get("openai_key_enc")),
        "google_key_set": bool(u.get("google_key_enc")),
        "openai_key_masked": _mask_key(oa),
        "google_key_masked": _mask_key(gk),
        "brand_handle": u.get("brand_handle", ""),
    }


async def enforce_quota(user: dict):
    oa, gk = user_keys(user)
    if oa or gk or user.get("is_subscribed") or is_admin_user(user):
        return
    if user.get("free_used", 0) < FREE_LIMIT:
        return
    raise HTTPException(402, (
        f"You've used your {FREE_LIMIT} free reels. Add your own OpenAI or Google key "
        f"in Settings, or subscribe, to keep generating."
    ))


async def consume_quota(user: dict):
    oa, gk = user_keys(user)
    if not (oa or gk) and not user.get("is_subscribed") and not is_admin_user(user):
        await db.users.update_one({"id": user["id"]}, {"$inc": {"free_used": 1}})


async def owned_reel(reel_id: str, user: dict) -> dict:
    """Fetch a reel and assert the requester owns it (404 if not, to avoid leaking existence)."""
    reel = await db.reels.find_one({"id": reel_id})
    if not reel or reel.get("user_id") != user["id"]:
        raise HTTPException(404, "Reel not found")
    return reel


async def apply_owner_keys(reel: dict):
    """Load the reel owner's BYOK keys into the pipeline for this generation."""
    oa = gk = ""
    if reel.get("user_id"):
        owner = await db.users.find_one({"id": reel["user_id"]})
        if owner:
            oa, gk = user_keys(owner)
    pipeline.set_user_keys(oa, gk)

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("reels")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def classify_error(exc) -> tuple:
    """Map raw pipeline exceptions to (error_code, friendly_message)."""
    msg = str(exc) or ""
    if re.search(r"invalid[_ ]?api[_ ]?key|incorrect api key|api key not valid|authentication|unauthorized|permission denied|\b401\b|\b403\b", msg, re.I):
        return "key", (
            "Your API key was rejected. Check the OpenAI / Google key you saved in "
            "Settings → AI keys (or clear it to use the built-in credits)."
        )
    if re.search(r"budget|exceeded|insufficient|quota|credit|rate limit|\b429\b", msg, re.I):
        return "budget", (
            "You're out of AI credits. Top up your Universal Key "
            "(Profile → Manage plan → Universal Key → Add Balance), then try again."
        )
    if re.search(r"objstore|storage|50\d\s+server error", msg, re.I):
        return "storage", (
            "Couldn't save your video to cloud storage just now. "
            "Please tap Try again in a moment."
        )
    return "generic", (msg[:300] or "Something went wrong while generating your reel.")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------
class ScriptRequest(BaseModel):
    topic: str
    seconds: int = 30


class ReelSettings(BaseModel):
    seconds: int = 30
    visual_mode: str = "gradient"       # "gradient" | "ai"
    image_style: str = "cinematic"
    voice_id: str = "onyx"
    voice_speed: str = "normal"
    caption_style: str = "signal"
    caption_position: str = "center"
    caption_size: str = "m"
    caption_font: str = "barlow"
    caption_anim: str = "pop"
    bg_theme: str = "ember"
    bg_motion: str = "subtle"
    music_id: str = "none"
    music_volume: float = 0.13
    watermark: Optional[str] = None
    hook_enabled: bool = False
    endcard_text: Optional[str] = None
    custom_c1: Optional[str] = None
    custom_c2: Optional[str] = None
    outro_id: Optional[str] = None


class CreateReelRequest(ReelSettings):
    title: Optional[str] = None
    input_mode: str = "topic"          # "topic" | "script"
    topic: Optional[str] = None
    script: Optional[str] = None


class BatchReelRequest(ReelSettings):
    topics: List[str] = []
    scheduled_at: Optional[str] = None  # ISO time; if future, reels wait until then
    # Optional reviewed scripts: [{topic, script}] paired 1:1 with `topics`.
    scripts: Optional[List[dict]] = None


class Character(BaseModel):
    name: str = ""
    description: str = ""


class SeriesCreate(ReelSettings):
    title: str
    premise: str = ""
    tone: str = ""
    characters: List[Character] = []


class SuggestRequest(BaseModel):
    premise: str
    tone: str = ""
    count: int = 3


class EpisodeRequest(BaseModel):
    topic: Optional[str] = None
    script: Optional[str] = None   # reviewed/edited script; skips AI scripting when provided


class SceneRegenRequest(BaseModel):
    prompt: Optional[str] = None


class LineRegenRequest(BaseModel):
    text: str


SETTINGS_ID = "global"


class SettingsUpdate(BaseModel):
    openai_key: Optional[str] = None   # None = unchanged; "" = clear
    google_key: Optional[str] = None
    brand_handle: Optional[str] = None


class TestKeysRequest(BaseModel):
    openai_key: Optional[str] = None
    google_key: Optional[str] = None


class AuthIn(BaseModel):
    email: str
    password: str


class SubscriptionSync(BaseModel):
    is_subscribed: bool


PUBLIC_FIELDS = {
    "id", "title", "input_mode", "topic", "script", "series_id", "episode_number", "seconds", "visual_mode", "image_style", "voice_id", "voice_speed",
    "caption_style", "caption_position", "caption_size", "caption_font", "caption_anim",
    "bg_theme", "bg_motion", "custom_c1", "custom_c2", "music_id", "music_volume", "watermark",
    "hook_enabled", "endcard_text", "outro_id", "views", "downloads", "scheduled_at",
    "status", "progress", "stage_label", "error", "error_code",
    "duration", "word_count", "has_video", "created_at", "updated_at",
}

SERIES_PUBLIC_FIELDS = {
    "id", "title", "premise", "tone", "characters", "settings",
    "episode_count", "created_at", "updated_at",
}


def validate_settings(s: ReelSettings):
    checks = [
        (s.voice_id, VOICE_MAP, "voice"),
        (s.voice_speed, VOICE_SPEED_MAP, "voice speed"),
        (s.caption_style, CAPTION_MAP, "caption style"),
        (s.caption_position, CAPTION_POSITION_MAP, "caption position"),
        (s.caption_size, CAPTION_SIZE_MAP, "caption size"),
        (s.caption_font, CAPTION_FONT_MAP, "caption font"),
        (s.caption_anim, CAPTION_ANIM_MAP, "caption animation"),
        (s.bg_motion, BG_MOTION_MAP, "background motion"),
        (s.music_id, MUSIC_MAP, "music track"),
    ]
    for value, table, label in checks:
        if value not in table:
            raise HTTPException(400, f"Unknown {label}")
    if s.bg_theme != "custom" and s.bg_theme not in BG_MAP:
        raise HTTPException(400, "Unknown background theme")
    if s.bg_theme == "custom":
        def _ok(h):
            h = (h or "").strip().lstrip("#")
            return len(h) == 6 and all(c in "0123456789abcdefABCDEF" for c in h)
        if not (_ok(s.custom_c1) and _ok(s.custom_c2)):
            raise HTTPException(400, "Custom theme needs two hex colours")


def build_reel_doc(s: ReelSettings, input_mode: str, topic, script, title: str,
                   series_id: str = None, episode_number: int = None, user_id: str = None) -> dict:
    reel_id = str(uuid.uuid4())
    return {
        "id": reel_id,
        "user_id": user_id,
        "title": title,
        "input_mode": input_mode,
        "topic": topic,
        "script": script,
        "series_id": series_id,
        "episode_number": episode_number,
        "seconds": s.seconds,
        "visual_mode": s.visual_mode if s.visual_mode in ("gradient", "ai") else "gradient",
        "image_style": s.image_style if s.image_style in IMAGE_STYLE_MAP else "cinematic",
        "voice_id": s.voice_id,
        "voice_speed": s.voice_speed,
        "caption_style": s.caption_style,
        "caption_position": s.caption_position,
        "caption_size": s.caption_size,
        "caption_font": s.caption_font,
        "caption_anim": s.caption_anim,
        "bg_theme": s.bg_theme,
        "bg_motion": s.bg_motion,
        "custom_c1": (s.custom_c1 or None),
        "custom_c2": (s.custom_c2 or None),
        "outro_id": (s.outro_id or None),
        "music_id": s.music_id,
        "music_volume": max(0.0, min(1.0, float(s.music_volume))),
        "watermark": (s.watermark or "").strip()[:32] or None,
        "hook_enabled": bool(s.hook_enabled),
        "endcard_text": (s.endcard_text or "").strip()[:40] or None,
        "views": 0,
        "downloads": 0,
        "scheduled_at": None,
        "status": "queued",
        "progress": 0,
        "stage_label": "Queued",
        "error": None,
        "error_code": None,
        "duration": None,
        "word_count": len(script.split()) if script else None,
        "has_video": False,
        "video_path": None,
        "thumb_path": None,
        "audio_path": None,
        "words": None,
        "scenes": None,
        "segments": None,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


def public_reel(doc: dict) -> dict:
    return {k: doc.get(k) for k in PUBLIC_FIELDS}


def public_series(doc: dict) -> dict:
    return {k: doc.get(k) for k in SERIES_PUBLIC_FIELDS}


async def update_reel(reel_id: str, **fields):
    fields["updated_at"] = now_iso()
    await db.reels.update_one({"id": reel_id}, {"$set": fields})


# ---------------------------------------------------------------------------
# Pipeline orchestrator (runs in background)
# ---------------------------------------------------------------------------
async def run_pipeline(reel_id: str):
    workdir = pipeline.new_workdir()
    try:
        reel = await db.reels.find_one({"id": reel_id})
        if not reel:
            return
        await apply_owner_keys(reel)

        series = None
        if reel.get("series_id"):
            series = await db.series.find_one({"id": reel["series_id"]})

        script = reel.get("script")
        # Stage 1: script (topic mode without a script yet)
        if not script:
            await update_reel(reel_id, status="scripting", progress=10, stage_label="Writing script")
            if series:
                prior = await db.reels.find({
                    "series_id": series["id"], "status": "ready",
                    "episode_number": {"$lt": reel.get("episode_number", 1)},
                }).sort("episode_number", 1).to_list(20)
                prior_scripts = [p.get("script") for p in prior if p.get("script")]
                script = await pipeline.generate_series_script(
                    series, prior_scripts, reel.get("topic"), reel.get("seconds", 30)
                )
            else:
                script = await pipeline.generate_script(reel["topic"], reel.get("seconds", 30))
            await update_reel(reel_id, script=script, word_count=len(script.split()))

        # Stage 2: voiceover — synth per-sentence so a single line can be re-recorded later
        await update_reel(reel_id, status="voicing", progress=30, stage_label="Recording voiceover")
        audio_path = os.path.join(workdir, "voice.mp3")
        speed = VOICE_SPEED_MAP.get(reel.get("voice_speed", "normal"), VOICE_SPEED_MAP["normal"])["speed"]
        sentences = pipeline.split_sentences(script)
        seg_paths = await pipeline.synth_voice_segments(sentences, reel["voice_id"], workdir, speed=speed)
        await pipeline.concat_audio(seg_paths, audio_path, transcript=" ".join(sentences))
        # Persist the full voice track + each sentence clip (for per-line re-record).
        with open(audio_path, "rb") as f:
            apath = f"{storage_client.APP_NAME}/reels/{reel_id}/voice.mp3"
            await run_in_threadpool(storage_client.put_object, apath, f.read(), "audio/mpeg")
        segments = []
        for i, (sent, sp) in enumerate(zip(sentences, seg_paths)):
            seg_store = f"{storage_client.APP_NAME}/reels/{reel_id}/seg_{i}.mp3"
            with open(sp, "rb") as f:
                await run_in_threadpool(storage_client.put_object, seg_store, f.read(), "audio/mpeg")
            segments.append({"text": sent, "audio_path": seg_store})
        await update_reel(reel_id, segments=segments)

        # Stage 3: captions
        await update_reel(reel_id, status="captioning", progress=55, stage_label="Aligning captions")
        words, duration = await pipeline.transcribe_words(audio_path)
        if not duration or duration <= 0:
            duration = max(3.0, len(script.split()) / pipeline.WORDS_PER_SEC)
        await update_reel(reel_id, audio_path=apath, words=words, duration=round(duration, 2))
        ass_path = os.path.join(workdir, "subs.ass")
        pipeline.build_ass(
            words, duration, reel["caption_style"], ass_path,
            position=reel.get("caption_position", "center"),
            size=reel.get("caption_size", "m"),
            watermark=reel.get("watermark") or "",
            hook_text=pipeline.hook_line(script) if reel.get("hook_enabled") else "",
            caption_font=reel.get("caption_font", "barlow"),
            endcard_text=reel.get("endcard_text") or "",
            caption_anim=reel.get("caption_anim", "pop"),
        )

        # Stage 4: render
        out_path = str(MEDIA_DIR / f"{reel_id}.mp4")
        thumb_path = str(MEDIA_DIR / f"{reel_id}.jpg")
        if reel.get("visual_mode") == "ai":
            await update_reel(reel_id, status="rendering", progress=66,
                              stage_label="Painting visuals", duration=round(duration, 2))
            bible = pipeline.character_bible_text(series) if series else ""
            n = pipeline.scene_count(reel.get("seconds", 30))
            prompts = await pipeline.generate_scene_prompts(script, n, character_bible=bible)
            style_suffix = IMAGE_STYLE_MAP.get(reel.get("image_style", "cinematic"), IMAGE_STYLE_MAP["cinematic"])["suffix"]
            images = await pipeline.generate_images(prompts, workdir, style_suffix=style_suffix, character_bible=bible)
            # Persist prompts + images so a single scene can be regenerated later.
            scenes = []
            for i, (p, img) in enumerate(zip(prompts, images)):
                spath = f"{storage_client.APP_NAME}/reels/{reel_id}/scene_{i}.png"
                with open(img, "rb") as f:
                    await run_in_threadpool(storage_client.put_object, spath, f.read(), "image/png")
                scenes.append({"prompt": p, "image_path": spath})
            await update_reel(reel_id, scenes=scenes)
            await update_reel(reel_id, status="rendering", progress=82, stage_label="Rendering video")
            await pipeline.render_video_images(
                audio_path, "subs.ass", images, duration, workdir, out_path,
                music_id=reel.get("music_id", "none"),
                music_volume=reel.get("music_volume", 0.13),
            )
        else:
            await update_reel(reel_id, status="rendering", progress=72,
                              stage_label="Rendering video", duration=round(duration, 2))
            await pipeline.render_video(
                audio_path, "subs.ass", reel["bg_theme"], duration, workdir, out_path,
                music_id=reel.get("music_id", "none"),
                music_volume=reel.get("music_volume", 0.13),
                bg_motion=reel.get("bg_motion", "subtle"),
                custom_colors=[reel.get("custom_c1"), reel.get("custom_c2")],
            )
        await pipeline.extract_thumbnail(out_path, thumb_path)
        await finalize_and_upload(reel, reel_id, workdir, out_path, thumb_path, duration)
        logger.info("Reel %s ready (%.1fs)", reel_id, duration)
    except Exception as e:  # noqa: BLE001
        logger.exception("Pipeline failed for %s", reel_id)
        code, friendly = classify_error(e)
        await update_reel(reel_id, status="failed", stage_label="Generation failed",
                          error=friendly, error_code=code)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


async def finalize_and_upload(reel, reel_id, workdir, out_path, thumb_path, duration):
    """Append optional outro, then upload video + thumb to durable storage and mark ready."""
    outro_id = reel.get("outro_id")
    if outro_id:
        outro_doc = await db.outros.find_one({"id": outro_id})
        if outro_doc and outro_doc.get("storage_path"):
            await update_reel(reel_id, stage_label="Adding outro")
            local_outro = os.path.join(workdir, "outro.mp4")
            content, _ = await run_in_threadpool(storage_client.get_object, outro_doc["storage_path"])
            with open(local_outro, "wb") as f:
                f.write(content)
            final_path = os.path.join(workdir, "final.mp4")
            await pipeline.append_outro(out_path, local_outro, final_path)
            shutil.move(final_path, out_path)

    await update_reel(reel_id, status="uploading", progress=92, stage_label="Finishing up")
    with open(out_path, "rb") as f:
        video_bytes = f.read()
    vpath = f"{storage_client.APP_NAME}/reels/{reel_id}.mp4"
    await run_in_threadpool(storage_client.put_object, vpath, video_bytes, "video/mp4")
    tpath = None
    if os.path.exists(thumb_path):
        with open(thumb_path, "rb") as f:
            tpath = f"{storage_client.APP_NAME}/reels/{reel_id}.jpg"
            await run_in_threadpool(storage_client.put_object, tpath, f.read(), "image/jpeg")
    await update_reel(
        reel_id, status="ready", progress=100, stage_label="Ready",
        has_video=True, video_path=vpath, thumb_path=tpath, error=None, error_code=None,
    )


async def recompose_reel(reel_id: str):
    """Re-render from stored voice + word timings (+ scene images for AI) — no re-voicing."""
    workdir = pipeline.new_workdir()
    try:
        reel = await db.reels.find_one({"id": reel_id})
        is_ai = reel and reel.get("visual_mode") == "ai"
        if not reel or not reel.get("audio_path") or (is_ai and not reel.get("scenes")):
            await update_reel(reel_id, status="failed", stage_label="Re-render failed",
                              error="This reel can't be re-rendered.", error_code="generic")
            return
        await update_reel(reel_id, status="rendering", progress=70, stage_label="Re-rendering",
                          error=None, error_code=None)

        audio_path = os.path.join(workdir, "voice.mp3")
        content, _ = await run_in_threadpool(storage_client.get_object, reel["audio_path"])
        with open(audio_path, "wb") as f:
            f.write(content)

        words = reel.get("words") or []
        duration = float(reel.get("duration") or max(3.0, len(words) * 0.4))
        ass_path = os.path.join(workdir, "subs.ass")
        pipeline.build_ass(
            words, duration, reel["caption_style"], ass_path,
            position=reel.get("caption_position", "center"),
            size=reel.get("caption_size", "m"),
            watermark=reel.get("watermark") or "",
            hook_text=pipeline.hook_line(reel.get("script") or "") if reel.get("hook_enabled") else "",
            caption_font=reel.get("caption_font", "barlow"),
            endcard_text=reel.get("endcard_text") or "",
            caption_anim=reel.get("caption_anim", "pop"),
        )

        out_path = str(MEDIA_DIR / f"{reel_id}.mp4")
        thumb_path = str(MEDIA_DIR / f"{reel_id}.jpg")
        if is_ai:
            images = []
            for i, s in enumerate(reel["scenes"]):
                ip = os.path.join(workdir, f"scene_{i}.png")
                content, _ = await run_in_threadpool(storage_client.get_object, s["image_path"])
                with open(ip, "wb") as f:
                    f.write(content)
                images.append(ip)
            await pipeline.render_video_images(
                audio_path, "subs.ass", images, duration, workdir, out_path,
                music_id=reel.get("music_id", "none"),
                music_volume=reel.get("music_volume", 0.13),
            )
        else:
            await pipeline.render_video(
                audio_path, "subs.ass", reel["bg_theme"], duration, workdir, out_path,
                music_id=reel.get("music_id", "none"),
                music_volume=reel.get("music_volume", 0.13),
                bg_motion=reel.get("bg_motion", "subtle"),
                custom_colors=[reel.get("custom_c1"), reel.get("custom_c2")],
            )
        await pipeline.extract_thumbnail(out_path, thumb_path)
        await finalize_and_upload(reel, reel_id, workdir, out_path, thumb_path, duration)
        logger.info("Reel %s recomposed", reel_id)
    except Exception as e:  # noqa: BLE001
        logger.exception("Recompose failed for %s", reel_id)
        code, friendly = classify_error(e)
        await update_reel(reel_id, status="failed", stage_label="Re-render failed",
                          error=friendly, error_code=code)
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


async def regenerate_scene_task(reel_id: str, index: int, prompt: str = None):
    """Regenerate a single scene image, then recompose the reel."""
    workdir = pipeline.new_workdir()
    try:
        reel = await db.reels.find_one({"id": reel_id})
        scenes = list(reel.get("scenes") or [])
        if index < 0 or index >= len(scenes):
            return
        await apply_owner_keys(reel)
        await update_reel(reel_id, status="rendering", progress=40, stage_label="Repainting scene",
                          error=None, error_code=None)
        if prompt and prompt.strip():
            scenes[index]["prompt"] = prompt.strip()[:400]

        series = await db.series.find_one({"id": reel["series_id"]}) if reel.get("series_id") else None
        bible = pipeline.character_bible_text(series) if series else ""
        style_suffix = IMAGE_STYLE_MAP.get(reel.get("image_style", "cinematic"), IMAGE_STYLE_MAP["cinematic"])["suffix"]
        new_imgs = await pipeline.generate_images([scenes[index]["prompt"]], workdir,
                                                  style_suffix=style_suffix, character_bible=bible)
        spath = scenes[index]["image_path"]
        with open(new_imgs[0], "rb") as f:
            await run_in_threadpool(storage_client.put_object, spath, f.read(), "image/png")
        # bust local cache of the scene image so the editor shows the new art
        local_scene = MEDIA_DIR / f"scene_{reel_id}_{index}.png"
        if local_scene.exists():
            local_scene.unlink(missing_ok=True)
        await update_reel(reel_id, scenes=scenes)
    except Exception as e:  # noqa: BLE001
        logger.exception("Scene regen failed for %s[%s]", reel_id, index)
        code, friendly = classify_error(e)
        await update_reel(reel_id, status="failed", stage_label="Re-render failed",
                          error=friendly, error_code=code)
        shutil.rmtree(workdir, ignore_errors=True)
        return
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    await recompose_reel(reel_id)


async def regenerate_line_task(reel_id: str, index: int, text: str):
    """Re-record one sentence, splice it back into the voice track, re-time captions, re-render."""
    workdir = pipeline.new_workdir()
    try:
        reel = await db.reels.find_one({"id": reel_id})
        segments = list(reel.get("segments") or [])
        if index < 0 or index >= len(segments):
            return
        await apply_owner_keys(reel)
        await update_reel(reel_id, status="voicing", progress=25, stage_label="Re-recording line",
                          error=None, error_code=None)
        segments[index]["text"] = (text or "").strip()[:400] or segments[index]["text"]

        speed = VOICE_SPEED_MAP.get(reel.get("voice_speed", "normal"), VOICE_SPEED_MAP["normal"])["speed"]
        # Re-record ONLY the edited sentence.
        new_seg = os.path.join(workdir, f"seg_{index}.mp3")
        await pipeline.synth_voice(segments[index]["text"], reel["voice_id"], new_seg, speed=speed)
        with open(new_seg, "rb") as f:
            await run_in_threadpool(storage_client.put_object, segments[index]["audio_path"], f.read(), "audio/mpeg")

        # Rebuild the full voice track from all (mostly unchanged) sentence clips.
        seg_paths = []
        for i, seg in enumerate(segments):
            lp = os.path.join(workdir, f"seg_{i}.mp3")
            content, _ = await run_in_threadpool(storage_client.get_object, seg["audio_path"])
            with open(lp, "wb") as f:
                f.write(content)
            seg_paths.append(lp)
        audio_path = os.path.join(workdir, "voice.mp3")
        transcript = " ".join(s["text"] for s in segments)
        await pipeline.concat_audio(seg_paths, audio_path, transcript=transcript)
        with open(audio_path, "rb") as f:
            await run_in_threadpool(storage_client.put_object, reel["audio_path"], f.read(), "audio/mpeg")

        await update_reel(reel_id, status="captioning", progress=55, stage_label="Re-aligning captions")
        words, duration = await pipeline.transcribe_words(audio_path)
        if not duration or duration <= 0:
            duration = max(3.0, len(transcript.split()) / pipeline.WORDS_PER_SEC)
        await update_reel(reel_id, segments=segments, words=words, script=transcript,
                          word_count=len(transcript.split()), duration=round(duration, 2))
    except Exception as e:  # noqa: BLE001
        logger.exception("Line regen failed for %s[%s]", reel_id, index)
        code, friendly = classify_error(e)
        await update_reel(reel_id, status="failed", stage_label="Re-render failed",
                          error=friendly, error_code=code)
        shutil.rmtree(workdir, ignore_errors=True)
        return
    finally:
        shutil.rmtree(workdir, ignore_errors=True)
    await recompose_reel(reel_id)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------
@api_router.get("/")
async def root():
    return {"message": "Faceless AI Reels API"}


@api_router.get("/config")
async def get_config():
    return {
        "voices": VOICES,
        "voice_speeds": VOICE_SPEEDS,
        "image_styles": IMAGE_STYLES,
        "caption_styles": CAPTION_STYLES,
        "caption_positions": CAPTION_POSITIONS,
        "caption_sizes": CAPTION_SIZES,
        "caption_fonts": CAPTION_FONTS,
        "caption_anims": CAPTION_ANIMS,
        "bg_themes": BG_THEMES,
        "bg_motions": BG_MOTIONS,
        "music_tracks": MUSIC_TRACKS,
    }


@api_router.post("/script")
async def make_script(req: ScriptRequest, user=Depends(current_user)):
    if not req.topic.strip():
        raise HTTPException(400, "Topic is required")
    moderate_text(req.topic)
    await enforce_quota(user)
    oa, gk = user_keys(user)
    pipeline.set_user_keys(oa, gk)
    try:
        script = await pipeline.generate_script(req.topic.strip(), req.seconds)
    except Exception as e:  # noqa: BLE001
        code, friendly = classify_error(e)
        raise HTTPException(402 if code in ("budget", "key") else 500, friendly)
    finally:
        pipeline.set_user_keys("", "")
    return {"script": script, "word_count": len(script.split())}


@api_router.get("/voices/{voice_id}/preview")
async def voice_preview(voice_id: str):
    if voice_id not in VOICE_MAP:
        raise HTTPException(404, "Unknown voice")
    local = MEDIA_DIR / f"voice_preview_{voice_id}.mp3"
    if not local.exists():
        await pipeline.synth_voice_sample(voice_id, str(local))
    return FileResponse(str(local), media_type="audio/mpeg",
                        headers={"Cache-Control": "public, max-age=86400"})


@api_router.post("/reels")
async def create_reel(req: CreateReelRequest, user=Depends(current_user)):
    validate_settings(req)
    await enforce_quota(user)
    script = (req.script or "").strip() or None
    topic = (req.topic or "").strip() or None
    if req.input_mode == "script" and not script:
        raise HTTPException(400, "Script is required")
    if req.input_mode == "topic" and not (topic or script):
        raise HTTPException(400, "Topic is required")
    moderate_text(topic, script, req.endcard_text, req.custom_c1, req.custom_c2, req.watermark)

    title = (req.title or "").strip() or ((script or topic or "Untitled")[:48].strip())
    doc = build_reel_doc(req, req.input_mode, topic, script, title, user_id=user["id"])
    await db.reels.insert_one(doc)
    await consume_quota(user)

    import asyncio
    asyncio.create_task(run_pipeline(doc["id"]))
    return public_reel(doc)


@api_router.post("/reels/batch")
async def create_reels_batch(req: BatchReelRequest, user=Depends(current_user)):
    validate_settings(req)
    oa, gk = user_keys(user)
    if not (oa or gk) and not user.get("is_subscribed") and not is_admin_user(user):
        raise HTTPException(402, "Batch generation needs your own OpenAI/Google key or a subscription.")
    topics = [t.strip() for t in (req.topics or []) if t.strip()]
    if not topics:
        raise HTTPException(400, "At least one topic is required")
    if len(topics) > 12:
        raise HTTPException(400, "Up to 12 topics per batch")
    moderate_text(*topics)

    # Determine scheduling.
    sched_iso = None
    now = datetime.now(timezone.utc)
    if req.scheduled_at:
        try:
            when = datetime.fromisoformat(req.scheduled_at.replace("Z", "+00:00"))
            if when.tzinfo is None:
                when = when.replace(tzinfo=timezone.utc)
            if when > now:
                sched_iso = when.isoformat()
        except Exception:
            sched_iso = None

    import asyncio
    created = []
    # Pair any reviewed scripts to their topic (1:1 by topic text).
    script_map = {}
    if req.scripts:
        for item in req.scripts:
            t = (item.get("topic") or "").strip()
            sc = (item.get("script") or "").strip()
            if t and sc:
                script_map[t] = sc
    if script_map:
        moderate_text(*script_map.values())
    for topic in topics:
        title = topic[:48].strip()
        script = script_map.get(topic)
        doc = build_reel_doc(req, "topic", topic, script, title, user_id=user["id"])
        if sched_iso:
            doc["status"] = "scheduled"
            doc["scheduled_at"] = sched_iso
            doc["stage_label"] = "Scheduled"
        await db.reels.insert_one(doc)
        if not sched_iso:
            asyncio.create_task(run_pipeline(doc["id"]))
        created.append(public_reel(doc))
    return {"created": created, "count": len(created), "scheduled": bool(sched_iso)}


class BatchScriptsRequest(BaseModel):
    topics: List[str] = []
    seconds: int = 30


@api_router.post("/reels/batch/scripts")
async def batch_scripts(req: BatchScriptsRequest, user=Depends(current_user)):
    """Generate a draft script per topic so the user can review/edit before building the batch."""
    oa, gk = user_keys(user)
    if not (oa or gk) and not user.get("is_subscribed") and not is_admin_user(user):
        raise HTTPException(402, "Batch generation needs your own OpenAI/Google key or a subscription.")
    topics = [t.strip() for t in (req.topics or []) if t.strip()]
    if not topics:
        raise HTTPException(400, "At least one topic is required")
    if len(topics) > 12:
        raise HTTPException(400, "Up to 12 topics per batch")
    moderate_text(*topics)
    pipeline.set_user_keys(oa, gk)
    try:
        import asyncio
        results = await asyncio.gather(
            *[pipeline.generate_script(t, req.seconds) for t in topics],
            return_exceptions=True,
        )
    finally:
        pipeline.set_user_keys("", "")
    scripts = []
    for t, r in zip(topics, results):
        if isinstance(r, Exception):
            code, friendly = classify_error(r)
            raise HTTPException(402 if code in ("budget", "key") else 500, friendly)
        scripts.append({"topic": t, "script": r, "word_count": len(r.split())})
    return {"scripts": scripts}



@api_router.post("/reels/{reel_id}/view")
async def add_view(reel_id: str):
    res = await db.reels.update_one({"id": reel_id}, {"$inc": {"views": 1}})
    if res.matched_count == 0:
        raise HTTPException(404, "Reel not found")
    doc = await db.reels.find_one({"id": reel_id})
    return {"views": doc.get("views", 0)}


@api_router.post("/reels/{reel_id}/download")
async def add_download(reel_id: str):
    res = await db.reels.update_one({"id": reel_id}, {"$inc": {"downloads": 1}})
    if res.matched_count == 0:
        raise HTTPException(404, "Reel not found")
    doc = await db.reels.find_one({"id": reel_id})
    return {"downloads": doc.get("downloads", 0)}


@api_router.get("/reels")
async def list_reels(user=Depends(current_user)):
    docs = await db.reels.find({"user_id": user["id"]}).sort("created_at", -1).to_list(200)
    return [public_reel(d) for d in docs]


@api_router.get("/reels/{reel_id}")
async def get_reel(reel_id: str, user=Depends(current_user)):
    doc = await owned_reel(reel_id, user)
    return public_reel(doc)


@api_router.delete("/reels/{reel_id}")
async def delete_reel(reel_id: str, user=Depends(current_user)):
    await owned_reel(reel_id, user)
    await db.reels.delete_one({"id": reel_id})
    for p in (MEDIA_DIR / f"{reel_id}.mp4", MEDIA_DIR / f"{reel_id}.jpg"):
        if p.exists():
            p.unlink(missing_ok=True)
    return {"ok": True}


async def _ensure_local(reel_id: str, ext: str, storage_field: str, content_type: str):
    local = MEDIA_DIR / f"{reel_id}.{ext}"
    if local.exists():
        return local
    doc = await db.reels.find_one({"id": reel_id})
    if not doc or not doc.get(storage_field):
        raise HTTPException(404, "File not found")
    content, _ = await run_in_threadpool(storage_client.get_object, doc[storage_field])
    local.write_bytes(content)
    return local


@api_router.get("/reels/{reel_id}/video")
async def get_video(reel_id: str):
    local = await _ensure_local(reel_id, "mp4", "video_path", "video/mp4")
    return FileResponse(str(local), media_type="video/mp4", filename=f"{reel_id}.mp4")


@api_router.get("/reels/{reel_id}/thumb")
async def get_thumb(reel_id: str):
    local = await _ensure_local(reel_id, "jpg", "thumb_path", "image/jpeg")
    return FileResponse(str(local), media_type="image/jpeg")


@api_router.post("/series")
async def create_series(req: SeriesCreate, user=Depends(current_user)):
    validate_settings(req)
    if not req.title.strip():
        raise HTTPException(400, "Series title is required")
    moderate_text(req.title, req.premise, req.tone,
                  *[c.name for c in req.characters], *[c.description for c in req.characters])
    settings = {k: getattr(req, k) for k in ReelSettings.model_fields}
    doc = {
        "id": str(uuid.uuid4()),
        "user_id": user["id"],
        "title": req.title.strip()[:80],
        "premise": (req.premise or "").strip()[:1200],
        "tone": (req.tone or "").strip()[:120],
        "characters": [c.model_dump() for c in req.characters][:8],
        "settings": settings,
        "episode_count": 0,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    await db.series.insert_one(doc)
    return public_series(doc)


@api_router.post("/series/suggest")
async def suggest_series_characters(req: SuggestRequest, user=Depends(current_user)):
    if not req.premise.strip():
        raise HTTPException(400, "Premise is required")
    moderate_text(req.premise, req.tone)
    oa, gk = user_keys(user)
    pipeline.set_user_keys(oa, gk)
    try:
        chars = await pipeline.suggest_characters(req.premise.strip(), req.tone.strip(), req.count)
    except Exception as e:  # noqa: BLE001
        code, friendly = classify_error(e)
        raise HTTPException(402 if code in ("budget", "key") else 500, friendly)
    finally:
        pipeline.set_user_keys("", "")
    return {"characters": chars}


@api_router.get("/series")
async def list_series(user=Depends(current_user)):
    docs = await db.series.find({"user_id": user["id"]}).sort("created_at", -1).to_list(100)
    return [public_series(d) for d in docs]


@api_router.get("/series/{series_id}")
async def get_series(series_id: str, user=Depends(current_user)):
    doc = await db.series.find_one({"id": series_id, "user_id": user["id"]})
    if not doc:
        raise HTTPException(404, "Series not found")
    reels = await db.reels.find({"series_id": series_id}).sort("episode_number", 1).to_list(200)
    return {"series": public_series(doc), "episodes": [public_reel(r) for r in reels]}


@api_router.delete("/series/{series_id}")
async def delete_series(series_id: str, user=Depends(current_user)):
    doc = await db.series.find_one({"id": series_id, "user_id": user["id"]})
    if not doc:
        raise HTTPException(404, "Series not found")
    await db.series.delete_one({"id": series_id})
    return {"ok": True}


@api_router.post("/series/{series_id}/episode/script")
async def series_episode_script(series_id: str, req: EpisodeRequest, user=Depends(current_user)):
    """Draft the next episode's script (with continuity) so the user can review/edit before building."""
    series = await db.series.find_one({"id": series_id, "user_id": user["id"]})
    if not series:
        raise HTTPException(404, "Series not found")
    moderate_text(req.topic)
    await enforce_quota(user)
    s = ReelSettings(**(series.get("settings") or {}))
    ep = int(series.get("episode_count", 0)) + 1
    topic = (req.topic or "").strip() or None
    prior = await db.reels.find({
        "series_id": series_id, "status": "ready",
        "episode_number": {"$lt": ep},
    }).sort("episode_number", 1).to_list(20)
    prior_scripts = [p.get("script") for p in prior if p.get("script")]
    oa, gk = user_keys(user)
    pipeline.set_user_keys(oa, gk)
    try:
        script = await pipeline.generate_series_script(series, prior_scripts, topic, s.seconds)
    except Exception as e:  # noqa: BLE001
        code, friendly = classify_error(e)
        raise HTTPException(402 if code in ("budget", "key") else 500, friendly)
    finally:
        pipeline.set_user_keys("", "")
    return {"script": script, "word_count": len(script.split()), "episode_number": ep}


@api_router.post("/series/{series_id}/episode")
async def create_series_episode(series_id: str, req: EpisodeRequest, user=Depends(current_user)):
    series = await db.series.find_one({"id": series_id, "user_id": user["id"]})
    if not series:
        raise HTTPException(404, "Series not found")
    moderate_text(req.topic, req.script)
    await enforce_quota(user)
    s = ReelSettings(**(series.get("settings") or {}))
    ep = int(series.get("episode_count", 0)) + 1
    topic = (req.topic or "").strip() or None
    script = (req.script or "").strip() or None
    title = f"{series['title']} — Ep {ep}"
    display_topic = topic or (series.get("premise") or series["title"])[:60]
    doc = build_reel_doc(s, "topic", display_topic, script, title,
                         series_id=series_id, episode_number=ep, user_id=user["id"])
    # keep the raw user topic (None -> AI continues the story on its own)
    doc["topic"] = topic
    await db.reels.insert_one(doc)
    await consume_quota(user)
    await db.series.update_one({"id": series_id},
                               {"$set": {"episode_count": ep, "updated_at": now_iso()}})

    import asyncio
    asyncio.create_task(run_pipeline(doc["id"]))
    return public_reel(doc)


@api_router.post("/outros")
async def upload_outro(file: UploadFile = File(...), name: str = Form(None)):
    data = await file.read()
    if not data:
        raise HTTPException(400, "Empty file")
    if len(data) > 40 * 1024 * 1024:
        raise HTTPException(413, "Outro clip must be under 40 MB")
    ct = (file.content_type or "").lower()
    if not (ct.startswith("video/") or (file.filename or "").lower().endswith((".mp4", ".mov", ".m4v"))):
        raise HTTPException(415, "Please upload a video clip (MP4/MOV)")

    outro_id = str(uuid.uuid4())
    storage_path = f"{storage_client.APP_NAME}/outros/{outro_id}.mp4"
    await run_in_threadpool(storage_client.put_object, storage_path, data, "video/mp4")
    doc = {
        "id": outro_id,
        "name": (name or file.filename or "Outro clip")[:60],
        "storage_path": storage_path,
        "size": len(data),
        "created_at": now_iso(),
    }
    await db.outros.insert_one(doc)
    return {k: doc[k] for k in ("id", "name", "size", "created_at")}


@api_router.get("/outros")
async def list_outros():
    docs = await db.outros.find().sort("created_at", -1).to_list(100)
    return [{k: d.get(k) for k in ("id", "name", "size", "created_at")} for d in docs]


@api_router.delete("/outros/{outro_id}")
async def delete_outro(outro_id: str):
    doc = await db.outros.find_one({"id": outro_id})
    if not doc:
        raise HTTPException(404, "Outro not found")
    await db.outros.delete_one({"id": outro_id})
    local = MEDIA_DIR / f"outro_{outro_id}.mp4"
    if local.exists():
        local.unlink(missing_ok=True)
    return {"ok": True}


@api_router.get("/outros/{outro_id}/video")
async def get_outro_video(outro_id: str):
    local = MEDIA_DIR / f"outro_{outro_id}.mp4"
    if not local.exists():
        doc = await db.outros.find_one({"id": outro_id})
        if not doc or not doc.get("storage_path"):
            raise HTTPException(404, "Outro not found")
        content, _ = await run_in_threadpool(storage_client.get_object, doc["storage_path"])
        local.write_bytes(content)
    return FileResponse(str(local), media_type="video/mp4")


@api_router.get("/reels/{reel_id}/scenes")
async def get_scenes(reel_id: str, user=Depends(current_user)):
    doc = await owned_reel(reel_id, user)
    scenes = doc.get("scenes") or []
    editable = bool(doc.get("visual_mode") == "ai" and doc.get("audio_path") and scenes)
    return {
        "editable": editable,
        "status": doc.get("status"),
        "scenes": [
            {"index": i, "prompt": s.get("prompt", ""),
             "image_url": f"/api/reels/{reel_id}/scene/{i}/image"}
            for i, s in enumerate(scenes)
        ],
    }


@api_router.get("/reels/{reel_id}/scene/{index}/image")
async def get_scene_image(reel_id: str, index: int):
    doc = await db.reels.find_one({"id": reel_id})
    scenes = (doc or {}).get("scenes") or []
    if not doc or index < 0 or index >= len(scenes):
        raise HTTPException(404, "Scene not found")
    local = MEDIA_DIR / f"scene_{reel_id}_{index}.png"
    if not local.exists():
        content, _ = await run_in_threadpool(storage_client.get_object, scenes[index]["image_path"])
        local.write_bytes(content)
    return FileResponse(str(local), media_type="image/png",
                        headers={"Cache-Control": "no-store"})


@api_router.post("/reels/{reel_id}/scene/{index}/regenerate")
async def regenerate_scene(reel_id: str, index: int, req: SceneRegenRequest, user=Depends(current_user)):
    doc = await owned_reel(reel_id, user)
    scenes = doc.get("scenes") or []
    if doc.get("visual_mode") != "ai" or not doc.get("audio_path") or not scenes:
        raise HTTPException(400, "This reel doesn't support scene editing")
    if index < 0 or index >= len(scenes):
        raise HTTPException(404, "Scene not found")
    moderate_text(req.prompt)
    if doc.get("status") not in ("ready", "failed"):
        raise HTTPException(409, "Reel is still processing")

    await update_reel(reel_id, status="rendering", progress=35, stage_label="Repainting scene",
                      error=None, error_code=None)
    import asyncio
    asyncio.create_task(regenerate_scene_task(reel_id, index, req.prompt))
    return public_reel(await db.reels.find_one({"id": reel_id}))


@api_router.get("/reels/{reel_id}/lines")
async def get_lines(reel_id: str, user=Depends(current_user)):
    doc = await owned_reel(reel_id, user)
    segments = doc.get("segments") or []
    editable = bool(doc.get("audio_path") and segments)
    return {
        "editable": editable,
        "status": doc.get("status"),
        "lines": [{"index": i, "text": s.get("text", "")} for i, s in enumerate(segments)],
    }


@api_router.post("/reels/{reel_id}/line/{index}/regenerate")
async def regenerate_line(reel_id: str, index: int, req: LineRegenRequest, user=Depends(current_user)):
    doc = await owned_reel(reel_id, user)
    segments = doc.get("segments") or []
    if not doc.get("audio_path") or not segments:
        raise HTTPException(400, "This reel doesn't support line editing")
    if index < 0 or index >= len(segments):
        raise HTTPException(404, "Line not found")
    if not (req.text or "").strip():
        raise HTTPException(400, "Line text is required")
    moderate_text(req.text)
    if doc.get("status") not in ("ready", "failed"):
        raise HTTPException(409, "Reel is still processing")

    await update_reel(reel_id, status="voicing", progress=20, stage_label="Re-recording line",
                      error=None, error_code=None)
    import asyncio
    asyncio.create_task(regenerate_line_task(reel_id, index, req.text))
    return public_reel(await db.reels.find_one({"id": reel_id}))


def _mask_key(k: str) -> str:
    if not k:
        return ""
    return (k[:3] + "••••" + k[-4:]) if len(k) > 10 else "••••"


@api_router.post("/auth/register")
async def register(body: AuthIn):
    email = body.email.strip().lower()
    if "@" not in email or "." not in email:
        raise HTTPException(400, "Enter a valid email")
    if len(body.password) < 8:
        raise HTTPException(400, "Password must be at least 8 characters")
    if await db.users.find_one({"email": email}):
        raise HTTPException(409, "An account with this email already exists")
    uid = str(uuid.uuid4())
    await db.users.insert_one({
        "id": uid, "email": email, "password_hash": hash_pw(body.password),
        "free_used": 0, "is_subscribed": False,
        "openai_key_enc": None, "google_key_enc": None, "brand_handle": "",
        "created_at": now_iso(),
    })
    user = await db.users.find_one({"id": uid})
    return {"access_token": make_token(uid), "user": public_user(user)}


@api_router.post("/auth/login")
async def login(body: AuthIn):
    email = body.email.strip().lower()
    user = await db.users.find_one({"email": email})
    stored = user["password_hash"] if user else DUMMY_HASH
    if not user or not verify_pw(body.password, stored):
        raise HTTPException(401, "Incorrect email or password")
    return {"access_token": make_token(user["id"]), "user": public_user(user)}


@api_router.get("/auth/me")
async def auth_me(user=Depends(current_user)):
    return public_user(user)


@api_router.post("/subscription/sync")
async def sync_subscription(body: SubscriptionSync, user=Depends(current_user)):
    """Sync the RevenueCat-verified `pro` entitlement (source of truth = the SDK on device)
    into the user record so the server-side free-reel quota unlocks for subscribers."""
    await db.users.update_one(
        {"id": user["id"]}, {"$set": {"is_subscribed": bool(body.is_subscribed)}}
    )
    logger.info("subscription/sync user=%s -> is_subscribed=%s", user["id"], bool(body.is_subscribed))
    fresh = await db.users.find_one({"id": user["id"]})
    return public_user(fresh)


@api_router.delete("/auth/me")
async def delete_account(user=Depends(current_user)):
    """Permanently delete the signed-in user and ALL of their data (Apple 5.1.1(v)).

    Removes reels (+ local media files), outros, series, and the user record —
    including the AES-encrypted BYOK keys stored on the user document."""
    uid = user["id"]
    # Reels + their locally-cached media files.
    reel_ids = [r["id"] async for r in db.reels.find({"user_id": uid}, {"id": 1})]
    for rid in reel_ids:
        for p in (MEDIA_DIR / f"{rid}.mp4", MEDIA_DIR / f"{rid}.jpg"):
            p.unlink(missing_ok=True)
    outro_ids = [o["id"] async for o in db.outros.find({"user_id": uid}, {"id": 1})]
    for oid in outro_ids:
        (MEDIA_DIR / f"{oid}.mp4").unlink(missing_ok=True)
    await db.reels.delete_many({"user_id": uid})
    await db.outros.delete_many({"user_id": uid})
    await db.series.delete_many({"user_id": uid})
    await db.users.delete_one({"id": uid})
    logger.info("account deleted user=%s reels=%d outros=%d", uid, len(reel_ids), len(outro_ids))
    return {"ok": True}


@api_router.get("/legal/privacy", response_class=HTMLResponse)
async def privacy_policy():
    """Public privacy policy page linked from the app (Apple 5.1.1 / Play User Data)."""
    return HTMLResponse(content=PRIVACY_POLICY_HTML)


@api_router.get("/legal/terms", response_class=HTMLResponse)
async def terms_of_service():
    """Public terms of service page linked from the app."""
    return HTMLResponse(content=TERMS_OF_SERVICE_HTML)


@api_router.get("/legal/delete-account", response_class=HTMLResponse)
async def delete_account_instructions():
    """Public account-deletion instructions page (Google Play Data safety requirement)."""
    return HTMLResponse(content=DELETE_ACCOUNT_HTML)


@api_router.get("/appstore-icon.png")
async def appstore_icon():
    """Direct download of the correct no-wordmark 1024x1024 app icon."""
    f = Path("/app/frontend/assets/images/icon.png")
    if not f.is_file():
        raise HTTPException(404, "not available")
    return FileResponse(str(f), media_type="image/png", filename="ghostreelsalpha-icon-1024.png")


@api_router.get("/android-icon-512.png")
async def android_icon_512():
    """Google Play app icon: 512x512 PNG (<1MB), no wordmark."""
    f = Path("/app/frontend/assets/images/android-icon-512.png")
    if not f.is_file():
        raise HTTPException(404, "not available")
    return FileResponse(str(f), media_type="image/png", filename="ghostreelsalpha-icon-512.png")


@api_router.get("/android-feature-graphic.png")
async def android_feature_graphic():
    """Google Play feature graphic: 1024x500 PNG."""
    f = Path("/app/frontend/appstore-screenshots/android/feature-graphic.png")
    if not f.is_file():
        raise HTTPException(404, "not available")
    return FileResponse(str(f), media_type="image/png", filename="ghostreelsalpha-feature-graphic.png")


@api_router.get("/appstore-screenshots.zip")
async def appstore_screenshots_zip():
    """One-off download of the generated App Store screenshot sets (6.7\" + 6.5\")."""
    f = Path("/app/frontend/appstore-screenshots.zip")
    if not f.is_file():
        raise HTTPException(404, "not available")
    return FileResponse(str(f), media_type="application/zip", filename="ghostreelsalpha-appstore-screenshots.zip")


@api_router.get("/settings")
async def get_settings(user=Depends(current_user)):
    return public_user(user)


@api_router.put("/settings")
async def update_settings(req: SettingsUpdate, user=Depends(current_user)):
    upd = {}
    if req.openai_key is not None:
        upd["openai_key_enc"] = enc_key(req.openai_key.strip(), user["id"], "openai") if req.openai_key.strip() else None
    if req.google_key is not None:
        upd["google_key_enc"] = enc_key(req.google_key.strip(), user["id"], "google") if req.google_key.strip() else None
    if req.brand_handle is not None:
        upd["brand_handle"] = req.brand_handle.strip()[:40]
    if upd:
        await db.users.update_one({"id": user["id"]}, {"$set": upd})
    fresh = await db.users.find_one({"id": user["id"]})
    return public_user(fresh)


@api_router.post("/settings/test")
async def test_keys(req: TestKeysRequest, user=Depends(current_user)):
    out = {}
    if req.openai_key and req.openai_key.strip():
        try:
            await pipeline.validate_openai_key(req.openai_key.strip())
            out["openai"] = {"ok": True, "message": "Valid — ready to save"}
        except Exception:  # noqa: BLE001
            out["openai"] = {"ok": False, "message": "OpenAI rejected this key"}
    if req.google_key and req.google_key.strip():
        try:
            await run_in_threadpool(pipeline.validate_google_key, req.google_key.strip())
            out["google"] = {"ok": True, "message": "Valid — ready to save"}
        except Exception:  # noqa: BLE001
            out["google"] = {"ok": False, "message": "Google rejected this key"}
    return out


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def scheduler_loop():
    import asyncio
    while True:
        try:
            now = datetime.now(timezone.utc).isoformat()
            due = await db.reels.find(
                {"status": "scheduled", "scheduled_at": {"$lte": now}}
            ).to_list(50)
            for d in due:
                await update_reel(d["id"], status="queued", stage_label="Queued", progress=0)
                asyncio.create_task(run_pipeline(d["id"]))
                logger.info("Scheduled reel %s promoted to queue", d["id"])
        except Exception as e:  # noqa: BLE001
            logger.warning("scheduler error: %s", e)
        await asyncio.sleep(30)


@app.on_event("startup")
async def startup():
    import asyncio
    try:
        await run_in_threadpool(storage_client.init_storage)
        logger.info("Object storage initialised")
    except Exception as e:  # noqa: BLE001
        logger.warning("Object storage init failed (will retry on demand): %s", e)
    try:
        await db.users.create_index("email", unique=True)
        await db.users.create_index("id", unique=True)
    except Exception as e:  # noqa: BLE001
        logger.warning("User index setup: %s", e)
    asyncio.create_task(scheduler_loop())


@app.on_event("shutdown")
async def shutdown():
    client.close()
