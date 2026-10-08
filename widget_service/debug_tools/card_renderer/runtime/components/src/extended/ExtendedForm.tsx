"use client";

import { useEffect, useId, useState } from "react";
import { domProps } from "./dom-props.js";
import type { CSSProperties } from "react";
import { applyFontScale, mergeCommonStyles, normalizeSchemaColor } from "./common-styles.js";
import {
  HARMONY_BORDER,
  HARMONY_PRIMARY,
  HARMONY_TEXT_PRIMARY,
  HARMONY_TEXT_TERTIARY,
  HARMONY_UNDERLINE_DISABLE,
} from "./harmony-defaults.js";

export interface ExtendedTextInputProps {
  text?: string;
  placeholder?: string;
  enabled?: boolean;
  maxLength?: number;
  type?: "normal" | "email" | "password" | "number";
  /** HTML `name` for {@link FormData} (e.g. set by the renderer as `surfaceId__nodeId`). */
  name?: string;
  /** HTML `form` — id of the associated `<form>`. */
  form?: string;
  /**
   * When `text` is a `{"path":"…"}` binding, the renderer sets this to write typed input into the data model.
   */
  onDataModelTextChange?: (value: string) => void;
  [key: string]: unknown;
}

const inputBase: CSSProperties = {
  padding: 12,
  borderRadius: 8,
  border: `1px solid ${HARMONY_BORDER}`,
  fontSize: 14,
  color: HARMONY_TEXT_PRIMARY,
  background: "#fff",
  boxSizing: "border-box",
};

