import { cleanup, render, screen, within } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it } from 'vitest';
import type { BatchRun } from '../batchApi';
import { BatchRetryParameters } from './BatchRetryParameters';

function run(): BatchRun {
  return {
    runId: 'batch_retry', status: 'completed', startedAt: '', endpoint: '', concurrency: 4,
    maxRetries: 1, total: 1, completed: 1, success: 1, degraded: 0, failed: 0,
    cancelled: 0, averageElapsedMs: 10, traceWarnings: 0, samples: [],
  };
}

describe('BatchRetryParameters', () => {
  afterEach(cleanup);

  it('shows each configured retry layer and distinguishes five repairs from three generations', async () => {
    const current = run();
    current.observedRetryParameters = {
      interfaceRetryEnabled: [true], interfaceExtraRetries: [2], interfaceMaxAttempts: [3],
      qualityRepairEnabled: [true], qualityRepairMaxAttempts: [5], planMaxAttempts: [2],
      modelFailureRetryEnabled: [false], modelFailureExtraRetries: [1],
    };
    render(<BatchRetryParameters run={current} />);
    expect(screen.getByText('批跑重试').parentElement).toHaveTextContent('额外 1 次 · 最多 2 次请求');
    expect(screen.getByText('微服务整接口重试').parentElement).toHaveTextContent('每次请求最多 3 轮完整生成');
    expect(screen.getByText('每轮质量 repair').parentElement).toHaveTextContent('最多 5 次修复');
    expect(screen.getByText(/按所示预算/)).toHaveTextContent('最多 6 轮完整生成、30 次 repair');
    await userEvent.click(screen.getByText('查看各层重试开关、次数与来源'));
    const row = screen.getByRole('row', { name: /模型调用失败重试开关/ });
    expect(within(row).getByRole('cell', { name: '关闭' })).toBeVisible();
    expect(screen.getByRole('row', { name: /每轮 Plan 提交上限/ })).toHaveTextContent('2');
  });

  it('never fills historical repair budgets with the current defaults or observed repair count', () => {
    const current = run();
    current.observedRetryParameters = { interfaceMaxAttempts: [1], planMaxAttempts: [2] };
    render(<BatchRetryParameters run={current} />);
    expect(screen.getByText('每轮质量 repair').parentElement).toHaveTextContent('未知');
    expect(screen.getByText('微服务整接口重试').parentElement).toHaveTextContent('每次请求最多 1 轮完整生成');
    expect(screen.getByText(/按所示预算/)).toHaveTextContent('最多 2 轮完整生成');
    expect(screen.getByText(/按所示预算/)).not.toHaveTextContent('次 repair');
  });

  it('shows only actual values when a saved task snapshot differs', async () => {
    const current = run();
    current.retryConfigSnapshot = { qualityRepairEnabled: true, qualityRepairMaxAttempts: 3 };
    current.observedRetryParameters = { qualityRepairEnabled: [true], qualityRepairMaxAttempts: [5] };
    render(<BatchRetryParameters run={current} />);
    expect(screen.getByText('每轮质量 repair').parentElement).toHaveTextContent('最多 5 次修复');
    await userEvent.click(screen.getByText('查看各层重试开关、次数与来源'));
    const row = screen.getByRole('row', { name: /每轮 repair 次数上限/ });
    expect(within(row).getByRole('cell', { name: '5' })).toBeVisible();
    expect(within(row).queryByRole('cell', { name: '3' })).not.toBeInTheDocument();
    expect(screen.getAllByRole('columnheader')).toHaveLength(2);
    expect(screen.getByRole('columnheader', { name: '实际配置' })).toBeVisible();
    expect(screen.queryByText('受管任务快照')).not.toBeInTheDocument();
  });

  it('shows mixed configurations instead of inventing one batch-wide limit', () => {
    const current = run();
    current.observedRetryParameters = {
      interfaceMaxAttempts: [1, 3], qualityRepairEnabled: [true], qualityRepairMaxAttempts: [3, 5],
    };
    render(<BatchRetryParameters run={current} />);
    expect(screen.getByText('每轮质量 repair').parentElement).toHaveTextContent('混合值：3 / 5');
    expect(screen.queryByText(/按所示预算/)).not.toBeInTheDocument();
  });

  it('does not fill missing actual switches from a task snapshot', () => {
    const current = run();
    current.observedRetryParameters = { qualityRepairMaxAttempts: [5] };
    current.retryConfigSnapshot = { qualityRepairEnabled: true };
    render(<BatchRetryParameters run={current} />);
    expect(screen.getByText('每轮质量 repair').parentElement)
      .toHaveTextContent('未知 · 最多 5 次修复');
    expect(screen.queryByText(/按所示预算/)).not.toBeInTheDocument();
  });

  it('does not use task snapshots to display actual values or calculate budgets', () => {
    const current = run();
    current.retryConfigSnapshot = {
      interfaceRetryEnabled: false, interfaceExtraRetries: 2,
      qualityRepairEnabled: true, qualityRepairMaxAttempts: 5,
    };
    render(<BatchRetryParameters run={current} />);
    expect(screen.getByText('微服务整接口重试').parentElement).toHaveTextContent('每次请求最多 未知 轮完整生成');
    expect(screen.getByText('每轮质量 repair').parentElement).toHaveTextContent('未知 · 最多 未知 次修复');
    expect(screen.queryByText(/按所示预算/)).not.toBeInTheDocument();
  });

  it('shows zero effective retries and marks configured counts inactive when switches are off', async () => {
    const current = run();
    current.observedRetryParameters = {
      interfaceRetryEnabled: [false], interfaceExtraRetries: [2], interfaceMaxAttempts: [1],
      qualityRepairEnabled: [false], qualityRepairMaxAttempts: [5],
      modelFailureRetryEnabled: [false], modelFailureExtraRetries: [1],
    };
    render(<BatchRetryParameters run={current} />);
    expect(screen.getByText('微服务整接口重试').parentElement).toHaveTextContent('关闭 · 不进行整接口重试');
    expect(screen.getByText('每轮质量 repair').parentElement).toHaveTextContent('关闭 · 允许 0 次修复');
    expect(screen.getByText(/按所示预算/)).toHaveTextContent('最多 2 轮完整生成、0 次 repair');
    await userEvent.click(screen.getByText('查看各层重试开关、次数与来源'));
    expect(screen.getByRole('row', { name: /整接口额外重试次数/ })).toHaveTextContent('2（开关关闭，不生效）');
    expect(screen.getByRole('row', { name: /每轮 repair 次数上限/ })).toHaveTextContent('5（开关关闭，不生效）');
    expect(screen.getByRole('row', { name: /主模型调用额外重试次数/ })).toHaveTextContent('1（开关关闭，不生效）');
  });
});
