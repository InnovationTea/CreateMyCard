import visualRecipes from "../../../../../widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/runtime/visual-recipes-v1.json";
import { adaptCompactRegions } from "../../../../../render/shared/compact-region-layout";

/** Expansion contracts from the shared Fusion Compact component runtime. */
export type MiniNode = { type: string; props: Record<string, unknown>; children: string[] };
export type CardSize = "2x2" | "2x4";
export type ExpansionDataContext = {
  get: (path: string) => unknown;
  setDerived: (path: string, value: unknown) => void;
};
type RecordValue = Record<string, unknown>;
type RecipePart = { component: string; styles: RecordValue };
type Recipe = {
  parts: Record<string, RecipePart>;
  metrics?: RecordValue;
  sizes?: Record<string, Partial<Recipe>>;
  variants?: Record<string, Partial<Recipe>>;
};

const PLACEMENT_PROPS = ["width", "height", "layoutWeight", "flexShrink", "margin"];

export const VISUAL_RECIPE_VERSION = "visual-recipes-v1";
export const HIGH_LEVEL_COMPONENT_TYPES = [
  "DoubleLineTitle", "Badge", "EmphasisText", "SecondaryBody", "H_BarChart",
  "NumericRatioStack",
  "PillButton", "CircleButton", "EmphasizedData", "InfoBlock", "ProgressCircle", "ProgressLine2",
  "TableText", "TextBlock", "CardButton", "ProgressCircleSingle", "EventCard",
  "DataDisplay", "TopTextBottomValue", "SummaryList",
] as const;

export const FUSION_PALETTES: Record<string, readonly string[]> = {
  "fusion-ball-battery-teal": ["#FF1F9985", "#FF24B3B3", "#FF5AB38E"],
  "fusion-ball-schedule-cool": ["#FF1F3399", "#FF2385B3", "#FF24B3B3"],
  "fusion-ball-schedule-warm": ["#FF731D28", "#FFFF5533", "#FFE68A2E"],
  "fusion-ball-sleep-violet": ["#FF493D99", "#FF5536B3", "#FF7D6B99"],
  "fusion-ball-sport-orange": ["#FFF24131", "#FFFF8833", "#FFE68073"],
};

const record = (value: unknown): value is RecordValue =>
  typeof value === "object" && value !== null && !Array.isArray(value);
const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T;

function deepMerge(base: RecordValue, override: RecordValue): RecordValue {
  const merged = clone(base);
  for (const [key, value] of Object.entries(override)) {
    const existing = merged[key];
    merged[key] = record(existing) && record(value) ? deepMerge(existing, value) : clone(value);
  }
  return merged;
}

function recipe(name: string, size?: CardSize, variant?: string): Recipe {
  if (visualRecipes.version !== VISUAL_RECIPE_VERSION) {
    throw new Error(`视觉 Recipe 必须使用 ${VISUAL_RECIPE_VERSION}。`);
  }
  const registered = (visualRecipes.components as unknown as Record<string, Recipe>)[name];
  if (!registered) throw new Error(`未注册高阶组件视觉 Recipe：${name}。`);
  let resolved = clone(registered);
  if (size && registered.sizes?.[size]) {
    resolved = deepMerge(
      resolved as unknown as RecordValue,
      registered.sizes[size] as RecordValue,
    ) as unknown as Recipe;
  }
  if (variant) {
    const variantRecipe = registered.variants?.[variant];
    if (!variantRecipe) throw new Error(`未注册视觉变体：${name}.${variant}。`);
    resolved = deepMerge(
      resolved as unknown as RecordValue,
      variantRecipe as RecordValue,
    ) as unknown as Recipe;
  }
  return resolved;
}

export function visualRecipePart(
  name: string,
  part: string,
  size?: CardSize,
  variant?: string,
): RecipePart {
  const result = recipe(name, size, variant).parts[part];
  if (!result || typeof result.component !== "string" || !record(result.styles)) {
    throw new Error(`未注册视觉部件：${name}.${part}。`);
  }
  return clone(result);
}

function row(
  id: string,
  name: string,
  part: string,
  size: CardSize,
  props: RecordValue = {},
  children: string[] = [],
  variant?: string,
): [string, MiniNode] {
  const visual = visualRecipePart(name, part, size, variant);
  return [id, { type: visual.component, props: { ...visual.styles, ...clone(props) }, children }];
}

function requireProps(
  id: string,
  type: string,
  props: RecordValue,
  required: string[],
  allowed: string[],
) {
  const missing = required.filter(name => !(name in props));
  if (missing.length) throw new Error(`${id}: ${type} 缺少 ${missing.join("、")}。`);
  const unknown = Object.keys(props).filter(name => !allowed.includes(name) && !PLACEMENT_PROPS.includes(name));
  if (unknown.length) throw new Error(`${id}: ${type} 不接受 ${unknown.join("、")}。`);
}

function requireNoChildren(id: string, type: string, children: string[]) {
  if (children.length) throw new Error(`${id}: ${type} 不接受 children。`);
}

function isDisplayValue(value: unknown) {
  return (typeof value === "string" && value.trim().length > 0)
    || (typeof value === "number" && Number.isFinite(value))
    || (record(value) && Object.keys(value).length === 1 && typeof value.path === "string");
}

function requireDisplay(id: string, type: string, props: RecordValue, name: string) {
  if (!isDisplayValue(props[name])) throw new Error(`${id}: ${type}.${name} 必须是可显示文本。`);
}

function requireColor(id: string, type: string, props: RecordValue, name: string) {
  if (typeof props[name] !== "string" || !/^#[\da-f]{8}$/i.test(props[name] as string)) {
    throw new Error(`${id}: ${type}.${name} 必须使用 #AARRGGBB。`);
  }
}

function requireAction(id: string, type: string, value: unknown) {
  if (!Array.isArray(value) || value.length !== 1 || !record(value[0])) {
    throw new Error(`${id}: ${type}.onClick 必须恰好包含一个动作。`);
  }
  const action = value[0];
  const valid = Object.keys(action).sort().join(",") === "args,call"
    && typeof action.call === "string"
    && action.call.trim().length > 0
    && record(action.args);
  if (!valid) throw new Error(`${id}: ${type}.onClick 动作只接受非空 call 和对象 args。`);
}

function requireOptionalIcon(id: string, type: string, props: RecordValue) {
  if (props.icon !== undefined && (typeof props.icon !== "string" || !props.icon.trim())) {
    throw new Error(`${id}: ${type}.icon 必须是非空字符串。`);
  }
  if (props.fillColor !== undefined && props.icon === undefined) {
    throw new Error(`${id}: ${type}.fillColor 需要 icon。`);
  }
  if (props.fillColor !== undefined) requireColor(id, type, props, "fillColor");
}

function labelValueItems(
  id: string,
  type: string,
  value: unknown,
  minimum: number,
  maximum: number,
) {
  if (!Array.isArray(value) || value.length < minimum || value.length > maximum) {
    throw new Error(`${id}: ${type}.items 需要 ${minimum}–${maximum} 项。`);
  }
  value.forEach((item, index) => {
    const valid = record(item)
      && Object.keys(item).sort().join(",") === "label,value"
      && typeof item.label === "string"
      && item.label.trim().length > 0
      && isDisplayValue(item.value);
    if (!valid) throw new Error(`${id}: ${type}.items[${index}] 只接受有效的 label/value。`);
  });
  return value as Array<{ label: string; value: unknown }>;
}

