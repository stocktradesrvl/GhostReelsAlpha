import * as Haptics from "expo-haptics";
import { Platform } from "react-native";

const on = Platform.OS !== "web";

export const haptic = {
  select: () => on && Haptics.selectionAsync(),
  light: () => on && Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light),
  medium: () => on && Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium),
  heavy: () => on && Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Heavy),
  success: () => on && Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success),
  error: () => on && Haptics.notificationAsync(Haptics.NotificationFeedbackType.Error),
};
