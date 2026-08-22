import { Ionicons } from "@expo/vector-icons";
import { Image } from "expo-image";
import { useFocusEffect, useRouter } from "expo-router";
import { useCallback, useState } from "react";
import { FlatList, RefreshControl, StyleSheet, Text, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Reel } from "@/src/api";
import PrimaryButton from "@/src/components/PrimaryButton";
import ReelCard from "@/src/components/ReelCard";
import { colors, font, spacing } from "@/src/theme";

const EMPTY_IMG =
  "https://images.pexels.com/photos/31050644/pexels-photo-31050644.jpeg?auto=compress&cs=tinysrgb&dpr=2&h=650&w=940";

export default function LibraryScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const [reels, setReels] = useState<Reel[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    try {
      const data = await api.listReels();
      setReels(data);
    } catch {
      // keep last state
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  }, []);

  useFocusEffect(
    useCallback(() => {
      load();
      const anyGenerating = reels.some(
        (r) => r.status !== "ready" && r.status !== "failed",
      );
      const interval = anyGenerating ? setInterval(load, 3000) : null;
      return () => {
        if (interval) clearInterval(interval);
      };
    }, [load, reels.length, reels.map((r) => r.status).join(",")]),
  );

  const empty = !loading && reels.length === 0;

  return (
    <View style={styles.root}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.sm }]}>
        <Text style={styles.title}>LIBRARY</Text>
        <Text style={styles.count}>{reels.length} reels</Text>
      </View>

      {empty ? (
        <View style={styles.empty}>
          <Image source={{ uri: EMPTY_IMG }} style={styles.emptyImg} contentFit="cover" />
          <Ionicons name="film-outline" size={40} color={colors.onSurfaceSecondary} />
          <Text style={styles.emptyTitle}>No reels yet</Text>
          <Text style={styles.emptySub}>Turn any topic or script into a scroll-stopping vertical video.</Text>
          <PrimaryButton
            testID="empty-create-button"
            label="Create your first reel"
            icon="add"
            onPress={() => router.push("/(tabs)")}
            style={{ marginTop: spacing.lg, alignSelf: "stretch" }}
          />
        </View>
      ) : (
        <FlatList
          testID="reels-grid"
          data={reels}
          keyExtractor={(r) => r.id}
          numColumns={2}
          columnWrapperStyle={{ gap: spacing.md }}
          contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + spacing.xl, gap: spacing.md }}
          showsVerticalScrollIndicator={false}
          refreshControl={
            <RefreshControl
              refreshing={refreshing}
              onRefresh={() => {
                setRefreshing(true);
                load();
              }}
              tintColor={colors.brand}
            />
          }
          renderItem={({ item }) => (
            <ReelCard reel={item} onPress={() => router.push(`/reel/${item.id}`)} />
          )}
        />
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  header: {
    flexDirection: "row",
    alignItems: "flex-end",
    justifyContent: "space-between",
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  title: { fontFamily: font.display, fontSize: 26, color: colors.onSurface, letterSpacing: 1 },
  count: { fontFamily: font.bodyMed, fontSize: 13, color: colors.onSurfaceSecondary, paddingBottom: 3 },
  empty: { flex: 1, alignItems: "center", justifyContent: "center", padding: spacing.xl },
  emptyImg: {
    width: 120,
    height: 120,
    borderRadius: 60,
    marginBottom: spacing.lg,
    opacity: 0.55,
  },
  emptyTitle: { fontFamily: font.display, fontSize: 24, color: colors.onSurface, marginTop: spacing.sm },
  emptySub: {
    fontFamily: font.body,
    fontSize: 14,
    color: colors.onSurfaceSecondary,
    textAlign: "center",
    marginTop: spacing.sm,
    lineHeight: 20,
  },
});