function labelValueUnitItems(id: string, type: string, value: unknown) {
  if (!Array.isArray(value) || value.length !== 3) {
    throw new Error(`${id}: ${type}.items 需要 3–3 项。`);
  }
  value.forEach((item, index) => {
    const valid = record(item)
      && Object.keys(item).sort().join(",") === "label,unit,value"
      && typeof item.label === "string"
      && item.label.trim().length > 0
      && typeof item.unit === "string"
      && item.unit.trim().length > 0
      && isDisplayValue(item.value);
    if (!valid) {
      throw new Error(`${id}: ${type}.items[${index}] 只接受有效的 label/value/unit。`);
    }
  });
  return value as Array<{ label: string; value: unknown; unit: string }>;
}

function colorWithAlpha(color: string, opacity: number) {
  const alpha = Math.round(Number.parseInt(color.slice(1, 3), 16) * opacity);
  return `#${alpha.toString(16).padStart(2, "0").toUpperCase()}${color.slice(3)}`;
}

function normalizedProgressValue(
  id: string,
  type: string,
  prop: string,
  value: unknown,
  total: number,
): number {
  if (typeof value === "boolean") {
    throw new Error(`${id}: ${type}.${prop} 必须是有限数值或完整数值百分比。`);
  }
  if (typeof value === "number" && Number.isFinite(value)) {
    if (value < 0 || value > total) {
      const range = total === 100 ? "0–100" : `0–${total}`;
      throw new Error(`${id}: ${type}.${prop} 必须在 ${range} 之间。`);
    }
    return value;
  }
  if (typeof value === "string") {
    const match = value.match(/^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*([%％]?)\s*$/);
    if (match) {
      let numeric = Number(match[1]);
      if (match[2]) numeric = Math.min(100, Math.max(0, numeric)) * total / 100;
      if (Number.isFinite(numeric) && numeric >= 0 && numeric <= total) return numeric;
    }
  }
  throw new Error(`${id}: ${type}.${prop} 必须是 0–100 有限数值或完整数值百分比。`);
}

function normalizedProgressBinding(
  id: string,
  type: string,
  prop: string,
  value: unknown,
  total: number,
  data?: ExpansionDataContext,
): unknown {
  if (record(value) && Object.keys(value).length === 1 && typeof value.path === "string") {
    const initial = data?.get(value.path);
    if (typeof initial !== "string" && typeof initial !== "number") return clone(value);
    const numeric = normalizedProgressValue(id, type, prop, initial, total);
    if (typeof initial !== "string") return clone(value);
    const derivedPath = `/__display${value.path}/progressValue`;
    data?.setDerived(derivedPath, numeric);
    return { path: derivedPath };
  }
  return normalizedProgressValue(id, type, prop, value, total);
}

function progressCircleValues(
  id: string,
  value: unknown,
  data?: ExpansionDataContext,
): [unknown, unknown] {
  if (record(value) && Object.keys(value).length === 1 && typeof value.path === "string") {
    const initial = data?.get(value.path);
    const progress = normalizedProgressBinding(
      id,
      "ProgressCircle",
      "externalText",
      value,
      100,
      data,
    );
    return typeof initial === "string"
      ? [progress, clone(value)]
      : [progress, `{{ \${${value.path}} + '%' }}`];
  }
  const numeric = normalizedProgressValue(id, "ProgressCircle", "externalText", value, 100);
  return typeof value === "string" ? [numeric, value.trim()] : [numeric, `${numeric}%`];
}

function requireProgressCircleAccessibility(id: string, value: unknown) {
  const allowed = ["description", "label"];
  const valid = record(value)
    && Object.keys(value).every(name => allowed.includes(name))
    && typeof value.label === "string"
    && value.label.trim().length > 0
    && (value.description === undefined
      || (typeof value.description === "string" && value.description.trim().length > 0));
  if (!valid) {
    throw new Error(`${id}: ProgressCircle.accessibility 必须包含非空 label。`);
  }
}

