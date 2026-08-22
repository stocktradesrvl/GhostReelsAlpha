"""The Faceless AI Reels render pipeline: script -> voice -> captions -> render."""
import asyncio
import base64
import json
import os
import re
import shutil
import tempfile
from pathlib import Path

import emoji
import imageio_ffmpeg
import openai
from dotenv import load_dotenv
from emergentintegrations.llm.chat import LlmChat, UserMessage
from emergentintegrations.llm.openai import OpenAISpeechToText, OpenAITextToSpeech
from google import genai as google_genai
from google.genai import types as genai_types

from reels_config import (
    BG_MAP,
    BG_MOTION_MAP,
    CAPTION_ANIM_MAP,
    CAPTION_FONT_MAP,
    CAPTION_MAP,
    CAPTION_POSITION_MAP,
    CAPTION_SIZE_MAP,
    MUSIC_MAP,
    MUSIC_VOLUME,
    VOICE_MAP,
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

EMERGENT_LLM_KEY = os.environ["EMERGENT_LLM_KEY"]

# Bring-Your-Own-Key: when the app owner saves their own provider keys in Settings,
# generation uses THOSE keys (real OpenAI / Google) instead of the shared Emergent key,
# lifting the shared budget cap. Updated by the backend from the app_settings doc.
USER_KEYS = {"openai": "", "google": ""}


def set_user_keys(openai_key: str = "", google_key: str = "") -> None:
    USER_KEYS["openai"] = (openai_key or "").strip()
    USER_KEYS["google"] = (google_key or "").strip()


async def validate_openai_key(key: str) -> bool:
    """Lightweight validation — lists models (no token cost). Raises on invalid key."""
    client = openai.AsyncOpenAI(api_key=key)
    await client.models.list()
    return True


def validate_google_key(key: str) -> bool:
    """Lightweight validation for a Google/Gemini key. Raises on invalid key."""
    client = google_genai.Client(api_key=key)
    next(iter(client.models.list()))
    return True


async def _chat_text(session_id: str, system: str, prompt: str) -> str:
    """Text generation via the user's own OpenAI key when set, else the Emergent key."""
    if USER_KEYS["openai"]:
        client = openai.AsyncOpenAI(api_key=USER_KEYS["openai"])
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "system", "content": system},
                      {"role": "user", "content": prompt}],
        )
        return resp.choices[0].message.content or ""
    chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=session_id,
                   system_message=system).with_model("openai", "gpt-5.4")
    return await chat.send_message(UserMessage(text=prompt))


async def _tts_bytes(text: str, voice_openai: str, speed: float) -> bytes:
    """TTS via the user's OpenAI key when set, else the Emergent key."""
    text = re.sub(r"\s+", " ", text).strip()[:4000]
    spd = max(0.5, min(1.5, float(speed)))
    if USER_KEYS["openai"]:
        client = openai.AsyncOpenAI(api_key=USER_KEYS["openai"])
        resp = await client.audio.speech.create(
            model="tts-1", voice=voice_openai, input=text, response_format="mp3", speed=spd)
        return resp.content
    tts = OpenAITextToSpeech(api_key=EMERGENT_LLM_KEY)
    return await tts.generate_speech(text=text, model="tts-1-hd", voice=voice_openai,
                                     speed=spd, response_format="mp3")
FONTS_DIR = str(ROOT_DIR / "assets" / "fonts")
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

MUSIC_DIR = str(ROOT_DIR / "assets" / "music")
WORDS_PER_SEC = 2.5

# Dev-only: when REELS_MOCK=1, skip all paid LLM/TTS/Whisper/image calls and
# synthesise placeholder script/audio/captions/images so the full render pipeline
# can be exercised end-to-end without spending Universal Key credits.
MOCK = os.environ.get("REELS_MOCK", "0") == "1"

_MOCK_SCRIPT = (
    "Deep beneath the waves lies a world we barely understand. "
    "Creatures glow in the crushing dark where sunlight never reaches. "
    "Some have survived unchanged for millions of years. "
    "The ocean still hides its greatest secrets from us. "
    "What else is down there, waiting to be found."
)


def _ffmpeg_exe() -> str:
    return FFMPEG if os.path.exists(FFMPEG) else (shutil.which("ffmpeg") or "ffmpeg")


