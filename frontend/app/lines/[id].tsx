import { Ionicons } from "@expo/vector-icons";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api } from "@/src/api";
import PrimaryButton from "@/src/components/PrimaryButton";
import { haptic } from "@/src/haptics";
import { colors, font, radius, spacing } from "@/src/theme";

type Line = { index: number; text: string };

export default function NarrationEditor() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const insets = useSafeAreaInsets();
  const router = useRouter();

  const [lines, setLines] = useState<Line[]>([]);
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [status, setStatus] = useState("ready");
  const [editable, setEditable] = useState(true);
  const [busyIndex, setBusyIndex] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async () => {
    if (!id) return;
    try {
      const data = await api.getLines(id);
      setLines(data.lines);
      setEditable(data.editable);
      setStatus(data.status);
      setDrafts((cur) => {
        const next = { ...cur };
        data.lines.forEach((l) => { if (next[l.index] === undefined) next[l.index] = l.text; });
        return next;
      });
      if (data.status === "ready" || data.status === "failed") setBusyIndex(null);
    } catch {
      setError("Couldn't load narration.");
    }
  }, [id]);

  useEffect(() => { load(); return () => { if (timer.current) clearTimeout(timer.current); }; }, [load]);

  const poll = useCallback(async () => {
    if (!id) return;
    const r = await api.getReel(id).catch(() => null);
    if (r) {
      setStatus(r.status);
      if (r.status === "ready" || r.status === "failed") {
        if (r.status === "failed") setError(r.error || "Re-record failed.");
        await load();
        haptic.success();
        return;
      }
    }
    timer.current = setTimeout(poll, 1800);
  }, [id, load]);

  const rerecord = useCallback(async (index: number) => {
    if (!id || busyIndex !== null) return;
    const text = (drafts[index] ?? "").trim();
    if (!text) { setError("Line can't be empty."); return; }
    setError(null);
    setBusyIndex(index);
    setStatus("voicing");
    haptic.medium();
    try {
      await api.regenerateLine(id, index, text);
      poll();
    } catch (e: any) {
      setError(e.message || "Couldn't re-record that line.");
      setBusyIndex(null);
      haptic.error();
    }
  }, [id, busyIndex, drafts, poll]);

  const working = status !== "ready" && status !== "failed";

  return (
    <View style={styles.root}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.xs }]}>
        <Pressable testID="lines-back" onPress={() => router.back()} style={styles.iconBtn}>
          <Ionicons name="chevron-back" size={22} color={colors.onSurface} />
        </Pressable>
        <Text style={styles.headerTitle}>Edit narration</Text>
        <View style={styles.iconBtn} />
      </View>

      <KeyboardAwareScrollView
        bottomOffset={90}
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + spacing.xxl }}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
      >
        <Text style={styles.lead}>
          Edit one line and re-record just that sentence — the rest of your voiceover stays exactly the same.
        </Text>

        {working && (
          <View style={styles.workingBar} testID="lines-working">
            <ActivityIndicator color={colors.brand} />
            <Text style={styles.workingTxt}>Re-recording & re-rendering…</Text>
          </View>
        )}

        {!editable && !working && (
          <Text style={styles.notEditable}>This reel was made before line editing — regenerate it once to enable this.</Text>
        )}

        {lines.map((l) => {
          const changed = (drafts[l.index] ?? l.text).trim() !== l.text.trim();
          return (
            <View key={l.index} style={styles.card} testID={`line-card-${l.index}`}>
              <View style={styles.lineHead}>
                <Text style={styles.lineNum}>Line {l.index + 1}</Text>
                {changed && <View style={styles.editedDot}><Text style={styles.editedTxt}>edited</Text></View>}
              </View>
              <TextInput
                testID={`line-text-${l.index}`}
                value={drafts[l.index] ?? l.text}
                onChangeText={(v) => setDrafts((cur) => ({ ...cur, [l.index]: v }))}
                multiline
                placeholder="Narration line"
                placeholderTextColor={colors.onSurfaceSecondary}
                style={styles.input}
              />
              <PrimaryButton
                testID={`line-regen-${l.index}`}
                variant="ghost"
                icon="mic"
                label="Re-record this line"
                loading={busyIndex === l.index}
                disabled={working || !editable}
                onPress={() => rerecord(l.index)}
                style={{ marginTop: spacing.sm }}
              />
            </View>
          );
        })}

        {!!error && (
          <View style={styles.errorBox} testID="lines-error">
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
  notEditable: { fontFamily: font.body, fontSize: 13, color: colors.onSurfaceSecondary, marginBottom: spacing.md },
  card: { backgroundColor: colors.surfaceSecondary, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.border, padding: spacing.md, marginBottom: spacing.md },
  lineHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: spacing.xs },
  lineNum: { fontFamily: font.bodyBold, fontSize: 12, letterSpacing: 1, color: colors.onSurfaceSecondary },
  editedDot: { paddingHorizontal: spacing.sm, height: 20, borderRadius: radius.pill, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center" },
  editedTxt: { fontFamily: font.bodyBold, fontSize: 10, color: colors.onBrandTertiary },
  input: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: spacing.md, fontFamily: font.body, fontSize: 15, color: colors.onSurface, textAlignVertical: "top", minHeight: 60 },
  errorBox: { flexDirection: "row", alignItems: "center", gap: spacing.sm, padding: spacing.md, borderRadius: radius.md, backgroundColor: "rgba(239,68,68,0.12)", borderWidth: 1, borderColor: "rgba(239,68,68,0.3)" },
  errorText: { flex: 1, fontFamily: font.bodyMed, fontSize: 13, color: colors.brandSecondary },
});
