import { Ionicons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { LinearGradient } from "expo-linear-gradient";
import dayjs from "dayjs";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { api, Reel } from "@/src/api";
import StatusBadge from "@/src/components/StatusBadge";
import { colors, font, radius, spacing } from "@/src/theme";

const BG_PREVIEW: Record<string, string[]> = {
  ember: ["#DC2626", "#450A0A", "#09090B"],
  midnight: ["#0D9488", "#0F766E", "#09090B"],
  sunset: ["#EA580C", "#7C2D12", "#09090B"],
  mono: ["#3F3F46", "#27272A", "#09090B"],
};

export default function ReelCard({ reel, onPress }: { reel: Reel; onPress: () => void }) {
  const preview = BG_PREVIEW[reel.bg_theme] || BG_PREVIEW.ember;
  const showThumb = reel.status === "ready" && reel.has_video;

  return (
    <Pressable
      testID={`reel-card-${reel.id}`}
      onPress={onPress}
      style={({ pressed }) => [styles.card, pressed && { opacity: 0.85 }]}
    >
      <View style={styles.media}>
        {showThumb ? (
          <Image
            source={{ uri: api.thumbUrl(reel.id) }}
            style={StyleSheet.absoluteFill}
            contentFit="cover"
            transition={200}
            cachePolicy="memory-disk"
          />
        ) : (
          <LinearGradient
            colors={preview as [string, string, ...string[]]}
            start={{ x: 0.2, y: 0 }}
            end={{ x: 0.8, y: 1 }}
            style={StyleSheet.absoluteFill}
          />
        )}

        {!showThumb && (
          <View style={styles.centerIcon}>
            <Ionicons
              name={reel.status === "failed" ? "alert-circle" : "sync"}
              size={30}
              color="rgba(255,255,255,0.85)"
            />
          </View>
        )}

        <View style={styles.badgeWrap}>
          <StatusBadge status={reel.status} />
        </View>

        {showThumb && (
          <View style={styles.playWrap}>
            <Ionicons name="play" size={18} color="#fff" />
          </View>
        )}

        <LinearGradient
          colors={["transparent", "rgba(9,9,11,0.95)"]}
          style={styles.scrim}
        />
        <View style={styles.info}>
          <Text style={styles.title} numberOfLines={2}>
            {reel.title}
          </Text>
          <Text style={styles.date}>{dayjs(reel.created_at).format("MMM D · h:mm A")}</Text>
        </View>
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  card: {
    flex: 1,
    aspectRatio: 9 / 16,
    borderRadius: radius.lg,
    overflow: "hidden",
    borderWidth: 1,
    borderColor: colors.border,
  },
  media: { flex: 1, backgroundColor: colors.surfaceSecondary },
  centerIcon: { ...StyleSheet.absoluteFillObject, alignItems: "center", justifyContent: "center" },
  badgeWrap: { position: "absolute", top: spacing.sm, left: spacing.sm },
  playWrap: {
    position: "absolute",
    top: spacing.sm,
    right: spacing.sm,
    width: 30,
    height: 30,
    borderRadius: 15,
    backgroundColor: "rgba(0,0,0,0.5)",
    alignItems: "center",
    justifyContent: "center",
  },
  scrim: { position: "absolute", left: 0, right: 0, bottom: 0, height: "55%" },
  info: { position: "absolute", left: spacing.sm, right: spacing.sm, bottom: spacing.sm },
  title: { fontFamily: font.bodyBold, fontSize: 14, color: colors.onSurface },
  date: { fontFamily: font.body, fontSize: 11, color: colors.onSurfaceSecondary, marginTop: 2 },
});