function expandHighLevel(
  id: string,
  node: MiniNode,
  size: CardSize,
  data?: ExpansionDataContext,
): Array<[string, MiniNode]> | null {
  const p = node.props;
  const type = node.type;
  if (!(HIGH_LEVEL_COMPONENT_TYPES as readonly string[]).includes(type)) return null;
  requireNoChildren(id, type, node.children);

  if (type === "DoubleLineTitle") {
    const allowed = ["title", "secondaryInfo", "fontColor"];
    requireProps(id, type, p, allowed, allowed);
    requireDisplay(id, type, p, "title");
    requireDisplay(id, type, p, "secondaryInfo");
    requireColor(id, type, p, "fontColor");
    const titleId = `${id}_title`;
    const secondaryId = `${id}_secondary`;
    return [
      row(id, type, "root", size, {}, [titleId, secondaryId]),
      row(titleId, type, "title", size, { content: p.title, fontColor: p.fontColor }),
      row(secondaryId, type, "secondary", size, {
        content: p.secondaryInfo,
        fontColor: colorWithAlpha(p.fontColor as string, 0.6),
      }),
    ];
  }

  if (type === "Badge") {
    const allowed = ["value", "fontColor", "backgroundColor"];
    requireProps(id, type, p, allowed, allowed);
    requireDisplay(id, type, p, "value");
    requireColor(id, type, p, "fontColor");
    requireColor(id, type, p, "backgroundColor");
    return [row(id, type, "root", size, {
      content: p.value,
      fontColor: p.fontColor,
      backgroundColor: p.backgroundColor,
    })];
  }

  if (type === "EmphasisText") {
    const allowed = ["mainText", "secondaryText", "fontColor"];
    requireProps(id, type, p, ["mainText", "fontColor"], allowed);
    requireDisplay(id, type, p, "mainText");
    if (p.secondaryText !== undefined) requireDisplay(id, type, p, "secondaryText");
    requireColor(id, type, p, "fontColor");
    const mainId = `${id}_main`;
    const children = [mainId];
    const rows: Array<[string, MiniNode]> = [
      row(mainId, type, "main", size, { content: p.mainText, fontColor: p.fontColor }),
    ];
    if (p.secondaryText !== undefined) {
      const secondaryId = `${id}_secondary`;
      children.push(secondaryId);
      rows.push(row(secondaryId, type, "secondary", size, {
        content: p.secondaryText,
        fontColor: colorWithAlpha(p.fontColor as string, 0.6),
      }));
    }
    return [row(id, type, "root", size, {}, children), ...rows];
  }

  if (type === "SecondaryBody") {
    const allowed = ["items", "role", "columns", "separator", "fontColor"];
    requireProps(id, type, p, ["items", "fontColor"], allowed);
    requireColor(id, type, p, "fontColor");
    if (!Array.isArray(p.items) || p.items.length < 1 || p.items.length > 4) {
      throw new Error(`${id}: SecondaryBody.items 需要 1–4 项。`);
    }
    const role = p.role ?? (p.items.length > 1 ? "supporting" : undefined);
    if (role === undefined) throw new Error(`${id}: 单项 SecondaryBody 必须声明 role。`);
    if (!["body", "metadata", "supporting"].includes(String(role))) {
      throw new Error(`${id}: SecondaryBody.role 只接受 body、metadata 或 supporting。`);
    }
    if (["body", "metadata"].includes(String(role)) && p.items.length !== 1) {
      throw new Error(`${id}: SecondaryBody role ${String(role)} 只能包含一项。`);
    }
    const items = p.items.map((item, index) => {
      if (!record(item) || !("value" in item) || !isDisplayValue(item.value)
        || Object.keys(item).some(key => !["label", "value", "maxLines"].includes(key))
        || (item.label !== undefined && (typeof item.label !== "string" || !item.label.trim()))) {
        throw new Error(`${id}: SecondaryBody.items[${index}] 只接受有效的 label/value/maxLines。`);
      }
      if (role === "body" && item.label !== undefined) {
        throw new Error(`${id}: body SecondaryBody 不接受 item.label。`);
      }
      const maxLines = item.maxLines ?? 1;
      if (!Number.isInteger(maxLines) || ![1, 2].includes(maxLines as number)) {
        throw new Error(`${id}: SecondaryBody.items[${index}].maxLines 只接受 1 或 2。`);
      }
      return item;
    });
    const separator = p.separator ?? " ｜ ";
    const columns = p.columns ?? 2;
    if (!Number.isInteger(columns) || ![1, 2].includes(columns as number)) {
      throw new Error(`${id}: SecondaryBody.columns 只接受 1 或 2。`);
    }
    if (typeof separator !== "string" || !separator) {
      throw new Error(`${id}: SecondaryBody.separator 必须是非空文本。`);
    }
    let variant: string | undefined;
    if (role === "body") variant = items[0].maxLines === 2 ? "bodyMultiline" : "body";
    else if (role === "metadata") variant = "metadata";
    else if (items.length > 2) variant = "multiline";
    const textStyles = recipe(type, size, variant).parts.text.styles;
    const lineHeight = Number(textStyles.height) / Number(textStyles.maxLines ?? 1);
    const rootChildren: string[] = [];
    const rows: Array<[string, MiniNode]> = [];
    for (let start = 0, rowIndex = 0; start < items.length; start += Number(columns), rowIndex++) {
      const rowId = `${id}_row${rowIndex}`;
      rootChildren.push(rowId);
      const rowChildren: string[] = [];
      const rowItems = items.slice(start, start + Number(columns));
      const rowHeight = lineHeight * Math.max(...rowItems.map(item => Number(item.maxLines ?? 1)));
      rowItems.forEach((item, localIndex) => {
        const maxLines = Number(item.maxLines ?? 1);
        const itemHeight = lineHeight * maxLines;
        const itemIndex = start + localIndex;
        if (rowChildren.length) {
          const separatorId = `${rowId}_separator`;
          rowChildren.push(separatorId);
          rows.push(row(separatorId, type, "separator", size, {
            content: separator,
            fontColor: colorWithAlpha(p.fontColor as string, 0.6),
          }, [], variant));
        }
        const itemId = `${id}_item${itemIndex}`;
        const itemChildren: string[] = [];
        rowChildren.push(itemId);
        if (item.label !== undefined) {
          const labelId = `${itemId}_label`;
          itemChildren.push(labelId);
          rows.push(row(labelId, type, "text", size, {
            content: item.label,
            fontColor: p.fontColor,
            height: lineHeight, maxLines: 1, flexShrink: 0,
          }, [], variant));
        }
        const valueId = `${itemId}_value`;
        itemChildren.push(valueId);
        rows.push(row(valueId, type, "text", size, {
          content: item.value,
          fontColor: colorWithAlpha(p.fontColor as string, 0.6),
          height: itemHeight, maxLines, layoutWeight: 1,
        }, [], variant));
        rows.push(row(itemId, type, "item", size, {
          layoutWeight: 1, height: itemHeight, alignItems: "start",
        }, itemChildren, variant));
      });
      rows.push(row(rowId, type, "row", size, {
        height: rowHeight, alignItems: "start",
      }, rowChildren, variant));
    }
    return [row(id, type, "root", size, {}, rootChildren, variant), ...rows];
  }

  if (type === "H_BarChart") {
    const allowed = ["items", "fontColor", "barColor", "trackColor"];
    requireProps(id, type, p, allowed, allowed);
    ["fontColor", "barColor", "trackColor"].forEach(name => requireColor(id, type, p, name));
    if (!Array.isArray(p.items) || p.items.length < 2 || p.items.length > 3) {
      throw new Error(`${id}: H_BarChart.items 需要 2–3 项。`);
    }
    const items = p.items.map((item, index) => {
      const valid = record(item)
        && Object.keys(item).sort().join(",") === "label,percent,valueUnit"
        && typeof item.label === "string" && item.label.trim()
        && isDisplayValue(item.valueUnit)
        && typeof item.percent === "number" && Number.isFinite(item.percent)
        && item.percent >= 0 && item.percent <= 100;
      if (!valid) throw new Error(`${id}: H_BarChart.items[${index}] 无效。`);
      return item;
    });
    const variant = items.length === 3 ? "threeItems" : undefined;
    const children: string[] = [];
    const rows: Array<[string, MiniNode]> = [];
    items.forEach((item, index) => {
      const itemId = `${id}_item${index}`;
      const metaId = `${itemId}_meta`;
      const labelId = `${itemId}_label`;
      const valueId = `${itemId}_value`;
      const barId = `${itemId}_bar`;
      children.push(itemId);
      rows.push(
        row(itemId, type, "item", size, {}, [metaId, barId], variant),
        row(metaId, type, "meta", size, {}, [labelId, valueId], variant),
        row(labelId, type, "label", size, { content: item.label, fontColor: p.fontColor }, [], variant),
        row(valueId, type, "value", size, { content: item.valueUnit, fontColor: p.fontColor }, [], variant),
        row(barId, type, "bar", size, {
          type: "linear", value: item.percent, total: 100,
          color: p.barColor, backgroundColor: p.trackColor,
        }, [], variant),
      );
    });
    return [row(id, type, "root", size, {}, children, variant), ...rows];
  }

  if (type === "NumericRatioStack") {
    const allowed = ["items", "direction", "fontColor", "fillColor"];
    requireProps(id, type, p, ["items", "fontColor", "fillColor"], allowed);
    requireColor(id, type, p, "fontColor");
    requireColor(id, type, p, "fillColor");
    const direction = p.direction ?? "column";
    if (!(["row", "column"] as unknown[]).includes(direction)) {
      throw new Error(`${id}: NumericRatioStack.direction 只接受 row 或 column。`);
    }
    if (!Array.isArray(p.items) || p.items.length !== 3) {
      throw new Error(`${id}: NumericRatioStack.items 必须恰好 3 项。`);
    }
    const variant = direction === "row" ? "row" : undefined;
    const children: string[] = [];
    const rows: Array<[string, MiniNode]> = [];
    p.items.forEach((item, index) => {
      const valid = record(item) && typeof item.icon === "string" && item.icon.trim()
        && isDisplayValue(item.value)
        && Object.keys(item).every(key => ["icon", "value", "unit"].includes(key))
        && (item.unit === undefined || (typeof item.unit === "string" && item.unit.trim()));
      if (!valid) throw new Error(`${id}: NumericRatioStack.items[${index}] 无效。`);
      const itemId = `${id}_item${index}`;
      const iconSlotId = `${itemId}_icon_slot`;
      const iconId = `${itemId}_icon`;
      const valueGroupId = `${itemId}_value_group`;
      const valueId = `${itemId}_value`;
      const valueChildren = [valueId];
      const itemChildren = [iconSlotId, valueGroupId];
      children.push(itemId);
      rows.push(
        row(iconSlotId, type, "iconSlot", size, {}, [iconId], variant),
        row(iconId, type, "icon", size, { src: item.icon, fillColor: p.fillColor }, [], variant),
        row(valueId, type, "value", size, { content: item.value, fontColor: p.fontColor }, [], variant),
      );
      let unit = item.unit;
      if (unit === undefined && typeof item.value === "number") unit = "%";
      if (unit === undefined && record(item.value) && typeof item.value.path === "string") {
        const initial = data?.get(item.value.path);
        if (typeof initial === "number") unit = "%";
      }
      if (unit !== undefined) {
        const unitId = `${itemId}_unit`;
        valueChildren.push(unitId);
        rows.push(row(unitId, type, "value", size, {
          content: unit, fontColor: p.fontColor,
        }, [], variant));
      }
      rows.push(row(valueGroupId, type, "valueGroup", size, {}, valueChildren, variant));
      rows.push(row(itemId, type, "item", size, {}, itemChildren, variant));
    });
    return [row(id, type, "root", size, {}, children, variant), ...rows];
  }

  if (type === "ProgressCircle") {
    const allowed = [
      "externalText", "icon", "accessibility", "fontColor", "fillColor", "color",
      "backgroundColor", "width", "height",
    ];
    const required = [
      "externalText", "icon", "accessibility", "fontColor", "color", "backgroundColor",
      "width", "height",
    ];
    requireProps(id, type, p, required, allowed);
    requireOptionalIcon(id, type, p);
    ["fontColor", "color", "backgroundColor"].forEach(name => requireColor(id, type, p, name));
    requireProgressCircleAccessibility(id, p.accessibility);
    const width = p.width;
    const height = p.height;
    if (typeof width !== "number" || !Number.isFinite(width) || width <= 0
      || typeof height !== "number" || !Number.isFinite(height) || height <= 0) {
      throw new Error(`${id}: ProgressCircle.width/height 必须是正数。`);
    }
    const metrics = recipe(type, size).metrics;
    const textHeight = metrics?.externalTextHeight;
    const itemMargin = metrics?.itemMargin;
    const minimumDiameter = metrics?.minimumRingDiameter;
    const strokeWidth = metrics?.strokeWidth;
    if (![textHeight, itemMargin, minimumDiameter, strokeWidth].every(value =>
      typeof value === "number" && Number.isFinite(value) && value > 0)) {
      throw new Error("ProgressCircle 视觉 Recipe 几何无效。");
    }
    const ringDiameter = Math.min(width, height - Number(textHeight) - Number(itemMargin));
    if (ringDiameter < Number(minimumDiameter)) {
      throw new Error(`${id}: ProgressCircle.width/height 留给圆环的空间不足。`);
    }
    const [progressValue, externalText] = progressCircleValues(id, p.externalText, data);
    const ringStackId = `${id}_ring_stack`;
    const ringId = `${id}_ring`;
    const iconId = `${id}_icon`;
    const externalTextId = `${id}_external_text`;
    return [
      row(
        id,
        type,
        "root",
        size,
        { width, height, accessibility: p.accessibility },
        [ringStackId, externalTextId],
      ),
      row(
        ringStackId,
        type,
        "ringStack",
        size,
        { width: ringDiameter, height: ringDiameter },
        [ringId, iconId],
      ),
      row(ringId, type, "ring", size, {
        width: ringDiameter,
        height: ringDiameter,
        value: progressValue,
        total: 100,
        strokeWidth,
        color: p.color,
        backgroundColor: p.backgroundColor,
      }),
      row(iconId, type, "icon", size, {
        src: p.icon,
        ...(p.fillColor ? { fillColor: p.fillColor } : {}),
      }),
      row(externalTextId, type, "externalText", size, {
        content: externalText,
        width,
        fontColor: p.fontColor,
      }),
    ];
  }

  if (type === "PillButton") {
    if (!["2x2", "2x4"].includes(size)) throw new Error("PillButton 仅支持 2x2 或 2x4 卡片。");
    const allowed = [
      "label", "icon", "actionInk", "actionSurface", "fontSize", "fontWeight", "onClick", "width",
    ];
    requireProps(id, type, p, ["label", "actionInk", "actionSurface", "onClick"], allowed);
    if (typeof p.label !== "string" || !p.label.trim()) {
      throw new Error(`${id}: PillButton.label 必须是非空文本。`);
    }
    requireOptionalIcon(id, type, p);
    requireAction(id, type, p.onClick);
    requireColor(id, type, p, "actionInk");
    requireColor(id, type, p, "actionSurface");
    if (p.fontSize !== undefined && p.fontSize !== 14) {
      throw new Error(`${id}: PillButton.fontSize 只能是 14。`);
    }
    if (p.fontWeight !== undefined && ![400, 500].includes(Number(p.fontWeight))) {
      throw new Error(`${id}: PillButton.fontWeight 只能是 400 或 500。`);
    }
    const allowedWidths = size === "2x2" ? ["matchParent", 126] : ["matchParent", 116, 132];
    if (p.width !== undefined && !allowedWidths.includes(p.width as string | number)) {
      throw new Error(`${id}: PillButton.width 不适用于 ${size}。`);
    }
    const visual = visualRecipePart(type, "root", size);
    const base = {
      ...visual.styles,
      ...(p.width !== undefined ? { width: p.width } : {}),
      backgroundColor: p.actionSurface,
      onClick: p.onClick,
    };
    if (!p.icon) {
      return [[id, {
        type: "Button",
        props: {
          ...base,
          label: p.label,
          enabled: true,
          fontColor: p.actionInk,
          fontSize: p.fontSize ?? visual.styles.fontSize ?? 14,
          fontWeight: p.fontWeight ?? visual.styles.fontWeight ?? 500,
          textAlign: "center",
        },
        children: [],
      }]];
    }
    const iconId = `${id}_icon`;
    const textId = `${id}_text`;
    return [
      [id, {
        type: "Row",
        props: { ...base, itemMargin: 8, justifyContent: "center", alignItems: "center" },
        children: [iconId, textId],
      }],
      [iconId, {
        type: "Image",
        props: {
          src: p.icon,
          width: 20,
          height: 20,
          objectFit: "contain",
          flexShrink: 0,
          fillColor: p.actionInk,
        },
        children: [],
      }],
      [textId, {
        type: "Text",
        props: {
          content: p.label,
          maxWidth: 96,
          height: p.height ?? visual.styles.height ?? 36,
          fontSize: p.fontSize ?? visual.styles.fontSize ?? 14,
          fontWeight: p.fontWeight ?? visual.styles.fontWeight ?? 500,
          fontColor: p.actionInk,
          textAlign: "center",
          maxLines: 1,
          flexShrink: 0,
        },
        children: [],
      }],
    ];
  }

  if (type === "CircleButton") {
    if (size !== "2x2") throw new Error("CircleButton 仅支持 2x2 卡片。");
    const allowed = ["icon", "accessibility", "actionInk", "actionSurface", "onClick"];
    requireProps(id, type, p, allowed, allowed);
    requireOptionalIcon(id, type, p);
    requireAction(id, type, p.onClick);
    requireColor(id, type, p, "actionInk");
    requireColor(id, type, p, "actionSurface");
    const accessibility = p.accessibility;
    const validAccessibility = record(accessibility)
      && Object.keys(accessibility).every(key => ["label", "description"].includes(key))
      && typeof accessibility.label === "string"
      && accessibility.label.trim().length > 0;
    if (!validAccessibility) {
      throw new Error(`${id}: CircleButton.accessibility 需要非空 label，只接受 label/description。`);
    }
    if (accessibility.description !== undefined
      && (typeof accessibility.description !== "string" || !accessibility.description.trim())) {
      throw new Error(`${id}: CircleButton.accessibility.description 必须是非空文本。`);
    }
    const visual = visualRecipePart(type, "root", size);
    const iconId = `${id}_icon`;
    return [
      [id, {
        type: "Stack",
        props: {
          ...visual.styles,
          backgroundColor: p.actionSurface,
          alignContent: "center",
          clip: true,
          onClick: p.onClick,
          accessibility: p.accessibility,
        },
        children: [iconId],
      }],
      [iconId, {
        type: "Image",
        props: {
          src: p.icon,
          width: 20,
          height: 20,
          objectFit: "contain",
          flexShrink: 0,
          fillColor: p.actionInk,
        },
        children: [],
      }],
    ];
  }

  if (type === "EmphasizedData") {
    requireProps(id, type, p, ["value", "fontColor"], ["value", "unit", "fontColor"]);
    requireDisplay(id, type, p, "value");
    requireColor(id, type, p, "fontColor");
    if (p.unit !== undefined && (typeof p.unit !== "string" || !p.unit.trim())) {
      throw new Error(`${id}: EmphasizedData.unit 必须是非空文本。`);
    }
    const valueId = `${id}_value`;
    const children = [valueId];
    const rows = [
      row(id, type, "root", size, { itemMargin: p.unit ? 2 : 0 }, children),
      row(valueId, type, "value", size, { content: p.value, fontColor: p.fontColor }),
    ];
    if (p.unit) {
      const unitId = `${id}_unit`;
      children.push(unitId);
      rows.push(row(
        unitId,
        type,
        "unit",
        size,
        { content: p.unit, fontColor: colorWithAlpha(String(p.fontColor), 0.6) },
      ));
    }
    return rows;
  }

  if (type === "InfoBlock") {
    const allowed = [
      "variant", "primaryText", "secondaryText", "fontColor", "backgroundColor",
      "unit", "visual", "icon", "fillColor", "onClick",
    ];
    requireProps(
      id,
      type,
      p,
      ["primaryText", "secondaryText", "fontColor", "backgroundColor"],
      allowed,
    );
    requireDisplay(id, type, p, "primaryText");
    requireDisplay(id, type, p, "secondaryText");
    requireColor(id, type, p, "fontColor");
    requireColor(id, type, p, "backgroundColor");
    if (p.icon !== undefined && (typeof p.icon !== "string" || !p.icon.trim())) {
      throw new Error(`${id}: InfoBlock.icon 必须是非空文本。`);
    }
    if (p.fillColor !== undefined) requireColor(id, type, p, "fillColor");
    if (p.onClick !== undefined) requireAction(id, type, p.onClick);
    if (p.unit !== undefined && (typeof p.unit !== "string" || !p.unit.trim())) {
      throw new Error(`${id}: InfoBlock.unit 必须是非空文本。`);
    }
    if (size === "2x2" && p.variant !== undefined && p.variant !== "stacked") {
      throw new Error('2x2 InfoBlock.variant 只能省略或使用 "stacked"。');
    }
    if (size === "2x4" && !["slot", "aux", "small"].includes(String(p.variant))) {
      throw new Error('2x4 InfoBlock.variant 必须是 "slot"，也兼容 "aux"/"small"。');
    }
    if (p.visual !== undefined && p.icon !== undefined) {
      throw new Error(`${id}: InfoBlock.visual 不能与 legacy icon 同时使用。`);
    }
    let visual: RecordValue | undefined;
    if (record(p.visual)) visual = p.visual;
    else if (p.visual !== undefined) throw new Error(`${id}: InfoBlock.visual 必须是对象。`);
    else if (p.icon !== undefined) visual = { type: "icon", icon: p.icon };
    if (visual) {
      const visualKeys = Object.keys(visual);
      if (visualKeys.some(key => !["type", "icon", "color"].includes(key))
        || !["icon", "progressCircle"].includes(String(visual.type))
        || typeof visual.icon !== "string" || !visual.icon.trim()
        || (visual.color !== undefined && (visual.type !== "icon" || visual.color !== "native"))) {
        throw new Error(`${id}: InfoBlock.visual 无效。`);
      }
    }
    const copyLayout = visual ? { layoutWeight: 1 } : { width: "matchParent" };
    const textId = `${id}_text`;
    const primaryId = `${id}_primary`;
    const secondaryId = `${id}_secondary`;
    const children = [textId];
    const textChildren = [primaryId, secondaryId];
    const rootProps: RecordValue = { backgroundColor: p.backgroundColor };
    if (p.onClick !== undefined) rootProps.onClick = p.onClick;
    const rows = [
      row(id, type, visual ? "root" : "rootNoVisual", size, rootProps, children),
      row(textId, type, "copy", size, copyLayout, textChildren),
      row(
        secondaryId,
        type,
        "secondary",
        size,
        {
          content: p.secondaryText,
          fontColor: colorWithAlpha(String(p.fontColor), 0.6),
        },
      ),
    ];
    if (p.unit === undefined) {
      rows.push(row(primaryId, type, "primary", size, {
        content: p.primaryText, fontColor: p.fontColor,
      }));
    } else {
      const primaryRowId = `${primaryId}_row`;
      const primaryValueId = `${primaryId}_value`;
      const unitId = `${primaryId}_unit`;
      textChildren[0] = primaryRowId;
      rows.push(
        row(primaryRowId, type, "primaryRow", size, {}, [primaryValueId, unitId]),
        row(primaryValueId, type, "primaryValue", size, {
          content: p.primaryText, fontColor: p.fontColor,
        }),
        row(unitId, type, "unit", size, {
          content: p.unit,
          fontColor: colorWithAlpha(p.fontColor as string, 0.6),
        }),
      );
    }
    if (visual?.type === "icon") {
      const iconId = `${id}_visual`;
      children.push(iconId);
      rows.push(row(
        iconId,
        type,
        "icon",
        size,
        {
          src: visual.icon,
          ...(visual.color === "native" ? {} : { fillColor: p.fillColor ?? p.fontColor }),
        },
      ));
    } else if (visual?.type === "progressCircle") {
      const visualId = `${id}_visual`;
      const progressId = `${visualId}_progress`;
      const iconId = `${visualId}_icon`;
      children.push(visualId);
      rows.push(
        row(visualId, type, "progressStack", size, {}, [progressId, iconId]),
        row(progressId, type, "progress", size, {
          type: "ring",
          value: normalizedProgressBinding(id, type, "primaryText", p.primaryText, 100, data),
          total: 100,
          color: p.fontColor,
          backgroundColor: colorWithAlpha(p.fontColor as string, 0.2),
        }),
        row(iconId, type, "progressIcon", size, {
          src: visual.icon,
          fillColor: p.fillColor ?? colorWithAlpha(p.fontColor as string, 0.6),
        }),
      );
    }
    return rows;
  }

  if (type === "ProgressLine2") {
    if (size !== "2x4") throw new Error("ProgressLine2 仅支持 2x4 卡片。");
    const allowed = [
      "value", "total", "displayValue", "unit", "fontColor", "color", "backgroundColor",
    ];
    requireProps(
      id,
      type,
      p,
      ["value", "total", "displayValue", "fontColor", "color", "backgroundColor"],
      allowed,
    );
    requireDisplay(id, type, p, "displayValue");
    if (p.unit !== undefined && (typeof p.unit !== "string" || !p.unit.trim())) {
      throw new Error(`${id}: ProgressLine2.unit 必须是非空文本。`);
    }
    ["fontColor", "color", "backgroundColor"].forEach(name => requireColor(id, type, p, name));
    if (typeof p.total !== "number" || !Number.isFinite(p.total) || p.total <= 0) {
      throw new Error(`${id}: ProgressLine2.total 必须是正数。`);
    }
    const readout = `${id}_readout`;
    const value = `${id}_value`;
    const bar = `${id}_bar`;
    const readoutChildren = [value];
    const rows = [
      row(id, type, "root", size, {}, [readout, bar]),
      row(readout, type, "readout", size, { itemMargin: p.unit ? 2 : 0 }, readoutChildren),
      row(value, type, "value", size, { content: p.displayValue, fontColor: p.fontColor }),
      row(
        bar,
        type,
        "bar",
        size,
        {
          type: "linear",
          value: normalizedProgressBinding(
            id,
            type,
            "value",
            p.value,
            p.total,
            data,
          ),
          total: p.total,
          color: p.color,
          backgroundColor: p.backgroundColor,
        },
      ),
    ];
    if (p.unit) {
      const unit = `${id}_unit`;
      readoutChildren.push(unit);
      rows.push(row(
        unit,
        type,
        "unit",
        size,
        { content: p.unit, fontColor: colorWithAlpha(String(p.fontColor), 0.6) },
      ));
    }
    return rows;
  }

  if (type === "TableText" || type === "TextBlock") {
    const isTable = type === "TableText";
    if (!isTable && size !== "2x4") {
      throw new Error("TextBlock 仅支持 2x4 卡片。");
    }
    const required = isTable
      ? ["items", "fontColor"]
      : ["items", "fontColor", "backgroundColor"];
    requireProps(id, type, p, required, ["items", "fontColor", "backgroundColor"]);
    requireColor(id, type, p, "fontColor");
    if (!isTable) requireColor(id, type, p, "backgroundColor");
    const items = labelValueItems(id, type, p.items, 2, isTable ? 3 : 4);
    const variant = isTable && items.length === 3 ? "compact" : undefined;
    const children: string[] = [];
    const rows: Array<[string, MiniNode]> = [];
    items.forEach((item, index) => {
      const itemId = `${id}_${isTable ? "row" : "item"}${index}`;
      const labelId = `${itemId}_label`;
      const valueId = `${itemId}_value`;
      children.push(itemId);
      rows.push(row(
        itemId,
        type,
        isTable ? "row" : "item",
        size,
        isTable ? {} : { backgroundColor: p.backgroundColor },
        [labelId, valueId],
        variant,
      ));
      rows.push(row(
        labelId,
        type,
        "label",
        size,
        {
          content: item.label,
          fontColor: isTable ? colorWithAlpha(String(p.fontColor), 0.6) : p.fontColor,
        },
        [],
        variant,
      ));
      rows.push(row(
        valueId,
        type,
        "value",
        size,
        { content: item.value, fontColor: p.fontColor },
        [],
        variant,
      ));
    });
    const gap = recipe(type, size, variant).metrics?.[
      items.length === 2 ? "twoRowGap" : "threeRowGap"
    ];
    return [
      row(id, type, "root", size, isTable ? { itemMargin: gap } : {}, children, variant),
      ...rows,
    ];
  }

  if (type === "CardButton") {
    if (size !== "2x4") throw new Error("CardButton 仅支持 2x4 卡片。");
    const allowed = [
      "label", "onClick", "fontColor", "backgroundColor", "icon", "fillColor",
    ];
    requireProps(id, type, p, ["label", "onClick", "fontColor", "backgroundColor"], allowed);
    requireDisplay(id, type, p, "label");
    requireColor(id, type, p, "fontColor");
    requireColor(id, type, p, "backgroundColor");
    requireOptionalIcon(id, type, p);
    requireAction(id, type, p.onClick);
    const label = `${id}_label`;
    const visual = `${id}_visual`;
    const visualProps = p.icon
      ? { src: p.icon, ...(p.fillColor ? { fillColor: p.fillColor } : {}) }
      : { backgroundColor: colorWithAlpha(String(p.fontColor), 0.2) };
    return [
      row(
        id,
        type,
        "root",
        size,
        { backgroundColor: p.backgroundColor, onClick: p.onClick },
        [label, visual],
      ),
      row(label, type, "label", size, { content: p.label, fontColor: p.fontColor }),
      row(visual, type, p.icon ? "icon" : "placeholder", size, visualProps),
    ];
  }

  if (type === "ProgressCircleSingle") {
    if (size !== "2x2" && size !== "2x4") {
      throw new Error("ProgressCircleSingle 仅支持 2x2 或 2x4 卡片。");
    }
    const allowed = [
      "value", "total", "icon", "displayValue", "label", "secondaryLabel", "fontColor",
      "color", "backgroundColor",
    ];
    requireProps(
      id,
      type,
      p,
      [
        "value", "total", "icon", "displayValue", "label", "fontColor", "color",
        "backgroundColor",
      ],
      allowed,
    );
    requireDisplay(id, type, p, "value");
    requireDisplay(id, type, p, "displayValue");
    requireOptionalIcon(id, type, p);
    if (typeof p.label !== "string" || !p.label.trim()) {
      throw new Error(`${id}: ProgressCircleSingle.label 必须是非空文本。`);
    }
    if (typeof p.total !== "number" || !Number.isFinite(p.total) || p.total <= 0) {
      throw new Error(`${id}: ProgressCircleSingle.total 必须是正数。`);
    }
    if (p.secondaryLabel !== undefined && !isDisplayValue(p.secondaryLabel)) {
      throw new Error(`${id}: ProgressCircleSingle.secondaryLabel 必须是可显示文本。`);
    }
    ["fontColor", "color", "backgroundColor"].forEach(name => requireColor(id, type, p, name));
    const ringStack = `${id}_ring_stack`;
    const ring = `${id}_ring`;
    const icon = `${id}_icon`;
    const labels = `${id}_labels`;
    const label = `${id}_label`;
    const display = `${id}_display`;
    const secondary = `${id}_secondary`;
    const variant = p.secondaryLabel === undefined ? undefined : "withSecondary";
    const labelChildren = [label, display];
    if (p.secondaryLabel !== undefined) labelChildren.push(secondary);
    const rows = [
      row(id, type, "root", size, {}, [ringStack, labels], variant),
      row(ringStack, type, "ringStack", size, {}, [ring, icon], variant),
      row(
        ring,
        type,
        "ring",
        size,
        {
          type: "ring",
          value: normalizedProgressBinding(
            id,
            type,
            "value",
            p.value,
            p.total,
            data,
          ),
          total: p.total,
          color: p.color,
          backgroundColor: p.backgroundColor,
        },
        [],
        variant,
      ),
      row(
        icon,
        type,
        "icon",
        size,
        { src: p.icon, fillColor: colorWithAlpha(String(p.fontColor), 0.6) },
        [],
        variant,
      ),
      row(labels, type, "labels", size, {}, labelChildren, variant),
      row(label, type, "label", size, { content: p.label, fontColor: p.fontColor }, [], variant),
      row(
        display,
        type,
        "display",
        size,
        {
          content: p.displayValue,
          fontColor: colorWithAlpha(String(p.fontColor), 0.6),
        },
        [],
        variant,
      ),
    ];
    if (p.secondaryLabel !== undefined) {
      rows.push(row(
        secondary,
        type,
        "secondary",
        size,
        {
          content: p.secondaryLabel,
          fontColor: colorWithAlpha(String(p.fontColor), 0.6),
        },
        [],
        variant,
      ));
    }
    return rows;
  }

  if (type === "EventCard") {
    const allowed = ["items", "title", "time", "location", "density", "fontColor"];
    requireProps(id, type, p, ["fontColor"], allowed);
    requireColor(id, type, p, "fontColor");
    if (p.density !== undefined && p.density !== "compact") {
      throw new Error(`${id}: EventCard.density 只接受 compact。`);
    }
    if (p.items !== undefined && (p.title !== undefined || p.time !== undefined)) {
      throw new Error(`${id}: EventCard.items 不能与 title/time 同时使用。`);
    }
    let items: RecordValue[];
    if (Array.isArray(p.items)) items = p.items as RecordValue[];
    else if (p.title !== undefined && p.time !== undefined) {
      items = [{ title: p.title, time: p.time, ...(p.location === undefined ? {} : { location: p.location }) }];
    } else throw new Error(`${id}: EventCard 需要 items 或 title/time。`);
    if (items.length < 1 || items.length > 2) {
      throw new Error(`${id}: EventCard.items 需要 1–2 项。`);
    }
    items.forEach((item, index) => {
      const valid = record(item) && isDisplayValue(item.title) && isDisplayValue(item.time)
        && Object.keys(item).every(key => ["title", "time", "location"].includes(key))
        && (item.location === undefined || isDisplayValue(item.location));
      if (!valid) throw new Error(`${id}: EventCard.items[${index}] 无效。`);
    });
    const compact = p.density === "compact";
    const secondaryColor = colorWithAlpha(String(p.fontColor), 0.6);
    const itemIds: string[] = [];
    const rows: Array<[string, MiniNode]> = [];
    let totalHeight = 0;
    items.forEach((item, index) => {
      const itemId = items.length === 1 ? id : `${id}_item${index}`;
      const variant = compact ? "compact" : (item.location === undefined ? "withoutLocation" : "withLocation");
      const metrics = recipe(type, size, variant).metrics!;
      const rail = `${itemId}_rail`;
      const dot = `${rail}_dot`;
      const line = `${rail}_line`;
      const texts = `${itemId}_texts`;
      const title = `${itemId}_title`;
      const time = `${itemId}_time`;
      const metaRow = `${itemId}_meta`;
      const location = `${itemId}_location`;
      const textChildren = compact ? [title, metaRow] : [title, time];
      if (!compact && item.location !== undefined) textChildren.push(location);
      itemIds.push(itemId);
      totalHeight += Number(metrics.height);
      rows.push(
        row(itemId, type, items.length === 1 ? "root" : "item", size, {
          height: metrics.height,
        }, [rail, texts], variant),
        row(rail, type, "rail", size, {
          height: metrics.height, clip: true,
        }, [dot, line], variant),
        row(dot, type, "dot", size, {
          borderColor: p.fontColor, backgroundColor: "#00FFFFFF", alignContent: "center",
        }, [], variant),
        row(line, type, "line", size, {
          height: metrics.lineHeight, color: secondaryColor,
        }, [], variant),
        row(texts, type, "copy", size, { height: metrics.height }, textChildren, variant),
        row(title, type, "title", size, {
          content: item.title, fontColor: p.fontColor,
        }, [], variant),
        row(time, type, "meta", size, {
          content: item.time, fontColor: secondaryColor,
        }, [], variant),
      );
      if (compact) {
        const metaChildren = [time];
        if (item.location !== undefined) {
          const separator = `${metaRow}_separator`;
          metaChildren.push(separator, location);
          rows.push(
            row(separator, type, "separator", size, {
              content: "｜", fontColor: secondaryColor,
            }, [], variant),
            row(location, type, "meta", size, {
              content: item.location, fontColor: secondaryColor,
            }, [], variant),
          );
        }
        rows.push(row(metaRow, type, "metaRow", size, {}, metaChildren, variant));
      } else if (item.location !== undefined) {
        rows.push(row(location, type, "meta", size, {
          content: item.location, fontColor: secondaryColor,
        }, [], variant));
      }
    });
    if (items.length === 1) return rows;
    totalHeight += 8;
    return [row(id, type, "multiRoot", size, { height: totalHeight }, itemIds), ...rows];
  }

  if (type === "DataDisplay") {
    if (size !== "2x2") throw new Error("DataDisplay 仅支持 2x2 卡片。");
    const allowed = ["label", "value", "supportingText", "fontColor"];
    requireProps(id, type, p, allowed, allowed);
    if (typeof p.label !== "string" || !p.label.trim()
      || typeof p.supportingText !== "string" || !p.supportingText.trim()) {
      throw new Error(`${id}: DataDisplay.label/supportingText 必须是非空文本。`);
    }
    requireDisplay(id, type, p, "value");
    requireColor(id, type, p, "fontColor");
    const secondaryColor = colorWithAlpha(String(p.fontColor), 0.6);
    const label = `${id}_label`;
    const value = `${id}_value`;
    const supporting = `${id}_supporting`;
    return [
      row(id, type, "root", size, {}, [label, value, supporting]),
      row(label, type, "label", size, { content: p.label, fontColor: secondaryColor }),
      row(value, type, "value", size, { content: p.value, fontColor: p.fontColor }),
      row(
        supporting,
        type,
        "supporting",
        size,
        { content: p.supportingText, fontColor: secondaryColor },
      ),
    ];
  }

  if (type === "TopTextBottomValue") {
    if (size !== "2x4") throw new Error("TopTextBottomValue 仅支持 2x4 卡片。");
    const allowed = ["items", "fontColor", "dividerColor"];
    requireProps(id, type, p, allowed, allowed);
    requireColor(id, type, p, "fontColor");
    requireColor(id, type, p, "dividerColor");
    const items = labelValueUnitItems(id, type, p.items);
    const children: string[] = [];
    const rows: Array<[string, MiniNode]> = [];
    items.forEach((item, index) => {
      if (index) {
        const divider = `${id}_divider${index - 1}`;
        children.push(divider);
        rows.push(row(divider, type, "divider", size, { color: p.dividerColor }));
      }
      const itemId = `${id}_item${index}`;
      const value = `${itemId}_value`;
      const label = `${itemId}_label`;
      const unit = `${itemId}_unit`;
      children.push(itemId);
      rows.push(row(itemId, type, "item", size, {}, [label, value, unit]));
      rows.push(row(
        label,
        type,
        "label",
        size,
        { content: item.label, fontColor: p.fontColor },
      ));
      rows.push(row(
        value,
        type,
        "value",
        size,
        { content: item.value, fontColor: p.fontColor },
      ));
      rows.push(row(
        unit,
        type,
        "unit",
        size,
        { content: item.unit, fontColor: colorWithAlpha(String(p.fontColor), 0.6) },
      ));
    });
    return [row(id, type, "root", size, {}, children), ...rows];
  }

  if (type === "SummaryList") {
    if (size !== "2x4") throw new Error("SummaryList 仅支持 2x4 卡片。");
    const allowed = ["items", "fontColor", "backgroundColor"];
    requireProps(id, type, p, allowed, allowed);
    requireColor(id, type, p, "fontColor");
    requireColor(id, type, p, "backgroundColor");
    if (!Array.isArray(p.items)
      || p.items.length < 2
      || p.items.length > 3
      || !p.items.every(isDisplayValue)) {
      throw new Error(`${id}: SummaryList.items 需要 2–3 项可显示文本。`);
    }
    const children = p.items.map((_, index) => `${id}_item${index}`);
    const rows: Array<[string, MiniNode]> = [[id, {
      type: "Column",
      props: {
        width: "matchParent",
        height: p.items.length === 2 ? 64 : 102,
        itemMargin: 8,
        alignItems: "start",
      },
      children,
    }]];
    p.items.forEach((item, index) => {
      const text = `${children[index]}_text`;
      rows.push([children[index], {
        type: "Row",
        props: {
          width: "matchParent",
          height: 28,
          padding: { left: 12, right: 12 },
          borderRadius: 8,
          backgroundColor: p.backgroundColor,
          alignItems: "center",
        },
        children: [text],
      }]);
      rows.push([text, {
        type: "Text",
        props: {
          content: item,
          width: "matchParent",
          fontSize: 12,
          fontWeight: 400,
          fontColor: p.fontColor,
          maxLines: 1,
        },
        children: [],
      }]);
    });
    return rows;
  }
  return null;
}

