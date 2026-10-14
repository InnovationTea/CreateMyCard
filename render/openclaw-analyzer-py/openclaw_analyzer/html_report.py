from __future__ import annotations

import html
from pathlib import Path

from .log_parser import ParsedLog
from .query_analyzer import ACTION_KIND_LABELS, ActionKind, UserQueryAnalysis, _latency_label_for_kind
from .time_utils import format_duration_ms

KIND_COLORS = {
    ActionKind.MODEL_CHANGE: "#8b5cf6",
    ActionKind.ASSISTANT_ROUND: "#3b82f6",
    ActionKind.TOOL_RESULT: "#f59e0b",
    ActionKind.ASSISTANT_RESPONSE: "#10b981",
    ActionKind.CUSTOM_EVENT: "#6b7280",
    ActionKind.CUSTOM_MESSAGE: "#64748b",
    ActionKind.OTHER: "#9ca3af",
}


def _esc(text: str) -> str:
    return html.escape(text or "")


def _kind_css_class(kind: ActionKind) -> str:
    return kind.value.replace("_", "-")


def _render_content_block(
    title: str,
    content: str,
    *,
    default_open: bool = False,
    block_class: str = "",
) -> str:
    if not content or not content.strip():
        return ""
    open_attr = " open" if default_open else ""
    extra_class = f" {block_class}" if block_class else ""
    char_count = len(content)
    line_count = content.count("\n") + 1
    return f"""
    <details class="content-block{extra_class}"{open_attr}>
      <summary>{_esc(title)} <span class="content-meta">({line_count} 行 · {char_count} 字符)</span></summary>
      <div class="content-toolbar">
        <button type="button" class="copy-btn" onclick="copyBlock(this)">复制</button>
      </div>
      <pre class="content-pre">{_esc(content)}</pre>
    </details>
    """


def _render_tool_calls(step) -> str:
    if not step.tool_calls:
        return ""
    blocks = []
    for i, call in enumerate(step.tool_calls, start=1):
        title = f"工具调用 #{i}: {call.name}"
        if call.id:
            title += f" ({call.id})"
        summary_line = f'<div class="tool-summary"><code>{_esc(call.name)}</code>'
        if call.arguments_summary:
            summary_line += f' — {_esc(call.arguments_summary)}'
        summary_line += "</div>"
        args_block = _render_content_block(
            f"完整参数 · {call.name}",
            call.arguments_full or call.arguments_summary,
        )
        blocks.append(summary_line + args_block)
    return f'<div class="tool-blocks">{"".join(blocks)}</div>'


def _render_step_details(step) -> str:
    parts = []

    if step.kind in (ActionKind.ASSISTANT_ROUND, ActionKind.ASSISTANT_RESPONSE):
        open_thinking = bool(step.thinking_content and not step.full_content)
        if step.thinking_content:
            parts.append(
                _render_content_block(
                    "LLM 思考链 (thinking) — 内部推理，通常不展示给用户",
                    step.thinking_content,
                    block_class="thinking-block",
                    default_open=open_thinking,
                )
            )
        if step.full_content:
            parts.append(
                _render_content_block(
                    "LLM 对外输出 (text) — 用户可见的助手正文",
                    step.full_content,
                    block_class="text-block",
                )
            )
        if not step.thinking_content and not step.full_content:
            parts.append('<div class="detail-tag muted">本步无 text/thinking 正文，仅包含工具调用。</div>')
        if step.usage_text:
            parts.append(_render_content_block("Token 用量", step.usage_text))

    if step.kind == ActionKind.TOOL_RESULT:
        if step.tool_call_id:
            parts.append(
                f'<div class="detail-tag">关联 toolCallId: <code>{_esc(step.tool_call_id)}</code></div>'
            )
        body = step.full_content or step.details_text
        if step.full_content and step.details_text and step.details_text.strip() != step.full_content.strip():
            parts.append(_render_content_block("工具返回内容 (message.content)", step.full_content))
            parts.append(_render_content_block("工具返回详情 (details)", step.details_text))
        else:
            parts.append(_render_content_block(f"工具 [{step.tool_name}] 完整返回", body))

    if step.kind == ActionKind.CUSTOM_MESSAGE:
        hidden = ' <span class="content-meta">(OpenClaw display=false，分析器仍展示)</span>' if step.hidden_from_ui else ""
        parts.append(f'<div class="detail-tag">运行时注入上下文{hidden}</div>')
        if step.full_content:
            parts.append(_render_content_block("运行时上下文 (custom_message.content)", step.full_content, default_open=True))
        if step.details_text:
            parts.append(_render_content_block("运行时上下文 details", step.details_text))

    if step.kind == ActionKind.CUSTOM_EVENT and step.full_content:
        parts.append(_render_content_block("事件详情", step.full_content))

    return f'<div class="step-details">{"".join(parts)}</div>' if parts else ""


