import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import * as FileSystem from "expo-file-system/legacy";
import * as MediaLibrary from "expo-media-library";
import { useLocalSearchParams, useRouter } from "expo-router";
import * as Sharing from "expo-sharing";
import { useCallback, useEffect, useRef, useState } from "react";
import { Linking, Platform, Pressable, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Reel } from "@/src/api";
import PreviewPlayer from "@/src/components/PreviewPlayer";
import PrimaryButton from "@/src/components/PrimaryButton";
import StageProgress from "@/src/components/StageProgress";
import { haptic } from "@/src/haptics";
import { colors, font, radius, spacing } from "@/src/theme";

const BG_PREVIEW: Record<string, string[]> = {
  ember: ["#3B0A0A", "#1A0505", "#09090B"],
  midnight: ["#0B3B37", "#08201E", "#09090B"],
  sunset: ["#3B1B08", "#1E0F05", "#09090B"],
  mono: ["#26262B", "#161618", "#09090B"],
};

export default function ReelDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const insets = useSafeAreaInsets();
  const router = useRouter();

  const [reel, setReel] = useState<Reel | null>(null);
  const [notFound, setNotFound] = useState(false);
  const [exporting, setExporting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<string | null>(null);
  const [permBlocked, setPermBlocked] = useState(false);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const toastTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const celebrated = useRef(false);
  const viewed = useRef(false);

  const showToast = useCallback((msg: string) => {
    setToast(msg);
    if (toastTimer.current) clearTimeout(toastTimer.current);
    toastTimer.current = setTimeout(() => setToast(null), 2800);
  }, []);

  const poll = useCallback(async () => {
    if (!id) return;
    try {
      const r = await api.getReel(id);
      setReel(r);
      if (r.status === "ready" && !celebrated.current) {
        celebrated.current = true;
        haptic.success();
      }
      if (r.status === "ready" && !viewed.current) {
        viewed.current = true;
        api.addView(r.id).then((res) => setReel((cur) => (cur ? { ...cur, views: res.views } : cur))).catch(() => {});
      }
      if (r.status !== "ready" && r.status !== "failed") {
        timer.current = setTimeout(poll, 1500);
      }
    } catch {
      setNotFound(true);
    }
  }, [id]);

  useEffect(() => {
    poll();
    return () => {
      if (timer.current) clearTimeout(timer.current);
    };
  }, [poll]);

  const downloadToCache = useCallback(async () => {
    const url = api.videoUrl(id!);
    const dest = `${FileSystem.cacheDirectory}reel-${id}.mp4`;
    const { uri } = await FileSystem.downloadAsync(url, dest);
    return uri;
  }, [id]);

  const exportReel = useCallback(async () => {
    if (!id) return;
    setExporting(true);
    try {
      const uri = await downloadToCache();
      haptic.medium();
      if (await Sharing.isAvailableAsync()) {
        await Sharing.shareAsync(uri, { mimeType: "video/mp4", dialogTitle: "Share your reel" });
      } else {
        showToast("Sharing isn't available here.");
      }
      api.addDownload(id).then((r) => setReel((cur) => (cur ? { ...cur, downloads: r.downloads } : cur))).catch(() => {});
    } catch {
      haptic.error();
      showToast("Couldn't export. Try again.");
    } finally {
      setExporting(false);
    }
  }, [id, downloadToCache, showToast]);

  const saveToGallery = useCallback(async () => {
    if (!id) return;
    setSaving(true);
    try {
      let perm = await MediaLibrary.getPermissionsAsync(true);
      if (perm.status !== "granted" && perm.canAskAgain) {
        perm = await MediaLibrary.requestPermissionsAsync(true);
      }
      if (perm.status !== "granted") {
        haptic.error();
        if (!perm.canAskAgain) {
          setPermBlocked(true);
          showToast("Photos access is off — enable it in Settings.");
        } else {
          showToast("Photos permission was denied.");
        }
        return;
      }
      const uri = await downloadToCache();
      await MediaLibrary.saveToLibraryAsync(uri);
      haptic.success();
      showToast("Saved to your gallery ✓");
      api.addDownload(id).then((r) => setReel((cur) => (cur ? { ...cur, downloads: r.downloads } : cur))).catch(() => {});
    } catch {
      haptic.error();
      showToast("Couldn't save. Try Share instead.");
    } finally {
      setSaving(false);
    }
  }, [id, downloadToCache, showToast]);

  const retry = useCallback(async () => {
    if (!reel) return;
    try {
      const fresh = await api.createReel({
        input_mode: reel.input_mode,
        topic: reel.topic || undefined,
        script: reel.script || undefined,
        seconds: reel.seconds,
        visual_mode: reel.visual_mode,
        voice_id: reel.voice_id,
        voice_speed: reel.voice_speed,
        caption_style: reel.caption_style,
        caption_position: reel.caption_position,
        caption_size: reel.caption_size,
        caption_font: reel.caption_font,
        caption_anim: reel.caption_anim,
        bg_theme: reel.bg_theme,
        bg_motion: reel.bg_motion,
        custom_c1: reel.custom_c1 || undefined,
        custom_c2: reel.custom_c2 || undefined,
        music_id: reel.music_id,
        music_volume: reel.music_volume,
        watermark: reel.watermark || undefined,
        hook_enabled: reel.hook_enabled,
        endcard_text: reel.endcard_text || undefined,
      } as any);
      celebrated.current = false;
      router.replace(`/reel/${fresh.id}`);
    } catch {
      haptic.error();
    }
  }, [reel, router]);

  const removeReel = useCallback(async () => {
    if (!id) return;
    haptic.medium();
    await api.deleteReel(id);
    router.back();
  }, [id, router]);

  const duplicate = useCallback(() => {
    if (!id) return;
    haptic.light();
    router.push({ pathname: "/(tabs)", params: { dup: id } });
  }, [id, router]);

  const grad = BG_PREVIEW[reel?.bg_theme || "ember"] || BG_PREVIEW.ember;
  const isReady = reel?.status === "ready";
  const isFailed = reel?.status === "failed";
  const isWorking = reel && !isReady && !isFailed;

  return (
    <View style={styles.root}>
      <LinearGradient colors={grad as [string, string, ...string[]]} style={StyleSheet.absoluteFill} />

      {/* Header */}
      <View style={[styles.header, { paddingTop: insets.top + spacing.xs }]}>
        <Pressable testID="back-button" onPress={() => router.back()} style={styles.iconBtn}>
          <Ionicons name="chevron-back" size={22} color={colors.onSurface} />
        </Pressable>
        <Text style={styles.headerTitle} numberOfLines={1}>
          {reel?.title || "Reel"}
        </Text>
        {reel && (isReady || isFailed) ? (
          <Pressable testID="delete-button" onPress={removeReel} style={styles.iconBtn}>
            <Ionicons name="trash-outline" size={20} color={colors.onSurfaceSecondary} />
          </Pressable>
        ) : (
          <View style={styles.iconBtn} />
        )}
      </View>

      {notFound && (
        <View style={styles.center}>
          <Ionicons name="cloud-offline-outline" size={40} color={colors.onSurfaceSecondary} />
          <Text style={styles.stateTitle}>Reel not found</Text>
          <PrimaryButton label="Back to library" onPress={() => router.replace("/(tabs)/library")} style={{ marginTop: spacing.lg }} />
        </View>
      )}

      {isWorking && (
        <View style={styles.progressWrap}>
          <View style={styles.progressCard} testID="progress-card">
            <Text style={styles.buildingLabel}>BUILDING YOUR REEL</Text>
            <StageProgress status={reel!.status} progress={reel!.progress} />
            <Text style={styles.hint}>This usually takes under a minute. Keep the app open.</Text>
          </View>
        </View>
      )}

      {isReady && (
        <View style={styles.readyWrap}>
          <View style={styles.playerFrame} testID="reel-player">
            <PreviewPlayer uri={api.videoUrl(id!)} testID="video-view" />
          </View>
          {toast && (
            <View style={styles.toast} testID="save-toast">
              <Text style={styles.toastText}>{toast}</Text>
            </View>
          )}
          <View style={[styles.actions, { paddingBottom: insets.bottom + spacing.md }]}>
            <View style={styles.statsRow}>
              <Text style={styles.meta}>
                {reel?.duration ? `${reel.duration.toFixed(0)}s` : ""} · 1080×1920
              </Text>
              <View style={styles.statChip}>
                <Ionicons name="eye-outline" size={14} color={colors.onSurfaceSecondary} />
                <Text style={styles.statTxt} testID="views-count">{reel?.views ?? 0}</Text>
              </View>
              <View style={styles.statChip}>
                <Ionicons name="download-outline" size={14} color={colors.onSurfaceSecondary} />
                <Text style={styles.statTxt} testID="downloads-count">{reel?.downloads ?? 0}</Text>
              </View>
            </View>
            {Platform.OS === "web" ? (
              <PrimaryButton
                testID="export-button"
                label="Download MP4"
                icon="download-outline"
                loading={exporting}
                onPress={exportReel}
              />
            ) : (
              <>
                <PrimaryButton
                  testID="save-gallery-button"
                  label="Save to gallery"
                  icon="download-outline"
                  loading={saving}
                  onPress={saveToGallery}
                />
                <PrimaryButton
                  testID="export-button"
                  variant="ghost"
                  label="Share MP4"
                  icon="share-outline"
                  loading={exporting}
                  onPress={exportReel}
                  style={{ marginTop: spacing.sm }}
                />
                {permBlocked && (
                  <PrimaryButton
                    testID="open-settings-button"
                    variant="ghost"
                    label="Open Settings"
                    icon="settings-outline"
                    onPress={() => Linking.openSettings()}
                    style={{ marginTop: spacing.sm }}
                  />
                )}
              </>
            )}
            <PrimaryButton
              testID="duplicate-button"
              variant="ghost"
              label="Duplicate & edit"
              icon="copy-outline"
              onPress={duplicate}
              style={{ marginTop: spacing.sm }}
            />
            <PrimaryButton
              testID="new-reel-button"
              variant="ghost"
              label="Create another reel"
              icon="add"
              onPress={() => router.replace("/(tabs)")}
              style={{ marginTop: spacing.sm }}
            />
          </View>
        </View>
      )}

      {isFailed && (
        <View style={styles.center}>
          <View style={styles.failIcon}>
            <Ionicons name="alert" size={30} color={colors.error} />
          </View>
          <Text style={styles.stateTitle}>Generation failed</Text>
          <Text style={styles.stateSub}>
            {reel?.error && /budget/i.test(reel.error)
              ? "Your AI credits ran out. Top up your Universal Key (Profile → Manage plan → Universal Key → Add Balance), then tap Try again."
              : (reel?.error || "Something went wrong while rendering.")}
          </Text>
          <PrimaryButton testID="retry-button" label="Try again" icon="refresh" onPress={retry} style={{ marginTop: spacing.lg, alignSelf: "stretch" }} />
          <PrimaryButton variant="ghost" label="Back" onPress={() => router.back()} style={{ marginTop: spacing.sm, alignSelf: "stretch" }} />
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.md,
    paddingBottom: spacing.sm,
  },
  iconBtn: {
    width: 40,
    height: 40,
    borderRadius: radius.md,
    alignItems: "center",
    justifyContent: "center",
  },
  headerTitle: { flex: 1, textAlign: "center", fontFamily: font.bodyBold, fontSize: 15, color: colors.onSurface },
  center: { flex: 1, alignItems: "center", justifyContent: "center", padding: spacing.xl },
  stateTitle: { fontFamily: font.display, fontSize: 24, color: colors.onSurface, marginTop: spacing.md },
  stateSub: { fontFamily: font.body, fontSize: 14, color: colors.onSurfaceSecondary, textAlign: "center", marginTop: spacing.sm, lineHeight: 20 },
  progressWrap: { flex: 1, justifyContent: "center", padding: spacing.lg },
  progressCard: {
    backgroundColor: "rgba(9,9,11,0.72)",
    borderRadius: radius.xl,
    borderWidth: 1,
    borderColor: colors.border,
    padding: spacing.xl,
  },
  buildingLabel: { fontFamily: font.bodyBold, fontSize: 12, letterSpacing: 1.4, color: colors.brand, marginBottom: spacing.sm },
  hint: { fontFamily: font.body, fontSize: 13, color: colors.onSurfaceSecondary, marginTop: spacing.xl, lineHeight: 19 },
  readyWrap: { flex: 1 },
  playerFrame: { flex: 1, marginHorizontal: spacing.lg, borderRadius: radius.lg, overflow: "hidden", borderWidth: 1, borderColor: colors.border },
  actions: { padding: spacing.lg, paddingTop: spacing.md },
  toast: {
    position: "absolute",
    left: spacing.lg,
    right: spacing.lg,
    bottom: 210,
    backgroundColor: colors.surfaceTertiary,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    borderRadius: radius.md,
    paddingVertical: spacing.sm,
    paddingHorizontal: spacing.md,
    alignItems: "center",
  },
  toastText: { fontFamily: font.bodySemi, fontSize: 13, color: colors.onSurface },
  meta: { fontFamily: font.bodyMed, fontSize: 12, color: colors.onSurfaceSecondary, textAlign: "center", marginBottom: spacing.md },
  statsRow: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: spacing.md, marginBottom: spacing.md },
  statChip: { flexDirection: "row", alignItems: "center", gap: 4 },
  statTxt: { fontFamily: font.bodySemi, fontSize: 12, color: colors.onSurfaceSecondary },
  failIcon: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: "rgba(239,68,68,0.14)",
    alignItems: "center",
    justifyContent: "center",
  },
});
