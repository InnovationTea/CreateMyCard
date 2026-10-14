// 只读取当前 Web 画面；不改变 DOM、DSL 或滚动位置。
// 可直接传给 Playwright locator.evaluate，不依赖外部闭包。
export function collectWebQuality(root) {
  const findings = [];
  const surface = root.querySelector('.card-renderer__surface') || root;
  const frame = surface.getBoundingClientRect();
  const rect = (r) => ({ x: r.x - frame.x, y: r.y - frame.y, width: r.width, height: r.height });
  const outside = (a, b) => a.left < b.left - 2 || a.top < b.top - 2 || a.right > b.right + 2 || a.bottom > b.bottom + 2;
  const owner = (el) => el.closest('[data-node-id]') || el;
  const identity = (el) => `${owner(el).getAttribute('data-node-id') || el.tagName}:${Array.from(surface.querySelectorAll('[data-node-id]')).indexOf(owner(el))}`;
  const visible = (el) => {
    for (let p = el; p && root.contains(p); p = p.parentElement) {
      const s = getComputedStyle(p);
      if (s.display === 'none' || s.visibility === 'hidden' || Number(s.opacity) === 0) return false;
    }
    return true;
  };
  const inScroller = (el) => {
    for (let p = el.parentElement; p && surface.contains(p); p = p.parentElement) {
      const s = getComputedStyle(p);
      if (/(auto|scroll)/.test(`${s.overflowX} ${s.overflowY}`)) return true;
    }
    return false;
  };
  const emit = (code, el, message, evidence, confirmed = true) => {
    findings.push({ rule_id: code, severity: 'P1', evidence_type: confirmed ? '程序已证实' : '待确认',
      components: [identity(el)], message, evidence: { component: owner(el).getAttribute('data-node-id'), ...evidence } });
  };
  const leaves = [];
  let excludedScrollable = 0;
  const walker = document.createTreeWalker(surface, NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const node = walker.currentNode;
    const el = node.parentElement;
    if (!el || !node.textContent.trim() || /^(STYLE|SCRIPT)$/.test(el.tagName) || !visible(el)) continue;
    if (inScroller(el)) { excludedScrollable += 1; continue; }
    const range = document.createRange();
    range.selectNodeContents(node);
    const boxes = Array.from(range.getClientRects()).filter((r) => r.width > 0 && r.height > 0);
    const style = getComputedStyle(el);
    const box = el.getBoundingClientRect();
    const evidence = { text: node.textContent, box: rect(box), textRects: boxes.map(rect),
      clientWidth: el.clientWidth, scrollWidth: el.scrollWidth, clientHeight: el.clientHeight, scrollHeight: el.scrollHeight };
    let clipped = false;
    for (let p = el; p && root.contains(p); p = p.parentElement) {
      const ps = getComputedStyle(p);
      const pr = p.getBoundingClientRect();
      const clipX = /hidden|clip/.test(ps.overflowX);
      const clipY = /hidden|clip/.test(ps.overflowY);
      if (boxes.some((r) => (clipX && (r.left < pr.left - 2 || r.right > pr.right + 2)) ||
          (clipY && (r.top < pr.top - 2 || r.bottom > pr.bottom + 2)))) clipped = true;
    }
    const clamp = Number.parseInt(style.webkitLineClamp, 10) > 0;
    if ((clamp || style.textOverflow === 'ellipsis') &&
        (el.scrollHeight > el.clientHeight + 2 || el.scrollWidth > el.clientWidth + 2)) clipped = true;
    if (clipped) emit('GEOMETRY.CLIP_TEXT', el, 'Web 渲染中文字被裁剪或省略', evidence);
    else if (boxes.some((r) => outside(r, frame))) emit('GEOMETRY.OVERFLOW_TEXT', el, '文字超出卡片画布', evidence);
    const shownBoxes = boxes.filter((r) => r.right > frame.left && r.left < frame.right && r.bottom > frame.top && r.top < frame.bottom);
    leaves.push({ el, boxes: shownBoxes });
  }
  let measuredImages = 0;
  for (const el of surface.querySelectorAll('img, [role="img"]')) {
    if (!visible(el) || inScroller(el)) continue;
    measuredImages += 1;
    const box = el.getBoundingClientRect();
    const missing = el.getAttribute('aria-label')?.startsWith('素材未找到：') ||
      (el.tagName === 'IMG' && el.complete && el.naturalWidth === 0);
    if (missing) emit('ASSET.WEB_LOAD_FAILED', el, '当前 Web 画面素材加载失败（不等于 DSL 引用错误）', { src: el.getAttribute('src') || el.getAttribute('title'), box: rect(box) });
    else if (box.width > 0 && box.height > 0 && outside(box, frame)) emit('GEOMETRY.OVERFLOW_IMAGE', el, '图片超出卡片画布', { box: rect(box) });
  }
  // ponytail: 一张卡内文字片段两两比对；超大文档改用空间索引，不跨卡比较。
  for (let i = 0; i < leaves.length; i += 1) {
    for (let j = i + 1; j < leaves.length; j += 1) {
      const a = leaves[i], b = leaves[j];
      if (a.el.contains(b.el) || b.el.contains(a.el) || owner(a.el) === owner(b.el)) continue;
      const overlaps = a.boxes.some((x) => b.boxes.some((y) =>
        Math.min(x.right, y.right) - Math.max(x.left, y.left) > 2 &&
        Math.min(x.bottom, y.bottom) - Math.max(x.top, y.top) > 2));
      if (overlaps) {
        const targets = [identity(a.el), identity(b.el)].sort();
        findings.push({ rule_id: 'GEOMETRY.OVERLAP_TEXT', severity: 'P1', evidence_type: '待确认',
          components: targets, root_cause_id: `web-overlap:${targets.join(':')}`,
          message: '两个独立文字区域相交；字形实际遮挡程度待确认',
          evidence: { a: a.boxes.map(rect), b: b.boxes.map(rect) } });
      }
    }
  }
  return { schemaVersion: 'web-quality-v1', complete: frame.width > 0 && frame.height > 0 && (leaves.length > 0 || measuredImages > 0),
    findings, frame: rect(frame), measuredTextNodes: leaves.length, measuredImages, excludedScrollable,
    coverage: ['text-clipping', 'card-boundary', 'text-overlap-candidates', 'image-loading', 'parser-warnings'],
    limitations: ['不验证真实端侧功能及 Query 语义完整性', '不验证品牌色板与整体审美', '滚动区域、隐藏态和字形级遮挡不作通过结论'] };
}