def _render_step_meta(step) -> str:
    parts = []
    if step.reported_duration_ms >= 0:
        parts.append(f'工具耗时 <strong>{_esc(format_duration_ms(step.reported_duration_ms))}</strong>')
        if step.scheduling_overhead_ms > 0:
            parts.append(
                f'调度开销 <strong>{_esc(format_duration_ms(step.scheduling_overhead_ms))}</strong>'
            )
    if step.model:
        model = f"{step.provider} / {step.model}" if step.provider else step.model
        reason = f" [{step.stop_reason}]" if step.stop_reason else ""
        parts.append(f'模型 <strong>{_esc(model + reason)}</strong>')
    if not parts:
        return ""
    return f'<div class="step-meta">{ " · ".join(parts) }</div>'


def _render_timeline_bars(query: UserQueryAnalysis) -> str:
    segments = []
    total = max(query.total_duration_ms, 1)

    for step in query.steps:
        width_ms = step.latency_from_prev_ms if step.latency_from_prev_ms > 0 else 0
        if width_ms <= 0 and step.reported_duration_ms > 0:
            width_ms = step.reported_duration_ms
        if width_ms <= 0:
            continue

        pct = min(100.0, width_ms / total * 100)
        if pct < 0.5:
            pct = 0.5
        color = KIND_COLORS.get(step.kind, "#9ca3af")
        label = ACTION_KIND_LABELS.get(step.kind, "其他")
        latency_label = _latency_label_for_kind(step.kind)
        tip = (
            f"#{step.step_index} {label}\\n"
            f"{latency_label}: {format_duration_ms(step.latency_from_prev_ms)}\\n"
            f"距Query: {format_duration_ms(step.latency_from_query_ms)}"
        )
        if step.reported_duration_ms >= 0:
            tip += f"\\n工具耗时: {format_duration_ms(step.reported_duration_ms)}"
        segments.append(
            f'<div class="timeline-seg" style="width:{pct:.2f}%;background:{color}" '
            f'title="{_esc(tip)}"></div>'
        )

    if not segments:
        return '<div class="timeline-empty">无可视化时延数据</div>'

    return f'<div class="timeline-bar">{"".join(segments)}</div>'


def _render_query_section(query: UserQueryAnalysis) -> str:
    steps_html = []
    max_prev = max((s.latency_from_prev_ms for s in query.steps), default=1) or 1

    for step in query.steps:
        kind_label = ACTION_KIND_LABELS.get(step.kind, "其他")
        latency_label = _latency_label_for_kind(step.kind)
        kind_class = _kind_css_class(step.kind)
        bar_pct = min(100.0, max(4.0, step.latency_from_prev_ms / max_prev * 100)) if step.latency_from_prev_ms > 0 else 4.0
        color = KIND_COLORS.get(step.kind, "#9ca3af")

        steps_html.append(
            f"""
            <article class="step-card kind-{kind_class}">
              <div class="step-head">
                <span class="step-index">#{step.step_index}</span>
                <span class="step-badge" style="background:{color}">{_esc(kind_label)}</span>
                <span class="step-time">{_esc(step.timestamp)}</span>
              </div>
              <p class="step-desc">{_esc(step.description)}</p>
              {_render_tool_calls(step)}
              {_render_step_details(step)}
              {_render_step_meta(step)}
              <div class="latency-row">
                <div class="latency-labels">
                  <span>{_esc(latency_label)} <strong>{_esc(format_duration_ms(step.latency_from_prev_ms))}</strong></span>
                  <span>距 Query <strong>{_esc(format_duration_ms(step.latency_from_query_ms))}</strong></span>
                </div>
                <div class="latency-bar-track">
                  <div class="latency-bar-fill" style="width:{bar_pct:.1f}%;background:{color}"></div>
                </div>
              </div>
            </article>
            """
        )

    model_line = f'<div class="meta-item"><span>模型</span><code>{_esc(query.model_at_start)}</code></div>' if query.model_at_start else ""
    run_line = f'<div class="meta-item"><span>RunId</span><code>{_esc(query.run_id)}</code></div>' if query.run_id else ""

    return f"""
    <section class="query-section" id="query-{query.query_index}">
      <header class="query-header">
        <div>
          <h2>Query #{query.query_index}</h2>
          <p class="query-text">{_esc(query.query_text)}</p>
        </div>
        <div class="query-stats">
          <div class="stat-pill total">{_esc(format_duration_ms(query.total_duration_ms))}</div>
          <div class="stat-pill">{len(query.steps)} 步</div>
        </div>
      </header>
      <div class="query-meta">
        <div class="meta-item"><span>时间</span><code>{_esc(query.timestamp)}</code></div>
        {model_line}
        {run_line}
      </div>
      <div class="timeline-block">
        <div class="block-title">时延分布（按步骤占比）</div>
        {_render_timeline_bars(query)}
        <div class="content-hint">
          <strong>thinking vs text：</strong>
          <code>thinking</code> 是模型内部推理链（Extended Thinking），用于规划与决策，通常不直接展示给用户；
          <code>text</code> 是对外输出的助手正文，会呈现给用户。一步 LLM 响应可同时包含两者，也可能仅有 thinking + 工具调用。
        </div>
        <div class="legend">
          <span><i style="background:#3b82f6"></i>LLM 推理</span>
          <span><i style="background:#f59e0b"></i>工具结果</span>
          <span><i style="background:#10b981"></i>最终回复</span>
          <span><i style="background:#6b7280"></i>系统事件</span>
        </div>
      </div>
      <div class="steps-grid">
        {"".join(steps_html)}
      </div>
    </section>
    """


