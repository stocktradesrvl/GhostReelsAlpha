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
- **Follow-up (2026-08 · batch 5): Caption Animations** (`caption_anim`: pop/slide/bounce/none per-word
  entrances via ASS \t/\move); **Dynamic Backgrounds** (`bg_motion` subtle/dynamic → gradient animation
  speed so colours visibly shift); **Save Preset** (local brand styles via storage JSON; PresetSheet
  uses plain TextInput — BottomSheetTextInput crashes on RN-web); **Batch Generate** (`POST /api/reels/batch`
  turns up to 12 topics into individual reels; dedicated /batch screen). Render-level features verified via
  synthetic-audio renders (no LLM spend); frontend controls + preset save/apply verified.
- **Follow-up (2026-08 · batch 6): Music Library** (6 CC0 beds: lofi/upbeat/cinematic/dreamy/groove/focus);
  **Reel Analytics** (`views`/`downloads` counters; `POST /reels/{id}/view` & `/download`; shown on detail);
  **Custom Colours** (`bg_theme='custom'` + `custom_c1`/`custom_c2` hex → 4-stop gradient; hex inputs in UI);
  **Scheduled Batches** (`POST /reels/batch` accepts `scheduled_at`; reels wait as status `scheduled` until an
  async scheduler_loop promotes them; Batch screen WHEN=Now/Tonight·2AM). Verified via synthetic renders +
  UI screenshots; generation itself gated only by LLM key budget.
- **Follow-up (2026-08 · batch 7): AI Visuals** — new `visual_mode` ('gradient'|'ai'). In 'ai' mode the
  backend derives N scene image prompts from the script (gpt-5.4), generates vertical images via Gemini
  Nano Banana (gemini-3.1-flash-image-preview, Emergent key), then composes them as a Ken-Burns pan/zoom
  background (`render_video_images`: `-loop 1 -t seg` per image + zoompan d=1 + concat) with captions on top.
  Create screen has a VISUAL STYLE toggle. Verified: backend 9/9 pytest; ffmpeg image render validated with
  dummy scenes (scenes advance correctly). NOTE: user's reported "error creating video" = Universal LLM key
  BUDGET CAP (Max budget 1.4 exceeded), confirmed by testing agent — a credits issue, not a code bug.

- **Follow-up (2026-08 · batch 8 · forked): SERIES + Custom Outro + friendlier errors.**
  - **Series** (`series` collection: `{id,title,premise,tone,characters:[{name,description}],settings(ReelSettings snapshot),episode_count}`).
    Reels gained `series_id` + `episode_number`. Endpoints: `POST/GET /api/series`, `GET /api/series/{id}`
    (returns `{series, episodes}`), `DELETE /api/series/{id}`, `POST /api/series/suggest` (AI character bible from
    premise), `POST /api/series/{id}/episode` (optional `topic`; blank = AI continues). `pipeline.generate_series_script`
    feeds premise+tone+character bible+prior episode scripts for continuity; AI-visual prompts get the character bible
    appended so recurring characters stay visually consistent. Frontend: new **Series tab** + `series/new` (title,
    premise, tone, AI-suggest characters, visual/voice/length, global outro) + `series/[id]` (bible, episode list,
    "Generate episode N" with optional topic).
  - **Custom Outro** (`outros` collection; `POST /api/outros` multipart → object storage, `GET/DELETE /api/outros`,
    `GET /api/outros/{id}/video`). `outro_id` added to ReelSettings → reels/series. `pipeline.append_outro` normalises
    the clip to 1080×1920/30fps and concats it after the render (adds silent audio if the clip has none). Frontend:
    reusable `OutroSheet` (upload via expo-image-picker, select/delete) wired into Create (per-reel) and New Series (global default).
  - **Share + Reminders**: reel detail "Post to YouTube / Instagram" opens the native share sheet; "Remind me to post"
    schedules a local notification (expo-notifications) via preset chips (1h/3h/tonight/tomorrow). Full auto-upload
    (YouTube OAuth / Meta API) intentionally deferred per user until the app has a build.
  - **Friendlier errors**: reels now carry `error_code` (`budget`|`storage`|`generic`); `classify_error()` maps raw
    litellm/objstore failures to friendly copy on Create banner + reel detail. `storage_client.put_object` retries 5xx.
  - **DEV FLAG**: `REELS_MOCK` in backend/.env — when `1`, the pipeline synthesises script/audio/captions/images/outro
    (no LLM/TTS/image credits) so the full render can be tested cheaply. **Must stay `0` in production.** Verified via
    testing agent iteration 7: backend 10/10 + frontend flows green.

## Backlog
- P1: multiple caption layout presets; background music track option; ElevenLabs voice option.
- P2: multi-aspect export (Reels/Shorts variants); onboarding; brand kit (logo watermark).
- P2: retry queue durability across server restarts; per-user library (auth).

## Next tasks
- Add optional background-music mixing.
- Add a captions position/size preset picker.
