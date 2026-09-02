"""Static catalogs for voices, caption styles and background gradient themes."""

# OpenAI TTS voices (default engine). engine="openai" so the picker can mix in ElevenLabs.
OPENAI_VOICES = [
    {"id": "onyx", "name": "Atlas", "tagline": "Deep, cinematic narrator", "openai": "onyx", "engine": "openai"},
    {"id": "nova", "name": "Nova", "tagline": "Energetic & upbeat", "openai": "nova", "engine": "openai"},
    {"id": "shimmer", "name": "Luna", "tagline": "Bright & friendly", "openai": "shimmer", "engine": "openai"},
    {"id": "echo", "name": "Echo", "tagline": "Calm & smooth", "openai": "echo", "engine": "openai"},
    {"id": "fable", "name": "Fable", "tagline": "Expressive storyteller", "openai": "fable", "engine": "openai"},
    {"id": "sage", "name": "Sage", "tagline": "Measured & wise", "openai": "sage", "engine": "openai"},
]

# ElevenLabs premade voices. `el_id` is the public catalog voice id (not a secret).
# Used only when the user has saved their own ElevenLabs key (BYOK). OpenAI remains
# the default; if ElevenLabs is unset we fall back to `openai_fallback`.
ELEVENLABS_VOICES = [
    {"id": "el_rachel", "name": "Rachel", "tagline": "Calm, conversational", "engine": "elevenlabs",
     "el_id": "21m00Tcm4TlvDq8ikWAM", "openai_fallback": "nova"},
    {"id": "el_domi", "name": "Domi", "tagline": "Strong & confident", "engine": "elevenlabs",
     "el_id": "AZnzlk1XvdvUeBnXmlld", "openai_fallback": "onyx"},
    {"id": "el_bella", "name": "Bella", "tagline": "Soft & warm", "engine": "elevenlabs",
     "el_id": "EXAVITQu4vr4xnSDxMaL", "openai_fallback": "shimmer"},
    {"id": "el_antoni", "name": "Antoni", "tagline": "Well-rounded narrator", "engine": "elevenlabs",
     "el_id": "ErXwobaYiN019PkySvjV", "openai_fallback": "echo"},
    {"id": "el_elli", "name": "Elli", "tagline": "Young & expressive", "engine": "elevenlabs",
     "el_id": "MF3mGyEYCl7XYWbV9V6O", "openai_fallback": "nova"},
    {"id": "el_josh", "name": "Josh", "tagline": "Deep & resonant", "engine": "elevenlabs",
     "el_id": "TxGEqnHWrfWFTfGW9XjX", "openai_fallback": "onyx"},
]

VOICES = OPENAI_VOICES + ELEVENLABS_VOICES
VOICE_MAP = {v["id"]: v for v in VOICES}

# Export aspect ratios. 9:16 is the master; 1:1 and 16:9 are recomposed from stored
# audio + captions + scenes (no LLM/TTS rerun).
ASPECTS = [
    {"id": "9:16", "name": "9:16 Vertical", "hint": "Reels / Shorts / TikTok", "width": 1080, "height": 1920},
    {"id": "1:1", "name": "1:1 Square", "hint": "Feed post", "width": 1080, "height": 1080},
    {"id": "16:9", "name": "16:9 Landscape", "hint": "YouTube", "width": 1920, "height": 1080},
]
ASPECT_MAP = {a["id"]: a for a in ASPECTS}

# Caption highlight color (ASS uses &HBBGGRR&).
CAPTION_STYLES = [
    {"id": "signal", "name": "Signal", "hint": "Red pop", "ass_color": "&H4444EF&", "hex": "#EF4444"},
    {"id": "mono", "name": "Mono", "hint": "Clean white", "ass_color": "&H00FFFFFF&", "hex": "#FFFFFF"},
    {"id": "sunset", "name": "Sunset", "hint": "Warm orange", "ass_color": "&H0B58EA&", "hex": "#EA580C"},
    {"id": "mint", "name": "Mint", "hint": "Fresh teal", "ass_color": "&H8894D9&", "hex": "#D99488"},
]
CAPTION_MAP = {c["id"]: c for c in CAPTION_STYLES}

