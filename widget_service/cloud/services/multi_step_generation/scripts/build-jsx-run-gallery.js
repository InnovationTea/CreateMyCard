#!/usr/bin/env node

const fs = require("node:fs");
const path = require("node:path");

function loadBabelParser() {
  try {
    return require("@babel/parser");
  } catch (error) {
    throw new Error("缺少 @babel/parser。请先执行 npm install。", { cause: error });
  }
}

function usage(exitCode = 0) {
  const stream = exitCode === 0 ? process.stdout : process.stderr;
  stream.write(`用法：\n  node scripts/build-jsx-run-gallery.js --run-dir <批次目录> [--output <HTML路径>]\n\n示例：\n  node scripts/build-jsx-run-gallery.js --run-dir outputs-a2ui/20260823-145804\n`);
  process.exit(exitCode);
}

function parseArgs(argv) {
  const result = {};
  for (let index = 0; index < argv.length; index += 1) {
    const argument = argv[index];
    if (argument === "--help" || argument === "-h") usage(0);
    if (argument === "--run-dir" || argument === "--output") {
      const value = argv[index + 1];
      if (!value || value.startsWith("--")) throw new Error(`${argument} 缺少参数值`);
      result[argument.slice(2).replace(/-([a-z])/g, (_, letter) => letter.toUpperCase())] = value;
      index += 1;
      continue;
    }
    throw new Error(`未知参数：${argument}`);
  }
  if (!result.runDir) throw new Error("必须通过 --run-dir 指定一个批次目录");
  return result;
}

function readJson(filePath, fallback = null) {
  if (!fs.existsSync(filePath)) return fallback;
  return JSON.parse(fs.readFileSync(filePath, "utf8"));
}

function posixPath(filePath) {
  return filePath.split(path.sep).join("/");
}

function relativeHref(fromDir, targetPath) {
  const relative = posixPath(path.relative(fromDir, targetPath));
  return encodeURI(relative.startsWith(".") ? relative : `./${relative}`);
}

function unique(values) {
  return [...new Set(values.filter(Boolean))];
}

function finiteNumber(value, fallback = 0) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function formatSeconds(value) {
  const seconds = finiteNumber(value);
  if (seconds >= 60) return `${Math.floor(seconds / 60)}分${(seconds % 60).toFixed(1)}秒`;
  return `${seconds.toFixed(2)}秒`;
}

function findRejectedJsx(runDir, componentName) {
  const rejectedDir = path.join(runDir, "rejected");
  if (!fs.existsSync(rejectedDir)) return null;
  const prefix = `${componentName}.turn-`;
  const candidates = fs.readdirSync(rejectedDir, { withFileTypes: true })
    .filter((entry) => entry.isFile() && entry.name.startsWith(prefix) && entry.name.endsWith(".rejected.jsx"))
    .map((entry) => ({
      path: path.join(rejectedDir, entry.name),
      turn: finiteNumber(entry.name.match(/\.turn-(\d+)\./)?.[1], -1),
    }))
    .sort((left, right) => right.turn - left.turn || right.path.localeCompare(left.path));
  return candidates[0]?.path || null;
}

function collectRetryReasons(trace) {
  const reasons = [];
  for (const turn of trace?.turn_trace || []) {
    if (turn.target !== "submit_card_jsx" || turn.tool_result?.ok !== false) continue;
    const findings = Array.isArray(turn.tool_result.findings) ? turn.tool_result.findings : [];
    if (findings.length) {
      for (const finding of findings) {
        const prefix = finding.code ? `[${finding.code}] ` : "";
        reasons.push(`${prefix}${finding.message || finding.error || "提交校验失败"}`);
      }
    } else {
      reasons.push(turn.tool_result.error || turn.tool_result.message || "提交校验失败");
    }
  }
  if (trace?.error) reasons.push(trace.error);
  return unique(reasons);
}

function sumApiSeconds(trace) {
  return (trace?.turn_trace || []).reduce(
    (sum, turn) => sum + finiteNumber(turn.api_elapsed_seconds),
    0,
  );
}

function inferFailedSubmissions(trace) {
  if (Number.isFinite(Number(trace?.failed_submissions))) return Number(trace.failed_submissions);
  return (trace?.turn_trace || []).filter(
    (turn) => turn.target === "submit_card_jsx" && turn.tool_result?.ok === false,
  ).length;
}

