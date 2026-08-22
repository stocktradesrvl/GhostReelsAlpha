# Faceless AI Reels — PRD

## Original problem statement
Build a mobile app ("Faceless AI Reels"): turn a topic or a pasted script into a TikTok-ready
vertical MP4. Pipeline: script → voice → captions → render. v1 skips stock b-roll and uses an
animated gradient background behind word-by-word karaoke captions.

## User choices (locked)
- Input: BOTH — paste a script OR generate a script from a topic (AI).
- Voiceover: OpenAI TTS (Emergent-managed, `tts-1-hd`).
- B-roll: skipped — animated gradient background behind captions.
- Captions: word-by-word karaoke highlight, burned into the MP4.
- Design: bold dark "creator studio" (Signal Red on obsidian; Barlow Condensed + Manrope).

## Architecture
- **Frontend:** Expo Router (SDK 54). Tabs: Create + Library. Stack route `reel/[id]` for
  generation progress + preview/export. Fonts loaded via expo-font. Bottom sheets via
  @gorhom/bottom-sheet. Keyboard via react-native-keyboard-controller. Video via expo-video.
- **Backend:** FastAPI. Async job model — `POST /api/reels` inserts a reel (status `queued`) and
  launches `run_pipeline` as an asyncio task; frontend polls `GET /api/reels/{id}`.
- **Pipeline (`pipeline.py`):**
  1. Script — Emergent LLM (`gpt-5.4`) via emergentintegrations `LlmChat`.
  2. Voice — `OpenAITextToSpeech` (`tts-1-hd`) → mp3.
  3. Captions — `OpenAISpeechToText` (whisper-1, verbose_json + word timestamps) → ASS karaoke
     (Barlow Condensed Bold, thick outline, active word colored/scaled).
  4. Render — ffmpeg (imageio-ffmpeg bundled binary): animated `gradients` bg + burned ASS subs
     + AAC audio → 1080×1920 H.264, `+faststart`. Thumbnail extracted at t=1.2s.
  5. Upload — Emergent Managed Object Storage (durable); local `/app/backend/media` cache serves
     video/thumb via FileResponse (Range support).
- **DB:** MongoDB `reels` collection; uuid `id`, `_id` never returned.

## Integrations
- Emergent LLM key (script gen, TTS, Whisper transcription, Object Storage) — in backend/.env.

## Data model — Reel
id, title, input_mode, topic, script, seconds, voice_id, caption_style, bg_theme,
status (queued|scripting|voicing|captioning|rendering|uploading|ready|failed), progress,
stage_label, error, duration, word_count, has_video, video_path, thumb_path, created_at, updated_at.

## API
- GET /api/config · POST /api/script · POST /api/reels · GET /api/reels · GET /api/reels/{id}
- DELETE /api/reels/{id} · GET /api/reels/{id}/video · GET /api/reels/{id}/thumb

## Implemented (2026-06 / 2026-08)
- Full topic→MP4 pipeline, async job + polling, karaoke captions, 4 gradient themes,
  6 voices, 4 caption colors, 15/30/60s lengths.
- Create screen (dual mode, AI script writer, editable preview, studio settings sheets, sticky CTA).
- Generation progress screen (4-stage tracker + % bar), 9:16 player, Save/Share export.
- Library grid with thumbnails + status badges, pull-to-refresh, empty state.
- **Follow-up (2026-08): Background Music** (CC0 lofi beds: lofi/upbeat/cinematic, ffmpeg amix
  ducked under voice); **Caption Presets** (position bottom/center/top + size s/m/l via ASS);
  **Brand Watermark** (top-center, rendered via libass overlay — static ffmpeg has no drawtext);
  **Voice Preview** (`GET /api/voices/{id}/preview` cached TTS sample, played via expo-audio in
  the voice picker). Tested: backend 8/8 + frontend 5/5 pass.
- **Follow-up (2026-08 · batch 3): Music Volume** per-reel slider (`music_volume` 0..1 → ffmpeg
  amix); **Voice Speed** slow/normal/fast (`voice_speed` → TTS speed); **Auto Hook Line**
  (`hook_enabled` burns the opening line as an amber title card in first ~2s via libass);
  **Save to Gallery** (native, expo-media-library with full permission handling + Open Settings
  fallback; web falls back to Download). Tested: backend 4/4 + frontend 5/5 pass.
- **Follow-up (2026-08 · batch 4): Music Fade** (afade in/out on the music bed); **Caption Font
  Styles** (`caption_font`: Barlow Condensed / Anton / Archivo Black via libass); **Duplicate Reel**
  ('Duplicate & edit' opens Create pre-filled via `?dup=<id>`); **End Card CTA** (`endcard_text`
  burns a closing card in the final ~1.6s; captions clamp to clear before it). Tested: backend 3/3
  + frontend pass (incl. full duplicate prefill flow).

## Backlog
- P1: multiple caption layout presets; background music track option; ElevenLabs voice option.
- P2: multi-aspect export (Reels/Shorts variants); onboarding; brand kit (logo watermark).
- P2: retry queue durability across server restarts; per-user library (auth).

## Next tasks
- Add optional background-music mixing.
- Add a captions position/size preset picker.
