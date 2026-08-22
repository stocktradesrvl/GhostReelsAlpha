import { BottomSheetModal } from "@gorhom/bottom-sheet";
import { Ionicons } from "@expo/vector-icons";
import Slider from "@react-native-community/slider";
import { useLocalSearchParams, useRouter } from "expo-router";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Pressable, StyleSheet, Switch, Text, TextInput, View } from "react-native";
import { KeyboardAwareScrollView, KeyboardStickyView } from "react-native-keyboard-controller";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { api, Config, Outro } from "@/src/api";
import { playPreview, stopPreview } from "@/src/audioPreview";
import OptionSheet, { SheetOption } from "@/src/components/OptionSheet";
import OutroSheet from "@/src/components/OutroSheet";
import PresetSheet from "@/src/components/PresetSheet";
import { loadDefaults } from "@/src/defaults";
import { useHidingTabBar } from "@/src/tabbar";
import PrimaryButton from "@/src/components/PrimaryButton";
import Segmented from "@/src/components/Segmented";
import { haptic } from "@/src/haptics";
import { colors, font, radius, spacing } from "@/src/theme";

const DURATIONS = [15, 30, 60];

export default function CreateScreen() {
  const insets = useSafeAreaInsets();
  const router = useRouter();
  const params = useLocalSearchParams<{ dup?: string }>();
  const appliedDup = useRef<string | null>(null);

  const [config, setConfig] = useState<Config | null>(null);
  const [mode, setMode] = useState<"topic" | "script">("topic");
  const [visualMode, setVisualMode] = useState<"gradient" | "ai">("gradient");
  const [imageStyle, setImageStyle] = useState("cinematic");
  const [creditWarn, setCreditWarn] = useState(false);
  const [topic, setTopic] = useState("");
  const [script, setScript] = useState("");
  const [seconds, setSeconds] = useState(30);
  const [voiceId, setVoiceId] = useState("onyx");
  const [voiceSpeed, setVoiceSpeed] = useState("normal");
  const [captionStyle, setCaptionStyle] = useState("signal");
  const [captionPosition, setCaptionPosition] = useState("center");
  const [captionSize, setCaptionSize] = useState("m");
  const [captionFont, setCaptionFont] = useState("barlow");
  const [captionAnim, setCaptionAnim] = useState("pop");
  const [bgTheme, setBgTheme] = useState("ember");
  const [bgMotion, setBgMotion] = useState("subtle");
  const [customC1, setCustomC1] = useState("#22D3EE");
  const [customC2, setCustomC2] = useState("#7C3AED");
  const [musicId, setMusicId] = useState("none");
  const [musicVolume, setMusicVolume] = useState(0.13);
  const [watermark, setWatermark] = useState("");
  const [hookEnabled, setHookEnabled] = useState(false);
  const [endcardText, setEndcardText] = useState("");
  const [outro, setOutro] = useState<Outro | null>(null);
  const [previewingVoice, setPreviewingVoice] = useState<string | null>(null);
  const [writing, setWriting] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const voiceSheet = useRef<BottomSheetModal>(null);
  const captionSheet = useRef<BottomSheetModal>(null);
  const bgSheet = useRef<BottomSheetModal>(null);
  const musicSheet = useRef<BottomSheetModal>(null);
  const presetSheet = useRef<BottomSheetModal>(null);
  const outroSheet = useRef<BottomSheetModal>(null);
  const scrollHide = useHidingTabBar();

  // Load studio defaults (set in Settings) to prefill new reels — skipped when duplicating.
  useEffect(() => {
    if (params.dup) return;
    loadDefaults().then((d) => {
      if (d.voice_id) setVoiceId(d.voice_id);
      if (d.seconds != null) setSeconds(d.seconds);
      if (d.caption_style) setCaptionStyle(d.caption_style);
      if (d.music_id) setMusicId(d.music_id);
      if (d.watermark != null) setWatermark(d.watermark);
    }).catch(() => {});
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const currentSettings = {
    seconds, visual_mode: visualMode, image_style: imageStyle, voice_id: voiceId, voice_speed: voiceSpeed, caption_style: captionStyle,
    caption_position: captionPosition, caption_size: captionSize, caption_font: captionFont,
    caption_anim: captionAnim, bg_theme: bgTheme, bg_motion: bgMotion, music_id: musicId,
    music_volume: musicVolume, watermark, hook_enabled: hookEnabled, endcard_text: endcardText,
    custom_c1: customC1, custom_c2: customC2, outro_id: outro?.id,
  };

  const applySettings = useCallback((s: Record<string, any>) => {
    if (s.seconds != null) setSeconds(s.seconds);
    if (s.visual_mode) setVisualMode(s.visual_mode);
    if (s.image_style) setImageStyle(s.image_style);
    if (s.voice_id) setVoiceId(s.voice_id);
    if (s.voice_speed) setVoiceSpeed(s.voice_speed);
    if (s.caption_style) setCaptionStyle(s.caption_style);
    if (s.caption_position) setCaptionPosition(s.caption_position);
    if (s.caption_size) setCaptionSize(s.caption_size);
    if (s.caption_font) setCaptionFont(s.caption_font);
    if (s.caption_anim) setCaptionAnim(s.caption_anim);
    if (s.bg_theme) setBgTheme(s.bg_theme);
    if (s.bg_motion) setBgMotion(s.bg_motion);
    if (s.custom_c1) setCustomC1(s.custom_c1);
    if (s.custom_c2) setCustomC2(s.custom_c2);
    if (s.music_id) setMusicId(s.music_id);
    if (s.music_volume != null) setMusicVolume(s.music_volume);
    setWatermark(s.watermark || "");
    setHookEnabled(!!s.hook_enabled);
    setEndcardText(s.endcard_text || "");
    setOutro(s.outro_id ? { id: s.outro_id, name: "Selected outro", size: 0, created_at: "" } : null);
    haptic.success();
    presetSheet.current?.dismiss();
  }, []);

  useEffect(() => {
    api.getConfig().then((c) => {
      setConfig(c);
      if (c.voices[0]) setVoiceId(c.voices[0].id);
      if (c.caption_styles[0]) setCaptionStyle(c.caption_styles[0].id);
      if (c.bg_themes[0]) setBgTheme(c.bg_themes[0].id);
    }).catch(() => setError("Couldn't load options. Pull to retry."));
  }, []);

  useEffect(() => {
    api.listReels().then((rs) => {
      const budgetFail = rs.some((r) => r.status === "failed" && (r.error_code === "budget" || (r.error && /budget|credit/i.test(r.error))));
      setCreditWarn(budgetFail);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    const dup = params.dup;
    if (!dup || appliedDup.current === dup) return;
    appliedDup.current = dup;
    api.getReel(dup).then((r) => {
      setMode(r.input_mode);
      setTopic(r.topic || "");
      setScript(r.script || "");
      setSeconds(r.seconds);
      if (r.visual_mode) setVisualMode(r.visual_mode);
      if (r.image_style) setImageStyle(r.image_style);
      setVoiceId(r.voice_id);
      setVoiceSpeed(r.voice_speed);
      setCaptionStyle(r.caption_style);
      setCaptionPosition(r.caption_position);
      setCaptionSize(r.caption_size);
      setCaptionFont(r.caption_font);
      setCaptionAnim(r.caption_anim);
      setBgTheme(r.bg_theme);
      setBgMotion(r.bg_motion);
      if (r.custom_c1) setCustomC1(r.custom_c1);
      if (r.custom_c2) setCustomC2(r.custom_c2);
      setMusicId(r.music_id);
      setMusicVolume(r.music_volume);
      setWatermark(r.watermark || "");
      setHookEnabled(r.hook_enabled);
      setEndcardText(r.endcard_text || "");
      setOutro(r.outro_id ? { id: r.outro_id, name: "Selected outro", size: 0, created_at: "" } : null);
      haptic.light();
      router.setParams({ dup: "" });
    }).catch(() => {});
  }, [params.dup, router]);

  const previewVoice = useCallback((id: string) => {
    if (previewingVoice === id) {
      stopPreview();
      setPreviewingVoice(null);
      return;
    }
    setPreviewingVoice(id);
    playPreview(api.voicePreviewUrl(id));
  }, [previewingVoice]);

  const wordCount = useMemo(
    () => script.trim().split(/\s+/).filter(Boolean).length,
    [script],
  );

  const voice = config?.voices.find((v) => v.id === voiceId);
  const caption = config?.caption_styles.find((c) => c.id === captionStyle);
  const bg = config?.bg_themes.find((b) => b.id === bgTheme);
  const music = config?.music_tracks.find((m) => m.id === musicId);

  const voiceOptions: SheetOption[] =
    config?.voices.map((v) => ({ id: v.id, title: v.name, subtitle: v.tagline })) || [];
  const captionOptions: SheetOption[] =
    config?.caption_styles.map((c) => ({ id: c.id, title: c.name, subtitle: c.hint, dot: c.hex })) || [];
  const bgOptions: SheetOption[] = [
    ...(config?.bg_themes.map((b) => ({ id: b.id, title: b.name, swatch: b.preview })) || []),
    { id: "custom", title: "Custom colours", swatch: [customC2, customC1] },
  ];
  const musicOptions: SheetOption[] =
    config?.music_tracks.map((m) => ({ id: m.id, title: m.name })) || [];

  const writeScript = useCallback(async () => {
    if (!topic.trim()) {
      setError("Enter a topic first.");
      return;
    }
    setError(null);
    setWriting(true);
    try {
      const res = await api.generateScript(topic.trim(), seconds);
      setScript(res.script);
      haptic.success();
    } catch (e: any) {
      setError(e.message || "Script generation failed.");
      haptic.error();
    } finally {
      setWriting(false);
    }
  }, [topic, seconds]);

  const canGenerate =
    mode === "script" ? script.trim().length > 0 : topic.trim().length > 0 || script.trim().length > 0;

  const generate = useCallback(async () => {
    if (!canGenerate) return;
    setError(null);
    setSubmitting(true);
    try {
      const reel = await api.createReel({
        input_mode: mode,
        topic: mode === "topic" ? topic.trim() : undefined,
        script: script.trim() || undefined,
        seconds,
        visual_mode: visualMode,
        image_style: imageStyle,
        voice_id: voiceId,
        voice_speed: voiceSpeed,
        caption_style: captionStyle,
        caption_position: captionPosition,
        caption_size: captionSize,
        caption_font: captionFont,
        caption_anim: captionAnim,
        bg_theme: bgTheme,
        bg_motion: bgMotion,
        custom_c1: bgTheme === "custom" ? customC1 : undefined,
        custom_c2: bgTheme === "custom" ? customC2 : undefined,
        music_id: musicId,
        music_volume: musicVolume,
        watermark: watermark.trim() || undefined,
        hook_enabled: hookEnabled,
        endcard_text: endcardText.trim() || undefined,
        outro_id: outro?.id || undefined,
      } as any);
      haptic.heavy();
      router.push(`/reel/${reel.id}`);
    } catch (e: any) {
      setError(e.message || "Couldn't start generation.");
      haptic.error();
    } finally {
      setSubmitting(false);
    }
  }, [canGenerate, mode, topic, script, seconds, visualMode, imageStyle, voiceId, voiceSpeed, captionStyle, captionPosition, captionSize, captionFont, captionAnim, bgTheme, bgMotion, customC1, customC2, musicId, musicVolume, watermark, hookEnabled, endcardText, outro, router]);

  return (
    <View style={styles.root}>
      <View style={[styles.header, { paddingTop: insets.top + spacing.sm }]}>
        <View>
          <Text style={styles.brand}>FACELESS REELS</Text>
          <Text style={styles.sub}>Topic → script → voice → captions → MP4</Text>
        </View>
        <View style={styles.headerRight}>
          <Pressable
            testID="batch-button"
            onPress={() => { haptic.select(); router.push("/batch"); }}
            style={styles.batchBtn}
          >
            <Ionicons name="layers-outline" size={16} color={colors.onSurface} />
            <Text style={styles.batchTxt}>Batch</Text>
          </Pressable>
          <Pressable
            testID="settings-button"
            onPress={() => { haptic.select(); router.push("/settings"); }}
            style={styles.logo}
          >
            <Ionicons name="settings-outline" size={20} color={colors.brand} />
          </Pressable>
        </View>
      </View>

      <KeyboardAwareScrollView
        bottomOffset={90}
        onScroll={scrollHide.onScroll}
        scrollEventThrottle={scrollHide.scrollEventThrottle}
        contentContainerStyle={{ padding: spacing.lg, paddingBottom: 180 }}
        showsVerticalScrollIndicator={false}
        keyboardShouldPersistTaps="handled"
      >
        {creditWarn && (
          <Pressable testID="credit-banner" onPress={() => setCreditWarn(false)} style={styles.creditBanner}>
            <Ionicons name="warning" size={16} color={colors.warning} />
            <Text style={styles.creditText}>Your AI credits ran out — top up your Universal Key to generate. Tap to dismiss.</Text>
          </Pressable>
        )}

        <Segmented
          testID="mode-segment"
          options={[{ id: "topic", label: "GENERATE FROM TOPIC" }, { id: "script", label: "PASTE SCRIPT" }]}
          value={mode}
          onChange={(m) => setMode(m as "topic" | "script")}
        />

        <Text style={styles.section}>VISUAL STYLE</Text>
        <Segmented
          testID="visual-mode-segment"
          options={[{ id: "gradient", label: "GRADIENT" }, { id: "ai", label: "AI IMAGES" }]}
          value={visualMode}
          onChange={(v) => setVisualMode(v as "gradient" | "ai")}
        />
        {visualMode === "ai" && (
          <Text style={styles.aiNote}>
            AI paints story-matching images for your reel (uses a few extra credits per video).
          </Text>
        )}
        {visualMode === "ai" && (
          <>
            <Text style={styles.section}>IMAGE STYLE</Text>
            <ChipSelector
              testID="image-style"
              options={config?.image_styles || []}
              value={imageStyle}
              onChange={setImageStyle}
            />
          </>
        )}

        {mode === "topic" ? (
          <>
            <Text style={styles.section}>TOPIC</Text>
            <TextInput
              testID="topic-input"
              value={topic}
              onChangeText={setTopic}
              placeholder="e.g. 3 mind-blowing facts about deep sea creatures"
              placeholderTextColor={colors.onSurfaceSecondary}
              multiline
              style={[styles.input, { minHeight: 88 }]}
            />

            <Text style={styles.section}>LENGTH</Text>
            <View style={styles.chipRow}>
              {DURATIONS.map((d) => {
                const active = d === seconds;
                return (
                  <Pressable
                    key={d}
                    testID={`duration-${d}`}
                    onPress={() => {
                      haptic.light();
                      setSeconds(d);
                    }}
                    style={[styles.chip, active && styles.chipActive]}
                  >
                    <Text style={[styles.chipText, active && styles.chipTextActive]}>{d}s</Text>
                  </Pressable>
                );
              })}
            </View>

            <PrimaryButton
              testID="write-script-button"
              variant="ghost"
              icon="sparkles"
              label={script ? "Rewrite script with AI" : "Write script with AI"}
              loading={writing}
              onPress={writeScript}
              style={{ marginTop: spacing.lg }}
            />

            {!!script && (
              <>
                <View style={styles.scriptHead}>
                  <Text style={styles.section}>SCRIPT · EDITABLE</Text>
                  <Text style={styles.wordCount}>{wordCount} words</Text>
                </View>
                <TextInput
                  testID="script-preview-input"
                  value={script}
                  onChangeText={setScript}
                  multiline
                  style={[styles.input, { minHeight: 160 }]}
                />
              </>
            )}
          </>
        ) : (
          <>
            <View style={styles.scriptHead}>
              <Text style={styles.section}>YOUR SCRIPT</Text>
              <Text style={styles.wordCount}>{wordCount} words</Text>
            </View>
            <TextInput
              testID="script-input"
              value={script}
              onChangeText={setScript}
              placeholder="Paste your narration script here. Short punchy sentences work best."
              placeholderTextColor={colors.onSurfaceSecondary}
              multiline
              style={[styles.input, { minHeight: 220 }]}
            />
          </>
        )}

        <View style={styles.sectionRow}>
          <Text style={styles.section}>STUDIO SETTINGS</Text>
          <Pressable
            testID="presets-button"
            onPress={() => { haptic.select(); presetSheet.current?.present(); }}
            style={styles.presetPill}
          >
            <Ionicons name="color-wand" size={14} color={colors.brand} />
            <Text style={styles.presetPillTxt}>Presets</Text>
          </Pressable>
        </View>
        <View style={styles.settings}>
          <SettingRow
            testID="setting-voice"
            icon="mic"
            label="Voice"
            value={voice?.name || "—"}
            onPress={() => voiceSheet.current?.present()}
          />
          <SettingRow
            testID="setting-caption"
            icon="text"
            label="Captions"
            value={caption?.name || "—"}
            dot={caption?.hex}
            onPress={() => captionSheet.current?.present()}
          />
          <SettingRow
            testID="setting-bg"
            icon="color-palette"
            label="Background"
            value={bgTheme === "custom" ? "Custom" : (bg?.name || "—")}
            swatch={bgTheme === "custom" ? [customC2, customC1] : bg?.preview}
            onPress={() => bgSheet.current?.present()}
          />
          <SettingRow
            testID="setting-music"
            icon="musical-notes"
            label="Music"
            value={music?.name || "—"}
            onPress={() => musicSheet.current?.present()}
          />
          <SettingRow
            testID="setting-outro"
            icon="play-forward"
            label="Outro clip"
            value={outro ? outro.name : "None"}
            onPress={() => outroSheet.current?.present()}
          />
        </View>

        <Text style={styles.section}>NARRATION SPEED</Text>
        <ChipSelector
          testID="voice-speed"
          options={config?.voice_speeds || []}
          value={voiceSpeed}
          onChange={setVoiceSpeed}
        />

        {musicId !== "none" && (
          <>
            <View style={styles.scriptHead}>
              <Text style={styles.section}>MUSIC LEVEL</Text>
              <Text style={styles.wordCount}>{Math.round(musicVolume * 100)}%</Text>
            </View>
            <Slider
              testID="music-volume-slider"
              style={{ width: "100%", height: 40 }}
              minimumValue={0}
              maximumValue={1}
              step={0.01}
              value={musicVolume}
              onValueChange={setMusicVolume}
              minimumTrackTintColor={colors.brand}
              maximumTrackTintColor={colors.surfaceTertiary}
              thumbTintColor={colors.brandSecondary}
            />
          </>
        )}

        <Text style={styles.section}>CAPTION POSITION</Text>
        <ChipSelector
          testID="caption-position"
          options={config?.caption_positions || []}
          value={captionPosition}
          onChange={setCaptionPosition}
        />

        <Text style={styles.section}>CAPTION SIZE</Text>
        <ChipSelector
          testID="caption-size"
          options={config?.caption_sizes || []}
          value={captionSize}
          onChange={setCaptionSize}
        />

        <Text style={styles.section}>CAPTION FONT</Text>
        <ChipSelector
          testID="caption-font"
          options={config?.caption_fonts || []}
          value={captionFont}
          onChange={setCaptionFont}
        />

        <Text style={styles.section}>CAPTION ANIMATION</Text>
        <ChipSelector
          testID="caption-anim"
          options={config?.caption_anims || []}
          value={captionAnim}
          onChange={setCaptionAnim}
        />

        <Text style={styles.section}>BACKGROUND MOTION</Text>
        <ChipSelector
          testID="bg-motion"
          options={config?.bg_motions || []}
          value={bgMotion}
          onChange={setBgMotion}
        />

        {bgTheme === "custom" && (
          <>
            <Text style={styles.section}>CUSTOM GRADIENT · HEX</Text>
            <View style={styles.colorRow}>
              <ColorField testID="custom-c1" value={customC1} onChange={setCustomC1} />
              <ColorField testID="custom-c2" value={customC2} onChange={setCustomC2} />
            </View>
          </>
        )}

        <View style={styles.toggleRow}>
          <View style={styles.settingLeft}>
            <Ionicons name="flash-outline" size={18} color={colors.onSurfaceSecondary} />
            <View>
              <Text style={styles.settingLabel}>Auto hook title</Text>
              <Text style={styles.toggleSub}>Flash the opening line for the first 2s</Text>
            </View>
          </View>
          <Switch
            testID="hook-toggle"
            value={hookEnabled}
            onValueChange={(v) => { haptic.light(); setHookEnabled(v); }}
            trackColor={{ false: colors.surfaceTertiary, true: colors.brandPrimary }}
            thumbColor="#fff"
          />
        </View>

        <Text style={styles.section}>WATERMARK · OPTIONAL</Text>
        <TextInput
          testID="watermark-input"
          value={watermark}
          onChangeText={setWatermark}
          placeholder="@yourhandle"
          placeholderTextColor={colors.onSurfaceSecondary}
          maxLength={32}
          autoCapitalize="none"
          style={[styles.input, { height: 48, paddingVertical: 0 }]}
        />

        <Text style={styles.section}>END CARD · OPTIONAL</Text>
        <TextInput
          testID="endcard-input"
          value={endcardText}
          onChangeText={setEndcardText}
          placeholder="Follow for more"
          placeholderTextColor={colors.onSurfaceSecondary}
          maxLength={40}
          style={[styles.input, { height: 48, paddingVertical: 0 }]}
        />

        {!!error && (
          <View style={styles.errorBox} testID="create-error">
            <Ionicons name="warning" size={16} color={colors.error} />
            <Text style={styles.errorText}>{error}</Text>
          </View>
        )}
      </KeyboardAwareScrollView>

      <KeyboardStickyView offset={{ closed: 0, opened: insets.bottom }}>
        <View style={[styles.ctaWrap, { paddingBottom: insets.bottom + spacing.sm }]}>
          <PrimaryButton
            testID="generate-reel-button"
            label="Generate Reel"
            icon="film"
            disabled={!canGenerate}
            loading={submitting}
            onPress={generate}
          />
        </View>
      </KeyboardStickyView>

      <OptionSheet
        ref={voiceSheet}
        title="Pick a voice"
        options={voiceOptions}
        selectedId={voiceId}
        onPreview={previewVoice}
        previewingId={previewingVoice}
        onSelect={(id) => { setVoiceId(id); stopPreview(); setPreviewingVoice(null); voiceSheet.current?.dismiss(); }}
      />
      <OptionSheet ref={captionSheet} title="Caption style" options={captionOptions} selectedId={captionStyle} onSelect={(id) => { setCaptionStyle(id); captionSheet.current?.dismiss(); }} />
      <OptionSheet ref={bgSheet} title="Background theme" options={bgOptions} selectedId={bgTheme} onSelect={(id) => { setBgTheme(id); bgSheet.current?.dismiss(); }} />
      <OptionSheet ref={musicSheet} title="Background music" options={musicOptions} selectedId={musicId} onSelect={(id) => { setMusicId(id); musicSheet.current?.dismiss(); }} />
      <PresetSheet ref={presetSheet} currentSettings={currentSettings} onApply={applySettings} />
      <OutroSheet
        ref={outroSheet}
        selectedId={outro?.id || null}
        onSelect={(o) => { setOutro(o); outroSheet.current?.dismiss(); }}
      />
    </View>
  );
}

function SettingRow({
  icon,
  label,
  value,
  onPress,
  dot,
  swatch,
  testID,
}: {
  icon: keyof typeof Ionicons.glyphMap;
  label: string;
  value: string;
  onPress: () => void;
  dot?: string;
  swatch?: string[];
  testID?: string;
}) {
  return (
    <Pressable
      testID={testID}
      onPress={() => {
        haptic.select();
        onPress();
      }}
      style={({ pressed }) => [styles.settingRow, pressed && { backgroundColor: colors.surfaceTertiary }]}
    >
      <View style={styles.settingLeft}>
        <Ionicons name={icon} size={18} color={colors.onSurfaceSecondary} />
        <Text style={styles.settingLabel}>{label}</Text>
      </View>
      <View style={styles.settingRight}>
        {dot && <View style={[styles.miniDot, { backgroundColor: dot }]} />}
        {swatch && (
          <View style={styles.miniSwatchWrap}>
            {swatch.map((c, i) => (
              <View key={i} style={[styles.miniSwatch, { backgroundColor: c }]} />
            ))}
          </View>
        )}
        <Text style={styles.settingValue}>{value}</Text>
        <Ionicons name="chevron-forward" size={16} color={colors.onSurfaceSecondary} />
      </View>
    </Pressable>
  );
}

function ChipSelector({
  options,
  value,
  onChange,
  testID,
}: {
  options: { id: string; name: string }[];
  value: string;
  onChange: (id: string) => void;
  testID?: string;
}) {
  return (
    <View style={styles.chipRow} testID={testID}>
      {options.map((o) => {
        const active = o.id === value;
        return (
          <Pressable
            key={o.id}
            testID={`${testID}-${o.id}`}
            onPress={() => {
              haptic.light();
              onChange(o.id);
            }}
            style={[styles.chip, active && styles.chipActive]}
          >
            <Text style={[styles.chipText, active && styles.chipTextActive]}>{o.name}</Text>
          </Pressable>
        );
      })}
    </View>
  );
}

function ColorField({
  value,
  onChange,
  testID,
}: {
  value: string;
  onChange: (v: string) => void;
  testID?: string;
}) {
  const v = value.trim();
  const valid = /^#?[0-9a-fA-F]{6}$/.test(v);
  const swatch = valid ? (v.startsWith("#") ? v : `#${v}`) : "#000000";
  return (
    <View style={styles.colorField}>
      <View style={[styles.colorSwatch, { backgroundColor: swatch }]} />
      <TextInput
        testID={testID}
        value={value}
        onChangeText={onChange}
        autoCapitalize="characters"
        autoCorrect={false}
        maxLength={7}
        placeholder="#RRGGBB"
        placeholderTextColor={colors.onSurfaceSecondary}
        style={styles.colorInput}
      />
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.surface },
  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.lg,
    paddingBottom: spacing.md,
    borderBottomWidth: 1,
    borderBottomColor: colors.border,
  },
  brand: { fontFamily: font.display, fontSize: 26, color: colors.onSurface, letterSpacing: 1 },
  sub: { fontFamily: font.body, fontSize: 12, color: colors.onSurfaceSecondary, marginTop: 2 },
  aiNote: { fontFamily: font.body, fontSize: 12, color: colors.brandSecondary, marginTop: spacing.sm, lineHeight: 17 },
  creditBanner: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    padding: spacing.md,
    marginBottom: spacing.md,
    borderRadius: radius.md,
    backgroundColor: "rgba(234,179,8,0.12)",
    borderWidth: 1,
    borderColor: "rgba(234,179,8,0.35)",
  },
  creditText: { flex: 1, fontFamily: font.bodyMed, fontSize: 12, color: colors.warning, lineHeight: 16 },
  headerRight: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  batchBtn: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    paddingHorizontal: spacing.md,
    height: 40,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surfaceSecondary,
  },
  batchTxt: { fontFamily: font.bodySemi, fontSize: 13, color: colors.onSurface },
  sectionRow: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  presetPill: {
    flexDirection: "row",
    alignItems: "center",
    gap: 5,
    marginTop: spacing.lg,
    paddingHorizontal: spacing.md,
    height: 30,
    borderRadius: radius.pill,
    borderWidth: 1,
    borderColor: colors.brandPrimary,
    backgroundColor: colors.brandTertiary,
  },
  presetPillTxt: { fontFamily: font.bodySemi, fontSize: 12, color: colors.onBrandTertiary },
  logo: {
    width: 40,
    height: 40,
    borderRadius: radius.md,
    backgroundColor: colors.brandTertiary,
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1,
    borderColor: colors.brandPrimary,
  },
  section: {
    fontFamily: font.bodyBold,
    fontSize: 11,
    letterSpacing: 1.2,
    color: colors.onSurfaceSecondary,
    marginTop: spacing.lg,
    marginBottom: spacing.sm,
  },
  input: {
    backgroundColor: colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    padding: spacing.md,
    fontFamily: font.body,
    fontSize: 15,
    color: colors.onSurface,
    textAlignVertical: "top",
  },
  chipRow: { flexDirection: "row", gap: spacing.sm },
  colorRow: { flexDirection: "row", gap: spacing.sm },
  colorField: {
    flex: 1,
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    backgroundColor: colors.surfaceSecondary,
    borderWidth: 1,
    borderColor: colors.border,
    borderRadius: radius.md,
    paddingHorizontal: spacing.md,
    height: 48,
  },
  colorSwatch: { width: 24, height: 24, borderRadius: 6, borderWidth: 1, borderColor: colors.borderStrong },
  colorInput: { flex: 1, fontFamily: font.bodyMed, fontSize: 15, color: colors.onSurface },
  chip: {
    flex: 1,
    height: 44,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surfaceSecondary,
    alignItems: "center",
    justifyContent: "center",
  },
  chipActive: { borderColor: colors.brand, backgroundColor: colors.brandTertiary },
  chipText: { fontFamily: font.bodySemi, fontSize: 14, color: colors.onSurfaceSecondary },
  chipTextActive: { color: colors.onBrandTertiary },
  scriptHead: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  wordCount: { fontFamily: font.bodyMed, fontSize: 11, color: colors.onSurfaceSecondary, marginTop: spacing.lg },
  settings: {
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surfaceSecondary,
    overflow: "hidden",
  },
  settingRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: spacing.md,
    height: 54,
    borderBottomWidth: 1,
    borderBottomColor: colors.divider,
  },
  settingLeft: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  settingLabel: { fontFamily: font.bodySemi, fontSize: 15, color: colors.onSurface },
  settingRight: { flexDirection: "row", alignItems: "center", gap: spacing.sm },
  settingValue: { fontFamily: font.bodyMed, fontSize: 14, color: colors.onSurfaceSecondary },
  toggleRow: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginTop: spacing.lg,
    padding: spacing.md,
    borderRadius: radius.md,
    borderWidth: 1,
    borderColor: colors.border,
    backgroundColor: colors.surfaceSecondary,
  },
  toggleSub: { fontFamily: font.body, fontSize: 11, color: colors.onSurfaceSecondary, marginTop: 2 },
  miniDot: { width: 12, height: 12, borderRadius: 6 },
  miniSwatchWrap: { flexDirection: "row", borderRadius: radius.sm, overflow: "hidden" },
  miniSwatch: { width: 8, height: 16 },
  errorBox: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.sm,
    marginTop: spacing.lg,
    padding: spacing.md,
    borderRadius: radius.md,
    backgroundColor: "rgba(239,68,68,0.12)",
    borderWidth: 1,
    borderColor: "rgba(239,68,68,0.3)",
  },
  errorText: { flex: 1, fontFamily: font.bodyMed, fontSize: 13, color: colors.brandSecondary },
  ctaWrap: {
    paddingHorizontal: spacing.lg,
    paddingTop: spacing.sm,
    backgroundColor: colors.surface,
    borderTopWidth: 1,
    borderTopColor: colors.border,
  },
});
