import { spawnSync } from "node:child_process";
import { existsSync } from "node:fs";
import { mkdir, mkdtemp, readdir, readFile, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import path from "node:path";
import type * as ReactDomServer from "react-dom/server";
import { defaultRegistry, renderTree } from "@genui-sdk/renderer";
import { compileA2uiJsonl } from "../lib/mini-renderer";

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
  repairAttemptsByRound?: Array<number | null>;
  totalRepairAttempts?: number;
};

type Summary = {
  round?: string;
  timestamp?: string;
  total?: number;
  success?: number;
  failed?: number;
  partial?: number;
  results: SummaryResult[];
};

type InputPayload = {
  content?: {
    userQuery?: string;
    title?: string;
    size?: CardSize;
    appVersion?: string;
    candidateDataBindings?: CapabilityCandidate[];
    candidateEventCandidates?: CapabilityCandidate[];
  };
  userQuery?: string;
  title?: string;
  size?: CardSize;
  appVersion?: string;
  candidateDataBindings?: CapabilityCandidate[];
  candidateEventCandidates?: CapabilityCandidate[];
  deviceInfo?: {
    prdVer?: string;
  };
};

type CapabilityCandidate = {
  capabilityId?: string;
};

type RenderedCase = SummaryResult & {
  userQuery: string;
  appVersion?: string;
  compactDsl: string;
  cloudA2ui: string;
  componentTypes: string[];
  warnings: string[];
  renderedMarkup: string;
  renderError: string;
  variants: RenderedVariant[];
};

type RenderedVariant = {
  key: string;
  label: string;
  compactDsl: string;
  issues: string;
  componentTypes: string[];
  warnings: string[];
  renderedMarkup: string;
  renderError: string;
  rejected: boolean;
};

type PythonConversionRequest = {
  key: string;
  source: string;
  size: CardSize;
  preview: boolean;
  appVersion?: string;
};

