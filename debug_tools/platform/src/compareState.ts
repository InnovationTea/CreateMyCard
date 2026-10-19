/**
 * 期望对比页的持久配置：跳去画廊、切模块或刷新后回来，不用再重新选一遍。
 *
 * 只存"选择"，不存结果：实际来源、选中的批跑运行、勾选的会话记录、启用维度与三个筛选条件，
 * 外加一个"上次跑出过结果"的标记。带标记时回到页面会自动按同一套配置重跑一次，
 * 所以看到的仍是同一份对比结果，而且拿到的一定是当前后端数据，不会展示过期结论。
 *
 * 存储失败（隐私模式、配额）只影响记忆能力，不影响页面：所有读写都吞掉异常并返回空配置。
 */

const STORAGE_KEY = 'ai-widget-expect-compare:v1';

export type CompareConfig = {
  /** 实际来源：本次会话的调试记录，或已落盘的批跑运行。 */
  actualSource: 'session' | 'batch';
  actualRunId: string;
  sessionIds: string[];
  dimensions: string[];
  tier: string;
  category: string;
  search: string;
  /** 上次确实跑出过结果；带上它才会在回到页面时自动重跑。 */
  hasResult: boolean;
};

function storage(): Storage | null {
  try {
    return window.localStorage;
  } catch {
    return null;
  }
}

export function loadCompareConfig(): CompareConfig | null {
  const store = storage();
  if (!store) return null;
  try {
    const raw = store.getItem(STORAGE_KEY);
    if (!raw) return null;
    const value = JSON.parse(raw) as Partial<CompareConfig>;
    const source = value.actualSource === 'batch' ? 'batch' : 'session';
    return {
      actualSource: source,
      actualRunId: typeof value.actualRunId === 'string' ? value.actualRunId : '',
      sessionIds: Array.isArray(value.sessionIds)
        ? value.sessionIds.filter((item): item is string => typeof item === 'string') : [],
      dimensions: Array.isArray(value.dimensions)
        ? value.dimensions.filter((item): item is string => typeof item === 'string') : [],
      tier: typeof value.tier === 'string' && value.tier ? value.tier : 'all',
      category: typeof value.category === 'string' && value.category ? value.category : 'all',
      search: typeof value.search === 'string' ? value.search : '',
      hasResult: value.hasResult === true,
    };
  } catch {
    return null;
  }
}

export function saveCompareConfig(config: CompareConfig): void {
  const store = storage();
  if (!store) return;
  try {
    store.setItem(STORAGE_KEY, JSON.stringify(config));
  } catch {
    // 配额或隐私模式：记忆是增强能力，失败不打断对比。
  }
}

export function clearCompareConfig(): void {
  const store = storage();
  if (!store) return;
  try {
    store.removeItem(STORAGE_KEY);
  } catch {
    // 同上，清不掉也不影响页面。
  }
}
