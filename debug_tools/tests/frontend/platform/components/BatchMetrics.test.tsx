import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it } from 'vitest';
import type { BatchMetricTotals, BatchRun, BatchSampleSummary } from '../../../../platform/src/batchApi';
import { BatchMetrics, firstDraftLabel } from '../../../../platform/src/components/BatchMetrics';

const totals: BatchMetricTotals = {
  firstDslPassRate: { numerator: 57, denominator: 119, percent: 47.9 },
  firstRequestDeliveryRate: { numerator: 102, denominator: 119, percent: 85.71 },
  finalDeliveryRate: { numerator: 110, denominator: 119, percent: 92.44 },
  repairRescueRate: { numerator: 45, denominator: 62, percent: 72.58 },
  batchRetryRate: { numerator: 17, denominator: 119, percent: 14.29 },
  batchRetryRescueRate: { numerator: 8, denominator: 17, percent: 47.06 },
  preDslFailed: 0, firstDslUnknown: 0, qualityRepairAttempts: 172,
  modelPhysicalCalls: 580, repairObservedAttempts: 136, modelObservedAttempts: 136,
  terminalAttempts: 136, coverageObserved: 110, coverageMissing: 8, p95ElapsedMs: 48123,
};

function run(metrics = true): BatchRun {
  return {
    runId: 'batch_test', status: 'completed', startedAt: '', endpoint: '', concurrency: 4,
    maxRetries: 1, total: 119, completed: 119,
    success: 110, degraded: 0, failed: 9, cancelled: 0, averageElapsedMs: 100,
    traceWarnings: 119, samples: [],
    generationMetrics: metrics ? { version: 1, ...totals, bySize: [{ size: '2x2', ...totals }] } : undefined,
  };
}

describe('BatchMetrics', () => {
  afterEach(cleanup);

  it('distinguishes the first draft, first request, final delivery and rescue rates', async () => {
    render(<BatchMetrics run={run()} />);
    const region = screen.getByRole('region', { name: '生成质量指标' });
    const draft = within(region).getByText('首次成功率（首稿校验）').parentElement;
    expect(draft).toHaveTextContent('47.9%');
    expect(draft).toHaveTextContent('57/119');
    expect(within(region).getByText('首次请求交付率').parentElement).toHaveTextContent('85.7%');
    expect(within(region).getByText('最终交付率（含降级）').parentElement).toHaveTextContent('92.4%');
    expect(within(region).getByText('P95 总耗时').parentElement).toHaveTextContent('48.1s');
    await userEvent.click(screen.getByText('统计口径、完整性与尺寸分组'));
    expect(screen.getByText(/^交付信息缺失告警/)).toHaveTextContent('8 个样本');
    expect(screen.getByText('覆盖检查证据 110/110 个交付样本')).toBeVisible();
    expect(screen.getByRole('cell', { name: '2x2' })).toBeVisible();
  });

  it('shows unknown evidence as unavailable instead of zero percent or a clean result', async () => {
    render(<BatchMetrics run={run(false)} />);
    expect(screen.getByText('首次成功率（首稿校验）').parentElement).toHaveTextContent('—');
    expect(screen.queryByText('0.0%')).not.toBeInTheDocument();
    await userEvent.click(screen.getByText('统计口径、完整性与尺寸分组'));
    expect(screen.getByText(/^交付信息缺失告警/)).toHaveTextContent('— 个样本');
    expect(screen.getByText('覆盖检查证据 0/110 个交付样本')).toBeVisible();
  });

  it('keeps a measured zero percent distinct from missing evidence', () => {
    const current = run();
    if (!current.generationMetrics) throw new Error('fixture metrics missing');
    current.generationMetrics.firstDslPassRate = { numerator: 0, denominator: 4, percent: 0 };
    render(<BatchMetrics run={current} />);
    expect(screen.getByText('首次成功率（首稿校验）').parentElement).toHaveTextContent('0.0%');
    expect(screen.getByText('首次成功率（首稿校验）').parentElement).toHaveTextContent('0/4');
  });

  it('labels pending samples separately from completed samples with missing trace', () => {
    const sample = { status: 'queued' } as BatchSampleSummary;
    expect(firstDraftLabel(sample)).toBe('待统计');
    expect(firstDraftLabel({ ...sample, status: 'success' })).toBe('未知');
  });
});
