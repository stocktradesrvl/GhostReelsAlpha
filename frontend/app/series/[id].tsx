import { Ionicons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import { useCallback, useState } from "react";
import { Alert, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Reel, Series } from "@/src/api";
import PrimaryButton from "@/src/components/PrimaryButton";
import { haptic } from "@/src/haptics";
import { colors, font, radius, spacing } from "@/src/theme";

const STATUS_LABEL: Record<string, string> = {
  ready: "Ready", failed: "Failed", queued: "Queued", scheduled: "Scheduled",
  scripting: "Writing", voicing: "Voicing", captioning: "Captions",
  rendering: "Rendering", uploading: "Finishing",
};

export default function SeriesDetail() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const insets = useSafeAreaInsets();
  const router = useRouter();

  const [series, setSeries] = useState<Series | null>(null);
  const [episodes, setEpisodes] = useState<Reel[]>([]);
  const [topic, setTopic] = useState("");
  const [script, setScript] = useState("");
  const [drafting, setDrafting] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (retry = true) => {
    if (!id) return;
    try {
      const data = await api.getSeries(id);
      setSeries(data.series);
      setEpisodes(data.episodes);
      setError(null);
    } catch {
      // Cold-navigate can race with auth hydration → retry once silently before surfacing.
      if (retry) {
        setTimeout(() => load(false), 700);
        return;
      }
      setError("Couldn't load this series.");
    }
  }, [id]);

  useFocusEffect(useCallback(() => {
    load();
    const anyWorking = episodes.some((e) => e.status !== "ready" && e.status !== "failed");
    const t = anyWorking ? setInterval(load, 2500) : null;
    return () => { if (t) clearInterval(t); };
  }, [load, episodes.length, episodes.map((e) => e.status).join(",")]));

  const writeScript = useCallback(async () => {
    if (!id) return;
    setError(null);
    setDrafting(true);
    try {
      const res = await api.episodeScript(id, topic.trim() || undefined);
      setScript(res.script);
      haptic.medium();
    } catch (e: any) {
      setError(e.message || "Couldn't draft the episode script.");
      haptic.error();
    } finally {
      setDrafting(false);
    }
  }, [id, topic]);

  const createEpisode = useCallback(async () => {
    if (!id || !script.trim()) return;
    setError(null);
    setCreating(true);
    try {
      const reel = await api.createEpisode(id, topic.trim() || undefined, script.trim());
      setTopic("");
      setScript("");
      haptic.heavy();
      router.push(`/reel/${reel.id}`);
    } catch (e: any) {
      setError(e.message || "Couldn't create the episode.");
      haptic.error();
    } finally {
      setCreating(false);
    }
  }, [id, topic, script, router]);

  const confirmDelete = useCallback(() => {
    Alert.alert("Delete series?", "This removes the series. Existing reels stay in your library.", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Delete", style: "destructive", onPress: async () => {
          if (!id) return;
          await api.deleteSeries(id);
          haptic.medium();
          router.back();
        },
      },
    ]);
  }, [id, router]);

  const nextEp = (series?.episode_count ?? 0) + 1;

  return (
    <View style={styles.root}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.xs }]}>
        <Pressable testID="series-detail-back" onPress={() => router.back()} style={styles.iconBtn}>
          <Ionicons name="chevron-back" size={22} color={colors.onSurface} />
        </Pressable>
        <Text style={styles.headerTitle} numberOfLines={1}>{series?.title || "Series"}</Text>
        <Pressable testID="series-delete" onPress={confirmDelete} style={styles.iconBtn}>
          <Ionicons name="trash-outline" size={20} color={colors.onSurfaceSecondary} />
        </Pressable>
      </View>

      <KeyboardAwareScrollView
        bottomOffset={90}
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + spacing.xxl }}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
      >
        {!!series?.premise && (
          <View style={styles.premiseCard}>
            <Text style={styles.premiseLabel}>PREMISE</Text>
            <Text style={styles.premiseText}>{series.premise}</Text>
            {!!series.tone && <Text style={styles.toneText}>Tone · {series.tone}</Text>}
          </View>
        )}

        {!!series?.characters?.length && (
          <>
            <Text style={styles.section}>CHARACTERS</Text>
            {series.characters.map((c, i) => (
              <View key={i} style={styles.charCard}>
                <Ionicons name="person-circle-outline" size={22} color={colors.brand} />
                <View style={{ flex: 1 }}>
                  {!!c.name && <Text style={styles.charName}>{c.name}</Text>}
                  {!!c.description && <Text style={styles.charDesc}>{c.description}</Text>}
                </View>
              </View>
            ))}
          </>
        )}

        <View style={styles.nextCard}>
          <Text style={styles.nextLabel}>CREATE EPISODE {nextEp}</Text>
          <Text style={styles.nextHint}>
            Leave blank to let AI continue the storyline, or give this episode a beat. Draft the
            script, review &amp; edit it, then build.
          </Text>
          <TextInput
            testID="episode-topic-input"
            value={topic}
            onChangeText={setTopic}
            placeholder="e.g. The priest confronts a possessed child"
            placeholderTextColor={colors.onSurfaceSecondary}
            multiline
            style={styles.input}
          />
          <Pressable
            testID="episode-write-script-button"
            onPress={() => { haptic.select(); writeScript(); }}
            disabled={drafting}
            style={({ pressed }) => [styles.draftBtn, pressed && { opacity: 0.85 }, drafting && { opacity: 0.6 }]}
          >
            <Ionicons name={drafting ? "hourglass-outline" : "sparkles"} size={16} color={colors.brand} />
            <Text style={styles.draftBtnTxt}>
              {drafting ? "Writing…" : script ? `Rewrite episode ${nextEp} script` : `Write episode ${nextEp} script`}
            </Text>
          </Pressable>

          {!!script && (
            <>
              <View style={styles.scriptHead}>
                <Text style={styles.scriptLabel}>EPISODE SCRIPT · REVIEW &amp; EDIT</Text>
                <Text style={styles.wordCount}>{script.trim().split(/\s+/).filter(Boolean).length} words</Text>
              </View>
              <TextInput
                testID="episode-script-input"
                value={script}
                onChangeText={setScript}
                multiline
                style={[styles.input, { minHeight: 130, marginTop: spacing.xs }]}
              />
            </>
          )}

          <PrimaryButton
            testID="create-episode-button"
            label={`Generate episode ${nextEp}`}
            icon="add-circle-outline"
            loading={creating}
            disabled={!script.trim()}
            onPress={createEpisode}
            style={{ marginTop: spacing.md }}
          />
          {!script.trim() && (
            <Text style={styles.buildHint}>Write &amp; review the script first, then build the episode.</Text>
          )}
          {!!error && (
            <View style={styles.errorBox}>
              <Ionicons name="warning" size={16} color={colors.error} />
              <Text style={styles.errorText}>{error}</Text>
            </View>
          )}
        </View>

        <Text style={styles.section}>EPISODES</Text>
        {episodes.length === 0 ? (
          <Text style={styles.emptyEp}>No episodes yet. Create your first one above.</Text>
        ) : (
          episodes.map((e) => (
            <Pressable
              key={e.id}
              testID={`episode-row-${e.episode_number}`}
              onPress={() => { haptic.select(); router.push(`/reel/${e.id}`); }}
              style={({ pressed }) => [styles.epRow, pressed && { backgroundColor: colors.surfaceTertiary }]}
            >
              <View style={styles.epThumb}>
                {e.status === "ready" ? (
                  <Image source={{ uri: api.thumbUrl(e.id) }} style={StyleSheet.absoluteFill} contentFit="cover" />
                ) : (
                  <Ionicons name="film-outline" size={20} color={colors.onSurfaceSecondary} />
                )}
                <View style={styles.epNumBadge}><Text style={styles.epNumTxt}>{e.episode_number}</Text></View>
              </View>
              <View style={{ flex: 1 }}>
                <Text style={styles.epTitle} numberOfLines={1}>Episode {e.episode_number}</Text>
                <Text style={styles.epSub} numberOfLines={1}>{e.topic || "AI continuation"}</Text>
              </View>
              <View style={[styles.epStatus, e.status === "ready" && styles.epStatusReady, e.status === "failed" && styles.epStatusFailed]}>
                <Text style={[styles.epStatusTxt, e.status === "ready" && { color: colors.success }, e.status === "failed" && { color: colors.error }]}>
                  {STATUS_LABEL[e.status] || e.status}
                </Text>
              </View>
            </Pressable>
          ))
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
  premiseCard: { backgroundColor: colors.surfaceSecondary, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.border, padding: spacing.lg },
  premiseLabel: { fontFamily: font.bodyBold, fontSize: 11, letterSpacing: 1.2, color: colors.brand, marginBottom: spacing.xs },
  premiseText: { fontFamily: font.body, fontSize: 14, color: colors.onSurfaceTertiary, lineHeight: 20 },
  toneText: { fontFamily: font.bodyMed, fontSize: 12, color: colors.onSurfaceSecondary, marginTop: spacing.sm },
  section: { fontFamily: font.bodyBold, fontSize: 11, letterSpacing: 1.2, color: colors.onSurfaceSecondary, marginTop: spacing.xl, marginBottom: spacing.sm },
  charCard: { flexDirection: "row", alignItems: "center", gap: spacing.sm, backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, padding: spacing.md, marginBottom: spacing.sm },
  charName: { fontFamily: font.bodyBold, fontSize: 14, color: colors.onSurface },
  charDesc: { fontFamily: font.body, fontSize: 12, color: colors.onSurfaceSecondary, marginTop: 2, lineHeight: 17 },
  nextCard: { marginTop: spacing.xl, backgroundColor: colors.brandTertiary, borderRadius: radius.lg, borderWidth: 1, borderColor: colors.brandPrimary, padding: spacing.lg },
  nextLabel: { fontFamily: font.display, fontSize: 18, color: colors.onBrandTertiary, letterSpacing: 0.5 },
  nextHint: { fontFamily: font.body, fontSize: 12, color: colors.brandSecondary, marginTop: spacing.xs, marginBottom: spacing.md, lineHeight: 17 },
  input: { backgroundColor: colors.surface, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, padding: spacing.md, fontFamily: font.body, fontSize: 15, color: colors.onSurface, textAlignVertical: "top", minHeight: 60 },
  draftBtn: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: spacing.sm, marginTop: spacing.md, height: 46, borderRadius: radius.md, borderWidth: 1, borderColor: colors.brand, backgroundColor: colors.surface },
  draftBtnTxt: { fontFamily: font.bodyBold, fontSize: 14, color: colors.brand },
  scriptHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: spacing.md },
  scriptLabel: { fontFamily: font.bodyBold, fontSize: 10, letterSpacing: 1, color: colors.brandSecondary },
  wordCount: { fontFamily: font.bodyMed, fontSize: 11, color: colors.brandSecondary },
  buildHint: { fontFamily: font.body, fontSize: 12, color: colors.brandSecondary, textAlign: "center", marginTop: spacing.sm },
  errorBox: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginTop: spacing.md, padding: spacing.md, borderRadius: radius.md, backgroundColor: "rgba(239,68,68,0.12)", borderWidth: 1, borderColor: "rgba(239,68,68,0.3)" },
  errorText: { flex: 1, fontFamily: font.bodyMed, fontSize: 13, color: colors.brandSecondary },
  emptyEp: { fontFamily: font.body, fontSize: 13, color: colors.onSurfaceSecondary, marginTop: spacing.sm },
  epRow: { flexDirection: "row", alignItems: "center", gap: spacing.md, paddingVertical: spacing.sm, paddingHorizontal: spacing.sm, borderRadius: radius.md, marginTop: spacing.xs },
  epThumb: { width: 44, height: 64, borderRadius: radius.sm, backgroundColor: colors.surfaceTertiary, alignItems: "center", justifyContent: "center", overflow: "hidden" },
  epNumBadge: { position: "absolute", top: 2, left: 2, minWidth: 18, height: 18, paddingHorizontal: 3, borderRadius: 9, backgroundColor: "rgba(9,9,11,0.8)", alignItems: "center", justifyContent: "center" },
  epNumTxt: { fontFamily: font.bodyBold, fontSize: 10, color: colors.onSurface },
  epTitle: { fontFamily: font.bodyBold, fontSize: 15, color: colors.onSurface },
  epSub: { fontFamily: font.body, fontSize: 12, color: colors.onSurfaceSecondary, marginTop: 2 },
  epStatus: { paddingHorizontal: spacing.sm, height: 24, borderRadius: radius.pill, backgroundColor: colors.surfaceTertiary, alignItems: "center", justifyContent: "center" },
  epStatusReady: { backgroundColor: "rgba(34,197,94,0.14)" },
  epStatusFailed: { backgroundColor: "rgba(239,68,68,0.14)" },
  epStatusTxt: { fontFamily: font.bodySemi, fontSize: 11, color: colors.onSurfaceSecondary },
});
