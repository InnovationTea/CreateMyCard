"use client";

import { useId } from "react";
import { domProps } from "./dom-props.js";
import type { CSSProperties, MouseEventHandler } from "react";
import { applyFontScale, mergeCommonStyles, normalizeSchemaColor } from "./common-styles.js";
import { HARMONY_TEXT_PRIMARY } from "./harmony-defaults.js";

export interface ExtendedTextProps {
  content?: string;
  /** When set (e.g. from component `action.functionCall` → `openUrl` in the renderer), text is clickable. */
  onClick?: MouseEventHandler<HTMLElement>;
  [key: string]: unknown;
}

const DECORATION_STYLE_MAP: Record<string, CSSProperties["textDecorationStyle"]> = {
  solid: "solid",
  doubleE: "double",
  dotted: "dotted",
  dashed: "dashed",
  wavy: "wavy",
};

function textSchema(styles?: Record<string, unknown>): CSSProperties {
  if (!styles) return {};
  const o: CSSProperties = {};
  let fs = typeof styles.fontSize === "number" ? styles.fontSize : undefined;
  fs = applyFontScale(fs, styles);
  if (typeof fs === "number") o.fontSize = fs;

  const fw = styles.fontWeight;
  if (typeof fw === "number" && [100, 200, 300, 400, 500, 600, 700, 800, 900].includes(fw)) {
    o.fontWeight = fw;
  } else if (fw === "300" || fw === "400" || fw === "500" || fw === "600" || fw === "700" || fw === "normal" || fw === "bold") {
    o.fontWeight = fw;
  }
  const fc = normalizeSchemaColor(typeof styles.fontColor === "string" ? styles.fontColor : undefined);
  if (fc) o.color = fc;
  const ta = styles.textAlign;
  if (ta === "start" || ta === "center" || ta === "end" || ta === "justify") {
    o.textAlign = ta;
  }

  const to = styles.textOverflow;
  if (to === "ellipsis") {
    o.textOverflow = "ellipsis";
    o.overflow = "hidden";
    o.whiteSpace = "nowrap";
  } else if (to === "clip") {
    o.textOverflow = "clip";
  } else if (to === "none") {
    o.textOverflow = "clip";
    o.whiteSpace = "normal";
  }
  // marquee: handled in component wrapper

  const ml = styles.maxLines;
  if (typeof ml === "number" && ml > 0) {
    o.display = "-webkit-box";
    o.WebkitBoxOrient = "vertical";
    o.WebkitLineClamp = ml;
    o.overflow = "hidden";
    o.whiteSpace = "normal";
  }

  const wb = styles.wordBreak;
  if (wb === "normal") {
    o.wordBreak = "normal";
    o.overflowWrap = "normal";
  } else if (wb === "breakAll") {
    o.wordBreak = "break-all";
  } else if (wb === "breakWord") {
    o.overflowWrap = "break-word";
  } else if (wb === "hyphenation") {
    o.hyphens = "auto";
    o.wordBreak = "normal";
    o.overflowWrap = "break-word";
  }

  const mfs = styles.maxFontSize;
  if (typeof o.fontSize === "number" && typeof mfs === "number" && o.fontSize > mfs) {
    o.fontSize = mfs;
  }

  const dec = styles.decoration;
  if (dec && typeof dec === "object" && !Array.isArray(dec)) {
    const d = dec as Record<string, unknown>;
    const ty = d.type;
    if (ty === "underline") o.textDecorationLine = "underline";
    else if (ty === "overline") o.textDecorationLine = "overline";
    else if (ty === "lineThrough") o.textDecorationLine = "line-through";
    else if (ty === "none") o.textDecorationLine = "none";

    const st = d.style;
    if (typeof st === "string" && st in DECORATION_STYLE_MAP) {
      o.textDecorationStyle = DECORATION_STYLE_MAP[st]!;
    }
    const decCol = normalizeSchemaColor(typeof d.color === "string" ? d.color : undefined);
    if (decCol) o.textDecorationColor = decCol;
  }

  return o;
}

export function ExtendedText({ content, onClick, ...styleProps }: ExtendedTextProps) {
  const uid = useId().replace(/:/g, "");
  const interactive = typeof onClick === "function";
  const base: CSSProperties = {
    margin: 0,
    padding: 0,
    fontSize: 14,
    lineHeight: 1.2,
    color: HARMONY_TEXT_PRIMARY,
    background: "transparent",
    border: "none",
    overflowWrap: "anywhere",
    ...(interactive ? { cursor: "pointer" as const } : {}),
  };

  const s = styleProps as Record<string, unknown>;
  const common = mergeCommonStyles(s);
  const ts = textSchema(s);
  const text = content == null ? "" : typeof content === "object" ? JSON.stringify(content) : String(content);

  if (s.textOverflow === "marquee") {
    const kf = `genui-marquee-${uid}`;
    return (
      <>
        <style>{`@keyframes ${kf}{0%{transform:translateX(0)}100%{transform:translateX(-50%)}}`}</style>
        <div
          {...domProps(s)}
          onClick={onClick}
          role={interactive ? "button" : undefined}
          tabIndex={interactive ? 0 : undefined}
          style={{
            ...base,
            ...common,
            overflow: "hidden",
            width: common.width ?? "100%",
            maxWidth: "100%",
          }}
        >
          <span
            style={{
              display: "inline-block",
              whiteSpace: "nowrap",
              animation: `${kf} 14s linear infinite`,
              ...ts,
            }}
          >
            {text}
            {"\u00a0\u00a0"}
            {text}
          </span>
        </div>
      </>
    );
  }

  return (
    <p
      {...domProps(s)}
      style={{ ...base, ...common, ...ts }}
      onClick={onClick}
      role={interactive ? "button" : undefined}
      tabIndex={interactive ? 0 : undefined}
    >
      {text}
    </p>
  );
}
