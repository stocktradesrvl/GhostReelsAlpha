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

- **Follow-up (2026-08 · batch 9 · forked): Per-Scene Redo.** AI-visual reels now persist their intermediate
  artifacts: voice mp3 (`audio_path`), Whisper word timings (`words`) and per-scene prompts+images
  (`scenes:[{prompt,image_path}]`) → all stored in object storage / the reel doc. New endpoints:
  `GET /api/reels/{id}/scenes`, `GET /api/reels/{id}/scene/{i}/image`, `POST /api/reels/{id}/scene/{i}/regenerate`
  (optional edited `prompt`). `regenerate_scene_task` regenerates just that one image then `recompose_reel` re-renders
  from stored audio+captions+images (skips script/TTS/Whisper → cheap & fast). Shared `finalize_and_upload` helper
  (thumb + outro + upload + ready) used by both full pipeline and recompose. Frontend: reel detail shows **Edit scenes**
  (AI reels only) → new `app/scenes/[id].tsx` editor (per-scene image + editable prompt + Regenerate, live polling,
  cache-busted image + video refresh). Verified: backend regen→recompose end-to-end (mock) + frontend 100% (iteration 8).
  NOTE: live "Confirm Live Output" run hit the Universal Key BUDGET CAP — real generation returns the friendly
  `error_code=budget` message (working as designed); top up credits to see real AI output.

- **Follow-up (2026-08 · batch 10 · forked): Regenerate Voice Line.** Voiceover is now synthesised **per sentence**
  (`pipeline.split_sentences` → `synth_voice_segments` → `concat_audio`); each sentence clip + the concatenated track
  are persisted (`segments:[{text,audio_path}]`, `audio_path`). New endpoints `GET /api/reels/{id}/lines` and
  `POST /api/reels/{id}/line/{i}/regenerate {text}`. `regenerate_line_task` re-records ONLY the edited sentence,
  re-concats all clips (unchanged lines stay byte-identical), re-runs Whisper for fresh word timings, updates
  script/words/duration, then `recompose_reel` (now handles BOTH gradient & AI) re-renders. Frontend: reel detail
  **Edit narration** → `app/lines/[id].tsx` (per-line text + "Re-record this line", live polling). Verified: backend
  line-regen→recompose end-to-end (mock, gradient) + narration editor UI renders. Live verify still blocked by budget cap.

- **Follow-up (2026-08 · batch 11 · forked): Settings page + BYOK + auto-hiding tab bar.**
  - **Settings** (`app/settings.tsx`, gear icon `testID settings-button` in Create/Series/Library headers, route in root stack): AI Keys (BYOK), Studio Defaults, Brand Kit, Saved Presets, About/credits.
  - **Bring-Your-Own-Key**: `app_settings` Mongo doc (`id="global"`) stores `openai_key`,`google_key`,`brand_handle`. `GET/PUT /api/settings` (GET masked only). Keys → `pipeline.set_user_keys()` at startup + on PUT. `pipeline.USER_KEYS` global; helpers `_chat_text` (OpenAI `gpt-4o-mini` when user key set else Emergent `gpt-5.4`), `_tts_bytes` (`tts-1`), whisper (`whisper-1`), images via `google-genai` `gemini-2.5-flash-image` (9:16) when Google key set — all fall back to Emergent key otherwise. `classify_error` maps auth/401/403 → `key`, 429 → `budget`; reel-detail handles `key`. Verified: invalid user key → friendly `error_code=key` (no Emergent credits spent).
  - **Studio Defaults** (`src/defaults.ts`, AsyncStorage): default voice/music/length/caption style prefill new reels (Create loads on mount; skipped when duplicating).
  - **Auto-hiding tab bar** (`src/tabbar.tsx`): `TabBarVisibilityProvider` + custom `HidingTabBar` (absolute, reanimated translateY) + `useHidingTabBar()` onScroll wired into Create/Series/Library. Slides away on scroll-down, returns on scroll-up (extra ~96 bottom padding added).
  - Verified via testing agent iteration 9: 6/6 frontend flows pass, no bugs.

## Backlog
- P1: multiple caption layout presets; background music track option; ElevenLabs voice option.
- P2: multi-aspect export (Reels/Shorts variants); onboarding; brand kit (logo watermark).
- P2: retry queue durability across server restarts; per-user library (auth).

## Next tasks
- **Optional hardening (flagged by tester):** scope `GET /reels/{id}`, `/video`, `/thumb`, `/view`,
  `/download`, `DELETE /reels/{id}`, and the scene/line regenerate endpoints by `user_id` (currently
  those reads/actions are uuid-guarded but not auth-scoped).
