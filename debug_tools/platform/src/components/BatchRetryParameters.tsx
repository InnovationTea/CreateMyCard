import type { BatchRun } from '../batchApi';

const PARAMETERS = [
  ['interfaceRetryEnabled', '整接口重试开关'],
  ['interfaceExtraRetries', '整接口额外重试次数'],
  ['interfaceMaxAttempts', '每请求完整生成轮数上限（含首次）'],
  ['qualityRepairEnabled', '质量 repair 开关'],
  ['qualityRepairMaxAttempts', '每轮 repair 次数上限（不含首稿）'],
  ['planMaxAttempts', '每轮 Plan 提交上限（含首次）'],
  ['modelFailureRetryEnabled', '模型调用失败重试开关'],
  ['modelFailureExtraRetries', '主模型调用额外重试次数'],
  ['fallbackModelFailureExtraRetries', '备用模型调用额外重试次数'],
  ['fallbackEnabled', '备用模型切换开关'],
  ['argumentRepairEnabled', '生成参数修复开关'],
  ['argumentRepairMaxAttempts', '生成参数修复次数上限'],
  ['argumentRepairReminderCount', '生成参数修复提醒次数'],
] as const;

function valueText(value: boolean | number | undefined): string {
  if (value === undefined) return '未知';
  if (typeof value === 'boolean') return value ? '开启' : '关闭';
  return String(value);
}

export function BatchRetryParameters({ run }: { run: BatchRun }) {
  const observed = run.observedRetryParameters ?? {};
  const single = (name: string): boolean | number | undefined => {
    const values = observed[name];
    if (values?.length === 1) return values[0];
    return undefined;
  };
  const text = (name: string): string => {
    const values = observed[name];
    if (values?.length) return `${values.length > 1 ? '混合值：' : ''}${values.map(valueText).join(' / ')}`;
    return '未知';
  };
  const source = (names: string[]): string => {
    if (names.some((name) => observed[name]?.length)) return '来源：服务实际记录，未记录的参数显示未知';
    return '服务未记录配置，显示未知';
  };
  const enabled = single('interfaceRetryEnabled');
  const extra = single('interfaceExtraRetries');
  const explicitRounds = single('interfaceMaxAttempts');
  const mixedInterface = ['interfaceRetryEnabled', 'interfaceExtraRetries', 'interfaceMaxAttempts']
    .some((name) => (observed[name]?.length ?? 0) > 1);
  const interfaceRounds = mixedInterface ? undefined : typeof explicitRounds === 'number' ? explicitRounds
    : enabled === false ? 1 : enabled === true && typeof extra === 'number' ? extra + 1 : undefined;
  const repairEnabled = single('qualityRepairEnabled');
  const repairCount = single('qualityRepairMaxAttempts');
  const batchAttempts = typeof run.maxRetries === 'number' ? run.maxRetries + 1 : undefined;
  const totalRounds = batchAttempts !== undefined && interfaceRounds !== undefined
    ? batchAttempts * interfaceRounds : undefined;
  const totalRepairs = totalRounds === undefined ? undefined : repairEnabled === false ? 0
    : repairEnabled === true && typeof repairCount === 'number' ? totalRounds * repairCount : undefined;
  const parameterText = (name: string): string => {
    const switches: Record<string, string> = {
      interfaceExtraRetries: 'interfaceRetryEnabled',
      qualityRepairMaxAttempts: 'qualityRepairEnabled',
      modelFailureExtraRetries: 'modelFailureRetryEnabled',
      fallbackModelFailureExtraRetries: 'modelFailureRetryEnabled',
      argumentRepairMaxAttempts: 'argumentRepairEnabled',
    };
    const switchName = switches[name];
    return switchName !== undefined && single(switchName) === false
      ? `${text(name)}（开关关闭，不生效）` : text(name);
  };

  return <section className="batch-retry-parameters" aria-label="本次批跑重试参数">
    <div className="batch-retry-cards">
      <div><small>批跑重试</small>
        <strong>{batchAttempts === undefined ? '未知' : `额外 ${run.maxRetries} 次 · 最多 ${batchAttempts} 次请求`}</strong>
        <span>来源：本次执行配置</span>
      </div>
      <div><small>微服务整接口重试</small>
        <strong>{enabled === false ? '关闭 · 不进行整接口重试'
          : `${text('interfaceRetryEnabled')} · 额外次数 ${text('interfaceExtraRetries')}`}</strong>
        <span>每次请求最多 {interfaceRounds ?? '未知'} 轮完整生成</span>
        <span>{source(['interfaceRetryEnabled', 'interfaceExtraRetries', 'interfaceMaxAttempts'])}</span>
      </div>
      <div><small>每轮质量 repair</small>
        <strong>{repairEnabled === false ? '关闭 · 允许 0 次修复'
          : `${text('qualityRepairEnabled')} · 最多 ${text('qualityRepairMaxAttempts')} 次修复`}</strong>
        <span>首稿不计入 repair 次数，成功即停止</span>
        <span>{source(['qualityRepairEnabled', 'qualityRepairMaxAttempts'])}</span>
      </div>
    </div>
    <details className="batch-metric-details">
      <summary>查看各层重试开关、次数与来源</summary>
      <p>实际配置来自服务在本次请求中的记录，包括加载的配置或明确记录的执行上限。
        未触发分支也可能有配置预算。未知不等于关闭，实际尝试次数不用于推断上限。同一批次观测到不同配置时显示混合值。</p>
      <table className="batch-size-metrics"><thead><tr><th>参数</th><th>实际配置</th></tr></thead>
        <tbody>{PARAMETERS.map(([name, label]) => <tr key={name}>
          <td>{label}</td>
          <td>{parameterText(name)}</td>
        </tr>)}</tbody>
      </table>
    </details>
    {totalRounds !== undefined && <p className="batch-retry-budget">
      按所示预算，每个样本最多 {totalRounds} 轮完整生成
      {totalRepairs !== undefined ? `、${totalRepairs} 次 repair` : ''}。
      这是理论上限，成功或不可重试错误会提前结束；不包含模型传输重试的额外调用。
    </p>}
  </section>;
}
