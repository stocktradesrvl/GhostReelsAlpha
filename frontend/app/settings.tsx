import { BottomSheetModal } from "@gorhom/bottom-sheet";
import { Ionicons } from "@expo/vector-icons";
import { useRouter } from "expo-router";
import * as WebBrowser from "expo-web-browser";
import { useCallback, useEffect, useRef, useState } from "react";
import { ActivityIndicator, Alert, Linking, Modal, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { KeyboardAwareScrollView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, AppSettings, Config, PRIVACY_POLICY_URL, TERMS_OF_SERVICE_URL, SUPPORT_EMAIL } from "@/src/api";
import { useAuth } from "@/src/auth";
import OptionSheet, { SheetOption } from "@/src/components/OptionSheet";
import OutroSheet from "@/src/components/OutroSheet";
import PrimaryButton from "@/src/components/PrimaryButton";
import { loadDefaults, saveDefaults, StudioDefaults } from "@/src/defaults";
import { haptic } from "@/src/haptics";
import { loadPresets, Preset, savePresets } from "@/src/presets";
import { colors, font, radius, spacing } from "@/src/theme";

const DURATIONS = [15, 30, 60];

export default function SettingsScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const { user, signOut, refresh: refreshAuth } = useAuth();

  const [config, setConfig] = useState<Config | null>(null);
  const [settings, setSettings] = useState<AppSettings | null>(null);
  const [openaiKey, setOpenaiKey] = useState("");
  const [googleKey, setGoogleKey] = useState("");
  const [savingKeys, setSavingKeys] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ openai?: { ok: boolean; message: string }; google?: { ok: boolean; message: string } }>({});

  const [defaults, setDefaults] = useState<StudioDefaults>({});
  const [brandHandle, setBrandHandle] = useState("");
  const [savingBrand, setSavingBrand] = useState(false);
  const [savingDefaults, setSavingDefaults] = useState(false);
  const [presets, setPresets] = useState<Preset[]>([]);
  const [toast, setToast] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const openPrivacy = useCallback(async () => {
    haptic.select();
    try { await WebBrowser.openBrowserAsync(PRIVACY_POLICY_URL); }
    catch { Linking.openURL(PRIVACY_POLICY_URL); }
  }, []);

  const openTerms = useCallback(async () => {
    haptic.select();
    try { await WebBrowser.openBrowserAsync(TERMS_OF_SERVICE_URL); }
    catch { Linking.openURL(TERMS_OF_SERVICE_URL); }
  }, []);

  const openSupport = useCallback(() => {
    haptic.select();
    const subject = encodeURIComponent("GhostReelsAlpha support");
    Linking.openURL(`mailto:${SUPPORT_EMAIL}?subject=${subject}`);
  }, []);

  const doDeleteAccount = useCallback(async () => {
    setDeleting(true);
    try {
      await api.deleteAccount();
      haptic.success();
      setConfirmDelete(false);
      await signOut();
    } catch {
      setDeleting(false);
      haptic.error();
      setToast("Couldn't delete your account. Please try again.");
      setTimeout(() => setToast(null), 2500);
    }
  }, [signOut]);

  const voiceSheet = useRef<BottomSheetModal>(null);
  const musicSheet = useRef<BottomSheetModal>(null);
  const outroSheet = useRef<BottomSheetModal>(null);

  useEffect(() => {
    if (!user) return; // wait for auth token hydration before hitting authed endpoints
    api.getConfig().then(setConfig).catch(() => {});
    api.getSettings().then((s) => { setSettings(s); setBrandHandle(s.brand_handle || ""); }).catch(() => {});
    loadDefaults().then((d) => setDefaults(d)).catch(() => {});
    loadPresets().then(setPresets).catch(() => {});
  }, [user]);

  const flash = useCallback((m: string) => { setToast(m); setTimeout(() => setToast(null), 2200); }, []);

  const testKeys = useCallback(async () => {
    setTesting(true);
    setTestResult({});
    try {
      const payload: any = {};
      if (openaiKey.trim()) payload.openai_key = openaiKey.trim();
      if (googleKey.trim()) payload.google_key = googleKey.trim();
      const res = await api.testKeys(payload);
      setTestResult(res);
      const vals = Object.values(res);
      (vals.length && vals.every((r: any) => r.ok) ? haptic.success : haptic.error)();
    } catch (e: any) {
      haptic.error();
      flash(e.message || "Couldn't test keys");
    } finally {
      setTesting(false);
    }
  }, [openaiKey, googleKey, flash]);

  const voice = config?.voices.find((v) => v.id === (defaults.voice_id || "onyx"));
  const music = config?.music_tracks.find((m) => m.id === (defaults.music_id || "none"));
  const voiceOptions: SheetOption[] = config?.voices.map((v) => ({ id: v.id, title: v.name, subtitle: v.tagline })) || [];
  const musicOptions: SheetOption[] = config?.music_tracks.map((m) => ({ id: m.id, title: m.name })) || [];

  const saveKeys = useCallback(async () => {
    setSavingKeys(true);
    try {
      const payload: any = {};
      if (openaiKey.trim()) payload.openai_key = openaiKey.trim();
      if (googleKey.trim()) payload.google_key = googleKey.trim();
      const s = await api.updateSettings(payload);
      setSettings(s);
      await refreshAuth();
      setOpenaiKey(""); setGoogleKey("");
      haptic.success();
      flash("Keys saved ✓");
    } catch (e: any) {
      haptic.error();
      flash(e.message || "Couldn't save keys");
    } finally {
      setSavingKeys(false);
    }
  }, [openaiKey, googleKey, flash, refreshAuth]);

  const clearKey = useCallback((which: "openai" | "google") => {
    Alert.alert("Remove key?", `The app will use built-in credits for ${which === "openai" ? "text & voice" : "AI images"}.`, [
      { text: "Cancel", style: "cancel" },
      {
        text: "Remove", style: "destructive", onPress: async () => {
          const payload = which === "openai" ? { openai_key: "" } : { google_key: "" };
          const s = await api.updateSettings(payload);
          setSettings(s); await refreshAuth(); haptic.medium(); flash("Key removed");
        },
      },
    ]);
  }, [flash, refreshAuth]);

  const setKeyMode = useCallback(async (mode: "own" | "builtin") => {
    if (settings?.key_mode === mode) return;
    haptic.select();
    // optimistic
    setSettings((prev) => (prev ? { ...prev, key_mode: mode } : prev));
    try {
      const s = await api.updateSettings({ key_mode: mode });
      setSettings(s);
      await refreshAuth();
      flash(mode === "own" ? "Using your own keys ✓" : "Using built-in credits ✓");
    } catch (e: any) {
      haptic.error();
      flash(e.message || "Couldn't switch AI engine");
      api.getSettings().then(setSettings).catch(() => {});
    }
  }, [settings?.key_mode, flash, refreshAuth]);

  const persistDefaults = useCallback(async (next: StudioDefaults) => {
    setDefaults(next);
    setSavingDefaults(true);
    await saveDefaults(next);
    setSavingDefaults(false);
    haptic.light();
  }, []);

  const saveBrand = useCallback(async () => {
    setSavingBrand(true);
    try {
      await api.updateSettings({ brand_handle: brandHandle.trim() });
      const next = { ...defaults, watermark: brandHandle.trim() };
      await saveDefaults(next); setDefaults(next);
      haptic.success(); flash("Brand saved ✓");
    } catch (e: any) {
      haptic.error(); flash(e.message || "Couldn't save");
    } finally {
      setSavingBrand(false);
    }
  }, [brandHandle, defaults, flash]);

  const removePreset = useCallback((name: string) => {
    Alert.alert("Delete preset?", name, [
      { text: "Cancel", style: "cancel" },
      {
        text: "Delete", style: "destructive", onPress: async () => {
          const next = presets.filter((p) => p.name !== name);
          setPresets(next); await savePresets(next); haptic.medium();
        },
      },
    ]);
  }, [presets]);

  const Section = ({ label, hint }: { label: string; hint?: string }) => (
    <View style={{ marginTop: spacing.xl }}>
      <Text style={styles.section}>{label}</Text>
      {!!hint && <Text style={styles.hint}>{hint}</Text>}
    </View>
  );

  return (
    <View style={styles.root}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.xs }]}>
        <Pressable testID="settings-back" onPress={() => router.back()} style={styles.iconBtn}>
          <Ionicons name="chevron-back" size={22} color={colors.onSurface} />
        </Pressable>
        <Text style={styles.headerTitle}>Settings</Text>
        <View style={styles.iconBtn} />
      </View>

      <KeyboardAwareScrollView
        bottomOffset={90}
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: insets.bottom + spacing.xxxl }}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
      >
        {/* ---- AI KEYS ---- */}
        <Section label="AI KEYS · BRING YOUR OWN" hint="Use your own API keys to skip the shared credit limit. Leave blank to keep using built-in credits." />

        <Text style={styles.keyLabel}>AI engine</Text>
        <Text style={styles.keyHint}>Choose which credits power your reels. Switch to “Built-in” anytime if your own key errors.</Text>
        <View style={styles.segRow}>
          <Pressable
            testID="key-mode-own"
            onPress={() => setKeyMode("own")}
            style={[styles.seg, (settings?.key_mode ?? "own") === "own" && styles.segActive]}
          >
            <Ionicons name="key" size={15} color={(settings?.key_mode ?? "own") === "own" ? colors.onBrandTertiary : colors.onSurfaceSecondary} />
            <Text style={[styles.segTxt, (settings?.key_mode ?? "own") === "own" && styles.segTxtActive]}>My own keys</Text>
          </Pressable>
          <Pressable
            testID="key-mode-builtin"
            onPress={() => setKeyMode("builtin")}
            style={[styles.seg, settings?.key_mode === "builtin" && styles.segActive]}
          >
            <Ionicons name="sparkles" size={15} color={settings?.key_mode === "builtin" ? colors.onBrandTertiary : colors.onSurfaceSecondary} />
            <Text style={[styles.segTxt, settings?.key_mode === "builtin" && styles.segTxtActive]}>Built-in credits</Text>
          </Pressable>
        </View>
        {settings?.key_mode === "builtin" && (
          <View style={styles.noteBox}>
            <Ionicons name="information-circle" size={15} color={colors.brand} />
            <Text style={styles.noteTxt}>Using the app's built-in (Universal) credits. Your saved keys are kept but ignored until you switch back.</Text>
          </View>
        )}
        {(settings?.key_mode ?? "own") === "own" && (
          <View style={styles.noteBox}>
            <Ionicons name="information-circle" size={15} color={colors.brand} />
            <Text style={styles.noteTxt}>AI Image reels need BOTH keys: OpenAI (script &amp; voice) and Google/Gemini (images). Any key left blank falls back to built-in credits for that step.</Text>
          </View>
        )}

        <View style={[styles.keyRow, { marginTop: spacing.lg }]}>
          <Text style={styles.keyLabel}>OpenAI key</Text>
          <View style={[styles.statusPill, settings?.openai_key_set ? styles.pillOn : styles.pillOff]}>
            <Text style={[styles.pillTxt, settings?.openai_key_set ? styles.pillTxtOn : styles.pillTxtOff]}>
              {settings?.openai_key_set ? `Yours · ${settings.openai_key_masked}` : "Built-in credits"}
            </Text>
          </View>
        </View>
        <Text style={styles.keyHint}>Powers script writing, voiceover and captions.</Text>
        <View style={styles.inputRow}>
          <TextInput
            testID="openai-key-input"
            value={openaiKey}
            onChangeText={setOpenaiKey}
            placeholder="sk-..."
            placeholderTextColor={colors.onSurfaceSecondary}
            autoCapitalize="none"
            secureTextEntry
            style={styles.input}
          />
          {settings?.openai_key_set && (
            <Pressable testID="clear-openai" onPress={() => clearKey("openai")} style={styles.clearBtn}>
              <Ionicons name="trash-outline" size={16} color={colors.onSurfaceSecondary} />
            </Pressable>
          )}
        </View>

        {!!testResult.openai && (
          <View style={styles.resultRow}>
            <Ionicons name={testResult.openai.ok ? "checkmark-circle" : "close-circle"} size={14} color={testResult.openai.ok ? colors.success : colors.error} />
            <Text style={[styles.resTxt, { color: testResult.openai.ok ? colors.success : colors.error }]}>{testResult.openai.message}</Text>
          </View>
        )}

        <View style={[styles.keyRow, { marginTop: spacing.lg }]}>
          <Text style={styles.keyLabel}>Google / Gemini key</Text>
          <View style={[styles.statusPill, settings?.google_key_set ? styles.pillOn : styles.pillOff]}>
            <Text style={[styles.pillTxt, settings?.google_key_set ? styles.pillTxtOn : styles.pillTxtOff]}>
              {settings?.google_key_set ? `Yours · ${settings.google_key_masked}` : "Built-in credits"}
            </Text>
          </View>
        </View>
        <Text style={styles.keyHint}>Powers AI image visuals (Nano Banana).</Text>
        <View style={styles.inputRow}>
          <TextInput
            testID="google-key-input"
            value={googleKey}
            onChangeText={setGoogleKey}
            placeholder="AIza..."
            placeholderTextColor={colors.onSurfaceSecondary}
            autoCapitalize="none"
            secureTextEntry
            style={styles.input}
          />
          {settings?.google_key_set && (
            <Pressable testID="clear-google" onPress={() => clearKey("google")} style={styles.clearBtn}>
              <Ionicons name="trash-outline" size={16} color={colors.onSurfaceSecondary} />
            </Pressable>
          )}
        </View>
        <PrimaryButton
          testID="save-keys-button"
          label="Save keys"
          icon="key-outline"
          loading={savingKeys}
          disabled={!openaiKey.trim() && !googleKey.trim()}
          onPress={saveKeys}
          style={{ marginTop: spacing.md }}
        />

        {/* ---- STUDIO DEFAULTS ---- */}
        <Section label="STUDIO DEFAULTS" hint="Prefill every new reel with your favourite settings." />
        <SettingRow icon="mic" label="Voice" value={voice?.name || "—"} onPress={() => voiceSheet.current?.present()} />
        <SettingRow icon="musical-notes" label="Music" value={music?.name || "None"} onPress={() => musicSheet.current?.present()} />
        <Text style={styles.miniLabel}>Length</Text>
        <View style={styles.chipRow}>
          {DURATIONS.map((d) => {
            const active = (defaults.seconds || 30) === d;
            return (
              <Pressable key={d} testID={`default-dur-${d}`} onPress={() => persistDefaults({ ...defaults, seconds: d })} style={[styles.chip, active && styles.chipActive]}>
                <Text style={[styles.chipTxt, active && styles.chipTxtActive]}>{d}s</Text>
              </Pressable>
            );
          })}
        </View>
        <Text style={styles.miniLabel}>Caption style</Text>
        <View style={styles.chipRow}>
          {(config?.caption_styles || []).map((c) => {
            const active = (defaults.caption_style || "signal") === c.id;
            return (
              <Pressable key={c.id} testID={`default-cap-${c.id}`} onPress={() => persistDefaults({ ...defaults, caption_style: c.id })} style={[styles.chip, active && styles.chipActive]}>
                <Text style={[styles.chipTxt, active && styles.chipTxtActive]}>{c.name}</Text>
              </Pressable>
            );
          })}
        </View>
        {savingDefaults && <Text style={styles.savingTxt}>Saved</Text>}

        {/* ---- BRAND KIT ---- */}
        <Section label="BRAND KIT" hint="Your @handle burns onto every reel as a watermark by default." />
        <View style={styles.inputRow}>
          <TextInput
            testID="brand-handle-input"
            value={brandHandle}
            onChangeText={setBrandHandle}
            placeholder="@yourhandle"
            placeholderTextColor={colors.onSurfaceSecondary}
            autoCapitalize="none"
            maxLength={40}
            style={styles.input}
          />
        </View>
        <PrimaryButton testID="save-brand-button" variant="ghost" label="Save brand" icon="pricetag-outline" loading={savingBrand} onPress={saveBrand} style={{ marginTop: spacing.sm }} />
        <PrimaryButton testID="manage-outros-button" variant="ghost" label="Manage outro clips" icon="film-outline" onPress={() => outroSheet.current?.present()} style={{ marginTop: spacing.sm }} />

        {/* ---- PRESETS ---- */}
        <Section label="SAVED PRESETS" hint={presets.length ? undefined : "Save presets from the Create screen to reuse setups."} />
        {presets.map((p) => (
          <View key={p.name} style={styles.presetRow} testID={`preset-${p.name}`}>
            <Ionicons name="bookmark-outline" size={18} color={colors.brand} />
            <Text style={styles.presetName} numberOfLines={1}>{p.name}</Text>
            <Pressable testID={`preset-delete-${p.name}`} onPress={() => removePreset(p.name)} style={styles.clearBtn}>
              <Ionicons name="trash-outline" size={16} color={colors.onSurfaceSecondary} />
            </Pressable>
          </View>
        ))}

        {/* ---- ABOUT ---- */}
        <Section label="PLAN & CREDITS" />
        <View style={styles.aboutCard}>
          {user && (
            <Text style={styles.planLine}>
              {user.is_admin
                ? "✓ Admin — unlimited reels"
                : user.is_subscribed
                ? "✓ Subscribed — unlimited reels"
                : user.has_own_key
                ? "✓ Using your own API key — unlimited reels"
                : `Free plan · ${Math.max(0, user.free_limit - user.free_used)} of ${user.free_limit} free reels left`}
            </Text>
          )}
          <Text style={styles.aboutText}>
            GhostReelsAlpha turns any topic into a TikTok-ready vertical video.{"\n\n"}
            Out of free reels? Subscribe for unlimited generation, or paste your own OpenAI/Google key above to generate freely.
          </Text>
          {!!user && <Text style={styles.version}>Signed in as {user.email} · v1.0</Text>}
        </View>
        {!user?.has_own_key && !user?.is_admin && (
          <PrimaryButton
            testID="subscribe-button"
            label={user?.is_subscribed ? "Manage subscription" : "Subscribe — unlimited reels"}
            icon={user?.is_subscribed ? "checkmark-circle-outline" : "rocket-outline"}
            onPress={() => { haptic.select(); router.push("/paywall"); }}
            style={{ marginTop: spacing.md }}
          />
        )}
        <PrimaryButton
          testID="signout-button"
          variant="ghost"
          icon="log-out-outline"
          label="Sign out"
          onPress={async () => { haptic.medium(); await signOut(); }}
          style={{ marginTop: spacing.md }}
        />

        <Text style={styles.sectionLabel}>LEGAL & SUPPORT</Text>
        <View style={styles.linkCard}>
          <Pressable testID="privacy-link" onPress={openPrivacy} style={styles.linkRow}>
            <View style={styles.settingLeft}>
              <Ionicons name="shield-checkmark-outline" size={18} color={colors.onSurfaceSecondary} />
              <Text style={styles.settingLabel}>Privacy Policy</Text>
            </View>
            <Ionicons name="open-outline" size={16} color={colors.onSurfaceSecondary} />
          </Pressable>
          <View style={styles.linkDivider} />
          <Pressable testID="terms-link" onPress={openTerms} style={styles.linkRow}>
            <View style={styles.settingLeft}>
              <Ionicons name="document-text-outline" size={18} color={colors.onSurfaceSecondary} />
              <Text style={styles.settingLabel}>Terms of Service</Text>
            </View>
            <Ionicons name="open-outline" size={16} color={colors.onSurfaceSecondary} />
          </Pressable>
          <View style={styles.linkDivider} />
          <Pressable testID="support-link" onPress={openSupport} style={styles.linkRow}>
            <View style={styles.settingLeft}>
              <Ionicons name="mail-outline" size={18} color={colors.onSurfaceSecondary} />
              <Text style={styles.settingLabel}>Contact Support</Text>
            </View>
            <Ionicons name="chevron-forward" size={16} color={colors.onSurfaceSecondary} />
          </Pressable>
        </View>

        <Pressable testID="delete-account-button" onPress={() => { haptic.medium(); setConfirmDelete(true); }} style={styles.deleteRow}>
          <Ionicons name="trash-outline" size={18} color={colors.error} />
          <Text style={styles.deleteTxt}>Delete account</Text>
        </Pressable>
        <Text style={styles.deleteHint}>Permanently deletes your account, reels, and saved keys. This can't be undone.</Text>

        {!!toast && (
          <View style={styles.toast} testID="settings-toast"><Text style={styles.toastTxt}>{toast}</Text></View>
        )}
      </KeyboardAwareScrollView>

      <Modal visible={confirmDelete} transparent animationType="fade" onRequestClose={() => !deleting && setConfirmDelete(false)}>
        <Pressable style={styles.backdrop} onPress={() => !deleting && setConfirmDelete(false)}>
          <Pressable style={styles.confirmCard} onPress={() => {}}>
            <Text style={styles.confirmTitle}>Delete account?</Text>
            <Text style={styles.confirmBody}>
              This permanently deletes your account and all your reels, outros, series, and saved API keys. This action cannot be undone.
            </Text>
            <View style={styles.confirmRow}>
              <Pressable testID="delete-cancel" disabled={deleting} onPress={() => setConfirmDelete(false)} style={[styles.confirmBtn, styles.confirmGhost]}>
                <Text style={styles.confirmGhostTxt}>Cancel</Text>
              </Pressable>
              <Pressable testID="delete-confirm" disabled={deleting} onPress={doDeleteAccount} style={[styles.confirmBtn, styles.confirmDanger]}>
                {deleting ? <ActivityIndicator color="#fff" /> : <Text style={styles.confirmDangerTxt}>Delete</Text>}
              </Pressable>
            </View>
          </Pressable>
        </Pressable>
      </Modal>

      <OptionSheet ref={voiceSheet} title="Default voice" options={voiceOptions} selectedId={defaults.voice_id || "onyx"} onSelect={(id) => { persistDefaults({ ...defaults, voice_id: id }); voiceSheet.current?.dismiss(); }} />
      <OptionSheet ref={musicSheet} title="Default music" options={musicOptions} selectedId={defaults.music_id || "none"} onSelect={(id) => { persistDefaults({ ...defaults, music_id: id }); musicSheet.current?.dismiss(); }} />
      <OutroSheet ref={outroSheet} selectedId={null} onSelect={() => outroSheet.current?.dismiss()} />
    </View>
  );
}

