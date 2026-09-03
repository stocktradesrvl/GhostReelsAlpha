import { BottomSheetModal } from "@gorhom/bottom-sheet";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Pressable, StyleSheet, Switch, Text, TextInput, View } from "react-native";
import { KeyboardAwareScrollView, KeyboardStickyView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Config, voiceSheetOption } from "@/src/api";
import OptionSheet, { SheetOption } from "@/src/components/OptionSheet";
import PrimaryButton from "@/src/components/PrimaryButton";
import Segmented from "@/src/components/Segmented";
import AiImageControls from "@/src/components/AiImageControls";
import { haptic } from "@/src/haptics";
import { colors, font, radius, spacing } from "@/src/theme";

const DURATIONS = [15, 30, 60];

export default function BatchScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();

  const [config, setConfig] = useState<Config | null>(null);
  const [topicsText, setTopicsText] = useState("");
  const [seconds, setSeconds] = useState(30);
  const [visualMode, setVisualMode] = useState<"gradient" | "ai">("gradient");
  const [imageStyle, setImageStyle] = useState("cinematic");
  const [imageCount, setImageCount] = useState<number | null>(null);
  const [imageDirection, setImageDirection] = useState("");
  const [voiceId, setVoiceId] = useState("onyx");
  const [captionFont, setCaptionFont] = useState("barlow");
  const [bgTheme, setBgTheme] = useState("ember");
  const [musicId, setMusicId] = useState("none");
  const [hookEnabled, setHookEnabled] = useState(true);
  const [whenMode, setWhenMode] = useState<"now" | "tonight">("now");
  const [drafts, setDrafts] = useState<{ topic: string; script: string }[]>([]);
  const [drafting, setDrafting] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const voiceSheet = useRef<BottomSheetModal>(null);
  const bgSheet = useRef<BottomSheetModal>(null);
  const musicSheet = useRef<BottomSheetModal>(null);

  useEffect(() => {
    api.getConfig().then((c) => {
      setConfig(c);
      if (c.voices[0]) setVoiceId(c.voices[0].id);
      if (c.bg_themes[0]) setBgTheme(c.bg_themes[0].id);
    }).catch(() => setError("Couldn't load options."));
  }, []);

  const topics = useMemo(
    () => topicsText.split("\n").map((t) => t.trim()).filter(Boolean),
    [topicsText],
  );

  // Editing topics or length invalidates any drafted scripts.
  useEffect(() => { setDrafts([]); }, [topicsText, seconds]);

  const writeScripts = useCallback(async () => {
    if (topics.length === 0) { setError("Add at least one topic."); return; }
    if (topics.length > 12) { setError("Up to 12 topics per batch."); return; }
    setError(null);
    setDrafting(true);
    try {
      const res = await api.batchScripts(topics, seconds);
      setDrafts(res.scripts.map((s) => ({ topic: s.topic, script: s.script })));
      haptic.medium();
    } catch (e: any) {
      setError(e.message || "Couldn't draft the scripts.");
      haptic.error();
    } finally {
      setDrafting(false);
    }
  }, [topics, seconds]);

  const editDraft = useCallback((i: number, text: string) => {
    setDrafts((prev) => prev.map((d, idx) => (idx === i ? { ...d, script: text } : d)));
  }, []);

  const voice = config?.voices.find((v) => v.id === voiceId);
  const bg = config?.bg_themes.find((b) => b.id === bgTheme);
  const music = config?.music_tracks.find((m) => m.id === musicId);

  const voiceOptions: SheetOption[] = config?.voices.map(voiceSheetOption) || [];
  const bgOptions: SheetOption[] = config?.bg_themes.map((b) => ({ id: b.id, title: b.name, swatch: b.preview })) || [];
  const musicOptions: SheetOption[] = config?.music_tracks.map((m) => ({ id: m.id, title: m.name })) || [];

  const generate = useCallback(async () => {
    if (topics.length === 0) { setError("Add at least one topic."); return; }
    if (topics.length > 12) { setError("Up to 12 topics per batch."); return; }
    setError(null);
    setSubmitting(true);
    try {
      let scheduled_at: string | undefined;
      if (whenMode === "tonight") {
        const d = new Date();
        d.setHours(2, 0, 0, 0);
        if (d.getTime() <= Date.now()) d.setDate(d.getDate() + 1);
        scheduled_at = d.toISOString();
      }
      const res = await api.createBatch({
        topics, seconds, voice_id: voiceId, caption_font: captionFont,
        caption_anim: "pop", bg_theme: bgTheme, bg_motion: "dynamic",
        music_id: musicId, hook_enabled: hookEnabled, scheduled_at,
        visual_mode: visualMode, image_style: imageStyle,
        image_count: visualMode === "ai" ? (imageCount ?? undefined) : undefined,
        image_direction: visualMode === "ai" ? (imageDirection.trim() || undefined) : undefined,
        scripts: drafts.length ? drafts : undefined,
      });
      haptic.heavy();
      router.replace("/(tabs)/library");
      return res;
    } catch (e: any) {
      setError(e.message || "Couldn't start the batch.");
      haptic.error();
    } finally {
      setSubmitting(false);
    }
  }, [topics, seconds, visualMode, imageStyle, imageCount, imageDirection, voiceId, captionFont, bgTheme, musicId, hookEnabled, whenMode, drafts, router]);

  return (
    <View style={styles.root}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.xs }]}>
        <Pressable testID="batch-back" onPress={() => router.back()} style={styles.iconBtn}>
          <Ionicons name="chevron-back" size={22} color={colors.onSurface} />
        </Pressable>
        <Text style={styles.headerTitle}>Batch Create</Text>
        <View style={styles.iconBtn} />
      </View>

      <KeyboardAwareScrollView
        bottomOffset={90}
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: 140 }}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
      >
        <Text style={styles.lead}>One topic per line — each becomes its own reel (up to 12).</Text>

        <View style={styles.scriptHead}>
          <Text style={styles.section}>TOPICS</Text>
          <Text style={styles.count}>{topics.length} / 12</Text>
        </View>
        <TextInput
          testID="batch-topics-input"
          value={topicsText}
          onChangeText={setTopicsText}
          placeholder={"5 morning habits of successful people\nWhy the ocean is blue\n3 quick pasta recipes"}
          placeholderTextColor={colors.onSurfaceSecondary}
          multiline
          style={[styles.input, { minHeight: 160 }]}
        />

        <Text style={styles.section}>VISUAL STYLE</Text>
        <Segmented
          testID="batch-visual-mode"
          options={[{ id: "gradient", label: "GRADIENT" }, { id: "ai", label: "AI IMAGES" }]}
          value={visualMode}
          onChange={(v) => setVisualMode(v as "gradient" | "ai")}
        />
        {visualMode === "ai" && (
          <AiImageControls
            testPrefix="batch"
            styles={config?.image_styles || []}
            imageStyle={imageStyle}
            onStyle={setImageStyle}
            imageCount={imageCount}
            onCount={setImageCount}
            direction={imageDirection}
            onDirection={setImageDirection}
          />
        )}

        <Text style={styles.section}>LENGTH</Text>
        <View style={styles.chipRow}>
          {DURATIONS.map((d) => {
            const active = d === seconds;
            return (
              <Pressable key={d} testID={`batch-duration-${d}`} onPress={() => { haptic.light(); setSeconds(d); }} style={[styles.chip, active && styles.chipActive]}>
                <Text style={[styles.chipText, active && styles.chipTextActive]}>{d}s</Text>
              </Pressable>
            );
          })}
        </View>

        <Text style={styles.section}>SHARED SETTINGS</Text>
        <View style={styles.settings}>
          <Row testID="batch-voice" icon="mic" label="Voice" value={voice?.name || "—"} onPress={() => voiceSheet.current?.present()} />
          <Row testID="batch-bg" icon="color-palette" label="Background" value={bg?.name || "—"} onPress={() => bgSheet.current?.present()} />
          <Row testID="batch-music" icon="musical-notes" label="Music" value={music?.name || "—"} onPress={() => musicSheet.current?.present()} />
        </View>

        <Text style={styles.section}>CAPTION FONT</Text>
        <View style={styles.chipRow}>
          {(config?.caption_fonts || []).map((f) => {
            const active = f.id === captionFont;
            return (
              <Pressable key={f.id} testID={`batch-font-${f.id}`} onPress={() => { haptic.light(); setCaptionFont(f.id); }} style={[styles.chip, active && styles.chipActive]}>
                <Text style={[styles.chipText, active && styles.chipTextActive]}>{f.name}</Text>
              </Pressable>
            );
          })}
        </View>

        <View style={styles.toggleRow}>
          <View style={styles.toggleLeft}>
            <Ionicons name="flash-outline" size={18} color={colors.onSurfaceSecondary} />
            <Text style={styles.settingLabel}>Auto hook title on every reel</Text>
          </View>
          <Switch testID="batch-hook-toggle" value={hookEnabled} onValueChange={(v) => { haptic.light(); setHookEnabled(v); }} trackColor={{ false: colors.surfaceTertiary, true: colors.brandPrimary }} thumbColor="#fff" />
        </View>

        <Text style={styles.section}>WHEN</Text>
        <View style={styles.chipRow}>
          {[{ id: "now", name: "Generate now" }, { id: "tonight", name: "Tonight · 2 AM" }].map((o) => {
            const active = o.id === whenMode;
            return (
              <Pressable key={o.id} testID={`batch-when-${o.id}`} onPress={() => { haptic.light(); setWhenMode(o.id as any); }} style={[styles.chip, active && styles.chipActive]}>
                <Text style={[styles.chipText, active && styles.chipTextActive]}>{o.name}</Text>
              </Pressable>
            );
          })}
        </View>

        {drafts.length > 0 && (
          <>
            <View style={styles.scriptHead}>
              <Text style={styles.section}>REVIEW SCRIPTS</Text>
              <Text style={styles.count}>{drafts.length} draft{drafts.length === 1 ? "" : "s"}</Text>
            </View>
            <Text style={styles.lead}>Edit any script below before building. Blank scripts fall back to AI.</Text>
            {drafts.map((d, i) => (
              <View key={i} style={styles.draftCard}>
                <Text style={styles.draftTopic} numberOfLines={1}>{i + 1}. {d.topic}</Text>
                <TextInput
                  testID={`batch-script-input-${i}`}
                  value={d.script}
                  onChangeText={(t) => editDraft(i, t)}
                  multiline
                  style={[styles.input, { minHeight: 110, marginTop: spacing.sm }]}
                />
              </View>
            ))}
          </>
        )}

        {!!error && (
          <View style={styles.errorBox} testID="batch-error">
            <Ionicons name="warning" size={16} color={colors.error} />
            <Text style={styles.errorText}>{error}</Text>
          </View>
        )}
      </KeyboardAwareScrollView>

      <KeyboardStickyView offset={{ closed: 0, opened: insets.bottom }}>
        <View style={[styles.ctaWrap, { paddingBottom: insets.bottom + spacing.sm }]}>
          {drafts.length === 0 ? (
            <PrimaryButton
              testID="batch-write-scripts-button"
              label={topics.length > 1 ? `Write ${topics.length} scripts` : "Write script"}
              icon="sparkles"
              disabled={topics.length === 0}
              loading={drafting}
              onPress={writeScripts}
            />
          ) : (
            <PrimaryButton
              testID="batch-generate-button"
              label={whenMode === "tonight" ? `Schedule ${topics.length || 0} reel${topics.length === 1 ? "" : "s"}` : (topics.length > 1 ? `Generate ${topics.length} reels` : "Generate reel")}
              icon="layers"
              disabled={topics.length === 0}
              loading={submitting}
              onPress={generate}
            />
          )}
        </View>
      </KeyboardStickyView>

      <OptionSheet ref={voiceSheet} title="Pick a voice" options={voiceOptions} selectedId={voiceId} onSelect={(id) => { setVoiceId(id); voiceSheet.current?.dismiss(); }} />
      <OptionSheet ref={bgSheet} title="Background theme" options={bgOptions} selectedId={bgTheme} onSelect={(id) => { setBgTheme(id); bgSheet.current?.dismiss(); }} />
      <OptionSheet ref={musicSheet} title="Background music" options={musicOptions} selectedId={musicId} onSelect={(id) => { setMusicId(id); musicSheet.current?.dismiss(); }} />
    </View>
  );
}

