"""Standalone repro for the '82% hang' AI-image render.
Creates realistic Gemini-sized vertical PNGs + a real audio track + an ASS file,
then runs pipeline.render_video_images and times it. Run: python tests/test_render_82.py
"""
import asyncio
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pipeline  # noqa: E402


async def _mk_png(path, w, h, color):
    proc = await asyncio.create_subprocess_exec(
        pipeline._ffmpeg_exe(), "-y", "-f", "lavfi",
        "-i", f"color=c={color}:s={w}x{h}:d=1", "-frames:v", "1", path,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await proc.communicate()


async def _mk_audio(path, dur):
    proc = await asyncio.create_subprocess_exec(
        pipeline._ffmpeg_exe(), "-y", "-f", "lavfi",
        "-i", f"sine=frequency=220:duration={dur}", "-c:a", "aac", path,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    await proc.communicate()


ASS = """[Script Info]
ScriptType: v4.00+
PlayResX: 1080
PlayResY: 1920

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Outline, Alignment, MarginV
Style: Default,Arial,72,&H00FFFFFF,&H00000000,&H00000000,1,4,5,120

[Events]
Format: Layer, Start, End, Style, Text
Dialogue: 0,0:00:00.00,0:00:30.00,Default,,Hello world caption test
"""


async def main():
    wd = "/tmp/render82"
    os.makedirs(wd, exist_ok=True)
    dur = 30.0
    # Gemini vertical images can be large; simulate a few realistic sizes incl. a big one.
    sizes = [(2048, 3072), (2816, 5013), (1290, 2304), (4096, 6144)]
    imgs = []
    colors = ["red", "green", "blue", "orange"]
    for i, (w, h) in enumerate(sizes):
        p = os.path.join(wd, f"scene_{i}.png")
        await _mk_png(p, w, h, colors[i])
        imgs.append(p)
    apath = os.path.join(wd, "voice.aac")
    await _mk_audio(apath, dur)
    with open(os.path.join(wd, "subs.ass"), "w") as f:
        f.write(ASS)
    out = os.path.join(wd, "out.mp4")

    t0 = time.time()
    try:
        await asyncio.wait_for(
            pipeline.render_video_images(apath, "subs.ass", imgs, dur, wd, out,
                                         music_id="lofi", music_volume=0.13),
            timeout=180,
        )
        el = time.time() - t0
        sz = os.path.getsize(out) if os.path.exists(out) else 0
        print(f"OK render in {el:.1f}s, out size={sz} bytes")
    except asyncio.TimeoutError:
        print(f"HANG: render exceeded 180s (reproduces the 82% hang)")
    except Exception as e:
        print(f"FAIL: {type(e).__name__}: {str(e)[:800]}")


if __name__ == "__main__":
    asyncio.run(main())
