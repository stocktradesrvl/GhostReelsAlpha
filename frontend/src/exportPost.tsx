import * as FileSystem from "expo-file-system/legacy";
import * as Sharing from "expo-sharing";
import { useCallback, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { api, Reel } from "@/src/api";
import PrimaryButton from "@/src/components/PrimaryButton";
import { haptic } from "@/src/haptics";
import { colors, font, radius, spacing } from "@/src/theme";

type Props = {
  id: string;
  reel: Reel;
  setReel: (r: Reel | ((cur: Reel | null) => Reel | null)) => void;
  showToast: (msg: string) => void;
};

export default function ExportAndPost({ id, reel, setReel, showToast }: Props) {
  const [exportAspect, setExportAspect] = useState<string | null>(null);
  const [posting, setPosting] = useState<"youtube" | "instagram" | null>(null);

  const downloadToCache = useCallback(async (aspect?: string) => {
    const url = api.videoUrl(id, aspect && aspect !== "9:16" ? { aspect } : undefined);
    const suffix = aspect && aspect !== "9:16" ? `-${aspect.replace(":", "x")}` : "";
    const dest = `${FileSystem.cacheDirectory}reel-${id}${suffix}.mp4`;
    const { uri } = await FileSystem.downloadAsync(url, dest, { headers: api.authHeaders() as any });
    return uri;
  }, [id]);

  const exportSize = useCallback(async (aspect: string) => {
    if (aspect === "9:16") {
      try {
        const uri = await downloadToCache();
        haptic.medium();
        if (await Sharing.isAvailableAsync()) {
          await Sharing.shareAsync(uri, { mimeType: "video/mp4", dialogTitle: "Share 9:16" });
        } else {
          showToast("Download started.");
        }
        api.addDownload(id).then((r) => setReel((cur) => (cur ? { ...cur, downloads: r.downloads } : cur))).catch(() => {});
      } catch {
        haptic.error();
        showToast("Couldn't export. Try again.");
      }
      return;
    }
    setExportAspect(aspect);
    try {
      let r = await api.exportAspect(id, aspect);
      setReel(r);
      const t0 = Date.now();
      while ((r.exports?.[aspect]?.status === "queued" || r.exports?.[aspect]?.status === "rendering") && Date.now() - t0 < 180000) {
        await new Promise((res) => setTimeout(res, 1500));
        r = await api.getReel(id);
        setReel(r);
      }
      if (r.exports?.[aspect]?.status !== "ready") {
        haptic.error();
        showToast(r.exports?.[aspect]?.error || "Couldn't make that size.");
        return;
      }
      const uri = await downloadToCache(aspect);
      haptic.success();
      if (await Sharing.isAvailableAsync()) {
        await Sharing.shareAsync(uri, { mimeType: "video/mp4", dialogTitle: `Share ${aspect}` });
      } else {
        showToast(`${aspect} ready ✓`);
      }
      api.addDownload(id).then((res) => setReel((cur) => (cur ? { ...cur, downloads: res.downloads } : cur))).catch(() => {});
    } catch (e: any) {
      haptic.error();
      showToast(e?.message || "Couldn't export that size.");
    } finally {
      setExportAspect(null);
    }
  }, [id, downloadToCache, setReel, showToast]);

  const postTo = useCallback(async (platform: "youtube" | "instagram") => {
    setPosting(platform);
    try {
      const res = await api.postReel(id, platform, { title: reel?.title || undefined, caption: reel?.script || undefined });
      haptic.success();
      if (res.mock) showToast(`Posted to ${platform} (test mode) ✓`);
      else showToast(res.url ? `Posted ✓  ${res.url}` : `Posted to ${platform} ✓`);
    } catch (e: any) {
      haptic.error();
      showToast(e?.message || `Couldn't post to ${platform}.`);
    } finally {
      setPosting(null);
    }
  }, [id, reel, showToast]);

  return (
    <>
      <Text style={styles.miniLabel}>EXPORT SIZE</Text>
      <View style={styles.aspectRow} testID="aspect-row">
        {[
          { id: "9:16", label: "9:16", hint: "Reels" },
          { id: "1:1", label: "1:1", hint: "Feed" },
          { id: "16:9", label: "16:9", hint: "YT" },
        ].map((a) => {
          const st = reel?.exports?.[a.id]?.status;
          const busy = exportAspect === a.id;
          return (
            <Pressable key={a.id} testID={`aspect-${a.id}`} onPress={() => exportSize(a.id)} style={styles.aspectChip}>
              <Text style={styles.aspectChipTxt}>{busy ? "…" : a.label}</Text>
              <Text style={styles.aspectHint}>{st === "ready" && a.id !== "9:16" ? "Ready" : a.hint}</Text>
            </Pressable>
          );
        })}
      </View>
      <PrimaryButton
        testID="post-youtube-button"
        variant="ghost"
        label="Post to YouTube"
        icon="logo-youtube"
        loading={posting === "youtube"}
        onPress={() => postTo("youtube")}
        style={{ marginTop: spacing.sm }}
      />
      <PrimaryButton
        testID="post-instagram-button"
        variant="ghost"
        label="Post to Instagram"
        icon="logo-instagram"
        loading={posting === "instagram"}
        onPress={() => postTo("instagram")}
        style={{ marginTop: spacing.sm }}
      />
    </>
  );
}

const styles = StyleSheet.create({
  miniLabel: { fontFamily: font.bodyBold, fontSize: 11, letterSpacing: 1, color: colors.onSurfaceSecondary, marginBottom: spacing.sm, textAlign: "center" },
  aspectRow: { flexDirection: "row", gap: spacing.sm, marginBottom: spacing.md },
  aspectChip: {
    flex: 1, height: 52, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border,
    backgroundColor: colors.surfaceSecondary, alignItems: "center", justifyContent: "center",
  },
  aspectChipTxt: { fontFamily: font.bodyBold, fontSize: 15, color: colors.onSurface },
  aspectHint: { fontFamily: font.body, fontSize: 11, color: colors.onSurfaceSecondary, marginTop: 2 },
});