- **Full auto-upload** (YouTube/Meta OAuth) — deferred by user until the app has a store build.

## RevenueCat subscriptions (2026-06 · batch 13 · forked) — DONE
- **Emergent-managed RevenueCat** provisioned via integration proxy (`/setup`): project `proja26f3c2c`,
  entitlement `pro`, offering `default`, packages `$rc_monthly` ($9.99/P1M) + `$rc_annual` ($79.99/P1Y).
  SDK keys written to `frontend/.env` (`EXPO_PUBLIC_REVENUECAT_TEST/IOS/ANDROID_API_KEY`). Durable facts
  in `/app/memory/revenuecat.md`.
- **Frontend**: `react-native-purchases` + `react-native-purchases-ui` + `@tanstack/react-query`.
  `src/revenuecat.tsx` = `SubscriptionProvider`/`useSubscription` (customer-info + offerings + app-user-id
  queries, purchase/restore mutations, customer-info listener). SDK init at module scope in `_layout.tsx`
  (try/catch). `RCIdentityBridge` in `_layout` binds `Purchases.logIn(user.id)` on every auth path and
  syncs the SDK-verified `pro` entitlement to the backend.
  - **Identity note**: on the web (purchases-js) SDK `originalAppUserId` stays anonymous after `logIn`, so
    `identityReady`/the purchase choke point use `Purchases.getAppUserID()` (the current id) instead.
  - New **`app/paywall.tsx`** (modal): coded paywall (prices from offerings, never hardcoded), custom
    confirm modal (no Alert), Restore button, identity gate, unavailable/empty-offering + userCancelled
    handling, "simulated" label in dev. Reached from Settings PLAN section (`subscribe-button`) and the
    Create quota banner (`quota-banner` → `/paywall`).
- **Backend**: `POST /api/subscription/sync {is_subscribed}` (auth-scoped) sets `users.is_subscribed`.
  The existing `enforce_quota`/`consume_quota` gate already grants unlimited generation when
  `is_subscribed` (or BYOK) is true. Sync gated client-side on `customerInfo` having resolved to avoid a
  loading-state `false` clobbering a real entitlement.
- **Verified (web Test Store, self-tested)**: SDK init in Browser Mode ✓, real offerings render ✓,
  identity binds ✓, Test Store checkout → `pro` active → `isSubscribed=true` ✓, backend synced
  `is_subscribed=True` in Mongo ✓ (then reset to clean). **Real device purchases require a native build.**

## Monetization foundation (2026-08 · batch 12 · forked) — Auth + Quota + per-user encrypted BYOK
- **Auth**: email+password, bcrypt hashes, JWT (30-day) via `Authorization: Bearer`. `users` collection
  (uuid id, email unique). Endpoints `POST /api/auth/register|login`, `GET /api/auth/me`. `current_user`
  dependency. Frontend `src/auth.tsx` (AuthProvider, token in platform-safe `storage.secure*` — SecureStore
  on native, AsyncStorage on web), gate in `app/_layout.tsx` (RootNavigator redirects to `/auth`), `app/auth.tsx`
  login/register screen. `api.ts` injects the Bearer token + surfaces `err.status`.
- **Quota**: lifetime `FREE_LIMIT=3` free reels per account on the shared Emergent pool, tracked server-side
  (`users.free_used`). `enforce_quota`/`consume_quota` gate `POST /reels`, `/series/*/episode`, `/script`.
  Users with a saved BYOK key OR `is_subscribed` are unlimited (not counted). Batch requires own key/subscription.
  Frontend surfaces HTTP 402 as a quota banner (`testID quota-banner`) linking to Settings; Settings shows plan status.
- **Per-user BYOK (encrypted)**: keys moved from a global doc to the user doc, **AES-256-GCM encrypted at rest**
  (`openai_key_enc`,`google_key_enc`; AES key from env `AES_SECRET_B64`, JWT from `JWT_SECRET` — both appended to
  backend/.env). `enc_key`/`dec_key` (AAD = `uid:provider`). `GET/PUT /api/settings` now auth-scoped and return
  only masked values (`public_user`). `run_pipeline`/regen tasks call `apply_owner_keys()` to load the reel owner's
  keys into `pipeline.set_user_keys()` before generation. `classify_error` maps auth/401/403 → `key`.
- **Reels/Series/Outros scoped by `user_id`** (create sets it; list/get/delete filter by owner).
- Verified: testing agent iteration 10 — backend 10/10 (auth, quota 3→402, BYOK bypass, encryption-at-rest,
  masking, isolation), frontend 7/7 after fixing the Settings `refreshAuth()` staleness bug.
