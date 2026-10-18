/**
 * 期望项输入：既能选候选，也能直接写具体字段。
 *
 * 候选来自 `/debug/expect/options`，中文名与原始 token 一起展示、一起参与匹配：
 * 输入中文按标签筛，输入路径／素材名按 token 筛，空格分隔的多个词需要同时命中；
 * 都没有命中时退回子序列模糊匹配。回车先取精确候选，其次取第一条提示，最后按原文收下，
 * 所以候选之外的写法不会被拦住。候选外的 token 用红色标出，提示它只会按原文比较。
 */

import { useMemo, useState } from 'react';

export type TokenOption = { value: string; label: string };

const SUGGESTION_LIMIT = 8;

function subsequence(needle: string, text: string): boolean {
  if (!needle) return true;
  let index = 0;
  for (const char of text) {
    if (char === needle[index]) index += 1;
    if (index === needle.length) return true;
  }
  return false;
}

/** 中文名与原始 token 一起匹配；多个词按「同时命中」处理。 */
export function matchOptions(
  options: TokenOption[], query: string, limit = SUGGESTION_LIMIT,
): TokenOption[] {
  const terms = query.trim().toLowerCase().split(/\s+/).filter(Boolean);
  if (!terms.length) return options.slice(0, limit);
  const haystack = (option: TokenOption) => `${option.label} ${option.value}`.toLowerCase();
  const direct = options.filter((option) => terms.every((term) => haystack(option).includes(term)));
  if (direct.length) return direct.slice(0, limit);
  const fuzzy = terms.join('').replace(/[^a-z0-9\u4e00-\u9fa5]/g, '');
  return options
    .filter((option) => subsequence(fuzzy, haystack(option).replace(/[^a-z0-9\u4e00-\u9fa5]/g, '')))
    .slice(0, limit);
}

export function TokenPicker({ legend, note, options, tokens, onChange, placeholder }: {
  legend: string;
  note?: string;
  options?: TokenOption[];
  tokens: string[];
  onChange: (next: string[]) => void;
  placeholder?: string;
}) {
  const catalog = options ?? [];
  const [query, setQuery] = useState('');
  const suggestions = useMemo(() => matchOptions(catalog, query), [catalog, query]);
  const labelOf = (value: string) => catalog.find((option) => option.value === value)?.label ?? '';

  function add(value: string) {
    const token = value.trim();
    setQuery('');
    if (!token || tokens.includes(token)) return;
    onChange([...tokens, token]);
  }

  function commit() {
    const raw = query.trim();
    if (!raw) return;
    if (catalog.some((option) => option.value === raw)) return add(raw);
    if (suggestions.length) return add(suggestions[0].value);
    add(raw);
  }

  return <fieldset className="expect-dimensions token-picker">
    <legend>{legend}</legend>
    {note && <p className="expect-dimension-note">{note}</p>}
    {tokens.length
      ? <div className="expect-chips">{tokens.map((token) => {
        const label = labelOf(token);
        return <span key={token}
          className={`expect-chip token-chip ${label ? 'is-hit' : 'is-missing'}`}
          title={label ? `${label} · ${token}` : `${token}（不在候选库里，匹配时按原文比较）`}>
          {label && <strong>{label}</strong>}
          <code>{token}</code>
          <button type="button" aria-label={`移除 ${token}`}
            onClick={() => onChange(tokens.filter((item) => item !== token))}>×</button>
        </span>;
      })}</div>
      : <span className="expect-empty">还没有填写，留空则按 DSL／CardSpec 自动提取</span>}
    <label className="quality-field">{legend}
      <input value={query} placeholder={placeholder}
        onChange={(event) => setQuery(event.target.value)}
        onKeyDown={(event) => {
          if (event.key !== 'Enter') return;
          event.preventDefault();
          commit();
        }} />
    </label>
    {query.trim() && <div className="token-suggestions" role="listbox" aria-label={`${legend}候选`}>
      {suggestions.map((option) => <button type="button" role="option" aria-selected={false}
        key={option.value} onClick={() => add(option.value)}>
        <span>{option.label}</span><code>{option.value}</code>
      </button>)}
      <button type="button" className="token-add-raw" onClick={() => add(query)}>
        按原文加入「{query.trim()}」
      </button>
    </div>}
  </fieldset>;
}