def _render_summary_cards(log: ParsedLog, queries: list[UserQueryAnalysis]) -> str:
    total_query_ms = sum(q.total_duration_ms for q in queries)
    total_steps = sum(len(q.steps) for q in queries)
    avg_ms = total_query_ms // len(queries) if queries else 0
    warn = ""
    if log.parse_stats.skipped_regions:
        warn = f"""
        <div class="content-hint" style="margin-top:12px">
          日志解析 recovered <strong>{log.parse_stats.skipped_regions}</strong> 处损坏/粘连 JSON 片段。
          共解析 <strong>{log.parse_stats.json_objects}</strong> 个 JSON 对象。
        </div>
        """

    return f"""
    <div class="summary-grid">
      <div class="summary-card">
        <div class="summary-value">{len(queries)}</div>
        <div class="summary-label">用户 Query</div>
      </div>
      <div class="summary-card">
        <div class="summary-value">{len(log.ordered_events)}</div>
        <div class="summary-label">日志事件</div>
      </div>
      <div class="summary-card">
        <div class="summary-value">{total_steps}</div>
        <div class="summary-label">分析步骤</div>
      </div>
      <div class="summary-card">
        <div class="summary-value">{_esc(format_duration_ms(avg_ms))}</div>
        <div class="summary-label">平均 Query 耗时</div>
      </div>
    </div>
    {warn}
    """


def _render_nav(queries: list[UserQueryAnalysis]) -> str:
    links = [
        f'<a href="#query-{q.query_index}">#{q.query_index} {_esc(_truncate_nav(q.query_text))}</a>'
        for q in queries
    ]
    return f'<nav class="query-nav">{"".join(links)}</nav>'


