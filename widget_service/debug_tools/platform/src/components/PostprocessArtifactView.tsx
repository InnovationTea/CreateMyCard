import { useEffect, useMemo, useState } from 'react';
import type { CSSProperties, ReactNode } from 'react';
import type { PostprocessArtifact } from '../batchApi';

type RecordRow = Record<string, unknown>;

function records(value: unknown): RecordRow[] {
  return Array.isArray(value) ? value.filter((item): item is RecordRow => (
    Boolean(item) && typeof item === 'object' && !Array.isArray(item)
  )) : [];
}

function displayValue(value: unknown): string {
  if (Array.isArray(value)) return value.map(String).join('、');
  if (value === null || value === undefined || value === '') return '—';
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}

function RecordTable({ rows }: { rows: RecordRow[] }) {
  const columns = useMemo(() => Array.from(new Set(rows.flatMap(Object.keys))), [rows]);
  if (!rows.length) return <div className="postprocess-empty">暂无记录</div>;
  return <div className="postprocess-artifact-table-scroll"><table className="postprocess-artifact-table">
    <thead><tr>{columns.map((column) => <th key={column}>{column}</th>)}</tr></thead>
    <tbody>{rows.map((row, index) => <tr key={index}>{columns.map((column) => (
      <td key={column}>{displayValue(row[column])}</td>
    ))}</tr>)}</tbody>
  </table></div>;
}

function BarChart({ rows }: { rows: RecordRow[] }) {
  const numericKey = Object.keys(rows[0] ?? {}).find((key) => typeof rows[0]?.[key] === 'number');
  const labelKey = Object.keys(rows[0] ?? {}).find((key) => key !== numericKey);
  const maximum = Math.max(1, ...rows.map((row) => Number(row[numericKey ?? ''] ?? 0)));
  if (!numericKey) return <RecordTable rows={rows} />;
  return <div className="postprocess-bar-chart" aria-label="柱状图">
    {rows.map((row, index) => {
      const value = Number(row[numericKey] ?? 0);
      return <div className="postprocess-bar-row" key={index}>
        <span>{displayValue(row[labelKey ?? ''])}</span>
        <div><i style={{ width: `${Math.max(2, value / maximum * 100)}%` }} /></div>
        <b>{displayValue(value)}</b>
      </div>;
    })}
  </div>;
}

function LineChart({ rows }: { rows: RecordRow[] }) {
  const numericKey = Object.keys(rows[0] ?? {}).find((key) => typeof rows[0]?.[key] === 'number');
  if (!numericKey || rows.length < 2) return <RecordTable rows={rows} />;
  const values = rows.map((row) => Number(row[numericKey] ?? 0));
  const maximum = Math.max(1, ...values);
  const points = values.map((value, index) => {
    const x = rows.length === 1 ? 0 : index * 100 / (rows.length - 1);
    return `${x},${100 - value * 90 / maximum}`;
  }).join(' ');
  return <div className="postprocess-line-chart">
    <svg viewBox="0 0 100 100" preserveAspectRatio="none" role="img" aria-label="折线图">
      <polyline points={points} fill="none" stroke="currentColor" strokeWidth="2" />
    </svg>
    <RecordTable rows={rows} />
  </div>;
}

function PieChart({ rows }: { rows: RecordRow[] }) {
  const numericKey = Object.keys(rows[0] ?? {}).find((key) => typeof rows[0]?.[key] === 'number');
  const labelKey = Object.keys(rows[0] ?? {}).find((key) => key !== numericKey);
  if (!numericKey) return <RecordTable rows={rows} />;
  const total = rows.reduce((sum, row) => sum + Number(row[numericKey] ?? 0), 0) || 1;
  let cursor = 0;
  const colors = ['#0a59f7', '#28a46b', '#f29b38', '#db3b47', '#77849b'];
  const stops = rows.map((row, index) => {
    const start = cursor;
    cursor += Number(row[numericKey] ?? 0) * 100 / total;
    return `${colors[index % colors.length]} ${start}% ${cursor}%`;
  });
  return <div className="postprocess-pie-layout">
    <div className="postprocess-pie" style={{ background: `conic-gradient(${stops.join(',')})` }} />
    <ul>{rows.map((row, index) => <li key={index}>
      <i style={{ background: colors[index % colors.length] }} />
      <span>{displayValue(row[labelKey ?? ''])}</span><b>{displayValue(row[numericKey])}</b>
    </li>)}</ul>
  </div>;
}

