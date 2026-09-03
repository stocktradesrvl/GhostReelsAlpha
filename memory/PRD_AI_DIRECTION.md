## Follow-up (2026-09 · AI picture direction) — DONE

- **Image count (AI mode):** user picks how many pictures (2–12). Default is still auto from
  length (`scene_count`: ~1 per 10s, 2–4). Persisted as `image_count` on the reel (and series
  settings / batch). `generate_scene_prompts` and Ken Burns split use that n when set. Invalid
  values clamp to 2–12. More images = more Gemini calls — that's OK.
- **Visual direction / mood:** free-text `image_direction` (e.g. "terrifying", "hopeful golden-hour",
  "found footage night vision"). Appended to every scene prompt and the image-generation suffix.
  Empty = previous cinematic lighting behavior. Kept on per-scene redo (style + mood).
- **More styles** in `IMAGE_STYLES`: cartoon, comic book (`comic`), noir, illustrated, 3D render,
  on top of cinematic / photoreal / anime / painterly. `/api/config` lists them plus
  `image_count_min` / `image_count_max`.
- **UI:** Create, Series new, and Batch show count + mood only when visual mode is AI Images
  (`AiImageControls`). Duplicate-reel prefill copies the new fields. Scene editor shows the
  reel's style + mood; regenerate keeps them.
- Boot hook `visual_dir.py` + `visual_boot.py` (imported from `storage_client`) — no wholesale
  rewrite of `server.py`. Auth / quota / RevenueCat from the lock PR unchanged. No new paid APIs.
- Tests: `backend/tests/test_image_direction.py` (REELS_MOCK, no LLM spend).
