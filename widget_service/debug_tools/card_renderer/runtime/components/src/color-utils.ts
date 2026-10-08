/**
 * Hex / contrast helpers so light backgrounds never get white label text (invisible on white).
 * Supports `#rgb`, `#RRGGBB`, and `#AARRGGBB` (ARGB, same as normalizeSchemaColor).
 */

export function parseHexColor(input: string): { r: number; g: number; b: number } | null {
  let s = input.trim();
  if (s.startsWith("#")) s = s.slice(1);
  if (s.length === 3) {
    s = s
      .split("")
      .map((c) => c + c)
      .join("");
  }
  if (s.length === 8) {
    const n = parseInt(s, 16);
    if (Number.isNaN(n)) return null;
    return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
  }
  if (s.length !== 6) return null;
  const n = parseInt(s, 16);
  if (Number.isNaN(n)) return null;
  return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
}

/** WCAG relative luminance for sRGB 0–255. */
export function relativeLuminance(r: number, g: number, b: number): number {
  const lin = [r, g, b].map((v) => {
    v /= 255;
    return v <= 0.03928 ? v / 12.92 : Math.pow((v + 0.055) / 1.055, 2.4);
  });
  return 0.2126 * lin[0]! + 0.7152 * lin[1]! + 0.0722 * lin[2]!;
}

/** True when hex background should use dark foreground for readable contrast. */
export function isLightSolidBackground(hex: string): boolean {
  const rgb = parseHexColor(hex);
  if (!rgb) return false;
  return relativeLuminance(rgb.r, rgb.g, rgb.b) > 0.55;
}

/**
 * Text `fill`: only override near-white / invisible-on-page cases so colored tints stay.
 */
export function isVeryLightTextFill(hex: string): boolean {
  const rgb = parseHexColor(hex);
  if (!rgb) return false;
  return relativeLuminance(rgb.r, rgb.g, rgb.b) > 0.85;
}