export function expandCompactComponents(
  input: Map<string, MiniNode>,
  size: CardSize,
  data?: ExpansionDataContext,
) {
  let nodes = new Map(input);
  const putExpansion = (
    originalId: string,
    type: string,
    rows: Array<[string, MiniNode]>,
  ) => {
    for (const [id, expanded] of rows) {
      if (id !== originalId && nodes.has(id)) {
        throw new Error(`${type} 生成的 ID 与现有组件冲突：${id}`);
      }
      nodes.set(id, expanded);
    }
  };

  for (const [id, node] of input) {
    const parent = [...input.values()].find(item => item.children.includes(id));
    const rows = expandHighLevel(id, node, size, data);
    if (rows) {
      if (node.type === "CircleButton") {
        const centeredSlot = parent?.type === "Stack"
          && parent.props.width === 40
          && parent.props.height === 40
          && parent.props.alignContent === "center";
        if (!centeredSlot) throw new Error("CircleButton 需要居中的 40×40 Stack 槽位。");
      }
      const props = rows[0][1].props;
      if (parent?.type === "Row" && props.width === "matchParent" && node.props.width === undefined) {
        props.layoutWeight = 1;
      }
      for (const key of PLACEMENT_PROPS) {
        if (node.props[key] !== undefined) props[key] = clone(node.props[key]);
      }
      if (node.props.width !== undefined && node.props.layoutWeight === undefined) delete props.layoutWeight;
      putExpansion(id, node.type, rows);
    }
  }

  const add = (id: string, type: string, props: RecordValue, children: string[] = []) => {
    if (nodes.has(id)) throw new Error(`高级组件生成的 ID 与现有组件冲突：${id}`);
    nodes.set(id, { type, props, children });
  };
  const rootDesign = input.get("root")?.props.design;
  const fusion = typeof rootDesign === "string" && Object.hasOwn(FUSION_PALETTES, rootDesign);
  for (const [id, node] of [...nodes]) {
    const p = node.props;
    if (!["SingleLineTitle", "TimelineUnit"].includes(node.type)) continue;
    requireNoChildren(id, node.type, node.children);
    if (node.type === "SingleLineTitle") {
      const allowed = ["title", "fontColor"];
      const invalid = Object.keys(p).some(key => !allowed.includes(key) && !PLACEMENT_PROPS.includes(key))
        || p.title == null
        || typeof p.fontColor !== "string";
      if (invalid) {
        throw new Error("SingleLineTitle 只接受 title/fontColor 和合法布局属性。");
      }
      const rootVisual = visualRecipePart("SingleLineTitle", "root", size);
      const titleVisual = visualRecipePart("SingleLineTitle", "title", size);
      const children = [`${id}_title`];
      add(children[0], "Text", {
        ...titleVisual.styles,
        content: p.title,
        fontColor: p.fontColor,
      });
      nodes.set(id, {
        type: rootVisual.component,
        props: {
          ...rootVisual.styles,
          ...([...input.values()].some(item => item.type === "Row" && item.children.includes(id))
            && p.width === undefined ? { layoutWeight: 1 } : {}),
          ...Object.fromEntries(PLACEMENT_PROPS.filter(key => key in p).map(key => [key, p[key]])),
        },
        children,
      });
    } else if (node.type === "TimelineUnit") {
      if (size !== "2x2") throw new Error("TimelineUnit 仅支持 2x2 卡片。");
      const invalid = Object.keys(p).some(key => !["color", "lineColor"].includes(key))
        || ![p.color, p.lineColor].every(
          color => typeof color === "string" && /^#[\da-f]{8}$/i.test(color),
        );
      if (invalid) throw new Error("TimelineUnit 需要 ARGB color 和 lineColor。");
      nodes.set(id, {
        type: "Column",
        props: {
          width: 8,
          height: 48,
          padding: { top: 4, right: 0, bottom: 2, left: 0 },
          itemMargin: 4,
          alignItems: "center",
          justifyContent: "start",
          flexShrink: 0,
        },
        children: [`${id}_dot`, `${id}_line`],
      });
      add(`${id}_dot`, "Divider", {
        width: 8,
        height: 8,
        strokeWidth: 0,
        color: "#00000000",
        borderWidth: 1.5,
        borderColor: p.color,
        borderRadius: 4,
        flexShrink: 0,
      });
      add(`${id}_line`, "Divider", {
        width: 1,
        height: 30,
        strokeWidth: 1,
        vertical: true,
        color: p.lineColor,
        flexShrink: 0,
      });
    }
  }

  nodes = adaptCompactRegions(nodes, input, size);
  if (fusion) {
    if (size !== "2x2") throw new Error("融球背景仅支持 2x2 卡片。");
    const root = nodes.get("root")!;
    const colors = FUSION_PALETTES[String(root.props.design)];
    const foreground = "__genui_render_component__root";
    const { design, backgroundColor, linearGradient, backgroundImage, ...props } = root.props;
    add(
      foreground,
      root.type,
      { ...props, width: "matchParent", height: "matchParent" },
      root.children,
    );
    nodes.set("root", {
      type: "Stack",
      props: {
        width: "matchParent",
        height: "matchParent",
        borderRadius: 20,
        clip: true,
        alignContent: "topStart",
      },
      children: ["fusionBallBackground", foreground],
    });
    add(
      "fusionBallBackground",
      "Stack",
      {
        width: "matchParent",
        height: "matchParent",
        borderRadius: 20,
        clip: true,
        alignContent: "topStart",
        accessibility: { decorative: true },
      },
      ["fusionBallLargeSlot", "fusionBallMediumSlot", "fusionBallSmallSlot", "fusionBallGlassLayer"],
    );
    const geometries = [
      [180, 44, 210, "center", "Large"],
      [80, 220, 160, "bottom", "Medium"],
      [195, 190, 100, "bottomEnd", "Small"],
    ] as const;
    geometries.forEach(([width, height, diameter, align, name], index) => {
      const ball = `fusionBall${name}`;
      add(
        `${ball}Slot`,
        "Stack",
        { width: `${width / 160 * 100}%`, height: `${height / 160 * 100}%`, alignContent: align },
        [ball],
      );
      add(ball, "Divider", {
        width: `${diameter / width * 100}%`,
        height: `${diameter / height * 100}%`,
        borderRadius: 999,
        strokeWidth: 0,
        color: "#00000000",
        backgroundColor: colors[index],
      });
    });
    add("fusionBallGlassLayer", "Divider", {
      width: "matchParent",
      height: "matchParent",
      strokeWidth: 0,
      color: "#00000000",
      backgroundColor: "#0DFFFFFF",
      backdropBlur: { radius: 210 },
    });
  }
  return nodes;
}
