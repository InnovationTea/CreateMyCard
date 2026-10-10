import { readFile, mkdir, writeFile } from "node:fs/promises";
import path from "node:path";
import type * as ReactDomServer from "react-dom/server";
import { defaultRegistry, renderTree } from "@genui-sdk/renderer";
import { compileMiniDsl } from "../lib/mini-renderer";
import {
  COMPONENT_GALLERY,
  GALLERY_GROUPS,
  type GalleryComponent,
} from "../src/component-gallery-data";

const platformRoot = process.cwd();
const outputDirectory = path.join(platformRoot, "output");
const outputPath = path.join(outputDirectory, "fusion-component-gallery.html");
// Renderer source is compiled with the SDK workspace's React runtime. Use the
// matching server renderer to avoid mixing it with Next.js's React 18 copy.
const { renderToStaticMarkup } = require(
  "../../genui-sdk/node_modules/react-dom/server",
) as typeof ReactDomServer;

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function mimeType(filePath: string): string {
  const extension = path.extname(filePath).toLowerCase();
  if (extension === ".svg") return "image/svg+xml";
  if (extension === ".png") return "image/png";
  if (extension === ".jpg" || extension === ".jpeg") return "image/jpeg";
  if (extension === ".webp") return "image/webp";
  throw new Error(`不支持内嵌的素材格式：${extension}`);
}

async function loadAssetDataUris(): Promise<Map<string, string>> {
  const assetPaths = new Set<string>();
  const pattern = /resources\/[\w./-]+\.(?:svg|png|jpe?g|webp)/gi;
  for (const component of COMPONENT_GALLERY) {
    for (const match of component.source.matchAll(pattern)) assetPaths.add(match[0]);
  }

  const dataUris = new Map<string, string>();
  for (const relativePath of assetPaths) {
    const absolutePath = path.join(platformRoot, "public", relativePath);
    const content = await readFile(absolutePath);
    const dataUri = `data:${mimeType(absolutePath)};base64,${content.toString("base64")}`;
    dataUris.set(`/${relativePath}`, dataUri);
  }
  return dataUris;
}

function inlineAssets(markup: string, dataUris: Map<string, string>): string {
  let inlined = markup;
  for (const [assetPath, dataUri] of dataUris) {
    inlined = inlined.replaceAll(assetPath, dataUri);
  }
  return inlined;
}

function renderComponent(component: GalleryComponent, dataUris: Map<string, string>): string {
  const result = compileMiniDsl(component.source, { size: component.size });
  if (result.warnings.length) {
    throw new Error(`${component.name} 导出时存在警告：${result.warnings.join("；")}`);
  }
  const rendered = renderToStaticMarkup(
    renderTree(result.graph, defaultRegistry, {
      formId: null,
      onDataModelUserEdit: () => undefined,
      interactionHost: {
        functionCall: () => undefined,
        submitForm: () => undefined,
      },
    }),
  );
  return inlineAssets(rendered, dataUris);
}

function propType(prop: string): string {
  if (prop === "颜色组") return "visual tokens";
  if (prop.includes("items[")) return "array · required";
  if (prop === "onClick") return "Action[] · required";
  if (prop.endsWith("?")) return "optional";
  return "required / constrained";
}

