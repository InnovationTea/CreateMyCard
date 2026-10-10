import { mkdir, readFile, writeFile } from "node:fs/promises";
import path from "node:path";
import type * as ReactDomServer from "react-dom/server";
import { defaultRegistry, renderTree } from "@genui-sdk/renderer";
import { compileMiniDsl } from "../lib/mini-renderer";

type CardSize = "2x2" | "2x4";

type SummaryResult = {
  index: number;
  title: string;
  size: CardSize;
  capabilities?: string[];
  status: string;
  errorCode?: string;
  message?: string;
  elapsed_ms?: number;
  attempts?: number;
  totalAttempts?: number;
};

type Summary = {
  round?: string;
  timestamp?: string;
  total?: number;
  success?: number;
  failed?: number;
  results: SummaryResult[];
};

type InputPayload = {
  content?: {
    userQuery?: string;
    title?: string;
    size?: CardSize;
  };
  userQuery?: string;
  title?: string;
  size?: CardSize;
};

type RenderedCase = SummaryResult & {
  userQuery: string;
  compactDsl: string;
  rendererA2ui: string;
  cloudA2ui: string;
  componentTypes: string[];
  warnings: string[];
  renderedMarkup: string;
  renderError: string;
};

const platformRoot = process.cwd();
const repositoryRoot = path.resolve(platformRoot, "../..");
const defaultBatchDirectory = path.join(
  repositoryRoot,
  "widget_service/cloud/fusion-runner/output/no_fewshot_all_3",
);
const defaultInputDirectory = path.join(
  repositoryRoot,
  "widget_service/cloud/fusion-runner/cardSpec0918",
);
const { renderToStaticMarkup } = require(
  "../../genui-sdk/node_modules/react-dom/server",
) as typeof ReactDomServer;

function argument(name: string): string | undefined {
  const direct = process.argv.find(value => value.startsWith(`${name}=`));
  if (direct) return direct.slice(name.length + 1);
  const index = process.argv.indexOf(name);
  return index >= 0 ? process.argv[index + 1] : undefined;
}

function escapeHtml(value: string): string {
  return value
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

async function readOptional(filePath: string): Promise<string> {
  try {
    return await readFile(filePath, "utf8");
  } catch (error) {
    const code = (error as NodeJS.ErrnoException).code;
    if (code === "ENOENT") return "";
    throw error;
  }
}

function componentTypes(source: string): string[] {
  const types: string[] = [];
  for (const rawLine of source.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) continue;
    try {
      const tuple = JSON.parse(line) as unknown;
      if (!Array.isArray(tuple) || typeof tuple[1] !== "string") continue;
      if (!types.includes(tuple[1])) types.push(tuple[1]);
    } catch {
      // The renderer reports the complete syntax error. Component badges are optional metadata.
    }
  }
  return types;
}

function assetMimeType(filePath: string): string {
  const extension = path.extname(filePath).toLowerCase();
  if (extension === ".svg") return "image/svg+xml";
  if (extension === ".png") return "image/png";
  if (extension === ".jpg" || extension === ".jpeg") return "image/jpeg";
  if (extension === ".webp") return "image/webp";
  throw new Error(`不支持内嵌的素材格式：${extension}`);
}

