import type { CSSProperties } from "react";
import { isVeryLightTextFill } from "./color-utils.js";
import { resolveFontFamily } from "./font-utils.js";

export interface TextProps {
  content?: string;
  fontSize?: number;
  fontWeight?: "300" | "400" | "500" | "600" | "700";
  letterSpacing?: number;
  lineHeight?: number;
  /** Text color (hex), e.g. "#1A1A1A" */
  fill?: string;
  fontFamily?: string;
  fontStyle?: "normal" | "italic" | "oblique";
  width?: number | "matchParent";
}

export function Text({
  content,
  fontSize,
  fontWeight,
  letterSpacing,
  lineHeight,
  fill,
  fontFamily,
  fontStyle,
  width,
}: TextProps) {
  const color =
    fill !== undefined && isVeryLightTextFill(fill)
      ? "#0f172a"
      : (fill ?? "#334155");

  const style: CSSProperties = {
    margin: 0,
    padding: 0,
    fontSize: fontSize ?? 14,
    lineHeight: lineHeight ?? 1.6,
    color,
    /** Typography only — no chip border/background; use Card for grouping. */
    background: "transparent",
    border: "none",
    overflowWrap: "anywhere",
  };

  if (fontWeight !== undefined) style.fontWeight = fontWeight;
  if (letterSpacing !== undefined) style.letterSpacing = `${letterSpacing}px`;
  const resolvedFamily = resolveFontFamily(fontFamily);
  if (resolvedFamily !== undefined) style.fontFamily = resolvedFamily;
  if (fontStyle !== undefined) style.fontStyle = fontStyle;

  if (width !== undefined) {
    if (width === "matchParent") {
      style.width = "100%";
      style.boxSizing = "border-box";
    } else {
      style.width = width;
    }
  }

  return <p style={style}>{content ?? ""}</p>;
}
