import { StyleSheet, Text, View } from "react-native";

import { ReelStatus } from "@/src/api";
import { colors, font, radius, spacing } from "@/src/theme";

const MAP: Record<string, { label: string; fg: string; bg: string }> = {
  ready: { label: "READY", fg: colors.success, bg: "rgba(34,197,94,0.14)" },
  failed: { label: "FAILED", fg: colors.error, bg: "rgba(239,68,68,0.14)" },
  generating: { label: "GENERATING", fg: colors.warning, bg: "rgba(234,179,8,0.14)" },
};

export default function StatusBadge({ status }: { status: ReelStatus }) {
  const key = status === "ready" ? "ready" : status === "failed" ? "failed" : "generating";
  const c = MAP[key];
  return (
    <View style={[styles.badge, { backgroundColor: c.bg }]} testID={`status-badge-${key}`}>
      {key === "generating" && <View style={[styles.dot, { backgroundColor: c.fg }]} />}
      <Text style={[styles.text, { color: c.fg }]}>{c.label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  badge: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    paddingHorizontal: spacing.sm,
    height: 22,
    borderRadius: radius.sm,
  },
  dot: { width: 6, height: 6, borderRadius: 3 },
  text: { fontFamily: font.bodyBold, fontSize: 10, letterSpacing: 0.6 },
});
