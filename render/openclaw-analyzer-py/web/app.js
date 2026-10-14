const state = {
  left: null,
  right: null,
  pkOpen: false,
};

const KIND_COLORS = {
  "模型切换": "#8b5cf6",
  "LLM 推理 + 工具决策": "#3b82f6",
  "工具执行结果": "#f59e0b",
  "最终回复": "#10b981",
  "系统事件": "#6b7280",
  "运行时上下文": "#64748b",
  "其他": "#9ca3af",
};

const els = {
  fileInput: document.getElementById("fileInput"),
  statusBar: document.getElementById("statusBar"),
  workspace: document.getElementById("workspace"),
  leftPanel: document.getElementById("leftPanel"),
  rightPanel: document.getElementById("rightPanel"),
  leftTitle: document.getElementById("leftTitle"),
  rightTitle: document.getElementById("rightTitle"),
  leftFrame: document.getElementById("leftFrame"),
  rightFrame: document.getElementById("rightFrame"),
  leftEmpty: document.getElementById("leftEmpty"),
  rightEmpty: document.getElementById("rightEmpty"),
  leftDownload: document.getElementById("leftDownload"),
  rightDownload: document.getElementById("rightDownload"),
  leftDelete: document.getElementById("leftDelete"),
  rightDelete: document.getElementById("rightDelete"),
  pkToggleBtn: document.getElementById("pkToggleBtn"),
  pkDrawer: document.getElementById("pkDrawer"),
  pkCloseBtn: document.getElementById("pkCloseBtn"),
  pkLeftReport: document.getElementById("pkLeftReport"),
  pkLeftQuery: document.getElementById("pkLeftQuery"),
  pkRightReport: document.getElementById("pkRightReport"),
  pkRightQuery: document.getElementById("pkRightQuery"),
  pkRunBtn: document.getElementById("pkRunBtn"),
  pkSummary: document.getElementById("pkSummary"),
  pkSteps: document.getElementById("pkSteps"),
  loadingOverlay: document.getElementById("loadingOverlay"),
};

function formatMs(ms) {
  if (ms == null || ms < 0) return "—";
  if (ms < 1000) return `${ms} ms`;
  return `${(ms / 1000).toFixed(2)} s`;
}

function truncate(text, limit = 48) {
  if (!text) return "";
  return text.length <= limit ? text : text.slice(0, limit - 1) + "…";
}

function setStatus(text, type = "") {
  els.statusBar.textContent = text;
  els.statusBar.className = "status-bar" + (type ? ` ${type}` : "");
}

function showLoading(show) {
  els.loadingOverlay.hidden = !show;
}

function getAllReports() {
  const items = [];
  if (state.left) items.push({ slot: "left", ...state.left });
  if (state.right) items.push({ slot: "right", ...state.right });
  return items;
}

function findReportById(id) {
  if (state.left?.id === id) return state.left;
  if (state.right?.id === id) return state.right;
  return null;
}

function clearFrame(frame) {
  if (frame.dataset.blobUrl) {
    URL.revokeObjectURL(frame.dataset.blobUrl);
    delete frame.dataset.blobUrl;
  }
  frame.removeAttribute("src");
  frame.hidden = true;
}

