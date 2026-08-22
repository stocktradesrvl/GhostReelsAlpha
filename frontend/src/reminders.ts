import * as Notifications from "expo-notifications";
import { Platform } from "react-native";

Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldShowBanner: true,
    shouldShowList: true,
    shouldPlaySound: true,
    shouldSetBadge: false,
  }),
});

export async function ensureNotificationPermission(): Promise<{ granted: boolean; canAskAgain: boolean }> {
  const cur = await Notifications.getPermissionsAsync();
  let status = cur.status;
  let canAskAgain = cur.canAskAgain;
  if (status !== "granted" && canAskAgain) {
    const req = await Notifications.requestPermissionsAsync();
    status = req.status;
    canAskAgain = req.canAskAgain;
  }
  return { granted: status === "granted", canAskAgain };
}

export async function schedulePostReminder(when: Date, title: string, reelId: string): Promise<void> {
  if (Platform.OS === "android") {
    await Notifications.setNotificationChannelAsync("post-reminders", {
      name: "Post reminders",
      importance: Notifications.AndroidImportance.HIGH,
    });
  }
  await Notifications.scheduleNotificationAsync({
    content: {
      title: "Time to post 🎬",
      body: `Share "${title}" to YouTube or Instagram.`,
      data: { reelId },
    },
    trigger: {
      type: Notifications.SchedulableTriggerInputTypes.DATE,
      date: when,
      channelId: Platform.OS === "android" ? "post-reminders" : undefined,
    },
  });
}
