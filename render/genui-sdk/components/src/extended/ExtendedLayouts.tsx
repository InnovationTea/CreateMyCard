import { Children, cloneElement, isValidElement, type CSSProperties, type ReactNode } from "react";
import { mergeCommonStyles } from "./common-styles.js";
import { domProps } from "./dom-props.js";

function visibleChildren(children: ReactNode): ReactNode[] {
  return Children.toArray(children).filter((c) => c != null && (c as unknown) !== false);
}

const flexJustifyMap: Record<string, CSSProperties["justifyContent"]> = {
  start: "flex-start",
  center: "center",
  end: "flex-end",
  spaceBetween: "space-between",
  spaceAround: "space-around",
  spaceEvenly: "space-evenly",
};
const flexAlignMap: Record<string, CSSProperties["alignItems"]> = {
  start: "flex-start",
  end: "flex-end",
  stretch: "stretch",
  baseline: "baseline",
  top: "flex-start",
  center: "center",
  bottom: "flex-end",
};

function rowColumnSchema(styles: Record<string, unknown> | undefined, dir: "row" | "column"): CSSProperties {
  if (!styles) return {};
  const o: CSSProperties = {};
  const jc = styles.justifyContent;
  if (typeof jc === "string" && jc in flexJustifyMap) o.justifyContent = flexJustifyMap[jc]!;
  const ai = styles.alignItems;
  if (typeof ai === "string" && ai in flexAlignMap) o.alignItems = flexAlignMap[ai]!;
  if (dir === "column" && o.alignItems === undefined) o.alignItems = "stretch";
  return o;
}

function listSchema(styles?: Record<string, unknown>): CSSProperties {
  const o: CSSProperties = {};
  if (styles?.listDirection === "horizontal") o.flexDirection = "row";
  else if (styles?.listDirection === "vertical") o.flexDirection = "column";
  const sb = styles?.scrollBar;
  if (sb === "off") o.overflow = "hidden";
  else if (sb === "auto") o.overflow = "auto";
  else if (sb === "on") o.overflow = "scroll";
  const ns = styles?.nestedScroll;
  if (ns === "scrollForward") {
    o.overflowX = "auto";
    o.overflowY = "hidden";
    if (!o.flexDirection) o.flexDirection = "row";
  } else if (ns === "scrollBackward") {
    o.overflowY = "auto";
    o.overflowX = "hidden";
    if (!o.flexDirection) o.flexDirection = "column";
  }
  return o;
}

function gridSchema(styles?: Record<string, unknown>): CSSProperties {
  if (!styles) return {};
  const o: CSSProperties = {};
  if (typeof styles.columnsTemplate === "string" && styles.columnsTemplate.length > 0) {
    o.gridTemplateColumns = styles.columnsTemplate;
  }
  const rt = styles.rowsTemplate;
  if (typeof rt === "string" && rt.length > 0) o.gridTemplateRows = rt;
  if (typeof styles.columnGap === "number") o.columnGap = styles.columnGap;
  if (typeof styles.rowsGap === "number") o.rowGap = styles.rowsGap;
  return o;
}

function layoutShell(
  direction: "row" | "column",
  space: number | undefined,
  styles: Record<string, unknown> | undefined,
  children: ReactNode,
): ReactNode {
  const items = visibleChildren(children);
  const gap = space ?? 0;
  const common = mergeCommonStyles(styles);
  const base: CSSProperties = {
    margin: 0,
    boxSizing: "border-box",
    display: "flex",
    flexDirection: direction,
    gap,
    minWidth: 0,
    minHeight: 0,
    alignItems: direction === "row" ? "center" : "stretch",
    ...common,
    ...rowColumnSchema(styles, direction),
  };

  if (items.length === 0) {
    return <div {...domProps(styles ?? {})} style={base} />;
  }
  return (
    <div {...domProps(styles ?? {})} style={base}>
      {items}
    </div>
  );
}

export interface ExtendedRowProps {
  space?: number;
  /** Same visual effect as {@link space}; if both are set, this wins. */
  itemMargin?: number;
  [key: string]: unknown;
}

export function ExtendedRow({ space, itemMargin, children, ...styleProps }: ExtendedRowProps) {
  const gap = itemMargin ?? space;
  return <>{layoutShell("row", gap, styleProps as Record<string, unknown>, children as ReactNode)}</>;
}

