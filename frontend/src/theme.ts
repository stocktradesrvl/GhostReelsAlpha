// Faceless AI Reels — Dark-First Utility theme tokens.
export const colors = {
  surface: "#09090B",
  surfaceSecondary: "#18181B",
  surfaceTertiary: "#27272A",
  surfaceElevated: "#1F1F23",
  onSurface: "#FAFAFA",
  onSurfaceSecondary: "#A1A1AA",
  onSurfaceTertiary: "#D4D4D8",
  brand: "#EF4444",
  brandPrimary: "#DC2626",
  brandSecondary: "#F87171",
  brandTertiary: "#450A0A",
  onBrandTertiary: "#FECACA",
  onBrand: "#FFFFFF",
  success: "#22C55E",
  warning: "#EAB308",
  error: "#EF4444",
  border: "#27272A",
  borderStrong: "#52525B",
  divider: "#18181B",
} as const;

export const spacing = {
  xs: 4,
  sm: 8,
  md: 12,
  lg: 16,
  xl: 24,
  xxl: 32,
  xxxl: 48,
} as const;

export const radius = {
  sm: 4,
  md: 8,
  lg: 12,
  xl: 18,
  pill: 999,
} as const;

export const font = {
  display: "BarlowCondensed-Bold",
  displaySemi: "BarlowCondensed-SemiBold",
  displayMed: "BarlowCondensed-Medium",
  body: "Manrope-Regular",
  bodyMed: "Manrope-Medium",
  bodySemi: "Manrope-SemiBold",
  bodyBold: "Manrope-Bold",
} as const;
