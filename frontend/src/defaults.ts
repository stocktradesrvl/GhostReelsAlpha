import { storage } from "@/src/utils/storage";

export type StudioDefaults = {
  voice_id?: string;
  seconds?: number;
  caption_style?: string;
  music_id?: string;
  watermark?: string;
};

const KEY = "studio_defaults";

export async function loadDefaults(): Promise<StudioDefaults> {
  const raw = await storage.getItem(KEY, "{}");
  try {
    const obj = JSON.parse((raw as string) || "{}");
    return obj && typeof obj === "object" ? obj : {};
  } catch {
    return {};
  }
}

export async function saveDefaults(d: StudioDefaults): Promise<void> {
  await storage.setItem(KEY, JSON.stringify(d));
}
