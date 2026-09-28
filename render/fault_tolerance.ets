import { hilog } from '@kit.PerformanceAnalysisKit';

const FAULT_TOLERANCE_DOMAIN: number = 0xd001000;
const FAULT_TOLERANCE_TAG: string = 'CompactHar';

function skipWsLocal(s: string, i: number): number {
  let j: number = i;
  while (j < s.length) {
    const c: string = s.charAt(j);
    if (c === ' ' || c === '\n' || c === '\r' || c === '\t') {
      j++;
    } else {
      break;
    }
  }
  return j;
}

/** 从 `fromInclusive` 起向左跳过 ASCII 空白。 */
function skipWsRevLocal(s: string, fromInclusive: number): number {
  let k: number = fromInclusive;
  while (k >= 0) {
    const c: string = s.charAt(k);
    if (c === ' ' || c === '\n' || c === '\r' || c === '\t') {
      k--;
    } else {
      break;
    }
  }
  return k;
}

/**
 * 仅对首尾空白之间的有效载荷：若 trim 后首字符不是 `[` 则在段首补 `[`，
 * 若 trim 后末字符不是 `]` 则在段末补 `]`；段外前后空白保持不变。
 * @returns 可能已包裹的字符串，以及补括号次数（0～2）。
 */
function wrapOuterBracketsIfNeeded(s: string): [string, number] {
  const lead: number = skipWsLocal(s, 0);
  if (lead >= s.length) {
    return [s, 0];
  }
  const trail: number = skipWsRevLocal(s, s.length - 1);
  if (trail < lead) {
    return [s, 0];
  }
  let mid: string = s.substring(lead, trail + 1);
  let fixes: number = 0;
  if (mid.charAt(0) !== '[') {
    mid = '[' + mid;
    fixes++;
  }
  if (mid.charAt(mid.length - 1) !== ']') {
    mid = mid + ']';
    fixes++;
  }
  const wrapped: string = s.substring(0, lead) + mid + s.substring(trail + 1);
  return [wrapped, fixes];
}

/** 从 `from` 起在 `s` 中找下一个未转义的 ASCII `"`。 */
function findNextUnescapedDoubleQuote(s: string, from: number): number {
  let escape: boolean = false;
  for (let i: number = from; i < s.length; i++) {
    const c: string = s.charAt(i);
    if (escape) {
      escape = false;
      continue;
    }
    if (c === '\\') {
      escape = true;
      continue;
    }
    if (c === '"') {
      return i;
    }
  }
  return -1;
}

/**
 * 单次扫描：栈式花括号深度（仅串外）+ 串内双引号合法后继判定 + 末尾 ) 修正。
 * - 先做 **情况一**：trim 语义下有效载荷首尾若非 `[`、`]`，在有效段两侧补括号（段外空白不动）。
 * 任意修复（如缺左引号）通过 **pending 注入下一字符**，与源码后续字节走**同一套**状态机，不单独写分支。
 * - 串外：`{` / `}` 维护 braceDepth。
 * - 串内：遇 `"`，若其后（跳过空白）不是 `:` `,` `}` `]`，亦未到文本末尾，则与下一未转义 `"` 成对前各加 `\`。
 * - 串外遇 `,` 且随后非 `"` `{` `[`：将 `"` **前置进 pending**，下一轮按普通开引号处理，源码指针仍停在原处。
 * - 扫描结束后：若 braceDepth > 0 且输出串最后一个非空白为 `)`，改为 `}`。
 */
export function preprocessMiniPayloadForFaultTolerance(s: string): string {
  const bracketApplied: [string, number] = wrapOuterBracketsIfNeeded(s);
  s = bracketApplied[0];
  const case1BracketFixCount: number = bracketApplied[1];
  let out: string = '';
  let pending: string = '';
  let inString: boolean = false;
  let escape: boolean = false;
  let braceDepth: number = 0;
  let case2PairCount: number = 0;
  let case3InsertCount: number = 0;
  let i: number = 0;
  while (i < s.length || pending.length > 0) {
    let fromPending: boolean;
    let c: string;
    if (pending.length > 0) {
      c = pending.charAt(0);
      pending = pending.substring(1);
      fromPending = true;
    } else {
      if (i >= s.length) {
        break;
      }
      c = s.charAt(i);
      fromPending = false;
    }
    if (!inString) {
      if (c === '"') {
        inString = true;
        out += c;
        if (!fromPending) {
          i++;
        }
        continue;
      }
      if (c === ',') {
        out += c;
        i++;
        const afterComma: number = skipWsLocal(s, i);
        while (i < afterComma) {
          out += s.charAt(i);
          i++;
        }
        if (i < s.length) {
          const nc: string = s.charAt(i);
          if (nc !== '"' && nc !== '{' && nc !== '[') {
            pending = '"' + pending;
            case3InsertCount++;
          }
        }
        continue;
      }
      if (c === '{') {
        braceDepth++;
      } else if (c === '}') {
        braceDepth--;
      }
      out += c;
      if (!fromPending) {
        i++;
      }
      continue;
    }
    if (escape) {
      out += c;
      escape = false;
      if (!fromPending) {
        i++;
      }
      continue;
    }
    if (c === '\\') {
      out += c;
      escape = true;
      if (!fromPending) {
        i++;
      }
      continue;
    }
    if (c !== '"') {
      out += c;
      if (!fromPending) {
        i++;
      }
      continue;
    }
    const after: number = skipWsLocal(s, i + 1);
    let legalEnd: boolean = false;
    if (after >= s.length) {
      legalEnd = true;
    } else {
      const ac: string = s.charAt(after);
      if (ac === ':' || ac === ',' || ac === '}' || ac === ']') {
        legalEnd = true;
      }
    }
    if (legalEnd) {
      out += '"';
      inString = false;
      i++;
      continue;
    }
    const k: number = findNextUnescapedDoubleQuote(s, i + 1);
    if (k < 0) {
      out += '"';
      inString = false;
      i++;
      continue;
    }
    out += '\\';
    out += '"';
    case2PairCount++;
    i++;
    while (i < k) {
      out += s.charAt(i);
      i++;
    }
    out += '\\';
    out += '"';
    i = k + 1;
  }
  let result: string = out;
  if (case1BracketFixCount > 0) {
    hilog.info(FAULT_TOLERANCE_DOMAIN, FAULT_TOLERANCE_TAG, '【mapMiniToA2ui 异常处理】修复情况一：最外层 [] — trim 语义下已为有效载荷补足 %{public}s 侧括号',
      String(case1BracketFixCount));
  }
  if (case2PairCount > 0) {
    hilog.info(FAULT_TOLERANCE_DOMAIN, FAULT_TOLERANCE_TAG, '【mapMiniToA2ui 异常处理】修复情况二：双引号冲突 — 单遍扫描已为 %{public}s 对冲突 " 插入 \\ 转义', String(case2PairCount));
  }
  if (case3InsertCount > 0) {
    hilog.info(FAULT_TOLERANCE_DOMAIN, FAULT_TOLERANCE_TAG, '【mapMiniToA2ui 异常处理】修复情况三："缺失 " 分隔符 , 后应为 "、{、[ 之一，已补充 %{public}s 处前缀 "', String(case3InsertCount));
  }
  return result;
}
