/** Expansion contracts from CreateMyCard/Br_feature_fusion (see docs/fusion-compatibility.md). */
export type MiniNode = { type: string; props: Record<string, unknown>; children: string[] };
export type CardSize = "2x2" | "2x4";
export const FUSION_PALETTES: Record<string, readonly string[]> = {
  "fusion-ball-battery-teal": ["#FF1F9985", "#FF24B3B3", "#FF5AB38E"],
  "fusion-ball-schedule-cool": ["#FF1F3399", "#FF2385B3", "#FF24B3B3"],
  "fusion-ball-schedule-warm": ["#FF731D28", "#FFFF5533", "#FFE68A2E"],
  "fusion-ball-sleep-violet": ["#FF493D99", "#FF5536B3", "#FF7D6B99"],
  "fusion-ball-sport-orange": ["#FFF24131", "#FFFF8833", "#FFE68073"],
};

export function expandCompactComponents(input: Map<string, MiniNode>, size: CardSize) {
  const nodes = new Map(input);
  const add = (id: string, type: string, props: Record<string, unknown>, children: string[] = []) => {
    if (nodes.has(id)) throw new Error(`高级组件生成的 ID 与现有组件冲突：${id}`);
    nodes.set(id, { type, props, children });
  };
  const fusion = typeof input.get("root")?.props.design === "string" && Object.hasOwn(FUSION_PALETTES, String(input.get("root")?.props.design));
  for (const [id, node] of input) {
    const p = node.props;
    if (!["CardHeader", "TimelineUnit", "ActionUnit"].includes(node.type)) continue;
    if (node.children.length) throw new Error(`${node.type} 不接受 children。`);
    if (node.type === "CardHeader") {
      const allowed = ["title", "fontColor", "icon", "fillColor"];
      if (Object.keys(p).some(k => !allowed.includes(k)) || p.title == null || typeof p.fontColor !== "string") throw new Error("CardHeader 需要 title/fontColor，只接受可选 icon/fillColor。");
      const width = size === "2x2" ? 126 : 276;
      const children = [`${id}_title`];
      add(children[0], "Text", { content: p.title, width: width - (p.icon ? 28 : 0), fontSize: 12, fontWeight: 400, fontColor: p.fontColor, textAlign: "start", maxLines: 1, flexShrink: 0 });
      if (p.icon) {
        children.push(`${id}_icon`);
        add(`${id}_icon`, "Image", { src: p.icon, width: 20, height: 20, objectFit: "contain", flexShrink: 0, ...(p.fillColor ? { fillColor: p.fillColor } : {}) });
      }
      nodes.set(id, { type: "Row", props: { width, height: 20, itemMargin: p.icon ? 8 : 0, flexShrink: 0, justifyContent: "start", alignItems: "center" }, children });
    } else if (node.type === "TimelineUnit") {
      if (size !== "2x2") throw new Error("TimelineUnit 仅支持 2x2 卡片。");
      if (Object.keys(p).some(k => !["color", "lineColor"].includes(k)) || ![p.color, p.lineColor].every(c => typeof c === "string" && /^#[\da-f]{8}$/i.test(c))) throw new Error("TimelineUnit 需要 ARGB color 和 lineColor。");
      nodes.set(id, { type: "Column", props: { width: 8, height: 48, padding: { top: 4, right: 0, bottom: 2, left: 0 }, itemMargin: 4, alignItems: "center", justifyContent: "start", flexShrink: 0 }, children: [`${id}_dot`, `${id}_line`] });
      add(`${id}_dot`, "Divider", { width: 8, height: 8, strokeWidth: 0, color: "#00000000", borderWidth: 1.5, borderColor: p.color, borderRadius: 4, flexShrink: 0 });
      add(`${id}_line`, "Divider", { width: 1, height: 30, strokeWidth: 1, vertical: true, color: p.lineColor, flexShrink: 0 });
    } else {
      if (!["capsule", "icon-round"].includes(String(p.state))) throw new Error("ActionUnit.state 只支持 capsule 或 icon-round。");
      if (!Array.isArray(p.onClick) || p.onClick.length === 0) throw new Error("ActionUnit 需要 onClick 动作。");
      if (p.state === "capsule" && p.label == null) throw new Error("capsule 需要 label。");
      if (p.state === "icon-round" && (!p.icon || p.label !== undefined)) throw new Error("icon-round 需要 icon，且不接受 label。");
      const surface = p.actionSurface ?? "#1A1F4799", ink = p.actionInk ?? "#FF1F4799";
      const base = { width: p.state === "capsule" ? "matchParent" : 30, height: p.state === "capsule" ? 36 : 30, borderRadius: p.state === "capsule" ? 20 : 15, padding: 0, flexShrink: p.flexShrink ?? 0, backgroundColor: surface, onClick: p.onClick, accessibility: p.accessibility };
      if (p.state === "capsule" && !p.icon) {
        nodes.set(id, { type: "Button", props: { ...base, label: p.label, enabled: p.enabled ?? true, fontColor: ink, fontSize: p.fontSize ?? 14, fontWeight: p.fontWeight ?? 400 }, children: [] });
      } else {
        const iconId = `${id}_icon`, children = [iconId];
        add(iconId, "Image", { src: p.icon, width: 20, height: 20, objectFit: "contain", flexShrink: 0, fillColor: fusion ? "#99FFFFFF" : ink });
        if (p.state === "capsule") {
          children.push(`${id}_text`);
          add(`${id}_text`, "Text", { content: p.label, fontSize: p.fontSize ?? 14, fontWeight: p.fontWeight ?? 400, fontColor: ink, maxLines: 1 });
        }
        nodes.set(id, { type: "Row", props: { ...base, enabled: p.enabled ?? true, justifyContent: "center", alignItems: "center", itemMargin: 8 }, children });
      }
    }
  }
  if (fusion) {
    if (size !== "2x2") throw new Error("融球背景仅支持 2x2 卡片。");
    const root = nodes.get("root")!;
    const colors = FUSION_PALETTES[String(root.props.design)];
    const foreground = "__genui_render_component__root";
    const { design, backgroundColor, linearGradient, backgroundImage, ...props } = root.props;
    add(foreground, root.type, { ...props, width: "matchParent", height: "matchParent" }, root.children);
    nodes.set("root", { type: "Stack", props: { width: "matchParent", height: "matchParent", borderRadius: 20, clip: true, alignContent: "topStart" }, children: ["fusionBallBackground", foreground] });
    add("fusionBallBackground", "Stack", { width: "matchParent", height: "matchParent", borderRadius: 20, clip: true, alignContent: "topStart", accessibility: { decorative: true } }, ["fusionBallLargeSlot", "fusionBallMediumSlot", "fusionBallSmallSlot", "fusionBallGlassLayer"]);
    const geometries = [[180, 44, 210, "center", "Large"], [80, 220, 160, "bottom", "Medium"], [195, 190, 100, "bottomEnd", "Small"]] as const;
    geometries.forEach(([w, h, diameter, align, name], i) => {
      const ball = `fusionBall${name}`;
      add(`${ball}Slot`, "Stack", { width: `${w / 160 * 100}%`, height: `${h / 160 * 100}%`, alignContent: align }, [ball]);
      add(ball, "Divider", { width: `${diameter / w * 100}%`, height: `${diameter / h * 100}%`, borderRadius: 999, strokeWidth: 0, color: "#00000000", backgroundColor: colors[i] });
    });
    add("fusionBallGlassLayer", "Divider", { width: "matchParent", height: "matchParent", strokeWidth: 0, color: "#00000000", backgroundColor: "#0DFFFFFF", backdropBlur: { radius: 210 } });
  }
  return nodes;
}
