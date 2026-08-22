"""The Faceless AI Reels render pipeline: script -> voice -> captions -> render."""
import asyncio
import os
import re
import shutil
import tempfile
from pathlib import Path

import emoji
import imageio_ffmpeg
from dotenv import load_dotenv
from emergentintegrations.llm.chat import LlmChat, UserMessage
from emergentintegrations.llm.openai import OpenAISpeechToText, OpenAITextToSpeech

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
FONTS_DIR = str(ROOT_DIR / "assets" / "fonts")
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

MUSIC_DIR = str(ROOT_DIR / "assets" / "music")
WORDS_PER_SEC = 2.5


def _ffmpeg_exe() -> str:
    return FFMPEG if os.path.exists(FFMPEG) else (shutil.which("ffmpeg") or "ffmpeg")


# ---------------------------------------------------------------------------
# 1. Script generation
# ---------------------------------------------------------------------------
async def generate_script(topic: str, seconds: int = 30) -> str:
    target_words = int(seconds * WORDS_PER_SEC)
    chat = LlmChat(
        api_key=EMERGENT_LLM_KEY,
        session_id=f"script-{abs(hash(topic)) % 100000}",
        system_message=(
            "You are an elite short-form video scriptwriter for TikTok, Reels and Shorts. "
            "You write punchy, spoken-word narration that hooks in the first 3 seconds."
        ),
    ).with_model("openai", "gpt-5.4")

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
    text = await chat.send_message(UserMessage(text=prompt))
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
# 2. Voiceover (TTS)
# ---------------------------------------------------------------------------
async def synth_voice(script: str, voice_id: str, out_path: str, speed: float = 1.0) -> None:
    voice = VOICE_MAP.get(voice_id, VOICE_MAP["onyx"])["openai"]
    tts = OpenAITextToSpeech(api_key=EMERGENT_LLM_KEY)
    text = re.sub(r"\s+", " ", script).strip()[:4000]
    spd = max(0.5, min(1.5, float(speed)))
    audio = await tts.generate_speech(text=text, model="tts-1-hd", voice=voice,
                                      speed=spd, response_format="mp3")
    with open(out_path, "wb") as f:
        f.write(audio)


async def synth_voice_sample(voice_id: str, out_path: str) -> None:
    v = VOICE_MAP.get(voice_id, VOICE_MAP["onyx"])
    tts = OpenAITextToSpeech(api_key=EMERGENT_LLM_KEY)
    phrase = f"Hi, I'm {v['name']}. Here's how I'll sound narrating your reels."
    audio = await tts.generate_speech(text=phrase, model="tts-1", voice=v["openai"], response_format="mp3")
    with open(out_path, "wb") as f:
        f.write(audio)


# ---------------------------------------------------------------------------
# 3. Caption alignment (Whisper word timestamps)
# ---------------------------------------------------------------------------
async def transcribe_words(audio_path: str):
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
