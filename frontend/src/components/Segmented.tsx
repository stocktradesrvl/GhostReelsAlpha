import { Pressable, StyleSheet, Text, View } from "react-native";

import { haptic } from "@/src/haptics";
import { colors, font, radius, spacing } from "@/src/theme";

type Option = { id: string; label: string };

export default function Segmented({
  options,
  value,
  onChange,
  testID,
}: {
  options: Option[];
  value: string;
  onChange: (id: string) => void;
  testID?: string;
}) {
  return (
    <View style={styles.track} testID={testID}>
      {options.map((o) => {
        const active = o.id === value;
        return (
          <Pressable
            key={o.id}
            testID={`segment-${o.id}`}
            onPress={() => {
              haptic.light();
              onChange(o.id);
            }}
            style={[styles.seg, active && styles.segActive]}
          >
            <Text style={[styles.label, active && styles.labelActive]}>{o.label}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  track: {
    flexDirection: "row",
    backgroundColor: colors.surfaceSecondary,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    padding: 4,
    gap: 4,
  },
  seg: {
    flex: 1,
    height: 40,
    borderRadius: radius.sm,
    alignItems: "center",
    justifyContent: "center",
  },
  segActive: { backgroundColor: colors.brandPrimary },
  label: { fontFamily: font.bodySemi, fontSize: 13, color: colors.onSurfaceSecondary, letterSpacing: 0.3 },
  labelActive: { color: colors.onBrand },
});