function assertRunDirectory(runDir) {
  if (!fs.existsSync(runDir) || !fs.statSync(runDir).isDirectory()) {
    throw new Error(`批次目录不存在：${runDir}`);
  }
  for (const required of ["manifest.json", "traces.json"]) {
    if (!fs.existsSync(path.join(runDir, required))) {
      throw new Error(`批次目录缺少 ${required}：${runDir}`);
    }
  }
}

function buildEntries({ runDir, outputDir, manifest, traces, babelParser }) {
  const manifestCards = new Map((manifest.cards || []).map((card) => [card.componentName, card]));
  const traceByName = new Map((traces || []).map((trace) => [trace.component_name, trace]));
  const orderedNames = [];
  for (const trace of traces || []) if (trace.component_name && !orderedNames.includes(trace.component_name)) orderedNames.push(trace.component_name);
  for (const card of manifest.cards || []) if (card.componentName && !orderedNames.includes(card.componentName)) orderedNames.push(card.componentName);

  return orderedNames.map((componentName, order) => {
    const trace = traceByName.get(componentName) || {};
    const manifestCard = manifestCards.get(componentName) || {};
    const finalJsxPath = manifestCard.jsx ? path.resolve(runDir, manifestCard.jsx) : path.join(runDir, "jsx", `${componentName}.jsx`);
    const hasFinalJsx = fs.existsSync(finalJsxPath);
    const rejectedJsxPath = hasFinalJsx ? null : findRejectedJsx(runDir, componentName);
    const sourcePath = hasFinalJsx ? finalJsxPath : rejectedJsxPath;
    let sourceKind = "none";
    if (hasFinalJsx) sourceKind = "final";
    else if (rejectedJsxPath) sourceKind = "rejected";
    let source = null;
    let compileError = null;
    if (sourcePath) {
      source = fs.readFileSync(sourcePath, "utf8");
      try {
        babelParser.parse(source, { sourceType: "script", plugins: ["jsx"] });
      } catch (error) {
        compileError = error.message;
        source = null;
      }
    }

    const reasons = collectRetryReasons(trace);
    const semanticStatus = trace.semantic_status || manifestCard.semanticStatus || null;
    const finalStatus = trace.status || manifestCard.status || "failed";
    const isPartial = semanticStatus
      ? semanticStatus !== "completed"
      : String(finalStatus).startsWith("partial") || String(finalStatus).startsWith("insufficient");
    let state = "failed";
    if (hasFinalJsx) state = isPartial ? "partial" : "success";
    const validationReports = Array.isArray(trace.validation_reports) ? trace.validation_reports : [];
    const validationFailures = validationReports.reduce(
      (count, report) => count + (Array.isArray(report.findings) ? report.findings.filter((finding) => finding.severity !== "warning").length : 0),
      0,
    );
    const warnings = validationReports.reduce(
      (count, report) => count + (Array.isArray(report.findings) ? report.findings.filter((finding) => finding.severity === "warning").length : 0),
      0,
    ) + (Array.isArray(trace.warnings) ? trace.warnings.length : 0);
    const taskId = trace.task_id ?? manifestCard.taskId ?? order + 1;
    const task = trace.task || {};
    const contextPath = manifestCard.context
      ? path.resolve(runDir, manifestCard.context)
      : path.join(runDir, "context", `${componentName}.context.json`);
    const context = readJson(contextPath, null);

    return {
      order,
      taskId,
      componentName,
      size: task.size || "unknown",
      query: task.userQuery || "",
      state,
      status: finalStatus,
      semanticStatus: semanticStatus || "unknown",
      validationStatus: trace.browser_validation || manifestCard.validationStatus || "unknown",
      elapsedSeconds: finiteNumber(trace.elapsed_seconds),
      apiSeconds: sumApiSeconds(trace),
      modelCalls: Array.isArray(trace.turn_trace) ? trace.turn_trace.length : finiteNumber(trace.turns),
      failedSubmissions: inferFailedSubmissions(trace),
      repairCalls: finiteNumber(trace.repair_calls),
      validationFailures,
      warnings,
      reasons,
      sourceKind,
      sourceName: sourcePath ? path.basename(sourcePath) : null,
      sourceHref: sourcePath ? relativeHref(outputDir, sourcePath) : null,
      source,
      compileError,
      context,
    };
  });
}

