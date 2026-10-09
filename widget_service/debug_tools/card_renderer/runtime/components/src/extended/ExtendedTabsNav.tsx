"use client";

import {
  Children,
  isValidElement,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
} from "react";
import { resolveFontFamily } from "../font-utils.js";
import { applyFontScale, mergeCommonStyles, normalizeSchemaColor } from "./common-styles.js";
import {
  HARMONY_BORDER,
  HARMONY_PRIMARY,
  HARMONY_PRIMARY_SELECTED_BG,
  HARMONY_BRAND,
  HARMONY_TEXT_PRIMARY,
  HARMONY_TEXT_TERTIARY,
} from "./harmony-defaults.js";

export interface ExtendedTabContentProps {
  title?: string;
  icon?: string;
  selectedSrc?: string;
  tabType?: "capsule" | "underline";
  styles?: Record<string, unknown>; // kept for internal tabLabelProps usage
  [key: string]: unknown;
}

function readIconSize(styles: Record<string, unknown> | undefined): number | undefined {
  if (!styles) return undefined;
  const raw = styles.IconSIze ?? styles.iconSize;
  return typeof raw === "number" ? raw : undefined;
}

/** Panel body only; tab chrome is rendered by {@link ExtendedTabs}. */
export function ExtendedTabContent({
  title: _title,
  icon: _icon,
  selectedSrc: _selectedSrc,
  tabType: _tabType,
  styles: _styles,
  children,
  ...styleProps
}: ExtendedTabContentProps) {
  // Accept both flat style props (post-render-tree spread) and legacy `styles`.
  const s = (Object.keys(styleProps).length > 0 ? styleProps : _styles) as Record<string, unknown> | undefined;
  const common = mergeCommonStyles(s);
  return (
    <div style={{ boxSizing: "border-box", minWidth: 0, minHeight: 0, flex: "1 1 auto", ...common }}>
      {children as ReactNode}
    </div>
  );
}

function tabLabelProps(child: ReactNode): ExtendedTabContentProps {
  if (!isValidElement(child)) return {};
  const p = child.props as Record<string, unknown>;
  return {
    title: typeof p.title === "string" ? p.title : "",
    icon: typeof p.icon === "string" ? p.icon : undefined,
    selectedSrc: typeof p.selectedSrc === "string" ? p.selectedSrc : undefined,
    tabType: p.tabType === "capsule" || p.tabType === "underline" ? p.tabType : undefined,
    // After render-tree flattens `styles`, style fields are at top level in p.
    // We also fall back to p.styles if present (e.g. direct component usage).
    styles:
      p.styles && typeof p.styles === "object" && !Array.isArray(p.styles)
        ? (p.styles as Record<string, unknown>)
        : (p as Record<string, unknown>),
  };
}

function tabButtonStyle(
  meta: ExtendedTabContentProps,
  selected: boolean,
): CSSProperties {
  const s = meta.styles ?? {};
  const tabType = meta.tabType ?? "underline";
  const fs = applyFontScale(typeof s.fontSize === "number" ? s.fontSize : 14, s);
  const fw = typeof s.fontWeight === "number" ? s.fontWeight : 500;
  const space = typeof s.space === "number" ? s.space : 6;
  const iconSize = readIconSize(s) ?? 16;

  const selColor = normalizeSchemaColor(typeof s.selectColor === "string" ? s.selectColor : undefined) ?? HARMONY_BRAND;
  const unselColor =
    normalizeSchemaColor(typeof s.unselectedColor === "string" ? s.unselectedColor : undefined) ?? HARMONY_TEXT_TERTIARY;
  const bgDef =
    normalizeSchemaColor(typeof s.defaultBackgroundColor === "string" ? s.defaultBackgroundColor : undefined) ??
    "transparent";
  const bgSel =
    normalizeSchemaColor(typeof s.selectedBackgroundColor === "string" ? s.selectedBackgroundColor : undefined) ??
    HARMONY_PRIMARY_SELECTED_BG;
  const bdDef =
    normalizeSchemaColor(typeof s.defaultBorderColor === "string" ? s.defaultBorderColor : undefined) ??
    "transparent";
  const bdSel =
    normalizeSchemaColor(typeof s.selectedBorderColor === "string" ? s.selectedBorderColor : undefined) ??
    HARMONY_PRIMARY;

  const base: CSSProperties = {
    display: "inline-flex",
    alignItems: "center",
    gap: space,
    cursor: "pointer",
    fontSize: fs,
    fontWeight: fw,
    color: selected ? selColor : unselColor,
    background: selected ? bgSel : bgDef,
    border: "1px solid",
    borderColor: selected ? bdSel : bdDef,
    padding: tabType === "capsule" ? "6px 12px" : "8px 4px",
    borderRadius: tabType === "capsule" ? 999 : 0,
    borderLeft: tabType === "underline" ? "none" : undefined,
    borderRight: tabType === "underline" ? "none" : undefined,
    borderTop: tabType === "underline" ? "none" : undefined,
    borderBottom:
      tabType === "underline"
        ? selected
          ? `2px solid ${bdSel}`
          : `2px solid ${normalizeSchemaColor(typeof s.defaultBorderColor === "string" ? s.defaultBorderColor : undefined) ?? "transparent"}`
        : undefined,
    whiteSpace: "nowrap",
    flexShrink: 0,
  };

  if (tabType === "underline") {
    base.borderLeft = "none";
    base.borderRight = "none";
    base.borderTop = "none";
    base.background = selected ? bgSel : "transparent";
  }

  return base;
}

