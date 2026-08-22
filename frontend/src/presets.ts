import { storage } from "@/src/utils/storage";

export type Preset = { name: string; settings: Record<string, any> };

const KEY = "reel_presets";

export async function loadPresets(): Promise<Preset[]> {
  const raw = await storage.getItem(KEY, "[]");
  try {
    const list = JSON.parse((raw as string) || "[]");
    return Array.isArray(list) ? list : [];
  } catch {
    return [];
  }
}

export async function savePresets(list: Preset[]): Promise<void> {
  await storage.setItem(KEY, JSON.stringify(list));
}
