import visualRecipes from "../../../../../cloud/data/protocol_profiles/design-compact-dsl-fusion/runtime/visual-recipes-v1.json";

/** Expansion contracts from the shared Fusion Compact component runtime. */
export type MiniNode = { type: string; props: Record<string, unknown>; children: string[] };
export type CardSize = "2x2" | "2x4";
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
  "PillButton", "CircleButton", "EmphasizedData", "InfoBlock", "ProgressLine2",
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

function expandHighLevel(
  id: string,
  node: MiniNode,
  size: CardSize,
): Array<[string, MiniNode]> | null {
  const p = node.props;
  const type = node.type;
  if (!(HIGH_LEVEL_COMPONENT_TYPES as readonly string[]).includes(type)) return null;
  requireNoChildren(id, type, node.children);

  if (type === "PillButton") {
    if (size !== "2x2") throw new Error("PillButton 仅支持 2x2 卡片。");
    const allowed = [
      "label", "icon", "actionInk", "actionSurface", "fontSize", "fontWeight", "onClick",
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
    return [row(id, type, "root", size, { ...p, state: "capsule" })];
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
    return [row(id, type, "root", size, { ...p, state: "icon-round" })];
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
      "icon", "fillColor", "onClick",
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
    requireOptionalIcon(id, type, p);
    if (p.onClick !== undefined) requireAction(id, type, p.onClick);
    if (size === "2x2" && p.variant !== undefined && p.variant !== "stacked") {
      throw new Error('2x2 InfoBlock.variant 只能省略或使用 "stacked"。');
    }
    if (size === "2x4" && !["slot", "aux", "small"].includes(String(p.variant))) {
      throw new Error('2x4 InfoBlock.variant 必须是 "slot"，也兼容 "aux"/"small"。');
    }
    const copyLayout = p.icon ? { layoutWeight: 1 } : { width: "matchParent" };
    const textId = `${id}_text`;
    const primaryId = `${id}_primary`;
    const secondaryId = `${id}_secondary`;
    const children = [textId];
    const rootProps: RecordValue = { backgroundColor: p.backgroundColor };
    if (p.onClick !== undefined) rootProps.onClick = p.onClick;
    const rows = [
      row(id, type, p.icon ? "root" : "rootNoVisual", size, rootProps, children),
      row(textId, type, "copy", size, copyLayout, [primaryId, secondaryId]),
      row(
        primaryId,
        type,
        "primary",
        size,
        { content: p.primaryText, fontColor: p.fontColor },
      ),
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
    if (p.icon) {
      const iconId = `${id}_icon`;
      children.push(iconId);
      rows.push(row(
        iconId,
        type,
        "icon",
        size,
        { src: p.icon, ...(p.fillColor ? { fillColor: p.fillColor } : {}) },
      ));
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
          value: p.value,
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
    if (size !== (isTable ? "2x2" : "2x4")) {
      throw new Error(`${type} 仅支持 ${isTable ? "2x2" : "2x4"} 卡片。`);
    }
    const required = isTable
      ? ["items", "fontColor"]
      : ["items", "fontColor", "backgroundColor"];
    requireProps(id, type, p, required, ["items", "fontColor", "backgroundColor"]);
    requireColor(id, type, p, "fontColor");
    if (!isTable) requireColor(id, type, p, "backgroundColor");
    const items = labelValueItems(id, type, p.items, 2, isTable ? 3 : 2);
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
      ));
      rows.push(row(
        valueId,
        type,
        "value",
        size,
        { content: item.value, fontColor: p.fontColor },
      ));
    });
    const gap = recipe(type, size).metrics?.[
      items.length === 2 ? "twoRowGap" : "threeRowGap"
    ];
    return [row(id, type, "root", size, isTable ? { itemMargin: gap } : {}, children), ...rows];
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
    if (size !== "2x4") throw new Error("ProgressCircleSingle 仅支持 2x4 卡片。");
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
          value: p.value,
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
    if (size !== "2x2") throw new Error("EventCard 仅支持 2x2 卡片。");
    const allowed = ["title", "time", "location", "fontColor"];
    requireProps(id, type, p, ["title", "time", "fontColor"], allowed);
    requireDisplay(id, type, p, "title");
    requireDisplay(id, type, p, "time");
    if (p.location !== undefined) requireDisplay(id, type, p, "location");
    requireColor(id, type, p, "fontColor");
    const secondaryColor = colorWithAlpha(String(p.fontColor), 0.6);
    const variant = p.location === undefined ? "withoutLocation" : "withLocation";
    const metrics = recipe(type, size, variant).metrics!;
    const rail = `${id}_rail`;
    const dot = `${rail}_dot`;
    const line = `${rail}_line`;
    const texts = `${id}_texts`;
    const title = `${id}_title`;
    const time = `${id}_time`;
    const textChildren = [title, time];
    const rows = [
      row(
        id,
        type,
        "root",
        size,
        { height: metrics.height, layoutWeight: 1 },
        [rail, texts],
        variant,
      ),
      row(
        rail,
        type,
        "rail",
        size,
        { height: metrics.height, clip: true },
        [dot, line],
        variant,
      ),
      row(
        dot,
        type,
        "dot",
        size,
        { borderColor: p.fontColor, backgroundColor: "#00FFFFFF", alignContent: "center" },
        [],
        variant,
      ),
      row(
        line,
        type,
        "line",
        size,
        { height: metrics.lineHeight, color: secondaryColor },
        [],
        variant,
      ),
      row(texts, type, "copy", size, { height: metrics.height }, textChildren, variant),
      row(
        title,
        type,
        "title",
        size,
        { content: p.title, fontColor: p.fontColor },
        [],
        variant,
      ),
      row(
        time,
        type,
        "meta",
        size,
        { content: p.time, fontColor: secondaryColor },
        [],
        variant,
      ),
    ];
    if (p.location !== undefined) {
      const location = `${id}_location`;
      textChildren.push(location);
      rows.push(row(
        location,
        type,
        "meta",
        size,
        { content: p.location, fontColor: secondaryColor },
        [],
        variant,
      ));
    }
    return rows;
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

export function expandCompactComponents(input: Map<string, MiniNode>, size: CardSize) {
  const nodes = new Map(input);
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
    const rows = expandHighLevel(id, node, size);
    if (rows) {
      const parent = [...input.values()].find(item => item.children.includes(id));
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
    if (!["CardHeader", "TimelineUnit", "ActionUnit"].includes(node.type)) continue;
    requireNoChildren(id, node.type, node.children);
    if (node.type === "CardHeader") {
      const allowed = ["title", "fontColor", "icon", "fillColor"];
      const invalid = Object.keys(p).some(key => !allowed.includes(key) && !PLACEMENT_PROPS.includes(key))
        || p.title == null
        || typeof p.fontColor !== "string";
      if (invalid) {
        throw new Error("CardHeader 需要 title/fontColor，只接受可选 icon/fillColor。");
      }
      const children = [`${id}_title`];
      add(children[0], "Text", {
        content: p.title,
        layoutWeight: 1,
        fontSize: 12,
        fontWeight: 400,
        fontColor: p.fontColor,
        textAlign: "start",
        maxLines: 1,
        flexShrink: 0,
      });
      if (p.icon) {
        children.push(`${id}_icon`);
        add(`${id}_icon`, "Image", {
          src: p.icon,
          width: 20,
          height: 20,
          objectFit: "contain",
          flexShrink: 0,
          ...(p.fillColor ? { fillColor: p.fillColor } : {}),
        });
      }
      nodes.set(id, {
        type: "Row",
        props: {
          width: "matchParent",
          height: 20,
          ...([...input.values()].some(item => item.type === "Row" && item.children.includes(id))
            && p.width === undefined ? { layoutWeight: 1 } : {}),
          itemMargin: p.icon ? 8 : 0,
          flexShrink: 0,
          justifyContent: "start",
          alignItems: "center",
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
    } else {
      if (!["capsule", "icon-round"].includes(String(p.state))) {
        throw new Error("ActionUnit.state 只支持 capsule 或 icon-round。");
      }
      if (!Array.isArray(p.onClick) || p.onClick.length === 0) {
        throw new Error("ActionUnit 需要 onClick 动作。");
      }
      if (p.state === "capsule" && p.label == null) throw new Error("capsule 需要 label。");
      if (p.state === "icon-round" && (!p.icon || p.label !== undefined)) {
        throw new Error("icon-round 需要 icon，且不接受 label。");
      }
      const surface = p.actionSurface ?? "#1A1F4799";
      const ink = p.actionInk ?? "#FF1F4799";
      const base = {
        width: p.width ?? (p.state === "capsule" ? "matchParent" : 30),
        height: p.height ?? (p.state === "capsule" ? 36 : 30),
        borderRadius: p.borderRadius ?? (p.state === "capsule" ? 20 : 15),
        padding: p.padding ?? 0,
        flexShrink: p.flexShrink ?? 0,
        ...Object.fromEntries(PLACEMENT_PROPS.filter(key => key in p).map(key => [key, p[key]])),
        backgroundColor: surface,
        onClick: p.onClick,
        accessibility: p.accessibility,
      };
      if (p.state === "capsule" && !p.icon) {
        nodes.set(id, {
          type: "Button",
          props: {
            ...base,
            label: p.label,
            enabled: p.enabled ?? true,
            fontColor: ink,
            fontSize: p.fontSize ?? 14,
            fontWeight: p.fontWeight ?? 400,
          },
          children: [],
        });
      } else {
        const iconId = `${id}_icon`;
        const children = [iconId];
        add(iconId, "Image", {
          src: p.icon,
          width: 20,
          height: 20,
          objectFit: "contain",
          flexShrink: 0,
          fillColor: fusion ? "#99FFFFFF" : ink,
        });
        if (p.state === "capsule") {
          children.push(`${id}_text`);
          add(`${id}_text`, "Text", {
            content: p.label,
            fontSize: p.fontSize ?? 14,
            fontWeight: p.fontWeight ?? 400,
            fontColor: ink,
            maxLines: 1,
          });
        }
        nodes.set(id, {
          type: "Row",
          props: {
            ...base,
            enabled: p.enabled ?? true,
            justifyContent: "center",
            alignItems: "center",
            itemMargin: 8,
          },
          children,
        });
      }
    }
  }

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