def _truncate_nav(text: str, limit: int = 28) -> str:
    return text if len(text) <= limit else text[: limit - 1] + "…"


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>OpenClaw 日志分析报告</title>
  <style>
    :root {{
      --bg: #0f172a;
      --panel: #111827;
      --panel-2: #1f2937;
      --text: #e5e7eb;
      --muted: #9ca3af;
      --line: #374151;
      --accent: #38bdf8;
    }}
    * {{ box-sizing: border-box; }}
    body {{
      margin: 0;
      font-family: "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
      background: linear-gradient(180deg, #0b1220 0%, #111827 100%);
      color: var(--text);
      line-height: 1.5;
    }}
    .container {{ max-width: 1100px; margin: 0 auto; padding: 24px; }}
    .hero {{
      background: rgba(17,24,39,.92);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 24px;
      margin-bottom: 20px;
    }}
    h1 {{ margin: 0 0 8px; font-size: 1.8rem; }}
    .subtitle {{ color: var(--muted); margin: 0; }}
    .session-meta {{
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
      gap: 12px;
      margin-top: 16px;
    }}
    .session-meta code {{
      display: block;
      margin-top: 4px;
      word-break: break-all;
      color: #cbd5e1;
    }}
    .summary-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin: 20px 0;
    }}
    .summary-card {{
      background: var(--panel-2);
      border: 1px solid var(--line);
      border-radius: 12px;
      padding: 16px;
      text-align: center;
    }}
    .summary-value {{ font-size: 1.6rem; font-weight: 700; color: var(--accent); }}
    .summary-label {{ color: var(--muted); font-size: .9rem; }}
    .query-nav {{
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 20px;
    }}
    .query-nav a {{
      color: #dbeafe;
      background: #1e3a8a;
      text-decoration: none;
      padding: 6px 10px;
      border-radius: 999px;
      font-size: .85rem;
    }}
    .query-section {{
      background: rgba(17,24,39,.95);
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 20px;
      margin-bottom: 24px;
    }}
    .query-header {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: flex-start;
    }}
    .query-header h2 {{ margin: 0; }}
    .query-text {{
      margin: 8px 0 0;
      font-size: 1.05rem;
      color: #f3f4f6;
    }}
    .query-stats {{ display: flex; gap: 8px; flex-shrink: 0; }}
    .stat-pill {{
      background: var(--panel-2);
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 6px 12px;
      font-size: .85rem;
      color: var(--muted);
    }}
    .stat-pill.total {{ color: #fef3c7; border-color: #92400e; background: #451a03; }}
    .query-meta {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin: 14px 0 18px;
    }}
    .meta-item {{
      background: var(--panel-2);
      border-radius: 8px;
      padding: 8px 12px;
      font-size: .85rem;
    }}
    .meta-item span {{ color: var(--muted); margin-right: 8px; }}
    .timeline-block {{
      background: var(--panel-2);
      border-radius: 12px;
      padding: 14px;
      margin-bottom: 18px;
    }}
    .block-title {{ color: var(--muted); font-size: .85rem; margin-bottom: 10px; }}
    .timeline-bar {{
      display: flex;
      height: 18px;
      border-radius: 999px;
      overflow: hidden;
      background: #0b1220;
      border: 1px solid var(--line);
    }}
    .timeline-seg {{ height: 100%; min-width: 2px; }}
    .timeline-empty {{ color: var(--muted); font-size: .9rem; }}
    .legend {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 10px;
      font-size: .8rem;
      color: var(--muted);
    }}
    .legend i {{
      display: inline-block;
      width: 10px;
      height: 10px;
      border-radius: 999px;
      margin-right: 4px;
    }}
    .steps-grid {{ display: grid; gap: 12px; }}
    .step-card {{
      background: #0b1220;
      border: 1px solid var(--line);
      border-left-width: 4px;
      border-radius: 12px;
      padding: 14px;
    }}
    .step-head {{
      display: flex;
      flex-wrap: wrap;
      align-items: center;
      gap: 8px;
      margin-bottom: 8px;
    }}
    .step-index {{ font-weight: 700; color: var(--accent); }}
    .step-badge {{
      color: white;
      font-size: .75rem;
      padding: 2px 8px;
      border-radius: 999px;
    }}
    .step-time {{ color: var(--muted); font-size: .8rem; margin-left: auto; }}
    .step-desc {{ margin: 0 0 8px; white-space: pre-wrap; word-break: break-word; color: #cbd5e1; }}
    .tool-blocks {{ display: grid; gap: 8px; margin-bottom: 10px; }}
    .tool-summary {{
      font-size: .9rem;
      color: #dbeafe;
      margin-bottom: 6px;
    }}
    .step-details {{ display: grid; gap: 8px; margin: 10px 0; }}
    .detail-tag {{
      font-size: .82rem;
      color: var(--muted);
      margin-bottom: 4px;
    }}
    .content-block {{
      background: #030712;
      border: 1px solid var(--line);
      border-radius: 10px;
      overflow: hidden;
    }}
    .content-block summary {{
      cursor: pointer;
      padding: 10px 12px;
      font-size: .88rem;
      color: #bfdbfe;
      user-select: none;
      list-style-position: outside;
    }}
    .content-block.thinking-block summary {{ color: #ddd6fe; }}
    .content-block.text-block summary {{ color: #bfdbfe; }}
    .content-block.thinking-block .content-pre {{ border-left: 3px solid #8b5cf6; }}
    .content-block.text-block .content-pre {{ border-left: 3px solid #3b82f6; }}
    .detail-tag.muted {{ color: var(--muted); font-size: .85rem; margin-bottom: 6px; }}
    .content-hint {{
      background: rgba(59,130,246,.08);
      border: 1px solid var(--line);
      border-radius: 10px;
      padding: 10px 12px;
      font-size: .85rem;
      color: #cbd5e1;
      margin-bottom: 14px;
    }}
    .content-hint strong {{ color: #e5e7eb; }}
    .content-meta {{ color: var(--muted); font-size: .78rem; margin-left: 6px; }}
    .content-toolbar {{
      display: flex;
      justify-content: flex-end;
      padding: 0 10px 6px;
    }}
    .copy-btn {{
      background: #1e293b;
      color: #e2e8f0;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 4px 10px;
      font-size: .78rem;
      cursor: pointer;
    }}
    .copy-btn:hover {{ background: #334155; }}
    .content-pre {{
      margin: 0;
      padding: 12px;
      max-height: 480px;
      overflow: auto;
      white-space: pre-wrap;
      word-break: break-word;
      font-family: Consolas, "Cascadia Code", monospace;
      font-size: .82rem;
      line-height: 1.45;
      color: #e2e8f0;
      background: #020617;
      border-top: 1px solid var(--line);
    }}
    .tool-list {{
      margin: 0 0 8px 18px;
      padding: 0;
      color: #dbeafe;
      font-size: .9rem;
    }}
    .tool-args {{
      display: block;
      color: var(--muted);
      font-size: .82rem;
      margin-top: 2px;
      word-break: break-all;
    }}
    .step-meta {{ color: var(--muted); font-size: .85rem; margin-bottom: 8px; }}
    .latency-row {{ margin-top: 8px; }}
    .latency-labels {{
      display: flex;
      justify-content: space-between;
      font-size: .82rem;
      color: var(--muted);
      margin-bottom: 4px;
    }}
    .latency-bar-track {{
      height: 8px;
      background: #1f2937;
      border-radius: 999px;
      overflow: hidden;
    }}
    .latency-bar-fill {{ height: 100%; border-radius: 999px; }}
    footer {{
      text-align: center;
      color: var(--muted);
      font-size: .85rem;
      padding: 24px 0 8px;
    }}
    @media (max-width: 768px) {{
      .summary-grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
      .query-header {{ flex-direction: column; }}
      .step-time {{ margin-left: 0; }}
    }}
  </style>
</head>
<body>
  <div class="container">
    <header class="hero">
      <h1>OpenClaw 日志分析报告</h1>
      <p class="subtitle">用户 Query 行为链路与各阶段时延可视化</p>
      <div class="session-meta">
        <div><span class="subtitle">Session ID</span><code>{session_id}</code></div>
        <div><span class="subtitle">工作目录</span><code>{cwd}</code></div>
        <div><span class="subtitle">会话开始</span><code>{start_ts}</code></div>
      </div>
      {summary_cards}
    </header>
    {nav}
    {queries}
    <footer>Generated by openclaw-analyzer-py</footer>
  </div>
  <script>
    function copyBlock(btn) {{
      const pre = btn.closest('.content-block').querySelector('.content-pre');
      if (!pre) return;
      navigator.clipboard.writeText(pre.textContent || '').then(() => {{
        const old = btn.textContent;
        btn.textContent = '已复制';
        setTimeout(() => {{ btn.textContent = old; }}, 1200);
      }}).catch(() => {{
        btn.textContent = '复制失败';
      }});
    }}
  </script>
</body>
</html>
"""


def render_analysis_html(log: ParsedLog, queries: list[UserQueryAnalysis]) -> str:
    queries_html = "".join(_render_query_section(q) for q in queries)
    return HTML_TEMPLATE.format(
        session_id=_esc(log.session.session_id),
        cwd=_esc(log.session.cwd),
        start_ts=_esc(log.session.start_timestamp),
        summary_cards=_render_summary_cards(log, queries),
        nav=_render_nav(queries) if queries else "",
        queries=queries_html or '<p class="subtitle">未找到用户 Query。</p>',
    )


def export_analysis_html(path: str | Path, log: ParsedLog, queries: list[UserQueryAnalysis]) -> None:
    Path(path).write_text(render_analysis_html(log, queries), encoding="utf-8")