type PythonConversionResult = {
  genui?: string;
  error?: string;
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

function pythonInterpreter(): string {
  const configured = argument("--python") ?? process.env.WIDGET_SERVICE_PYTHON?.trim();
  if (configured) return configured;
  const candidates = process.platform === "win32"
    ? [path.join(repositoryRoot, "widget_service/.venv/Scripts/python.exe")]
    : [path.join(repositoryRoot, "widget_service/.venv/bin/python")];
  return candidates.find(candidate => existsSync(candidate))
    ?? (process.platform === "win32" ? "python" : "python3");
}

async function convertCompactVariants(
  requests: PythonConversionRequest[],
): Promise<Map<string, PythonConversionResult>> {
  const converted = new Map<string, PythonConversionResult>();
  if (!requests.length) return converted;
  const temporaryDirectory = await mkdtemp(path.join(tmpdir(), "create-my-card-gallery-"));
  const inputPath = path.join(temporaryDirectory, "input.json");
  const outputPath = path.join(temporaryDirectory, "output.json");
  const converterPath = path.join(
    repositoryRoot,
    "widget_service/tools/convert_compact_gallery.py",
  );
  try {
    await writeFile(inputPath, JSON.stringify({ requests }), "utf8");
    const completed = spawnSync(
      pythonInterpreter(),
      [converterPath, "--input", inputPath, "--output", outputPath],
      {
        cwd: repositoryRoot,
        encoding: "utf8",
        env: {
          ...process.env,
          WIDGET_SERVICE_LOCAL_FLAG: process.env.WIDGET_SERVICE_LOCAL_FLAG ?? "true",
        },
        maxBuffer: 64 * 1024 * 1024,
      },
    );
    if (completed.error) throw completed.error;
    if (completed.status !== 0) {
      const detail = completed.stderr.trim() || completed.stdout.trim() || "未知错误";
      throw new Error(`正式 Python Gallery 转换失败：${detail}`);
    }
    const payload = JSON.parse(await readFile(outputPath, "utf8")) as {
      results?: Array<{ key?: unknown; genui?: unknown; error?: unknown }>;
    };
    if (!Array.isArray(payload.results)) {
      throw new Error("正式 Python Gallery 转换器返回了无效结果");
    }
    for (const result of payload.results) {
      if (typeof result.key !== "string") continue;
      converted.set(result.key, {
        genui: typeof result.genui === "string" ? result.genui : undefined,
        error: typeof result.error === "string" ? result.error : undefined,
      });
    }
    return converted;
  } finally {
    await rm(temporaryDirectory, { recursive: true, force: true });
  }
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

async function resultIndices(directory: string, pattern: RegExp): Promise<number[]> {
  let entries;
  try {
    entries = await readdir(directory, { withFileTypes: true });
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return [];
    throw error;
  }
  const indices: number[] = [];
  for (const entry of entries) {
    const match = pattern.exec(entry.name);
    if (!match) continue;
    const index = Number(match[1]);
    if (Number.isInteger(index)) indices.push(index);
  }
  return indices;
}

function inputCapabilities(input: InputPayload): string[] {
  const content = input.content ?? {};
  const bindings = content.candidateDataBindings ?? input.candidateDataBindings ?? [];
  const events = content.candidateEventCandidates ?? input.candidateEventCandidates ?? [];
  const capabilities: string[] = [];
  for (const candidate of [...bindings, ...events]) {
    const capabilityId = candidate.capabilityId?.trim();
    if (capabilityId && !capabilities.includes(capabilityId)) capabilities.push(capabilityId);
  }
  return capabilities;
}

async function buildPartialSummary(
  batchDirectory: string,
  inputDirectory: string,
): Promise<Summary> {
  const [compactIndices, a2uiIndices, rejectedIndices] = await Promise.all([
    resultIndices(path.join(batchDirectory, "designcompactdsl"), /^q(\d+)\.jsonl$/),
    resultIndices(path.join(batchDirectory, "dsl"), /^q(\d+)\.jsonl$/),
    resultIndices(path.join(batchDirectory, "rejected"), /^q(\d+)$/),
  ]);
  const finalIndices = new Set([...compactIndices, ...a2uiIndices]);
  const indices = [...new Set([...finalIndices, ...rejectedIndices])]
    .sort((left, right) => left - right);
  if (!indices.length) {
    throw new Error("批次目录没有可导出的最终结果或 rejected 中间结果");
  }

  const results: SummaryResult[] = [];
  for (const index of indices) {
    const input = await loadInput(index, inputDirectory);
    const content = input.content ?? {};
    const size = content.size ?? input.size;
    if (size !== "2x2" && size !== "2x4") {
      const filename = `Q${String(index).padStart(3, "0")}.json`;
      throw new Error(`部分结果 ${filename} 缺少合法 size，请确认 --cards 指向原始任务目录`);
    }
    results.push({
      index,
      title: content.title ?? input.title ?? `Q${index}`,
      size,
      capabilities: inputCapabilities(input),
      status: "partial",
    });
  }
  return {
    round: `${path.basename(batchDirectory)}（部分结果）`,
    total: results.length,
    success: 0,
    failed: 0,
    partial: results.length,
    results,
  };
}

function rejectedVariantLabel(caller: string, filename: string): string {
  const callerIndex = Number(caller.replace("caller-", ""));
  const match = /^(\d+)\.(initial|repair)\.attempt-(\d+)\.rejected\.jsonl$/.exec(filename);
  if (!match) return `请求 ${callerIndex + 1} · ${filename}`;
  const phase = match[2] === "initial" ? "初始输出" : `修复第 ${match[3]} 轮`;
  return `请求 ${callerIndex + 1} · ${phase}`;
}

async function loadRejectedVariants(
  index: number,
  batchDirectory: string,
): Promise<RenderedVariant[]> {
  const caseDirectory = path.join(batchDirectory, "rejected", `q${index}`);
  let callers: string[];
  try {
    callers = (await readdir(caseDirectory, { withFileTypes: true }))
      .filter(entry => entry.isDirectory() && /^caller-\d+$/.test(entry.name))
      .map(entry => entry.name)
      .sort();
  } catch (error) {
    if ((error as NodeJS.ErrnoException).code === "ENOENT") return [];
    throw error;
  }

  const variants: RenderedVariant[] = [];
  for (const caller of callers) {
    const callerDirectory = path.join(caseDirectory, caller);
    const filenames = (await readdir(callerDirectory))
      .filter(filename => filename.endsWith(".rejected.jsonl"))
      .sort();
    for (const filename of filenames) {
      const sourcePath = path.join(callerDirectory, filename);
      const issuesPath = sourcePath.replace(/\.jsonl$/, ".issues.json");
      const compactDsl = await readFile(sourcePath, "utf8");
      variants.push({
        key: `${caller}/${filename}`,
        label: rejectedVariantLabel(caller, filename),
        compactDsl,
        issues: await readOptional(issuesPath),
        componentTypes: componentTypes(compactDsl),
        warnings: [],
        renderedMarkup: "",
        renderError: "",
        rejected: true,
      });
    }
  }
  return variants;
}

async function loadCase(
  result: SummaryResult,
  batchDirectory: string,
  inputDirectory: string,
): Promise<RenderedCase> {
  const basename = `q${result.index}.jsonl`;
  const [input, compactDsl, cloudA2ui, rejectedVariants] = await Promise.all([
    loadInput(result.index, inputDirectory),
    readOptional(path.join(batchDirectory, "designcompactdsl", basename)),
    readOptional(path.join(batchDirectory, "dsl", basename)),
    loadRejectedVariants(result.index, batchDirectory),
  ]);
  const content = input.content ?? {};
  const finalVariant: RenderedVariant = {
    key: "final",
    label: compactDsl || cloudA2ui ? "最终结果" : "最终结果（未生成）",
    compactDsl,
    issues: "",
    componentTypes: componentTypes(compactDsl),
    warnings: [],
    renderedMarkup: "",
    renderError: "",
    rejected: false,
  };

  return {
    ...result,
    title: result.title || content.title || input.title || `Q${result.index}`,
    size: result.size || content.size || input.size || "2x2",
    userQuery: content.userQuery || input.userQuery || "",
    appVersion: content.appVersion || input.appVersion || input.deviceInfo?.prdVer,
    compactDsl,
    cloudA2ui,
    componentTypes: componentTypes(compactDsl),
    warnings: [],
    renderedMarkup: "",
    renderError: "",
    variants: [finalVariant, ...rejectedVariants],
  };
}

function renderVariant(
  variant: RenderedVariant,
  size: CardSize,
  dataUris: Map<string, string>,
  a2ui: string,
  conversionError = "",
): void {
  if (!a2ui) {
    variant.renderError = conversionError
      || (variant.compactDsl ? "正式 Python 转换器没有返回 A2UI" : "没有最终 Compact DSL 产物");
    return;
  }
  try {
    const compiled = compileA2uiJsonl(a2ui, { size });
    variant.warnings = compiled.warnings;
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
    variant.renderedMarkup = inlineAssets(markup, dataUris);
  } catch (error) {
    variant.renderError = error instanceof Error ? error.message : String(error);
  }
}

function conversionKey(item: RenderedCase, variant: RenderedVariant): string {
  return `q${item.index}:${variant.key}`;
}

async function renderCases(
  cases: RenderedCase[],
  dataUris: Map<string, string>,
): Promise<void> {
  const requests: PythonConversionRequest[] = [];
  for (const item of cases) {
    for (const [index, variant] of item.variants.entries()) {
      if (!variant.compactDsl) continue;
      if (index === 0 && item.cloudA2ui) continue;
      requests.push({
        key: conversionKey(item, variant),
        source: variant.compactDsl,
        size: item.size,
        preview: variant.rejected,
        appVersion: item.appVersion,
      });
    }
  }
  const conversions = await convertCompactVariants(requests);
  for (const item of cases) {
    for (const [index, variant] of item.variants.entries()) {
      const conversion = conversions.get(conversionKey(item, variant));
      const a2ui = index === 0 && item.cloudA2ui ? item.cloudA2ui : conversion?.genui ?? "";
      renderVariant(variant, item.size, dataUris, a2ui, conversion?.error);
    }
    const finalVariant = item.variants[0];
    item.warnings = finalVariant.warnings;
    item.renderedMarkup = finalVariant.renderedMarkup;
    item.renderError = finalVariant.renderError;
    item.componentTypes = finalVariant.componentTypes;
  }
}

function badges(values: string[], className = "badge"): string {
  return values.map(value => `<span class="${className}">${escapeHtml(value)}</span>`).join("");
}

function details(label: string, content: string, open = false): string {
  if (!content) return "";
  return `<details${open ? " open" : ""}><summary>${escapeHtml(label)}</summary><pre>${escapeHtml(content)}</pre></details>`;
}

function renderVariantPanel(item: RenderedCase, variant: RenderedVariant, index: number): string {
  const width = item.size === "2x4" ? 300 : 150;
  const preview = variant.renderedMarkup
    ? `<div class="cardViewport" style="width:${width}px;height:150px">${variant.renderedMarkup}</div>`
    : `<div class="renderFailure"><strong>无法渲染</strong><span>${escapeHtml(variant.renderError || "没有可渲染产物")}</span></div>`;
  const warnings = variant.warnings.length
    ? `<div class="warningBox"><strong>Renderer 警告</strong>${variant.warnings.map(warning => `<p>${escapeHtml(warning)}</p>`).join("")}</div>`
    : "";
  return `<section class="variantPanel" data-variant-panel="${escapeHtml(variant.key)}"${index === 0 ? "" : " hidden"}>
    <div class="metaRow">${badges(variant.componentTypes, "componentBadge")}</div>
    <div class="previewStage">${preview}<span class="dimension">${width} × 150 · ${variant.rejected ? "rejected 宽松预览" : "最终结果"}</span></div>
    ${warnings}
    <div class="detailsStack">
      ${details(variant.rejected ? "Rejected Compact DSL" : "Compact DSL", variant.compactDsl, Boolean(variant.renderError))}
      ${variant.issues ? details("当轮校验问题", variant.issues) : ""}
      ${variant.renderError ? details("Renderer 错误", variant.renderError, true) : ""}
    </div>
  </section>`;
}

function renderCase(item: RenderedCase): string {
  const renderStatus = item.renderedMarkup ? "rendered" : "failed";
  const search = [
    item.index,
    item.title,
    item.userQuery,
    item.size,
    item.status,
    item.errorCode,
    ...item.componentTypes,
    ...item.variants.flatMap(variant => [variant.label, ...variant.componentTypes]),
    ...(item.capabilities ?? []),
  ].join(" ").toLocaleLowerCase();
  const statusClass = item.status === "success"
    ? "success"
    : item.status === "partial" ? "partial" : "failure";
  const selector = item.variants.length > 1
    ? `<label class="variantPicker"><span>查看版本</span><select data-variant-select>${item.variants.map(variant => `<option value="${escapeHtml(variant.key)}">${escapeHtml(variant.label)}</option>`).join("")}</select></label>`
    : `<span class="finalOnly">仅有最终结果</span>`;
  const repairAttempts = item.repairAttemptsByRound?.length
    ? item.repairAttemptsByRound
      .map((count, index) => `第${index + 1}轮:${count ?? "未记录"}`)
      .join(" / ")
    : "未记录";
  const totalRepairAttempts = item.totalRepairAttempts ?? "未记录";

  return `<article class="caseCard" data-case data-size="${item.size}" data-status="${item.status}" data-render="${renderStatus}" data-search="${escapeHtml(search)}">
    <header class="caseHead">
      <div><span class="caseIndex">Q${String(item.index).padStart(3, "0")}</span><h2>${escapeHtml(item.title)}</h2></div>
      <div class="statusGroup"><span class="status ${statusClass}">${escapeHtml(item.status)}</span><span class="size">${item.size}</span></div>
    </header>
    <p class="query">${escapeHtml(item.userQuery || "未读取到用户问题")}</p>
    <div class="variantBar">${selector}<span class="rejectedCount">${item.variants.length - 1} 个 rejected 版本</span></div>
    ${item.variants.map((variant, index) => renderVariantPanel(item, variant, index)).join("\n")}
    <div class="caseFacts">
      <span>耗时 <b>${Math.round(item.elapsed_ms ?? 0)} ms</b></span>
      <span>本轮尝试 <b>${item.attempts ?? 0}</b></span>
      <span>累计尝试 <b>${item.totalAttempts ?? item.attempts ?? 0}</b></span>
      <span>修复总计 <b>${escapeHtml(String(totalRepairAttempts))}</b></span>
      <span>各轮修复 <b>${escapeHtml(repairAttempts)}</b></span>
      <span>Rejected <b>${item.variants.length - 1}</b></span>
    </div>
  </article>`;
}

function pageStyles(): string {
  return `
    :root { color-scheme:light; --surface:#fffdf7; --page:#f5f3eb; --toolbar:#eeeee5; --line:#d7ddd3; --text:#233831; --muted:#63736b; --blue:#176c56; --green:#176c56; --red:#ae4636; --amber:#956415; }
    * { box-sizing:border-box; }
    html { scroll-behavior:smooth; }
    body { margin:0; color:var(--text); background:var(--page); font-family:"HarmonyOS Sans SC","HarmonyOS Sans","PingFang SC",sans-serif; }
    button,input { font:inherit; }
    .topbar { position:sticky; top:0; z-index:10; display:flex; justify-content:space-between; gap:20px; padding:16px 28px; border-bottom:1px solid var(--line); background:rgba(245,243,235,.95); backdrop-filter:blur(14px); }
    .topbar h1 { margin:0; font-size:18px; }
    .topbar p { margin:4px 0 0; color:var(--muted); font-size:12px; }
    .summary { display:flex; align-items:center; gap:8px; flex-wrap:wrap; }
    .metric { min-width:72px; padding:7px 10px; border:1px solid var(--line); border-top:3px solid var(--blue); border-radius:4px; background:var(--surface); text-align:center; }
    .metric b { display:block; font-size:16px; }
    .metric span { color:var(--muted); font-size:10px; }
    main { max-width:1480px; margin:0 auto; padding:22px 28px 80px; }
    .toolbar { position:sticky; top:82px; z-index:9; display:flex; align-items:center; gap:12px; margin-bottom:20px; padding:12px; border:1px solid var(--line); border-radius:4px; background:rgba(238,238,229,.96); backdrop-filter:blur(12px); }
    .toolbar input { flex:1; min-width:160px; padding:9px 12px; border:1px solid var(--line); border-radius:4px; outline:none; background:var(--surface); }
    .filters { display:flex; gap:5px; flex-wrap:wrap; }
    .filters button { padding:7px 11px; border:1px solid var(--line); border-radius:4px; color:var(--muted); background:var(--surface); cursor:pointer; }
    .filters button[aria-pressed="true"] { color:#fff; border-color:var(--blue); background:var(--blue); }
    .count { color:var(--muted); font-size:12px; white-space:nowrap; }
    .grid { display:grid; grid-template-columns:repeat(auto-fill,minmax(390px,1fr)); gap:18px; align-items:start; }
    .caseCard { overflow:hidden; border:1px solid var(--line); border-radius:4px; background:var(--surface); box-shadow:0 5px 22px rgba(35,56,49,.05); }
    .caseHead { display:flex; justify-content:space-between; gap:12px; padding:16px 18px 0; }
    .caseHead > div:first-child { display:flex; align-items:center; gap:9px; min-width:0; }
    .caseHead h2 { margin:0; overflow:hidden; font-size:15px; white-space:nowrap; text-overflow:ellipsis; }
    .caseIndex { color:var(--muted); font-family:ui-monospace,monospace; font-size:11px; }
    .statusGroup,.metaRow { display:flex; align-items:center; gap:6px; flex-wrap:wrap; }
    .status,.size,.badge,.componentBadge,.capabilityBadge { padding:3px 7px; border-radius:999px; font-size:9px; font-weight:600; }
    .status.success { color:var(--green); background:#e8f7f0; }
    .status.partial { color:var(--amber); background:#fff5d8; }
    .status.failure { color:var(--red); background:#fff0f0; }
    .size { color:#5c46b8; background:#f0edff; }
    .query { min-height:34px; margin:10px 18px 8px; color:var(--muted); font-size:11px; line-height:1.55; }
    .metaRow { min-height:21px; padding:9px 18px; border-top:1px solid var(--line); background:#f7f5ed; }
    .componentBadge { color:#176c56; background:#e9eee5; }
    .capabilityBadge { color:#765510; background:#fff5d8; }
    .variantBar { display:flex; align-items:end; justify-content:space-between; gap:12px; padding:10px 18px 12px; border-top:1px solid var(--line); background:#f7f5ed; }
    .variantPicker { display:flex; flex-direction:column; gap:3px; min-width:210px; color:var(--muted); font-size:9px; }
    .variantPicker select { max-width:100%; padding:7px 9px; border:1px solid #bfcac0; border-radius:4px; color:var(--text); background:var(--surface); font:inherit; font-size:11px; }
    .rejectedCount,.finalOnly { color:var(--muted); font-size:10px; }
    .previewStage { min-height:236px; padding:26px 18px 18px; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:12px; border-top:1px solid var(--line); border-bottom:1px solid var(--line); background:repeating-linear-gradient(0deg,#eff0e8 0,#eff0e8 1px,transparent 1px,transparent 16px),repeating-linear-gradient(90deg,#eff0e8 0,#eff0e8 1px,transparent 1px,transparent 16px); }
    .cardViewport { flex:0 0 auto; overflow:hidden; isolation:isolate; border-radius:20px; background:#fff; box-shadow:0 14px 34px rgba(24,32,51,.15); }
    .dimension { color:var(--muted); font-family:ui-monospace,monospace; font-size:9px; }
    .renderFailure { width:min(300px,100%); min-height:150px; display:flex; flex-direction:column; align-items:center; justify-content:center; gap:7px; padding:18px; border:1px dashed #efb0b0; border-radius:14px; color:var(--red); background:#fff7f7; text-align:center; }
    .renderFailure span { font-size:10px; overflow-wrap:anywhere; }
    .warningBox { margin:12px 18px 0; padding:9px 11px; border-left:3px solid var(--amber); color:#815d00; background:#fff5d8; font-size:10px; }
    .warningBox p { margin:4px 0 0; }
    .caseFacts { display:flex; flex-wrap:wrap; gap:8px 14px; padding:12px 18px; color:var(--muted); font-size:10px; }
    .caseFacts b { color:var(--text); }
    .detailsStack { padding:0 18px 16px; display:flex; flex-direction:column; gap:7px; }
    details { border:1px solid var(--line); border-radius:4px; background:#f7f5ed; }
    summary { padding:8px 10px; color:#3856a8; cursor:pointer; font-size:10px; font-weight:600; }
    pre { max-height:320px; margin:0; padding:11px; overflow:auto; border-top:1px solid var(--line); color:#344b43; background:#f0f1e9; font-family:ui-monospace,"SFMono-Regular",Menlo,monospace; font-size:9px; line-height:1.55; white-space:pre-wrap; overflow-wrap:anywhere; }
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
      for (const select of document.querySelectorAll('[data-variant-select]')) {
        select.addEventListener('change', () => {
          const card = select.closest('[data-case]');
          for (const panel of card.querySelectorAll('[data-variant-panel]')) {
            panel.hidden = panel.dataset.variantPanel !== select.value;
          }
        });
      }
    })();
  `;
}

function renderDocument(summary: Summary, cases: RenderedCase[]): string {
  const rendered = cases.filter(item => item.renderedMarkup).length;
  const renderFailed = cases.filter(item => !item.renderedMarkup).length;
  const warnings = cases.reduce((total, item) => total + item.warnings.length, 0);
  const rejected = cases.reduce((total, item) => total + item.variants.length - 1, 0);
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
    <div><h1>${escapeHtml(title)}</h1><p>最终结果复用云侧 A2UI，中间结果使用正式 Python 转换器与 @genui-sdk/renderer 生成 · ${escapeHtml(summary.timestamp ?? "")}</p></div>
    <div class="summary">
      <div class="metric"><b>${cases.length}</b><span>总任务</span></div>
      <div class="metric"><b>${summary.success ?? 0}</b><span>生成成功</span></div>
      ${summary.partial ? `<div class="metric"><b>${summary.partial}</b><span>部分结果</span></div>` : ""}
      <div class="metric"><b>${rendered}</b><span>渲染成功</span></div>
      <div class="metric"><b>${summary.failed ?? 0}</b><span>生成失败</span></div>
      <div class="metric"><b>${renderFailed}</b><span>渲染失败</span></div>
      <div class="metric"><b>${rejected}</b><span>Rejected 版本</span></div>
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
        ${summary.partial ? `<button type="button" aria-pressed="false" data-filter="partial">部分结果</button>` : ""}
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
  const summaryPath = path.join(batchDirectory, "summary.json");
  let summary: Summary;
  if (existsSync(summaryPath)) {
    summary = JSON.parse(await readFile(summaryPath, "utf8")) as Summary;
  } else if (process.argv.includes("--partial")) {
    summary = await buildPartialSummary(batchDirectory, inputDirectory);
  } else {
    throw new Error(`批次目录缺少 summary.json：${summaryPath}`);
  }
  const cases = await Promise.all(
    summary.results.map(result => loadCase(result, batchDirectory, inputDirectory)),
  );
  const dataUris = await loadAssetDataUris(
    cases.flatMap(item => item.variants.map(variant => variant.compactDsl)),
  );
  await renderCases(cases, dataUris);
  const document = renderDocument(summary, cases);
  await mkdir(path.dirname(outputPath), { recursive: true });
  await writeFile(outputPath, document, "utf8");

  const rendered = cases.filter(item => item.renderedMarkup).length;
  const errors = cases.filter(item => item.renderError);
  const rejected = cases.reduce((total, item) => total + item.variants.length - 1, 0);
  console.log(`已导出 ${cases.length} 条最终结果和 ${rejected} 条 rejected 中间结果，其中 ${rendered} 条最终结果由 Renderer 成功渲染：${outputPath}`);
  if (errors.length) {
    console.log(`Renderer 失败 ${errors.length} 条：${errors.map(item => `Q${item.index} ${item.renderError}`).join("；")}`);
  }
}

void main().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