function safeJson(value) {
  return JSON.stringify(value).replace(/</g, "\\u003c").replace(/\u2028/g, "\\u2028").replace(/\u2029/g, "\\u2029");
}

function collectEmbeddedSvgAssets(entries, skillDir) {
  const references = new Set();
  const quotedSvg = /["']([^"'\r\n]+\.svg)["']/gi;
  for (const entry of entries) {
    if (!entry.source) continue;
    for (const match of entry.source.matchAll(quotedSvg)) references.add(match[1]);
  }

  const root = path.resolve(skillDir);
  const rootPrefix = `${root}${path.sep}`;
  const assets = {};
  for (const reference of references) {
    if (/^(?:[a-z]+:|\/|data:)/i.test(reference)) continue;
    const normalized = reference.replace(/\\/g, "/").replace(/^\.\//, "");
    if (normalized.startsWith("../")) continue;
    const assetPath = normalized.includes("/")
      ? normalized
      : `resources/base/media/${normalized}`;
    const resolved = path.resolve(skillDir, ...assetPath.split("/"));
    if (resolved !== root && !resolved.startsWith(rootPrefix)) continue;
    if (!fs.existsSync(resolved) || !fs.statSync(resolved).isFile()) continue;
    const dataUri = `data:image/svg+xml;base64,${fs.readFileSync(resolved).toString("base64")}`;
    assets[normalized] = dataUri;
    assets[assetPath] = dataUri;
  }
  return assets;
}

function withGalleryAssetBase(runtimeSource, assetBaseHref, embeddedAssets) {
  const functionMarker = "  function assetUrl(value) {";
  const functionStart = runtimeSource.indexOf(functionMarker);
  if (functionStart < 0) {
    throw new Error("design-system-runtime.jsx 缺少 assetUrl()，无法配置 gallery 资源路径");
  }

  const functionTail = runtimeSource.slice(functionStart);
  const functionEndMatch = functionTail.match(/\r?\n  }\r?\n/);
  if (!functionEndMatch) {
    throw new Error("无法识别 design-system-runtime.jsx 中 assetUrl() 的结束位置");
  }

  const lineBreak = runtimeSource.includes("\r\n") ? "\r\n" : "\n";
  const functionEnd = functionStart + functionEndMatch.index + functionEndMatch[0].length;
  const replacement = [
    `  const GALLERY_EMBEDDED_ASSETS = Object.freeze(${safeJson(embeddedAssets)});`,
    "",
    "  function assetUrl(value) {",
    "    if (!value) return \"\";",
    "    if (/^(?:[a-z]+:|\\/|data:)/i.test(value)) return value;",
    "    const normalized = String(value).replace(/\\\\/g, \"/\");",
    "    if (normalized.startsWith(\"./\") || normalized.startsWith(\"../\")) return normalized;",
    "    const assetPath = normalized.includes(\"/\")",
    "      ? normalized",
    "      : `${ASSET_ROOT}${normalized.includes(\".\") ? normalized : `${normalized}.svg`}`;",
    "    const embedded = GALLERY_EMBEDDED_ASSETS[normalized] || GALLERY_EMBEDDED_ASSETS[assetPath];",
    "    if (embedded) return embedded;",
    `    return ${JSON.stringify(assetBaseHref)} + assetPath;`,
    "  }",
    "",
  ].join(lineBreak);

  return runtimeSource.slice(0, functionStart) + replacement + runtimeSource.slice(functionEnd);
}

