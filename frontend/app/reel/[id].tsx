import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import * as FileSystem from "expo-file-system/legacy";
import { useLocalSearchParams, useRouter } from "expo-router";
import * as Sharing from "expo-sharing";
import { useCallback, useEffect, useRef, useState } from "react";
import { Platform, Pressable, StyleSheet, Text, View } from "react-native";
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
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const celebrated = useRef(false);

  const poll = useCallback(async () => {
    if (!id) return;
    try {
      const r = await api.getReel(id);
      setReel(r);
      if (r.status === "ready" && !celebrated.current) {
        celebrated.current = true;
        haptic.success();
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

  const exportReel = useCallback(async () => {
    if (!id) return;
    setExporting(true);
    try {
      const url = api.videoUrl(id);
      const dest = `${FileSystem.cacheDirectory}reel-${id}.mp4`;
      const { uri } = await FileSystem.downloadAsync(url, dest);
      haptic.medium();
      if (await Sharing.isAvailableAsync()) {
        await Sharing.shareAsync(uri, { mimeType: "video/mp4", dialogTitle: "Share your reel" });
      }
    } catch {
      haptic.error();
    } finally {
      setExporting(false);
    }
  }, [id]);

  const retry = useCallback(async () => {
    if (!reel) return;
    try {
      const fresh = await api.createReel({
        input_mode: reel.input_mode,
        topic: reel.topic || undefined,
        script: reel.script || undefined,
        seconds: reel.seconds,
        voice_id: reel.voice_id,
        caption_style: reel.caption_style,
        bg_theme: reel.bg_theme,
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
          <View style={[styles.actions, { paddingBottom: insets.bottom + spacing.md }]}>
            <Text style={styles.meta}>
              {reel?.duration ? `${reel.duration.toFixed(0)}s` : ""} · 1080×1920 · {reel?.word_count || 0} words
            </Text>
            <PrimaryButton
              testID="export-button"
              label={Platform.OS === "web" ? "Download MP4" : "Save / Share MP4"}
              icon="share-outline"
              loading={exporting}
              onPress={exportReel}
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
          <Text style={styles.stateSub}>{reel?.error || "Something went wrong while rendering."}</Text>
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
  meta: { fontFamily: font.bodyMed, fontSize: 12, color: colors.onSurfaceSecondary, textAlign: "center", marginBottom: spacing.md },
  failIcon: {
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: "rgba(239,68,68,0.14)",
    alignItems: "center",
    justifyContent: "center",
  },
});
