import { Ionicons } from "@expo/vector-icons";
import * as WebBrowser from "expo-web-browser";
import { useCallback, useState } from "react";
import { Alert, Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { api, AppSettings } from "@/src/api";
import PrimaryButton from "@/src/components/PrimaryButton";
import { haptic } from "@/src/haptics";
import { colors, font, radius, spacing } from "@/src/theme";

type Props = {
  settings: AppSettings | null;
  setSettings: (s: AppSettings) => void;
  refreshAuth: () => Promise<any> | any;
  flash: (m: string) => void;
};

export default function SettingsExtras({ settings, setSettings, refreshAuth, flash }: Props) {
  const [elKey, setElKey] = useState("");
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [test, setTest] = useState<{ ok: boolean; message: string } | null>(null);
  const [connecting, setConnecting] = useState<"youtube" | "instagram" | null>(null);

  const saveEl = useCallback(async () => {
    if (!elKey.trim()) return;
    setSaving(true);
    try {
      const s = await api.updateSettings({ elevenlabs_key: elKey.trim() });
      setSettings(s);
      await refreshAuth();
      setElKey("");
      haptic.success();
      flash("ElevenLabs key saved ✓");
    } catch (e: any) {
      haptic.error();
      flash(e.message || "Couldn't save ElevenLabs key");
    } finally {
      setSaving(false);
    }
  }, [elKey, setSettings, refreshAuth, flash]);

  const testEl = useCallback(async () => {
    if (!elKey.trim()) return;
    setTesting(true);
    try {
      const res = await api.testKeys({ elevenlabs_key: elKey.trim() });
      const r = res.elevenlabs || null;
      setTest(r);
      (r?.ok ? haptic.success : haptic.error)();
    } catch (e: any) {
      haptic.error();
      flash(e.message || "Couldn't test key");
    } finally {
      setTesting(false);
    }
  }, [elKey, flash]);

  const clearEl = useCallback(() => {
    Alert.alert("Remove ElevenLabs key?", "ElevenLabs voices will fall back to a similar OpenAI voice.", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Remove", style: "destructive", onPress: async () => {
          const s = await api.updateSettings({ elevenlabs_key: "" });
          setSettings(s); await refreshAuth(); haptic.medium(); flash("Key removed");
        },
      },
    ]);
  }, [setSettings, refreshAuth, flash]);

  const connect = useCallback(async (platform: "youtube" | "instagram") => {
    setConnecting(platform);
    try {
      const start = platform === "youtube" ? await api.connectYoutube() : await api.connectInstagram();
      if (!start.configured || !start.url) {
        flash(start.message || "Connect isn't set up on the server yet. Native share still works.");
        return;
      }
      const result = await WebBrowser.openAuthSessionAsync(start.url, "frontend://connect");
      if (result.type === "success" || result.type === "dismiss") {
        const s = await api.getSettings();
        setSettings(s);
        await refreshAuth();
        const ok = platform === "youtube" ? s.youtube_connected : s.instagram_connected;
        if (ok) { haptic.success(); flash(`${platform === "youtube" ? "YouTube" : "Instagram"} connected ✓`); }
        else flash("Window closed — tap Connect again if it didn't finish.");
      }
    } catch (e: any) {
      haptic.error();
      flash(e.message || "Couldn't connect.");
    } finally {
      setConnecting(null);
    }
  }, [setSettings, refreshAuth, flash]);

  const disconnect = useCallback((platform: "youtube" | "instagram") => {
    Alert.alert(`Disconnect ${platform}?`, "You can reconnect anytime. Native share still works.", [
      { text: "Cancel", style: "cancel" },
      {
        text: "Disconnect", style: "destructive", onPress: async () => {
          const s = platform === "youtube" ? await api.disconnectYoutube() : await api.disconnectInstagram();
          setSettings(s); await refreshAuth(); haptic.medium(); flash("Disconnected");
        },
      },
    ]);
  }, [setSettings, refreshAuth, flash]);

  return (
    <>
      <View style={[styles.keyRow, { marginTop: spacing.lg }]}>
        <Text style={styles.keyLabel}>ElevenLabs key</Text>
        <View style={[styles.statusPill, settings?.elevenlabs_key_set ? styles.pillOn : styles.pillOff]}>
          <Text style={[styles.pillTxt, settings?.elevenlabs_key_set ? styles.pillTxtOn : styles.pillTxtOff]}>
            {settings?.elevenlabs_key_set ? `Yours · ${settings.elevenlabs_key_masked}` : "Not set — OpenAI fallback"}
          </Text>
        </View>
      </View>
      <Text style={styles.keyHint}>Optional. Pick ElevenLabs voices on Create. Leave blank to keep using OpenAI TTS.</Text>
      <View style={styles.inputRow}>
        <TextInput
          testID="elevenlabs-key-input"
          value={elKey}
          onChangeText={setElKey}
          placeholder="sk_..."
          placeholderTextColor={colors.onSurfaceSecondary}
          autoCapitalize="none"
          secureTextEntry
          style={styles.input}
        />
        {settings?.elevenlabs_key_set && (
          <Pressable testID="clear-elevenlabs" onPress={clearEl} style={styles.clearBtn}>
            <Ionicons name="trash-outline" size={16} color={colors.onSurfaceSecondary} />
          </Pressable>
        )}
      </View>
      {!!test && (
        <View style={styles.resultRow}>
          <Ionicons name={test.ok ? "checkmark-circle" : "close-circle"} size={14} color={test.ok ? colors.success : colors.error} />
          <Text style={[styles.resTxt, { color: test.ok ? colors.success : colors.error }]}>{test.message}</Text>
        </View>
      )}
      <View style={styles.rowBtns}>
        <PrimaryButton
          testID="test-elevenlabs-button"
          variant="ghost"
          label="Test"
          icon="flask-outline"
          loading={testing}
          disabled={!elKey.trim()}
          onPress={testEl}
          style={{ flex: 1 }}
        />
        <PrimaryButton
          testID="save-elevenlabs-button"
          label="Save ElevenLabs"
          icon="key-outline"
          loading={saving}
          disabled={!elKey.trim()}
          onPress={saveEl}
          style={{ flex: 1 }}
        />
      </View>

      <Text style={styles.section}>CONNECTED ACCOUNTS</Text>
      <Text style={styles.keyHint}>Post a finished reel from its page. Tokens stay encrypted on the server. Native share sheet still works.</Text>
      <AccountRow
        testID="connect-youtube"
        label="YouTube"
        connected={!!settings?.youtube_connected}
        detail={settings?.youtube_channel || ""}
        loading={connecting === "youtube"}
        onConnect={() => connect("youtube")}
        onDisconnect={() => disconnect("youtube")}
      />
      <AccountRow
        testID="connect-instagram"
        label="Instagram"
        connected={!!settings?.instagram_connected}
        detail={settings?.instagram_username || ""}
        loading={connecting === "instagram"}
        onConnect={() => connect("instagram")}
        onDisconnect={() => disconnect("instagram")}
      />
    </>
  );
}

