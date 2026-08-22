import {
  BottomSheetBackdrop,
  BottomSheetModal,
  BottomSheetView,
} from "@gorhom/bottom-sheet";
import { Ionicons } from "@expo/vector-icons";
import { forwardRef, useCallback, useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { haptic } from "@/src/haptics";
import { loadPresets, Preset, savePresets } from "@/src/presets";
import { colors, font, radius, spacing } from "@/src/theme";

type Props = {
  currentSettings: Record<string, any>;
  onApply: (settings: Record<string, any>) => void;
};

const PresetSheet = forwardRef<BottomSheetModal, Props>(
  ({ currentSettings, onApply }, ref) => {
    const insets = useSafeAreaInsets();
    const [presets, setPresets] = useState<Preset[]>([]);
    const [name, setName] = useState("");

    const refresh = useCallback(async () => setPresets(await loadPresets()), []);
    useEffect(() => {
      refresh();
    }, [refresh]);

    const renderBackdrop = useCallback(
      (props: any) => (
        <BottomSheetBackdrop {...props} appearsOnIndex={0} disappearsOnIndex={-1} opacity={0.6} />
      ),
      [],
    );

    const save = useCallback(async () => {
      const nm = name.trim() || `Style ${presets.length + 1}`;
      const next = [...presets.filter((p) => p.name !== nm), { name: nm, settings: currentSettings }];
      await savePresets(next);
      setPresets(next);
      setName("");
      haptic.success();
    }, [name, presets, currentSettings]);

    const remove = useCallback(async (nm: string) => {
      const next = presets.filter((p) => p.name !== nm);
      await savePresets(next);
      setPresets(next);
      haptic.light();
    }, [presets]);

    return (
      <BottomSheetModal
        ref={ref}
        enableDynamicSizing
        backdropComponent={renderBackdrop}
        handleIndicatorStyle={{ backgroundColor: colors.borderStrong }}
        backgroundStyle={{ backgroundColor: colors.surfaceSecondary }}
        keyboardBehavior="interactive"
        android_keyboardInputMode="adjustResize"
      >
        <BottomSheetView style={[styles.container, { paddingBottom: insets.bottom + spacing.lg }]}>
          <Text style={styles.title}>Brand styles</Text>
          <Text style={styles.hint}>Save your current voice, font, colours & music as a one-tap style.</Text>

          <View style={styles.saveRow}>
            <TextInput
              testID="preset-name-input"
              value={name}
              onChangeText={setName}
              placeholder="Name this style"
              placeholderTextColor={colors.onSurfaceSecondary}
              style={styles.input}
            />
            <Pressable testID="preset-save-button" onPress={save} style={styles.saveBtn}>
              <Ionicons name="bookmark" size={16} color={colors.onBrand} />
              <Text style={styles.saveTxt}>Save</Text>
            </Pressable>
          </View>

          <View style={styles.list}>
            {presets.length === 0 ? (
              <Text style={styles.empty}>No saved styles yet.</Text>
            ) : (
              presets.map((p) => (
                <View key={p.name} style={styles.row}>
                  <Pressable
                    testID={`preset-apply-${p.name}`}
                    style={styles.rowMain}
                    onPress={() => {
                      haptic.select();
                      onApply(p.settings);
                    }}
                  >
                    <Ionicons name="color-wand" size={18} color={colors.brand} />
                    <Text style={styles.rowName}>{p.name}</Text>
                  </Pressable>
                  <Pressable testID={`preset-delete-${p.name}`} hitSlop={8} onPress={() => remove(p.name)}>
                    <Ionicons name="trash-outline" size={18} color={colors.onSurfaceSecondary} />
                  </Pressable>
                </View>
              ))
            )}
          </View>
        </BottomSheetView>
      </BottomSheetModal>
    );
  },
);

PresetSheet.displayName = "PresetSheet";
export default PresetSheet;

const styles = StyleSheet.create({
  container: { paddingHorizontal: spacing.lg, paddingTop: spacing.xs },
  title: { fontFamily: font.display, fontSize: 24, color: colors.onSurface, letterSpacing: 0.4 },
  hint: { fontFamily: font.body, fontSize: 12, color: colors.onSurfaceSecondary, marginTop: 4, marginBottom: spacing.md },
  saveRow: { flexDirection: "row", gap: spacing.sm },
  input: {
    flex: 1,
    height: 48,
    backgroundColor: colors.surface,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    fontFamily: font.body,
    fontSize: 15,
    color: colors.onSurface,
  },
  saveBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 6,
    paddingHorizontal: spacing.lg,
    borderRadius: radius.md,
    backgroundColor: colors.brandPrimary,
  },
  saveTxt: { fontFamily: font.bodyBold, fontSize: 14, color: colors.onBrand },
  list: { marginTop: spacing.md, gap: spacing.sm },
  empty: { fontFamily: font.body, fontSize: 13, color: colors.onSurfaceSecondary, paddingVertical: spacing.md },
  row: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    padding: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surface,
  },
  rowMain: { flex: 1, flexDirection: "row", alignItems: "center", gap: spacing.sm },
  rowName: { fontFamily: font.bodySemi, fontSize: 15, color: colors.onSurface },
});