async def _run_ffmpeg(cmd: list, cwd: str | None = None) -> None:
    proc = await asyncio.create_subprocess_exec(
        *cmd, cwd=cwd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed: {stderr.decode()[-800:]}")


# ---------------------------------------------------------------------------
# 1. Script generation
# ---------------------------------------------------------------------------
async def generate_script(topic: str, seconds: int = 30) -> str:
    target_words = int(seconds * WORDS_PER_SEC)
    if MOCK:
        return _clean_script(f"{topic}. {_MOCK_SCRIPT}")
    chat_system = (
        "You are an elite short-form video scriptwriter for TikTok, Reels and Shorts. "
        "You write punchy, spoken-word narration that hooks in the first 3 seconds."
    )

    prompt = (
        f"Write a faceless video narration script about: \"{topic}\".\n\n"
        f"Rules:\n"
        f"- About {target_words} words (~{seconds} seconds when spoken).\n"
        f"- Start with a scroll-stopping hook in the first sentence.\n"
        f"- Short, punchy, conversational spoken sentences.\n"
        f"- Plain narration ONLY. No headings, no scene directions, no speaker labels.\n"
        f"- No emojis, no hashtags, no markdown, no quotation marks.\n"
        f"- End with a memorable closing line.\n\n"
        f"Return only the narration text."
    )
    text = await _chat_text(f"script-{abs(hash(topic)) % 100000}", chat_system, prompt)
    return _clean_script(text)


def _clean_script(text: str) -> str:
    text = emoji.replace_emoji(text or "", replace="")
    text = re.sub(r"[*_#>~|`]", "", text)
    text = re.sub(r"^\s*[-•]\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"[\"“”]", "", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def hook_line(script: str) -> str:
    """First sentence of the script, trimmed to a punchy title-card length."""
    flat = re.sub(r"\s+", " ", script or "").strip()
    if not flat:
        return ""
    m = re.split(r"(?<=[.!?])\s", flat, maxsplit=1)
    first = m[0].strip().rstrip(".!?").strip()
    words = first.split()
    if len(words) > 7:
        first = " ".join(words[:7])
    return first[:48].strip()


# ---------------------------------------------------------------------------
# 1b. Series continuity — consistent characters + storyline across episodes
# ---------------------------------------------------------------------------
def character_bible_text(series: dict) -> str:
    """Flatten a series' character list into a compact, prompt-ready block."""
    chars = (series or {}).get("characters") or []
    lines = []
    for c in chars:
        name = (c.get("name") or "").strip()
        desc = (c.get("description") or "").strip()
        if name or desc:
            lines.append(f"- {name}: {desc}".strip(" -:") if not name else f"- {name}: {desc}")
    return "\n".join(lines)


async def suggest_characters(premise: str, tone: str = "", count: int = 3) -> list:
    """Propose a small character bible for a new series from its premise."""
    n = max(1, min(6, int(count or 3)))
    if MOCK:
        return [
            {"name": f"Character {i + 1}", "description": "A vivid recurring figure central to the story."}
            for i in range(n)
        ]
    ask = (
        f"For a short-form video SERIES with this premise: \"{premise}\"\n"
        f"Tone: {tone or 'engaging'}.\n\n"
        f"Invent exactly {n} recurring characters. For each give a short name and a vivid, "
        f"visually specific description (appearance, clothing, defining features) so an image "
        f"generator can draw them identically every episode.\n\n"
        f"Return ONLY a JSON array of objects with keys \"name\" and \"description\"."
    )
    raw = await _chat_text(
        f"chars-{abs(hash(premise)) % 100000}",
        "You design memorable, visually distinct recurring characters for a video series.",
        ask,
    )
    out = []
    try:
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        data = json.loads(m.group(0)) if m else []
        for d in data:
            name = str(d.get("name", "")).strip()[:48]
            desc = str(d.get("description", "")).strip()[:240]
            if name or desc:
                out.append({"name": name, "description": desc})
    except Exception:
        out = []
    return out[:n]


async def generate_series_script(series: dict, prior_scripts: list, topic, seconds: int = 30) -> str:
    """Write the next episode, keeping characters, tone and plot consistent."""
    target_words = int(seconds * WORDS_PER_SEC)
    episode_no = len(prior_scripts) + 1
    if MOCK:
        lead = (topic or "The story continues").strip()
        return _clean_script(f"Episode {episode_no}. {lead}. {_MOCK_SCRIPT}")

    bible = character_bible_text(series)
    prior = "\n\n".join(
        f"Episode {i + 1}: {s}" for i, s in enumerate(prior_scripts[-4:])
    ) or "(This is the first episode — establish the world and characters.)"
    if topic:
        direction = f"The beat/topic for this episode: \"{topic}\". Weave it into the ongoing storyline."
    else:
        direction = "Continue the storyline naturally from where the previous episode ended, advancing the plot."

    chat_system = (
        "You are an elite serialized short-form video scriptwriter. You keep characters, "
        "tone and story continuity perfectly consistent across episodes."
    )
    prompt = (
        f"Write episode {episode_no} of a faceless narrated video series.\n\n"
        f"SERIES PREMISE: {series.get('premise','')}\n"
        f"TONE: {series.get('tone','')}\n"
        f"RECURRING CHARACTERS:\n{bible or '(none defined)'}\n\n"
        f"PREVIOUS EPISODES:\n{prior}\n\n"
        f"{direction}\n\n"
        f"Rules:\n"
        f"- About {target_words} words (~{seconds} seconds when spoken).\n"
        f"- Open with a scroll-stopping hook that nods to the continuing story.\n"
        f"- Keep character names and traits perfectly consistent with above.\n"
        f"- Short, punchy, conversational spoken sentences.\n"
        f"- Plain narration ONLY. No headings, scene directions, speaker labels.\n"
        f"- No emojis, hashtags, markdown, or quotation marks.\n"
        f"- End on a cliffhanger or hook that sets up the next episode.\n\n"
        f"Return only the narration text."
    )
    text = await _chat_text(f"series-{series.get('id','x')}-{episode_no}", chat_system, prompt)
    return _clean_script(text)


# ---------------------------------------------------------------------------
# 2. Voiceover (TTS)
# ---------------------------------------------------------------------------
async def synth_voice(script: str, voice_id: str, out_path: str, speed: float = 1.0) -> None:
    if MOCK:
        words = [w for w in re.sub(r"\s+", " ", script).strip().split(" ") if w]
        dur = max(3.0, len(words) / WORDS_PER_SEC)
        await _run_ffmpeg([
            _ffmpeg_exe(), "-y", "-f", "lavfi", "-i", "anullsrc=r=24000:cl=mono",
            "-t", f"{dur:.2f}", "-q:a", "9", out_path,
        ])
        Path(out_path + ".txt").write_text(script, encoding="utf-8")
        return
    voice = VOICE_MAP.get(voice_id, VOICE_MAP["onyx"])["openai"]
    audio = await _tts_bytes(script, voice, speed)
    with open(out_path, "wb") as f:
        f.write(audio)


def split_sentences(script: str) -> list:
    """Split a narration script into spoken sentences for per-line editing."""
    flat = re.sub(r"\s+", " ", script or "").strip()
    if not flat:
        return []
    parts = re.split(r"(?<=[.!?])\s+", flat)
    out = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        # Merge tiny fragments into the previous sentence to avoid choppy clips.
        if out and len(p.split()) <= 2:
            out[-1] = (out[-1] + " " + p).strip()
        else:
            out.append(p)
    return out or [flat]


async def synth_voice_segments(sentences: list, voice_id: str, workdir: str,
                               speed: float = 1.0) -> list:
    """TTS each sentence into its own mp3 clip; returns clip paths in order."""
    paths = []
    for i, sentence in enumerate(sentences):
        out = os.path.join(workdir, f"seg_{i}.mp3")
        await synth_voice(sentence, voice_id, out, speed=speed)
        paths.append(out)
    return paths


async def concat_audio(paths: list, out_path: str, transcript: str = None) -> None:
    """Concatenate sentence mp3 clips into one voice track (re-encoded)."""
    if len(paths) == 1:
        shutil.copyfile(paths[0], out_path)
    else:
        inputs = []
        for p in paths:
            inputs += ["-i", p]
        streams = "".join(f"[{i}:a]" for i in range(len(paths)))
        fc = f"{streams}concat=n={len(paths)}:v=0:a=1[a]"
        await _run_ffmpeg([
            _ffmpeg_exe(), "-y", *inputs, "-filter_complex", fc,
            "-map", "[a]", "-c:a", "libmp3lame", "-q:a", "4", out_path,
        ])
    if MOCK and transcript is not None:
        Path(out_path + ".txt").write_text(transcript, encoding="utf-8")



async def synth_voice_sample(voice_id: str, out_path: str) -> None:
    v = VOICE_MAP.get(voice_id, VOICE_MAP["onyx"])
    phrase = f"Hi, I'm {v['name']}. Here's how I'll sound narrating your reels."
    audio = await _tts_bytes(phrase, v["openai"], 1.0)
    with open(out_path, "wb") as f:
        f.write(audio)


# ---------------------------------------------------------------------------
# 3. Caption alignment (Whisper word timestamps)
# ---------------------------------------------------------------------------
async def transcribe_words(audio_path: str):
    if MOCK:
        sidecar = audio_path + ".txt"
        script = Path(sidecar).read_text(encoding="utf-8") if os.path.exists(sidecar) else _MOCK_SCRIPT
        tokens = [w for w in re.sub(r"\s+", " ", script).strip().split(" ") if w]
        duration = max(3.0, len(tokens) / WORDS_PER_SEC)
        step = duration / max(1, len(tokens))
        words = []
        for i, tok in enumerate(tokens):
            start = round(i * step, 2)
            end = round((i + 1) * step - 0.02, 2)
            words.append({"word": tok, "start": start, "end": max(start + 0.05, end)})
        return words, duration
    if USER_KEYS["openai"]:
        client = openai.AsyncOpenAI(api_key=USER_KEYS["openai"])
        with open(audio_path, "rb") as fh:
            result = await client.audio.transcriptions.create(
                model="whisper-1", file=fh,
                response_format="verbose_json", timestamp_granularities=["word"],
            )
        return _parse_words(result)
    stt = OpenAISpeechToText(api_key=EMERGENT_LLM_KEY)
    with open(audio_path, "rb") as fh:
        result = await stt.transcribe(
            file=("voice.mp3", fh.read(), "audio/mpeg"),
            model="whisper-1",
            response_format="verbose_json",
            timestamp_granularities=["word"],
        )
    words, duration = _parse_words(result)
    return words, duration


def _parse_words(result):
    def get(obj, key, default=None):
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    raw_words = get(result, "words") or []
    duration = get(result, "duration")
    words = []
    for w in raw_words:
        token = (get(w, "word") or "").strip()
        start = get(w, "start")
        end = get(w, "end")
        if token and start is not None and end is not None:
            words.append({"word": token, "start": float(start), "end": float(end)})
    if duration is not None:
        duration = float(duration)
    elif words:
        duration = words[-1]["end"]
    return words, duration


# ---------------------------------------------------------------------------
# 4. Build ASS karaoke subtitles
# ---------------------------------------------------------------------------
def _ass_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")")


def _ass_header(fontsize: int, alignment: int, marginv: int, fontname: str = "Barlow Condensed") -> str:
    # White base fill, thick black outline for readability on any gradient.
    # WM = watermark, Hook = opening title flash, End = closing CTA card.
    return (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        "PlayResX: 1080\n"
        "PlayResY: 1920\n"
        "WrapStyle: 2\n"
        "ScaledBorderAndShadow: yes\n\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Cap,{fontname},{fontsize},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,"
        f"-1,0,0,0,100,100,1,0,1,7,3,{alignment},120,120,{marginv},1\n"
        "Style: WM,Barlow Condensed,46,&H2EFFFFFF,&H2EFFFFFF,&H80000000,&H00000000,"
        "0,0,0,0,100,100,2,0,1,2,0,8,60,60,60,1\n"
        "Style: Hook,Barlow Condensed,96,&H0000E5FF,&H0000E5FF,&H00000000,&H64000000,"
        "-1,0,0,0,100,100,1,0,1,8,2,8,80,80,560,1\n"
        "Style: End,Barlow Condensed,104,&H00FFFFFF,&H00FFFFFF,&H00000000,&H96000000,"
        "-1,0,0,0,100,100,1,0,1,7,3,5,120,120,0,1\n\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )


def _fmt_time(t: float) -> str:
    if t < 0:
        t = 0
    h = int(t // 3600)
    m = int((t % 3600) // 60)
    s = int(t % 60)
    cs = int(round((t - int(t)) * 100))
    if cs == 100:
        cs = 99
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def build_ass(words, duration, caption_style: str, out_path: str,
              position: str = "center", size: str = "m", watermark: str = "",
              hook_text: str = "", caption_font: str = "barlow", endcard_text: str = "",
              caption_anim: str = "pop") -> None:
    color = CAPTION_MAP.get(caption_style, CAPTION_MAP["signal"])["ass_color"]
    pos = CAPTION_POSITION_MAP.get(position, CAPTION_POSITION_MAP["center"])
    sz = CAPTION_SIZE_MAP.get(size, CAPTION_SIZE_MAP["m"])
    fam = CAPTION_FONT_MAP.get(caption_font, CAPTION_FONT_MAP["barlow"])["family"]
    anim = caption_anim if caption_anim in CAPTION_ANIM_MAP else "pop"
    header = _ass_header(sz["fontsize"], pos["an"], pos["marginv"], fontname=fam)
    lines = [header]

    # Anchor Y for slide animation, derived from alignment + vertical margin.
    an, mv = pos["an"], pos["marginv"]
    cap_y = (1920 - mv) if an == 2 else (mv if an == 8 else 960)
    if anim == "none":
        intro = "{\\fad(50,40)}"
    elif anim == "slide":
        intro = f"{{\\fad(40,30)\\move(540,{cap_y + 70},540,{cap_y},0,160)}}"
    elif anim == "bounce":
        intro = "{\\fad(40,20)\\fscx55\\fscy55\\t(0,130,\\fscx113\\fscy113)\\t(130,240,\\fscx100\\fscy100)}"
    else:  # pop
        intro = "{\\fad(50,30)\\fscx86\\fscy86\\t(0,110,\\fscx100\\fscy100)}"

    wm = _sanitize_watermark(watermark)
    total = max(1.0, float(duration or 1.0))
    cap_limit = total  # captions must clear before the end card (if any)
    if wm:
        lines.append(
            f"Dialogue: 1,{_fmt_time(0)},{_fmt_time(total)},WM,,0,0,0,,{_ass_escape(wm)}\n"
        )

    hk = _ass_escape((hook_text or "").strip().upper())
    if hk:
        hook_end = min(total, 1.9)
        pop = "{\\fad(120,300)\\fscx55\\fscy55\\t(0,220,\\fscx104\\fscy104)\\t(220,360,\\fscx100\\fscy100)}"
        lines.append(
            f"Dialogue: 2,{_fmt_time(0.12)},{_fmt_time(hook_end)},Hook,,0,0,0,,{pop}{hk}\n"
        )

    ec = _ass_escape((endcard_text or "").strip().upper())
    if ec:
        ec_start = max(0.0, total - 1.6)
        cap_limit = ec_start
        ecpop = "{\\fad(180,120)\\fscx70\\fscy70\\t(0,260,\\fscx103\\fscy103)\\t(260,420,\\fscx100\\fscy100)}"
        lines.append(
            f"Dialogue: 3,{_fmt_time(ec_start)},{_fmt_time(total)},End,,0,0,0,,{ecpop}{ec}\n"
        )

    if not words:
        # Fallback: no timestamps -> keep watermark/hook/endcard only (video still renders).
        Path(out_path).write_text("".join(lines), encoding="utf-8")
        return

    # Group words into on-screen phrases of up to 3 words.
    groups = [words[i:i + 3] for i in range(0, len(words), 3)]
    for gi, group in enumerate(groups):
        next_group_start = (
            groups[gi + 1][0]["start"] if gi + 1 < len(groups) else group[-1]["end"] + 0.4
        )
        for wi, w in enumerate(group):
            seg_start = w["start"]
            if seg_start >= cap_limit:
                continue
            if wi + 1 < len(group):
                seg_end = group[wi + 1]["start"]
            else:
                seg_end = next_group_start
            if seg_end <= seg_start:
                seg_end = seg_start + 0.15
            seg_end = min(seg_end, cap_limit)

            parts = []
            for k, gw in enumerate(group):
                tok = _ass_escape(gw["word"].upper())
                if k == wi:
                    parts.append(f"{{\\c{color}\\fscx112\\fscy112}}{tok}{{\\r}}")
                else:
                    parts.append(tok)
            text = " ".join(parts)
            lines.append(
                f"Dialogue: 0,{_fmt_time(seg_start)},{_fmt_time(seg_end)},Cap,,0,0,0,,{intro}{text}\n"
            )

    Path(out_path).write_text("".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# 5. Render with ffmpeg (animated gradient bg + burned captions + voice)
# ---------------------------------------------------------------------------
def _sanitize_watermark(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r"[^A-Za-z0-9 @._\-]", "", text).strip()
    return text[:32]


def _hex_to_ff(h: str):
    h = (h or "").strip().lstrip("#")
    if len(h) == 6 and all(ch in "0123456789abcdefABCDEF" for ch in h):
        return "0x" + h.upper()
    return None


async def render_video(audio_path: str, ass_name: str, bg_theme: str, duration: float,
                       workdir: str, out_path: str, music_id: str = "none",
                       music_volume: float = MUSIC_VOLUME, bg_motion: str = "subtle",
                       custom_colors=None) -> None:
    if bg_theme == "custom" and custom_colors and len(custom_colors) == 2:
        c1, c2 = _hex_to_ff(custom_colors[0]), _hex_to_ff(custom_colors[1])
        c = ["0x09090B", c2, c1, "0x18181B"] if (c1 and c2) else BG_MAP["ember"]["colors"]
    else:
        c = BG_MAP.get(bg_theme, BG_MAP["ember"])["colors"]
    dur = max(1.0, float(duration))
    speed = BG_MOTION_MAP.get(bg_motion, BG_MOTION_MAP["subtle"])["speed"]

    grad = (
        f"gradients=s=1080x1920:c0={c[0]}:c1={c[1]}:c2={c[2]}:c3={c[3]}"
        f":x0=120:y0=120:x1=960:y1=1800:nb_colors=4:seed=7:duration={dur:.2f}:speed={speed}:rate=30"
    )

    # Video chain: gradient -> captions + optional watermark (both baked into the ASS).
    vchain = f"[0:v]format=yuv420p,ass={ass_name}:fontsdir={FONTS_DIR}[v]"

    # Optional background music bed.
    track = MUSIC_MAP.get(music_id or "none", MUSIC_MAP["none"])
    music_path = None
    if track["file"]:
        candidate = os.path.join(MUSIC_DIR, track["file"])
        if os.path.exists(candidate):
            music_path = candidate

    inputs = ["-f", "lavfi", "-i", grad, "-i", audio_path]
    if music_path:
        vol = max(0.0, min(1.0, float(music_volume)))
        fout = max(0.1, dur - 1.0)
        inputs += ["-stream_loop", "-1", "-i", music_path]
        achain = (
            f"[1:a]volume=1.0[va];"
            f"[2:a]volume={vol:.3f},afade=t=in:st=0:d=0.8,afade=t=out:st={fout:.2f}:d=1.0[ma];"
            f"[va][ma]amix=inputs=2:duration=first:dropout_transition=2:normalize=0[aout]"
        )
        filter_complex = f"{vchain};{achain}"
        amap = ["-map", "[v]", "-map", "[aout]"]
    else:
        filter_complex = vchain
        amap = ["-map", "[v]", "-map", "1:a"]

    cmd = [
        _ffmpeg_exe(), "-y",
        *inputs,
        "-filter_complex", filter_complex,
        *amap,
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k",
        "-t", f"{dur:.2f}", "-shortest",
        "-movflags", "+faststart",
        out_path,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, cwd=workdir,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg render failed: {stderr.decode()[-1500:]}")


async def extract_thumbnail(video_path: str, out_path: str) -> None:
    cmd = [
        _ffmpeg_exe(), "-y", "-ss", "1.2", "-i", video_path,
        "-frames:v", "1", "-q:v", "3", out_path,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    await proc.communicate()


def new_workdir() -> str:
    return tempfile.mkdtemp(prefix="reel_")


# ---------------------------------------------------------------------------
# Custom outro — append a user-supplied clip (e.g. "stay tuned for more")
# ---------------------------------------------------------------------------
async def _probe_clip(path: str):
    """Return (duration_seconds, has_audio) for a media file via ffmpeg -i."""
    proc = await asyncio.create_subprocess_exec(
        _ffmpeg_exe(), "-i", path,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    _, err = await proc.communicate()
    s = err.decode(errors="ignore")
    has_audio = " Audio:" in s
    dur = 3.0
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", s)
    if m:
        h, mn, sec = m.groups()
        dur = int(h) * 3600 + int(mn) * 60 + float(sec)
    return max(0.3, dur), has_audio


async def append_outro(main_path: str, outro_path: str, out_path: str) -> None:
    """Concatenate `outro_path` after `main_path`, normalising the outro to 1080x1920."""
    outro_dur, has_audio = await _probe_clip(outro_path)
    vnorm = (
        "scale=1080:1920:force_original_aspect_ratio=decrease,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps=30,format=yuv420p"
    )
    if has_audio:
        inputs = ["-i", main_path, "-i", outro_path]
        outro_audio = "[1:a]"
    else:
        inputs = ["-i", main_path, "-i", outro_path,
                  "-f", "lavfi", "-t", f"{outro_dur:.2f}", "-i", "anullsrc=r=44100:cl=stereo"]
        outro_audio = "[2:a]"
    filter_complex = (
        f"[0:v]{vnorm}[v0];"
        f"[1:v]{vnorm}[v1];"
        f"[0:a]aformat=sample_rates=44100:channel_layouts=stereo[a0];"
        f"{outro_audio}aformat=sample_rates=44100:channel_layouts=stereo[a1];"
        f"[v0][a0][v1][a1]concat=n=2:v=1:a=1[v][a]"
    )
    cmd = [
        _ffmpeg_exe(), "-y", *inputs,
        "-filter_complex", filter_complex, "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", out_path,
    ]
    await _run_ffmpeg(cmd)


# ---------------------------------------------------------------------------
# AI Visuals: scene image prompts -> Gemini images -> Ken Burns background
# ---------------------------------------------------------------------------
def scene_count(seconds: int) -> int:
    return max(2, min(4, round((seconds or 30) / 10)))


async def generate_scene_prompts(script: str, n: int, character_bible: str = "") -> list:
    if MOCK:
        return [f"Mock cinematic vertical scene {i + 1} for the story" for i in range(n)]
    char_note = (
        f"\n\nRecurring characters that MUST appear consistently (same face, hair, clothing "
        f"and style) whenever they are relevant to a beat:\n{character_bible}\n"
        f"When a character appears, describe them using these exact details so they look "
        f"identical across every scene."
        if character_bible else ""
    )
    ask = (
        f"For this short video narration, write exactly {n} vivid image-generation prompts, "
        f"one per key beat, that visually support the story. Cinematic, photographic, dramatic "
        f"lighting, vertical 9:16 composition. Do NOT include any text/words/letters in the image. "
        f"Keep a consistent visual style across all prompts.{char_note}\n\n"
        f"Narration:\n{script}\n\n"
        f"Return ONLY a JSON array of {n} strings."
    )
    raw = await _chat_text(
        f"prompts-{abs(hash(script)) % 100000}",
        "You turn video scripts into vivid cinematic image prompts.",
        ask,
    )
    prompts = []
    try:
        m = re.search(r"\[.*\]", raw, re.DOTALL)
        prompts = json.loads(m.group(0)) if m else []
    except Exception:
        prompts = []
    prompts = [str(p).strip() for p in prompts if str(p).strip()][:n]
    while len(prompts) < n:
        prompts.append(f"Cinematic dramatic vertical scene illustrating: {script[:120]}")
    return prompts


async def generate_images(prompts: list, workdir: str, style_suffix: str = "",
                          character_bible: str = "") -> list:
    paths = []
    if MOCK:
        _colors = ["0x1E3A8A", "0x7C2D12", "0x065F46", "0x4C1D95", "0x9A3412", "0x155E75"]
        for i, _ in enumerate(prompts):
            out = os.path.join(workdir, f"scene_{i}.png")
            await _run_ffmpeg([
                _ffmpeg_exe(), "-y", "-f", "lavfi",
                "-i", f"color=c={_colors[i % len(_colors)]}:s=1080x1920:d=1",
                "-frames:v", "1", out,
            ])
            paths.append(out)
        return paths
    for i, prompt in enumerate(prompts):
        style = f" {style_suffix}." if style_suffix else ""
        style += " Vertical 9:16 aspect ratio, ultra-detailed, no text."
        if character_bible:
            style += (f" Keep recurring characters visually identical across images "
                      f"(same face, hair, outfit): {character_bible}.")
        out = os.path.join(workdir, f"scene_{i}.png")
        if USER_KEYS["google"]:
            client = google_genai.Client(api_key=USER_KEYS["google"])
            resp = await client.aio.models.generate_content(
                model="gemini-2.5-flash-image",
                contents=prompt + style,
                config=genai_types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                    image_config={"aspect_ratio": "9:16"},
                ),
            )
            img_bytes = None
            for part in resp.candidates[0].content.parts:
                if getattr(part, "inline_data", None) and part.inline_data.data:
                    img_bytes = part.inline_data.data
                    break
            if not img_bytes:
                raise RuntimeError("Image generation returned no image")
            with open(out, "wb") as f:
                f.write(img_bytes)
        else:
            chat = LlmChat(
                api_key=EMERGENT_LLM_KEY,
                session_id=f"img-{i}-{abs(hash(prompt)) % 100000}",
                system_message="You are an image generation assistant.",
            ).with_model("gemini", "gemini-3.1-flash-image-preview").with_params(modalities=["image", "text"])
            _text, images = await chat.send_message_multimodal_response(UserMessage(text=prompt + style))
            if not images:
                raise RuntimeError("Image generation returned no image")
            with open(out, "wb") as f:
                f.write(base64.b64decode(images[0]["data"]))
        paths.append(out)
    return paths


async def render_video_images(audio_path: str, ass_name: str, image_paths: list, duration: float,
                              workdir: str, out_path: str, music_id: str = "none",
                              music_volume: float = MUSIC_VOLUME) -> None:
    dur = max(1.0, float(duration))
    n = max(1, len(image_paths))
    fps = 30
    seg_sec = dur / n

    inputs = []
    vlabels = ""
    for img in image_paths:
        inputs += ["-loop", "1", "-t", f"{seg_sec:.3f}", "-i", img]
    for i in range(n):
        # Ken Burns: cover-crop, fix fps so the clip is finite, slow continuous zoom.
        vlabels += (
            f"[{i}:v]scale=1620:2880:force_original_aspect_ratio=increase,crop=1620:2880,"
            f"fps={fps},zoompan=z='min(1.0+0.0012*on,1.18)':d=1:x='iw/2-(iw/zoom/2)':"
            f"y='ih/2-(ih/zoom/2)':s=1080x1920,setsar=1[v{i}];"
        )
    concat_in = "".join(f"[v{i}]" for i in range(n))
    vchain = f"{vlabels}{concat_in}concat=n={n}:v=1:a=0[vc];[vc]ass={ass_name}:fontsdir={FONTS_DIR}[v]"

    audio_idx = n
    inputs += ["-i", audio_path]
    track = MUSIC_MAP.get(music_id or "none", MUSIC_MAP["none"])
    music_path = os.path.join(MUSIC_DIR, track["file"]) if track["file"] else None
    if music_path and os.path.exists(music_path):
        vol = max(0.0, min(1.0, float(music_volume)))
        fout = max(0.1, dur - 1.0)
        inputs += ["-stream_loop", "-1", "-i", music_path]
        achain = (
            f"[{audio_idx}:a]volume=1.0[va];"
            f"[{audio_idx + 1}:a]volume={vol:.3f},afade=t=in:st=0:d=0.8,afade=t=out:st={fout:.2f}:d=1.0[ma];"
            f"[va][ma]amix=inputs=2:duration=first:dropout_transition=2:normalize=0[aout]"
        )
        filter_complex = f"{vchain};{achain}"
        amap = ["-map", "[v]", "-map", "[aout]"]
    else:
        filter_complex = vchain
        amap = ["-map", "[v]", "-map", f"{audio_idx}:a"]

    cmd = [
        _ffmpeg_exe(), "-y", *inputs,
        "-filter_complex", filter_complex, *amap,
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-t", f"{dur:.2f}", "-shortest", "-movflags", "+faststart",
        out_path,
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, cwd=workdir, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg image render failed: {stderr.decode()[-1500:]}")
