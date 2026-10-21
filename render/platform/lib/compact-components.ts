import visualRecipes from "../../../widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/runtime/visual-recipes-v1.json";
import { adaptCompactRegions } from "./compact-region-layout";
import { compactReferenceWidths } from "../../shared/compact-region-layout";
import { resolvePathBindingsInValue } from "@genui-sdk/interactions";

/** Expansion contracts from the shared Fusion Compact component runtime. */
export type MiniNode = { type: string; props: Record<string, unknown>; children: string[] };
export type CardSize = "2x2" | "2x4";
export type ExpansionDataContext = {
  get: (path: string) => unknown;
  setDerived: (path: string, value: unknown) => void;
  previewMode?: boolean;
  warn?: (message: string) => void;
};
type RecordValue = Record<string, unknown>;
type RecipePart = { component: string; styles: RecordValue };
type Recipe = {
  parts: Record<string, RecipePart>;
  metrics?: RecordValue;
  sizes?: Record<string, Partial<Recipe>>;
  variants?: Record<string, Partial<Recipe>>;
};
type PaletteContract = {
  backgrounds: string[];
  gradients: string[][];
  roles: Record<string, string>;
};

const PLACEMENT_PROPS = ["width", "height", "layoutWeight", "flexShrink", "margin"];
const EMPHASIS_TEXT_MULTI_VALUE_SEPARATOR = " | ";
const SYSTEM_FONT_ROLE_BY_COMPONENT: Record<string, string> = {
  SingleLineTitle: "secondary",
  DoubleLineTitle: "primary",
  Badge: "primary",
  EmphasizedData: "primary",
  EmphasisText: "primary",
  SecondaryBody: "primary",
  DataDisplay: "primary",
  InfoBlock: "primary",
  TableText: "primary",
  SummaryList: "primary",
  ProgressCircle: "primary",
  ProgressLine2: "primary",
  ProgressCircleSingle: "primary",
  H_BarChart: "primary",
  NumericRatioStack: "secondary",
  EventCard: "primary",
  TopTextBottomValue: "primary",
  TextBlock: "primary",
  CardButton: "primary",
};

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

function systemPalette(rootProps: RecordValue): Record<string, string> {
  const palettes = visualRecipes.palettes as unknown as Record<string, PaletteContract>;
  const design = rootProps.design;
  if (typeof design === "string" && Object.hasOwn(FUSION_PALETTES, design)) {
    return clone(palettes.fusionDark.roles);
  }
  const gradient = record(rootProps.linearGradient) ? rootProps.linearGradient.colors : undefined;
  const gradientColors = Array.isArray(gradient)
    ? gradient.flatMap(stop => Array.isArray(stop) && isArgbColor(stop[0])
      ? [String(stop[0]).toUpperCase()]
      : [])
    : [];
  const background = isArgbColor(rootProps.backgroundColor)
    ? String(rootProps.backgroundColor).toUpperCase()
    : undefined;
  const surfaceColors = gradientColors.length ? gradientColors : (background ? [background] : []);
  for (const name of ["blue", "purple", "warm"]) {
    const palette = palettes[name];
    const matchesBackground = surfaceColors.length === 1
      && palette.backgrounds.map(color => color.toUpperCase()).includes(surfaceColors[0]);
    const matchesGradient = gradientColors.length > 0
      && palette.gradients.some(colors => colors.length === gradientColors.length
        && colors.every((color, index) => color.toUpperCase() === gradientColors[index]));
    if (matchesBackground || matchesGradient) return clone(palette.roles);
  }
  if (!surfaceColors.length) return clone(palettes.blue.roles);
  const dark = [26, 26, 26] as const;
  const light = [255, 255, 255] as const;
  const backgrounds = surfaceColors.map(color => compositedRgb(color));
  const darkContrast = Math.min(...backgrounds.map(color => contrastRatio(dark, color)));
  const lightContrast = Math.min(...backgrounds.map(color => contrastRatio(light, color)));
  return clone((lightContrast > darkContrast ? palettes.neutralDark : palettes.neutralLight).roles);
}

function applySystemComponentColors(input: Map<string, MiniNode>): Map<string, MiniNode> {
  const palette = systemPalette(input.get("root")?.props ?? {});
  return new Map([...input].map(([id, node]) => {
    const role = SYSTEM_FONT_ROLE_BY_COMPONENT[node.type];
    if (!role || node.props.fontColor !== undefined) return [id, node];
    const color = palette[role];
    if (!isArgbColor(color)) throw new Error(`系统色板角色 ${role} 必须使用 #AARRGGBB。`);
    return [id, { ...node, props: { ...clone(node.props), fontColor: color } }];
  }));
}

