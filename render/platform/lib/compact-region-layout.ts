import referenceProfile from "../../../widget_service/cloud/data/protocol_profiles/design-compact-dsl/protocol.json";
import layoutContract from "../../../widget_service/cloud/data/protocol_profiles/design-compact-dsl-fusion/runtime/layout-contracts-v1.json";
import type { CardSize, MiniNode } from "./compact-components";

// 与云侧 compact_region_layout 保持同一闭合几何算法；不读取设备信息。
type Axis = "width" | "height";
type Box = Record<Axis, number | undefined>;
const regions = new Set(["Row", "Column", "InfoBlock", "CardButton"]);
const widthFill = new Set([...regions, "Text", "Button", "PillButton", "CardHeader"]);
const actions = new Set(["Button", "PillButton", "CircleButton", "ActionUnit"]);
const constraints = ["aspectRatio", "constraintSize", "minWidth", "maxWidth", "minHeight", "maxHeight", "borderWidth"];
const axes: Axis[] = ["width", "height"];
const number = (value: unknown): number | undefined =>
  typeof value === "number" && Number.isFinite(value) && value >= 0 ? value : undefined;
const mainAxis = (node: MiniNode): Axis | undefined =>
  node.type === "Row" ? "width" : node.type === "Column" ? "height" : undefined;
const gap = (node: MiniNode) => number(node.props.itemMargin ?? node.props.space ?? 0);
type Rule = {
  path: number[]; types?: string[]; props?: Record<string, unknown>;
  slotSize?: Partial<Record<Axis, number>>; eventPolicy?: string;
  childCount?: number; childCountMin?: number; childCountMax?: number;
};
type Layout = { size: string; patterns: Array<{rules: Rule[]}>; actionCount?: {min:number;max:number} };

function adaptiveSlots(authors: Map<string, MiniNode>, expanded: Map<string, MiniNode>, size: CardSize) {
  const clicked = (node: MiniNode) => Array.isArray(node.props.onClick) && node.props.onClick.length > 0;
  function subtreeEvent(id: string, seen = new Set<string>()): boolean {
    const node = authors.get(id);
    if (!node || seen.has(id)) return false;
    return clicked(node) || node.children.some(child => subtreeEvent(child, new Set([...seen, id])));
  }
  const actionCount = [...authors.values()].filter(clicked).length;
  for (const layout of Object.values(layoutContract.layouts) as Layout[]) {
    if (layout.size !== size) continue;
    if (layout.actionCount && (actionCount < layout.actionCount.min || actionCount > layout.actionCount.max)) continue;
    for (const pattern of layout.patterns) {
      const slots = new Set<string>();
      const matches = pattern.rules.every(rule => {
        let id: string | undefined = "root";
        for (const index of rule.path) id = id === undefined ? undefined : authors.get(id)?.children[index];
        if (id === undefined) return false;
        const node = authors.get(id), actual = expanded.get(id);
        if (!node || !actual || (rule.types && !rule.types.includes(node.type))) return false;
        if (Object.entries(rule.props ?? {}).some(([key, value]) => JSON.stringify(node.props[key]) !== JSON.stringify(value))) return false;
        const count = node.children.length;
        if (rule.childCount !== undefined && count !== rule.childCount) return false;
        if (rule.childCountMin !== undefined && count < rule.childCountMin) return false;
        if (rule.childCountMax !== undefined && count > rule.childCountMax) return false;
        if (rule.eventPolicy === "require" && !clicked(node)) return false;
        if (rule.eventPolicy === "forbid" && clicked(node)) return false;
        if (rule.eventPolicy === "forbid-subtree" && subtreeEvent(id)) return false;
        for (const axis of axes) {
          const expected = rule.slotSize?.[axis];
          if (expected === undefined) continue;
          let length = node.props[axis] ?? actual.props[axis];
          if (axis === "width" && length === "matchParent") length = expected;
          if (length !== expected) return false;
        }
        if (rule.slotSize) slots.add(id);
        return true;
      });
      if (matches) return slots;
    }
  }
  return new Set<string>();
}
function inset(node: MiniNode, name: string, axis: Axis): number | undefined {
  const value = node.props[name] ?? 0;
  if (typeof value !== "object" || value === null || Array.isArray(value)) {
    const scalar = number(value);
    return scalar === undefined ? undefined : scalar * 2;
  }
  const sides = axis === "width" ? ["left", "right"] : ["top", "bottom"];
  const [first, second] = sides.map(side => number((value as Record<string, unknown>)[side] ?? 0));
  return first === undefined || second === undefined ? undefined : first + second;
}

