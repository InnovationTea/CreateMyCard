"use client";
import { useState, type CSSProperties } from "react";
import { mergeCommonStyles, normalizeSchemaColor } from "./common-styles.js";
import { domProps } from "./dom-props.js";
import { HARMONY_BORDER } from "./harmony-defaults.js";

export interface ExtendedImageProps {
  src?: string;
  [key: string]: unknown;
}

const fitMap: Record<string, CSSProperties["objectFit"]> = {
  fill: "fill",
  contain: "contain",
  cover: "cover",
  auto: "fill",
  none: "none",
  scaleDown: "scale-down",
};

/** Positional presets: fixed alignment, no scale (schema: 保持原有尺寸). */
const posMap: Record<string, string> = {
  topStart: "left top",
  top: "center top",
  topEnd: "right top",
  start: "left center",
  center: "center center",
  end: "right center",
  bottomStart: "left bottom",
  bottom: "center bottom",
  bottomEnd: "right bottom",
};

function readAspectRatio(styles: Record<string, unknown>): number | undefined {
  const primary =
    typeof styles.aspectRatio === "number" && styles.aspectRatio > 0
      ? styles.aspectRatio
      : undefined;
  if (primary !== undefined) return primary;
  const legacy =
    typeof styles.aspectRadio === "number" && styles.aspectRadio > 0
      ? styles.aspectRadio
      : undefined;
  return legacy;
}

function imgSchema(styles?: Record<string, unknown>): CSSProperties {
  if (!styles) return {};
  const o: CSSProperties = {};
  const aspect = readAspectRatio(styles);
  if (aspect !== undefined) o.aspectRatio = aspect;
  const of = styles.objectFit;
  if (typeof of === "string") {
    if (of in fitMap) {
      o.objectFit = fitMap[of]!;
    } else if (of in posMap) {
      o.objectFit = "none";
      o.objectPosition = posMap[of]!;
    } else if (of === "matrix") {
      o.objectFit = "none";
      const mtx = styles.imageMatrix;
      if (typeof mtx === "string" && mtx.trim().length > 0) {
        o.transform = mtx.trim();
      }
    }
  }
  return o;
}

export function ExtendedImage({ src = "", ...styleProps }: ExtendedImageProps) {
  const [failedSource, setFailedSource] = useState<string | null>(null);
  const s = styleProps as Record<string, unknown>;
  const common = mergeCommonStyles(s);
  const img = imgSchema(s);
  const base: CSSProperties = {
    display: "block",
    maxWidth: "100%",
    height: "auto",
    objectFit: "cover",
    ...common,
    ...img,
  };
  // Debug Tools deliberately does not expose the Next.js /img-proxy endpoint:
  // external images remain browser-direct, while repository assets use /resources/.
  const source = src.startsWith("resources/") ? `/${src}` : src;
  const fill = typeof s.fillColor === "string" && /\.svg(?:$|[?#])/i.test(source) ? normalizeSchemaColor(s.fillColor) : undefined;
  if (!source || failedSource === source) return <span {...domProps(s)} role="img" aria-label={`素材未找到：${src}`} title={src} style={{ ...base, display: "grid", placeItems: "center", border: "1px dashed #b57b43", color: "#b57b43", fontSize: 12 }}>?</span>;
  if (fill) {
    const mask = `url(${JSON.stringify(source)})`;
    return <span {...domProps(s)} role="img" style={{ ...base, backgroundColor: fill, maskImage: mask, WebkitMaskImage: mask, maskSize: "contain", WebkitMaskSize: "contain", maskRepeat: "no-repeat", WebkitMaskRepeat: "no-repeat", maskPosition: "center", WebkitMaskPosition: "center" }}>
      <img src={source} alt="" onError={() => setFailedSource(source)} style={{ width: "100%", height: "100%", opacity: 0 }} />
    </span>;
  }
  return <img {...domProps(s)} src={source} alt="" style={base} onError={() => setFailedSource(source)} />;
}

export interface ExtendedDividerProps {
  [key: string]: unknown;
}

export function ExtendedDivider({ ...styleProps }: ExtendedDividerProps) {
  const s = styleProps as Record<string, unknown>;
  const common = mergeCommonStyles(s);
  const stroke = typeof s.strokeWidth === "number" ? s.strokeWidth : 1;
  const color = normalizeSchemaColor(typeof s.color === "string" ? s.color : undefined) ?? HARMONY_BORDER;
  const vertical = s.vertical === true;
  return <div {...domProps(s)} role="separator" aria-orientation={vertical ? "vertical" : "horizontal"} style={{
    width: vertical ? stroke : "100%", height: vertical ? "100%" : stroke,
    margin: 0, flexShrink: 0, backgroundColor: stroke === 0 ? "transparent" : color,
    ...common,
  }} />;
}
