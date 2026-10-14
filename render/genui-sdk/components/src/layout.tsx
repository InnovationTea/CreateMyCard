import { Children, type CSSProperties, type ReactNode } from "react";
import { paddingInsetsToCss } from "./extended/common-styles.js";

/** Layout-only flex container: no background, border, or shadow (use Card for surfaces). */
export interface FlexLayoutProps {
  width?: number | "matchParent";
  height?: number | "matchParent";
  justifyContent?:
    | "flex_start"
    | "center"
    | "flex_end"
    | "space_between"
    | "space_around";
  alignItems?: "flex_start" | "center" | "flex_end" | "stretch";
  /** Gap between children in pixels */
  gap?: number;
  padding?:
    | number
    | [number, number]
    | [number, number, number, number]
    | { top?: number; right?: number; bottom?: number; left?: number };
  children?: ReactNode;
}

export type RowProps = FlexLayoutProps;
export type ColumnProps = FlexLayoutProps;

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

function flexLayoutStyle(
  flexDirection: "row" | "column",
  {
    width,
    height,
    justifyContent = "flex_start",
    alignItems = "stretch",
    gap = 8,
    padding,
  }: FlexLayoutProps,
): CSSProperties {
  const style: CSSProperties = {
    margin: 0,
    boxSizing: "border-box",
    display: "flex",
    flexDirection,
    gap,
    justifyContent: justifyMap[justifyContent] ?? "flex-start",
    alignItems: alignMap[alignItems] ?? "stretch",
    minWidth: 0,
    minHeight: "min-content",
    flex: "none",
    background: "transparent",
    border: "none",
    boxShadow: "none",
    overflow: "visible",
  };

  const padCss = paddingToCss(
    typeof padding === "number" || Array.isArray(padding) ? padding : undefined,
  );
  if (padCss !== undefined) style.padding = padCss;
  else Object.assign(style, paddingInsetsToCss(padding));

  if (width !== undefined) {
    if (width === "matchParent") style.width = "100%";
    else style.width = width;
  }
  if (height !== undefined) {
    if (height === "matchParent") {
      style.minHeight = "100%";
      style.height = "auto";
      style.alignSelf = "stretch";
    } else {
      style.minHeight = height;
      style.height = "auto";
    }
  } else {
    style.height = "auto";
  }

  return style;
}

/** Ignore empty slots so single-child detection matches visible UI. */
function visibleChildren(children: ReactNode): ReactNode[] {
  return Children.toArray(children).filter((c) => {
    if (c == null) return false;
    // `{cond && <X />}` yields `false` when cond is false
    return (c as unknown) !== false;
  });
}

/**
 * Flex items default to `min-width: auto`, which blocks shrinking in a row and causes overflow.
 * Wrapping each child fixes long Text / metrics inside Row / Column.
 */
const flexItemShell: CSSProperties = {
  minWidth: 0,
  minHeight: 0,
  flex: "0 1 auto",
};

export function Row(props: FlexLayoutProps) {
  const { children, ...rest } = props;
  const items = visibleChildren(children);
  const style = flexLayoutStyle("row", rest);

  if (items.length === 0) {
    return <div style={style} />;
  }

  // One visible child: horizontal flex adds no value and can exaggerate odd spacing; use block flow.
  if (items.length === 1) {
    const single = { ...style };
    single.display = "block";
    delete single.gap;
    return <div style={single}>{items[0]}</div>;
  }

  return (
    <div style={style}>
      {items.map((child, index) => (
        <div key={index} style={flexItemShell}>
          {child}
        </div>
      ))}
    </div>
  );
}

export function Column(props: FlexLayoutProps) {
  const { children, ...rest } = props;
  const items = visibleChildren(children);
  const style = flexLayoutStyle("column", rest);

  if (items.length === 0) {
    return <div style={style} />;
  }

  if (items.length === 1) {
    const single = { ...style };
    single.display = "block";
    delete single.gap;
    return <div style={single}>{items[0]}</div>;
  }

  return (
    <div style={style}>
      {items.map((child, index) => (
        <div key={index} style={flexItemShell}>
          {child}
        </div>
      ))}
    </div>
  );
}