export interface ExtendedTabsProps {
  barPosition?: "start" | "end";
  vertical?: boolean;
  scrollable?: boolean;
  tableIndex?: number;
  [key: string]: unknown;
}

export function ExtendedTabs({
  barPosition = "start",
  vertical = false,
  scrollable = false,
  tableIndex = 0,
  children,
  ...styleProps
}: ExtendedTabsProps) {
  const styles = styleProps as Record<string, unknown>;
  const items = useMemo(
    () => Children.toArray(children as ReactNode).filter((c) => c != null && (c as unknown) !== false),
    [children],
  );
  const count = items.length;

  const clamp = useCallback(
    (i: number) => (count <= 0 ? 0 : Math.max(0, Math.min(i, count - 1))),
    [count],
  );

  const [idx, setIdx] = useState(() => clamp(typeof tableIndex === "number" ? tableIndex : 0));

  useEffect(() => {
    if (typeof tableIndex === "number") setIdx(clamp(tableIndex));
  }, [tableIndex, clamp]);

  const contentRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!scrollable || !contentRef.current) return;
    const el = contentRef.current;
    const w = el.clientWidth;
    if (w <= 0) return;
    el.scrollTo({ left: idx * w, behavior: "smooth" });
  }, [idx, scrollable]);

  const onContentScroll = useCallback(() => {
    if (!scrollable || !contentRef.current) return;
    const el = contentRef.current;
    const w = el.clientWidth;
    if (w <= 0) return;
    const next = Math.round(el.scrollLeft / w);
    setIdx(clamp(next));
  }, [scrollable, clamp]);

  const common = mergeCommonStyles(styles);

  const barFirst = barPosition === "start";
  const rowDir = vertical ? (barFirst ? "row" : "row-reverse") : barFirst ? "column" : "column-reverse";

  const outer: CSSProperties = {
    boxSizing: "border-box",
    display: "flex",
    flexDirection: rowDir,
    minWidth: 0,
    minHeight: 0,
    flex: "1 1 auto",
    gap: vertical ? 12 : 8,
    ...common,
  };

  const bar: CSSProperties = {
    display: "flex",
    flexDirection: vertical ? "column" : "row",
    flexShrink: 0,
    gap: vertical ? 4 : 8,
    alignItems: vertical ? "stretch" : "center",
    overflow: vertical ? "auto" : "auto",
    maxHeight: vertical ? 220 : undefined,
    maxWidth: vertical ? undefined : "100%",
  };

  const panelsWrap: CSSProperties = scrollable
    ? {
        flex: "1 1 auto",
        minWidth: 0,
        minHeight: 0,
        overflowX: "auto",
        overflowY: "hidden",
        scrollSnapType: "x mandatory",
        display: "flex",
        flexDirection: "row",
        WebkitOverflowScrolling: "touch",
      }
    : {
        flex: "1 1 auto",
        minWidth: 0,
        minHeight: 0,
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
      };

  if (count === 0) {
    return <div style={outer} />;
  }

  return (
    <div style={outer}>
      <div style={bar} role="tablist" aria-orientation={vertical ? "vertical" : "horizontal"}>
        {items.map((child, i) => {
          const meta = tabLabelProps(child);
          const selected = i === idx;
          const src = selected && meta.selectedSrc ? meta.selectedSrc : meta.icon;
          return (
            <button
              key={i}
              type="button"
              role="tab"
              aria-selected={selected}
              onClick={() => setIdx(i)}
              style={tabButtonStyle(meta, selected)}
            >
              {src ? (
                <img
                  src={src}
                  alt=""
                  style={{
                    width: readIconSize(meta.styles) ?? 16,
                    height: readIconSize(meta.styles) ?? 16,
                    objectFit: "contain",
                  }}
                />
              ) : null}
              <span>{meta.title ?? `Tab ${i + 1}`}</span>
            </button>
          );
        })}
      </div>
      <div ref={contentRef} style={panelsWrap} onScroll={scrollable ? onContentScroll : undefined}>
        {items.map((child, i) => {
          const panelStyle: CSSProperties = scrollable
            ? {
                flex: "0 0 100%",
                width: "100%",
                minWidth: "100%",
                scrollSnapAlign: "start",
                boxSizing: "border-box",
                overflow: "auto",
              }
            : {
                flex: "1 1 auto",
                display: i === idx ? "flex" : "none",
                flexDirection: "column",
                minHeight: 0,
                minWidth: 0,
                overflow: "auto",
              };
          return (
            <div key={i} role="tabpanel" hidden={!scrollable && i !== idx} style={panelStyle}>
              {child}
            </div>
          );
        })}
      </div>
    </div>
  );
}

