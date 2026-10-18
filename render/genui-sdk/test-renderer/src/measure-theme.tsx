// Development diagnostics only. Explicit test dimensions are not device geometry evidence.
import { readFile } from "node:fs/promises";
import path from "node:path";
import { pathToFileURL } from "node:url";
import { renderToStaticMarkup } from "react-dom/server";
import { defaultRegistry, renderTree } from "@genui-sdk/renderer";
import { compileA2uiJsonl } from "../../../platform/lib/mini-renderer";
import { textBound } from "./theme-text-bounds";

async function main() {
  let input = "";
  for await (const chunk of process.stdin) input += chunk.toString();
  const payload = JSON.parse(input);
  const width = payload.viewport?.width;
  const height = payload.viewport?.height;
  if (![width, height].every(value => typeof value === "number" && Number.isFinite(value) && value > 0 && value <= 4096)) {
    throw new Error("Explicit test viewport width and height are required");
  }
  const layoutSize = payload.layoutSize || payload.size;
  const records = payload.source.trim().split(/\r?\n/).map((line: string) => JSON.parse(line));
  for (const row of records) {
    if (row.createSurface) Object.assign(row.createSurface, { width, height });
  }
  const nodes = records.find((row: any) => row.updateComponents)?.updateComponents.components || [];
  const modelById = Object.fromEntries(nodes.map((node: any) => [node.id, node]));
  const textBounds = Object.fromEntries(nodes.filter((node: any) => node.component === "Text")
    .map((node: any) => [node.id, textBound(node.content ?? node.label, payload.dataModelSchema)]));
  const compiled = compileA2uiJsonl(records.map((row: any) => JSON.stringify(row)).join("\n"), { size: payload.size });
  let markup = renderToStaticMarkup(renderTree(compiled.graph, defaultRegistry, { formId: null }));
  const repo = path.resolve(__dirname, "../../../..");
  const sources = new Set(markup.match(/\/?resources\/[\w./-]+\.(?:svg|png|jpg|jpeg|webp)/g) || []);
  for (const src of sources) {
    const relative = src.replace(/^\//, "");
    const filename = path.resolve(repo, relative);
    if (!filename.startsWith(repo + path.sep)) throw new Error("Invalid resource path");
    try {
      const bytes = await readFile(filename);
      const ext = path.extname(filename).slice(1);
      const mime = ext === "svg" ? "svg+xml" : ext === "jpg" ? "jpeg" : ext;
      markup = markup.split(src).join(`data:image/${mime};base64,${bytes.toString("base64")}`);
    } catch (error) {
      // Missing assets remain visible as a measurement failure, never as free space.
      console.error(`Missing local resource: ${relative}`);
    }
  }
  const playwrightPath = process.env.THEME_PLAYWRIGHT_MODULE;
  if (!playwrightPath) throw new Error("THEME_PLAYWRIGHT_MODULE is required");
  const { chromium } = await import(pathToFileURL(playwrightPath).href);
  const browser = await chromium.launch({ executablePath: process.env.THEME_BROWSER_EXECUTABLE, headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 640, height: 480 }, deviceScaleFactor: 1 });
    await page.route("**/*", (route: any) => route.request().url().startsWith("data:") ? route.continue() : route.abort());
    await page.setContent(`<html><meta charset="utf-8"><style>*{box-sizing:border-box}body{margin:0;font-family:Arial,'Microsoft YaHei',sans-serif}#surface{width:${width}px;height:${height}px;position:relative}</style><div id="surface">${markup}</div></html>`);
    await page.addScriptTag({ content: "globalThis.__name = (value) => value;" });
    await page.evaluate(() => document.fonts.ready);
    const evidence = await page.evaluate(({ modelById, width, height, layoutSize, buttonIds, dynamicTextReservation, textBounds }: any) => {
      const surface = document.getElementById("surface")!;
      const frame = surface.getBoundingClientRect();
      const occupied: any[] = [], visible: any[] = [], unsafe: string[] = [];
      const rect = (r: DOMRect) => [(r.x - frame.x) / width, (r.y - frame.y) / height, r.width / width, r.height / height];
      const expand = (r: DOMRect) => new DOMRect(r.x - 2, r.y - 2, r.width + 4, r.height + 4);
      const measuredTexts = new Set<string>();
      const textReservations: Record<string, any> = {};
      const horizontalGrowth: Record<string, number> = {};
      const reserveText = (id: string, owner: HTMLElement, parent: HTMLElement, boxes: DOMRect[], current: string) => {
        const bound = textBounds[id];
        const dynamic = bound?.dynamic ?? false;
        if (!dynamic) return boxes;
        const slot = owner.getBoundingClientRect();
        const model = modelById[id];
        const declaredWidth = model?.styles?.width;
        const fixedWidth = typeof declaredWidth === "number" || declaredWidth === "matchParent" ||
          Number(model?.styles?.layoutWeight) > 0 ||
          (typeof declaredWidth === "string" && /^\d+(\.\d+)?%$/.test(declaredWidth));
        const style = getComputedStyle(parent);
        const em = Number.parseFloat(style.fontSize);
        let anchor = style.textAlign;
        if (anchor === "start") anchor = style.direction === "rtl" ? "right" : "left";
        if (anchor === "end") anchor = style.direction === "rtl" ? "left" : "right";
        if (!fixedWidth && owner.parentElement) {
          const parentStyle = getComputedStyle(owner.parentElement);
          const alignment = parentStyle.flexDirection.startsWith("row")
            ? parentStyle.justifyContent : parentStyle.alignItems;
          if (["center", "space-between", "space-around", "space-evenly"].includes(alignment)) anchor = "center";
          else if (["end", "flex-end"].includes(alignment)) anchor = "right";
        }
        if (!["left", "right", "center"].includes(anchor) || !Number.isFinite(em)) {
          unsafe.push(`unmeasured-dynamic-alignment:${id}`);
          return boxes;
        }
        let reason = "estimated-current-glyphs";
        let maxWidth = 0;
        const singleLine = model?.styles?.maxLines === 1 && boxes.length <= 1;
        if (bound?.candidates && singleLine) {
          const probe = document.createElement("span");
          probe.style.cssText = "position:fixed;visibility:hidden;white-space:pre;width:max-content;height:auto";
          for (const key of ["fontFamily", "fontSize", "fontWeight", "fontStyle", "fontVariant", "letterSpacing", "textTransform"] as const) {
            probe.style[key] = style[key];
          }
          document.body.appendChild(probe);
          for (const candidate of [...bound.candidates, current]) {
            probe.textContent = candidate;
            maxWidth = Math.max(maxWidth, probe.getBoundingClientRect().width);
          }
          probe.remove();
          reason = "finite-contract";
        }
        let glyphs = boxes;
        if (!glyphs.length && maxWidth > 0) {
          const lineHeight = parseFloat(style.lineHeight) || em * 1.4;
          let x = slot.x;
          if (anchor === "center") x += slot.width / 2;
          else if (anchor === "right") x += slot.width;
          glyphs = [new DOMRect(x, slot.y, 0, Math.min(slot.height || lineHeight, lineHeight))];
        }
        if (!glyphs.length) {
          unsafe.push(`unmeasured-dynamic-text:${id}`);
          textReservations[id] = { reason: "unmeasured-empty-glyphs", slot: rect(slot), reservedRects: [] };
          return [];
        }
        let growth = 0;
        const reservations = glyphs.map(box => {
          const baseWidth = Math.max(box.width, maxWidth);
          const extra = baseWidth - box.width + Math.max(em * 0.5, baseWidth * 0.15);
          growth = Math.max(growth, extra);
          let left = box.x;
          if (anchor === "center") left -= extra / 2;
          else if (anchor === "right") left -= extra;
          return new DOMRect(left, box.y, box.width + extra, box.height);
        });
        if (!fixedWidth) horizontalGrowth[id] = growth / width;
        const left = Math.min(...reservations.map(box => box.x));
        const top = Math.min(...reservations.map(box => box.y));
        const right = Math.max(...reservations.map(box => box.right));
        const bottom = Math.max(...reservations.map(box => box.bottom));
        const reservation = new DOMRect(left, top, right - left, bottom - top);
        textReservations[id] = { reason, candidates: bound?.candidates, slot: rect(slot), reserved: rect(reservation),
          reservedRects: reservations.map(rect), anchor,
          ...(reason === "estimated-current-glyphs" ? { risk: "future-long-text-may-overlap", extraEm: 0.5, growthRatio: 0.15 } : {}) };
        return reservations;
      };
      const walker = document.createTreeWalker(surface, NodeFilter.SHOW_TEXT);
      while (walker.nextNode()) {
        const text = walker.currentNode;
        if (!text.textContent?.trim()) continue;
        const parent = text.parentElement!;
        const owner = parent.closest("[data-node-id]") as HTMLElement;
        if (!owner) { unsafe.push("unowned-text"); continue; }
        const id = owner.dataset.nodeId!;
        const range = document.createRange();
        range.selectNodeContents(text);
        const boxes = [...range.getClientRects()].filter(r => r.width && r.height);
        const dynamic = textBounds[id]?.dynamic ?? false;
        for (const box of boxes) visible.push({ id, text: text.textContent, rect: rect(box) });
        const reservation = reserveText(id, owner, parent, boxes, text.textContent || "");
        measuredTexts.add(id);
        for (const box of reservation) occupied.push({ id, dynamic, rect: rect(expand(box)) });
        if (owner.scrollWidth > owner.clientWidth + 2 || owner.scrollHeight > owner.clientHeight + 2) {
          unsafe.push(`text-overflow:${id}`);
        }
      }
      for (const [id, bound] of Object.entries(textBounds) as [string, any][]) {
        if (!bound.dynamic || measuredTexts.has(id)) continue;
        const owner = [...surface.querySelectorAll<HTMLElement>("[data-node-id]")].find(el => el.dataset.nodeId === id);
        if (!owner) { unsafe.push(`unmeasured-text:${id}`); continue; }
        for (const box of reserveText(id, owner, owner, [], "")) {
          if (!box.width || !box.height) unsafe.push(`empty-dynamic-slot:${id}`);
          occupied.push({ id, dynamic: true, rect: rect(expand(box)) });
        }
      }
      const measuredImages = new Set<string>();
      for (const id of buttonIds) {
        const owner = [...surface.querySelectorAll<HTMLElement>("[data-node-id]")]
          .find(element => element.dataset.nodeId === id);
        const box = owner?.getBoundingClientRect();
        if (!box?.width || !box?.height) {
          unsafe.push(`unmeasured-button:${id}`);
        } else occupied.push({ id, kind: "button", rect: rect(expand(box)) });
      }
      for (const element of surface.querySelectorAll("img,svg,canvas,[role=img]")) {
        const owner = element.closest("[data-node-id]") as HTMLElement;
        const id = owner?.dataset.nodeId || "unknown-image";
        if (id.startsWith("__post_theme_") || id.startsWith("fusionBall")) continue;
        const box = owner ? owner.getBoundingClientRect() : element.getBoundingClientRect();
        if (element instanceof HTMLImageElement && (!element.complete || !element.naturalWidth)) unsafe.push(`missing:${id}`);
        if (box.width && box.height && !measuredImages.has(id)) {
          occupied.push({ id, rect: rect(expand(box)) });
          measuredImages.add(id);
        }
      }
      for (const [id, node] of Object.entries(modelById) as [string, any][]) {
        if (id.startsWith("__post_theme_") || id.startsWith("fusionBall")) continue;
        const kind = node.component;
        if (["Text", "Image", "Button", "Row", "Column", "Stack", "Divider", "Progress"].includes(kind)) {
          if (["Divider", "Progress"].includes(kind)) {
            const el = [...surface.querySelectorAll("[data-node-id]")].find(el => el.getAttribute("data-node-id") === id);
            if (el) occupied.push({ id, rect: rect(expand(el.getBoundingClientRect())) });
            else unsafe.push(`unmeasured:${id}`);
          }
        } else unsafe.push(`unsupported:${kind}`);
      }
      // Auto-width text can push following units; include the swept area, not just today's unit position.
      const growDescendants = (id: string, growth: number, visited = new Set<string>()) => {
        if (visited.has(id)) return;
        visited.add(id);
        for (const item of occupied) if (item.id === id) item.rect[2] += growth;
        for (const child of modelById[id]?.children || []) growDescendants(child, growth, visited);
      };
      for (const node of Object.values(modelById) as any[]) {
        if (node.component !== "Row" || ![undefined, "start"].includes(node.styles?.justifyContent)) continue;
        let growth = 0;
        for (const child of node.children || []) {
          if (growth) growDescendants(child, growth);
          growth += horizontalGrowth[child] || 0;
        }
      }
      const subjectAvoidance = occupied;
      const estimatedTextIds = Object.keys(textReservations).filter(id => textReservations[id].reason === "estimated-current-glyphs");
      return { complete: occupied.length > 0, occupied, visible, unsafe, subjectAvoidance,
        buttonPolicy: "whole-button", buttonIds,
        basis: "explicit-test-viewport", deviceGeometryKnown: false,
        dynamicPolicy: "actual-glyphs-with-dynamic-margin",
        dynamicTextReservation, textReservations, estimatedTextIds, horizontalGrowth, viewport: { width, height }, layoutSize,
        matchingConfidence: estimatedTextIds.length ? "heuristic-with-growth-margin" : "contract-or-static-glyphs", paddingVp: 2 };
    }, { modelById, textBounds, width, height, layoutSize, buttonIds: payload.buttonIds || [], dynamicTextReservation: payload.dynamicTextReservation || {} });
    if (payload.screenshot) await page.locator("#surface").screenshot({ path: payload.screenshot });
    process.stdout.write(JSON.stringify(evidence));
  } finally {
    await browser.close();
  }
}
main().catch(error => { console.error(error); process.exitCode = 1; });
