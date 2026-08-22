import { BottomTabBar, BottomTabBarProps } from "@react-navigation/bottom-tabs";
import React, { createContext, useContext, useRef } from "react";
import { NativeScrollEvent, NativeSyntheticEvent, View } from "react-native";
import Animated, { useAnimatedStyle, useSharedValue, withTiming } from "react-native-reanimated";

type Ctx = { show: () => void; hide: () => void; translate: Animated.SharedValue<number> };

const TabBarCtx = createContext<Ctx | null>(null);

export function TabBarVisibilityProvider({ children }: { children: React.ReactNode }) {
  const translate = useSharedValue(0);
  const show = () => { translate.value = withTiming(0, { duration: 180 }); };
  const hide = () => { translate.value = withTiming(140, { duration: 200 }); };
  return <TabBarCtx.Provider value={{ show, hide, translate }}>{children}</TabBarCtx.Provider>;
}

export function useHidingTabBar() {
  const ctx = useContext(TabBarCtx);
  const lastY = useRef(0);
  const onScroll = (e: NativeSyntheticEvent<NativeScrollEvent>) => {
    if (!ctx) return;
    const y = e.nativeEvent.contentOffset.y;
    const dy = y - lastY.current;
    if (y <= 4) ctx.show();
    else if (dy > 6) ctx.hide();
    else if (dy < -6) ctx.show();
    lastY.current = y;
  };
  return { onScroll, scrollEventThrottle: 16 };
}

export function HidingTabBar(props: BottomTabBarProps) {
  const ctx = useContext(TabBarCtx);
  const style = useAnimatedStyle(() => ({
    transform: [{ translateY: ctx ? ctx.translate.value : 0 }],
  }));
  if (!ctx) {
    return <BottomTabBar {...props} />;
  }
  return (
    <Animated.View style={[{ position: "absolute", left: 0, right: 0, bottom: 0 }, style]}>
      <View>
        <BottomTabBar {...props} />
      </View>
    </Animated.View>
  );
}