function renderSpecimen(
  component: GalleryComponent,
  dataUris: Map<string, string>,
  index: string,
): string {
  const searchable = [component.name, component.summary, component.usage, ...component.props]
    .join(" ")
    .toLocaleLowerCase();
  const badges = component.sizes
    .map(size => `<span class="sizeBadge">${size}</span>`)
    .join("");
  const props = component.props
    .map(prop => `<div class="propsRow">
      <div class="propName"><code>${escapeHtml(prop)}</code><span>${escapeHtml(propType(prop))}</span></div>
      <div class="propValues"><span class="propChip">Compact DSL</span><span class="propChip">由组件合同与 Runtime 校验</span></div>
    </div>`)
    .join("");
  const preview = renderComponent(component, dataUris);

  return `<section class="section" id="${escapeHtml(component.id)}" data-gallery-component="${escapeHtml(component.name)}" data-search="${escapeHtml(searchable)}" data-sizes="${component.sizes.join(" ")}">
    <div class="sectionHead">
      <div class="sectionTitle">${index} ${escapeHtml(component.name)}</div>
      <div class="sectionDescription">${escapeHtml(component.summary)}</div>
    </div>
    <div class="componentCard">
      <div class="propsTable"><div class="propsHeader">Props</div>${props}</div>
      <div class="subsection">
        <div class="subsectionLabel">使用规则</div>
        <div class="ruleList">
          <div class="ruleItem"><span>使用场景</span><p>${escapeHtml(component.usage)}</p></div>
          <div class="ruleItem"><span>适用尺寸</span><div class="badges">${badges}</div></div>
          <div class="ruleItem"><span>样式来源</span><p>基础组件由 Renderer 直接渲染；高阶组件读取共享的 visual-recipes-v1。</p></div>
        </div>
      </div>
      <div class="subsection">
        <div class="subsectionLabel">典型用法</div>
        <div class="exampleStage">
          <div class="previewGroup">
            <div class="cardViewport" style="width:${component.width}px;height:${component.height}px" data-renderer-engine="fusion-renderer">${preview}</div>
            <span class="previewMeta">${component.width} × ${component.height} · ${component.size}</span>
          </div>
        </div>
      </div>
      <div class="subsection">
        <div class="subsectionLabel">Compact DSL</div>
        <details class="dslDetails"><summary>查看示例源码</summary><pre>${escapeHtml(component.source)}</pre></details>
      </div>
    </div>
  </section>`;
}

function renderGroups(dataUris: Map<string, string>): string {
  return GALLERY_GROUPS.map((group, groupIndex) => {
    const components = COMPONENT_GALLERY.filter(component => component.category === group.title);
    const specimens = components
      .map((component, componentIndex) => renderSpecimen(
        component,
        dataUris,
        `${groupIndex + 1}.${componentIndex + 1}`,
      ))
      .join("\n");
    return `<div data-gallery-group>
      <div class="categoryDivider" id="${group.id}"><span>${groupIndex + 1} ${group.title} —— ${escapeHtml(group.description)}</span></div>
      ${specimens}
    </div>`;
  }).join("\n");
}

function renderNavigation(): string {
  return GALLERY_GROUPS.map((group, groupIndex) => {
    const components = COMPONENT_GALLERY.filter(component => component.category === group.title);
    const links = components.map((component, componentIndex) => (
      `<a class="tocLink" href="#${component.id}">${groupIndex + 1}.${componentIndex + 1} ${escapeHtml(component.name)}</a>`
    )).join("");
    const separator = groupIndex > 0 ? '<div class="tocSeparator"></div>' : "";
    return `${separator}<div class="tocGroup"><div class="tocTitle">${groupIndex + 1} ${group.title}</div><div class="tocLinks">${links}</div></div>`;
  }).join("\n");
}

