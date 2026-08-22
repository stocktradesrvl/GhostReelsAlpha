const BASE = `${process.env.EXPO_PUBLIC_BACKEND_URL}/api`;

export type Voice = { id: string; name: string; tagline: string };
export type VoiceSpeed = { id: string; name: string };
export type CaptionStyle = { id: string; name: string; hint: string; hex: string };
export type CaptionPosition = { id: string; name: string };
export type CaptionSize = { id: string; name: string };
export type CaptionFont = { id: string; name: string };
export type CaptionAnim = { id: string; name: string };
export type BgTheme = { id: string; name: string; preview: string[] };
export type BgMotion = { id: string; name: string };
export type MusicTrack = { id: string; name: string };
export type Config = {
  voices: Voice[];
  voice_speeds: VoiceSpeed[];
  caption_styles: CaptionStyle[];
  caption_positions: CaptionPosition[];
  caption_sizes: CaptionSize[];
  caption_fonts: CaptionFont[];
  caption_anims: CaptionAnim[];
  bg_themes: BgTheme[];
  bg_motions: BgMotion[];
  music_tracks: MusicTrack[];
};

export type ReelStatus =
  | "queued" | "scripting" | "voicing" | "captioning"
  | "rendering" | "uploading" | "ready" | "failed";

export type Reel = {
  id: string;
  title: string;
  input_mode: "topic" | "script";
  topic: string | null;
  script: string | null;
  seconds: number;
  voice_id: string;
  voice_speed: string;
  caption_style: string;
  caption_position: string;
  caption_size: string;
  caption_font: string;
  caption_anim: string;
  bg_theme: string;
  bg_motion: string;
  music_id: string;
  music_volume: number;
  watermark: string | null;
  hook_enabled: boolean;
  endcard_text: string | null;
  status: ReelStatus;
  progress: number;
  stage_label: string;
  error: string | null;
  duration: number | null;
  word_count: number | null;
  has_video: boolean;
  created_at: string;
  updated_at: string;
};

async function req<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options?.headers || {}) },
  });
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      msg = body.detail || msg;
    } catch {}
    throw new Error(msg);
  }
  return res.json() as Promise<T>;
}

export const api = {
  getConfig: () => req<Config>("/config"),
  generateScript: (topic: string, seconds: number) =>
    req<{ script: string; word_count: number }>("/script", {
      method: "POST",
      body: JSON.stringify({ topic, seconds }),
    }),
  createReel: (payload: Partial<Reel>) =>
    req<Reel>("/reels", { method: "POST", body: JSON.stringify(payload) }),
  createBatch: (payload: Record<string, any>) =>
    req<{ created: Reel[]; count: number }>("/reels/batch", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  listReels: () => req<Reel[]>("/reels"),
  getReel: (id: string) => req<Reel>(`/reels/${id}`),
  deleteReel: (id: string) => req<{ ok: boolean }>(`/reels/${id}`, { method: "DELETE" }),
  videoUrl: (id: string) => `${BASE}/reels/${id}/video`,
  thumbUrl: (id: string) => `${BASE}/reels/${id}/thumb`,
  voicePreviewUrl: (voiceId: string) => `${BASE}/voices/${voiceId}/preview`,
};
