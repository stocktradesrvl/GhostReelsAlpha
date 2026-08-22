"""Static catalogs for voices, caption styles and background gradient themes."""

# OpenAI TTS voices surfaced with friendly, creator-facing names.
VOICES = [
    {"id": "onyx", "name": "Atlas", "tagline": "Deep, cinematic narrator", "openai": "onyx"},
    {"id": "nova", "name": "Nova", "tagline": "Energetic & upbeat", "openai": "nova"},
    {"id": "shimmer", "name": "Luna", "tagline": "Bright & friendly", "openai": "shimmer"},
    {"id": "echo", "name": "Echo", "tagline": "Calm & smooth", "openai": "echo"},
    {"id": "fable", "name": "Fable", "tagline": "Expressive storyteller", "openai": "fable"},
    {"id": "sage", "name": "Sage", "tagline": "Measured & wise", "openai": "sage"},
]
VOICE_MAP = {v["id"]: v for v in VOICES}

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