function MatrixView({ value }: { value: unknown }) {
  const matrix = value && typeof value === 'object' ? value as RecordRow : {};
  const rowLabels = Array.isArray(matrix.rows) ? matrix.rows.map(String) : [];
  const columnLabels = Array.isArray(matrix.columns) ? matrix.columns.map(String) : [];
  const cells = Array.isArray(matrix.cells) ? matrix.cells : [];
  if (!rowLabels.length || !columnLabels.length) return <pre>{JSON.stringify(value, null, 2)}</pre>;
  const numeric = cells.flatMap((row) => Array.isArray(row) ? row.map(Number) : []);
  const maximum = Math.max(1, ...numeric);
  return <div className="postprocess-matrix" style={{ gridTemplateColumns: `auto repeat(${columnLabels.length}, 1fr)` }}>
    <span />{columnLabels.map((column) => <b key={column}>{column}</b>)}
    {rowLabels.flatMap((row, rowIndex) => [
      <b key={`${row}-label`}>{row}</b>,
      ...columnLabels.map((column, columnIndex) => {
        const valueAtCell = Number((cells[rowIndex] as unknown[] | undefined)?.[columnIndex] ?? 0);
        return <span key={`${row}-${column}`} style={{ '--heat': valueAtCell / maximum } as CSSProperties}>
          {displayValue(valueAtCell)}
        </span>;
      }),
    ])}
  </div>;
}

function RemoteText({ url }: { url: string }) {
  const [text, setText] = useState('正在加载…');
  useEffect(() => {
    const controller = new AbortController();
    fetch(url, { signal: controller.signal })
      .then((response) => response.ok ? response.text() : Promise.reject(new Error('读取失败')))
      .then(setText)
      .catch((reason) => { if (reason.name !== 'AbortError') setText(String(reason)); });
    return () => controller.abort();
  }, [url]);
  return <pre>{text}</pre>;
}

export function PostprocessArtifactView({ artifact }: { artifact: PostprocessArtifact }) {
  const rows = records(artifact.data);
  const renderer = artifact.renderer;
  let body: ReactNode;
  if (artifact.dataType === 'metrics') {
    body = <div className="postprocess-kpis">{rows.map((item, index) => <div key={index}>
      <b>{displayValue(item.value)}{item.unit ? <small>{String(item.unit)}</small> : null}</b>
      <span>{displayValue(item.label)}</span>
    </div>)}</div>;
  } else if (artifact.dataType === 'records' && renderer === 'bar') {
    body = <BarChart rows={rows} />;
  } else if (artifact.dataType === 'records' && renderer === 'line') {
    body = <LineChart rows={rows} />;
  } else if (artifact.dataType === 'records' && renderer === 'pie') {
    body = <PieChart rows={rows} />;
  } else if (artifact.dataType === 'records' || artifact.dataType === 'issues') {
    body = <RecordTable rows={rows} />;
  } else if (artifact.dataType === 'matrix') {
    body = <MatrixView value={artifact.data} />;
  } else if (artifact.dataType === 'image' && artifact.url) {
    body = <figure><img src={artifact.url} alt={artifact.alt ?? artifact.title ?? '插件图片产物'} />
      {artifact.fullUrl ? <a href={String(artifact.fullUrl)} target="_blank" rel="noreferrer">查看原图 ↗</a> : null}
    </figure>;
  } else if ((artifact.dataType === 'link' || artifact.dataType === 'file') && artifact.url) {
    body = <a className="postprocess-file-link" href={artifact.url} target="_blank" rel="noreferrer">
      {artifact.label ?? (artifact.dataType === 'file' ? '下载文件' : '打开链接')} ↗
    </a>;
  } else if ((artifact.dataType === 'code' || artifact.dataType === 'diff') && artifact.url) {
    body = <RemoteText url={artifact.url} />;
  } else if (artifact.dataType === 'code' || artifact.dataType === 'diff') {
    body = <pre>{displayValue(artifact.data ?? artifact.text)}</pre>;
  } else if (artifact.dataType === 'text') {
    body = <p>{displayValue(artifact.data ?? artifact.text)}</p>;
  } else {
    body = <pre>{JSON.stringify(artifact.data ?? artifact, null, 2)}</pre>;
  }
  return <section className={`postprocess-artifact ${artifact.dataType}`}>
    <h3>{artifact.title ?? artifact.key}</h3>{body}
  </section>;
}
