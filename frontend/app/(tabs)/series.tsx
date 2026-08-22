import { Ionicons } from "@expo/vector-icons";
import { useFocusEffect, useRouter } from "expo-router";
import { useCallback, useState } from "react";
import { FlatList, Pressable, RefreshControl, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Series } from "@/src/api";
import PrimaryButton from "@/src/components/PrimaryButton";
import { haptic } from "@/src/haptics";
import { useHidingTabBar } from "@/src/tabbar";
import { colors, font, radius, spacing } from "@/src/theme";

export default function SeriesScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const [series, setSeries] = useState<Series[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const scrollHide = useHidingTabBar();

  const load = useCallback(async () => {
    try {
      setSeries(await api.listSeries());
    } catch {
      // keep last
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(useCallback(() => { load(); }, [load]));

  const empty = !loading && series.length === 0;

  return (
    <View style={styles.root}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.sm }]}>
        <View>
          <Text style={styles.title}>SERIES</Text>
          <Text style={styles.sub}>Recurring characters · continuing story</Text>
        </View>
        <View style={styles.headerActions}>
          <Pressable
            testID="settings-button"
            onPress={() => { haptic.select(); router.push("/settings"); }}
            style={styles.gearBtn}
          >
            <Ionicons name="settings-outline" size={20} color={colors.onSurface} />
          </Pressable>
          <Pressable
            testID="new-series-button"
            onPress={() => { haptic.select(); router.push("/series/new"); }}
            style={styles.newBtn}
          >
            <Ionicons name="add" size={18} color={colors.onBrand} />
            <Text style={styles.newTxt}>New</Text>
          </Pressable>
        </View>
      </View>

      {empty ? (
        <View style={styles.empty}>
          <View style={styles.emptyIcon}>
            <Ionicons name="film-outline" size={34} color={colors.brand} />
          </View>
          <Text style={styles.emptyTitle}>Start a series</Text>
          <Text style={styles.emptySub}>
            Keep the same characters, tone and storyline across every episode. Great for
            multi-part stories, lore drops, and cliffhangers.
          </Text>
          <PrimaryButton
            testID="empty-new-series-button"
            label="Create a series"
            icon="add"
            onPress={() => router.push("/series/new")}
            style={{ marginTop: spacing.lg, alignSelf: "stretch" }}
          />
        </View>
      ) : (
        <FlatList
          testID="series-list"
          data={series}
          keyExtractor={(s) => s.id}
          onScroll={scrollHide.onScroll}
          scrollEventThrottle={scrollHide.scrollEventThrottle}
          contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + 96, gap: spacing.md }}
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl refreshing={refreshing} onRefresh={() => { setRefreshing(true); load(); }} tintColor={colors.brand} />
          }
          renderItem={({ item }) => (
            <Pressable
              testID={`series-card-${item.id}`}
              onPress={() => { haptic.select(); router.push(`/series/${item.id}`); }}
              style={({ pressed }) => [styles.card, pressed && { opacity: 0.85 }]}
            >
              <View style={styles.cardTop}>
                <Text style={styles.cardTitle} numberOfLines={1}>{item.title}</Text>
                <View style={styles.epBadge}>
                  <Text style={styles.epBadgeTxt}>{item.episode_count} ep{item.episode_count === 1 ? "" : "s"}</Text>
                </View>
              </View>
              {!!item.premise && <Text style={styles.cardPremise} numberOfLines={2}>{item.premise}</Text>}
              <View style={styles.cardMetaRow}>
                {!!item.tone && (
                  <View style={styles.metaChip}>
                    <Ionicons name="color-wand-outline" size={12} color={colors.onSurfaceSecondary} />
                    <Text style={styles.metaTxt} numberOfLines={1}>{item.tone}</Text>
                  </View>
                )}
                <View style={styles.metaChip}>
                  <Ionicons name="people-outline" size={12} color={colors.onSurfaceSecondary} />
                  <Text style={styles.metaTxt}>{item.characters.length} character{item.characters.length === 1 ? "" : "s"}</Text>
                </View>
              </View>
            </Pressable>
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  header: {
    flexDirection: "row", alignItems: "flex-end", justifyContent: "space-between",
    paddingHorizontal: spacing.lg, paddingBottom: spacing.md,
    borderBottomWidth: 1, borderBottomColor: colors.border,
  },
  title: { fontFamily: font.display, fontSize: 26, color: colors.onSurface, letterSpacing: 1 },
  sub: { fontFamily: font.body, fontSize: 12, color: colors.onSurfaceSecondary, marginTop: 2 },
  newBtn: {
    flexDirection: "row", alignItems: "center", gap: 4,
    paddingHorizontal: spacing.md, height: 38, borderRadius: radius.pill,
    backgroundColor: colors.brandPrimary,
  },
  newTxt: { fontFamily: font.bodyBold, fontSize: 14, color: colors.onBrand },
  headerActions: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  gearBtn: { width: 38, height: 38, borderRadius: 19, alignItems: "center", justifyContent: "center", backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border },
  empty: { flex: 1, alignItems: "center", justifyContent: "center", padding: spacing.xl },
  emptyIcon: {
    width: 72, height: 72, borderRadius: 36, backgroundColor: colors.brandTertiary,
    borderWidth: 1, borderColor: colors.brandPrimary, alignItems: "center", justifyContent: "center",
  },
  emptyTitle: { fontFamily: font.display, fontSize: 24, color: colors.onSurface, marginTop: spacing.lg },
  emptySub: { fontFamily: font.body, fontSize: 14, color: colors.onSurfaceSecondary, textAlign: "center", marginTop: spacing.sm, lineHeight: 20 },
  card: {
    backgroundColor: colors.surfaceSecondary, borderRadius: radius.lg,
    borderWidth: 1, borderColor: colors.border, padding: spacing.lg,
  },
  cardTop: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: spacing.sm },
  cardTitle: { flex: 1, fontFamily: font.display, fontSize: 20, color: colors.onSurface, letterSpacing: 0.3 },
  epBadge: { paddingHorizontal: spacing.sm, height: 24, borderRadius: radius.pill, backgroundColor: colors.brandTertiary, alignItems: "center", justifyContent: "center" },
  epBadgeTxt: { fontFamily: font.bodyBold, fontSize: 11, color: colors.onBrandTertiary },
  cardPremise: { fontFamily: font.body, fontSize: 13, color: colors.onSurfaceSecondary, marginTop: spacing.sm, lineHeight: 19 },
  cardMetaRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm, marginTop: spacing.md },
  metaChip: { flexDirection: "row", alignItems: "center", gap: 5, maxWidth: "70%" },
  metaTxt: { fontFamily: font.bodyMed, fontSize: 12, color: colors.onSurfaceSecondary },
});