type SelectOption = {
  value?: string;
  icon?: string;
  symbolIcon?: Record<string, unknown>;
};

function selectOptionFormValue(opt: SelectOption | undefined, index: number): string {
  if (opt && typeof opt.value === "string" && opt.value.length > 0) {
    return opt.value;
  }
  return `i_${index}`;
}

function fontBlockCss(
  block: Record<string, unknown> | undefined,
  fallbackSize: number,
  fallbackWeight: number,
): CSSProperties {
  if (!block) return { fontSize: fallbackSize, fontWeight: fallbackWeight };
  const size = typeof block.size === "number" ? block.size : fallbackSize;
  const weight = typeof block.weight === "number" ? block.weight : fallbackWeight;
  const family =
    typeof block.family === "string" ? resolveFontFamily(block.family) ?? block.family : undefined;
  const style = block.style === "italic" || block.style === "normal" ? block.style : undefined;
  return {
    fontSize: size,
    fontWeight: weight,
    ...(family ? { fontFamily: family } : {}),
    ...(style ? { fontStyle: style } : {}),
  };
}

export interface ExtendedSelectFieldProps {
  options?: SelectOption[];
  selected?: number;
  value?: string;
  /** HTML `name` for {@link FormData} (e.g. from the renderer). */
  name?: string;
  form?: string;
  [key: string]: unknown;
}

export function ExtendedSelectField({
  options = [],
  selected = 0,
  value,
  name: nameAttr,
  form: formAttr,
  ...styleProps
}: ExtendedSelectFieldProps) {
  const safeIdx = (options as SelectOption[]).length === 0 ? 0 : Math.max(0, Math.min(selected as number, (options as SelectOption[]).length - 1));
  const [idx, setIdx] = useState(safeIdx);

  useEffect(() => {
    setIdx(safeIdx);
  }, [safeIdx]);

  const s = styleProps as Record<string, unknown>;
  const common = mergeCommonStyles(s);
  const fontColor = normalizeSchemaColor(typeof s.fontColor === "string" ? s.fontColor : undefined) ?? HARMONY_TEXT_PRIMARY;
  const optBg =
    normalizeSchemaColor(typeof s.optionBgColor === "string" ? s.optionBgColor : undefined) ?? "#ffffff";
  const optFg =
    normalizeSchemaColor(typeof s.optionFontColor === "string" ? s.optionFontColor : undefined) ?? HARMONY_TEXT_PRIMARY;
  const selBg =
    normalizeSchemaColor(typeof s.selectedOptionBgColor === "string" ? s.selectedOptionBgColor : undefined) ??
    HARMONY_PRIMARY_SELECTED_BG;
  const selFg =
    normalizeSchemaColor(typeof s.selectedOptionFontColor === "string" ? s.selectedOptionFontColor : undefined) ??
    HARMONY_PRIMARY;

  const arrowPos = s.arrowPosition === "end" ? "end" : "start";
  const space = typeof s.space === "number" ? s.space : 8;
  const optW = typeof s.optionWidth === "number" ? s.optionWidth : undefined;
  const optH = typeof s.optionHeight === "number" ? s.optionHeight : undefined;
  const menuBg =
    normalizeSchemaColor(typeof s.menuBackgroundColor === "string" ? s.menuBackgroundColor : undefined) ?? "#ffffff";

  const fontMain = fontBlockCss(
    s.font && typeof s.font === "object" && !Array.isArray(s.font) ? (s.font as Record<string, unknown>) : undefined,
    14,
    400,
  );
  const fontOpt = fontBlockCss(
    s.optionFont && typeof s.optionFont === "object" && !Array.isArray(s.optionFont)
      ? (s.optionFont as Record<string, unknown>)
      : undefined,
    14,
    400,
  );
  const fontSel = fontBlockCss(
    s.selectedOptionFont && typeof s.selectedOptionFont === "object" && !Array.isArray(s.selectedOptionFont)
      ? (s.selectedOptionFont as Record<string, unknown>)
      : undefined,
    14,
    500,
  );

  const wrap: CSSProperties = {
    boxSizing: "border-box",
    display: "flex",
    flexDirection: arrowPos === "start" ? "row" : "row-reverse",
    alignItems: "center",
    gap: space,
    color: fontColor,
    ...fontMain,
    ...common,
  };

  const opts = options as SelectOption[];
  const optValueAt = (i: number) => selectOptionFormValue(opts[i], i);
  const opt = opts[idx];
  const ariaLabel =
    opts.length === 0
      ? "Select"
      : typeof value === "string" && value.length > 0
        ? value
        : typeof opt?.value === "string" && opt.value.length > 0
          ? opt.value
          : `Option ${idx + 1}`;

  const selectStyle: CSSProperties = {
    flex: "1 1 auto",
    minWidth: 0,
    padding: 12,
    borderRadius: 8,
    border: `1px solid ${HARMONY_BORDER}`,
    background: menuBg,
    color: fontColor,
    ...fontMain,
    cursor: "pointer",
  };

  return (
    <div style={wrap}>
      <select
        name={nameAttr}
        form={formAttr}
        aria-label={ariaLabel}
        value={optValueAt(idx)}
        onChange={(e) => {
          const v = e.target.value;
          const ni = opts.findIndex((_, i) => optValueAt(i) === v);
          if (ni >= 0) setIdx(ni);
        }}
        style={selectStyle}
      >
        {opts.map((opt, i) => {
          const label = typeof opt.value === "string" && opt.value.length > 0 ? opt.value : `Option ${i + 1}`;
          const isSel = i === idx;
          return (
            <option
              key={i}
              value={optValueAt(i)}
              style={{
                background: isSel ? selBg : optBg,
                color: isSel ? selFg : optFg,
                ...fontOpt,
                ...(isSel ? fontSel : {}),
                minHeight: optH,
                minWidth: optW,
              }}
            >
              {label}
            </option>
          );
        })}
      </select>
    </div>
  );
}

