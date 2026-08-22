import { Ionicons } from "@expo/vector-icons";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
  ViewStyle,
} from "react-native";

import { haptic } from "@/src/haptics";
import { colors, font, radius, spacing } from "@/src/theme";

type Props = {
  label: string;
  onPress: () => void;
  loading?: boolean;
  disabled?: boolean;
  icon?: keyof typeof Ionicons.glyphMap;
  variant?: "primary" | "ghost";
  testID?: string;
  style?: ViewStyle;
};

export default function PrimaryButton({
  label,
  onPress,
  loading,
  disabled,
  icon,
  variant = "primary",
  testID,
  style,
}: Props) {
  const isPrimary = variant === "primary";
  const off = disabled || loading;
  return (
    <Pressable
      testID={testID}
      disabled={off}
      onPress={() => {
        haptic.medium();
        onPress();
      }}
      style={({ pressed }) => [
        styles.btn,
        isPrimary ? styles.primary : styles.ghost,
        off && styles.off,
        pressed && !off && styles.pressed,
        style,
      ]}
    >
      {loading ? (
        <ActivityIndicator color={isPrimary ? colors.onBrand : colors.onSurface} />
      ) : (
        <View style={styles.row}>
          {icon && (
            <Ionicons
              name={icon}
              size={18}
              color={isPrimary ? colors.onBrand : colors.onSurface}
            />
          )}
          <Text style={[styles.label, { color: isPrimary ? colors.onBrand : colors.onSurface }]}>
            {label}
          </Text>
        </View>
      )}
    </Pressable>
  );
}

const styles = StyleSheet.create({
  btn: {
    height: 54,
    borderRadius: radius.lg,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: spacing.lg,
  },
  primary: { backgroundColor: colors.brandPrimary },
  ghost: { backgroundColor: colors.surfaceTertiary, borderWidth: 1, borderColor: colors.border },
  off: { opacity: 0.45 },
  pressed: { opacity: 0.85, transform: [{ scale: 0.99 }] },
  row: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  label: { fontFamily: font.bodyBold, fontSize: 16, letterSpacing: 0.2 },
});