function tinSchema(
  styles: Record<string, unknown> | undefined,
  opts: { enabled: boolean },
): CSSProperties {
  if (!styles) return {};
  const o: CSSProperties = {};
  let fs = typeof styles.fontSize === "number" ? styles.fontSize : undefined;
  fs = applyFontScale(fs, styles);
  if (typeof fs === "number") o.fontSize = fs;

  const fw = styles.fontWeight;
  if (typeof fw === "number") o.fontWeight = fw;
  const fco = normalizeSchemaColor(typeof styles.fontColor === "string" ? styles.fontColor : undefined);
  if (fco) o.color = fco;
  const ta = styles.textAlign;
  if (ta === "start" || ta === "center" || ta === "end" || ta === "justify") {
    o.textAlign = ta;
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

  const ml = styles.maxLines;
  if (typeof ml === "number" && ml > 0) {
    o.display = "-webkit-box";
    o.WebkitBoxOrient = "vertical";
    o.WebkitLineClamp = ml;
    o.overflow = "hidden";
  }

  const mfs = styles.maxFontSize;
  if (typeof o.fontSize === "number" && typeof mfs === "number" && o.fontSize > mfs) {
    o.fontSize = mfs;
  }

  if (typeof styles.caretColor === "string") o.caretColor = styles.caretColor;

  const uc = styles.underlineColor;
  const ucObj =
    uc && typeof uc === "object" && !Array.isArray(uc) ? (uc as Record<string, unknown>) : null;

  if (styles.showUnderline === true) {
    o.border = "none";
    o.borderRadius = 0;
    const line =
      !opts.enabled && ucObj && typeof ucObj.disable === "string"
        ? normalizeSchemaColor(ucObj.disable) ?? HARMONY_UNDERLINE_DISABLE
        : ucObj && typeof ucObj.normal === "string"
          ? normalizeSchemaColor(ucObj.normal) ?? HARMONY_BORDER
          : HARMONY_BORDER;
    o.borderBottom = `2px solid ${line}`;
  }

  return o;
}

export function ExtendedTextInput({
  text = "",
  placeholder = "",
  enabled = true,
  maxLength,
  type = "normal",
  name: nameAttr,
  form: formAttr,
  onDataModelTextChange,
  ...styleProps
}: ExtendedTextInputProps) {
  const s = styleProps as Record<string, unknown>;
  const uid = useId().replace(/:/g, "");
  const [val, setVal] = useState(text as string);
  const [focused, setFocused] = useState(false);

  useEffect(() => {
    setVal(text as string);
  }, [text]);

  const htmlType = type === "normal" ? "text" : type === "number" ? "number" : type;
  const common = mergeCommonStyles(s);
  const tin = tinSchema(s, { enabled: enabled as boolean });
  const ph = s.placeholderColor;
  const selBg = s.selectedBackgroundColor;
  const cls = `genui-ti-${uid}`;

  const cb = s.cancelButton;
  const cbObj =
    cb && typeof cb === "object" && !Array.isArray(cb) ? (cb as Record<string, unknown>) : null;
  const cbStyle = cbObj?.style;
  const clearMode = typeof cbStyle === "string" ? cbStyle : "input";
  const showClear =
    enabled &&
    (val as string).length > 0 &&
    cbObj &&
    clearMode !== "invisible" &&
    (clearMode === "constant" || (clearMode === "input" && focused));

  const ucObj =
    s.underlineColor && typeof s.underlineColor === "object"
      ? (s.underlineColor as Record<string, unknown>)
      : null;
  const typingLine =
    focused && ucObj && typeof ucObj.typeing === "string"
      ? normalizeSchemaColor(ucObj.typeing)
      : undefined;
  const tinWithFocus =
    typingLine && s.showUnderline
      ? { ...tin, borderBottom: `2px solid ${typingLine}` }
      : tin;

  const clearColor =
    typeof cbObj?.fontColor === "string" && cbObj.fontColor.length > 0
      ? cbObj.fontColor
      : HARMONY_TEXT_TERTIARY;
  const clearFs =
    typeof cbObj?.fontSize === "number" ? cbObj.fontSize : 18;

  return (
    <>
      {typeof ph === "string" && ph.length > 0 && (
        <style>{`.${cls}::placeholder{color:${ph};opacity:1}`}</style>
      )}
      {typeof selBg === "string" && selBg.length > 0 && (
        <style>{`.${cls}::selection{background:${selBg}}`}</style>
      )}
      <div
        style={{
          display: "flex",
          alignItems: "center",
          gap: 6,
          width: "100%",
          minWidth: 0,
        }}
      >
        <input
          className={cls}
          type={htmlType}
          name={nameAttr}
          form={formAttr}
          value={val as string}
          onChange={(e) => {
            const v = e.target.value;
            setVal(v);
            onDataModelTextChange?.(v);
          }}
          onFocus={() => setFocused(true)}
          onBlur={() => setFocused(false)}
          placeholder={placeholder}
          disabled={!enabled}
          maxLength={maxLength}
          style={{
            ...inputBase,
            flex: 1,
            minWidth: 0,
            maxWidth: "100%",
            ...common,
            ...tinWithFocus,
          }}
        />
        {showClear && (
          <button
            type="button"
            aria-label="Clear"
            onClick={() => {
              setVal("");
              onDataModelTextChange?.("");
            }}
            style={{
              flexShrink: 0,
              border: "none",
              background: "transparent",
              cursor: "pointer",
              color: clearColor,
              fontSize: clearFs,
              lineHeight: 1,
              padding: "2px 4px",
            }}
          >
            ×
          </button>
        )}
      </div>
    </>
  );
}

export interface ExtendedToggleProps {
  isOn?: boolean;
  enabled?: boolean;
  /** Text label shown beside the switch. */
  label?: string;
  [key: string]: unknown;
}

function togglePal(s?: Record<string, unknown>) {
  return {
    selected: typeof s?.selectedColor === "string" ? s.selectedColor : HARMONY_PRIMARY,
    unselected: typeof s?.unselectedColor === "string" ? s.unselectedColor : "#cbd5e1",
    thumb: typeof s?.switchPointColor === "string" ? s.switchPointColor : "#ffffff",
  };
}

export function ExtendedToggle({
  isOn = false,
  enabled = true,
  label,
  ...styleProps
}: ExtendedToggleProps) {
  const [on, setOn] = useState(isOn as boolean);
  useEffect(() => {
    setOn(isOn as boolean);
  }, [isOn]);

  const s = styleProps as Record<string, unknown>;
  const common = mergeCommonStyles(s);
  const pal = togglePal(s);
  const labelText = typeof label === "string" ? label : "";
  const showLabel = labelText.length > 0;

  const thumbStyle: CSSProperties = {
    position: "absolute",
    top: 2,
    left: on ? 22 : 2,
    width: 20,
    height: 20,
    borderRadius: "50%",
    background: pal.thumb,
    boxShadow: "0 1px 2px rgba(0,0,0,0.2)",
    transition: "left 0.2s ease",
    pointerEvents: "none",
  };

  const buttonStyle: CSSProperties = {
    position: "relative",
    width: 44,
    height: 24,
    borderRadius: 12,
    border: "none",
    padding: 0,
    cursor: enabled ? "pointer" : "not-allowed",
    opacity: enabled ? 1 : 0.5,
    background: on ? pal.selected : pal.unselected,
    transition: "background 0.2s ease",
    flexShrink: 0,
    ...(showLabel ? {} : common),
  };

  const switchButton = (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      disabled={!enabled}
      onClick={() => enabled && setOn(!on)}
      style={buttonStyle}
    >
      <span style={thumbStyle} />
    </button>
  );

  if (!showLabel) {
    return switchButton;
  }

  return (
    <label
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 8,
        fontSize: 14,
        color: HARMONY_TEXT_PRIMARY,
        cursor: enabled ? "pointer" : "not-allowed",
        ...common,
      }}
    >
      {switchButton}
      <span style={{ userSelect: "none" }}>{labelText}</span>
    </label>
  );
}

