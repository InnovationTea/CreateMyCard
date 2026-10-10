import {
  createContext,
  useContext,
  type CSSProperties,
  type ReactNode,
} from "react";
import { isEdgeInsetsRecord, mergeCommonStyles } from "./extended/common-styles.js";

/**
 * Number of Card ancestors wrapping this node.
 * Default border + chrome: depth 0 (root) and depth 1 (direct child sections).
 * Deeper nesting: no default border unless `strokeThickness` + `strokeColor` are set (avoids heavy “boxes in boxes”).
 */
export const CardDepthContext = createContext(0);

/** depth 0 and 1 use default border + shadow when custom stroke is absent (depth 2+ does not). */
const DEFAULT_BORDER_MAX_DEPTH = 2;

export type CardStrokeThickness =
  | number
  | { top?: number; right?: number; bottom?: number; left?: number };

/** Per-corner radii in px: top-left, top-right, bottom-right, bottom-left. */
export type CardRadius = number | [number, number, number, number];

const DEFAULT_CARD_GRADIENT =
  "linear-gradient(160deg, #ffffff 0%, #f8fafc 100%)";

export interface CardProps {
  title?: string;
  description?: string;
  width?: number | "matchParent";
  height?: number | "matchParent";
  /** Background color */
  fill?: string;
  /** Border width in px: a number, or per-edge object. Requires `strokeColor`. */
  strokeThickness?: CardStrokeThickness;
  /** Border color (hex, etc.). Requires `strokeThickness`. */
  strokeColor?: string;
  layout?: "vertical" | "horizontal";
  justifyContent?: "flex_start" | "center" | "flex_end" | "space_between" | "space_around";
  alignItems?: "flex_start" | "center" | "flex_end" | "stretch";
  /** Gap between children in pixels */
  gap?: number;
  /** Mini DSL: number or tuple. Common Styles (a2ui / flattened): `{ top, right, bottom, left }`. */
  padding?:
    | number
    | [number, number]
    | [number, number, number, number]
    | { top?: number; right?: number; bottom?: number; left?: number };
  /** Corner radius in px: single value or [tl, tr, br, bl]. Default 12. */
  radius?: CardRadius;
  /** Image URL or `url(...)` — blended with `fill` using `backgroundBlendMode` (default multiply). */
  backgroundImage?: string;
  /**
   * CSS `background-blend-mode` between the image layer and the fill layer.
   * Default `multiply` (正片叠底). Use `normal` to disable blending.
   */
  backgroundBlendMode?: string;
  /** CSS `background-position` for the image layer (default `center`). */
  backgroundPosition?: string;
  /** CSS `background-size` for the image layer (default `cover`). */
  backgroundSize?: string;
  /** UI schema Common Styles (merged onto the card container after DSL props). */
  styles?: Record<string, unknown>;
  children?: ReactNode;
  /** Protocol / renderer may pass Common Styles at the top level after `styles` is flattened. */
  [key: string]: unknown;
}

const justifyMap: Record<string, CSSProperties["justifyContent"]> = {
  flex_start: "flex-start",
  center: "center",
  flex_end: "flex-end",
  space_between: "space-between",
  space_around: "space-around",
};

const alignMap: Record<string, CSSProperties["alignItems"]> = {
  flex_start: "flex-start",
  center: "center",
  flex_end: "flex-end",
  stretch: "stretch",
};

function paddingToCss(
  p: number | [number, number] | [number, number, number, number] | undefined,
): string | undefined {
  if (p === undefined) return undefined;
  if (typeof p === "number") return `${p}px`;
  if (!Array.isArray(p)) return undefined;
  if (p.length === 2) return `${p[0]}px ${p[1]}px`;
  return `${p[0]}px ${p[1]}px ${p[2]}px ${p[3]}px`;
}

function radiusToCss(
  radius: CardRadius | undefined,
  defaultPx: number,
): string {
  if (radius === undefined) return `${defaultPx}px`;
  if (typeof radius === "number") return `${radius}px`;
  return `${radius[0]}px ${radius[1]}px ${radius[2]}px ${radius[3]}px`;
}

