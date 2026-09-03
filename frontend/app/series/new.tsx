import { BottomSheetModal } from "@gorhom/bottom-sheet";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { KeyboardAwareScrollView, KeyboardStickyView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Character, Config, Outro, voiceSheetOption } from "@/src/api";
import OptionSheet, { SheetOption } from "@/src/components/OptionSheet";
import OutroSheet from "@/src/components/OutroSheet";
import PrimaryButton from "@/src/components/PrimaryButton";
import Segmented from "@/src/components/Segmented";
import AiImageControls from "@/src/components/AiImageControls";
import { haptic } from "@/src/haptics";
import { colors, font, radius, spacing } from "@/src/theme";

const DURATIONS = [15, 30, 60];

export default function NewSeriesScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();

  const [config, setConfig] = useState<Config | null>(null);
  const [title, setTitle] = useState("");
  const [premise, setPremise] = useState("");
  const [tone, setTone] = useState("");
  const [visualMode, setVisualMode] = useState<"gradient" | "ai">("ai");
  const [imageStyle, setImageStyle] = useState("cinematic");
  const [imageCount, setImageCount] = useState<number | null>(null);
  const [imageDirection, setImageDirection] = useState("");
  const [voiceId, setVoiceId] = useState("onyx");
  const [seconds, setSeconds] = useState(30);
  const [outro, setOutro] = useState<Outro | null>(null);
  const [characters, setCharacters] = useState<Character[]>([{ name: "", description: "" }]);
  const [suggesting, setSuggesting] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const voiceSheet = useRef<BottomSheetModal>(null);
  const outroSheet = useRef<BottomSheetModal>(null);

  useEffect(() => {
    api.getConfig().then((c) => {
      setConfig(c);
      if (c.voices[0]) setVoiceId(c.voices[0].id);
    }).catch(() => setError("Couldn't load options."));
  }, []);

  const voice = config?.voices.find((v) => v.id === voiceId);
  const voiceOptions: SheetOption[] = config?.voices.map(voiceSheetOption) || [];

  const setChar = (i: number, key: keyof Character, val: string) =>
    setCharacters((cur) => cur.map((c, idx) => (idx === i ? { ...c, [key]: val } : c)));
  const addChar = () => { haptic.light(); setCharacters((cur) => [...cur, { name: "", description: "" }]); };
  const removeChar = (i: number) => { haptic.light(); setCharacters((cur) => cur.filter((_, idx) => idx !== i)); };

  const suggest = useCallback(async () => {
    if (!premise.trim()) { setError("Add a premise so AI can design characters."); return; }
    setError(null);
    setSuggesting(true);
    try {
      const res = await api.suggestCharacters(premise.trim(), tone.trim());
      if (res.characters.length) { setCharacters(res.characters); haptic.success(); }
      else setError("AI couldn't suggest characters. Try a richer premise.");
    } catch (e: any) {
      setError(e.message || "Couldn't suggest characters.");
      haptic.error();
    } finally {
      setSuggesting(false);
    }
  }, [premise, tone]);

  const create = useCallback(async () => {
    if (!title.trim()) { setError("Give your series a title."); return; }
    setError(null);
    setSubmitting(true);
    try {
      const cleaned = characters
        .map((c) => ({ name: c.name.trim(), description: c.description.trim() }))
        .filter((c) => c.name || c.description);
      const s = await api.createSeries({
        title: title.trim(),
        premise: premise.trim(),
        tone: tone.trim(),
        characters: cleaned,
        visual_mode: visualMode,
        image_style: imageStyle,
        image_count: visualMode === "ai" ? (imageCount ?? undefined) : undefined,
        image_direction: visualMode === "ai" ? (imageDirection.trim() || undefined) : undefined,
        voice_id: voiceId,
        seconds,
        outro_id: outro?.id || undefined,
      });
      haptic.heavy();
      router.replace(`/series/${s.id}`);
    } catch (e: any) {
      setError(e.message || "Couldn't create the series.");
      haptic.error();
    } finally {
      setSubmitting(false);
    }
  }, [title, premise, tone, characters, visualMode, imageStyle, imageCount, imageDirection, voiceId, seconds, outro, router]);

  return (
    <View style={styles.root}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.xs }]}>
        <Pressable testID="series-new-back" onPress={() => router.back()} style={styles.iconBtn}>
          <Ionicons name="chevron-back" size={22} color={colors.onSurface} />
        </Pressable>
        <Text style={styles.headerTitle}>New Series</Text>
        <View style={styles.iconBtn} />
      </View>

      <KeyboardAwareScrollView
        bottomOffset={90}
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: 140 }}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
      >
        <Text style={styles.section}>SERIES TITLE</Text>
        <TextInput
          testID="series-title-input"
          value={title}
          onChangeText={setTitle}
          placeholder="e.g. The Exorcist Files"
          placeholderTextColor={colors.onSurfaceSecondary}
          maxLength={80}
          style={[styles.input, { height: 48, paddingVertical: 0 }]}
        />

        <Text style={styles.section}>PREMISE · THE OVERALL STORY</Text>
        <TextInput
          testID="series-premise-input"
          value={premise}
          onChangeText={setPremise}
          placeholder="A rogue priest hunts demons through a decaying city, one case at a time."
          placeholderTextColor={colors.onSurfaceSecondary}
          multiline
          style={[styles.input, { minHeight: 96 }]}
        />

        <Text style={styles.section}>TONE · OPTIONAL</Text>
        <TextInput
          testID="series-tone-input"
          value={tone}
          onChangeText={setTone}
          placeholder="suspenseful horror, cinematic"
          placeholderTextColor={colors.onSurfaceSecondary}
          maxLength={120}
          style={[styles.input, { height: 48, paddingVertical: 0 }]}
        />

        <View style={styles.charsHead}>
          <Text style={styles.section}>CHARACTERS · STAY CONSISTENT</Text>
          <Pressable testID="suggest-characters-button" onPress={suggest} disabled={suggesting} style={styles.suggestPill}>
            <Ionicons name="sparkles" size={13} color={colors.brand} />
            <Text style={styles.suggestTxt}>{suggesting ? "Thinking…" : "AI suggest"}</Text>
          </Pressable>
        </View>
        <Text style={styles.helper}>Describe main characters (look, clothing, vibe) so AI draws them the same every episode.</Text>

        {characters.map((c, i) => (
          <View key={i} style={styles.charCard} testID={`character-row-${i}`}>
            <View style={styles.charTop}>
              <TextInput
                testID={`character-name-${i}`}
                value={c.name}
                onChangeText={(v) => setChar(i, "name", v)}
                placeholder="Name"
                placeholderTextColor={colors.onSurfaceSecondary}
                maxLength={48}
                style={styles.charName}
              />
              {characters.length > 1 && (
                <Pressable testID={`character-remove-${i}`} onPress={() => removeChar(i)} style={styles.charRemove}>
                  <Ionicons name="close" size={16} color={colors.onSurfaceSecondary} />
                </Pressable>
              )}
            </View>
            <TextInput
              testID={`character-desc-${i}`}
              value={c.description}
              onChangeText={(v) => setChar(i, "description", v)}
              placeholder="Appearance & defining features"
              placeholderTextColor={colors.onSurfaceSecondary}
              multiline
              maxLength={240}
              style={styles.charDesc}
            />
          </View>
        ))}
        <PrimaryButton
          testID="add-character-button"
          variant="ghost"
          icon="person-add-outline"
          label="Add character"
          onPress={addChar}
          style={{ marginTop: spacing.sm }}
        />

        <Text style={styles.section}>VISUAL STYLE</Text>
        <Segmented
          testID="series-visual-mode"
          options={[{ id: "gradient", label: "GRADIENT" }, { id: "ai", label: "AI IMAGES" }]}
          value={visualMode}
          onChange={(v) => setVisualMode(v as "gradient" | "ai")}
        />
        {visualMode === "ai" && (
          <Text style={styles.helper}>AI images keep your characters consistent across episodes (uses a few extra credits per reel).</Text>
        )}
        {visualMode === "ai" && (
          <AiImageControls
            testPrefix="series"
            styles={config?.image_styles || []}
            imageStyle={imageStyle}
            onStyle={setImageStyle}
            imageCount={imageCount}
            onCount={setImageCount}
            direction={imageDirection}
            onDirection={setImageDirection}
          />
        )}

        <Text style={styles.section}>EPISODE LENGTH</Text>
        <View style={styles.chipRow}>
          {DURATIONS.map((d) => {
            const active = d === seconds;
            return (
              <Pressable key={d} testID={`series-duration-${d}`} onPress={() => { haptic.light(); setSeconds(d); }} style={[styles.chip, active && styles.chipActive]}>
                <Text style={[styles.chipText, active && styles.chipTextActive]}>{d}s</Text>
              </Pressable>
            );
          })}
        </View>

        <Text style={styles.section}>VOICE</Text>
        <Pressable testID="series-voice-row" onPress={() => { haptic.select(); voiceSheet.current?.present(); }} style={styles.settingRow}>
          <View style={styles.settingLeft}>
            <Ionicons name="mic" size={18} color={colors.onSurfaceSecondary} />
            <Text style={styles.settingLabel}>Narrator</Text>
          </View>
          <View style={styles.settingRight}>
            <Text style={styles.settingValue}>{voice?.name || "—"}</Text>
            <Ionicons name="chevron-forward" size={16} color={colors.onSurfaceSecondary} />
          </View>
        </Pressable>

        <Text style={styles.section}>OUTRO CLIP · APPLIED TO EVERY EPISODE</Text>
        <Pressable testID="series-outro-row" onPress={() => { haptic.select(); outroSheet.current?.present(); }} style={styles.settingRow}>
          <View style={styles.settingLeft}>
            <Ionicons name="play-forward" size={18} color={colors.onSurfaceSecondary} />
            <Text style={styles.settingLabel}>Outro</Text>
          </View>
          <View style={styles.settingRight}>
            <Text style={styles.settingValue}>{outro ? outro.name : "None"}</Text>
            <Ionicons name="chevron-forward" size={16} color={colors.onSurfaceSecondary} />
          </View>
        </Pressable>

        {!!error && (
          <View style={styles.errorBox} testID="series-new-error">
            <Ionicons name="warning" size={16} color={colors.error} />
            <Text style={styles.errorText}>{error}</Text>
          </View>
        )}
      </KeyboardAwareScrollView>

      <KeyboardStickyView offset={{ closed: 0, opened: insets.bottom }}>
        <View style={[styles.ctaWrap, { paddingBottom: insets.bottom + spacing.sm }]}>
          <PrimaryButton
            testID="create-series-button"
            label="Create series"
            icon="film"
            disabled={!title.trim()}
            loading={submitting}
            onPress={create}
          />
        </View>
      </KeyboardStickyView>

      <OptionSheet ref={voiceSheet} title="Pick a voice" options={voiceOptions} selectedId={voiceId} onSelect={(id) => { setVoiceId(id); voiceSheet.current?.dismiss(); }} />
      <OutroSheet ref={outroSheet} selectedId={outro?.id || null} onSelect={(o) => { setOutro(o); outroSheet.current?.dismiss(); }} />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: spacing.md, paddingBottom: spacing.sm, borderBottomWidth: 1, borderBottomColor: colors.border },
  iconBtn: { width: 40, height: 40, borderRadius: radius.md, alignItems: "center", justifyContent: "center" },
  headerTitle: { flex: 1, textAlign: "center", fontFamily: font.display, fontSize: 22, color: colors.onSurface, letterSpacing: 0.5 },
  section: { fontFamily: font.bodyBold, fontSize: 11, letterSpacing: 1.2, color: colors.onSurfaceSecondary, marginTop: spacing.lg, marginBottom: spacing.sm },
  helper: { fontFamily: font.body, fontSize: 12, color: colors.onSurfaceSecondary, lineHeight: 17, marginBottom: spacing.sm },
  input: { backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: spacing.md, fontFamily: font.body, fontSize: 15, color: colors.onSurface, textAlignVertical: "top" },
  charsHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  suggestPill: { flexDirection: "row", alignItems: "center", gap: 5, marginTop: spacing.lg, paddingHorizontal: spacing.md, height: 30, borderRadius: radius.pill, borderWidth: 1, borderColor: colors.brandPrimary, backgroundColor: colors.brandTertiary },
  suggestTxt: { fontFamily: font.bodySemi, fontSize: 12, color: colors.onBrandTertiary },
  charCard: { backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: spacing.md, marginBottom: spacing.sm },
  charTop: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  charName: { flex: 1, fontFamily: font.bodyBold, fontSize: 15, color: colors.onSurface, paddingVertical: spacing.xs },
  charRemove: { width: 28, height: 28, borderRadius: 14, backgroundColor: colors.surfaceTertiary, alignItems: "center", justifyContent: "center" },
  charDesc: { fontFamily: font.body, fontSize: 14, color: colors.onSurfaceTertiary, marginTop: spacing.xs, textAlignVertical: "top", minHeight: 44 },
  chipRow: { flexDirection: "row", gap: spacing.sm, flexWrap: "wrap" },
  chip: { minWidth: 72, flexGrow: 1, height: 44, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surfaceSecondary, alignItems: "center", justifyContent: "center", paddingHorizontal: spacing.md },
  chipActive: { borderColor: colors.brand, backgroundColor: colors.brandTertiary },
  chipText: { fontFamily: font.bodySemi, fontSize: 14, color: colors.onSurfaceSecondary },
  chipTextActive: { color: colors.onBrandTertiary },
  settingRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: spacing.md, height: 54, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surfaceSecondary },
  settingLeft: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  settingLabel: { fontFamily: font.bodySemi, fontSize: 15, color: colors.onSurface },
  settingRight: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  settingValue: { fontFamily: font.bodyMed, fontSize: 14, color: colors.onSurfaceSecondary },
  errorBox: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginTop: spacing.lg, padding: spacing.md, borderRadius: radius.md, backgroundColor: "rgba(239,68,68,0.12)", borderWidth: 1, borderColor: "rgba(239,68,68,0.3)" },
  errorText: { flex: 1, fontFamily: font.bodyMed, fontSize: 13, color: colors.brandSecondary },
  ctaWrap: { paddingHorizontal: spacing.lg, paddingTop: spacing.sm, backgroundColor: colors.surface, borderTopWidth: 1, borderTopColor: colors.border },
});