function Row({ icon, label, value, onPress, testID }: { icon: keyof typeof Ionicons.glyphMap; label: string; value: string; onPress: () => void; testID?: string }) {
  return (
    <Pressable testID={testID} onPress={() => { haptic.select(); onPress(); }} style={({ pressed }) => [styles.settingRow, pressed && { backgroundColor: colors.surfaceTertiary }]}>
      <View style={styles.toggleLeft}>
        <Ionicons name={icon} size={18} color={colors.onSurfaceSecondary} />
        <Text style={styles.settingLabel}>{label}</Text>
      </View>
      <View style={styles.settingRight}>
        <Text style={styles.settingValue}>{value}</Text>
        <Ionicons name="chevron-forward" size={16} color={colors.onSurfaceSecondary} />
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: spacing.md, paddingBottom: spacing.sm, borderBottomWidth: 1, borderBottomColor: colors.border },
  iconBtn: { width: 40, height: 40, borderRadius: radius.md, alignItems: "center", justifyContent: "center" },
  headerTitle: { flex: 1, textAlign: "center", fontFamily: font.display, fontSize: 22, color: colors.onSurface, letterSpacing: 0.5 },
  lead: { fontFamily: font.body, fontSize: 13, color: colors.onSurfaceSecondary, lineHeight: 19 },
  section: { fontFamily: font.bodyBold, fontSize: 11, letterSpacing: 1.2, color: colors.onSurfaceSecondary, marginTop: spacing.lg, marginBottom: spacing.sm },
  scriptHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  count: { fontFamily: font.bodyMed, fontSize: 11, color: colors.onSurfaceSecondary, marginTop: spacing.lg },
  input: { backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: spacing.md, fontFamily: font.body, fontSize: 15, color: colors.onSurface, textAlignVertical: "top" },
  draftCard: { marginTop: spacing.md, backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, padding: spacing.md },
  draftTopic: { fontFamily: font.bodyBold, fontSize: 13, color: colors.brand },
  chipRow: { flexDirection: "row", gap: spacing.sm },
  chip: { flex: 1, height: 44, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surfaceSecondary, alignItems: "center", justifyContent: "center" },
  chipActive: { borderColor: colors.brand, backgroundColor: colors.brandTertiary },
  chipText: { fontFamily: font.bodySemi, fontSize: 14, color: colors.onSurfaceSecondary },
  chipTextActive: { color: colors.onBrandTertiary },
  settings: { borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surfaceSecondary, overflow: "hidden" },
  settingRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: spacing.md, height: 54, borderBottomWidth: 1, borderBottomColor: colors.divider },
  toggleLeft: { flexDirection: "row", alignItems: "center", gap: spacing.sm, flex: 1 },
  settingLabel: { fontFamily: font.bodySemi, fontSize: 15, color: colors.onSurface },
  settingRight: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  settingValue: { fontFamily: font.bodyMed, fontSize: 14, color: colors.onSurfaceSecondary },
  toggleRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: spacing.lg, padding: spacing.md, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surfaceSecondary },
  errorBox: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginTop: spacing.lg, padding: spacing.md, borderRadius: radius.md, backgroundColor: "rgba(239,68,68,0.12)", borderWidth: 1, borderColor: "rgba(239,68,68,0.3)" },
  errorText: { flex: 1, fontFamily: font.bodyMed, fontSize: 13, color: colors.brandSecondary },
  ctaWrap: { paddingHorizontal: spacing.lg, paddingTop: spacing.sm, backgroundColor: colors.surface, borderTopWidth: 1, borderTopColor: colors.border },
});
