import { BottomSheetBackdrop, BottomSheetModal, BottomSheetView } from "@gorhom/bottom-sheet";
import { Ionicons } from "@expo/vector-icons";
import * as ImagePicker from "expo-image-picker";
import { forwardRef, useCallback, useEffect, useState } from "react";
import { ActivityIndicator, Alert, Linking, Pressable, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Outro } from "@/src/api";
import { haptic } from "@/src/haptics";
import { colors, font, radius, spacing } from "@/src/theme";

type Props = {
  selectedId: string | null;
  onSelect: (outro: Outro | null) => void;
};

const OutroSheet = forwardRef<BottomSheetModal, Props>(({ selectedId, onSelect }, ref) => {
  const insets = useSafeAreaInsets();
  const [outros, setOutros] = useState<Outro[]>([]);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try { setOutros(await api.listOutros()); } catch { /* keep */ }
  }, []);

  useEffect(() => { load(); }, [load]);

  const renderBackdrop = useCallback(
    (props: any) => <BottomSheetBackdrop {...props} appearsOnIndex={0} disappearsOnIndex={-1} opacity={0.6} />,
    [],
  );

  const pickAndUpload = useCallback(async () => {
    setError(null);
    let perm = await ImagePicker.getMediaLibraryPermissionsAsync();
    if (perm.status !== "granted" && perm.canAskAgain) {
      perm = await ImagePicker.requestMediaLibraryPermissionsAsync();
    }
    if (perm.status !== "granted") {
      haptic.error();
      Alert.alert(
        "Photos access needed",
        "Allow photo access to pick an outro clip.",
        perm.canAskAgain
          ? [{ text: "OK" }]
          : [{ text: "Cancel", style: "cancel" }, { text: "Open Settings", onPress: () => Linking.openSettings() }],
      );
      return;
    }
    const res = await ImagePicker.launchImageLibraryAsync({
      mediaTypes: ImagePicker.MediaTypeOptions.Videos,
      quality: 1,
      videoMaxDuration: 15,
    });
    if (res.canceled || !res.assets?.[0]) return;
    const asset = res.assets[0];
    setUploading(true);
    try {
      const name = asset.fileName || "Outro clip";
      const created = await api.uploadOutro(asset.uri, name);
      haptic.success();
      await load();
      onSelect(created);
    } catch (e: any) {
      setError(e.message || "Couldn't upload that clip.");
      haptic.error();
    } finally {
      setUploading(false);
    }
  }, [load, onSelect]);

  const remove = useCallback((id: string) => {
    Alert.alert("Delete outro?", "This removes the clip from your outros.", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Delete", style: "destructive", onPress: async () => {
          await api.deleteOutro(id);
          if (selectedId === id) onSelect(null);
          haptic.medium();
          load();
        },
      },
    ]);
  }, [selectedId, onSelect, load]);

  return (
    <BottomSheetModal
      ref={ref}
      enableDynamicSizing
      backdropComponent={renderBackdrop}
      handleIndicatorStyle={{ backgroundColor: colors.borderStrong }}
      backgroundStyle={{ backgroundColor: colors.surfaceSecondary }}
    >
      <BottomSheetView style={[styles.container, { paddingBottom: insets.bottom + spacing.lg }]}>
        <Text style={styles.title}>Outro clip</Text>
        <Text style={styles.hint}>Append a short clip (e.g. “stay tuned for more”) to the end of your reel.</Text>

        <Pressable
          testID="outro-none"
          onPress={() => { haptic.select(); onSelect(null); }}
          style={[styles.row, !selectedId && styles.rowActive]}
        >
          <Ionicons name="close-circle-outline" size={22} color={colors.onSurfaceSecondary} />
          <Text style={styles.rowTitle}>No outro</Text>
          {!selectedId && <Ionicons name="checkmark-circle" size={22} color={colors.brand} />}
        </Pressable>

        {outros.map((o) => {
          const active = o.id === selectedId;
          return (
            <Pressable
              key={o.id}
              testID={`outro-${o.id}`}
              onPress={() => { haptic.select(); onSelect(o); }}
              style={[styles.row, active && styles.rowActive]}
            >
              <Ionicons name="film-outline" size={22} color={colors.brand} />
              <Text style={styles.rowTitle} numberOfLines={1}>{o.name}</Text>
              <Pressable testID={`outro-delete-${o.id}`} hitSlop={8} onPress={() => remove(o.id)} style={styles.trash}>
                <Ionicons name="trash-outline" size={16} color={colors.onSurfaceSecondary} />
              </Pressable>
              {active && <Ionicons name="checkmark-circle" size={22} color={colors.brand} />}
            </Pressable>
          );
        })}

        <Pressable testID="outro-upload" onPress={pickAndUpload} disabled={uploading} style={styles.uploadBtn}>
          {uploading ? (
            <ActivityIndicator color={colors.onBrandTertiary} />
          ) : (
            <>
              <Ionicons name="cloud-upload-outline" size={18} color={colors.onBrandTertiary} />
              <Text style={styles.uploadTxt}>Upload outro clip</Text>
            </>
          )}
        </Pressable>
        {!!error && <Text style={styles.error}>{error}</Text>}
      </BottomSheetView>
    </BottomSheetModal>
  );
});

OutroSheet.displayName = "OutroSheet";
export default OutroSheet;

const styles = StyleSheet.create({
  container: { paddingHorizontal: spacing.lg, paddingTop: spacing.xs },
  title: { fontFamily: font.display, fontSize: 24, color: colors.onSurface, letterSpacing: 0.4 },
  hint: { fontFamily: font.body, fontSize: 12, color: colors.onSurfaceSecondary, marginTop: spacing.xs, marginBottom: spacing.md, lineHeight: 17 },
  row: {
    flexDirection: "row", alignItems: "center", gap: spacing.md, padding: spacing.md,
    borderRadius: radius.md, borderWidth: 1, borderColor: colors.border,
    backgroundColor: colors.surface, marginBottom: spacing.sm,
  },
  rowActive: { borderColor: colors.brand, backgroundColor: colors.surfaceTertiary },
  rowTitle: { flex: 1, fontFamily: font.bodyBold, fontSize: 15, color: colors.onSurface },
  trash: { width: 32, height: 32, borderRadius: 16, alignItems: "center", justifyContent: "center", backgroundColor: colors.surfaceTertiary },
  uploadBtn: {
    flexDirection: "row", alignItems: "center", justifyContent: "center", gap: spacing.sm,
    height: 50, borderRadius: radius.md, marginTop: spacing.xs,
    backgroundColor: colors.brandTertiary, borderWidth: 1, borderColor: colors.brandPrimary,
  },
  uploadTxt: { fontFamily: font.bodyBold, fontSize: 15, color: colors.onBrandTertiary },
  error: { fontFamily: font.bodyMed, fontSize: 13, color: colors.brandSecondary, marginTop: spacing.sm },
});
