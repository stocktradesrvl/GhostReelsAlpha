import { BottomSheetBackdrop, BottomSheetModal, BottomSheetView } from "@gorhom/bottom-sheet";
import { Ionicons } from "@expo/vector-icons";
import { LinearGradient } from "expo-linear-gradient";
import { forwardRef, useCallback } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { haptic } from "@/src/haptics";
import { colors, font, radius, spacing } from "@/src/theme";

export type SheetOption = {
  id: string;
  title: string;
  subtitle?: string;
  swatch?: string[]; // gradient preview
  dot?: string; // single color dot
};

type Props = {
  title: string;
  options: SheetOption[];
  selectedId: string;
  onSelect: (id: string) => void;
  onPreview?: (id: string) => void;
  previewingId?: string | null;
};

const OptionSheet = forwardRef<BottomSheetModal, Props>(
  ({ title, options, selectedId, onSelect, onPreview, previewingId }, ref) => {
    const insets = useSafeAreaInsets();

    const renderBackdrop = useCallback(
      (props: any) => (
        <BottomSheetBackdrop {...props} appearsOnIndex={0} disappearsOnIndex={-1} opacity={0.6} />
      ),
      [],
    );

    return (
      <BottomSheetModal
        ref={ref}
        enableDynamicSizing
        backdropComponent={renderBackdrop}
        handleIndicatorStyle={{ backgroundColor: colors.borderStrong }}
        backgroundStyle={{ backgroundColor: colors.surfaceSecondary }}
      >
        <BottomSheetView style={[styles.container, { paddingBottom: insets.bottom + spacing.lg }]}>
          <Text style={styles.title}>{title}</Text>
          <View style={styles.list}>
            {options.map((o) => {
              const active = o.id === selectedId;
              return (
                <Pressable
                  key={o.id}
                  testID={`sheet-option-${o.id}`}
                  onPress={() => {
                    haptic.select();
                    onSelect(o.id);
                  }}
                  style={[styles.row, active && styles.rowActive]}
                >
                  {o.swatch && (
                    <LinearGradient
                      colors={o.swatch as [string, string, ...string[]]}
                      start={{ x: 0, y: 0 }}
                      end={{ x: 1, y: 1 }}
                      style={styles.swatch}
                    />
                  )}
                  {o.dot && <View style={[styles.dotWrap]}><View style={[styles.dot, { backgroundColor: o.dot }]} /></View>}
                  <View style={styles.textWrap}>
                    <Text style={styles.optTitle}>{o.title}</Text>
                    {o.subtitle && <Text style={styles.optSub}>{o.subtitle}</Text>}
                  </View>
                  {onPreview && (
                    <Pressable
                      testID={`preview-${o.id}`}
                      hitSlop={8}
                      onPress={(e) => {
                        (e as any).stopPropagation?.();
                        haptic.light();
                        onPreview(o.id);
                      }}
                      style={styles.previewBtn}
                    >
                      <Ionicons
                        name={previewingId === o.id ? "pause" : "play"}
                        size={16}
                        color={colors.onSurface}
                      />
                    </Pressable>
                  )}
                  {active && <Ionicons name="checkmark-circle" size={22} color={colors.brand} />}
                </Pressable>
              );
            })}
          </View>
        </BottomSheetView>
      </BottomSheetModal>
    );
  },
);

OptionSheet.displayName = "OptionSheet";
export default OptionSheet;

const styles = StyleSheet.create({
  container: { paddingHorizontal: spacing.lg, paddingTop: spacing.xs },
  title: {
    fontFamily: font.display,
    fontSize: 24,
    color: colors.onSurface,
    letterSpacing: 0.4,
    marginBottom: spacing.md,
  },
  list: { gap: spacing.sm },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    padding: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  rowActive: { borderColor: colors.brand, backgroundColor: colors.surfaceTertiary },
  swatch: { width: 40, height: 40, borderRadius: radius.sm },
  dotWrap: {
    width: 40,
    height: 40,
    borderRadius: radius.sm,
    backgroundColor: colors.surfaceTertiary,
    alignItems: "center",
    justifyContent: "center",
  },
  dot: { width: 16, height: 16, borderRadius: 8 },
  textWrap: { flex: 1 },
  previewBtn: {
    width: 34,
    height: 34,
    borderRadius: 17,
    backgroundColor: colors.surfaceTertiary,
    borderWidth: 1,
    borderColor: colors.borderStrong,
    alignItems: "center",
    justifyContent: "center",
  },
  optTitle: { fontFamily: font.bodyBold, fontSize: 15, color: colors.onSurface },
  optSub: { fontFamily: font.body, fontSize: 12, color: colors.onSurfaceSecondary, marginTop: 2 },
});
