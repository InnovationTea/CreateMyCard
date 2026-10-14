"use client";

import { useState, type MouseEventHandler, type ReactNode } from "react";
import { domProps } from "./dom-props.js";
import type { CSSProperties } from "react";
import { applyFontScale, mergeCommonStyles, normalizeSchemaColor } from "./common-styles.js";
import {
  HARMONY_OVERLAY_5,
  HARMONY_PRIMARY,
  HARMONY_PRIMARY_HOVER,
  HARMONY_TEXT_DISABLED,
} from "./harmony-defaults.js";

export interface ExtendedButtonProps {
  label?: string;
  enabled?: boolean;
  /** Fired after internal hover state; used by renderer for `action.functionCall` (e.g. `openUrl`). */
  onClick?: MouseEventHandler<HTMLButtonElement>;
  [key: string]: unknown;
}

function btnSchema(s?: Record<string, unknown>): CSSProperties {
  if (!s) return {};
  const o: CSSProperties = {};
  const color = normalizeSchemaColor(typeof s.fontColor === "string" ? s.fontColor : undefined);
  if (color) o.color = color;
  if (typeof s.height === "number") o.minHeight = 0;
  let fs = typeof s.fontSize === "number" ? s.fontSize : undefined;
  fs = applyFontScale(fs, s);
  if (typeof fs === "number") o.fontSize = fs;

  const fw = s.fontWeight;
  if (typeof fw === "number" && [100, 300, 400, 500, 700, 900].includes(fw)) {
    o.fontWeight = fw;
  } else if (fw === "300" || fw === "400" || fw === "500" || fw === "600" || fw === "700") {
    o.fontWeight = fw;
  }
  const mfs = s.maxFontSize;
  if (typeof o.fontSize === "number" && typeof mfs === "number" && o.fontSize > mfs) {
    o.fontSize = mfs;
  }
  return o;
}

export function ExtendedButton({
  label,
  enabled = true,
  onClick,
  children,
  ...styleProps
}: ExtendedButtonProps) {
  const [hover, setHover] = useState(false);
  const s = styleProps as Record<string, unknown>;
  const common = mergeCommonStyles(s);
  const btn = btnSchema(s);
  const style: CSSProperties = {
    margin: 0,
    boxSizing: "border-box",
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    cursor: enabled ? "pointer" : "not-allowed",
    font: "inherit",
    minHeight: 40,
    padding: "0 16px",
    borderRadius: 20,
    fontSize: 16,
    fontWeight: 500,
    lineHeight: 1.25,
    border: "none",
    color: enabled ? "#0A59F7" : HARMONY_TEXT_DISABLED,
    backgroundColor: enabled
      ? hover
        ? HARMONY_PRIMARY_HOVER
        : HARMONY_PRIMARY
      : HARMONY_OVERLAY_5,
    ...common,
    ...btn,
  };

  return (
    <button
      {...domProps(s)}
      type="button"
      disabled={!enabled}
      style={style}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      onClick={onClick}
    >
      {label ?? ""}
      {children as ReactNode}
    </button>
  );
}