export interface ExtendedColumnProps {
  space?: number;
  /** Same visual effect as {@link space}; if both are set, this wins. */
  itemMargin?: number;
  [key: string]: unknown;
}

export function ExtendedColumn({ space, itemMargin, children, ...styleProps }: ExtendedColumnProps) {
  const gap = itemMargin ?? space;
  return <>{layoutShell("column", gap, styleProps as Record<string, unknown>, children as ReactNode)}</>;
}

export interface ExtendedListProps {
  space?: number;
  [key: string]: unknown;
}

/** List: direction + scroll from flat style props; flex gap from `space`. */
export function ExtendedList({ space, itemMargin, children, ...styleProps }: ExtendedListProps) {
  const s = styleProps as Record<string, unknown>;
  const items = visibleChildren(children as ReactNode);
  const common = mergeCommonStyles(s);
  const le = listSchema(s);
  const fd = le.flexDirection ?? "column";
  const gap = typeof itemMargin === "number" ? itemMargin : space ?? 0;
  const base: CSSProperties = {
    margin: 0,
    boxSizing: "border-box",
    display: "flex",
    flexDirection: fd,
    gap,
    minWidth: 0,
    alignItems: "stretch",
    ...common,
    ...le,
  };
  return <div {...domProps(s)} style={base}>{items}</div>;
}

export interface ExtendedStackProps {
  [key: string]: unknown;
}

/** True overlay: wrappers cover the content box, so percentage children resolve against it. */
export function ExtendedStack({ children, ...styleProps }: ExtendedStackProps) {
  const s = styleProps as Record<string, unknown>;
  const items = visibleChildren(children as ReactNode);
  const common = mergeCommonStyles(s);
  const base: CSSProperties = {
    position: "relative",
    minWidth: 0,
    minHeight: 0,
    ...common,
  };
  const align = String(s.alignContent ?? "center");
  const justifyContent = align.includes("Start") || align === "start" ? "flex-start" : align.includes("End") || align === "end" ? "flex-end" : "center";
  const alignItems = align.startsWith("top") ? "flex-start" : align.startsWith("bottom") ? "flex-end" : "center";
  return <div {...domProps(s)} style={base}>{items.map((child, i) => (
    <div key={isValidElement(child) ? child.key ?? i : i} style={{ position: "absolute", inset: 0, display: "flex", justifyContent, alignItems, pointerEvents: "none" }}>
      {isValidElement(child) ? cloneElement(child as React.ReactElement<Record<string, unknown>>, { __stackChild: true }) : child}
    </div>
  ))}</div>;
}

export interface ExtendedGridProps {
  space?: number;
  [key: string]: unknown;
}

export function ExtendedGrid({ space, children, ...styleProps }: ExtendedGridProps) {
  const s = styleProps as Record<string, unknown>;
  const items = visibleChildren(children as ReactNode);
  const n = Math.max(1, items.length);
  const cols = Math.min(3, n);
  const common = mergeCommonStyles(s);
  const gs = gridSchema(s);
  const gSpace = space ?? 12;
  const cGap = typeof gs.columnGap === "number" ? gs.columnGap : gSpace;
  const rGap = typeof gs.rowGap === "number" ? gs.rowGap : gSpace;
  const base: CSSProperties = {
    ...common,
    ...gs,
    display: "grid",
    gridTemplateColumns: gs.gridTemplateColumns ?? `repeat(${cols}, minmax(0, 1fr))`,
    gridTemplateRows: gs.gridTemplateRows,
    columnGap: cGap,
    rowGap: rGap,
  };
  return <div style={base}>{items}</div>;
}

export interface ExtendedGridRowProps {
  [key: string]: unknown;
}

export function ExtendedGridRow({ children, ...styleProps }: ExtendedGridRowProps) {
  const s = styleProps as Record<string, unknown>;
  const common = mergeCommonStyles(s);
  const base: CSSProperties = {
    display: "flex",
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 12,
    gridColumn: "1 / -1",
    width: "100%",
    minWidth: 0,
    ...common,
  };
  return <div style={base}>{children as ReactNode}</div>;
}
