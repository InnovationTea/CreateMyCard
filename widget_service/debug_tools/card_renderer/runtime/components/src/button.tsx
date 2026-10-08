"use client";

import { useState } from "react";
import type { CSSProperties, MouseEventHandler, ReactNode } from "react";
import { isLightSolidBackground } from "./color-utils.js";
import { strokeToCss, type CardStrokeThickness } from "./card.js";
import { isEdgeInsetsRecord, paddingInsetsToCss } from "./extended/common-styles.js";
import { readFormValuesByFormId } from "./form-utils.js";
import { resolveFontFamily } from "./font-utils.js";

export interface ButtonContentItem {
  type: "text" | "icon";
  value: string;
}

/** Payload when the user activates a button tied to a form (for LLM follow-up). */
export interface FormActionDetail {
  /** Usually from {@link ButtonProps.actionText}; falls back to `label`. */
  action: string;
  formValues: Record<string, string>;
}

export interface ButtonProps {
  label?: string;
  content?: ButtonContentItem[];
  actionText?: string;
  /** Id of the &lt;form&gt; whose fields are read when {@link onFormAction} runs. */
  form?: string;
  onClick?: MouseEventHandler<HTMLButtonElement>;
  /**
   * If set with `form`, runs on click after reading `FormData` from that form.
   * `action` is `actionText`, or `label` if `actionText` is empty.
   */
  onFormAction?: (detail: FormActionDetail) => void;
  fill?: string;
  fillHover?: string;
  strokeThickness?: CardStrokeThickness;
  strokeColor?: string;
  padding?:
    | number
    | [number, number]
    | [number, number, number, number]
    | { top?: number; right?: number; bottom?: number; left?: number };
  fontSize?: number;
  fontWeight?: "300" | "400" | "500" | "600" | "700";
  letterSpacing?: number;
  lineHeight?: number;
  fontFamily?: string;
  fontStyle?: "normal" | "italic" | "oblique";
  radius?: number;
  children?: ReactNode;
}

const defaultFill = "#4f46e5";
const defaultFillHover = "#4338ca";

function paddingToCss(
  p: number | [number, number] | [number, number, number, number] | undefined,
): string | undefined {
  if (p === undefined) return undefined;
  if (typeof p === "number") return `${p}px`;
  if (!Array.isArray(p)) return undefined;
  if (p.length === 2) return `${p[0]}px ${p[1]}px`;
  return `${p[0]}px ${p[1]}px ${p[2]}px ${p[3]}px`;
}

function resolveBackground(
  hover: boolean,
  fill: string | undefined,
  fillHover: string | undefined,
  hasStroke: boolean,
): string {
  if (fill !== undefined) {
    if (hover && fillHover !== undefined) return fillHover;
    return fill;
  }
  if (hasStroke) return "transparent";
  if (hover) return fillHover ?? defaultFillHover;
  return defaultFill;
}

function resolveLabelColor(
  fill: string | undefined,
  fillHover: string | undefined,
  hasStroke: boolean,
  hover: boolean,
): string {
  if (hasStroke && fill === undefined) return "#0f172a";
  const bg =
    hover && fillHover !== undefined ? fillHover : fill ?? defaultFill;
  if (isLightSolidBackground(bg)) return "#0f172a";
  return "#ffffff";
}

export function Button({
  label,
  content,
  actionText,
  form,
  onClick,
  onFormAction,
  fill,
  fillHover,
  strokeThickness,
  strokeColor,
  padding,
  fontSize = 14,
  fontWeight = "600",
  letterSpacing,
  lineHeight = 1.25,
  fontFamily,
  fontStyle,
  radius = 8,
  children,
}: ButtonProps) {
  const [hover, setHover] = useState(false);
  const hasStroke =
    strokeThickness !== undefined && strokeColor !== undefined;

  const padCss = paddingToCss(
    typeof padding === "number" || Array.isArray(padding) ? padding : undefined,
  );
  const paddingInset = isEdgeInsetsRecord(padding) ? paddingInsetsToCss(padding) : {};
  const paddingStyle = padCss ?? "10px 18px";

  const style: CSSProperties = {
    margin: 0,
    boxSizing: "border-box",
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    cursor: "pointer",
    font: "inherit",
    WebkitTapHighlightColor: "transparent",
    ...(Object.keys(paddingInset).length > 0 ? paddingInset : { padding: paddingStyle }),
    borderRadius: radius,
    fontSize,
    fontWeight,
    lineHeight,
    fontFamily: resolveFontFamily(fontFamily),
    fontStyle,
    background: resolveBackground(hover, fill, fillHover, hasStroke),
    color: resolveLabelColor(fill, fillHover, hasStroke, hover),
  };

  if (letterSpacing !== undefined) style.letterSpacing = `${letterSpacing}px`;

  if (strokeThickness !== undefined && strokeColor !== undefined) {
    Object.assign(style, strokeToCss(strokeThickness, strokeColor));
  } else {
    style.border = "none";
  }

  const segments =
    content && content.length > 0
      ? content.map((item, i) =>
          item.type === "icon" ? (
            <span key={i} style={{ display: "inline-flex", lineHeight: 1 }} aria-hidden>
              {item.value}
            </span>
          ) : (
            <span key={i}>{item.value}</span>
          ),
        )
      : null;

  const text =
    segments ??
    (label != null && label !== "" ? (
      label
    ) : actionText != null && actionText !== "" ? (
      actionText
    ) : null);

  const handleClick: MouseEventHandler<HTMLButtonElement> = (e) => {
    if (onFormAction && form) {
      const values = readFormValuesByFormId(form);
      if (values) {
        const action =
          actionText != null && actionText !== ""
            ? actionText
            : label != null && label !== ""
              ? label
              : "";
        onFormAction({ action, formValues: values });
      }
    }
    onClick?.(e);
  };

  return (
    <button
      type="button"
      form={form}
      style={style}
      onClick={handleClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
    >
      {text}
      {children}
    </button>
  );
}
