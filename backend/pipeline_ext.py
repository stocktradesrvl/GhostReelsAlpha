"""Runtime patches for ElevenLabs TTS + multi-aspect ffmpeg (imported from storage_client)."""
from __future__ import annotations

import contextvars
import os
import re
from pathlib import Path as _Path

import pipeline
from reels_config import ASPECT_MAP, VOICE_MAP

_USER_ELEVEN: contextvars.ContextVar = contextvars.ContextVar("user_elevenlabs_key", default="")
_oa = pipeline._USER_OPENAI
_gk = pipeline._USER_GOOGLE


class _UserKeys:
    def __getitem__(self, k):
        if k == "openai":
            return _oa.get()
        if k == "elevenlabs":
            return _USER_ELEVEN.get()
        return _gk.get()


pipeline.USER_KEYS = _UserKeys()
# Keep a module-global alias used by patched helpers below.
USER_KEYS = pipeline.USER_KEYS
OwnKeyError = pipeline.OwnKeyError


def set_user_keys(openai_key: str = "", google_key: str = "", elevenlabs_key: str = "") -> None:
    _oa.set((openai_key or "").strip())
    _gk.set((google_key or "").strip())
    _USER_ELEVEN.set((elevenlabs_key or "").strip())


async def validate_elevenlabs_key(key: str) -> bool:
    import httpx
    async with httpx.AsyncClient(timeout=20) as client:
        r = await client.get("https://api.elevenlabs.io/v1/user", headers={"xi-api-key": key})
        if r.status_code >= 400:
            raise RuntimeError(f"ElevenLabs rejected this key ({r.status_code})")
    return True


async def _elevenlabs_tts_bytes(text: str, el_voice_id: str, speed: float) -> bytes:
    import httpx
    key = USER_KEYS["elevenlabs"]
    if not key:
        raise RuntimeError("ElevenLabs key is not set")
    text = re.sub(r"\s+", " ", text).strip()[:4000]
    spd = max(0.7, min(1.2, float(speed)))
    payload = {
        "text": text,
        "model_id": "eleven_multilingual_v2",
        "voice_settings": {"stability": 0.5, "similarity_boost": 0.75, "speed": spd},
    }
    headers = {"xi-api-key": key, "accept": "audio/mpeg", "content-type": "application/json"}
    url = f"https://api.elevenlabs.io/v1/text-to-speech/{el_voice_id}"
    try:
        async with httpx.AsyncClient(timeout=90) as client:
            r = await client.post(url, headers=headers, json=payload)
            if r.status_code == 400 and "speed" in (r.text or "").lower():
                payload["voice_settings"].pop("speed", None)
                r = await client.post(url, headers=headers, json=payload)
            if r.status_code >= 400:
                raise RuntimeError(r.text[:400] or f"ElevenLabs HTTP {r.status_code}")
            return r.content
    except OwnKeyError:
        raise
    except Exception as e:  # noqa: BLE001
        raise OwnKeyError("elevenlabs", e)


def resolve_voice(voice_id: str) -> dict:
    v = VOICE_MAP.get(voice_id) or VOICE_MAP["onyx"]
    if v.get("engine") == "elevenlabs" and not USER_KEYS["elevenlabs"]:
        return VOICE_MAP.get(v.get("openai_fallback") or "onyx", VOICE_MAP["onyx"])
    return v


_orig_synth = pipeline.synth_voice
_orig_sample = pipeline.synth_voice_sample


async def synth_voice(script: str, voice_id: str, out_path: str, speed: float = 1.0) -> None:
    if pipeline.MOCK:
        return await _orig_synth(script, voice_id, out_path, speed=speed)
    voice = resolve_voice(voice_id)
    if voice.get("engine") == "elevenlabs":
        audio = await _elevenlabs_tts_bytes(script, voice["el_id"], speed)
        with open(out_path, "wb") as f:
            f.write(audio)
        return
    audio = await pipeline._tts_bytes(script, voice.get("openai") or "onyx", speed)
    with open(out_path, "wb") as f:
        f.write(audio)


