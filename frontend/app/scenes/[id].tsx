import { Ionicons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import PrimaryButton from "@/src/components/PrimaryButton";
import { haptic } from "@/src/haptics";
import { colors, font, radius, spacing } from "@/src/theme";

type Scene = { index: number; prompt: string; image_url: string };

export default function ScenesEditor() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const insets = useSafeAreaInsets();
  const router = useRouter();

  const [scenes, setScenes] = useState<Scene[]>([]);
  const [prompts, setPrompts] = useState<Record<number, string>>({});
  const [status, setStatus] = useState<string>("ready");
  const [editable, setEditable] = useState(true);
  const [busyIndex, setBusyIndex] = useState<number | null>(null);
  const [bust, setBust] = useState(Date.now());
  const [error, setError] = useState<string | null>(null);
  const [direction, setDirection] = useState("");
  const [imageStyle, setImageStyle] = useState("");
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    try {
      const data = await api.getScenes(id);
      setScenes(data.scenes);
      setEditable(data.editable);
      setStatus(data.status);
      if (data.image_direction) setDirection(data.image_direction);
      if (data.image_style) setImageStyle(data.image_style);
      setPrompts((cur) => {
        const next = { ...cur };
        data.scenes.forEach((s) => { if (next[s.index] === undefined) next[s.index] = s.prompt; });
        return next;
      });
      if (data.status === "ready" || data.status === "failed") {
        setBusyIndex(null);
        setBust(Date.now());
      }
    } catch {
      setError("Couldn't load scenes.");
    }
  }, [id]);

  useEffect(() => { load(); return () => { if (timer.current) clearTimeout(timer.current); }; }, [load]);

  const poll = useCallback(async () => {
    if (!id) return;
    const r = await api.getReel(id).catch(() => null);
    if (r) {
      setStatus(r.status);
      if (r.status === "ready" || r.status === "failed") {
        if (r.status === "failed") setError(r.error || "Re-render failed.");
        await load();
        haptic.success();
        return;
      }
    }
    timer.current = setTimeout(poll, 1800);
  }, [id, load]);

  const regenerate = useCallback(async (index: number) => {
    if (!id || busyIndex !== null) return;
    setError(null);
    setBusyIndex(index);
    setStatus("rendering");
    haptic.medium();
    try {
      await api.regenerateScene(id, index, prompts[index]);
      poll();
    } catch (e: any) {
      setError(e.message || "Couldn't regenerate that scene.");
      setBusyIndex(null);
      haptic.error();
    }
  }, [id, busyIndex, prompts, poll]);

  const working = status !== "ready" && status !== "failed";

  return (
    <View style={styles.root}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.xs }]}>
        <Pressable testID="scenes-back" onPress={() => router.back()} style={styles.iconBtn}>
          <Ionicons name="chevron-back" size={22} color={colors.onSurface} />
        </Pressable>
        <Text style={styles.headerTitle}>Edit scenes</Text>
        <View style={styles.iconBtn} />
      </View>

      <KeyboardAwareScrollView
        bottomOffset={90}
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + spacing.xxl }}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
      >
        <Text style={styles.lead}>
          Tweak a scene's prompt and regenerate just that visual — your voice and captions stay exactly the same. Style and mood from this reel are kept.
        </Text>
        {!!(direction || imageStyle) && (
          <Text style={styles.dirNote} testID="scenes-direction">
            {[imageStyle && `Style: ${imageStyle}`, direction && `Mood: ${direction}`].filter(Boolean).join(" · ")}
          </Text>
        )}

        {working && (
          <View style={styles.workingBar} testID="scenes-working">
            <ActivityIndicator color={colors.brand} />
            <Text style={styles.workingTxt}>Repainting & re-rendering…</Text>
          </View>
        )}

        {!editable && !working && (
          <Text style={styles.notEditable}>This reel uses gradient backgrounds, so there are no AI scenes to edit.</Text>
        )}

        {scenes.map((s) => (
          <View key={s.index} style={styles.card} testID={`scene-card-${s.index}`}>
            <View style={styles.imgWrap}>
              <Image
                source={{ uri: api.sceneImageUrl(id!, s.index, { t: String(bust) }) }}
                style={StyleSheet.absoluteFill}
                contentFit="cover"
                cachePolicy="none"
              />
              <View style={styles.sceneBadge}><Text style={styles.sceneBadgeTxt}>Scene {s.index + 1}</Text></View>
              {busyIndex === s.index && (
                <View style={styles.imgOverlay}><ActivityIndicator color="#fff" /></View>
              )}
            </View>
            <TextInput
              testID={`scene-prompt-${s.index}`}
              value={prompts[s.index] ?? s.prompt}
              onChangeText={(v) => setPrompts((cur) => ({ ...cur, [s.index]: v }))}
              multiline
              placeholder="Describe this scene"
              placeholderTextColor={colors.onSurfaceSecondary}
              style={styles.prompt}
            />
            <PrimaryButton
              testID={`scene-regen-${s.index}`}
              variant="ghost"
              icon="refresh"
              label="Regenerate this scene"
              loading={busyIndex === s.index}
              disabled={working || !editable}
              onPress={() => regenerate(s.index)}
              style={{ marginTop: spacing.sm }}
            />
          </View>
        ))}

        {!!error && (
          <View style={styles.errorBox} testID="scenes-error">
            <Ionicons name="warning" size={16} color={colors.error} />
            <Text style={styles.errorText}>{error}</Text>
          </View>
        )}
      </KeyboardAwareScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: spacing.md, paddingBottom: spacing.sm, borderBottomWidth: 1, borderBottomColor: colors.border },
  iconBtn: { width: 40, height: 40, borderRadius: radius.md, alignItems: "center", justifyContent: "center" },
  headerTitle: { flex: 1, textAlign: "center", fontFamily: font.display, fontSize: 22, color: colors.onSurface, letterSpacing: 0.5 },
  lead: { fontFamily: font.body, fontSize: 13, color: colors.onSurfaceSecondary, lineHeight: 19, marginBottom: spacing.md },
  workingBar: { flexDirection: "row", alignItems: "center", gap: spacing.sm, padding: spacing.md, borderRadius: radius.md, backgroundColor: colors.brandTertiary, borderWidth: 1, borderColor: colors.brandPrimary, marginBottom: spacing.md },
  workingTxt: { fontFamily: font.bodySemi, fontSize: 13, color: colors.onBrandTertiary },
  dirNote: { fontFamily: font.bodyMed, fontSize: 12, color: colors.brandSecondary, marginBottom: spacing.md },
  notEditable: { fontFamily: font.body, fontSize: 13, color: colors.onSurfaceSecondary, marginBottom: spacing.md },
  card: { backgroundColor: colors.surfaceSecondary, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.border, padding: spacing.md, marginBottom: spacing.lg },
  imgWrap: { width: "100%", aspectRatio: 9 / 16, maxHeight: 320, borderRadius: radius.md, overflow: "hidden", backgroundColor: colors.surfaceTertiary, alignSelf: "center" },
  sceneBadge: { position: "absolute", top: spacing.sm, left: spacing.sm, paddingHorizontal: spacing.sm, height: 24, borderRadius: radius.pill, backgroundColor: "rgba(9,9,11,0.75)", alignItems: "center", justifyContent: "center" },
  sceneBadgeTxt: { fontFamily: font.bodyBold, fontSize: 11, color: colors.onSurface },
  imgOverlay: { ...StyleSheet.absoluteFillObject, backgroundColor: "rgba(9,9,11,0.55)", alignItems: "center", justifyContent: "center" },
  prompt: { marginTop: spacing.md, backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: spacing.md, fontFamily: font.body, fontSize: 14, color: colors.onSurface, textAlignVertical: "top", minHeight: 60 },
  errorBox: { flexDirection: "row", alignItems: "center", gap: spacing.sm, padding: spacing.md, borderRadius: radius.md, backgroundColor: "rgba(239,68,68,0.12)", borderWidth: 1, borderColor: "rgba(239,68,68,0.3)" },
  errorText: { flex: 1, fontFamily: font.bodyMed, fontSize: 13, color: colors.brandSecondary },
});