function SettingRow({ icon, label, value, onPress }: { icon: any; label: string; value: string; onPress: () => void }) {
  return (
    <Pressable onPress={() => { haptic.select(); onPress(); }} style={styles.settingRow} testID={`default-row-${label}`}>
      <View style={styles.settingLeft}>
        <Ionicons name={icon} size={18} color={colors.onSurfaceSecondary} />
        <Text style={styles.settingLabel}>{label}</Text>
      </View>
      <View style={styles.settingRight}>
        <Text style={styles.settingValue}>{value}</Text>
        <Ionicons name="chevron-forward" size={16} color={colors.onSurfaceSecondary} />
      </View>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: spacing.md, paddingBottom: spacing.sm, borderBottomWidth: 1, borderBottomColor: colors.border },
  iconBtn: { width: 40, height: 40, borderRadius: radius.md, alignItems: "center", justifyContent: "center" },
  headerTitle: { flex: 1, textAlign: "center", fontFamily: font.display, fontSize: 22, color: colors.onSurface, letterSpacing: 0.5 },
  section: { fontFamily: font.bodyBold, fontSize: 11, letterSpacing: 1.2, color: colors.brand },
  hint: { fontFamily: font.body, fontSize: 12, color: colors.onSurfaceSecondary, marginTop: spacing.xs, lineHeight: 17 },
  keyRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginTop: spacing.md },
  keyLabel: { fontFamily: font.bodyBold, fontSize: 15, color: colors.onSurface },
  keyHint: { fontFamily: font.body, fontSize: 12, color: colors.onSurfaceSecondary, marginTop: 2 },
  segRow: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.sm },
  seg: { flex: 1, flexDirection: "row", alignItems: "center", justifyContent: "center", gap: spacing.xs, height: 46, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surfaceSecondary },
  segActive: { borderColor: colors.brand, backgroundColor: colors.brandTertiary },
  segTxt: { fontFamily: font.bodySemi, fontSize: 13, color: colors.onSurfaceSecondary },
  segTxtActive: { color: colors.onBrandTertiary },
  noteBox: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.sm, padding: spacing.sm, borderRadius: radius.md, backgroundColor: colors.brandTertiary, borderWidth: 1, borderColor: colors.brandPrimary },
  noteTxt: { flex: 1, fontFamily: font.body, fontSize: 12, color: colors.brandSecondary, lineHeight: 17 },
  statusPill: { paddingHorizontal: spacing.sm, height: 24, borderRadius: radius.pill, alignItems: "center", justifyContent: "center", maxWidth: "58%" },
  pillOn: { backgroundColor: "rgba(34,197,94,0.14)" },
  pillOff: { backgroundColor: colors.surfaceTertiary },
  pillTxt: { fontFamily: font.bodySemi, fontSize: 11 },
  pillTxtOn: { color: colors.success },
  pillTxtOff: { color: colors.onSurfaceSecondary },
  inputRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm, marginTop: spacing.sm },
  input: { flex: 1, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, paddingHorizontal: spacing.md, height: 48, fontFamily: font.body, fontSize: 15, color: colors.onSurface },
  clearBtn: { width: 40, height: 40, borderRadius: radius.md, alignItems: "center", justifyContent: "center", backgroundColor: colors.surfaceTertiary },
  settingRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: spacing.md, height: 54, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surfaceSecondary, marginTop: spacing.sm },
  settingLeft: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  settingLabel: { fontFamily: font.bodySemi, fontSize: 15, color: colors.onSurface },
  settingRight: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  settingValue: { fontFamily: font.bodyMed, fontSize: 14, color: colors.onSurfaceSecondary },
  miniLabel: { fontFamily: font.bodyBold, fontSize: 11, letterSpacing: 1, color: colors.onSurfaceSecondary, marginTop: spacing.md, marginBottom: spacing.sm },
  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: spacing.sm },
  chip: { minWidth: 64, flexGrow: 1, height: 42, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surfaceSecondary, alignItems: "center", justifyContent: "center", paddingHorizontal: spacing.sm },
  chipActive: { borderColor: colors.brand, backgroundColor: colors.brandTertiary },
  chipTxt: { fontFamily: font.bodySemi, fontSize: 13, color: colors.onSurfaceSecondary },
  chipTxtActive: { color: colors.onBrandTertiary },
  savingTxt: { fontFamily: font.bodyMed, fontSize: 11, color: colors.success, marginTop: spacing.sm },
  presetRow: { flexDirection: "row", alignItems: "center", gap: spacing.sm, padding: spacing.md, borderRadius: radius.md, borderWidth: 1, borderColor: colors.border, backgroundColor: colors.surfaceSecondary, marginTop: spacing.sm },
  presetName: { flex: 1, fontFamily: font.bodyBold, fontSize: 14, color: colors.onSurface },
  aboutCard: { padding: spacing.md, borderRadius: radius.md, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, marginTop: spacing.sm },
  aboutText: { fontFamily: font.body, fontSize: 13, color: colors.onSurfaceSecondary, lineHeight: 19 },
  planLine: { fontFamily: font.bodyBold, fontSize: 14, color: colors.onSurface, marginBottom: spacing.sm },
  version: { fontFamily: font.bodyMed, fontSize: 11, color: colors.onSurfaceSecondary, marginTop: spacing.sm },
  toast: { marginTop: spacing.lg, alignSelf: "center", paddingHorizontal: spacing.lg, height: 40, borderRadius: radius.pill, backgroundColor: colors.surfaceTertiary, alignItems: "center", justifyContent: "center" },
  toastTxt: { fontFamily: font.bodySemi, fontSize: 13, color: colors.onSurface },
  sectionLabel: { fontFamily: font.bodyBold, fontSize: 11, letterSpacing: 1.2, color: colors.brand, marginTop: spacing.xl, marginBottom: spacing.sm },
  linkCard: { borderRadius: radius.md, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, overflow: "hidden" },
  linkRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: spacing.md, paddingVertical: spacing.md, minHeight: 48 },
  linkDivider: { height: 1, backgroundColor: colors.border, marginLeft: spacing.md },
  deleteRow: { flexDirection: "row", alignItems: "center", justifyContent: "center", gap: spacing.sm, marginTop: spacing.xl, height: 48, borderRadius: radius.md, borderWidth: 1, borderColor: colors.error },
  deleteTxt: { fontFamily: font.bodyBold, fontSize: 15, color: colors.error },
  deleteHint: { fontFamily: font.body, fontSize: 12, color: colors.onSurfaceSecondary, textAlign: "center", marginTop: spacing.sm, lineHeight: 17 },
  backdrop: { flex: 1, backgroundColor: "rgba(0,0,0,0.6)", alignItems: "center", justifyContent: "center", padding: spacing.xl },
  confirmCard: { width: "100%", maxWidth: 360, borderRadius: radius.lg, backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, padding: spacing.lg },
  confirmTitle: { fontFamily: font.display, fontSize: 20, color: colors.onSurface },
  confirmBody: { fontFamily: font.body, fontSize: 14, color: colors.onSurfaceSecondary, marginTop: spacing.sm, lineHeight: 20 },
  confirmRow: { flexDirection: "row", gap: spacing.sm, marginTop: spacing.lg },
  confirmBtn: { flex: 1, height: 48, borderRadius: radius.md, alignItems: "center", justifyContent: "center" },
  confirmGhost: { backgroundColor: colors.surfaceTertiary },
  confirmGhostTxt: { fontFamily: font.bodySemi, fontSize: 15, color: colors.onSurface },
  confirmDanger: { backgroundColor: colors.error },
  confirmDangerTxt: { fontFamily: font.bodyBold, fontSize: 15, color: "#fff" },
});