function AccountRow({ testID, label, connected, detail, loading, onConnect, onDisconnect }: {
  testID: string; label: string; connected: boolean; detail: string; loading: boolean;
  onConnect: () => void; onDisconnect: () => void;
}) {
  return (
    <View style={styles.acct} testID={testID}>
      <View style={{ flex: 1 }}>
        <Text style={styles.acctLabel}>{label}</Text>
        <Text style={styles.keyHint}>{connected ? (detail || "Connected") : "Not connected"}</Text>
      </View>
      <Pressable
        testID={`${testID}-btn`}
        onPress={connected ? onDisconnect : onConnect}
        style={[styles.acctBtn, connected && styles.acctBtnOn]}
      >
        <Text style={[styles.acctBtnTxt, connected && styles.acctBtnTxtOn]}>{loading ? "…" : connected ? "Disconnect" : "Connect"}</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  keyRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  keyLabel: { fontFamily: font.bodyBold, fontSize: 13, color: colors.onSurface },
  keyHint: { fontFamily: font.body, fontSize: 12, color: colors.onSurfaceSecondary, marginTop: 4, marginBottom: spacing.sm, lineHeight: 17 },
  statusPill: { borderRadius: 99, paddingHorizontal: 8, paddingVertical: 3 },
  pillOn: { backgroundColor: "rgba(34,197,94,0.14)" },
  pillOff: { backgroundColor: colors.surfaceTertiary },
  pillTxt: { fontFamily: font.bodySemi, fontSize: 11 },
  pillTxtOn: { color: colors.success },
  pillTxtOff: { color: colors.onSurfaceSecondary },
  inputRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  input: {
    flex: 1, height: 48, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border,
    backgroundColor: colors.surfaceSecondary, color: colors.onSurface, paddingHorizontal: spacing.md,
    fontFamily: font.body, fontSize: 14,
  },
  clearBtn: { width: 48, height: 48, borderRadius: radius.md, alignItems: "center", justifyContent: "center", backgroundColor: colors.surfaceSecondary },
  resultRow: { flexDirection: "row", alignItems: "center", gap: 6, marginTop: spacing.sm },
  resTxt: { fontFamily: font.bodyMed, fontSize: 12, flex: 1 },
  rowBtns: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.md },
  section: { fontFamily: font.bodyBold, fontSize: 12, letterSpacing: 1.2, color: colors.onSurfaceSecondary, marginTop: spacing.xxl, marginBottom: spacing.sm },
  acct: {
    flexDirection: "row", alignItems: "center", gap: spacing.md, marginTop: spacing.sm,
    padding: spacing.md, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surfaceSecondary,
  },
  acctLabel: { fontFamily: font.bodyBold, fontSize: 14, color: colors.onSurface },
  acctBtn: { height: 36, paddingHorizontal: spacing.md, borderRadius: radius.md, borderWidth: 1, borderColor: colors.brand, alignItems: "center", justifyContent: "center" },
  acctBtnOn: { borderColor: colors.border },
  acctBtnTxt: { fontFamily: font.bodySemi, fontSize: 12, color: colors.brand },
  acctBtnTxtOn: { color: colors.onSurfaceSecondary },
});