export interface ExtendedRadioProps {
  value?: string;
  checked?: boolean;
  group?: string;
  /** HTML `name` for the radio group (e.g. `surfaceId__g__${group}` from the renderer). Falls back to `group`. */
  name?: string;
  form?: string;
  indicationType?: "tick" | "dot";
  [key: string]: unknown;
}

export function ExtendedRadio({
  value = "",
  checked = false,
  group = "radio",
  name: nameAttr,
  form: formAttr,
  indicationType = "dot",
  ...styleProps
}: ExtendedRadioProps) {
  const s = styleProps as Record<string, unknown>;
  const htmlRadioName = nameAttr != null && String(nameAttr).length > 0 ? String(nameAttr) : group;
  const rid = useId().replace(/:/g, "");
  const common = mergeCommonStyles(s);
  const acc =
    typeof s.indicatorColor === "string" && s.indicatorColor.length > 0
      ? s.indicatorColor
      : HARMONY_PRIMARY;
  const checkedBg = normalizeSchemaColor(
    typeof s.checkedBackgroundColor === "string" ? s.checkedBackgroundColor : undefined,
  );
  const uncheckedBorder = normalizeSchemaColor(
    typeof s.uncheckedBackgroundColor === "string"
      ? s.uncheckedBackgroundColor
      : undefined,
  );
  const cls = `genui-radio-${rid}`;
  const ub = uncheckedBorder ?? "transparent";
  const cb = checkedBg ?? "transparent";

  return (
    <>
      <style>{`
        .${cls} { border: 2px solid ${ub}; background: transparent; }
        .${cls}:has(input:checked) { background: ${cb}; border-color: ${cb === "transparent" ? ub : "transparent"}; }
      `}</style>
      <label
        className={cls}
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: 8,
          fontSize: 14,
          color: HARMONY_TEXT_PRIMARY,
          cursor: "pointer",
          padding: "4px 8px",
          borderRadius: 8,
          ...common,
        }}
      >
        <input
          key={`${group}-${value}-${checked}`}
          type="radio"
          name={htmlRadioName}
          form={formAttr}
          value={value}
          defaultChecked={checked}
          style={{
            accentColor: acc,
            borderRadius: indicationType === "dot" ? "50%" : 4,
            width: 18,
            height: 18,
          }}
        />
        {value}
      </label>
    </>
  );
}

export interface ExtendedCheckboxProps {
  /** Logical group / id (e.g. for `name` fallback); never rendered as visible text. */
  group?: string;
  select?: boolean;
  /** Visible text beside the checkbox (optional). */
  label?: string;
  /** HTML `name` (e.g. from renderer). Falls back to `group`. */
  name?: string;
  form?: string;
  [key: string]: unknown;
}

function markSize(s?: Record<string, unknown>): { w: number; h: number } {
  const m = s?.mark;
  if (m && typeof m === "object" && !Array.isArray(m)) {
    const sz = (m as { size?: unknown }).size;
    if (typeof sz === "number") return { w: sz, h: sz };
  }
  return { w: 18, h: 18 };
}

export function ExtendedCheckbox({
  group = "cb",
  select = false,
  label,
  name: nameAttr,
  form: formAttr,
  ...styleProps
}: ExtendedCheckboxProps) {
  const [on, setOn] = useState(select as boolean);
  useEffect(() => {
    setOn(select as boolean);
  }, [select]);

  const s = styleProps as Record<string, unknown>;
  const htmlCbName = nameAttr != null && String(nameAttr).length > 0 ? String(nameAttr) : group;
  const common = mergeCommonStyles(s);
  const sel = normalizeSchemaColor(typeof s.selectedColor === "string" ? s.selectedColor : undefined) ?? HARMONY_PRIMARY;
  const unselected = s.unSelectedColor ?? s.unselectedColor;
  const unsel = normalizeSchemaColor(typeof unselected === "string" ? unselected : undefined) ?? "rgba(148, 163, 184, 0.9)";
  const shp = s.shape === "circle" ? "50%" : 6;
  const { w, h } = markSize(s);
  const mark = s.mark;
  const mk =
    mark && typeof mark === "object" && !Array.isArray(mark)
      ? (mark as { strokeColor?: string; strokeWidth?: number })
      : {};
  const strokeW = typeof mk.strokeWidth === "number" ? mk.strokeWidth : 2;
  const strokeC =
    typeof mk.strokeColor === "string" && mk.strokeColor.length > 0 ? mk.strokeColor : "#fff";
  const labelText = typeof label === "string" && label.length > 0 ? label : "";

  return (
    <label
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: labelText.length > 0 ? 8 : 0,
        fontSize: 14,
        color: HARMONY_TEXT_PRIMARY,
        cursor: "pointer",
        ...common,
      }}
    >
      <span
        style={{
          position: "relative",
          width: w,
          height: h,
          borderRadius: shp,
          border: `${strokeW}px solid ${on ? sel : unsel}`,
          background: on ? sel : "transparent",
          boxSizing: "border-box",
          flexShrink: 0,
        }}
      >
        <input
          type="checkbox"
          {...domProps(s)}
          value={typeof s.value === "string" ? s.value : undefined}
          name={htmlCbName}
          form={formAttr}
          checked={on}
          onChange={(e) => setOn(e.target.checked)}
          style={{
            position: "absolute",
            inset: 0,
            opacity: 0,
            cursor: "pointer",
            width: "100%",
            height: "100%",
            margin: 0,
          }}
        />
        {on && (
          <svg
            viewBox="0 0 12 12"
            style={{
              position: "absolute",
              left: "50%",
              top: "50%",
              transform: "translate(-50%, -50%)",
              width: Math.max(10, w - 6),
              height: Math.max(10, h - 6),
              pointerEvents: "none",
            }}
            aria-hidden
          >
            <path
              d="M2 6 L5 9 L10 3"
              fill="none"
              stroke={strokeC}
              strokeWidth={strokeW}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
        )}
      </span>
      {labelText.length > 0 ? <span style={{ userSelect: "none" }}>{labelText}</span> : null}
    </label>
  );
}

