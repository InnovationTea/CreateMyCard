import type { CSSProperties } from "react";
import { mergeCommonStyles, normalizeSchemaColor } from "./common-styles.js";
import { domProps } from "./dom-props.js";
import { HARMONY_BORDER, HARMONY_PRIMARY } from "./harmony-defaults.js";
export interface ExtendedProgressProps { value?: number; total?: number; [key: string]: unknown; }

export function ExtendedProgress({ value = 0, total = 100, ...s }: ExtendedProgressProps) {
  const common = mergeCommonStyles(s);
  const valid = typeof value === "number" && Number.isFinite(value) && typeof total === "number" && Number.isFinite(total) && total > 0 && value >= 0 && value <= total;
  if (!valid) return <span role="alert" style={common}>进度值无效</span>;
  const pct = value / total * 100;
  const color = normalizeSchemaColor(typeof s.color === "string" ? s.color : undefined) ?? HARMONY_PRIMARY;
  const trackColor = normalizeSchemaColor(typeof s.backgroundColor === "string" ? s.backgroundColor : undefined) ?? HARMONY_BORDER;
  const stroke = typeof s.strokeWidth === "number" ? s.strokeWidth : 4;
  const metadata = { ...domProps(s), role: "progressbar", "aria-valuenow": value, "aria-valuemin": 0, "aria-valuemax": total };
  if (s.type === "ring" || s.type === "scaleRing") {
    const width = typeof s.width === "number" ? s.width : 48;
    const height = typeof s.height === "number" ? s.height : width;
    const radius = Math.max(0, (Math.min(width, height) - stroke) / 2);
    const circumference = 2 * Math.PI * radius;
    return <div {...metadata} style={{ width, height, flexShrink: 0, ...common, backgroundColor: "transparent" }}>
      <svg viewBox={`0 0 ${width} ${height}`} width="100%" height="100%" aria-hidden="true" style={{ display: "block", overflow: "visible" }}>
        <circle cx={width / 2} cy={height / 2} r={radius} fill="none" stroke={trackColor} strokeWidth={stroke} />
        <circle cx={width / 2} cy={height / 2} r={radius} fill="none" stroke={color} strokeWidth={stroke} strokeLinecap="round"
          strokeDasharray={circumference} strokeDashoffset={circumference * (1 - value / total)} transform={`rotate(-90 ${width / 2} ${height / 2})`} />
      </svg>
    </div>;
  }
  const track: CSSProperties = { width: "100%", height: stroke, borderRadius: 999, flexShrink: 0, ...common, backgroundColor: trackColor, overflow: "hidden" };
  return <div {...metadata} style={track}><div style={{ width: `${pct}%`, height: "100%", backgroundColor: color, borderRadius: "inherit" }} /></div>;
}