/** 只将参考画布中可证明闭合的区域改成相对布局；Recipe 内部保持原样。 */
export function adaptCompactRegions(
  input: Map<string, MiniNode>, authors: Map<string, MiniNode>, size: CardSize,
): Map<string, MiniNode> {
  const output = new Map<string, MiniNode>();
  for (const [id, node] of input) output.set(id, { ...node, props: { ...node.props } });
  const boxes = new Map<string, Box>();
  const slots = adaptiveSlots(authors, input, size);
  const slotActions = new Set([...slots].filter(id => {
    const author = authors.get(id);
    return author?.type === "CardButton" && !constraints.some(key => key in author.props);
  }));
  const children = (node: MiniNode) => node.children.filter(id => input.has(id));
  function intrinsic(id: string, axis: Axis, seen = new Set<string>()): number | undefined {
    const node = input.get(id)!;
    const explicit = number(node.props[axis]);
    if (explicit !== undefined || seen.has(id)) return explicit;
    if (axis in node.props) return undefined;
    if ((node.props.borderWidth ?? 0) !== 0) return undefined;
    const main = mainAxis(node), ids = children(node);
    if (main === undefined || !ids.length) return undefined;
    const nextSeen = new Set([...seen, id]);
    const lengths: number[] = [];
    for (const child of ids) {
      const length = intrinsic(child, axis, nextSeen), margin = inset(input.get(child)!, "margin", axis);
      if (length === undefined || margin === undefined) return undefined;
      lengths.push(length + margin);
    }
    const padding = inset(node, "padding", axis), spacing = gap(node);
    if (padding === undefined || spacing === undefined) return undefined;
    return padding + (main === axis
      ? lengths.reduce((sum, value) => sum + value, 0) + spacing * (lengths.length - 1)
      : Math.max(...lengths));
  }
  function inner(node: MiniNode, box: Box): Box {
    const result: Box = { width: undefined, height: undefined };
    if ((node.props.borderWidth ?? 0) !== 0) return result;
    for (const axis of axes) {
      const padding = inset(node, "padding", axis), extent = box[axis];
      if (padding !== undefined && extent !== undefined) result[axis] = Math.max(0, extent - padding);
    }
    return result;
  }
  function lengths(node: MiniNode, space: Box, axis: Axis): Array<number | undefined> {
    const ids = children(node), available = space[axis];
    const values = ids.map(id => input.get(id)!.props[axis] === "matchParent" ? available : intrinsic(id, axis));
    const weights = ids.map(id => number(input.get(id)!.props.layoutWeight) ?? 0);
    const totalWeight = weights.reduce((sum, value) => sum + value, 0);
    if (axis !== mainAxis(node) || totalWeight === 0) return values;
    const spacing = gap(node);
    let fixed = 0, known = available !== undefined && spacing !== undefined;
    ids.forEach((id, index) => {
      const margin = inset(input.get(id)!, "margin", axis), length = values[index];
      if (margin === undefined || (weights[index] === 0 && length === undefined)) known = false;
      else fixed += margin + (weights[index] === 0 ? length! : 0);
    });
    const remaining = known ? Math.max(0, available! - fixed - spacing! * Math.max(0, ids.length - 1)) : undefined;
    return values.map((value, index) => weights[index] === 0 ? value
      : remaining === undefined ? undefined : remaining * weights[index] / totalWeight);
  }
  function visit(id: string, box: Box, seen = new Set<string>()) {
    const node = input.get(id);
    if (!node || seen.has(id)) return;
    boxes.set(id, box);
    const space = inner(node, box), widths = lengths(node, space, "width"), heights = lengths(node, space, "height");
    children(node).forEach((child, index) => visit(child, {
      width: widths[index], height: heights[index],
    }, new Set([...seen, id])));
  }
  function fixedAction(id: string, seen = new Set<string>()): boolean {
    if (seen.has(id)) return true;
    const kind = authors.get(id)?.type, node = input.get(id)!;
    if (kind === "CardButton") return false;
    if (actions.has(kind ?? "") || node.props.onClick) return true;
    const ids = children(node);
    return ids.length === 1 && fixedAction(ids[0], new Set([...seen, id]));
  }
  const reference = referenceProfile.sizes[size];
  visit("root", { width: reference.width, height: reference.height });
  // 上层实际压缩会让下层参考盒失真；已知超占用时保留整卡原几何。
  for (const [id, box] of boxes) {
    const node = input.get(id)!, axis = mainAxis(node), spacing = gap(node);
    if (axis === undefined || spacing === undefined) continue;
    const available = inner(node, box)[axis];
    if (available === undefined) continue;
    const ids = children(node);
    let used = spacing * Math.max(0, ids.length - 1);
    for (const child of ids) {
      used += (boxes.get(child)?.[axis] ?? 0) + (inset(input.get(child)!, "margin", axis) ?? 0);
    }
    if (used > available + 1e-7) return output;
  }
  for (const [id, box] of boxes) {
    if (!authors.has(id)) continue;
    const parent = input.get(id)!, main = mainAxis(parent), space = inner(parent, box);
    const ids = children(parent);
    for (const child of ids) {
      const node = input.get(child)!, kind = authors.get(child)?.type ?? "", props = node.props;
      if (constraints.some(key => key in props)) continue;
      for (const axis of axes) {
        if (axis === main || !(axis === "width" ? widthFill : regions).has(kind)) continue;
        if (inset(node, "margin", axis) !== 0) continue;
        const value = number(props[axis]), available = space[axis];
        if (value !== undefined && value > 0 && available !== undefined && Math.abs(value - available) <= 1e-7) {
          output.get(child)!.props[axis] = "matchParent";
        }
      }
    }
    const spacing = gap(parent);
    if (main === undefined || space[main] === undefined || spacing === undefined) continue;
    let used = spacing * Math.max(0, ids.length - 1), known = true;
    const candidates: Array<[string, number]> = [];
    for (const child of ids) {
      const node = input.get(child)!, props = node.props;
      const length = boxes.get(child)?.[main], margin = inset(node, "margin", main);
      if ((number(props.layoutWeight) ?? 0) > 0 || length === undefined || margin === undefined) {
        known = false; break;
      }
      used += length + margin;
      if (!regions.has(authors.get(child)?.type ?? "") || length <= 0) continue;
      if (constraints.some(key => key in props && !(key === "constraintSize" && slotActions.has(child)))) continue;
      if (main === "height" && fixedAction(child) && !slots.has(child)) continue;
      candidates.push([child, length]);
    }
    if (!known || Math.abs(used - space[main]!) > 1e-7) continue;
    // Web flex 的 padding 不参与权重分配；原盒比例无法保持时不转换。
    const ratios = candidates.map(([child, length]) => {
      const padding = inset(input.get(child)!, "padding", main);
      return padding === undefined ? undefined : padding / length;
    });
    if (ratios.some(ratio => ratio === undefined || Math.abs(ratio - ratios[0]!) > 1e-7)) continue;
    for (const [child, length] of candidates) {
      const props = output.get(child)!.props;
      delete props[main]; props.layoutWeight = length;
      if (main === "height" && slotActions.has(child) && props.constraintSize) {
        const limits = { ...(props.constraintSize as Record<string, unknown>) };
        delete limits.maxHeight;
        props.constraintSize = limits;
      }
    }
  }
  return output;
}
