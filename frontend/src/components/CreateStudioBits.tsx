import { Ionicons } from "@expo/vector-icons";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { haptic } from "@/src/haptics";
import { colors, font, radius, spacing } from "@/src/theme";

export function SettingRow({
  icon,
  label,
  value,
  onPress,
  dot,
  swatch,
  testID,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  value: string;
  onPress: () => void;
  dot?: string;
  swatch?: string[];
  testID?: string;
}) {
  return (
    <Pressable
      testID={testID}
      onPress={() => {
        haptic.select();
        onPress();
      }}
      style={({ pressed }) => [styles.settingRow, pressed && { backgroundColor: colors.surfaceTertiary }]}
    >
      <View style={styles.settingLeft}>
        <Ionicons name={icon} size={18} color={colors.onSurfaceSecondary} />
        <Text style={styles.settingLabel}>{label}</Text>
      </View>
      <View style={styles.settingRight}>
        {dot && <View style={[styles.miniDot, { backgroundColor: dot }]} />}
        {swatch && (
          <View style={styles.miniSwatchWrap}>
            {swatch.map((c, i) => (
              <View key={i} style={[styles.miniSwatch, { backgroundColor: c }]} />
            ))}
          </View>
        )}
        <Text style={styles.settingValue}>{value}</Text>
        <Ionicons name="chevron-forward" size={16} color={colors.onSurfaceSecondary} />
      </View>
    </Pressable>
  );
}

export function ChipSelector({
  options,
  value,
  onChange,
  testID,
}: {
  options: { id: string; name: string }[];
  value: string;
  onChange: (id: string) => void;
  testID?: string;
}) {
  return (
    <View style={styles.chipRow} testID={testID}>
      {options.map((o) => {
        const active = o.id === value;
        return (
          <Pressable
            key={o.id}
            testID={`${testID}-${o.id}`}
            onPress={() => {
              haptic.light();
              onChange(o.id);
            }}
            style={[styles.chip, active && styles.chipActive]}
          >
            <Text style={[styles.chipText, active && styles.chipTextActive]}>{o.name}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

export function ColorField({
  value,
  onChange,
  testID,
}: {
  value: string;
  onChange: (v: string) => void;
  testID?: string;
}) {
  const v = value.trim();
  const valid = /^#?[0-9a-fA-F]{6}$/.test(v);
  const swatch = valid ? (v.startsWith("#") ? v : `#${v}`) : "#000000";
  return (
    <View style={styles.colorField}>
      <View style={[styles.colorSwatch, { backgroundColor: swatch }]} />
      <TextInput
        testID={testID}
        value={value}
        onChangeText={onChange}
        autoCapitalize="characters"
        autoCorrect={false}
        maxLength={7}
        placeholder="#RRGGBB"
        placeholderTextColor={colors.onSurfaceSecondary}
        style={styles.colorInput}
      />
    </View>
  );
}

export const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  brand: { fontFamily: font.display, fontSize: 26, color: colors.onSurface, letterSpacing: 1 },
  sub: { fontFamily: font.body, fontSize: 12, color: colors.onSurfaceSecondary, marginTop: 2 },
  aiNote: { fontFamily: font.body, fontSize: 12, color: colors.brandSecondary, marginTop: spacing.sm, lineHeight: 17 },
  creditBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    padding: spacing.md,
    marginBottom: spacing.md,
    borderRadius: radius.md,
    backgroundColor: "rgba(234,179,8,0.12)",
    borderWidth: 1,
    borderColor: "rgba(234,179,8,0.35)",
  },
  creditText: { flex: 1, fontFamily: font.bodyMed, fontSize: 12, color: colors.warning, lineHeight: 16 },
  headerRight: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  batchBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    paddingHorizontal: spacing.md,
    height: 40,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surfaceSecondary,
  },
  batchTxt: { fontFamily: font.bodySemi, fontSize: 13, color: colors.onSurface },
  sectionRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  presetPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    marginTop: spacing.lg,
    paddingHorizontal: spacing.md,
    height: 30,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.brandPrimary,
    backgroundColor: colors.brandTertiary,
  },
  presetPillTxt: { fontFamily: font.bodySemi, fontSize: 12, color: colors.onBrandTertiary },
  logo: {
    width: 40,
    height: 40,
    borderRadius: radius.md,
    backgroundColor: colors.brandTertiary,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.brandPrimary,
  },
  section: {
    fontFamily: font.bodyBold,
    fontSize: 11,
    letterSpacing: 1.2,
    color: colors.onSurfaceSecondary,
    marginTop: spacing.lg,
    marginBottom: spacing.sm,
  },
  input: {
    backgroundColor: colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.md,
    fontFamily: font.body,
    fontSize: 15,
    color: colors.onSurface,
    textAlignVertical: "top",
  },
  chipRow: { flexDirection: "row", gap: spacing.sm },
  colorRow: { flexDirection: "row", gap: spacing.sm },
  colorField: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    height: 48,
  },
  colorSwatch: { width: 24, height: 24, borderRadius: 6, borderWidth: 1, borderColor: colors.borderStrong },
  colorInput: { flex: 1, fontFamily: font.bodyMed, fontSize: 15, color: colors.onSurface },
  chip: {
    flex: 1,
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
  scriptHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  wordCount: { fontFamily: font.bodyMed, fontSize: 11, color: colors.onSurfaceSecondary, marginTop: spacing.lg },
  settings: {
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surfaceSecondary,
    overflow: "hidden",
  },
  settingRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.md,
    height: 54,
    borderBottomWidth: 1,
    borderBottomColor: colors.divider,
  },
  settingLeft: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  settingLabel: { fontFamily: font.bodySemi, fontSize: 15, color: colors.onSurface },
  settingRight: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  settingValue: { fontFamily: font.bodyMed, fontSize: 14, color: colors.onSurfaceSecondary },
  toggleRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: spacing.lg,
    padding: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surfaceSecondary,
  },
  toggleSub: { fontFamily: font.body, fontSize: 11, color: colors.onSurfaceSecondary, marginTop: 2 },
  miniDot: { width: 12, height: 12, borderRadius: 6 },
  miniSwatchWrap: { flexDirection: "row", borderRadius: radius.sm, overflow: "hidden" },
  miniSwatch: { width: 8, height: 16 },
  errorBox: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginTop: spacing.lg,
    padding: spacing.md,
    borderRadius: radius.md,
    backgroundColor: "rgba(239,68,68,0.12)",
    borderWidth: 1,
    borderColor: "rgba(239,68,68,0.3)",
  },
  errorText: { flex: 1, fontFamily: font.bodyMed, fontSize: 13, color: colors.brandSecondary },
  ctaWrap: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
  ctaHint: {
    fontFamily: font.body,
    fontSize: 12,
    color: colors.onSurfaceSecondary,
    textAlign: "center",
    marginBottom: spacing.sm,
  },
});