export interface ExtendedCheckboxGroupProps {
  group?: string;
  selectAll?: boolean;
  name?: string;
  form?: string;
  [key: string]: unknown;
}

export function ExtendedCheckboxGroup({
  group = "group",
  selectAll = false,
  name: nameAttr,
  form: formAttr,
  ...styleProps
}: ExtendedCheckboxGroupProps) {
  const [all, setAll] = useState(selectAll as boolean);
  useEffect(() => {
    setAll(selectAll as boolean);
  }, [selectAll]);

  const s = styleProps as Record<string, unknown>;
  const common = mergeCommonStyles(s);
  const sel =
    typeof s.selectedColor === "string" && s.selectedColor.length > 0
      ? s.selectedColor
      : HARMONY_PRIMARY;
  const unsel =
    typeof s.unselectedColor === "string" && s.unselectedColor.length > 0
      ? s.unselectedColor
      : "rgba(148, 163, 184, 0.9)";
  const shp = s.checkboxShape === "circle" ? "50%" : 6;
  const { w, h } = markSize(s);
  const mark = s.mark;
  const mk =
    mark && typeof mark === "object" && !Array.isArray(mark)
      ? (mark as { strokeColor?: string; strokeWidth?: number })
      : {};
  const strokeW = typeof mk.strokeWidth === "number" ? mk.strokeWidth : 2;
  const strokeC =
    typeof mk.strokeColor === "string" && mk.strokeColor.length > 0 ? mk.strokeColor : "#fff";

  return (
    <fieldset
      form={formAttr}
      style={{
        border: "none",
        margin: 0,
        padding: 0,
        display: "flex",
        flexDirection: "column",
        gap: 8,
        fontSize: 14,
        color: HARMONY_TEXT_PRIMARY,
        ...common,
      }}
    >
      <legend style={{ fontWeight: 600, marginBottom: 4 }}>{group}</legend>
      <label style={{ display: "inline-flex", alignItems: "center", gap: 8, cursor: "pointer" }}>
        <span
          style={{
            position: "relative",
            width: w,
            height: h,
            borderRadius: shp,
            border: `${strokeW}px solid ${all ? sel : unsel}`,
            background: all ? sel : "transparent",
            boxSizing: "border-box",
          }}
        >
          <input
            type="checkbox"
            name={nameAttr != null && String(nameAttr).length > 0 ? String(nameAttr) : undefined}
            form={formAttr}
            checked={all}
            onChange={(e) => setAll(e.target.checked)}
            style={{
              position: "absolute",
              inset: 0,
              opacity: 0,
              cursor: "pointer",
              width: "100%",
              height: "100%",
              margin: 0,
            }}
          />
          {all && (
            <svg
              viewBox="0 0 12 12"
              style={{
                position: "absolute",
                left: "50%",
                top: "50%",
                transform: "translate(-50%, -50%)",
                width: Math.max(10, w - 6),
                height: Math.max(10, h - 6),
                pointerEvents: "none",
              }}
              aria-hidden
            >
              <path
                d="M2 6 L5 9 L10 3"
                fill="none"
                stroke={strokeC}
                strokeWidth={strokeW}
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          )}
        </span>
        全选
      </label>
    </fieldset>
  );
}
