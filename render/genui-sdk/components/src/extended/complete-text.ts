import { useLayoutEffect, useRef, useState } from "react";

/** 按字素边界裁剪，避免拆开汉字、组合音标和 emoji。 */
export function fitCompleteText(text: string, width: number, measure: (value: string) => number): string {
  if (width <= 0) return "";
  if (measure(text) <= width) return text;
  const segments = new Intl.Segmenter(undefined, { granularity: "grapheme" }).segment(text);
  const ends = Array.from(segments, part => part.index + part.segment.length);
  let low = 0;
  let high = ends.length;
  while (low < high) {
    const middle = Math.ceil((low + high) / 2);
    if (measure(text.slice(0, ends[middle - 1])) <= width) low = middle;
    else high = middle - 1;
  }
  return low === 0 ? "" : text.slice(0, ends[low - 1]);
}

function measureCompleteText(element: HTMLElement, text: string): string {
  // 未布局或隐藏的元素等待尺寸通知后再计算；也兼容无布局引擎的测试环境。
  if (element.getClientRects().length === 0) return text;
  const document = element.ownerDocument;
  const computed = document.defaultView!.getComputedStyle(element);
  const probe = document.createElement("span");
  for (const property of [
    "font-family", "font-size", "font-weight", "font-style", "font-stretch", "font-variant",
    "font-feature-settings", "font-variation-settings", "font-kerning", "letter-spacing", "word-spacing",
    "text-transform",
  ]) probe.style.setProperty(property, computed.getPropertyValue(property));
  Object.assign(probe.style, { position: "fixed", visibility: "hidden", whiteSpace: "nowrap", left: "-100000px" });
  document.body.appendChild(probe);
  const originalWidth = element.style.width;
  try {
    // 自然宽度必须按原文重新布局，避免裁剪后的短前缀阻止容器变宽时恢复原文。
    probe.textContent = text;
    if (!originalWidth) element.style.width = `${probe.getBoundingClientRect().width}px`;
    const layout = document.defaultView!.getComputedStyle(element);
    const horizontalPadding = parseFloat(layout.paddingLeft) + parseFloat(layout.paddingRight);
    let width = parseFloat(layout.width);
    if (!Number.isFinite(width)) width = element.clientWidth - horizontalPadding;
    else if (layout.boxSizing === "border-box") {
      width -= horizontalPadding + parseFloat(layout.borderLeftWidth) + parseFloat(layout.borderRightWidth);
    }
    // computed width 会舍入小数；补偿不足千分之一像素的序列化误差。
    return fitCompleteText(text, width + 0.001, value => {
      probe.textContent = value;
      return probe.getBoundingClientRect().width;
    });
  } finally {
    element.style.width = originalWidth;
    probe.remove();
  }
}

export function useCompleteText(text: string, enabled: boolean, styleKey: string) {
  const ref = useRef<HTMLParagraphElement>(null);
  const [visibleText, setVisibleText] = useState(text);
  useLayoutEffect(() => {
    const element = ref.current;
    if (!enabled || !element) return;
    let active = true;
    const update = () => {
      if (active) setVisibleText(measureCompleteText(element, text));
    };
    update();
    const observer = typeof ResizeObserver === "undefined" ? undefined : new ResizeObserver(update);
    observer?.observe(element);
    if (element.parentElement) observer?.observe(element.parentElement);
    const fonts = element.ownerDocument.fonts;
    fonts?.addEventListener("loadingdone", update);
    void fonts?.ready.then(update);
    const window = element.ownerDocument.defaultView;
    window?.addEventListener("resize", update);
    return () => {
      active = false;
      observer?.disconnect();
      fonts?.removeEventListener("loadingdone", update);
      window?.removeEventListener("resize", update);
    };
  }, [text, enabled, styleKey]);
  return { ref, visibleText: enabled ? visibleText : text };
}
