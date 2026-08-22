import { Ionicons } from "@expo/vector-icons";
import { Tabs } from "expo-router";
import { Platform } from "react-native";

import { haptic } from "@/src/haptics";
import { HidingTabBar, TabBarVisibilityProvider } from "@/src/tabbar";
import { colors, font } from "@/src/theme";

export default function TabsLayout() {
  return (
    <TabBarVisibilityProvider>
      <Tabs
        tabBar={(props) => <HidingTabBar {...props} />}
        screenOptions={{
          headerShown: false,
          tabBarActiveTintColor: colors.brand,
          tabBarInactiveTintColor: colors.onSurfaceSecondary,
          tabBarStyle: {
            backgroundColor: colors.surfaceSecondary,
            borderTopColor: colors.border,
            borderTopWidth: 1,
            height: Platform.OS === "ios" ? 88 : 64,
            paddingTop: 8,
          },
          tabBarLabelStyle: {
            fontFamily: font.bodySemi,
            fontSize: 11,
            letterSpacing: 0.3,
          },
        }}
        screenListeners={{ tabPress: () => haptic.select() }}
      >
        <Tabs.Screen
          name="index"
          options={{
            title: "Create",
            tabBarTestID: "tab-create",
            tabBarIcon: ({ color, focused }) => (
              <Ionicons name={focused ? "flash" : "flash-outline"} size={24} color={color} />
            ),
          }}
        />
        <Tabs.Screen
          name="series"
          options={{
            title: "Series",
            tabBarTestID: "tab-series",
            tabBarIcon: ({ color, focused }) => (
              <Ionicons name={focused ? "film" : "film-outline"} size={24} color={color} />
            ),
          }}
        />
        <Tabs.Screen
          name="library"
          options={{
            title: "Library",
            tabBarTestID: "tab-library",
            tabBarIcon: ({ color, focused }) => (
              <Ionicons name={focused ? "albums" : "albums-outline"} size={24} color={color} />
            ),
          }}
        />
      </Tabs>
    </TabBarVisibilityProvider>
  );
}