# Background gradient themes -> 4 ffmpeg gradient colors (0xRRGGBB) + preview colors.
BG_THEMES = [
    {
        "id": "ember",
        "name": "Ember",
        "colors": ["0x09090B", "0x450A0A", "0xDC2626", "0x18181B"],
        "preview": ["#DC2626", "#450A0A", "#09090B"],
    },
    {
        "id": "midnight",
        "name": "Midnight",
        "colors": ["0x09090B", "0x0F766E", "0x0D9488", "0x18181B"],
        "preview": ["#0D9488", "#0F766E", "#09090B"],
    },
    {
        "id": "sunset",
        "name": "Sunset",
        "colors": ["0x18120B", "0x7C2D12", "0xEA580C", "0x09090B"],
        "preview": ["#EA580C", "#7C2D12", "#09090B"],
    },
    {
        "id": "mono",
        "name": "Graphite",
        "colors": ["0x09090B", "0x27272A", "0x3F3F46", "0x18181B"],
        "preview": ["#3F3F46", "#27272A", "#09090B"],
    },
]
BG_MAP = {b["id"]: b for b in BG_THEMES}

# Caption position -> ASS alignment (\an) + vertical margin.
CAPTION_POSITIONS = [
    {"id": "bottom", "name": "Lower", "an": 2, "marginv": 300},
    {"id": "center", "name": "Center", "an": 5, "marginv": 0},
    {"id": "top", "name": "Upper", "an": 8, "marginv": 300},
]
CAPTION_POSITION_MAP = {p["id"]: p for p in CAPTION_POSITIONS}

# Caption size -> ASS font size.
CAPTION_SIZES = [
    {"id": "s", "name": "Small", "fontsize": 80},
    {"id": "m", "name": "Medium", "fontsize": 104},
    {"id": "l", "name": "Large", "fontsize": 132},
]
CAPTION_SIZE_MAP = {s["id"]: s for s in CAPTION_SIZES}

# Caption fonts -> libass font family name (files live in assets/fonts).
CAPTION_FONTS = [
    {"id": "barlow", "name": "Barlow", "family": "Barlow Condensed"},
    {"id": "anton", "name": "Anton", "family": "Anton"},
    {"id": "archivo", "name": "Archivo", "family": "Archivo Black"},
]
CAPTION_FONT_MAP = {f["id"]: f for f in CAPTION_FONTS}

# Caption entrance animation styles.
CAPTION_ANIMS = [
    {"id": "pop", "name": "Pop"},
    {"id": "slide", "name": "Slide"},
    {"id": "bounce", "name": "Bounce"},
    {"id": "none", "name": "None"},
]
CAPTION_ANIM_MAP = {a["id"]: a for a in CAPTION_ANIMS}

# AI image styles -> prompt suffix appended to each scene prompt.
IMAGE_STYLES = [
    {"id": "cinematic", "name": "Cinematic", "suffix": "cinematic film still, dramatic moody lighting, shallow depth of field, photographic"},
    {"id": "photoreal", "name": "Photoreal", "suffix": "ultra photorealistic, 8k, natural realistic lighting, lifelike detail"},
    {"id": "anime", "name": "Anime", "suffix": "anime illustration, vibrant colors, clean linework, studio quality"},
    {"id": "painterly", "name": "Painterly", "suffix": "digital painting, concept art, artstation, dramatic brushwork"},
]
IMAGE_STYLE_MAP = {s["id"]: s for s in IMAGE_STYLES}

# Background motion -> gradient animation speed (higher = colors shift faster).
BG_MOTIONS = [
    {"id": "subtle", "name": "Subtle", "speed": 0.006},
    {"id": "dynamic", "name": "Dynamic", "speed": 0.035},
]
BG_MOTION_MAP = {m["id"]: m for m in BG_MOTIONS}

# Background music beds (CC0). `file` is relative to assets/music; None = silent.
MUSIC_TRACKS = [
    {"id": "none", "name": "No music", "file": None},
    {"id": "lofi", "name": "Lo-Fi Chill", "file": "chill.mp3"},
    {"id": "upbeat", "name": "Upbeat", "file": "upbeat.mp3"},
    {"id": "cinematic", "name": "Cinematic", "file": "cinematic.mp3"},
    {"id": "dreamy", "name": "Dreamy", "file": "dreamy.mp3"},
    {"id": "groove", "name": "Groove", "file": "groove.mp3"},
    {"id": "focus", "name": "Focus", "file": "focus.mp3"},
]
MUSIC_MAP = {m["id"]: m for m in MUSIC_TRACKS}
MUSIC_VOLUME = 0.13

# Narration pace -> OpenAI TTS speed multiplier.
VOICE_SPEEDS = [
    {"id": "slow", "name": "Slow", "speed": 0.85},
    {"id": "normal", "name": "Normal", "speed": 1.0},
    {"id": "fast", "name": "Fast", "speed": 1.15},
]
VOICE_SPEED_MAP = {s["id"]: s for s in VOICE_SPEEDS}
