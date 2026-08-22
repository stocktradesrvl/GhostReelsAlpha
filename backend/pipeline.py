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

from reels_config import BG_MAP, CAPTION_MAP, VOICE_MAP

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

EMERGENT_LLM_KEY = os.environ["EMERGENT_LLM_KEY"]
FONTS_DIR = str(ROOT_DIR / "assets" / "fonts")
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

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


# ---------------------------------------------------------------------------
# 2. Voiceover (TTS)
# ---------------------------------------------------------------------------
async def synth_voice(script: str, voice_id: str, out_path: str) -> None:
    voice = VOICE_MAP.get(voice_id, VOICE_MAP["onyx"])["openai"]
    tts = OpenAITextToSpeech(api_key=EMERGENT_LLM_KEY)
    text = re.sub(r"\s+", " ", script).strip()[:4000]
    audio = await tts.generate_speech(text=text, model="tts-1-hd", voice=voice, response_format="mp3")
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


def _ass_header(caption_color: str) -> str:
    # White base fill, thick black outline for readability on any gradient.
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
        "Style: Cap,Barlow Condensed,104,&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,"
        "-1,0,0,0,100,100,1,0,1,7,3,5,120,120,120,1\n\n"
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


def build_ass(words, duration, caption_style: str, out_path: str) -> None:
    color = CAPTION_MAP.get(caption_style, CAPTION_MAP["signal"])["ass_color"]
    lines = [_ass_header(color)]

    if not words:
        # Fallback: no timestamps -> nothing to karaoke; leave empty (video still renders).
        Path(out_path).write_text(lines[0], encoding="utf-8")
        return

    # Group words into on-screen phrases of up to 3 words.
    groups = [words[i:i + 3] for i in range(0, len(words), 3)]
    for gi, group in enumerate(groups):
        next_group_start = (
            groups[gi + 1][0]["start"] if gi + 1 < len(groups) else group[-1]["end"] + 0.4
        )
        for wi, w in enumerate(group):
            seg_start = w["start"]
            if wi + 1 < len(group):
                seg_end = group[wi + 1]["start"]
            else:
                seg_end = next_group_start
            if seg_end <= seg_start:
                seg_end = seg_start + 0.15

            parts = []
            for k, gw in enumerate(group):
                tok = _ass_escape(gw["word"].upper())
                if k == wi:
                    parts.append(f"{{\\c{color}\\fscx112\\fscy112}}{tok}{{\\r}}")
                else:
                    parts.append(tok)
            text = " ".join(parts)
            fade = "{\\fad(60,40)}"
            lines.append(
                f"Dialogue: 0,{_fmt_time(seg_start)},{_fmt_time(seg_end)},Cap,,0,0,0,,{fade}{text}\n"
            )

    Path(out_path).write_text("".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# 5. Render with ffmpeg (animated gradient bg + burned captions + voice)
# ---------------------------------------------------------------------------
async def render_video(audio_path: str, ass_name: str, bg_theme: str, duration: float, workdir: str, out_path: str) -> None:
    theme = BG_MAP.get(bg_theme, BG_MAP["ember"])
    c = theme["colors"]
    dur = max(1.0, float(duration))

    grad = (
        f"gradients=s=1080x1920:c0={c[0]}:c1={c[1]}:c2={c[2]}:c3={c[3]}"
        f":x0=120:y0=120:x1=960:y1=1800:nb_colors=4:seed=7:duration={dur:.2f}:speed=0.006:rate=30"
    )
    filter_complex = f"[0:v]format=yuv420p,ass={ass_name}:fontsdir={FONTS_DIR}[v]"

    cmd = [
        _ffmpeg_exe(), "-y",
        "-f", "lavfi", "-i", grad,
        "-i", audio_path,
        "-filter_complex", filter_complex,
        "-map", "[v]", "-map", "1:a",
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
