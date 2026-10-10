import type { CSSProperties } from "react";

/**
 * UI schema colors: hex / `#rgb` / `#RRGGBB` / `#AARRGGBB` / `0xRRGGBB` / `0xAARRGGBB` (ARGB) → CSS color.
 * Eight-digit `#`/`0x` values use Android-style ARGB (same as CSS would mis-read `#RRGGBBAA`).
 */
function hexArgb8DigitsToRgba(hex8: string): string | null {
  if (!/^[0-9a-fA-F]{8}$/.test(hex8)) return null;
  const n = parseInt(hex8, 16);
  if (Number.isNaN(n)) return null;
  const a = ((n >>> 24) & 0xff) / 255;
  const r = (n >> 16) & 0xff;
  const g = (n >> 8) & 0xff;
  const b = n & 0xff;
  return `rgba(${r},${g},${b},${a})`;
}

export function normalizeSchemaColor(
  input: string | undefined | null,
): string | undefined {
  if (input == null || typeof input !== "string") return undefined;
  const s = input.trim();
  if (s.length === 0) return undefined;
  if (/^0x[0-9a-fA-F]{8}$/.test(s)) {
    return hexArgb8DigitsToRgba(s.slice(2)) ?? s;
  }
  if (/^#[0-9a-fA-F]{8}$/.test(s)) {
    return hexArgb8DigitsToRgba(s.slice(1)) ?? s;
  }
  if (/^0x[0-9a-fA-F]{6}$/.test(s)) {
    return `#${s.slice(2)}`;
  }
  return s;
}

const SHADOW_BY_TYPE: Record<string, string> = {
  outerDefaultXS: "0 1px 2px rgba(0, 0, 0, 0.06)",
  outerDefaultSM:
    "0 1px 3px rgba(0, 0, 0, 0.08), 0 4px 12px rgba(0, 0, 0, 0.04)",
  outerDefaultMD:
    "0 4px 6px -1px rgba(0, 0, 0, 0.08), 0 10px 24px -4px rgba(0, 0, 0, 0.06)",
  outerDefaultLG: "0 10px 40px -8px rgba(0, 0, 0, 0.12)",
  outerFloatingSM: "0 4px 14px rgba(0, 0, 0, 0.12)",
  outerFloatingMD: "0 12px 40px rgba(0, 0, 0, 0.15)",
};

function shadowToCss(o: Record<string, unknown>): string | undefined {
  const typ = o.type;
  if (typeof typ === "string" && SHADOW_BY_TYPE[typ]) {
    return SHADOW_BY_TYPE[typ];
  }

  const r = o.radius;
  if (typeof r !== "number") return undefined;

  const ox = typeof o.offsetX === "number" ? o.offsetX : 0;
  const oy = typeof o.offsetY === "number" ? o.offsetY : 0;
  const c =
    normalizeSchemaColor(typeof o.color === "string" ? o.color : undefined) ??
    "rgba(0, 0, 0, 0.12)";

  if (typ === "blur") {
    return `${ox}px ${oy}px ${r}px ${c}`;
  }

  return `${ox}px ${oy}px ${r}px ${c}`;
}

function backgroundSizeFromSchema(bis: unknown): string | undefined {
  if (typeof bis === "string" && bis.length > 0) {
    const k = bis.toLowerCase();
    if (k === "fill") return "100% 100%";
    return bis;
  }
  if (bis && typeof bis === "object" && !Array.isArray(bis)) {
    const o = bis as Record<string, unknown>;
    const bw = o.width;
    const bh = o.height;
    if (typeof bw === "number" && typeof bh === "number") {
      return `${bw}px ${bh}px`;
    }
  }
  return undefined;
}

/**
 * Applies fontScaleMode / min / max as multipliers on a base px size (schema "custom" mode).
 */
export function applyFontScale(
  basePx: number | undefined,
  styles?: Record<string, unknown>,
): number | undefined {
  if (basePx === undefined || typeof basePx !== "number") return basePx;
  if (styles?.fontScaleMode !== "custom") return basePx;
  const minS =
    typeof styles.minFontScale === "number" ? styles.minFontScale : undefined;
  const maxS =
    typeof styles.maxFontScale === "number" ? styles.maxFontScale : undefined;
  let mul = 1;
  if (minS !== undefined && maxS !== undefined) {
    mul = Math.max(minS, Math.min(maxS, 1));
  } else if (maxS !== undefined) mul = maxS;
  else if (minS !== undefined) mul = minS;
  return Math.round(basePx * mul * 100) / 100;
}