async def synth_voice_sample(voice_id: str, out_path: str) -> None:
    catalog = VOICE_MAP.get(voice_id, VOICE_MAP["onyx"])
    phrase = f"Hi, I'm {catalog['name']}. Here's how I'll sound narrating your reels."
    if pipeline.MOCK:
        return await _orig_sample(voice_id, out_path)
    voice = resolve_voice(voice_id)
    if voice.get("engine") == "elevenlabs":
        audio = await _elevenlabs_tts_bytes(phrase, voice["el_id"], 1.0)
    else:
        audio = await pipeline._tts_bytes(phrase, voice.get("openai") or "onyx", 1.0)
    with open(out_path, "wb") as f:
        f.write(audio)


def aspect_size(aspect: str = "9:16") -> tuple:
    a = ASPECT_MAP.get(aspect) or ASPECT_MAP["9:16"]
    return int(a["width"]), int(a["height"])


def _ass_header(fontsize: int, alignment: int, marginv: int, fontname: str = "Barlow Condensed",
                width: int = 1080, height: int = 1920) -> str:
    return (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {int(width)}\n"
        f"PlayResY: {int(height)}\n"
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


_orig_build = pipeline.build_ass
_orig_header = pipeline._ass_header
_orig_render = pipeline.render_video
_orig_render_img = pipeline.render_video_images


def build_ass(words, duration, caption_style: str, out_path: str,
              position: str = "center", size: str = "m", watermark: str = "",
              hook_text: str = "", caption_font: str = "barlow", endcard_text: str = "",
              caption_anim: str = "pop", width: int = 1080, height: int = 1920) -> None:
    from reels_config import CAPTION_ANIM_MAP, CAPTION_FONT_MAP, CAPTION_MAP, CAPTION_POSITION_MAP, CAPTION_SIZE_MAP
    width, height = int(width or 1080), int(height or 1920)
    if width == 1080 and height == 1920:
        return _orig_build(words, duration, caption_style, out_path, position, size, watermark,
                           hook_text, caption_font, endcard_text, caption_anim)
    color = CAPTION_MAP.get(caption_style, CAPTION_MAP["signal"])["ass_color"]
    pos = CAPTION_POSITION_MAP.get(position, CAPTION_POSITION_MAP["center"])
    sz = CAPTION_SIZE_MAP.get(size, CAPTION_SIZE_MAP["m"])
    fam = CAPTION_FONT_MAP.get(caption_font, CAPTION_FONT_MAP["barlow"])["family"]
    anim = caption_anim if caption_anim in CAPTION_ANIM_MAP else "pop"
    scale = min(width / 1080.0, height / 1920.0)
    fontsize = max(28, int(sz["fontsize"] * scale))
    marginv = int(pos["marginv"] * (height / 1920.0))
    pipeline._ass_header = lambda *a, **k: _ass_header(fontsize, pos["an"], marginv, fontname=fam,
                                                       width=width, height=height)
    try:
        header = _ass_header(fontsize, pos["an"], marginv, fontname=fam, width=width, height=height)
        lines = [header]
        an, mv = pos["an"], marginv
        cap_y = (height - mv) if an == 2 else (mv if an == 8 else height // 2)
        cx = width // 2
        if anim == "none":
            intro = "{\\fad(50,40)}"
        elif anim == "slide":
            intro = f"{{\\fad(40,30)\\move({cx},{cap_y + 70},{cx},{cap_y},0,160)}}"
        elif anim == "bounce":
            intro = "{\\fad(40,20)\\fscx55\\fscy55\\t(0,130,\\fscx113\\fscy113)\\t(130,240,\\fscx100\\fscy100)}"
        else:
            intro = "{\\fad(50,30)\\fscx86\\fscy86\\t(0,110,\\fscx100\\fscy100)}"
        wm = pipeline._sanitize_watermark(watermark)
        total = max(1.0, float(duration or 1.0))
        cap_limit = total
        if wm:
            lines.append(f"Dialogue: 1,{pipeline._fmt_time(0)},{pipeline._fmt_time(total)},WM,,0,0,0,,{pipeline._ass_escape(wm)}\n")
        hk = pipeline._ass_escape((hook_text or "").strip().upper())
        if hk:
            hook_end = min(total, 1.9)
            pop = "{\\fad(120,300)\\fscx55\\fscy55\\t(0,220,\\fscx104\\fscy104)\\t(220,360,\\fscx100\\fscy100)}"
            lines.append(f"Dialogue: 2,{pipeline._fmt_time(0.12)},{pipeline._fmt_time(hook_end)},Hook,,0,0,0,,{pop}{hk}\n")
        ec = pipeline._ass_escape((endcard_text or "").strip().upper())
        if ec:
            ec_start = max(0.0, total - 1.6)
            cap_limit = ec_start
            ecpop = "{\\fad(180,120)\\fscx70\\fscy70\\t(0,260,\\fscx103\\fscy103)\\t(260,420,\\fscx100\\fscy100)}"
            lines.append(f"Dialogue: 3,{pipeline._fmt_time(ec_start)},{pipeline._fmt_time(total)},End,,0,0,0,,{ecpop}{ec}\n")
        if not words:
            _Path(out_path).write_text("".join(lines), encoding="utf-8")
            return
        groups = [words[i:i + 3] for i in range(0, len(words), 3)]
        for gi, group in enumerate(groups):
            next_group_start = groups[gi + 1][0]["start"] if gi + 1 < len(groups) else group[-1]["end"] + 0.4
            for wi, w in enumerate(group):
                seg_start = w["start"]
                if seg_start >= cap_limit:
                    continue
                seg_end = group[wi + 1]["start"] if wi + 1 < len(group) else next_group_start
                if seg_end <= seg_start:
                    seg_end = seg_start + 0.15
                seg_end = min(seg_end, cap_limit)
                parts = []
                for k, gw in enumerate(group):
                    tok = pipeline._ass_escape(gw["word"].upper())
                    if k == wi:
                        parts.append(f"{{\\c{color}\\fscx112\\fscy112}}{tok}{{\\r}}")
                    else:
                        parts.append(tok)
                text = " ".join(parts)
                lines.append(f"Dialogue: 0,{pipeline._fmt_time(seg_start)},{pipeline._fmt_time(seg_end)},Cap,,0,0,0,,{intro}{text}\n")
        _Path(out_path).write_text("".join(lines), encoding="utf-8")
    finally:
        pipeline._ass_header = _orig_header


async def render_video(audio_path: str, ass_name: str, bg_theme: str, duration: float,
                       workdir: str, out_path: str, music_id: str = "none",
                       music_volume=None, bg_motion: str = "subtle",
                       custom_colors=None, width: int = 1080, height: int = 1920) -> None:
    if music_volume is None:
        music_volume = pipeline.MUSIC_VOLUME
    width, height = int(width or 1080), int(height or 1920)
    if width == 1080 and height == 1920:
        return await _orig_render(audio_path, ass_name, bg_theme, duration, workdir, out_path,
                                  music_id, music_volume, bg_motion, custom_colors)
    from reels_config import BG_MAP, BG_MOTION_MAP, MUSIC_MAP
    if bg_theme == "custom" and custom_colors and len(custom_colors) == 2:
        c1, c2 = pipeline._hex_to_ff(custom_colors[0]), pipeline._hex_to_ff(custom_colors[1])
        c = ["0x09090B", c2, c1, "0x18181B"] if (c1 and c2) else BG_MAP["ember"]["colors"]
    else:
        c = BG_MAP.get(bg_theme, BG_MAP["ember"])["colors"]
    dur = max(1.0, float(duration))
    speed = BG_MOTION_MAP.get(bg_motion, BG_MOTION_MAP["subtle"])["speed"]
    x1, y1 = int(width * 0.89), int(height * 0.94)
    grad = (
        f"gradients=s={width}x{height}:c0={c[0]}:c1={c[1]}:c2={c[2]}:c3={c[3]}"
        f":x0=120:y0=120:x1={x1}:y1={y1}:nb_colors=4:seed=7:duration={dur:.2f}:speed={speed}:rate=30"
    )
    vchain = f"[0:v]format=yuv420p,ass={ass_name}:fontsdir={pipeline.FONTS_DIR}[v]"
    track = MUSIC_MAP.get(music_id or "none", MUSIC_MAP["none"])
    music_path = None
    if track["file"]:
        candidate = os.path.join(pipeline.MUSIC_DIR, track["file"])
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
        pipeline._ffmpeg_exe(), "-y", *inputs, "-filter_complex", filter_complex, *amap,
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-t", f"{dur:.2f}", "-shortest", "-movflags", "+faststart",
        out_path,
    ]
    import asyncio
    proc = await asyncio.create_subprocess_exec(*cmd, cwd=workdir, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg render failed: {stderr.decode()[-1500:]}")


async def render_video_images(audio_path: str, ass_name: str, image_paths: list, duration: float,
                              workdir: str, out_path: str, music_id: str = "none",
                              music_volume=None, width: int = 1080, height: int = 1920) -> None:
    if music_volume is None:
        music_volume = pipeline.MUSIC_VOLUME
    width, height = int(width or 1080), int(height or 1920)
    if width == 1080 and height == 1920:
        return await _orig_render_img(audio_path, ass_name, image_paths, duration, workdir, out_path,
                                      music_id, music_volume)
    from reels_config import MUSIC_MAP
    import asyncio
    dur = max(1.0, float(duration))
    n = max(1, len(image_paths))
    fps = 30
    seg_sec = dur / n
    sw, sh = int(width * 1.25), int(height * 1.25)
    inputs = []
    vlabels = ""
    for img in image_paths:
        inputs += ["-loop", "1", "-t", f"{seg_sec:.3f}", "-i", img]
    for i in range(n):
        vlabels += (
            f"[{i}:v]scale={sw}:{sh}:force_original_aspect_ratio=increase,crop={sw}:{sh},"
            f"fps={fps},zoompan=z='min(1.0+0.0012*on,1.18)':d=1:x='iw/2-(iw/zoom/2)':"
            f"y='ih/2-(ih/zoom/2)':s={width}x{height},setsar=1[v{i}];"
        )
    concat_in = "".join(f"[v{i}]" for i in range(n))
    vchain = f"{vlabels}{concat_in}concat=n={n}:v=1:a=0[vc];[vc]ass={ass_name}:fontsdir={pipeline.FONTS_DIR}[v]"
    audio_idx = n
    inputs += ["-i", audio_path]
    track = MUSIC_MAP.get(music_id or "none", MUSIC_MAP["none"])
    music_path = os.path.join(pipeline.MUSIC_DIR, track["file"]) if track["file"] else None
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
        pipeline._ffmpeg_exe(), "-y", *inputs, "-filter_complex", filter_complex, *amap,
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "26", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "160k", "-t", f"{dur:.2f}", "-shortest", "-movflags", "+faststart",
        out_path,
    ]
    proc = await asyncio.create_subprocess_exec(*cmd, cwd=workdir, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg image render failed: {stderr.decode()[-1500:]}")


pipeline.set_user_keys = set_user_keys
pipeline.validate_elevenlabs_key = validate_elevenlabs_key
pipeline._elevenlabs_tts_bytes = _elevenlabs_tts_bytes
pipeline.resolve_voice = resolve_voice
pipeline.synth_voice = synth_voice
pipeline.synth_voice_sample = synth_voice_sample
pipeline.aspect_size = aspect_size
pipeline.build_ass = build_ass
pipeline.render_video = render_video
pipeline.render_video_images = render_video_images