/** Border styles from flat stroke props; used by Card and Button. */
export function strokeToCss(
  thickness: CardStrokeThickness,
  strokeColor: string,
): CSSProperties {
  if (typeof thickness === "number") {
    return {
      borderWidth: thickness,
      borderStyle: "solid",
      borderColor: strokeColor,
    };
  }
  return {
    borderStyle: "solid",
    borderColor: strokeColor,
    borderTopWidth: thickness.top ?? 0,
    borderRightWidth: thickness.right ?? 0,
    borderBottomWidth: thickness.bottom ?? 0,
    borderLeftWidth: thickness.left ?? 0,
  };
}

export function normalizeBackgroundImage(src: string): string {
  const s = src.trim();
  if (s.startsWith("url(") || s.startsWith("linear-gradient(")) return s;
  const escaped = s.replace(/\\/g, "\\\\").replace(/"/g, '\\"');
  return `url("${escaped}")`;
}

function looksLikeCssGradient(s: string): boolean {
  const t = s.trim().toLowerCase();
  return (
    t.startsWith("linear-gradient") ||
    t.startsWith("radial-gradient") ||
    t.startsWith("conic-gradient")
  );
}

/** Stacks image on top of solid or gradient fill; uses background-blend-mode (default multiply). */
function applyCardBackgroundLayers(
  outer: CSSProperties,
  opts: {
    backgroundImage: string;
    fill: string | undefined;
    backgroundBlendMode: string | undefined;
    backgroundPosition: string | undefined;
    backgroundSize: string | undefined;
  },
): void {
  const url = normalizeBackgroundImage(opts.backgroundImage);
  const blend =
    opts.backgroundBlendMode === undefined || opts.backgroundBlendMode === ""
      ? "multiply"
      : opts.backgroundBlendMode;
  const pos = opts.backgroundPosition ?? "center";
  const size = opts.backgroundSize ?? "cover";

  const baseFill = opts.fill ?? DEFAULT_CARD_GRADIENT;

  if (looksLikeCssGradient(baseFill)) {
    outer.backgroundImage = `${url}, ${baseFill}`;
    outer.backgroundSize = `${size}, cover`;
    outer.backgroundPosition = `${pos}, center`;
    outer.backgroundRepeat = "no-repeat, no-repeat";
    outer.backgroundBlendMode = blend as CSSProperties["backgroundBlendMode"];
  } else {
    outer.backgroundColor = baseFill;
    outer.backgroundImage = url;
    outer.backgroundSize = size;
    outer.backgroundPosition = pos;
    outer.backgroundRepeat = "no-repeat";
    outer.backgroundBlendMode = blend as CSSProperties["backgroundBlendMode"];
  }
}

export function Card({
  title,
  description,
  width,
  height,
  fill,
  strokeThickness,
  strokeColor,
  layout = "vertical",
  justifyContent = "flex_start",
  alignItems = "stretch",
  gap = 8,
  padding,
  radius,
  backgroundImage,
  backgroundBlendMode,
  backgroundPosition,
  backgroundSize,
  styles,
  children,
  ...rest
}: CardProps) {
  const depth = useContext(CardDepthContext);
  const useDefaultChrome = depth < DEFAULT_BORDER_MAX_DEPTH;

  // Common Styles may live in `styles` (a2ui) or on flattened top-level props (post-render-tree).
  // Flat keys win so renderer `flattenStyles` output overrides legacy `styles` for the same key.
  const commonStyleSource: Record<string, unknown> = {
    ...(styles && typeof styles === "object" && !Array.isArray(styles) ? styles : {}),
    ...(rest as Record<string, unknown>),
  };
  // DSL `padding` as Common Styles edge object is destructured out of `rest`; feed it into
  // mergeCommonStyles so flattened a2ui `styles.padding` still applies (paddingToCss only supports number/tuple).
  if (isEdgeInsetsRecord(padding)) {
    commonStyleSource.padding = padding;
  }

  const justify = justifyMap[justifyContent] ?? "flex-start";
  const align = alignMap[alignItems] ?? "stretch";
  const flexDir: CSSProperties["flexDirection"] =
    layout === "horizontal" ? "row" : "column";

  const padCss = paddingToCss(
    typeof padding === "number" || Array.isArray(padding) ? padding : undefined,
  );
  const paddingFromCommonObject = isEdgeInsetsRecord(padding);
  const defaultPadding = padCss ?? (paddingFromCommonObject ? undefined : 20);

  const outer: CSSProperties = {
    margin: 0,
    boxSizing: "border-box",
    borderRadius: radiusToCss(radius, 12),
    ...(defaultPadding !== undefined ? { padding: defaultPadding } : {}),
    display: "flex",
    flexDirection: "column",
    alignItems: "stretch",
  };

  // Root and first-level child Cards: framed. Deeper nesting: lighter (no default border).
  if (useDefaultChrome) {
    outer.boxShadow =
      "0 1px 3px rgba(15, 23, 42, 0.06), 0 4px 12px rgba(15, 23, 42, 0.04)";
  } else {
    outer.border = "none";
    outer.boxShadow = "0 1px 2px rgba(15, 23, 42, 0.05)";
  }

  if (width !== undefined) {
    if (width === "matchParent") outer.width = "100%";
    else outer.width = width;
  }
  // `height: 100%` alone fixes the card to the parent height; when content is taller than
  // that area, it spills outside the border. Prefer growing with content while still
  // filling at least the container when using matchParent.
  // Never use overflow:auto inside the card — always grow with content (page scrolls instead).
  outer.overflow = "visible";
  if (height !== undefined) {
    if (height === "matchParent") {
      outer.minHeight = "100%";
      outer.height = "auto";
      outer.alignSelf = "stretch";
    } else {
      // Numeric height from DSL = minimum height; allow expansion past it.
      outer.minHeight = height;
      outer.height = "auto";
    }
  } else {
    outer.height = "auto";
  }

  if (strokeThickness !== undefined && strokeColor !== undefined) {
    Object.assign(outer, strokeToCss(strokeThickness, strokeColor));
  } else if (useDefaultChrome) {
    outer.border = "1px solid rgba(15, 23, 42, 0.12)";
  }

  if (backgroundImage !== undefined && backgroundImage.trim() !== "") {
    applyCardBackgroundLayers(outer, {
      backgroundImage,
      fill,
      backgroundBlendMode,
      backgroundPosition,
      backgroundSize,
    });
  } else if (fill !== undefined) {
    outer.background = fill;
  } else {
    outer.background = DEFAULT_CARD_GRADIENT;
  }

  Object.assign(outer, mergeCommonStyles(commonStyleSource));

  // Common Styles often set `height` as a number → mergeCommonStyles applies fixed
  // `height`, which with `overflow: visible` lets content paint outside the card. Match DSL
  // `height` prop semantics: numeric height = minimum; grow with content.
  const styleHeight = commonStyleSource.height;
  if (typeof styleHeight === "number") {
    outer.height = "auto";
    const prev = outer.minHeight;
    if (typeof prev === "number") {
      outer.minHeight = Math.max(prev, styleHeight);
    } else if (prev === undefined) {
      outer.minHeight = styleHeight;
    }
    // If prev is non-numeric (e.g. "100%" from matchParent), keep it; drop fixed height only.
  }

  const body: CSSProperties = {
    display: "flex",
    flexDirection: flexDir,
    gap,
    justifyContent: justify,
    alignItems: align,
    minWidth: 0,
    minHeight: "min-content",
    flex: "none",
  };

  return (
    <CardDepthContext.Provider value={depth + 1}>
      <article style={outer}>
        {title && (
          <h2
            style={{
              margin: "0 0 6px",
              fontSize: 17,
              fontWeight: 600,
              color: "#0f172a",
              letterSpacing: "-0.02em",
            }}
          >
            {title}
          </h2>
        )}
        {description && (
          <p
            style={{
              margin: "0 0 14px",
              fontSize: 13,
              lineHeight: 1.5,
              color: "#64748b",
            }}
          >
            {description}
          </p>
        )}
        <div style={body}>{children}</div>
      </article>
    </CardDepthContext.Provider>
  );
}
