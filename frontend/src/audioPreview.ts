import { createAudioPlayer, setAudioModeAsync, type AudioPlayer } from "expo-audio";

let player: AudioPlayer | null = null;
let inited = false;

async function ensureMode() {
  if (inited) return;
  inited = true;
  try {
    await setAudioModeAsync({ playsInSilentMode: true, allowsRecording: false });
  } catch {}
}

export async function playPreview(url: string) {
  await ensureMode();
  try {
    if (!player) player = createAudioPlayer({ uri: url });
    else player.replace({ uri: url });
    player.seekTo(0);
    player.play();
  } catch {}
}

export function stopPreview() {
  try {
    player?.pause();
  } catch {}
}

export function releasePreview() {
  try {
    player?.remove();
  } catch {}
  player = null;
}
