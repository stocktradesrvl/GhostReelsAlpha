import { Stack, useRouter, useSegments } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { StatusBar } from "expo-status-bar";
import { useFonts } from "expo-font";
import { useEffect, useRef } from "react";
import { LogBox } from "react-native";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { SafeAreaProvider } from "react-native-safe-area-context";
import { KeyboardProvider } from "react-native-keyboard-controller";
import { BottomSheetModalProvider } from "@gorhom/bottom-sheet";
import { QueryClient, QueryClientProvider, useQueryClient } from "@tanstack/react-query";

import { AuthProvider, useAuth } from "@/src/auth";
import { api } from "@/src/api";
import {
  initializeRevenueCat,
  Purchases,
  rcEnabled,
  SubscriptionProvider,
  useSubscription,
} from "@/src/revenuecat";
import { useIconFonts } from "@/src/hooks/use-icon-fonts";
import { colors } from "@/src/theme";

// Disable logbox errors etc so that users can see the app
// and agent works as expected.
LogBox.ignoreAllLogs(true);

const queryClient = new QueryClient();

// SDK init MUST happen once at module scope, before any component mounts.
try {
  initializeRevenueCat();
} catch (err) {
  console.warn("RevenueCat unavailable:", err);
}

// Keep the native splash visible from cold start until icon fonts register.
// Required because @expo/vector-icons' componentDidMount fallback fires
// Font.loadAsync against a broken vendor path if any <Icon> mounts before
// the family is registered — which throws on Android Expo Go.
SplashScreen.preventAutoHideAsync();

export default function RootLayout() {
  const [iconsLoaded, iconError] = useIconFonts();
  const [fontsLoaded, fontError] = useFonts({
    "BarlowCondensed-Bold": require("../assets/fonts/BarlowCondensed-Bold.ttf"),
    "BarlowCondensed-SemiBold": require("../assets/fonts/BarlowCondensed-SemiBold.ttf"),
    "BarlowCondensed-Medium": require("../assets/fonts/BarlowCondensed-Medium.ttf"),
    "Manrope-Regular": require("../assets/fonts/Manrope-Regular.ttf"),
    "Manrope-Medium": require("../assets/fonts/Manrope-Medium.ttf"),
    "Manrope-SemiBold": require("../assets/fonts/Manrope-SemiBold.ttf"),
    "Manrope-Bold": require("../assets/fonts/Manrope-Bold.ttf"),
  });

  const ready = (iconsLoaded || iconError) && (fontsLoaded || fontError);

  useEffect(() => {
    if (ready) SplashScreen.hideAsync();
  }, [ready]);

  if (!ready) return null;

  return (
    <GestureHandlerRootView style={{ flex: 1, backgroundColor: colors.surface }}>
      <SafeAreaProvider>
        <KeyboardProvider>
          <BottomSheetModalProvider>
            <StatusBar style="light" />
            <QueryClientProvider client={queryClient}>
              <AuthProvider>
                <SubscriptionProvider>
                  <RCIdentityBridge />
                  <RootNavigator />
                </SubscriptionProvider>
              </AuthProvider>
            </QueryClientProvider>
          </BottomSheetModalProvider>
        </KeyboardProvider>
      </SafeAreaProvider>
    </GestureHandlerRootView>
  );
}

// Binds RevenueCat identity to the backend user on every auth path and keeps
// the server-side subscription flag in sync with the SDK-verified entitlement.
function RCIdentityBridge() {
  const { user, refresh } = useAuth();
  const { isSubscribed, customerInfo } = useSubscription();
  const queryClient = useQueryClient();
  const rcIdentityRef = useRef<string | null>(null);
  const lastSyncedRef = useRef<string | null>(null);

  // Identity — COMPULSORY on session restore / sign-in / sign-up / sign-out.
  useEffect(() => {
    if (!rcEnabled) return;
    (async () => {
      try {
        if (user?.id && rcIdentityRef.current !== user.id) {
          const { customerInfo } = await Purchases.logIn(user.id);
          rcIdentityRef.current = user.id;
          // Reflect the now-identified state immediately (web SDK keeps
          // originalAppUserId anonymous, so drive identity off the current id).
          queryClient.setQueryData(["revenuecat", "customer-info"], customerInfo);
          queryClient.setQueryData(["revenuecat", "app-user-id"], user.id);
        } else if (!user?.id && rcIdentityRef.current) {
          await Purchases.logOut();
          rcIdentityRef.current = null;
          lastSyncedRef.current = null;
          queryClient.setQueryData(["revenuecat", "app-user-id"], null);
        }
      } catch (e) {
        console.warn("[RevenueCat] identity bind failed:", e);
      }
    })();
  }, [user?.id, queryClient]);

  // Push the SDK-verified entitlement to the backend so the free-reel quota
  // unlocks for subscribers. Only fires when the flag actually changes.
  useEffect(() => {
    if (!rcEnabled || !user?.id) return;
    // Wait until the SDK has actually resolved CustomerInfo — otherwise the
    // initial `false` (query still loading) would clobber a real entitlement.
    if (customerInfo === undefined) return;
    const key = `${user.id}:${isSubscribed}`;
    if (lastSyncedRef.current === key) return;
    if (user.is_subscribed === isSubscribed) {
      lastSyncedRef.current = key;
      return;
    }
    (async () => {
      try {
        await api.syncSubscription(isSubscribed);
        lastSyncedRef.current = key;
        await refresh();
      } catch (e) {
        console.warn("[RevenueCat] subscription sync failed:", e);
      }
    })();
  }, [isSubscribed, customerInfo, user?.id, user?.is_subscribed, refresh]);

  return null;
}

function RootNavigator() {
  const { ready, user } = useAuth();
  const segments = useSegments();
  const router = useRouter();

  useEffect(() => {
    if (!ready) return;
    const onAuthScreen = segments[0] === "auth";
    if (!user && !onAuthScreen) router.replace("/auth");
    else if (user && onAuthScreen) router.replace("/(tabs)");
  }, [ready, user, segments, router]);

  return (
    <Stack
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: colors.surface },
      }}
    >
      <Stack.Screen name="auth" />
      <Stack.Screen name="(tabs)" />
      <Stack.Screen name="reel/[id]" options={{ animation: "slide_from_right" }} />
      <Stack.Screen name="batch" options={{ animation: "slide_from_right" }} />
      <Stack.Screen name="series/new" options={{ animation: "slide_from_right" }} />
      <Stack.Screen name="series/[id]" options={{ animation: "slide_from_right" }} />
      <Stack.Screen name="scenes/[id]" options={{ animation: "slide_from_right" }} />
      <Stack.Screen name="lines/[id]" options={{ animation: "slide_from_right" }} />
      <Stack.Screen name="settings" options={{ animation: "slide_from_right" }} />
      <Stack.Screen name="paywall" options={{ animation: "slide_from_bottom", presentation: "modal" }} />
    </Stack>
  );
}