function isArgbColor(value: unknown): value is string {
  return typeof value === "string" && /^#[\da-f]{8}$/i.test(value);
}

function compositedRgb(color: string): [number, number, number] {
  const alpha = Number.parseInt(color.slice(1, 3), 16) / 255;
  return [3, 5, 7].map(index => {
    const channel = Number.parseInt(color.slice(index, index + 2), 16);
    return Math.round(channel * alpha + 255 * (1 - alpha));
  }) as [number, number, number];
}

function contrastRatio(
  foreground: readonly [number, number, number],
  background: readonly [number, number, number],
) {
  const lighter = Math.max(relativeLuminance(foreground), relativeLuminance(background));
  const darker = Math.min(relativeLuminance(foreground), relativeLuminance(background));
  return (lighter + 0.05) / (darker + 0.05);
}

function relativeLuminance(color: readonly [number, number, number]) {
  const channels = color.map(value => {
    const normalized = value / 255;
    return normalized <= 0.04045
      ? normalized / 12.92
      : ((normalized + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * channels[0] + 0.7152 * channels[1] + 0.0722 * channels[2];
}

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

function requireRecipeFontSize(
  id: string,
  type: string,
  props: RecordValue,
  size: CardSize,
  part: string,
  variant?: string,
) {
  if (props.fontSize === undefined) return;
  const expected = visualRecipePart(type, part, size, variant).styles.fontSize;
  if (typeof props.fontSize !== "number"
    || !Number.isFinite(props.fontSize)
    || props.fontSize !== expected) {
    throw new Error(`${id}: ${type}.fontSize 必须使用固定 Recipe 值 ${String(expected)}。`);
  }
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

function dataDisplayValueKind(
  value: unknown,
  data?: ExpansionDataContext,
): { kind?: "numeric" | "text"; text?: string } {
  if (record(value) && Object.keys(value).length === 1 && typeof value.path === "string") {
    value = data?.get(value.path);
  }
  if (typeof value === "number" && Number.isFinite(value)) return { kind: "numeric" };
  if (typeof value !== "string" || !value.trim() || value.trim().startsWith("{{")) return {};
  const normalized = value.trim();
  if (/^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[%％])?$/.test(normalized)) {
    return { kind: "numeric" };
  }
  return { kind: "text", text: normalized };
}

function dataDisplayVariant(
  id: string,
  props: RecordValue,
  data?: ExpansionDataContext,
): string | undefined {
  const { kind, text } = dataDisplayValueKind(props.value, data);
  const fontSize = props.fontSize;
  if (kind === "numeric" && fontSize === 24) {
    throw new Error(`${id}: 数值 DataDisplay.value 必须使用 48fp。`);
  }
  if (kind === "text" && fontSize !== undefined && fontSize !== 24) {
    throw new Error(`${id}: 文本 DataDisplay.value 必须使用 24fp。`);
  }
  if (text !== undefined) {
    const characterCount = [...text.replace(/\s+/g, "")].length;
    if (characterCount < 4 || characterCount > 8) {
      throw new Error(`${id}: 文本 DataDisplay.value 必须为 4–8 个字符。`);
    }
  }
  return fontSize === 24 || (fontSize === undefined && kind === "text")
    ? "textConclusion"
    : undefined;
}

function emphasisSecondaryContent(id: string, value: unknown): unknown {
  if (!Array.isArray(value)) {
    if (!isDisplayValue(value)) throw new Error(`${id}: EmphasisText.secondaryText 必须是可显示文本。`);
    return value;
  }
  if (value.length < 2) {
    throw new Error(`${id}: EmphasisText.secondaryText 数组至少需要两个有序 PathBinding。`);
  }
  const paths = value.map((item, index) => {
    if (!record(item) || Object.keys(item).length !== 1 || typeof item.path !== "string"
      || !item.path.startsWith("/")) {
      throw new Error(`${id}: EmphasisText.secondaryText[${index}] 必须是 PathBinding。`);
    }
    return item.path;
  });
  const body = paths.map(path => `\${${path}}`).join(
    ` + '${EMPHASIS_TEXT_MULTI_VALUE_SEPARATOR}' + `,
  );
  return `{{ ${body} }}`;
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
  try {
    return normalizedProgressValue(id, type, prop, value, total);
  } catch (error) {
    if (!data?.previewMode) throw error;
    const paths = typeof value === "string"
      ? [...value.matchAll(/\$\{(\/[^{}]+)\}/g)].map(match => match[1])
      : [];
    const resolved = paths.reduce(
      (text, path) => text.replaceAll("${" + path + "}", String(data.get(path) ?? "")),
      String(value),
    );
    const numeric = resolved.match(/[+-]?(?:\d+(?:\.\d*)?|\.\d+)/);
    const candidate = numeric ? Number(numeric[0]) : 0;
    const fallback = Number.isFinite(candidate)
      ? Math.min(total, Math.max(0, candidate))
      : 0;
    const detail = error instanceof Error ? error.message : String(error);
    data.warn?.(`${detail} 宽松预览已使用 ${fallback} 作为进度值。`);
    return fallback;
  }
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
  if (completeExpression(value)) return progressCircleExpressionValues(value);
  const numeric = normalizedProgressValue(id, "ProgressCircle", "externalText", value, 100);
  return typeof value === "string" ? [numeric, value.trim()] : [numeric, `${numeric}%`];
}

function completeExpression(value: unknown): value is string {
  if (typeof value !== "string") return false;
  const stripped = value.trim();
  return stripped.startsWith("{{")
    && stripped.endsWith("}}")
    && stripped.slice(2, -2).trim().length > 0;
}

function progressCircleExpressionValues(value: string): [string, string] {
  const stripped = value.trim();
  const body = stripped.slice(2, -2).trim();
  const percentage = body.match(/^([\s\S]+?)\s*\+\s*(['"])[%％]\2\s*$/);
  if (percentage) return [`{{ ${percentage[1].trim()} }}`, stripped];
  return [stripped, `{{ (${body}) + '%' }}`];
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

function secondaryTextWidth(text: string, font: number) {
  return [...text].reduce((width, character) => width + font * (character.codePointAt(0)! < 128 ? 0.6 : 1), 0);
}

function secondaryDisplayText(item: RecordValue, data?: ExpansionDataContext): string | undefined {
  const value = item.value;
  if (typeof value === "string" && !value.includes("{{")) return String(item.label ?? "") + value;
  if (!data) return undefined;
  if (typeof value === "string") {
    const references = [...value.matchAll(/\$\{(\/[^{}]+)\}/g)];
    if (references.length !== 1 || data.get(references[0][1]) === undefined) return undefined;
    const body = value.replace(/^\s*\{\{/, "").replace(/\}\}\s*$/, "");
    const literal = '(?:"(?:[^"\\\\]|\\\\.)*"|\'(?:[^\'\\\\]|\\\\.)*\')';
    const conditional = body.match(new RegExp(
      '^\\s*\\$\\{(/[^{}]+)\\}\\s*(?:(==|!=)\\s*-?\\d+(?:\\.\\d+)?\\s*)?\\?\\s*('
      + literal + ')\\s*:\\s*(' + literal + ')\\s*$',
    ));
    if (conditional) {
      const actual = data.get(conditional[1]);
      if (conditional[2] ? typeof actual !== "number" : typeof actual !== "boolean") return undefined;
      const branches = [conditional[3], conditional[4]].map(branch =>
        resolvePathBindingsInValue("{{ " + branch + " }}", data.get));
      if (!branches.every(branch => typeof branch === "string")) return undefined;
      branches.sort((left, right) => secondaryTextWidth(String(right), 1) - secondaryTextWidth(String(left), 1));
      return String(item.label ?? "") + String(branches[0]);
    }
    const tokens = /\$\{\/[^{}]+\}|"(?:[^"\\]|\\.)*"|'(?:[^'\\]|\\.)*'/g;
    if (!/^\s*(?:\+\s*)*$/.test(body.replace(tokens, ""))) return undefined;
  }
  const result = resolvePathBindingsInValue(value, data.get);
  if (typeof result !== "string" && typeof result !== "number") return undefined;
  return String(item.label ?? "") + String(result);
}

function secondaryBodyLayout(
  items: RecordValue[], texts: Array<string | undefined>, columns: number,
  separator: string, width?: number,
) {
  const rowSizes: number[] = [];
  const maxLines = items.map(item => Number(item.maxLines ?? 1));
  let multiline = items.length > columns || maxLines.includes(2);
  for (let index = 0; index < items.length;) {
    let rowSize = Math.min(columns, items.length - index);
    const text = texts[index];
    if (width !== undefined && text !== undefined) {
      if (text.includes("\n") || secondaryTextWidth(text, 14) > width) {
        multiline = true;
        rowSize = 1;
      }
      const next = texts[index + 1];
      if (rowSize === 2 && next !== undefined && secondaryTextWidth(text + separator + next, 14) > width) {
        rowSize = 1;
        multiline = true;
      }
    }
    rowSizes.push(rowSize);
    index += rowSize;
  }
  multiline ||= rowSizes.length > 1;
  if (multiline && width !== undefined) {
    texts.forEach((text, index) => {
      if (text === undefined) return;
      const required = secondaryTextWidth(text, 12);
      if (text.includes("\n") || (width < required && required <= width * 2)) maxLines[index] = 2;
    });
  }
  return { rowSizes, maxLines, multiline };
}

function secondaryPrefixedValue(label: string, value: unknown) {
  const escaped = label.replaceAll("\\", "\\\\").replaceAll("'", "\\'")
    .replaceAll("\n", "\\n").replaceAll("\r", "\\r");
  if (record(value)) return "{{ '" + escaped + "' + ${" + value.path + "} }}";
  if (typeof value === "string" && value.trim().startsWith("{{")) {
    return "{{ '" + escaped + "' + (" + value.trim().slice(2, -2).trim() + ") }}";
  }
  return label + String(value);
}

function previewDisplayValues(props: RecordValue): unknown[] {
  const values: unknown[] = [];
  const append = (value: unknown) => {
    if (isDisplayValue(value)) values.push(value);
  };
  for (const name of [
    "title", "mainText", "secondaryText", "value", "displayValue", "primaryText",
    "secondaryInfo", "secondaryLabel", "label", "supportingText",
  ]) {
    append(props[name]);
  }
  if (Array.isArray(props.items)) {
    for (const item of props.items) {
      if (isDisplayValue(item)) {
        append(item);
        continue;
      }
      if (!record(item)) continue;
      for (const name of ["title", "label", "value", "time", "location", "unit"]) {
        append(item[name]);
      }
    }
  }
  return values;
}

function previewHighLevelFallback(
  id: string,
  node: MiniNode,
  palette: Record<string, string>,
): Array<[string, MiniNode]> {
  const actionTypes = new Set(["PillButton", "CircleButton", "CardButton"]);
  const placement = Object.fromEntries(
    PLACEMENT_PROPS.filter(key => key in node.props).map(key => [key, clone(node.props[key])]),
  );
  const values = previewDisplayValues(node.props);
  if (actionTypes.has(node.type)) {
    return [[id, {
      type: "Button",
      props: {
        label: values[0] ?? "操作",
        width: "matchParent",
        height: 36,
        borderRadius: 18,
        backgroundColor: palette.actionSurface,
        fontColor: palette.actionInk,
        ...placement,
        ...(node.props.onClick === undefined ? {} : { onClick: clone(node.props.onClick) }),
      },
      children: [],
    }]];
  }

  const children = (values.length ? values : [`无法完整预览 ${node.type}`])
    .map((_, index) => `${id}_preview_text${index}`);
  const rows: Array<[string, MiniNode]> = [[id, {
    type: "Column",
    props: {
      width: "matchParent",
      itemMargin: 2,
      alignItems: "start",
      justifyContent: "start",
      ...placement,
    },
    children,
  }]];
  children.forEach((child, index) => {
    rows.push([child, {
      type: "Text",
      props: {
        content: values[index] ?? `无法完整预览 ${node.type}`,
        width: "matchParent",
        fontSize: index === 0 ? 14 : 12,
        fontWeight: index === 0 ? 500 : 400,
        fontColor: palette.primary,
        maxLines: 2,
      },
      children: [],
    }]);
  });
  return rows;
}

function expandHighLevel(
  id: string,
  node: MiniNode,
  size: CardSize,
  palette: Record<string, string>,
  data?: ExpansionDataContext,
  availableWidth?: number,
): Array<[string, MiniNode]> | null {
  const p = node.props;
  const type = node.type;
  if (!(HIGH_LEVEL_COMPONENT_TYPES as readonly string[]).includes(type)) return null;
  requireNoChildren(id, type, node.children);

  if (type === "DoubleLineTitle") {
    const allowed = ["title", "secondaryInfo", "fontColor", "fontSize"];
    requireProps(id, type, p, ["title", "secondaryInfo", "fontColor"], allowed);
    requireRecipeFontSize(id, type, p, size, "title");
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
    const allowed = ["mainText", "secondaryText", "fontColor", "fontSize"];
    requireProps(id, type, p, ["mainText", "fontColor"], allowed);
    requireRecipeFontSize(id, type, p, size, "main");
    requireDisplay(id, type, p, "mainText");
    const secondaryContent = p.secondaryText === undefined
      ? undefined
      : emphasisSecondaryContent(id, p.secondaryText);
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
        content: secondaryContent,
        fontColor: colorWithAlpha(p.fontColor as string, 0.6),
      }));
    }
    return [row(id, type, "root", size, {}, children), ...rows];
  }

  if (type === "SecondaryBody") {
    const allowed = ["items", "role", "columns", "separator", "fontColor", "fontSize"];
    requireProps(id, type, p, ["items", "fontColor"], allowed);
    requireColor(id, type, p, "fontColor");
    if (!Array.isArray(p.items) || p.items.length < 1 || p.items.length > 6) {
      const countDetail = Array.isArray(p.items) ? `，实际 ${p.items.length} 项` : "";
      throw new Error(`${id}: SecondaryBody.items 需要 1–6 项${countDetail}。`);
    }
    // 历史 role 输入忽略；样式仅由行布局决定。
    const items = p.items.map((item, index) => {
      if (!record(item) || !("value" in item) || !isDisplayValue(item.value)
        || Object.keys(item).some(key => !["label", "value", "maxLines"].includes(key))
        || (item.label !== undefined && (typeof item.label !== "string" || !item.label.trim()))) {
        throw new Error(`${id}: SecondaryBody.items[${index}] 只接受有效的 label/value/maxLines。`);
      }
      const maxLines = item.maxLines ?? 1;
      if (!Number.isInteger(maxLines) || ![1, 2].includes(maxLines as number)) {
        throw new Error(`${id}: SecondaryBody.items[${index}].maxLines 只接受 1 或 2。`);
      }
      return item;
    });
    const separator = p.separator ?? " | ";
    const columns = p.columns ?? 2;
    if (!Number.isInteger(columns) || ![1, 2].includes(columns as number)) {
      throw new Error(`${id}: SecondaryBody.columns 只接受 1 或 2。`);
    }
    if (typeof separator !== "string" || !separator) {
      throw new Error(`${id}: SecondaryBody.separator 必须是非空文本。`);
    }
    const multiline = items.length > Number(columns)
      || items.some(item => item.maxLines === 2);
    let variant = multiline ? "multiline" : undefined;
    requireRecipeFontSize(id, type, p, size, "text", variant);
    const texts = items.map(item => secondaryDisplayText(item, data));
    const layout = secondaryBodyLayout(items, texts, Number(columns), separator, availableWidth);
    variant = layout.multiline ? "multiline" : undefined;
    const textStyles = recipe(type, size, variant).parts.text.styles;
    const lineHeight = Number(textStyles.height) / Number(textStyles.maxLines ?? 1);
    const rootChildren: string[] = [];
    const rows: Array<[string, MiniNode]> = [];
    let start = 0;
    for (let rowIndex = 0; rowIndex < layout.rowSizes.length; rowIndex++) {
      const rowSize = layout.rowSizes[rowIndex];
      const rowId = `${id}_row${rowIndex}`;
      rootChildren.push(rowId);
      const rowChildren: string[] = [];
      const rowItems = items.slice(start, start + rowSize);
      const naturalRow = availableWidth !== undefined
        && texts.slice(start, start + rowSize).every(text => text !== undefined);
      const rowHeight = lineHeight * Math.max(...layout.maxLines.slice(start, start + rowSize));
      rowItems.forEach((item, localIndex) => {
        const maxLines = layout.maxLines[start + localIndex];
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
        const prefixValue = maxLines > Number(item.maxLines ?? 1) && typeof item.label === "string";
        if (item.label !== undefined && !prefixValue) {
          const labelId = `${itemId}_label`;
          itemChildren.push(labelId);
          rows.push(row(labelId, type, "text", size, {
            content: item.label,
            fontColor: colorWithAlpha(p.fontColor as string, 0.6),
            flexShrink: 0,
          }, [], variant));
        }
        const valueId = `${itemId}_value`;
        itemChildren.push(valueId);
        rows.push(row(valueId, type, "text", size, {
          content: prefixValue ? secondaryPrefixedValue(String(item.label), item.value) : item.value,
          fontColor: item.label !== undefined
            ? p.fontColor : colorWithAlpha(p.fontColor as string, 0.6),
          height: itemHeight, maxLines, layoutWeight: 1,
        }, [], variant));
        const itemLayout: RecordValue = { layoutWeight: 1, height: itemHeight, alignItems: "start" };
        const text = texts[itemIndex];
        if (rowSize === 2 && naturalRow && text !== undefined) {
          delete itemLayout.layoutWeight;
          itemLayout.width = secondaryTextWidth(text, layout.multiline ? 12 : 14);
        }
        rows.push(row(itemId, type, "item", size, itemLayout, itemChildren, variant));
      });
      rows.push(row(rowId, type, "row", size, {
        height: rowHeight, alignItems: "start",
      }, rowChildren, variant));
      start += rowSize;
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
        row(labelId, type, "label", size, {
          content: item.label, fontColor: colorWithAlpha(String(p.fontColor), 0.6),
        }, [], variant),
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
    if (p.width !== undefined) throw new Error(`${id}: PillButton 不接受 width。`);
    const allowed = ["label", "icon", "onClick"];
    requireProps(id, type, p, ["label", "onClick"], allowed);
    if (typeof p.label !== "string" || !p.label.trim()) {
      throw new Error(`${id}: PillButton.label 必须是非空文本。`);
    }
    requireOptionalIcon(id, type, p);
    requireAction(id, type, p.onClick);
    const visual = visualRecipePart(type, "root", size);
    const base = {
      ...visual.styles,
      backgroundColor: palette.componentSecondary,
      onClick: p.onClick,
    };
    if (!p.icon) {
      return [[id, {
        type: "Button",
        props: {
          ...base,
          label: p.label,
          enabled: true,
          fontColor: palette.primary,
          fontSize: visual.styles.fontSize ?? 14,
          fontWeight: visual.styles.fontWeight ?? 500,
          textAlign: "center",
        },
        children: [],
      }]];
    }
    const iconId = `${id}_icon`;
    const textId = `${id}_text`;
    const iconVisual = visualRecipePart(type, "icon", size);
    const labelVisual = visualRecipePart(type, "label", size);
    return [
      [id, {
        type: "Row",
        props: { ...base, itemMargin: 8, justifyContent: "center", alignItems: "center" },
        children: [iconId, textId],
      }],
      [iconId, {
        type: iconVisual.component,
        props: {
          ...iconVisual.styles,
          src: p.icon,
          fillColor: palette.primary,
        },
        children: [],
      }],
      [textId, {
        type: labelVisual.component,
        props: {
          ...labelVisual.styles,
          content: p.label,
          fontSize: visual.styles.fontSize ?? 14,
          fontWeight: visual.styles.fontWeight ?? 500,
          fontColor: palette.primary,
        },
        children: [],
      }],
    ];
  }

  if (type === "CircleButton") {
    if (size !== "2x2") throw new Error("CircleButton 仅支持 2x2 卡片。");
    const allowed = ["icon", "accessibility", "onClick"];
    requireProps(id, type, p, allowed, allowed);
    requireOptionalIcon(id, type, p);
    requireAction(id, type, p.onClick);
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
          backgroundColor: palette.componentSecondary,
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
          fillColor: palette.primary,
        },
        children: [],
      }],
    ];
  }

  if (type === "EmphasizedData") {
    requireProps(
      id,
      type,
      p,
      ["value", "fontColor"],
      ["value", "unit", "fontColor", "fontSize"],
    );
    requireRecipeFontSize(id, type, p, size, "value");
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
    const required = ["items", "fontColor"];
    const allowed = isTable ? [...required, "fontSize"] : required;
    requireProps(id, type, p, required, allowed);
    requireColor(id, type, p, "fontColor");
    const items = labelValueItems(id, type, p.items, 2, isTable ? 3 : 4);
    const variant = isTable && items.length === 3 ? "compact" : undefined;
    if (isTable) requireRecipeFontSize(id, type, p, size, "value", variant);
    const children: string[] = [];
    const rows: Array<[string, MiniNode]> = [];
    items.forEach((item, index) => {
      const itemId = `${id}_${isTable ? "row" : "item"}${index}`;
      const labelId = `${itemId}_label`;
      const valueId = `${itemId}_value`;
      const labelSlotId = `${itemId}_label_slot`;
      const valueSlotId = `${itemId}_value_slot`;
      const itemChildren = isTable ? [labelId, valueId] : [labelSlotId, valueSlotId];
      children.push(itemId);
      rows.push(row(
        itemId,
        type,
        isTable ? "row" : "item",
        size,
        {},
        itemChildren,
        variant,
      ));
      if (!isTable) {
        rows.push(row(labelSlotId, type, "labelSlot", size, {}, [labelId], variant));
      }
      rows.push(row(
        labelId,
        type,
        "label",
        size,
        {
          content: item.label,
          fontColor: colorWithAlpha(String(p.fontColor), 0.6),
        },
        [],
        variant,
      ));
      if (!isTable) {
        rows.push(row(valueSlotId, type, "valueSlot", size, {}, [valueId], variant));
      }
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
      "label", "labelLines", "onClick", "fontColor", "icon", "fillColor",
    ];
    requireProps(id, type, p, ["label", "onClick", "fontColor"], allowed);
    requireDisplay(id, type, p, "label");
    requireColor(id, type, p, "fontColor");
    requireOptionalIcon(id, type, p);
    requireAction(id, type, p.onClick);
    const labelLines = p.labelLines === undefined ? 1 : p.labelLines;
    if (!Number.isInteger(labelLines) || ![1, 2].includes(labelLines as number)) {
      throw new Error(`${id}: CardButton.labelLines 只接受 1 或 2。`);
    }
    const variant = labelLines === 2 ? "multilineLabel" : undefined;
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
        { onClick: p.onClick },
        [label, visual],
      ),
      row(label, type, "label", size, { content: p.label, fontColor: p.fontColor }, [], variant),
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
      row(label, type, "label", size, {
        content: p.label, fontColor: colorWithAlpha(String(p.fontColor), 0.6),
      }, [], variant),
      row(
        display,
        type,
        "display",
        size,
        {
          content: p.displayValue,
          fontColor: p.fontColor,
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
    if (items.length < 1) {
      throw new Error(`${id}: EventCard.items 至少需要 1 项。`);
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
    let itemMargin = 8;
    items.forEach((item, index) => {
      const itemId = items.length === 1 ? id : `${id}_item${index}`;
      const variant = compact ? "compact" : (item.location === undefined ? "withoutLocation" : "withLocation");
      const metrics = recipe(type, size, variant).metrics!;
      if (compact) itemMargin = Number(metrics.itemMargin);
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
        if (item.location !== undefined) {
          for (const [nodeId, node] of rows) {
            if (nodeId !== time && nodeId !== location) continue;
            delete node.props.width;
            if (nodeId === location) node.props.layoutWeight = 1;
          }
        }
      } else if (item.location !== undefined) {
        rows.push(row(location, type, "meta", size, {
          content: item.location, fontColor: secondaryColor,
        }, [], variant));
      }
    });
    if (items.length === 1) return rows;
    totalHeight += itemMargin * (items.length - 1);
    return [row(
      id,
      type,
      "multiRoot",
      size,
      { height: totalHeight, itemMargin },
      itemIds,
    ), ...rows];
  }

  if (type === "DataDisplay") {
    if (size !== "2x2") throw new Error("DataDisplay 仅支持 2x2 卡片。");
    const allowed = [
      "label", "icon", "fillColor", "value", "supportingText", "fontColor", "fontSize",
    ];
    requireProps(id, type, p, ["value", "supportingText", "fontColor"], allowed);
    const variant = dataDisplayVariant(id, p, data);
    requireRecipeFontSize(id, type, p, size, "value", variant);
    const label = typeof p.label === "string" && p.label.trim() ? p.label : undefined;
    const icon = typeof p.icon === "string" && p.icon.trim() ? p.icon : undefined;
    if (p.label !== undefined && label === undefined) {
      throw new Error(`${id}: DataDisplay.label 必须是非空静态文本。`);
    }
    if (p.icon !== undefined && icon === undefined) {
      throw new Error(`${id}: DataDisplay.icon 必须是非空静态路径。`);
    }
    if ((label === undefined) === (icon === undefined)) {
      throw new Error(`${id}: DataDisplay 必须在 label 和 icon 中二选一。`);
    }
    if (variant === undefined && label === undefined) {
      throw new Error(`${id}: 数值 DataDisplay 必须使用文本 label。`);
    }
    if (p.fillColor !== undefined) {
      if (icon === undefined) throw new Error(`${id}: DataDisplay.fillColor 需要 icon。`);
      requireColor(id, type, p, "fillColor");
      if (/\.(?:png|jpe?g|webp|gif|bmp)$/i.test(icon)) {
        throw new Error(`${id}: DataDisplay 位图 icon 不能设置 fillColor。`);
      }
    }
    requireDisplay(id, type, p, "value");
    requireDisplay(id, type, p, "supportingText");
    requireColor(id, type, p, "fontColor");
    const secondaryColor = colorWithAlpha(String(p.fontColor), 0.6);
    const labelId = `${id}_label`;
    const iconId = `${id}_icon`;
    const valueAreaId = `${id}_value_area`;
    const valueId = `${id}_value`;
    const supportingId = `${id}_supporting`;
    const leadingId = label === undefined ? iconId : labelId;
    const valueChildId = variant === "textConclusion" ? valueAreaId : valueId;
    const valueRow = row(
      valueId,
      type,
      "value",
      size,
      { content: p.value, fontColor: p.fontColor },
      [],
      variant,
    );
    if (variant === "textConclusion") delete valueRow[1].props.height;
    const rows: Array<[string, MiniNode]> = [
      row(id, type, "root", size, {}, [leadingId, valueChildId, supportingId], variant),
      valueRow,
      row(
        supportingId,
        type,
        "supporting",
        size,
        { content: p.supportingText, fontColor: secondaryColor },
        [],
        variant,
      ),
    ];
    if (variant === "textConclusion") {
      rows.splice(1, 0, row(
        valueAreaId,
        type,
        "valueArea",
        size,
        {},
        [valueId],
        variant,
      ));
    }
    if (label !== undefined) {
      rows.splice(1, 0, row(
        labelId,
        type,
        "label",
        size,
        { content: label, fontColor: secondaryColor },
        [],
        variant,
      ));
    } else {
      rows.splice(1, 0, row(
        iconId,
        type,
        "icon",
        size,
        { src: icon, ...(p.fillColor === undefined ? {} : { fillColor: p.fillColor }) },
        [],
        variant,
      ));
    }
    return rows;
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
        { content: item.label, fontColor: colorWithAlpha(String(p.fontColor), 0.6) },
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
    requireProps(id, type, p, ["items", "fontColor"], allowed);
    requireColor(id, type, p, "fontColor");
    if (p.backgroundColor !== undefined) requireColor(id, type, p, "backgroundColor");
    if (!Array.isArray(p.items)
      || p.items.length < 2
      || p.items.length > 3
      || !p.items.every(isDisplayValue)) {
      throw new Error(`${id}: SummaryList.items 需要 2–3 项可显示文本。`);
    }
    const children = p.items.map((_, index) => `${id}_item${index}`);
    const minimumHeight = p.items.length === 2 ? 64 : 102;
    const rows: Array<[string, MiniNode]> = [row(
      id,
      type,
      "root",
      size,
      { constraintSize: { minHeight: minimumHeight } },
      children,
    )];
    p.items.forEach((item, index) => {
      const text = `${children[index]}_text`;
      rows.push(row(
        children[index],
        type,
        "item",
        size,
        p.backgroundColor === undefined ? {} : { backgroundColor: p.backgroundColor },
        [text],
      ));
      rows.push(row(
        text,
        type,
        "text",
        size,
        {
          content: item,
          fontColor: p.fontColor,
        },
      ));
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
  const palette = systemPalette(input.get("root")?.props ?? {});
  input = applySystemComponentColors(input);
  const widthNodes = new Map([...input].map(([id, node]) => [id, node.type === "SecondaryBody"
    ? { ...node, type: "Column", props: { width: "matchParent", ...node.props } } : node]));
  const secondaryWidths = compactReferenceWidths(widthNodes, size);
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
    let rows: Array<[string, MiniNode]> | null;
    try {
      rows = expandHighLevel(id, node, size, palette, data, secondaryWidths.get(id));
    } catch (error) {
      if (!data?.previewMode
        || !(HIGH_LEVEL_COMPONENT_TYPES as readonly string[]).includes(node.type)) {
        throw error;
      }
      const reason = error instanceof Error ? error.message : String(error);
      data.warn?.(`${id}: ${reason} 宽松预览已改用只读占位展开。`);
      rows = previewHighLevelFallback(id, node, palette);
    }
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
      if (size === "2x4" && ["InfoBlock", "CardButton"].includes(node.type)) {
        const slotRoot = visualRecipePart(node.type, "root", size).styles;
        props.height = slotRoot.height;
        props.flexShrink = slotRoot.flexShrink;
        if (parent?.type === "Column") delete props.layoutWeight;
      }
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
      const allowed = ["title", "icon", "fillColor", "fontColor", "fontSize"];
      const icon = typeof p.icon === "string" && p.icon.trim() ? p.icon : undefined;
      const variant = icon ? "withIcon" : undefined;
      const rootVisual = visualRecipePart("SingleLineTitle", "root", size, variant);
      const expectedHeight = rootVisual.styles.height;
      const invalid = Object.keys(p).some(key => !allowed.includes(key) && !PLACEMENT_PROPS.includes(key))
        || p.title == null
        || typeof p.fontColor !== "string"
        || (p.icon !== undefined && !icon)
        || (p.fillColor !== undefined && (!icon || !isArgbColor(p.fillColor)))
        || (p.height !== undefined && p.height !== expectedHeight);
      if (invalid) {
        throw new Error(
          "SingleLineTitle 只接受 title、静态 icon、可选 fillColor 和合法布局属性；"
            + "文字色由运行时注入。",
        );
      }
      requireRecipeFontSize(id, node.type, p, size, "title", variant);
      const titleVisual = visualRecipePart("SingleLineTitle", "title", size, variant);
      const children = [`${id}_title`];
      add(children[0], "Text", {
        ...titleVisual.styles,
        content: p.title,
        fontColor: p.fontColor,
      });
      if (icon) {
        const iconId = `${id}_icon`;
        const iconVisual = visualRecipePart("SingleLineTitle", "icon", size, variant);
        children.push(iconId);
        add(iconId, iconVisual.component, {
          ...iconVisual.styles,
          src: icon,
          ...(p.fillColor === undefined ? {} : { fillColor: p.fillColor }),
        });
      }
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