async function loadAssetDataUris(sources: string[]): Promise<Map<string, string>> {
  const assetPaths = new Set<string>();
  const pattern = /resources\/[\w./-]+\.(?:svg|png|jpe?g|webp)/gi;
  for (const source of sources) {
    for (const match of source.matchAll(pattern)) assetPaths.add(match[0]);
  }

  const dataUris = new Map<string, string>();
  for (const relativePath of assetPaths) {
    const absolutePath = path.join(platformRoot, "public", relativePath);
    try {
      const content = await readFile(absolutePath);
      const dataUri = `data:${assetMimeType(absolutePath)};base64,${content.toString("base64")}`;
      dataUris.set(`/${relativePath}`, dataUri);
    } catch (error) {
      const code = (error as NodeJS.ErrnoException).code;
      if (code !== "ENOENT") throw error;
    }
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

async function loadInput(index: number, inputDirectory: string): Promise<InputPayload> {
  const filename = `Q${String(index).padStart(3, "0")}.json`;
  const source = await readOptional(path.join(inputDirectory, filename));
  return source ? JSON.parse(source) as InputPayload : {};
}

async function loadCase(
  result: SummaryResult,
  batchDirectory: string,
  inputDirectory: string,
): Promise<RenderedCase> {
  const basename = `q${result.index}.jsonl`;
  const [input, compactDsl, cloudA2ui] = await Promise.all([
    loadInput(result.index, inputDirectory),
    readOptional(path.join(batchDirectory, "designcompactdsl", basename)),
    readOptional(path.join(batchDirectory, "dsl", basename)),
  ]);
  const content = input.content ?? {};

  return {
    ...result,
    title: result.title || content.title || input.title || `Q${result.index}`,
    size: result.size || content.size || input.size || "2x2",
    userQuery: content.userQuery || input.userQuery || "",
    compactDsl,
    rendererA2ui: "",
    cloudA2ui,
    componentTypes: componentTypes(compactDsl),
    warnings: [],
    renderedMarkup: "",
    renderError: "",
  };
}

function renderCases(cases: RenderedCase[], dataUris: Map<string, string>): void {
  for (const item of cases) {
    if (!item.compactDsl) continue;
    try {
      const compiled = compileMiniDsl(item.compactDsl, { size: item.size });
      item.rendererA2ui = compiled.jsonl;
      item.warnings = compiled.warnings;
      const markup = renderToStaticMarkup(
        renderTree(compiled.graph, defaultRegistry, {
          formId: null,
          onDataModelUserEdit: () => undefined,
          interactionHost: {
            functionCall: () => undefined,
            submitForm: () => undefined,
          },
        }),
      );
      item.renderedMarkup = inlineAssets(markup, dataUris);
    } catch (error) {
      item.renderError = error instanceof Error ? error.message : String(error);
    }
  }
}

function badges(values: string[], className = "badge"): string {
  return values.map(value => `<span class="${className}">${escapeHtml(value)}</span>`).join("");
}

function details(label: string, content: string, open = false): string {
  if (!content) return "";
  return `<details${open ? " open" : ""}><summary>${escapeHtml(label)}</summary><pre>${escapeHtml(content)}</pre></details>`;
}

function renderCase(item: RenderedCase): string {
  const width = item.size === "2x4" ? 300 : 150;
  const renderStatus = item.renderedMarkup ? "rendered" : "failed";
  const search = [
    item.index,
    item.title,
    item.userQuery,
    item.size,
    item.status,
    item.errorCode,
    ...item.componentTypes,
    ...(item.capabilities ?? []),
  ].join(" ").toLocaleLowerCase();
  const diagnostic = item.renderError || item.message || item.errorCode || "没有生成 Compact DSL";
  const preview = item.renderedMarkup
    ? `<div class="cardViewport" style="width:${width}px;height:150px">${item.renderedMarkup}</div>`
    : `<div class="renderFailure"><strong>无法渲染</strong><span>${escapeHtml(diagnostic)}</span></div>`;
  const warnings = item.warnings.length
    ? `<div class="warningBox"><strong>Renderer 警告</strong>${item.warnings.map(warning => `<p>${escapeHtml(warning)}</p>`).join("")}</div>`
    : "";
  const statusClass = item.status === "success" ? "success" : "failure";

  return `<article class="caseCard" data-case data-size="${item.size}" data-status="${item.status}" data-render="${renderStatus}" data-search="${escapeHtml(search)}">
    <header class="caseHead">
      <div><span class="caseIndex">Q${String(item.index).padStart(3, "0")}</span><h2>${escapeHtml(item.title)}</h2></div>
      <div class="statusGroup"><span class="status ${statusClass}">${escapeHtml(item.status)}</span><span class="size">${item.size}</span></div>
    </header>
    <p class="query">${escapeHtml(item.userQuery || "未读取到用户问题")}</p>
    <div class="metaRow">
      ${badges(item.componentTypes, "componentBadge")}
      ${badges(item.capabilities ?? [], "capabilityBadge")}
    </div>
    <div class="previewStage">${preview}<span class="dimension">${width} × 150 · 当前 render</span></div>
    ${warnings}
    <div class="caseFacts">
      <span>耗时 <b>${Math.round(item.elapsed_ms ?? 0)} ms</b></span>
      <span>本轮尝试 <b>${item.attempts ?? 0}</b></span>
      <span>累计尝试 <b>${item.totalAttempts ?? item.attempts ?? 0}</b></span>
      <span>组件 <b>${item.componentTypes.length}</b></span>
    </div>
    <div class="detailsStack">
      ${details("Compact DSL", item.compactDsl, Boolean(item.renderError))}
      ${details("Renderer 展开的 A2UI", item.rendererA2ui)}
      ${details("云侧保存的 A2UI", item.cloudA2ui)}
      ${item.renderError ? details("Renderer 错误", item.renderError, true) : ""}
    </div>
  </article>`;
}

function pageStyles(): string {
  return `
    :root { color-scheme: light; --surface:#fff; --page:#f3f5f8; --line:#e6e9ef; --text:#182033; --muted:#667085; --blue:#315efb; --green:#16845b; --red:#d04444; }
    * { box-sizing:border-box; }
    html { scroll-behavior:smooth; }
    body { margin:0; color:var(--text); background:var(--page); font-family:"HarmonyOS Sans SC","HarmonyOS Sans","PingFang SC",sans-serif; }
    button,input { font:inherit; }
    .topbar { position:sticky; top:0; z-index:10; display:flex; justify-content:space-between; gap:20px; padding:16px 28px; border-bottom:1px solid var(--line); background:rgba(255,255,255,.94); backdrop-filter:blur(14px); }
    .topbar h1 { margin:0; font-size:18px; }
    .topbar p { margin:4px 0 0; color:var(--muted); font-size:12px; }
    .summary { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
    .metric { min-width:72px; padding:7px 10px; border:1px solid var(--line); border-radius:10px; background:#fff; text-align:center; }
    .metric b { display:block; font-size:16px; }
    .metric span { color:var(--muted); font-size:10px; }
    main { max-width:1480px; margin:0 auto; padding:22px 28px 80px; }
    .toolbar { position:sticky; top:82px; z-index:9; display:flex; align-items:center; gap:12px; margin-bottom:20px; padding:12px; border:1px solid var(--line); border-radius:14px; background:rgba(255,255,255,.94); backdrop-filter:blur(12px); }
    .toolbar input { flex:1; min-width:160px; padding:9px 12px; border:1px solid var(--line); border-radius:9px; outline:none; background:#f9fafb; }
    .filters { display:flex; gap:5px; flex-wrap:wrap; }
    .filters button { padding:7px 11px; border:1px solid var(--line); border-radius:8px; color:var(--muted); background:#fff; cursor:pointer; }
    .filters button[aria-pressed="true"] { color:#fff; border-color:var(--blue); background:var(--blue); }
    .count { color:var(--muted); font-size:12px; white-space:nowrap; }
    .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(390px,1fr)); gap:18px; align-items:start; }
    .caseCard { overflow:hidden; border:1px solid var(--line); border-radius:16px; background:var(--surface); box-shadow:0 5px 22px rgba(31,42,68,.05); }
    .caseHead { display:flex; justify-content:space-between; gap:12px; padding:16px 18px 0; }
    .caseHead > div:first-child { display:flex; align-items:center; gap:9px; min-width:0; }
    .caseHead h2 { margin:0; overflow:hidden; font-size:15px; white-space:nowrap; text-overflow:ellipsis; }
    .caseIndex { color:var(--muted); font-family:ui-monospace,monospace; font-size:11px; }
    .statusGroup,.metaRow { display:flex; align-items:center; gap:6px; flex-wrap:wrap; }
    .status,.size,.badge,.componentBadge,.capabilityBadge { padding:3px 7px; border-radius:999px; font-size:9px; font-weight:600; }
    .status.success { color:var(--green); background:#e8f7f0; }
    .status.failure { color:var(--red); background:#fff0f0; }
    .size { color:#5c46b8; background:#f0edff; }
    .query { min-height:34px; margin:10px 18px 8px; color:var(--muted); font-size:11px; line-height:1.55; }
    .metaRow { min-height:21px; padding:0 18px 12px; }
    .componentBadge { color:#2254c8; background:#edf3ff; }
    .capabilityBadge { color:#765510; background:#fff7df; }
    .previewStage { min-height:236px; padding:26px 18px 18px; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:12px; border-top:1px solid var(--line); border-bottom:1px solid var(--line); background-color:#f8fafc; background-image:radial-gradient(#d8dde7 .7px,transparent .7px); background-size:16px 16px; }
    .cardViewport { flex:0 0 auto; overflow:hidden; isolation:isolate; border-radius:20px; background:#fff; box-shadow:0 14px 34px rgba(24,32,51,.15); }
    .dimension { color:var(--muted); font-family:ui-monospace,monospace; font-size:9px; }
    .renderFailure { width:min(300px,100%); min-height:150px; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:7px; padding:18px; border:1px dashed #efb0b0; border-radius:14px; color:var(--red); background:#fff7f7; text-align:center; }
    .renderFailure span { font-size:10px; overflow-wrap:anywhere; }
    .warningBox { margin:12px 18px 0; padding:9px 11px; border-radius:9px; color:#815d00; background:#fff8dc; font-size:10px; }
    .warningBox p { margin:4px 0 0; }
    .caseFacts { display:flex; flex-wrap:wrap; gap:8px 14px; padding:12px 18px; color:var(--muted); font-size:10px; }
    .caseFacts b { color:var(--text); }
    .detailsStack { padding:0 18px 16px; display:flex; flex-direction:column; gap:7px; }
    details { border:1px solid var(--line); border-radius:8px; background:#fbfcfe; }
    summary { padding:8px 10px; color:#3856a8; cursor:pointer; font-size:10px; font-weight:600; }
    pre { max-height:320px; margin:0; padding:11px; overflow:auto; border-top:1px solid var(--line); color:#344054; font-family:ui-monospace,"SFMono-Regular",Menlo,monospace; font-size:9px; line-height:1.55; white-space:pre-wrap; overflow-wrap:anywhere; }
    .empty { padding:60px; color:var(--muted); text-align:center; }
    footer { margin-top:32px; color:var(--muted); font-size:10px; text-align:center; }
    [hidden] { display:none !important; }
    @media (max-width:760px) { .topbar { position:static; padding:14px 16px; flex-direction:column; } main { padding:16px; } .toolbar { top:8px; flex-wrap:wrap; } .grid { grid-template-columns:1fr; } }
  `;
}

function pageScript(): string {
  return String.raw`
    (() => {
      const cards = [...document.querySelectorAll('[data-case]')];
      const search = document.querySelector('[data-search]');
      const buttons = [...document.querySelectorAll('[data-filter]')];
      const count = document.querySelector('[data-count]');
      const empty = document.querySelector('[data-empty]');
      let active = 'all';
      const refresh = () => {
        const query = search.value.trim().toLocaleLowerCase();
        let visible = 0;
        for (const card of cards) {
          const matchesText = !query || card.dataset.search.includes(query);
          const matchesFilter = active === 'all'
            || card.dataset.size === active
            || card.dataset.status === active
            || card.dataset.render === active;
          card.hidden = !(matchesText && matchesFilter);
          if (!card.hidden) visible += 1;
        }
        count.textContent = visible + ' / ' + cards.length;
        empty.hidden = visible !== 0;
      };
      search.addEventListener('input', refresh);
      for (const button of buttons) {
        button.addEventListener('click', () => {
          active = button.dataset.filter;
          for (const candidate of buttons) candidate.setAttribute('aria-pressed', String(candidate === button));
          refresh();
        });
      }
    })();
  `;
}

function renderDocument(summary: Summary, cases: RenderedCase[]): string {
  const rendered = cases.filter(item => item.renderedMarkup).length;
  const renderFailed = cases.filter(item => item.compactDsl && !item.renderedMarkup).length;
  const warnings = cases.reduce((total, item) => total + item.warnings.length, 0);
  const title = `${summary.round ?? "Fusion batch"} · Renderer 结果审阅`;
  return `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <meta name="description" content="Fusion Runner Compact DSL 的 Renderer 离线审阅页">
  <title>${escapeHtml(title)}</title>
  <link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E%3Crect width='32' height='32' rx='8' fill='%23315efb'/%3E%3Cpath d='M9 10h14v12H9z' fill='none' stroke='white' stroke-width='2'/%3E%3C/svg%3E">
  <style>${pageStyles()}</style>
</head>
<body>
  <header class="topbar">
    <div><h1>${escapeHtml(title)}</h1><p>直接使用 render/platform 的 compileMiniDsl 与 @genui-sdk/renderer 生成 · ${escapeHtml(summary.timestamp ?? "")}</p></div>
    <div class="summary">
      <div class="metric"><b>${cases.length}</b><span>总任务</span></div>
      <div class="metric"><b>${summary.success ?? 0}</b><span>生成成功</span></div>
      <div class="metric"><b>${rendered}</b><span>渲染成功</span></div>
      <div class="metric"><b>${summary.failed ?? 0}</b><span>生成失败</span></div>
      <div class="metric"><b>${renderFailed}</b><span>渲染失败</span></div>
      <div class="metric"><b>${warnings}</b><span>渲染警告</span></div>
    </div>
  </header>
  <main>
    <section class="toolbar">
      <input type="search" placeholder="搜索编号、标题、问题、组件或能力" aria-label="搜索结果" data-search>
      <div class="filters" role="group" aria-label="筛选结果">
        <button type="button" aria-pressed="true" data-filter="all">全部</button>
        <button type="button" aria-pressed="false" data-filter="2x2">2×2</button>
        <button type="button" aria-pressed="false" data-filter="2x4">2×4</button>
        <button type="button" aria-pressed="false" data-filter="success">生成成功</button>
        <button type="button" aria-pressed="false" data-filter="failed">生成失败</button>
        <button type="button" aria-pressed="false" data-filter="rendered">已渲染</button>
      </div>
      <span class="count" data-count>${cases.length} / ${cases.length}</span>
    </section>
    <section class="grid">${cases.map(renderCase).join("\n")}</section>
    <div class="empty" data-empty hidden>没有匹配的结果。</div>
    <footer>Fusion Compact DSL · standalone renderer review</footer>
  </main>
  <script>${pageScript()}</script>
</body>
</html>`;
}

async function main(): Promise<void> {
  const batchDirectory = path.resolve(argument("--input") ?? defaultBatchDirectory);
  const inputDirectory = path.resolve(argument("--cards") ?? defaultInputDirectory);
  const outputPath = path.resolve(argument("--output") ?? path.join(batchDirectory, "example.html"));
  const summary = JSON.parse(
    await readFile(path.join(batchDirectory, "summary.json"), "utf8"),
  ) as Summary;
  const cases = await Promise.all(
    summary.results.map(result => loadCase(result, batchDirectory, inputDirectory)),
  );
  const dataUris = await loadAssetDataUris(cases.map(item => item.compactDsl));
  renderCases(cases, dataUris);
  const document = renderDocument(summary, cases);
  await mkdir(path.dirname(outputPath), { recursive: true });
  await writeFile(outputPath, document, "utf8");

  const rendered = cases.filter(item => item.renderedMarkup).length;
  const errors = cases.filter(item => item.renderError);
  console.log(`已导出 ${cases.length} 条结果，其中 ${rendered} 条由 Renderer 成功渲染：${outputPath}`);
  if (errors.length) {
    console.log(`Renderer 失败 ${errors.length} 条：${errors.map(item => `Q${item.index} ${item.renderError}`).join("；")}`);
  }
}

void main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
