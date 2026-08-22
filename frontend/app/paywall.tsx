import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import { useMemo, useState } from "react";
import {
  ActivityIndicator,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import type { PurchasesPackage } from "react-native-purchases";

import { rcEnabled, useSubscription } from "@/src/revenuecat";
import { haptic } from "@/src/haptics";
import { colors, font, radius, spacing } from "@/src/theme";

const PERKS = [
  { icon: "infinite", text: "Unlimited reels — no 3-reel cap" },
  { icon: "flash", text: "Batch generate up to 12 at once" },
  { icon: "sparkles", text: "AI visuals, voices & series continuity" },
  { icon: "cloud-done", text: "Priority rendering on the shared engine" },
];

export default function PaywallScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const {
    offerings,
    isSubscribed,
    identityReady,
    isLoading,
    purchase,
    restore,
    isPurchasing,
    isRestoring,
  } = useSubscription();

  const [pending, setPending] = useState<PurchasesPackage | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  const packages: PurchasesPackage[] = useMemo(
    () => offerings?.current?.availablePackages ?? [],
    [offerings],
  );

  const flash = (m: string) => { setToast(m); setTimeout(() => setToast(null), 2400); };

  const confirmPurchase = async () => {
    if (!pending) return;
    const pkg = pending;
    setPending(null);
    setError(null);
    try {
      await purchase(pkg);
      haptic.success();
      flash("You're subscribed 🎉");
      setTimeout(() => router.back(), 900);
    } catch (e: any) {
      if (e?.userCancelled) return; // silent
      haptic.error();
      setError(e?.message === "identity_not_ready"
        ? "We couldn't link your account yet. Please try again in a moment."
        : (e?.message || "Purchase failed. Please try again."));
    }
  };

  const onRestore = async () => {
    setError(null);
    try {
      await restore();
      haptic.success();
      flash("Purchases restored");
    } catch (e: any) {
      haptic.error();
      setError(e?.message || "Nothing to restore.");
    }
  };

  const busy = isPurchasing || isRestoring;

  return (
    <View style={styles.root}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.xs }]}>
        <Pressable testID="paywall-close" onPress={() => router.back()} style={styles.iconBtn}>
          <Ionicons name="close" size={24} color={colors.onSurface} />
        </Pressable>
        <Text style={styles.headerTitle}>Go Pro</Text>
        <View style={styles.iconBtn} />
      </View>

      <ScrollView
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + spacing.xxxl }}
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.hero}>
          <View style={styles.heroBadge}><Ionicons name="rocket" size={26} color={colors.brand} /></View>
          <Text style={styles.heroTitle}>Create without limits</Text>
          <Text style={styles.heroSub}>Unlock unlimited AI reels on the built-in engine — no API keys needed.</Text>
        </View>

        <View style={styles.perks}>
          {PERKS.map((p) => (
            <View key={p.text} style={styles.perkRow}>
              <Ionicons name={p.icon as any} size={18} color={colors.brand} />
              <Text style={styles.perkTxt}>{p.text}</Text>
            </View>
          ))}
        </View>

        {isSubscribed ? (
          <View testID="paywall-active" style={styles.activeCard}>
            <Ionicons name="checkmark-circle" size={20} color={colors.success} />
            <Text style={styles.activeTxt}>You're subscribed — enjoy unlimited reels!</Text>
          </View>
        ) : isLoading ? (
          <View style={styles.loadingBox}><ActivityIndicator color={colors.brand} /></View>
        ) : packages.length === 0 ? (
          <View testID="paywall-unavailable" style={styles.unavailBox}>
            <Text style={styles.unavailTxt}>
              Subscription options are unavailable right now. Please try again later.
            </Text>
          </View>
        ) : (
          <View style={{ marginTop: spacing.xl }}>
            {packages.map((pkg) => (
              <Pressable
                key={pkg.identifier}
                testID={`plan-${pkg.identifier}`}
                disabled={busy || !identityReady}
                onPress={() => { haptic.select(); setError(null); setPending(pkg); }}
                style={[styles.planCard, (busy || !identityReady) && { opacity: 0.6 }]}
              >
                <View style={{ flex: 1 }}>
                  <Text style={styles.planName}>{pkg.product.title || pkg.identifier}</Text>
                  {!!pkg.product.description && (
                    <Text style={styles.planDesc} numberOfLines={2}>{pkg.product.description}</Text>
                  )}
                </View>
                <Text style={styles.planPrice}>{pkg.product.priceString}</Text>
              </Pressable>
            ))}

            {!identityReady && (
              <Text testID="paywall-identity-warn" style={styles.warnTxt}>
                Preparing your account… hold on a second, then tap a plan.
              </Text>
            )}

            <Pressable testID="paywall-restore" onPress={onRestore} disabled={busy} style={styles.restoreBtn}>
              {isRestoring
                ? <ActivityIndicator color={colors.onSurfaceSecondary} />
                : <Text style={styles.restoreTxt}>Restore purchases</Text>}
            </Pressable>

            {rcEnabled && __DEV__ && (
              <Text style={styles.simTxt}>Test mode · purchases here are simulated (RevenueCat Test Store)</Text>
            )}
          </View>
        )}

        {!!error && (
          <View testID="paywall-error" style={styles.errBox}>
            <Ionicons name="alert-circle" size={16} color={colors.error} />
            <Text style={styles.errTxt}>{error}</Text>
          </View>
        )}

        <Text style={styles.legal}>
          Subscriptions auto-renew until cancelled. Manage or cancel anytime in your App Store / Play Store account.
        </Text>
      </ScrollView>

      {/* Custom confirm modal (Alert is unreliable per RevenueCat guidance) */}
      <Modal visible={!!pending} transparent animationType="fade" onRequestClose={() => setPending(null)}>
        <Pressable style={styles.backdrop} onPress={() => setPending(null)}>
          <Pressable style={styles.confirmCard} onPress={() => {}}>
            <Text style={styles.confirmTitle}>Confirm subscription</Text>
            <Text style={styles.confirmBody}>
              {pending
                ? `Subscribe to ${pending.product.title || "Pro"} for ${pending.product.priceString}?`
                : ""}
            </Text>
            <View style={styles.confirmRow}>
              <Pressable testID="confirm-cancel" onPress={() => setPending(null)} style={[styles.confirmBtn, styles.confirmGhost]}>
                <Text style={styles.confirmGhostTxt}>Cancel</Text>
              </Pressable>
              <Pressable testID="confirm-buy" onPress={confirmPurchase} disabled={isPurchasing} style={[styles.confirmBtn, styles.confirmPrimary]}>
                {isPurchasing
                  ? <ActivityIndicator color={colors.onBrand} />
                  : <Text style={styles.confirmPrimaryTxt}>Subscribe</Text>}
              </Pressable>
            </View>
          </Pressable>
        </Pressable>
      </Modal>

      {!!toast && (
        <View style={[styles.toast, { bottom: insets.bottom + spacing.xl }]} testID="paywall-toast">
          <Text style={styles.toastTxt}>{toast}</Text>
        </View>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: spacing.md, paddingBottom: spacing.sm, borderBottomWidth: 1, borderBottomColor: colors.border },
  iconBtn: { width: 40, height: 40, borderRadius: radius.md, alignItems: "center", justifyContent: "center" },
  headerTitle: { flex: 1, textAlign: "center", fontFamily: font.display, fontSize: 22, color: colors.onSurface, letterSpacing: 0.5 },
  hero: { alignItems: "center", marginTop: spacing.lg },
  heroBadge: { width: 64, height: 64, borderRadius: 32, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center", marginBottom: spacing.md },
  heroTitle: { fontFamily: font.display, fontSize: 30, color: colors.onSurface, textAlign: "center", letterSpacing: 0.4 },
  heroSub: { fontFamily: font.body, fontSize: 14, color: colors.onSurfaceSecondary, textAlign: "center", marginTop: spacing.xs, lineHeight: 20, paddingHorizontal: spacing.md },
  perks: { marginTop: spacing.xl, gap: spacing.md },
  perkRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  perkTxt: { flex: 1, fontFamily: font.bodyMed, fontSize: 15, color: colors.onSurface },
  loadingBox: { marginTop: spacing.xxl, alignItems: "center" },
  unavailBox: { marginTop: spacing.xl, padding: spacing.lg, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surfaceSecondary },
  unavailTxt: { fontFamily: font.bodyMed, fontSize: 14, color: colors.onSurfaceSecondary, textAlign: "center", lineHeight: 20 },
  activeCard: { marginTop: spacing.xl, flexDirection: "row", alignItems: "center", gap: spacing.sm, padding: spacing.lg, borderRadius: radius.md, backgroundColor: "rgba(34,197,94,0.14)" },
  activeTxt: { flex: 1, fontFamily: font.bodyBold, fontSize: 15, color: colors.success },
  planCard: { flexDirection: "row", alignItems: "center", gap: spacing.md, padding: spacing.lg, borderRadius: radius.lg, borderWidth: 1.5, borderColor: colors.brand, backgroundColor: colors.surfaceSecondary, marginBottom: spacing.md },
  planName: { fontFamily: font.bodyBold, fontSize: 17, color: colors.onSurface },
  planDesc: { fontFamily: font.body, fontSize: 12, color: colors.onSurfaceSecondary, marginTop: 2 },
  planPrice: { fontFamily: font.display, fontSize: 22, color: colors.brand },
  warnTxt: { fontFamily: font.bodyMed, fontSize: 12, color: colors.onSurfaceSecondary, textAlign: "center", marginBottom: spacing.sm },
  restoreBtn: { height: 48, alignItems: "center", justifyContent: "center", marginTop: spacing.xs },
  restoreTxt: { fontFamily: font.bodySemi, fontSize: 14, color: colors.onSurfaceSecondary, textDecorationLine: "underline" },
  simTxt: { fontFamily: font.body, fontSize: 11, color: colors.onSurfaceSecondary, textAlign: "center", marginTop: spacing.xs },
  errBox: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginTop: spacing.lg, padding: spacing.md, borderRadius: radius.md, backgroundColor: "rgba(239,68,68,0.12)" },
  errTxt: { flex: 1, fontFamily: font.bodyMed, fontSize: 13, color: colors.error },
  legal: { fontFamily: font.body, fontSize: 11, color: colors.onSurfaceSecondary, textAlign: "center", marginTop: spacing.xl, lineHeight: 16, paddingHorizontal: spacing.md },
  backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.6)", alignItems: "center", justifyContent: "center", padding: spacing.xl },
  confirmCard: { width: "100%", maxWidth: 360, borderRadius: radius.lg, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, padding: spacing.lg },
  confirmTitle: { fontFamily: font.display, fontSize: 20, color: colors.onSurface },
  confirmBody: { fontFamily: font.body, fontSize: 14, color: colors.onSurfaceSecondary, marginTop: spacing.sm, lineHeight: 20 },
  confirmRow: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.lg },
  confirmBtn: { flex: 1, height: 48, borderRadius: radius.md, alignItems: "center", justifyContent: "center" },
  confirmGhost: { backgroundColor: colors.surfaceTertiary },
  confirmGhostTxt: { fontFamily: font.bodySemi, fontSize: 15, color: colors.onSurface },
  confirmPrimary: { backgroundColor: colors.brand },
  confirmPrimaryTxt: { fontFamily: font.bodyBold, fontSize: 15, color: colors.onBrand },
  toast: { position: "absolute", alignSelf: "center", paddingHorizontal: spacing.lg, height: 44, borderRadius: radius.pill, backgroundColor: colors.surfaceTertiary, alignItems: "center", justifyContent: "center" },
  toastTxt: { fontFamily: font.bodySemi, fontSize: 14, color: colors.onSurface },
});
