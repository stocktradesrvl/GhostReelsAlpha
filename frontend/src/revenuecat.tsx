import React, { createContext, useContext, useEffect } from "react";
import { Platform } from "react-native";
import Purchases, { LOG_LEVEL } from "react-native-purchases";
import type { CustomerInfo, PurchasesPackage } from "react-native-purchases";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

const REVENUECAT_TEST_API_KEY = process.env.EXPO_PUBLIC_REVENUECAT_TEST_API_KEY;
const REVENUECAT_IOS_API_KEY = process.env.EXPO_PUBLIC_REVENUECAT_IOS_API_KEY;
const REVENUECAT_ANDROID_API_KEY = process.env.EXPO_PUBLIC_REVENUECAT_ANDROID_API_KEY;

export const REVENUECAT_ENTITLEMENT_IDENTIFIER = "pro"; // from setup: entitlement_lookup_key

export const rcEnabled = Platform.OS !== "web" || __DEV__; // web preview uses the Test Store

function getRevenueCatApiKey() {
  if (!REVENUECAT_TEST_API_KEY || !REVENUECAT_IOS_API_KEY || !REVENUECAT_ANDROID_API_KEY) {
    throw new Error("RevenueCat public API keys not found — run the Setup section first");
  }
  if (Platform.OS === "web" || __DEV__) {
    return REVENUECAT_TEST_API_KEY; // Expo Go and the web preview use the RevenueCat Test Store
  }
  if (Platform.OS === "ios") return REVENUECAT_IOS_API_KEY;
  if (Platform.OS === "android") return REVENUECAT_ANDROID_API_KEY;
  return REVENUECAT_TEST_API_KEY;
}

export function initializeRevenueCat() {
  if (!rcEnabled) return; // no store on production web
  Purchases.setLogLevel(__DEV__ ? LOG_LEVEL.DEBUG : LOG_LEVEL.WARN);
  Purchases.configure({ apiKey: getRevenueCatApiKey() });
}

function useSubscriptionContext() {
  const queryClient = useQueryClient();

  const customerInfoQuery = useQuery({
    queryKey: ["revenuecat", "customer-info"],
    queryFn: () => Purchases.getCustomerInfo(),
    enabled: rcEnabled,
    staleTime: 60 * 1000,
  });

  const offeringsQuery = useQuery({
    queryKey: ["revenuecat", "offerings"],
    queryFn: () => Purchases.getOfferings(),
    enabled: rcEnabled,
    staleTime: 300 * 1000,
  });

  // The CURRENT app user id (after logIn this is the backend user id). Unlike
  // `originalAppUserId` — which tracks the FIRST identity and can stay anonymous
  // on the web (purchases-js) SDK even after a successful logIn — this reflects
  // who the SDK will attribute a purchase to right now.
  const appUserIdQuery = useQuery({
    queryKey: ["revenuecat", "app-user-id"],
    queryFn: () => Purchases.getAppUserID(),
    enabled: rcEnabled,
    staleTime: 60 * 1000,
  });

  // Reactive entitlement updates — the SDK pushes fresh CustomerInfo after
  // purchases, restores, renewals, and logIn/logOut. Never poll for this.
  useEffect(() => {
    if (!rcEnabled) return;
    const listener = (info: CustomerInfo) =>
      queryClient.setQueryData(["revenuecat", "customer-info"], info);
    Purchases.addCustomerInfoUpdateListener(listener);
    return () => {
      Purchases.removeCustomerInfoUpdateListener(listener);
    };
  }, [queryClient]);

  const purchaseMutation = useMutation({
    mutationFn: async (packageToPurchase: PurchasesPackage) => {
      // Choke point: never let an anonymous purchase through (see identity rule).
      const id = await Purchases.getAppUserID();
      if (!id || id.startsWith("$RCAnonymousID:")) throw new Error("identity_not_ready");
      const { customerInfo } = await Purchases.purchasePackage(packageToPurchase);
      return customerInfo;
    },
    onSuccess: (info) => {
      // The web (purchases-js) customer-info listener is unreliable, so write the
      // fresh CustomerInfo the SDK returned straight into the cache.
      queryClient.setQueryData(["revenuecat", "customer-info"], info);
    },
  });

  const restoreMutation = useMutation({
    mutationFn: () => Purchases.restorePurchases(),
    onSuccess: (info) => {
      queryClient.setQueryData(["revenuecat", "customer-info"], info);
    },
  });

  const isSubscribed =
    customerInfoQuery.data?.entitlements.active?.[REVENUECAT_ENTITLEMENT_IDENTIFIER] !== undefined;

  const appUserId = appUserIdQuery.data;
  const identityReady = !!appUserId && !appUserId.startsWith("$RCAnonymousID:");

  return {
    customerInfo: customerInfoQuery.data,
    offerings: offeringsQuery.data,
    isSubscribed,
    identityReady,
    isLoading: customerInfoQuery.isLoading || offeringsQuery.isLoading,
    purchase: purchaseMutation.mutateAsync,
    restore: restoreMutation.mutateAsync,
    isPurchasing: purchaseMutation.isPending,
    isRestoring: restoreMutation.isPending,
  };
}

type SubscriptionContextValue = ReturnType<typeof useSubscriptionContext>;
const Context = createContext<SubscriptionContextValue | null>(null);

export function SubscriptionProvider({ children }: { children: React.ReactNode }) {
  const value = useSubscriptionContext();
  return <Context.Provider value={value}>{children}</Context.Provider>;
}

export function useSubscription() {
  const ctx = useContext(Context);
  if (!ctx) throw new Error("useSubscription must be used within a SubscriptionProvider");
  return ctx;
}

export { Purchases };
