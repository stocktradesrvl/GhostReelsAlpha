import { Ionicons } from "@expo/vector-icons";
import { useCallback, useState } from "react";
import { KeyboardAvoidingView, Platform, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { useAuth } from "@/src/auth";
import PrimaryButton from "@/src/components/PrimaryButton";
import { haptic } from "@/src/haptics";
import { colors, font, radius, spacing } from "@/src/theme";

export default function AuthScreen() {
  const insets = useSafeAreaInsets();
  const { signIn, register } = useAuth();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const submit = useCallback(async () => {
    setError(null);
    if (!email.trim() || !password) { setError("Enter your email and password."); return; }
    if (mode === "register" && password.length < 8) { setError("Password must be at least 8 characters."); return; }
    setBusy(true);
    try {
      if (mode === "login") await signIn(email.trim(), password);
      else await register(email.trim(), password);
      haptic.success();
    } catch (e: any) {
      setError(e.message || "Something went wrong.");
      haptic.error();
    } finally {
      setBusy(false);
    }
  }, [mode, email, password, signIn, register]);

  return (
    <View style={[styles.root, { paddingTop: insets.top }]}>
      <KeyboardAvoidingView behavior={Platform.OS === "ios" ? "padding" : undefined} style={styles.flex}>
        <View style={styles.body}>
          <View style={styles.logo}>
            <Ionicons name="flash" size={34} color={colors.brand} />
          </View>
          <Text style={styles.brand}>GHOSTREELS ALPHA</Text>
          <Text style={styles.tagline}>Turn any idea into a TikTok-ready video.</Text>

          <View style={styles.segment}>
            <Pressable testID="tab-login" onPress={() => { setMode("login"); setError(null); }} style={[styles.segBtn, mode === "login" && styles.segActive]}>
              <Text style={[styles.segTxt, mode === "login" && styles.segTxtActive]}>Log in</Text>
            </Pressable>
            <Pressable testID="tab-register" onPress={() => { setMode("register"); setError(null); }} style={[styles.segBtn, mode === "register" && styles.segActive]}>
              <Text style={[styles.segTxt, mode === "register" && styles.segTxtActive]}>Sign up</Text>
            </Pressable>
          </View>

          <TextInput
            testID="email-input"
            value={email}
            onChangeText={setEmail}
            placeholder="you@email.com"
            placeholderTextColor={colors.onSurfaceSecondary}
            autoCapitalize="none"
            autoComplete="email"
            keyboardType="email-address"
            style={styles.input}
          />
          <TextInput
            testID="password-input"
            value={password}
            onChangeText={setPassword}
            placeholder={mode === "register" ? "Create a password (8+ chars)" : "Password"}
            placeholderTextColor={colors.onSurfaceSecondary}
            autoCapitalize="none"
            secureTextEntry
            style={styles.input}
          />

          {!!error && (
            <View style={styles.errorBox} testID="auth-error">
              <Ionicons name="warning" size={15} color={colors.error} />
              <Text style={styles.errorTxt}>{error}</Text>
            </View>
          )}

          <PrimaryButton
            testID="auth-submit"
            label={mode === "login" ? "Log in" : "Create account"}
            icon="arrow-forward"
            loading={busy}
            onPress={submit}
            style={{ marginTop: spacing.lg }}
          />
          <Text style={styles.free}>New accounts get 3 free reels — then add your own key or subscribe.</Text>
        </View>
      </KeyboardAvoidingView>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  flex: { flex: 1 },
  body: { flex: 1, justifyContent: "center", paddingHorizontal: spacing.xl },
  logo: { alignSelf: "center", width: 72, height: 72, borderRadius: 20, backgroundColor: colors.brandTertiary, borderWidth: 1, borderColor: colors.brandPrimary, alignItems: "center", justifyContent: "center" },
  brand: { textAlign: "center", fontFamily: font.display, fontSize: 30, color: colors.onSurface, letterSpacing: 1.5, marginTop: spacing.lg },
  tagline: { textAlign: "center", fontFamily: font.body, fontSize: 14, color: colors.onSurfaceSecondary, marginTop: spacing.xs, marginBottom: spacing.xl },
  segment: { flexDirection: "row", backgroundColor: colors.surfaceSecondary, borderRadius: radius.md, padding: 4, borderWidth: 1, borderColor: colors.border, marginBottom: spacing.lg },
  segBtn: { flex: 1, height: 40, borderRadius: radius.sm, alignItems: "center", justifyContent: "center" },
  segActive: { backgroundColor: colors.brandPrimary },
  segTxt: { fontFamily: font.bodySemi, fontSize: 14, color: colors.onSurfaceSecondary },
  segTxtActive: { color: colors.onBrand },
  input: { backgroundColor: colors.surfaceSecondary, borderWidth: 1, borderColor: colors.border, borderRadius: radius.md, paddingHorizontal: spacing.md, height: 52, fontFamily: font.body, fontSize: 15, color: colors.onSurface, marginBottom: spacing.md },
  errorBox: { flexDirection: "row", alignItems: "center", gap: spacing.sm, padding: spacing.md, borderRadius: radius.md, backgroundColor: "rgba(239,68,68,0.12)", borderWidth: 1, borderColor: "rgba(239,68,68,0.3)" },
  errorTxt: { flex: 1, fontFamily: font.bodyMed, fontSize: 13, color: colors.brandSecondary },
  free: { textAlign: "center", fontFamily: font.body, fontSize: 12, color: colors.onSurfaceSecondary, marginTop: spacing.lg, lineHeight: 17 },
});
