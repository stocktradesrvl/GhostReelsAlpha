import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { haptic } from "@/src/haptics";
import { colors, font, radius, spacing } from "@/src/theme";

export const IMAGE_COUNT_CHIPS = [2, 3, 4, 6, 8, 12] as const;

type StyleOpt = { id: string; name: string };

export default function AiImageControls({
  styles: styleOpts,
  imageStyle,
  onStyle,
  imageCount,
  onCount,
  direction,
  onDirection,
  testPrefix = "",
}: {
  styles: StyleOpt[];
  imageStyle: string;
  onStyle: (id: string) => void;
  imageCount: number | null;
  onCount: (n: number | null) => void;
  direction: string;
  onDirection: (v: string) => void;
  testPrefix?: string;
}) {
  const styleTid = (id: string) =>
    testPrefix === "series" ? `series-img-${id}` : testPrefix ? `${testPrefix}-image-style-${id}` : `image-style-${id}`;
  const countTid = (id: string) =>
    testPrefix ? `${testPrefix}-image-count-${id}` : `image-count-${id}`;

  return (
    <>
      <Text style={styles.section}>IMAGE STYLE</Text>
      <View style={styles.chipWrap} testID={testPrefix ? `${testPrefix}-image-style` : "image-style"}>
        {styleOpts.map((o) => {
          const active = o.id === imageStyle;
          return (
            <Pressable
              key={o.id}
              testID={styleTid(o.id)}
              onPress={() => { haptic.light(); onStyle(o.id); }}
              style={[styles.chip, active && styles.chipActive]}
            >
              <Text style={[styles.chipText, active && styles.chipTextActive]}>{o.name}</Text>
            </Pressable>
          );
        })}
      </View>

      <View style={styles.head}>
        <Text style={styles.section}>HOW MANY IMAGES</Text>
        <Text style={styles.hintRight}>{imageCount == null ? "Auto" : `${imageCount}`}</Text>
      </View>
      <Text style={styles.helper}>
        Auto matches length (~1 image per 10 seconds, 2–4). Pick more for a 30s horror reel — more images means more Gemini calls, that's OK.
      </Text>
      <View style={styles.chipWrap} testID={testPrefix ? `${testPrefix}-image-count` : "image-count"}>
        <Pressable
          testID={countTid("auto")}
          onPress={() => { haptic.light(); onCount(null); }}
          style={[styles.chip, imageCount == null && styles.chipActive]}
        >
          <Text style={[styles.chipText, imageCount == null && styles.chipTextActive]}>Auto</Text>
        </Pressable>
        {IMAGE_COUNT_CHIPS.map((n) => {
          const active = imageCount === n;
          return (
            <Pressable
              key={n}
              testID={countTid(String(n))}
              onPress={() => { haptic.light(); onCount(n); }}
              style={[styles.chip, active && styles.chipActive]}
            >
              <Text style={[styles.chipText, active && styles.chipTextActive]}>{n}</Text>
            </Pressable>
          );
        })}
      </View>

      <Text style={styles.section}>MOOD / DIRECTION · OPTIONAL</Text>
      <TextInput
        testID={testPrefix ? `${testPrefix}-image-direction-input` : "image-direction-input"}
        value={direction}
        onChangeText={onDirection}
        placeholder="e.g. terrifying, hopeful golden-hour, found footage night vision"
        placeholderTextColor={colors.onSurfaceSecondary}
        maxLength={120}
        style={styles.input}
      />
    </>
  );
}

const styles = StyleSheet.create({
  section: {
    fontFamily: font.bodyBold,
    fontSize: 11,
    letterSpacing: 1.2,
    color: colors.onSurfaceSecondary,
    marginTop: spacing.lg,
    marginBottom: spacing.sm,
  },
  helper: {
    fontFamily: font.body,
    fontSize: 12,
    color: colors.onSurfaceSecondary,
    lineHeight: 17,
    marginBottom: spacing.sm,
  },
  head: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  hintRight: { fontFamily: font.bodyMed, fontSize: 11, color: colors.onSurfaceSecondary, marginTop: spacing.lg },
  chipWrap: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  chip: {
    minWidth: 72,
    paddingHorizontal: spacing.md,
    height: 44,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surfaceSecondary,
    alignItems: "center",
    justifyContent: "center",
  },
  chipActive: { borderColor: colors.brand, backgroundColor: colors.brandTertiary },
  chipText: { fontFamily: font.bodySemi, fontSize: 14, color: colors.onSurfaceSecondary },
  chipTextActive: { color: colors.onBrandTertiary },
  input: {
    backgroundColor: colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    height: 48,
    fontFamily: font.body,
    fontSize: 15,
    color: colors.onSurface,
  },
});
