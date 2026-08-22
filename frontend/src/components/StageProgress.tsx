import { Ionicons } from "@expo/vector-icons";
import { useEffect } from "react";
import { ActivityIndicator, StyleSheet, Text, View } from "react-native";
import Animated, {
  useAnimatedStyle,
  useSharedValue,
  withTiming,
} from "react-native-reanimated";

import { ReelStatus } from "@/src/api";
import { colors, font, radius, spacing } from "@/src/theme";

const RANK: Record<string, number> = {
  queued: 0,
  scripting: 1,
  voicing: 2,
  captioning: 3,
  rendering: 4,
  uploading: 4,
  ready: 5,
  failed: -1,
};

const STAGES = [
  { rank: 1, label: "Writing script", icon: "create-outline" as const },
  { rank: 2, label: "Recording voiceover", icon: "mic-outline" as const },
  { rank: 3, label: "Aligning captions", icon: "text-outline" as const },
  { rank: 4, label: "Rendering video", icon: "film-outline" as const },
];

export default function StageProgress({
  status,
  progress,
}: {
  status: ReelStatus;
  progress: number;
}) {
  const width = useSharedValue(0);
  useEffect(() => {
    width.value = withTiming(progress, { duration: 500 });
  }, [progress, width]);

  const barStyle = useAnimatedStyle(() => ({ width: `${width.value}%` }));
  const current = RANK[status] ?? 0;

  return (
    <View style={styles.wrap}>
      <View style={styles.barTrack}>
        <Animated.View style={[styles.barFill, barStyle]} />
      </View>
      <Text style={styles.pct}>{Math.round(progress)}%</Text>

      <View style={styles.stages}>
        {STAGES.map((s) => {
          const done = current > s.rank;
          const active = current === s.rank;
          return (
            <View key={s.rank} style={styles.stageRow}>
              <View
                style={[
                  styles.iconCircle,
                  done && styles.iconDone,
                  active && styles.iconActive,
                ]}
              >
                {done ? (
                  <Ionicons name="checkmark" size={18} color={colors.onBrand} />
                ) : active ? (
                  <ActivityIndicator size="small" color={colors.brand} />
                ) : (
                  <Ionicons name={s.icon} size={16} color={colors.onSurfaceSecondary} />
                )}
              </View>
              <Text
                style={[
                  styles.stageLabel,
                  (done || active) && { color: colors.onSurface },
                  active && { fontFamily: font.bodyBold },
                ]}
              >
                {s.label}
              </Text>
              {active && <Text style={styles.working}>working…</Text>}
              {done && <Text style={styles.doneTxt}>done</Text>}
            </View>
          );
        })}
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { width: "100%" },
  barTrack: {
    height: 6,
    borderRadius: radius.pill,
    backgroundColor: colors.surfaceTertiary,
    overflow: "hidden",
  },
  barFill: { height: "100%", backgroundColor: colors.brand, borderRadius: radius.pill },
  pct: {
    fontFamily: font.display,
    fontSize: 40,
    color: colors.onSurface,
    letterSpacing: 1,
    marginTop: spacing.md,
    marginBottom: spacing.xl,
  },
  stages: { gap: spacing.md },
  stageRow: { flexDirection: "row", alignItems: "center", gap: spacing.md },
  iconCircle: {
    width: 40,
    height: 40,
    borderRadius: 20,
    alignItems: "center",
    justifyContent: "center",
    backgroundColor: colors.surfaceTertiary,
    borderWidth: 1,
    borderColor: colors.border,
  },
  iconActive: { borderColor: colors.brand, backgroundColor: colors.brandTertiary },
  iconDone: { backgroundColor: colors.brandPrimary, borderColor: colors.brandPrimary },
  stageLabel: { flex: 1, fontFamily: font.bodyMed, fontSize: 15, color: colors.onSurfaceSecondary },
  working: { fontFamily: font.bodySemi, fontSize: 12, color: colors.brand },
  doneTxt: { fontFamily: font.bodyMed, fontSize: 12, color: colors.success },
});