/**
 * Maps {@link UI_SCHEMA_PROMPT} **Common Styles** to React inline `style`.
 * Only documented keys are applied; unknown keys are ignored.
 */
export function mergeCommonStyles(styles?: Record<string, unknown>): CSSProperties {
  if (!styles || typeof styles !== "object") return {};
  const out: CSSProperties = {};

  const w = styles.width;
  if (styles.__stackChild === true) { out.pointerEvents = "auto"; out.flexShrink = 0; }
  const h = styles.height;
  if (typeof w === "number") out.width = w;
  else if (w === "matchParent") out.width = "100%";
  else if (typeof w === "string" && /^\d+(?:\.\d+)?%$/.test(w)) out.width = w;

  if (typeof h === "number") out.height = h;
  else if (typeof h === "string" && /^\d+(?:\.\d+)?%$/.test(h)) out.height = h;
  else if (h === "matchParent") {
    out.height = "100%";
    out.alignSelf = "stretch";
  }

  const fs = styles.flexShrink;
  if (typeof fs === "number") out.flexShrink = fs;
  if (typeof styles.aspectRatio === "number" && styles.aspectRatio > 0) out.aspectRatio = styles.aspectRatio;
  if (typeof styles.opacity === "number") out.opacity = styles.opacity;
  for (const key of ["minWidth", "minHeight", "maxWidth", "maxHeight"] as const) {
    if (typeof styles[key] === "number") out[key] = styles[key];
  }
  const gradient = styles.linearGradient;
  if (gradient && typeof gradient === "object" && !Array.isArray(gradient)) {
    const g = gradient as Record<string, unknown>;
    const directions: Record<string, string> = { Left: "to left", Right: "to right", Top: "to top", Bottom: "to bottom", LeftTop: "to top left", LeftBottom: "to bottom left", RightTop: "to top right", RightBottom: "to bottom right" };
    const angle = typeof g.angle === "number" ? `${g.angle}deg` : directions[String(g.direction)] ?? "to bottom";
    if (Array.isArray(g.colors) && g.colors.length >= 2) {
      const stops = g.colors.map(stop => Array.isArray(stop) ? `${normalizeSchemaColor(String(stop[0]))} ${Number(stop[1]) * 100}%` : normalizeSchemaColor(String(stop)));
      out.backgroundImage = `linear-gradient(${angle}, ${stops.join(", ")})`;
    }
  }
  const blur = styles.backdropBlur;
  if (blur && typeof blur === "object" && "radius" in blur && typeof blur.radius === "number") out.backdropFilter = `blur(${blur.radius}px)`;

  const bs = backgroundSizeFromSchema(styles.backgroundImageSizeWithStyle);
  if (bs !== undefined) out.backgroundSize = bs;

  const cs = styles.constraintSize;
  if (cs && typeof cs === "object" && !Array.isArray(cs)) {
    const o = cs as Record<string, unknown>;
    if (typeof o.minWidth === "number") out.minWidth = o.minWidth;
    if (typeof o.maxWidth === "number") out.maxWidth = o.maxWidth;
    if (typeof o.minHeight === "number") out.minHeight = o.minHeight;
    if (typeof o.maxHeight === "number") out.maxHeight = o.maxHeight;
  }

  const bgImg = styles.backgroundImage;
  if (typeof bgImg === "string" && bgImg.trim() !== "") {
    out.backgroundImage = normalizeBackgroundImageValue(bgImg.trim());
  }

  Object.assign(out, boxEdgeToCss(styles.margin, "margin"));
  Object.assign(out, boxEdgeToCss(styles.padding, "padding"));

  const br = styles.borderRadius;
  if (typeof br === "number") {
    out.borderRadius = br;
  } else if (br && typeof br === "object" && !Array.isArray(br)) {
    const o = br as Record<string, unknown>;
    if (typeof o.topLeft === "number") out.borderTopLeftRadius = o.topLeft;
    if (typeof o.topRight === "number") out.borderTopRightRadius = o.topRight;
    if (typeof o.bottomRight === "number") out.borderBottomRightRadius = o.bottomRight;
    if (typeof o.bottomLeft === "number") out.borderBottomLeftRadius = o.bottomLeft;
  }

  const vis = styles.visibility;
  if (vis === "visible") out.visibility = "visible";
  else if (vis === "hidden") out.visibility = "hidden";
  else if (vis === "none") out.display = "none";

  if (styles.clip === true) {
    out.overflow = "hidden";
    // Explicit compositor clipping also contains backdrop-filter layers in Chromium.
    const radii = typeof br === "number" ? `${br}px` : br && typeof br === "object" ?
      ["topLeft", "topRight", "bottomRight", "bottomLeft"].map(k => `${Number((br as Record<string, unknown>)[k]) || 0}px`).join(" ") : "0px";
    out.clipPath = `inset(0 round ${radii})`;
    out.isolation = "isolate";
  }

  const bgc = normalizeSchemaColor(
    typeof styles.backgroundColor === "string" ? styles.backgroundColor : undefined,
  );
  if (bgc) out.backgroundColor = bgc;

  const bw = styles.borderWidth;
  if (typeof bw === "number" || typeof bw === "string") {
    out.borderWidth = bw;
    out.borderStyle = "solid";
  }

  const bc = normalizeSchemaColor(
    typeof styles.borderColor === "string" ? styles.borderColor : undefined,
  );
  if (bc) out.borderColor = bc;

  const lw = styles.layoutWeight;
  if (typeof lw === "number") {
    out.flexGrow = lw;
    if (lw > 0) out.flexBasis = 0;
  }

  const sh = styles.shadow;
  if (typeof sh === "string" && SHADOW_BY_TYPE[sh]) out.boxShadow = SHADOW_BY_TYPE[sh];
  if (sh && typeof sh === "object" && !Array.isArray(sh)) {
    const box = shadowToCss(sh as Record<string, unknown>);
    if (box) out.boxShadow = box;
  }

  return out;
}