function buildBrowserSource({ runtimeSource, entries }) {
  const renderable = entries.filter((entry) => entry.source);
  const cardSources = renderable.map((entry) => entry.source).join("\n\n");
  const registryLines = renderable.map(
    (entry) => `${JSON.stringify(entry.componentName)}: typeof ${entry.componentName} === "function" ? ${entry.componentName} : null`,
  );
  const publicEntries = entries.map(({ source, ...entry }) => entry);

  const appSource = `
const JSX_BINDING_RUNTIME = window.JsxBindingPreview.createBoundDesignSystem(
  React,
  window.ClawWidgetDesignSystem,
);
const BindingProvider = JSX_BINDING_RUNTIME.Provider;
const {
  Card, Stack, Grid, Icon, AppIcon, WeatherIcon, SingleLineTitle, DoubleLineTitle,
  Badge, DataDisplay, InfoBlock, TopTextBottomValue, TableText, TextBlock,
  EmphasizedData, EmphasisText, SecondaryBody, Summary, WeatherSummaryCard,
  SecondaryBodyCard, ProgressLine1, ProgressLine2, ProgressCircleSingle,
  ProgressCircle, NumericRatio, NumericRatioStack, ChecklistItem, EventCard,
  H_BarChart, Gauge, PillButton, CircleButton, CardButton,
} = JSX_BINDING_RUNTIME.components;

const RUN_ENTRIES = ${safeJson(publicEntries)};
const CARD_REGISTRY = { ${registryLines.join(",\n")} };

function formatSeconds(value) {
  const seconds = Number.isFinite(Number(value)) ? Number(value) : 0;
  if (seconds >= 60) return Math.floor(seconds / 60) + "分" + (seconds % 60).toFixed(1) + "秒";
  return seconds.toFixed(2) + "秒";
}

class CardErrorBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }
  static getDerivedStateFromError(error) {
    return { error };
  }
  render() {
    if (this.state.error) {
      return <div className="render-error"><strong>JSX 运行失败</strong><span>{this.state.error.message}</span></div>;
    }
    return this.props.children;
  }
}

function Metric({ label, value }) {
  return <span className="metric"><b>{value}</b><small>{label}</small></span>;
}

function ResultItem({ entry }) {
  const Component = CARD_REGISTRY[entry.componentName];
  const reasons = entry.reasons || [];
  return (
    <article className="result-item" data-state={entry.state} data-size={entry.size} data-search={(entry.componentName + " " + entry.query).toLowerCase()}>
      <header className="item-head">
        <div>
          <span className={"status-badge " + entry.state}>{entry.state === "success" ? "成功" : entry.state === "partial" ? "部分完成" : "失败"}</span>
          <h2>{entry.componentName}</h2>
        </div>
        <span className="task-id">任务 {entry.taskId} · {entry.size}</span>
      </header>
      <div className="card-stage">
        {Component ? (
          <CardErrorBoundary>
            <BindingProvider context={entry.context}>
              <Component />
            </BindingProvider>
          </CardErrorBoundary>
        ) : (
          <div className="render-error">
            <strong>{entry.sourceKind === "none" ? "没有可渲染的 JSX" : "JSX 无法编译"}</strong>
            <span>{entry.compileError || "该任务没有最终 JSX，也没有可用的 rejected JSX。"}</span>
          </div>
        )}
      </div>
      <div className="metrics">
        <Metric label="总耗时" value={formatSeconds(entry.elapsedSeconds)} />
        <Metric label="API 累计" value={formatSeconds(entry.apiSeconds)} />
        <Metric label="模型调用" value={entry.modelCalls} />
        <Metric label="提交拒绝" value={entry.failedSubmissions} />
      </div>
      <p className="query" title={entry.query}>{entry.query || "未记录 userQuery"}</p>
      <div className="artifact-row">
        {entry.sourceHref ? <a href={entry.sourceHref} target="_blank" rel="noreferrer">{entry.sourceName}</a> : <span>无 JSX 文件</span>}
        <span>{entry.sourceKind === "final" ? "最终 JSX" : entry.sourceKind === "rejected" ? "最后一次 rejected JSX" : "错误记录"}</span>
      </div>
      <details className="details" open={entry.state === "failed"}>
        <summary>校验与重试明细</summary>
        <dl>
          <div><dt>运行状态</dt><dd>{entry.status}</dd></div>
          <div><dt>语义状态</dt><dd>{entry.semanticStatus}</dd></div>
          <div><dt>浏览器校验</dt><dd>{entry.validationStatus}</dd></div>
          <div><dt>修复调用</dt><dd>{entry.repairCalls}</dd></div>
          <div><dt>校验记录错误 / 警告</dt><dd>{entry.validationFailures} / {entry.warnings}</dd></div>
        </dl>
        {reasons.length ? <ol>{reasons.map((reason, index) => <li key={index}>{reason}</li>)}</ol> : <p className="no-reason">没有提交拒绝记录。</p>}
      </details>
    </article>
  );
}

function RunGallery() {
  const [filter, setFilter] = React.useState("all");
  const [search, setSearch] = React.useState("");
  const visible = RUN_ENTRIES.filter((entry) => {
    const matchesState = filter === "all" || entry.state === filter;
    const haystack = (entry.componentName + " " + entry.query + " " + entry.taskId).toLowerCase();
    return matchesState && haystack.includes(search.trim().toLowerCase());
  });
  return (
    <React.Fragment>
      <section className="toolbar" aria-label="筛选">
        <div className="filter-buttons">
          {["all", "success", "partial", "failed"].map((value) => (
            <button key={value} className={filter === value ? "active" : ""} onClick={() => setFilter(value)}>
              {value === "all" ? "全部" : value === "success" ? "成功" : value === "partial" ? "部分完成" : "失败"}
            </button>
          ))}
        </div>
        <input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="搜索任务、组件名或需求" />
        <span className="visible-count">显示 {visible.length} / {RUN_ENTRIES.length}</span>
      </section>
      <main className="gallery">
        {visible.map((entry) => <ResultItem key={entry.componentName} entry={entry} />)}
      </main>
    </React.Fragment>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<RunGallery />);
document.documentElement.dataset.jsxRunGallery = "mounted";
`;
  return `${runtimeSource}\n${cardSources}\n${appSource}`.replace(/<\/script/gi, "<\\/script");
}