function setFrameHtml(frame, html) {
  const blob = new Blob([html], { type: "text/html;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  frame.dataset.blobUrl = url;
  frame.hidden = false;
  frame.src = url;
}

async function renderReportInFrame(frame, emptyEl, report) {
  clearFrame(frame);
  if (!report?.id) {
    emptyEl.hidden = false;
    emptyEl.querySelector("p").textContent = emptyEl.dataset.defaultText || "暂无报告";
    return;
  }

  let html = report.html;
  if (!html) {
    try {
      const resp = await fetch(`/api/view/${encodeURIComponent(report.id)}`);
      if (!resp.ok) throw new Error(`报告加载失败 (HTTP ${resp.status})`);
      html = await resp.text();
      report.html = html;
    } catch (err) {
      emptyEl.hidden = false;
      emptyEl.querySelector("p").textContent = `${err.message}。请重新上传 JSONL。`;
      setStatus(err.message, "error");
      return;
    }
  }

  emptyEl.hidden = true;
  setFrameHtml(frame, html);
}

function updatePanelUI() {
  const hasLeft = !!state.left;
  const hasRight = !!state.right;
  const split = hasLeft && hasRight;

  els.workspace.classList.toggle("split", split);
  els.rightPanel.classList.toggle("panel-hidden", !split);

  els.leftTitle.textContent = hasLeft
    ? `${state.left.filename} · ${state.left.summary.queryCount} queries`
    : "暂无报告";
  els.rightTitle.textContent = hasRight
    ? `${state.right.filename} · ${state.right.summary.queryCount} queries`
    : "暂无报告";

  void renderReportInFrame(els.leftFrame, els.leftEmpty, state.left);
  void renderReportInFrame(els.rightFrame, els.rightEmpty, state.right);

  els.leftDownload.disabled = !hasLeft;
  els.leftDelete.disabled = !hasLeft;
  els.rightDownload.disabled = !hasRight;
  els.rightDelete.disabled = !hasRight;
  els.pkToggleBtn.disabled = !hasLeft;

  if (hasLeft && !hasRight) {
    setStatus(`已加载: ${state.left.filename}。上传第二个 JSONL 可开启双屏对比。`, "ok");
  } else if (hasLeft && hasRight) {
    setStatus(`双屏: 左 ${state.left.filename} | 右 ${state.right.filename}`, "ok");
  } else {
    setStatus("请上传第一个 JSONL 文件");
  }

  refreshPkSelectors();
}

function assignReport(reportPayload) {
  const entry = {
    id: reportPayload.summary.id,
    filename: reportPayload.summary.filename,
    html: reportPayload.html || null,
    data: reportPayload.data,
    summary: reportPayload.summary,
  };

  if (!state.left) {
    state.left = entry;
  } else if (!state.right) {
    state.right = entry;
  } else {
    state.left = state.right;
    state.right = entry;
  }
  updatePanelUI();
}

async function uploadFile(file) {
  if (!file) return;
  showLoading(true);
  setStatus(`正在解析 ${file.name}…`);
  try {
    const form = new FormData();
    form.append("file", file);
    const resp = await fetch("/api/analyze", { method: "POST", body: form });
    const payload = await resp.json();
    if (!resp.ok) throw new Error(payload.error || "解析失败");
    assignReport(payload);
  } catch (err) {
    setStatus(`错误: ${err.message}`, "error");
  } finally {
    showLoading(false);
    els.fileInput.value = "";
  }
}

function downloadReport(slot) {
  const report = slot === "left" ? state.left : state.right;
  if (!report) return;
  const a = document.createElement("a");
  a.href = `/api/download/${encodeURIComponent(report.id)}`;
  a.download = report.filename.replace(/\.(jsonl|json|txt)$/i, "") + ".html";
  a.click();
}

async function deleteReport(slot) {
  const report = slot === "left" ? state.left : state.right;
  if (!report) return;
  try {
    await fetch(`/api/report/${report.id}`, { method: "DELETE" });
  } catch (_) {
    /* server may already be gone; still clear locally */
  }
  if (slot === "left") {
    state.left = state.right;
    state.right = null;
  } else {
    state.right = null;
  }
  updatePanelUI();
}

function fillSelect(select, options, selectedValue) {
  select.innerHTML = "";
  for (const opt of options) {
    const el = document.createElement("option");
    el.value = opt.value;
    el.textContent = opt.label;
    select.appendChild(el);
  }
  if (selectedValue != null) select.value = String(selectedValue);
}

function refreshPkSelectors() {
  const reports = getAllReports();
  const reportOptions = reports.map((r) => ({
    value: r.id,
    label: `${r.slot === "left" ? "左" : "右"} · ${r.filename}`,
  }));

  const leftReportId = els.pkLeftReport.value || reports[0]?.id || "";
  const rightReportId = els.pkRightReport.value || reports[reports.length - 1]?.id || leftReportId;

  fillSelect(els.pkLeftReport, reportOptions, leftReportId);
  fillSelect(els.pkRightReport, reportOptions, rightReportId);

  const leftReport = findReportById(els.pkLeftReport.value);
  const rightReport = findReportById(els.pkRightReport.value);

  const leftQueryOptions = (leftReport?.data?.queries || []).map((q) => ({
    value: q.index,
    label: `#${q.index} ${truncate(q.text, 40)} (${formatMs(q.totalDurationMs)})`,
  }));
  const rightQueryOptions = (rightReport?.data?.queries || []).map((q) => ({
    value: q.index,
    label: `#${q.index} ${truncate(q.text, 40)} (${formatMs(q.totalDurationMs)})`,
  }));

  fillSelect(els.pkLeftQuery, leftQueryOptions, leftQueryOptions[0]?.value);
  fillSelect(els.pkRightQuery, rightQueryOptions, rightQueryOptions[0]?.value);
}

function stepFingerprint(step) {
  if (!step) return "";
  const tools = (step.toolCalls || []).map((t) => `${t.name}:${t.arguments || ""}`).join("|");
  return [step.kind, step.description, tools, step.thinkingContent || "", step.fullContent || ""].join("||");
}

function stepsDiffer(a, b) {
  if (!a || !b) return true;
  return stepFingerprint(a) !== stepFingerprint(b);
}

function renderStepBlock(title, content) {
  if (!content || !content.trim()) return "";
  return `
    <details class="pk-block">
      <summary>${escapeHtml(title)}</summary>
      <pre>${escapeHtml(content)}</pre>
    </details>`;
}

function escapeHtml(text) {
  return String(text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function renderStepCard(step, sideLabel, diff = false) {
  const cardClass = "pk-step-card" + (diff ? " diff" : "") + (step ? "" : " missing");
  if (!step) {
    return `<article class="${cardClass}"><div class="pk-step-head"><span class="pk-step-index">${escapeHtml(sideLabel)}</span><span class="pk-badge" style="background:#6b7280">无对应步骤</span></div><p class="pk-step-desc">此侧在该序号没有步骤。</p></article>`;
  }

  const color = KIND_COLORS[step.kind] || KIND_COLORS["其他"];
  const tools = (step.toolCalls || [])
    .map((t) => `<div><code>${escapeHtml(t.name)}</code> — ${escapeHtml(t.arguments || "")}</div>`)
    .join("");

  return `
    <article class="${cardClass}">
      <div class="pk-step-head">
        <span class="pk-step-index">${escapeHtml(sideLabel)} #${step.index}</span>
        <span class="pk-badge" style="background:${color}">${escapeHtml(step.kind)}</span>
      </div>
      <p class="pk-step-desc">${escapeHtml(step.description)}</p>
      <div class="pk-meta">
        ${escapeHtml(step.latencyLabel || "距上一步")}: ${formatMs(step.latencyFromPrevMs)}
        · 距 Query: ${formatMs(step.latencyFromQueryMs)}
        ${step.model ? ` · 模型: ${escapeHtml(step.model)}` : ""}
      </div>
      ${tools ? `<div class="pk-meta">${tools}</div>` : ""}
      ${renderStepBlock("LLM 思考链", step.thinkingContent)}
      ${renderStepBlock("LLM 对外输出", step.fullContent)}
      ${renderStepBlock("完整参数 / 工具返回", (step.toolCalls || []).map((t) => `${t.name}:\n${t.argumentsFull || t.arguments || ""}`).join("\n\n") || step.detailsText)}
      ${renderStepBlock("Token 用量", step.usageText)}
    </article>`;
}

function runPkCompare() {
  const leftReport = findReportById(els.pkLeftReport.value);
  const rightReport = findReportById(els.pkRightReport.value);
  const leftIdx = Number(els.pkLeftQuery.value);
  const rightIdx = Number(els.pkRightQuery.value);

  if (!leftReport || !rightReport) {
    setStatus("请选择有效的报告", "error");
    return;
  }

  const leftQuery = leftReport.data.queries.find((q) => q.index === leftIdx);
  const rightQuery = rightReport.data.queries.find((q) => q.index === rightIdx);
  if (!leftQuery || !rightQuery) {
    setStatus("请选择有效的 Query", "error");
    return;
  }

  const maxSteps = Math.max(leftQuery.steps.length, rightQuery.steps.length);
  let diffCount = 0;
  const rows = [];

  for (let i = 0; i < maxSteps; i++) {
    const ls = leftQuery.steps[i];
    const rs = rightQuery.steps[i];
    const diff = stepsDiffer(ls, rs);
    if (diff) diffCount += 1;

    rows.push(`
      <div class="pk-row-label">步骤 ${i + 1}${diff ? " · 存在差异" : ""}</div>
      <div class="pk-step-row">
        <div>${renderStepCard(ls, "A", diff)}</div>
        <div>${renderStepCard(rs, "B", diff)}</div>
      </div>`);
  }

  const sameReport = leftReport.id === rightReport.id;
  els.pkSummary.hidden = false;
  els.pkSummary.innerHTML = `
    <strong>A</strong> ${escapeHtml(leftReport.filename)} · Query #${leftQuery.index}
    &nbsp;vs&nbsp;
    <strong>B</strong> ${escapeHtml(rightReport.filename)} · Query #${rightQuery.index}
    ${sameReport ? "（同一报告内对比）" : "（跨报告对比）"}
    · 共 ${maxSteps} 步，<strong>${diffCount}</strong> 步存在差异
    · 总耗时 A ${formatMs(leftQuery.totalDurationMs)} / B ${formatMs(rightQuery.totalDurationMs)}
  `;
  els.pkSteps.innerHTML = rows.join("");
}

function togglePk(open) {
  state.pkOpen = open;
  els.pkDrawer.hidden = !open;
  els.pkToggleBtn.textContent = open ? "关闭 PK 对比" : "进入 PK 对比";
  if (open) refreshPkSelectors();
}

els.fileInput.addEventListener("change", (e) => {
  const file = e.target.files?.[0];
  uploadFile(file);
});

els.leftDownload.addEventListener("click", () => downloadReport("left"));
els.rightDownload.addEventListener("click", () => downloadReport("right"));
els.leftDelete.addEventListener("click", () => deleteReport("left"));
els.rightDelete.addEventListener("click", () => deleteReport("right"));

els.pkToggleBtn.addEventListener("click", () => togglePk(!state.pkOpen));
els.pkCloseBtn.addEventListener("click", () => togglePk(false));
els.pkRunBtn.addEventListener("click", runPkCompare);

els.pkLeftReport.addEventListener("change", refreshPkSelectors);
els.pkRightReport.addEventListener("change", refreshPkSelectors);

els.leftEmpty.dataset.defaultText = els.leftEmpty.querySelector("p").textContent;
els.rightEmpty.dataset.defaultText = els.rightEmpty.querySelector("p").textContent;

updatePanelUI();
