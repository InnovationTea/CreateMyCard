import { createElement, useEffect, useState, type ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { getQualityEvaluation, type QualityEvaluation } from '../batchApi';

function inline(text: string): ReactNode {
  return text.split(/(`[^`]+`|\*\*[^*]+\*\*)/g).map((part, index) => (
    part.startsWith('`') ? <code key={index}>{part.slice(1, -1)}</code>
      : part.startsWith('**') ? <strong key={index}>{part.slice(2, -2)}</strong> : part
  ));
}

function Markdown({ text }: { text: string }) {
  // ponytail: 仅支持方案使用的标题、单层列表、简单表格和围栏代码；复杂 Markdown 再接成熟解析器。
  // 所有内容均由 React 转义，不执行 HTML、不加载远程图片或脚本。
  const lines = text.replace(/\r\n/g, '\n').split('\n');
  const blocks: ReactNode[] = [];
  const cells = (line: string) => line.trim().replace(/^\|/, '').replace(/\|$/, '').split('|').map((cell) => cell.trim());
  for (let index = 0; index < lines.length; index++) {
    const line = lines[index];
    const key = index;
    if (!line.trim() || /^<!--.*-->$/.test(line.trim())) continue;
    if (line.startsWith('```')) {
      const code: string[] = [];
      while (++index < lines.length && !lines[index].startsWith('```')) code.push(lines[index]);
      blocks.push(<pre key={key}><code>{code.join('\n')}</code></pre>);
      continue;
    }
    const heading = line.match(/^(#{1,6})\s+(.+)$/);
    if (heading) {
      blocks.push(createElement(`h${Math.min(heading[1].length + 1, 6)}`, { key }, inline(heading[2])));
      continue;
    }
    if (line.includes('|') && /^\s*\|?\s*:?-{3,}/.test(lines[index + 1] ?? '')) {
      const headers = cells(line);
      const rows: string[][] = [];
      index += 2;
      while (index < lines.length && lines[index].includes('|')) rows.push(cells(lines[index++]));
      index--;
      blocks.push(<div className="quality-table-scroll" key={key}><table className="quality-table">
        <thead><tr>{headers.map((cell, i) => <th key={i}>{inline(cell)}</th>)}</tr></thead>
        <tbody>{rows.map((row, i) => <tr key={i}>{row.map((cell, j) => <td key={j}>{inline(cell)}</td>)}</tr>)}</tbody>
      </table></div>);
      continue;
    }
    const list = line.match(/^\s*(\d+\.|[-*])\s+(.+)$/);
    if (list) {
      const ordered = /^\d/.test(list[1]);
      const pattern = ordered ? /^\s*\d+\.\s+(.+)$/ : /^\s*[-*]\s+(.+)$/;
      const items: ReactNode[] = [];
      let match: RegExpMatchArray | null;
      while (index < lines.length && (match = lines[index].match(pattern))) {
        items.push(<li key={index}>{inline(match[1])}</li>); index++;
      }
      index--;
      blocks.push(ordered ? <ol key={key}>{items}</ol> : <ul key={key}>{items}</ul>);
      continue;
    }
    blocks.push(<p key={key}>{inline(line)}</p>);
  }
  return <article className="quality-markdown">{blocks}</article>;
}

export function QualityEvaluationRoute() {
  const [evaluation, setEvaluation] = useState<QualityEvaluation | null>(null);
  const [error, setError] = useState('');
  useEffect(() => {
    let cancelled = false;
    getQualityEvaluation().then((value) => { if (!cancelled) setEvaluation(value); })
      .catch((reason) => { if (!cancelled) setError(String(reason)); });
    return () => { cancelled = true; };
  }, []);
  return <div className="quality-page">
    <header className="batch-center-header"><div><h1>评估方案（当前版本）</h1>
      <p>这是当前方案，不代表历史评分参数。历史结果以对应评分看板的 policy 快照为准。</p></div>
      <nav className="quality-links"><Link to="/quality">选择批次</Link><Link to="/quality/compare">批次对比</Link></nav>
    </header>
    {error && <div className="batch-error" role="alert">{error}</div>}
    {!evaluation && !error && <p role="status">正在加载当前方案…</p>}
    {evaluation && <section className="quality-card">
      <p className="quality-digest">当前方案 SHA-256：<code>{evaluation.policySha256}</code></p>
      <Markdown text={evaluation.markdown} />
      <details><summary>查看当前参数 JSON</summary><pre>{JSON.stringify(evaluation.policy, null, 2)}</pre></details>
    </section>}
  </div>;
}