function buildHtml({ manifest, entries, bundle, runDir, outputPath }) {
  const runId = manifest.runId || path.basename(runDir);
  const totalElapsed = entries.reduce((sum, entry) => sum + entry.elapsedSeconds, 0);
  const averageElapsed = entries.length ? totalElapsed / entries.length : 0;
  const finalCount = entries.filter((entry) => entry.sourceKind === "final").length;
  const failedCount = entries.filter((entry) => entry.state === "failed").length;
  const partialCount = entries.filter((entry) => entry.state === "partial").length;
  const totalCalls = entries.reduce((sum, entry) => sum + entry.modelCalls, 0);
  const totalRejected = entries.reduce((sum, entry) => sum + entry.failedSubmissions, 0);
  const outputDir = path.dirname(outputPath);
  const manifestHref = relativeHref(outputDir, path.join(runDir, "manifest.json"));
  const tracesHref = relativeHref(outputDir, path.join(runDir, "traces.json"));
  const escape = (value) => String(value ?? "")
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

  return `<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>${escape(runId)} · JSX 批次预览</title>
<style>
*{box-sizing:border-box}html,body{margin:0;min-height:100%;font-family:"HarmonyOS Sans SC","HarmonyOS Sans",-apple-system,BlinkMacSystemFont,"PingFang SC","Microsoft YaHei",sans-serif;color:#1f2937;background:#eef1f5}body{padding:32px 24px 64px}.page-shell{max-width:1600px;margin:0 auto}.page-head{text-align:center;margin:0 auto 24px}.page-head h1{margin:0;font-size:26px}.page-head p{margin:8px 0 0;color:#667085;font-size:13px}.run-links{display:flex;justify-content:center;gap:14px;margin-top:10px}.run-links a{color:#0a59f7;text-decoration:none}.run-summary{display:flex;flex-wrap:wrap;justify-content:center;gap:10px;margin:22px auto 0}.summary-chip{min-width:112px;padding:10px 14px;border:1px solid #d8dee8;border-radius:12px;background:#fff;box-shadow:0 3px 12px rgba(32,48,72,.05)}.summary-chip b{display:block;font-size:18px}.summary-chip span{display:block;margin-top:2px;color:#667085;font-size:11px}.toolbar{position:sticky;top:12px;z-index:30;display:flex;align-items:center;justify-content:center;flex-wrap:wrap;gap:12px;max-width:980px;margin:0 auto 26px;padding:10px 12px;border:1px solid rgba(210,217,229,.92);border-radius:16px;background:rgba(255,255,255,.93);box-shadow:0 8px 28px rgba(32,48,72,.1);backdrop-filter:blur(12px)}.filter-buttons{display:flex;gap:6px}.toolbar button{border:0;border-radius:9px;padding:8px 12px;background:#eef2f7;color:#475467;cursor:pointer}.toolbar button.active{background:#0a59f7;color:#fff}.toolbar input{width:min(320px,70vw);padding:8px 11px;border:1px solid #d0d7e2;border-radius:9px;background:#fff}.visible-count{font-size:12px;color:#667085}.gallery{display:flex;flex-wrap:wrap;justify-content:center;align-items:stretch;gap:24px}.result-item{display:flex;flex-direction:column;width:232px;min-height:390px;padding:16px;border:1px solid #dbe1ea;border-radius:18px;background:#fff;box-shadow:0 10px 30px rgba(30,42,64,.08)}.result-item[data-size="2x4"]{width:392px}.result-item[data-state="failed"]{border-color:#f3b5b5;background:#fffafa}.item-head{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;margin-bottom:12px}.item-head>div{display:flex;align-items:center;gap:8px;min-width:0}.item-head h2{overflow:hidden;margin:0;font-size:14px;white-space:nowrap;text-overflow:ellipsis}.status-badge{flex:none;padding:4px 7px;border-radius:999px;font-size:10px;font-weight:700}.status-badge.success{color:#14723d;background:#dff7e8}.status-badge.partial{color:#9a5b00;background:#fff0c7}.status-badge.failed{color:#b42318;background:#fee4e2}.task-id{flex:none;color:#667085;font-size:11px}.card-stage{display:flex;align-items:center;justify-content:center;min-height:184px;padding:12px;border-radius:14px;background-color:#e9edf2;background-image:linear-gradient(45deg,#f8f9fb 25%,transparent 25%),linear-gradient(-45deg,#f8f9fb 25%,transparent 25%),linear-gradient(45deg,transparent 75%,#f8f9fb 75%),linear-gradient(-45deg,transparent 75%,#f8f9fb 75%);background-position:0 0,0 8px,8px -8px,-8px 0;background-size:16px 16px;overflow:hidden}.render-error{display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;width:100%;min-height:156px;padding:14px;border:1px dashed #e98c8c;border-radius:12px;color:#9f2525;background:#fff6f6;text-align:center}.render-error span{max-height:90px;overflow:auto;font:11px/1.45 ui-monospace,monospace}.metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:6px;margin-top:12px}.metric{min-width:0;padding:7px 5px;border-radius:9px;background:#f5f7fa;text-align:center}.metric b{display:block;overflow:hidden;font-size:11px;white-space:nowrap;text-overflow:ellipsis}.metric small{display:block;margin-top:2px;color:#7b8494;font-size:9px}.query{display:-webkit-box;min-height:36px;margin:10px 0 8px;overflow:hidden;color:#4b5565;font-size:12px;line-height:18px;-webkit-box-orient:vertical;-webkit-line-clamp:2}.artifact-row{display:flex;align-items:center;justify-content:space-between;gap:8px;font-size:10px;color:#7b8494}.artifact-row a{overflow:hidden;color:#0a59f7;text-decoration:none;white-space:nowrap;text-overflow:ellipsis}.details{margin-top:10px;border-top:1px solid #e7eaf0;padding-top:8px;color:#596273;font-size:11px}.details summary{cursor:pointer;font-weight:600}.details dl{margin:8px 0}.details dl div{display:flex;justify-content:space-between;gap:10px;padding:2px 0}.details dt{color:#7b8494}.details dd{margin:0;text-align:right}.details ol{margin:8px 0 0;padding-left:18px;color:#a33}.details li+li{margin-top:4px}.no-reason{margin:8px 0 0;color:#7b8494}.fatal-error{max-width:900px;margin:20px auto;padding:16px;border-radius:12px;color:#fff;background:#7a1717;white-space:pre-wrap;font:12px/1.5 ui-monospace,monospace}@media(max-width:720px){body{padding:20px 10px 40px}.result-item,.result-item[data-size="2x4"]{width:min(100%,392px)}.toolbar{top:6px}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style>
<script>window.__showGalleryError=function(message){var el=document.getElementById("fatal-error");if(el){el.hidden=false;el.textContent=String(message||"Unknown gallery error")}}</script>
<script src="https://unpkg.com/react@18/umd/react.production.min.js" crossorigin onerror="this.onerror=null;this.src='https://cdn.jsdelivr.net/npm/react@18/umd/react.production.min.js'"></script>
<script src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js" crossorigin onerror="this.onerror=null;this.src='https://cdn.jsdelivr.net/npm/react-dom@18/umd/react-dom.production.min.js'"></script>
<script src="https://unpkg.com/@babel/standalone@7/babel.min.js" crossorigin onerror="this.onerror=null;this.src='https://cdn.jsdelivr.net/npm/@babel/standalone@7/babel.min.js'"></script>
</head>
<body>
<div class="page-shell">
  <header class="page-head">
    <h1>批次 ${escape(runId)} · JSX 生成结果</h1>
    <p>${escape(manifest.provider || "unknown")} / ${escape(manifest.model || "unknown")} · ${escape(manifest.startedAt || "未记录开始时间")} · 优先渲染最终 JSX，失败时回退最后一次 rejected JSX</p>
    <nav class="run-links"><a href="${manifestHref}" target="_blank">manifest.json</a><a href="${tracesHref}" target="_blank">traces.json</a></nav>
    <div class="run-summary">
      <div class="summary-chip"><b>${entries.length}</b><span>任务总数</span></div>
      <div class="summary-chip"><b>${finalCount}</b><span>有最终 JSX</span></div>
      <div class="summary-chip"><b>${partialCount}</b><span>部分完成</span></div>
      <div class="summary-chip"><b>${failedCount}</b><span>失败</span></div>
      <div class="summary-chip"><b>${formatSeconds(averageElapsed)}</b><span>平均每任务</span></div>
      <div class="summary-chip"><b>${formatSeconds(totalElapsed)}</b><span>任务耗时合计</span></div>
      <div class="summary-chip"><b>${totalCalls}</b><span>模型调用</span></div>
      <div class="summary-chip"><b>${totalRejected}</b><span>提交拒绝</span></div>
    </div>
  </header>
  <div id="root"></div>
  <pre id="fatal-error" class="fatal-error" hidden></pre>
</div>
<script>window.addEventListener("error",function(event){window.__showGalleryError((event.message||"Script error")+(event.filename?"\\n"+event.filename+":"+event.lineno+":"+event.colno:""))});window.addEventListener("unhandledrejection",function(event){window.__showGalleryError(event.reason&&(event.reason.stack||event.reason.message)||event.reason)})</script>
<script type="text/babel" data-presets="env,react">${bundle}</script>
</body>
</html>\n`;
}

