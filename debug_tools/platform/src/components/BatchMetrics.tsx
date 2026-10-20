import type { BatchRate, BatchRun, BatchSampleSummary } from '../batchApi';

export function rateText(rate?: BatchRate): string {
  return rate?.percent == null ? '—' : `${rate.percent.toFixed(1)}%`;
}

function fraction(rate?: BatchRate): string {
  return rate ? `${rate.numerator}/${rate.denominator}` : '证据不足';
}

export function firstDraftLabel(sample: BatchSampleSummary): string {
  if (['queued', 'running'].includes(sample.status) && !sample.generationMetrics?.firstRequestStatus) {
    return '待统计';
  }
  return ({
    passed: '首稿通过', failed: '首稿失败', before_dsl_failure: '生成前失败', unknown: '未知',
  } as Record<string, string>)[sample.generationMetrics?.firstDsl ?? 'unknown'];
}

export function BatchMetrics({ run }: { run: BatchRun }) {
  const metrics = run.generationMetrics;
  const delivered = run.success + run.degraded;
  return (
    <section className="batch-generation-metrics" aria-label="生成质量指标">
      <div className="batch-quality-kpis">
        <div title="首次请求中，第一份 DSL 完成全部校验的通过数 / 有首轮评估证据的样本数。">
          <small>首次成功率（首稿校验）</small>
          <strong>{rateText(metrics?.firstDslPassRate)}</strong>
          <span>{fraction(metrics?.firstDslPassRate)}</span>
        </div>
        <div title="首次请求已交付 / 首次请求已结束；包含内部修复和降级，不含批跑重试。">
          <small>首次请求交付率</small>
          <strong>{rateText(metrics?.firstRequestDeliveryRate)}</strong>
          <span>{fraction(metrics?.firstRequestDeliveryRate)}</span>
        </div>
        <div title="成功或降级且已交付的样本 / 已结束的非取消样本。">
          <small>最终交付率（含降级）</small>
          <strong>{rateText(metrics?.finalDeliveryRate)}</strong>
          <span>{fraction(metrics?.finalDeliveryRate)}</span>
        </div>
        <div title="首次请求首稿失败后，在同一次请求内交付的样本 / 首稿失败且首次请求已结束的样本。">
          <small>内部修复挽救率</small>
          <strong>{rateText(metrics?.repairRescueRate)}</strong>
          <span>{fraction(metrics?.repairRescueRate)}</span>
        </div>
        <div title="批跑重试后交付的样本 / 已结束的重试样本；不包含请求内部修复。">
          <small>批跑重试挽救率</small>
          <strong>{rateText(metrics?.batchRetryRescueRate)}</strong>
          <span>{fraction(metrics?.batchRetryRescueRate)}</span>
        </div>
        <div title="已结束的非取消样本总耗时，包含其全部批跑尝试；使用最近秩 P95。">
          <small>P95 总耗时</small>
          <strong>{metrics?.p95ElapsedMs == null ? '—' : `${(metrics.p95ElapsedMs / 1000).toFixed(1)}s`}</strong>
          <span>包含批跑重试</span>
        </div>
      </div>
      <details className="batch-metric-details">
        <summary>统计口径、完整性与尺寸分组</summary>
        <div className="batch-metric-facts">
          <span>生成前失败 <b>{metrics?.preDslFailed ?? '—'}</b></span>
          <span>首稿证据缺失 <b>{metrics?.firstDslUnknown ?? '—'}</b></span>
          <span>批跑重试率 <b>{rateText(metrics?.batchRetryRate)}</b>（{fraction(metrics?.batchRetryRate)}）</span>
          <span>内部修复尝试 <b>{metrics?.qualityRepairAttempts ?? '—'}</b> 次
            <small>计数证据 {metrics?.repairObservedAttempts ?? 0}/{metrics?.terminalAttempts ?? 0} 次请求</small>
          </span>
          <span>模型物理调用 <b>{metrics?.modelPhysicalCalls ?? '—'}</b> 次
            <small>计数证据 {metrics?.modelObservedAttempts ?? 0}/{metrics?.terminalAttempts ?? 0} 次请求</small>
          </span>
          <span>交付信息缺失告警 <b>{metrics?.coverageObserved ? metrics.coverageMissing : '—'}</b> 个样本
            <small>覆盖检查证据 {metrics?.coverageObserved ?? 0}/{delivered} 个交付样本</small>
          </span>
        </div>
        <p>所有比率均显示分子/分母；取消、未运行和缺少证据的记录不补零。生成前失败单列，不计入首稿校验分母。
          内部修复与模型调用累计所有批跑尝试，证据不全时仅代表已观测部分。
          信息缺失告警来自最终 Plan 覆盖检查，不代表完整需求或视觉验收结论。</p>
        {!!metrics?.bySize.length && <table className="batch-size-metrics">
          <thead><tr><th>请求尺寸</th><th>首稿校验通过</th><th>首次请求交付</th><th>最终交付</th><th>信息缺失告警 / 已检查</th></tr></thead>
          <tbody>{metrics.bySize.map((group) => <tr key={group.size}>
            <td>{group.size === 'unknown' ? '未知' : group.size}</td>
            <td>{rateText(group.firstDslPassRate)} <small>({fraction(group.firstDslPassRate)})</small></td>
            <td>{rateText(group.firstRequestDeliveryRate)} <small>({fraction(group.firstRequestDeliveryRate)})</small></td>
            <td>{rateText(group.finalDeliveryRate)} <small>({fraction(group.finalDeliveryRate)})</small></td>
            <td>{group.coverageObserved ? group.coverageMissing : '—'} / {group.coverageObserved}</td>
          </tr>)}</tbody>
        </table>}
      </details>
    </section>
  );
}
