const BASE = `${process.env.EXPO_PUBLIC_BACKEND_URL}/api`;

export const PRIVACY_POLICY_URL = `${BASE}/legal/privacy`;
export const SUPPORT_EMAIL = "russngina@gmail.com";

export type Voice = { id: string; name: string; tagline: string };
export type VoiceSpeed = { id: string; name: string };
export type ImageStyle = { id: string; name: string };
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
  image_styles: ImageStyle[];
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
  | "rendering" | "uploading" | "ready" | "failed" | "scheduled";

export type Reel = {
  id: string;
  title: string;
  input_mode: "topic" | "script";
  topic: string | null;
  script: string | null;
  series_id: string | null;
  episode_number: number | null;
  seconds: number;
  visual_mode: string;
  image_style: string;
  voice_id: string;
  voice_speed: string;
  caption_style: string;
  caption_position: string;
  caption_size: string;
  caption_font: string;
  caption_anim: string;
  bg_theme: string;
  bg_motion: string;
  custom_c1: string | null;
  custom_c2: string | null;
  music_id: string;
  music_volume: number;
  watermark: string | null;
  hook_enabled: boolean;
  endcard_text: string | null;
  outro_id: string | null;
  views: number;
  downloads: number;
  scheduled_at: string | null;
  status: ReelStatus;
  progress: number;
  stage_label: string;
  error: string | null;
  error_code: string | null;
  duration: number | null;
  word_count: number | null;
  has_video: boolean;
  created_at: string;
  updated_at: string;
};

export type Character = { name: string; description: string };
export type Outro = { id: string; name: string; size: number; created_at: string };
export type AppSettings = {
  openai_key_set: boolean;
  openai_key_masked: string;
  google_key_set: boolean;
  google_key_masked: string;
  brand_handle: string;
};
export type Series = {
  id: string;
  title: string;
  premise: string;
  tone: string;
  characters: Character[];
  settings: Record<string, any>;
  episode_count: number;
  created_at: string;
  updated_at: string;
};

let authToken: string | null = null;
export function setAuthToken(t: string | null) { authToken = t; }

export type UserProfile = {
  id: string; email: string;
  free_used: number; free_limit: number; is_subscribed: boolean;
  has_own_key: boolean; openai_key_set: boolean; google_key_set: boolean;
  openai_key_masked: string; google_key_masked: string; brand_handle: string;
};

async function req<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(authToken ? { Authorization: `Bearer ${authToken}` } : {}),
      ...(options?.headers || {}),
    },
  });
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      msg = body.detail || msg;
    } catch {}
    const err: any = new Error(msg);
    err.status = res.status;
    throw err;
  }
  return res.json() as Promise<T>;
}

export const api = {
  register: (email: string, password: string) =>
    req<{ access_token: string; user: UserProfile }>("/auth/register", { method: "POST", body: JSON.stringify({ email, password }) }),
  login: (email: string, password: string) =>
    req<{ access_token: string; user: UserProfile }>("/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  me: () => req<UserProfile>("/auth/me"),
  deleteAccount: () => req<{ ok: boolean }>("/auth/me", { method: "DELETE" }),
  syncSubscription: (is_subscribed: boolean) =>
    req<UserProfile>("/subscription/sync", { method: "POST", body: JSON.stringify({ is_subscribed }) }),
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
  addView: (id: string) => req<{ views: number }>(`/reels/${id}/view`, { method: "POST" }),
  addDownload: (id: string) => req<{ downloads: number }>(`/reels/${id}/download`, { method: "POST" }),
  listSeries: () => req<Series[]>("/series"),
  getSeries: (id: string) => req<{ series: Series; episodes: Reel[] }>(`/series/${id}`),
  createSeries: (payload: Record<string, any>) =>
    req<Series>("/series", { method: "POST", body: JSON.stringify(payload) }),
  suggestCharacters: (premise: string, tone: string) =>
    req<{ characters: Character[] }>("/series/suggest", {
      method: "POST",
      body: JSON.stringify({ premise, tone }),
    }),
  createEpisode: (id: string, topic?: string) =>
    req<Reel>(`/series/${id}/episode`, {
      method: "POST",
      body: JSON.stringify({ topic: topic || null }),
    }),
  deleteSeries: (id: string) => req<{ ok: boolean }>(`/series/${id}`, { method: "DELETE" }),
  getScenes: (id: string) =>
    req<{ editable: boolean; status: string; scenes: { index: number; prompt: string; image_url: string }[] }>(
      `/reels/${id}/scenes`,
    ),
  regenerateScene: (id: string, index: number, prompt?: string) =>
    req<Reel>(`/reels/${id}/scene/${index}/regenerate`, {
      method: "POST",
      body: JSON.stringify({ prompt: prompt || null }),
    }),
  sceneImageUrl: (id: string, index: number) => `${BASE}/reels/${id}/scene/${index}/image`,
  getSettings: () => req<AppSettings>("/settings"),
  updateSettings: (payload: { openai_key?: string; google_key?: string; brand_handle?: string }) =>
    req<AppSettings>("/settings", { method: "PUT", body: JSON.stringify(payload) }),
  testKeys: (payload: { openai_key?: string; google_key?: string }) =>
    req<{ openai?: { ok: boolean; message: string }; google?: { ok: boolean; message: string } }>(
      "/settings/test", { method: "POST", body: JSON.stringify(payload) },
    ),
  getLines: (id: string) =>
    req<{ editable: boolean; status: string; lines: { index: number; text: string }[] }>(
      `/reels/${id}/lines`,
    ),
  regenerateLine: (id: string, index: number, text: string) =>
    req<Reel>(`/reels/${id}/line/${index}/regenerate`, {
      method: "POST",
      body: JSON.stringify({ text }),
    }),
  listOutros: () => req<Outro[]>("/outros"),
  deleteOutro: (id: string) => req<{ ok: boolean }>(`/outros/${id}`, { method: "DELETE" }),
  outroVideoUrl: (id: string) => `${BASE}/outros/${id}/video`,
  uploadOutro: async (uri: string, name: string): Promise<Outro> => {
    const form = new FormData();
    form.append("file", { uri, name: name || "outro.mp4", type: "video/mp4" } as any);
    form.append("name", name || "Outro clip");
    const res = await fetch(`${BASE}/outros`, {
      method: "POST",
      headers: authToken ? { Authorization: `Bearer ${authToken}` } : undefined,
      body: form,
    });
    if (!res.ok) {
      let msg = "Upload failed";
      try { msg = (await res.json()).detail || msg; } catch {}
      throw new Error(msg);
    }
    return res.json() as Promise<Outro>;
  },
  videoUrl: (id: string) => `${BASE}/reels/${id}/video`,
  thumbUrl: (id: string) => `${BASE}/reels/${id}/thumb`,
  voicePreviewUrl: (voiceId: string) => `${BASE}/voices/${voiceId}/preview`,
};