function main() {
  const args = parseArgs(process.argv.slice(2));
  const runDir = path.resolve(process.cwd(), args.runDir);
  assertRunDirectory(runDir);
  const manifest = readJson(path.join(runDir, "manifest.json"), {});
  const tracesValue = readJson(path.join(runDir, "traces.json"), []);
  const traces = Array.isArray(tracesValue) ? tracesValue : tracesValue.traces || [];
  const skillDir = path.resolve(__dirname, "..");
  const runId = manifest.runId || path.basename(runDir);
  const outputPath = args.output
    ? path.resolve(process.cwd(), args.output)
    : path.join(runDir, "jsx-gallery.html");
  const outputDir = path.dirname(outputPath);
  fs.mkdirSync(outputDir, { recursive: true });

  const babelParser = loadBabelParser();
  const entries = buildEntries({ runDir, outputDir, manifest, traces, babelParser });
  if (!entries.length) throw new Error("批次没有可汇总的任务记录");
  const runtimeSource = fs.readFileSync(path.join(skillDir, "design-system-runtime.jsx"), "utf8");
  const bindingRuntimeSource = fs.readFileSync(path.join(skillDir, "preview", "jsx-binding-runtime.js"), "utf8");
  const assetBaseHref = relativeHref(outputDir, skillDir).replace(/\/?$/, "/");
  const embeddedAssets = collectEmbeddedSvgAssets(entries, skillDir);
  const galleryRuntimeSource = withGalleryAssetBase(runtimeSource, assetBaseHref, embeddedAssets);
  const bundle = buildBrowserSource({
    runtimeSource: `${bindingRuntimeSource}\n${galleryRuntimeSource}`,
    entries,
  });
  const html = buildHtml({ manifest, entries, bundle, runDir, outputPath });
  fs.writeFileSync(outputPath, html, "utf8");

  const finalCount = entries.filter((entry) => entry.sourceKind === "final").length;
  const rejectedCount = entries.filter((entry) => entry.sourceKind === "rejected").length;
  const missingCount = entries.filter((entry) => entry.sourceKind === "none").length;
  console.log(`built ${path.relative(process.cwd(), outputPath)} (${Buffer.byteLength(html)} bytes)`);
  console.log(`tasks=${entries.length}, final_jsx=${finalCount}, rejected_jsx=${rejectedCount}, no_jsx=${missingCount}`);
}

try {
  main();
} catch (error) {
  console.error(`错误：${error.message}`);
  process.exitCode = 1;
}