function normalizeBackgroundImageValue(s: string): string {
  const lower = s.toLowerCase();
  if (
    lower.startsWith("url(") ||
    lower.startsWith("linear-gradient") ||
    lower.startsWith("radial-gradient") ||
    lower.startsWith("conic-gradient")
  ) {
    return s;
  }
  const escaped = s.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
  return `url("${escaped}")`;
}

function boxEdgeToCss(
  v: unknown,
  kind: "margin" | "padding",
): CSSProperties {
  const out: CSSProperties = {};
  if (typeof v === "number") {
    if (kind === "margin") out.margin = v;
    else out.padding = v;
    return out;
  }
  if (!v || typeof v !== "object" || Array.isArray(v)) return out;
  const o = v as Record<string, unknown>;
  const top = o.top;
  const right = o.right;
  const bottom = o.bottom;
  const left = o.left;
  if (kind === "margin") {
    if (typeof top === "number") out.marginTop = top;
    if (typeof right === "number") out.marginRight = right;
    if (typeof bottom === "number") out.marginBottom = bottom;
    if (typeof left === "number") out.marginLeft = left;
  } else {
    if (typeof top === "number") out.paddingTop = top;
    if (typeof right === "number") out.paddingRight = right;
    if (typeof bottom === "number") out.paddingBottom = bottom;
    if (typeof left === "number") out.paddingLeft = left;
  }
  return out;
}

/** True if `v` looks like Common Styles `{ top?, right?, bottom?, left? }` (numeric px). */
export function isEdgeInsetsRecord(v: unknown): boolean {
  if (v === null || typeof v !== "object" || Array.isArray(v)) return false;
  const o = v as Record<string, unknown>;
  return (
    typeof o.top === "number" ||
    typeof o.right === "number" ||
    typeof o.bottom === "number" ||
    typeof o.left === "number"
  );
}

/** Common Styles `padding: { top, right, bottom, left }` → React longhands; otherwise `{}`. */
export function paddingInsetsToCss(padding: unknown): CSSProperties {
  if (!isEdgeInsetsRecord(padding)) return {};
  return boxEdgeToCss(padding, "padding");
}