const standaloneScript = String.raw`
(() => {
  const input = document.querySelector('[data-gallery-search]');
  const buttons = [...document.querySelectorAll('[data-size-filter]')];
  const articles = [...document.querySelectorAll('[data-gallery-component]')];
  const groups = [...document.querySelectorAll('[data-gallery-group]')];
  const result = document.querySelector('[data-result-count]');
  const emptyState = document.querySelector('[data-empty-state]');
  const shell = document.querySelector('.galleryShell');
  const themeButton = document.querySelector('[data-theme-toggle]');
  const themeLabel = document.querySelector('[data-theme-label]');
  let activeSize = 'all';

  const applyFilters = () => {
    const query = input.value.trim().toLocaleLowerCase();
    let visible = 0;
    for (const article of articles) {
      const matchesQuery = !query || article.dataset.search.includes(query);
      const matchesSize = activeSize === 'all' || article.dataset.sizes.split(' ').includes(activeSize);
      article.hidden = !(matchesQuery && matchesSize);
      if (!article.hidden) visible += 1;
    }
    for (const group of groups) {
      group.hidden = !group.querySelector('[data-gallery-component]:not([hidden])');
    }
    result.textContent = visible + ' / ' + articles.length;
    emptyState.hidden = visible !== 0;
  };

  input.addEventListener('input', applyFilters);
  for (const button of buttons) {
    button.addEventListener('click', () => {
      activeSize = button.dataset.sizeFilter;
      for (const candidate of buttons) candidate.setAttribute('aria-pressed', String(candidate === button));
      applyFilters();
    });
  }
  themeButton.addEventListener('click', () => {
    const next = shell.dataset.theme === 'light' ? 'dark' : 'light';
    shell.dataset.theme = next;
    themeLabel.textContent = next === 'light' ? '暗色' : '亮色';
  });
})();`;

async function main() {
  const [galleryCss, iconSvg, dataUris] = await Promise.all([
    readFile(path.join(platformRoot, "src", "ComponentGallery.module.css"), "utf8"),
    readFile(path.join(platformRoot, "app", "icon.svg"), "utf8"),
    loadAssetDataUris(),
  ]);
  const iconDataUri = `data:image/svg+xml;base64,${Buffer.from(iconSvg).toString("base64")}`;
  const document = `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="description" content="Fusion Compact DSL 组件离线预览">
  <title>Fusion 组件总览</title>
  <link rel="icon" href="${iconDataUri}">
  <style>
    * { box-sizing: border-box; }
    html { scroll-behavior: smooth; }
    body { margin: 0; font-family: "HarmonyOS Sans SC", "PingFang SC", "Microsoft YaHei", sans-serif; }
    button, input { font: inherit; }
    button { cursor: pointer; }
    [hidden] { display: none !important; }
    ${galleryCss}
  </style>
</head>
<body>
  <main class="galleryShell" data-theme="light">
    <header class="topHeader">
      <div>
        <div class="headerTitle">Fusion Compact DSL · Component Library</div>
        <div class="headerMeta">${COMPONENT_GALLERY.length} 个组件 · 4 大分类 · Renderer 离线预览</div>
      </div>
      <div class="headerActions">
        <button type="button" class="themeButton" data-theme-toggle><span aria-hidden="true">◐</span><span data-theme-label>暗色</span></button>
      </div>
    </header>
    <div class="mainContent" id="top">
      <nav class="toc" aria-label="组件目录">${renderNavigation()}</nav>
      <section class="filterBar" aria-label="筛选组件">
        <label class="searchBox"><span aria-hidden="true">⌕</span><input type="search" placeholder="搜索组件、用途或属性" aria-label="搜索组件" data-gallery-search></label>
        <div class="sizeFilter" role="group" aria-label="按卡片尺寸筛选">
          <button type="button" aria-pressed="true" data-size-filter="all">全部</button>
          <button type="button" aria-pressed="false" data-size-filter="2x2">2x2</button>
          <button type="button" aria-pressed="false" data-size-filter="2x4">2x4</button>
        </div>
        <span class="resultCount" data-result-count>${COMPONENT_GALLERY.length} / ${COMPONENT_GALLERY.length}</span>
      </section>
      ${renderGroups(dataUris)}
      <section class="emptyState" data-empty-state hidden><strong>没有匹配的组件</strong><p>请调整关键词或卡片尺寸筛选。</p></section>
      <footer class="pageFooter"><span>Fusion Component Library</span><span>Compact DSL · visual-recipes-v1</span></footer>
    </div>
  </main>
  <script>${standaloneScript}</script>
</body>
</html>`;

  await mkdir(outputDirectory, { recursive: true });
  await writeFile(outputPath, document, "utf8");
  console.log(`已导出 ${COMPONENT_GALLERY.length} 个组件：${outputPath}`);
}

void main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