export interface ExtendedWebProps {
  url?: string;
  [key: string]: unknown;
}

export function ExtendedWeb({ url = "", ...styleProps }: ExtendedWebProps) {
  const common = mergeCommonStyles(styleProps as Record<string, unknown>);
  const frame: CSSProperties = {
    boxSizing: "border-box",
    width: "100%",
    minHeight: 240,
    border: "none",
    borderRadius: 8,
    flex: "1 1 auto",
    ...common,
  };
  if (!url.trim()) {
    return (
      <div
        style={{
          ...frame,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          color: HARMONY_TEXT_TERTIARY,
          fontSize: 13,
          border: `1px dashed ${HARMONY_BORDER}`,
        }}
      >
        No URL
      </div>
    );
  }
  return (
    <iframe
      title="Extended.Web"
      src={url}
      style={frame}
      sandbox="allow-scripts allow-forms allow-popups allow-same-origin"
    />
  );
}

export interface ExtendedNavigationProps {
  currentIndex?: number;
  title?: string;
  [key: string]: unknown;
}

export function ExtendedNavigation({
  currentIndex = 0,
  title = "",
  children,
  ...styleProps
}: ExtendedNavigationProps) {
  const items = useMemo(
    () => Children.toArray(children as ReactNode).filter((c) => c != null && (c as unknown) !== false),
    [children],
  );
  const count = items.length;
  const idx = count === 0 ? 0 : Math.max(0, Math.min(currentIndex as number, count - 1));

  const s = styleProps as Record<string, unknown>;
  const common = mergeCommonStyles(s);
  const headerBg =
    normalizeSchemaColor(typeof s.backgroundColor === "string" ? s.backgroundColor : undefined) ?? "#ffffff";

  const outer: CSSProperties = {
    boxSizing: "border-box",
    display: "flex",
    flexDirection: "column",
    minWidth: 0,
    minHeight: 0,
    flex: "1 1 auto",
    overflow: "hidden",
    ...common,
  };

  const header: CSSProperties = {
    flexShrink: 0,
    padding: "10px 14px",
    fontSize: 16,
    fontWeight: 600,
    color: HARMONY_TEXT_PRIMARY,
    background: headerBg,
    borderBottom: `1px solid ${HARMONY_BORDER}`,
  };

  const body: CSSProperties = {
    flex: "1 1 auto",
    minHeight: 0,
    minWidth: 0,
    overflow: "auto",
  };

  return (
    <div style={outer}>
      {title ? <div style={header}>{title}</div> : null}
      <div style={body}>{count > 0 ? items[idx] : null}</div>
    </div>
  );
}
