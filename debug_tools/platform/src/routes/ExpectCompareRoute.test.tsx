import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { ExpectCompareRoute } from './ExpectCompareRoute';
import { WorkbenchProvider } from '../context';
import type { BatchRun, ExpectComparison } from '../batchApi';

const A2UI = JSON.stringify({ version: 'v0.9', createSurface: { surfaceId: 's', catalogId: 'c' } })
  + '\n' + JSON.stringify({ version: 'v0.9', updateComponents: { surfaceId: 's', root: 'root', components: [
    { id: 'root', component: 'Text', content: '天气' },
  ] } });

const LABELS = {
  data: { '/data/weather/current/condition': '天气状况' },
  actions: {
    'clickToDeeplink:Weather': '跳转链接 · 天气',
    'clickToIntent:Battery': '打开页面 · 电池设置',
  },
  icons: { 'common/images/sunny.png': '晴天' },
};

const expected = {
  sampleId: 'Q001', title: 'Q001', query: '做个天气卡片', size: '2x2', attempt: 'input',
  sizeSource: 'declared', genui: A2UI, category: '天气',
  fingerprint: {
    data: ['/data/weather/current/condition'],
    actions: ['clickToDeeplink:Weather'],
    icons: ['common/images/sunny.png'],
  },
  explicit: { data: [], actions: [] }, labels: LABELS,
  imageUrl: '/debug/expect/runs/imp/samples/Q001/input-image',
};
const actual = {
  sampleId: 'B002', title: '天气卡', query: '天气', size: '2x2', attempt: 'attempt_000',
  status: 'success', sizeSource: 'derived', genui: A2UI,
  fingerprint: {
    data: ['/data/weather/current/condition'],
    actions: [], icons: ['common/images/sunny.png'],
  },
  labels: LABELS,
};
const comparison: ExpectComparison = {
  importRunId: 'imp', importName: '期望批次', runId: 'session-live', runName: '本次会话调试记录',
  actualSource: 'session',
  summary: {
    expected: 1, actual: 2, matched: 0, none: 1,
  },
  options: { dimensions: ['data', 'actions', 'icons'] },
  categories: ['天气'],
  pairs: [{ expected, actual, tier: 'none', match: {
    tier: 'none',
    missingData: [], missingActions: ['clickToDeeplink:Weather'], missingIcons: [],
  }, diff: {
    data: { missing: [], extra: [] },
    actions: { missing: ['clickToDeeplink:Weather'], extra: ['clickToIntent:Battery'] },
    icons: { missing: [], extra: [] },
  } }],
  unmatchedActual: [{ ...actual, sampleId: 'B001', title: 'B001', query: '电量' }],
  warnings: ['演示警告'],
};

/** 完全匹配：分组视图只渲染这种配对，两侧卡片都会出现。 */
const fullActual = {
  ...actual,
  fingerprint: { ...actual.fingerprint, actions: ['clickToDeeplink:Weather'] },
};
const matchedCompare: ExpectComparison = {
  ...comparison,
  summary: { expected: 1, actual: 2, matched: 1, none: 0 },
  pairs: [{
    expected, actual: fullActual, tier: 'matched',
    match: {
      tier: 'matched', missingData: [], missingActions: [], missingIcons: [],
    },
    diff: {
      data: { missing: [], extra: [] }, actions: { missing: [], extra: [] },
      icons: { missing: [], extra: [] },
    },
  }],
  unmatchedActual: [{ ...actual, sampleId: 'B001', title: 'B001', query: '电量' }],
  warnings: [],
};

/** 内容全覆盖，只是期望 2x2、实际 2x4：尺寸不进指纹也不参与判定，仍算已匹配。 */
const sizesDiffer: ExpectComparison = {
  ...comparison,
  summary: { expected: 1, actual: 1, matched: 1, none: 0 },
  pairs: [{
    expected, tier: 'matched',
    actual: { ...actual, sampleId: 'B002', size: '2x4', sizeSource: 'declared',
      fingerprint: { ...actual.fingerprint, actions: ['clickToDeeplink:Weather'] } },
    match: {
      tier: 'matched', missingData: [], missingActions: [], missingIcons: [],
    },
    diff: {
      data: { missing: [], extra: [] }, actions: { missing: [], extra: [] },
      icons: { missing: [], extra: [] },
    },
  }],
  unmatchedActual: [],
};

/** 两个期望样本落到同一张实际卡片：页面应只出一张实际卡片并列出两条期望。 */
const multiToOne: ExpectComparison = {
  ...comparison,
  summary: { expected: 2, actual: 2, matched: 2, none: 0 },
  pairs: [{
    ...comparison.pairs[0],
    tier: 'matched',
    match: { ...comparison.pairs[0].match!, tier: 'matched', missingActions: [] },
  }, {
    ...comparison.pairs[0],
    tier: 'matched',
    match: { ...comparison.pairs[0].match!, tier: 'matched', missingActions: [] },
    expected: { ...expected, sampleId: 'Q002', title: 'Q002', query: '再来一张天气卡' },
  }],
  unmatchedActual: [],
};

function response(body: unknown, status = 200): Response {
  return { ok: status < 400, status, json: async () => body } as Response;
}

const DEFAULT_RUNS: Partial<BatchRun>[] = [
  { runId: 'imp', name: '期望批次', status: 'completed', sourceType: 'external-quality',
    total: 3 },
  { runId: 'run1', name: '十月中旬批跑', status: 'completed' },
];

/** 期望侧不再挑批次：进页面只等期望池读完即可。 */
async function waitForPool() {
  await screen.findByText(/已导入 3 条 · 1 个批次/);
}

function mockApi(status = 200, body: ExpectComparison = comparison, runs = DEFAULT_RUNS) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
    const url = String(input);
    if (url === '/debug/batch/runs') return response({ items: runs });
    if (url === '/debug/expect/compare-live') {
      return response(status === 200 ? body : { detail: '实际输出为空' }, status);
    }
    if (url.startsWith('/debug/expect/compare?')) {
      return response(status === 200 ? body : { detail: '批次结果不可读' }, status);
    }
    throw new Error(`unexpected request: ${url}`);
  });
}

/** 会话调用历史：端到端调试拿到的一张 2x2 天气卡。 */
function seedSessionCall(genui: string) {
  window.sessionStorage.setItem('ai-widget-debug-call-history:v1', JSON.stringify({
    calls: [{
      id: 'call-weather-1', operation: 'generateWidgetCardCompactDsl', source: 'e2e',
      status: 'success', startedAt: '2026-10-17T08:00:00.000Z',
      finishedAt: '2026-10-17T08:00:06.000Z',
      request: { utterance: { original: '做个天气卡片，点击跳转到天气详情' } },
      response: { operation: 'generateWidgetCardCompactDsl', status: 'success',
        data: { genui, cardSpec: { suggestSize: '2x2' } } },
    }],
    selectedCallId: 'call-weather-1',
  }));
}

function renderRoute(entry = '/expect') {
  return render(<WorkbenchProvider>
    <MemoryRouter initialEntries={[entry]}><ExpectCompareRoute /></MemoryRouter>
  </WorkbenchProvider>);
}

/** 卡片区默认折叠（留在卡片区的都是已匹配的配对）：要看左右对比的用例先展开。 */
function expandAll() {
  fireEvent.click(screen.getAllByRole('button', { name: '全部展开' })[0]);
}

async function openComparison(body: ExpectComparison = comparison) {
  mockApi(200, body);
  seedSessionCall(A2UI);
  renderRoute();
  await waitForPool();
  fireEvent.click(screen.getByRole('checkbox', { name: /端到端/ }));
  fireEvent.click(screen.getByRole('button', { name: '自动匹配并对比' }));
  await screen.findByRole('heading', { name: '匹配汇总' });
}

describe('ExpectCompareRoute', () => {
  afterEach(() => {
    cleanup(); vi.restoreAllMocks();
    window.sessionStorage.clear();
    window.localStorage.clear();
  });

  it('compares only against this session\'s output and groups pairs by actual sample', async () => {
    const fetchMock = mockApi();
    seedSessionCall(A2UI);
    renderRoute();
    // 页面上不再出现批跑来源或批跑下拉。
    // 实际来源与期望池都在表单上，但进页面不自动发起对比。
    expect(screen.getByRole('radio', { name: '本次会话的真实输出' })).toBeChecked();
    fireEvent.click(screen.getByRole('checkbox', { name: /端到端/ }));
    fireEvent.click(screen.getByRole('button', { name: '自动匹配并对比' }));
    await screen.findByRole('heading', { name: '匹配汇总' });
    expect(screen.getByText('演示警告')).toBeInTheDocument();
    expect(screen.getByText(/真实输出来源：本次会话调试记录/)).toBeInTheDocument();
    expect(screen.getAllByText('未匹配').length).toBeGreaterThan(0);
    // 精度、权重、覆盖率与综合分不再是这个页面的概念。
    expect(screen.queryByLabelText('最低匹配精度（%）')).toBeNull();
    expect(screen.queryByText(/权重/)).toBeNull();
    expect(screen.queryByText(/覆盖率|综合分|综合 /)).toBeNull();
    // 未匹配的期望不进分组，也不再渲染卡片：只在配对明细表里给出层级与缺项。
    expect(screen.queryByRole('heading', { name: '真实输出 · 天气卡' })).toBeNull();
    expect(screen.queryByText(/未匹配的期望（/)).toBeNull();
    const row = screen.getByText('Q001 · Q001').closest('tr') as HTMLElement;
    expect(within(row).getByText('未匹配')).toBeInTheDocument();
    expect(within(row).getByText('跳转链接 · 天气')).toBeInTheDocument();
    expect(fetchMock.mock.calls.filter(([url]) => String(url).includes('/compare')))
      .toHaveLength(1);
    expect(fetchMock.mock.calls.every(([url]) => !String(url).includes('compare?'))).toBe(true);
  });

  it('renders Chinese labels for data, actions and icons while keeping raw tokens in title', async () => {
    await openComparison(matchedCompare);
    expandAll();
    expect(screen.getAllByText('天气状况').length).toBeGreaterThan(0);
    expect(screen.getAllByText('跳转链接 · 天气').length).toBeGreaterThan(0);
    expect(screen.getAllByText('晴天').length).toBeGreaterThan(0);
    expect(screen.getAllByTitle('天气状况 · /data/weather/current/condition').length)
      .toBeGreaterThan(0);
  });

  it('spells out the missing and extra tokens in the pair table verdict', async () => {
    await openComparison();
    const row = screen.getByText('Q001 · Q001').closest('tr') as HTMLElement;
    expect(within(row).getByText('缺项')).toBeInTheDocument();
    expect(within(row).getByText('跳转链接 · 天气')).toBeInTheDocument();
    expect(within(row).getByText('多出')).toBeInTheDocument();
    expect(within(row).getByText('打开页面 · 电池设置')).toBeInTheDocument();
  });

  it('lists query, size, data, actions and icons under both the expected and actual card', async () => {
    await openComparison(matchedCompare);
    expandAll();
    const group = document.querySelector('.expect-group') as HTMLElement;
    const cards = group.querySelectorAll('.expect-group-expected .expect-card, '
      + '.expect-group-actual .expect-card');
    expect(cards).toHaveLength(2);
    const [left, right] = [...cards].map((node) => within(node as HTMLElement));
    expect(left.getByText('做个天气卡片')).toBeInTheDocument();
    expect(right.getByText('天气')).toBeInTheDocument();
    expect(left.getByText('天气状况')).toBeInTheDocument();
    expect(right.getByText('天气状况')).toBeInTheDocument();
    // 两侧身份写在卡片上：左「期望输出」、右「真实输出」。
    expect(left.getByText('期望输出')).toBeInTheDocument();
    expect(right.getByText('真实输出')).toBeInTheDocument();
    expect(left.getByText('尺寸')).toBeInTheDocument();
    expect(right.getByText('动作')).toBeInTheDocument();
    expect(left.getByText('图标')).toBeInTheDocument();
    expect(left.getByText(/2x2/)).toBeInTheDocument();
    expect(right.getByText(/2x2/)).toBeInTheDocument();
  });

  it('shows multiple expected cards under a single actual card', async () => {
    await openComparison(multiToOne);
    expandAll();
    expect(screen.getByText('2 个已匹配期望')).toBeInTheDocument();
    expect(document.querySelectorAll('.expect-group')).toHaveLength(1);
    expect(document.querySelectorAll('.expect-group-actual .expect-card')).toHaveLength(1);
    expect(document.querySelectorAll('.expect-group-expected .expect-card')).toHaveLength(2);
  });

  it('treats 2x2 and 2x4 with the same content as a match', async () => {
    await openComparison(sizesDiffer);
    expandAll();
    // 尺寸不进指纹：两侧卡片都渲染，层级是已匹配。
    const group = document.querySelector('.expect-group') as HTMLElement;
    expect(within(group).getAllByText('已匹配').length).toBeGreaterThan(0);
    expect(group.querySelectorAll('.expect-group-expected .expect-card')).toHaveLength(1);
    expect(group.querySelectorAll('.expect-group-actual .expect-card')).toHaveLength(1);
    const row = screen.getByText('Q001 · Q001').closest('tr') as HTMLElement;
    expect(within(row).getByText('已匹配')).toBeInTheDocument();
    expect(within(row).getByText('需求项全部命中')).toBeInTheDocument();
    // 尺寸仍作为信息展示，只是不参与判定。
    expect(within(row).getByText('2x2 ／ 2x4')).toBeInTheDocument();
    expect(screen.queryByText(/尺寸不一致/)).toBeNull();
  });

  it('uses every imported expectation without asking for a batch', async () => {
    const fetchMock = mockApi();
    seedSessionCall(A2UI);
    renderRoute();
    // 期望侧不再有批次下拉，只有已导入的汇总说明。
    expect(screen.queryByLabelText(/期望批次/)).toBeNull();
    await waitForPool();
    // 批次名不再铺一整行，只在 title 里给悬停提示。
    expect(screen.getByTitle('期望批次 · imp')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('checkbox', { name: /端到端/ }));
    fireEvent.click(screen.getByRole('button', { name: '自动匹配并对比' }));
    await screen.findByRole('heading', { name: '匹配汇总' });
    // 请求里不带 importRunId：期望侧由后端汇总全部导入批次。
    const [, init] = fetchMock.mock.calls.find(([, item]) =>
      String(item?.body ?? '').includes('actuals'))!;
    expect(JSON.parse(String(init?.body))).not.toHaveProperty('importRunId');
  });

  it('opens the uploaded screenshot instead of the rendered card', async () => {
    await openComparison(matchedCompare);
    expandAll();
    fireEvent.click(screen.getByRole('checkbox', { name: '显示上传截图' }));
    expect(screen.getByRole('img', { name: 'Q001 上传截图' }))
      .toHaveAttribute('src', '/debug/expect/runs/imp/samples/Q001/input-image');
  });

  it('surfaces backend conflicts as alerts', async () => {
    mockApi(409);
    seedSessionCall(A2UI);
    renderRoute();
    fireEvent.click(screen.getByRole('checkbox', { name: /端到端/ }));
    fireEvent.click(screen.getByRole('button', { name: '自动匹配并对比' }));
    await screen.findByRole('alert');
  });

  it('submits only the selected filter dimensions', async () => {
    const fetchMock = mockApi();
    seedSessionCall(A2UI);
    renderRoute();
    fireEvent.click(screen.getByRole('checkbox', { name: /端到端/ }));
    fireEvent.click(screen.getByRole('checkbox', { name: '动作' }));
    fireEvent.click(screen.getByRole('button', { name: '自动匹配并对比' }));
    await screen.findByRole('heading', { name: '匹配汇总' });
    const post = fetchMock.mock.calls.find(([, init]) =>
      (init as RequestInit | undefined)?.method === 'POST');
    expect(post?.[0]).toBe('/debug/expect/compare-live');
    // 后端按 JSON 体解析模型，漏了 Content-Type 会被判成字符串而 422。
    expect((post?.[1]?.headers as Record<string, string>)['Content-Type'])
      .toBe('application/json');
    const body = JSON.parse(String(post?.[1]?.body));
    expect(body.dimensions).toEqual(['data', 'icons']);
    expect(body).not.toHaveProperty('minScore');
    expect(body.actuals).toEqual([{
      id: 'call-weather-1', title: '端到端 · generateWidgetCardCompactDsl',
      query: '做个天气卡片，点击跳转到天气详情', genui: A2UI, size: '2x2',
    }]);
  });

  it('filters the grouped view by tier, category and query', async () => {
    await openComparison(matchedCompare);
    expect(screen.getByRole('heading', { name: '真实输出 · 天气卡' })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('匹配层级'), { target: { value: 'none' } });
    expect(screen.getByText('没有符合筛选条件的已匹配配对')).toBeInTheDocument();
    expect(screen.getByText(/显示 0 对配对/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('匹配层级'), { target: { value: 'matched' } });
    expect(screen.getByRole('heading', { name: '真实输出 · 天气卡' })).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('数据分类'), { target: { value: '__none__' } });
    expect(screen.getByText('没有符合筛选条件的已匹配配对')).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('数据分类'), { target: { value: '天气' } });
    fireEvent.change(screen.getByLabelText('筛选 Query'), { target: { value: '电量' } });
    expect(screen.getByText('没有符合筛选条件的已匹配配对')).toBeInTheDocument();
  });

  it('defaults to a finished batch run when the session has no output yet', async () => {
    mockApi();
    renderRoute();
    const batchRadio = screen.getByRole('radio', { name: '已落盘的批跑运行／导入的实际输出' });
    await waitFor(() => expect(batchRadio).toBeChecked());
    expect(screen.getByLabelText('真实输出来源批次')).toHaveValue('run1');
    expect(screen.queryByText(/勾选至少一条真实输出/)).toBeNull();
    expect(screen.queryByText(/还没有带 DSL 的成功调用/)).toBeNull();
  });

  it('keeps the session source and tells the user to generate a card when no run exists',
    async () => {
      mockApi(200, comparison, [DEFAULT_RUNS[0]]);
      renderRoute();
      expect(await screen.findByText(/还没有带 DSL 的成功调用/)).toBeInTheDocument();
      expect(screen.getByRole('radio', { name: '本次会话的真实输出' })).toBeChecked();
    });

  it('picks the newest finished run when the list mixes both time formats', async () => {
    mockApi(200, comparison, [
      DEFAULT_RUNS[0],
      { runId: 'old', name: '早先批跑', status: 'completed',
        startedAt: '2026/10/17 09:00:00', finishedAt: '2026/10/17 09:05:00' },
      { runId: 'new', name: '新批跑', status: 'completed',
        startedAt: '2026-10-18T03:57:43+00:00', finishedAt: '2026-10-18T03:57:43+00:00' },
    ]);
    renderRoute();
    await waitFor(() => expect(screen.getByLabelText('真实输出来源批次')).toHaveValue('new'));
  });

  it('leaves module switching to the left sidebar and keeps only the import entry here', async () => {
    mockApi();
    renderRoute();
    const nav = screen.getByRole('navigation', { name: '期望对比工具' });
    expect(within(nav).getByRole('link', { name: '导入期望输出' }))
      .toHaveAttribute('href', '/expect/import');
    expect(within(nav).getByRole('link', { name: '期望数据画廊' }))
      .toHaveAttribute('href', '/expect/gallery');
    expect(within(nav).queryByRole('link', { name: '质量评分' })).toBeNull();
    expect(within(nav).queryByRole('link', { name: '批量测试' })).toBeNull();
  });

  it('keeps the rule line short and the full wording one click away', async () => {
    mockApi();
    renderRoute();
    const method = screen.getByRole('region', { name: '比对方法' });
    // 默认只占一行：判定口径摘要。
    expect(within(method).getByText(/尺寸不进指纹、不参与判定/)).toBeInTheDocument();
    fireEvent.click(within(method).getByText('展开完整口径'));
    expect(within(method).getByText(/按启用维度筛选/)).toBeInTheDocument();
    expect(within(method).getByText(/缺任意一项即「未匹配」/)).toBeInTheDocument();
    expect(within(method).getByText('至少一个期望需求项在实际指纹里找不到')).toBeInTheDocument();
  });

  it('lists which expected sample paired with which actual sample and the verdict',
    async () => {
      await openComparison();
      const overview = screen.getByText(/配对明细表/).closest('details')!;
      const row = within(overview).getByText('Q001 · Q001').closest('tr')!;
      expect(within(row).getByText('B002 · 天气卡')).toBeInTheDocument();
      expect(within(row).getByText('未匹配')).toBeInTheDocument();
      expect(within(row).getByText('2x2 ／ 2x2')).toBeInTheDocument();
      expect(within(overview).getByText('B001 · B001')).toBeInTheDocument();
      expect(within(overview).getByText('没有期望匹配到它')).toBeInTheDocument();
    });

  it('puts the record id into the picker so a real output stays identifiable', async () => {
    mockApi();
    seedSessionCall(A2UI);
    renderRoute();
    const picker = await screen.findByText(/记录 call-weather-1/);
    expect(picker.textContent).toContain('做个天气卡片，点击跳转到天气详情');
  });

  it('says what is still missing before the comparison can run', async () => {
    mockApi();
    seedSessionCall(A2UI);
    renderRoute();
    expect(await screen.findByText(/还不能比对，还差：勾选至少一条真实输出/)).toBeInTheDocument();
  });

  it('compares against a finished batch run when that source is picked', async () => {
    const fetchMock = mockApi();
    renderRoute();
    await waitForPool();
    fireEvent.click(screen.getByRole('radio', { name: '已落盘的批跑运行／导入的实际输出' }));
    const runSelect = screen.getByLabelText('真实输出来源批次');
    await within(runSelect).findByRole('option', { name: '[批跑] 十月中旬批跑 · run1' });
    fireEvent.change(runSelect, { target: { value: 'run1' } });
    // 批跑来源不需要会话记录，也不应再提示勾选真实输出。
    expect(screen.queryByText(/勾选至少一条真实输出/)).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '自动匹配并对比' }));
    await screen.findByRole('heading', { name: '匹配汇总' });
    const url = String(fetchMock.mock.calls.at(-1)?.[0]);
    expect(url).toBe('/debug/expect/compare?runId=run1&dimensions=data%2Cactions%2Cicons');
  });

  it('offers imported real outputs as the actual side and never as the expectation pool',
    async () => {
      const importedActual: Partial<BatchRun> = {
        runId: 'act', name: '外部实际输出', status: 'completed',
        sourceType: 'external-quality', purpose: 'actual', total: 4,
        startedAt: '2026-10-18T04:00:00+00:00', finishedAt: '2026-10-18T04:00:00+00:00',
      };
      const fetchMock = mockApi(200, comparison, [...DEFAULT_RUNS, importedActual]);
      renderRoute();
      await waitForPool();
      // 期望池只数 purpose=expect 的导入批次：实际输出批次进来会自己和自己配对。
      expect(screen.getByText(/已导入 3 条 · 1 个批次/)).toBeInTheDocument();
      expect(screen.getByText(/已导入实际输出 4 条/)).toBeInTheDocument();
      fireEvent.click(screen.getByRole('radio', { name: '已落盘的批跑运行／导入的实际输出' }));
      const runSelect = screen.getByLabelText('真实输出来源批次');
      // 时间最新的排最前：导入的实际输出批次要能在下拉里选到，并标明来源。
      await within(runSelect).findByRole('option', { name: '[导入实际] 外部实际输出 · act' });
      expect(within(runSelect).queryByRole('option', { name: /期望批次 · imp/ })).toBeNull();
      fireEvent.change(runSelect, { target: { value: 'act' } });
      fireEvent.click(screen.getByRole('button', { name: '自动匹配并对比' }));
      await screen.findByRole('heading', { name: '匹配汇总' });
      expect(String(fetchMock.mock.calls.at(-1)?.[0]))
        .toBe('/debug/expect/compare?runId=act&dimensions=data%2Cactions%2Cicons');
    });

  it('links to the real output import from the comparison page', async () => {
    mockApi();
    renderRoute();
    const nav = screen.getByRole('navigation', { name: '期望对比工具' });
    expect(within(nav).getByRole('link', { name: '导入实际输出' }))
      .toHaveAttribute('href', '/expect/actual-import');
  });

  it('keeps unmatched expectations out of the card view and only in the pair table',
    async () => {
      await openComparison();
      // 页面底部不再有「未匹配的期望」区，也没有任何期望卡片被渲染出来。
      expect(screen.queryByText(/未匹配的期望（/)).toBeNull();
      expect(document.querySelectorAll('.expect-group-expected .expect-card')).toHaveLength(0);
      const row = screen.getByText('Q001 · Q001').closest('tr') as HTMLElement;
      expect(within(row).getByText('未匹配')).toBeInTheDocument();
      expect(within(row).getByText('B002 · 天气卡')).toBeInTheDocument();
      // 未配对的实际输出仍在明细表里留一行，避免被误判成"没跑"。
      expect(screen.getByText('没有期望匹配到它')).toBeInTheDocument();
    });

  it('marks an expectation without any counterpart in the table instead of comparing a card',
    async () => {
      await openComparison({
        ...comparison,
        summary: { expected: 1, actual: 1, matched: 0, none: 0 },
        pairs: [{ expected, actual: null, match: null, diff: null, tier: 'no-actual' }],
        unmatchedActual: [actual],
        warnings: ['1 条期望没有同名或同 Query 的实际输出，已标为「没有对应的实际输出」：Q001'],
      });
      expect(document.querySelectorAll('.expect-group-expected .expect-card')).toHaveLength(0);
      const row = screen.getByText('Q001 · Q001').closest('tr') as HTMLElement;
      expect(within(row).getByText('没有可比的真实输出')).toBeInTheDocument();
      expect(within(row).getByText('没有同名样本、无相同 Query，分类＋数据＋动作也未强绑定')).toBeInTheDocument();
      expect(screen.getByText(/强绑定不成立/)).toBeInTheDocument();
    });

  it('restores the last selection and re-runs it without asking again', async () => {
    const fetchMock = mockApi();
    window.localStorage.setItem('ai-widget-expect-compare:v1', JSON.stringify({
      actualSource: 'batch', actualRunId: 'run1', sessionIds: [],
      dimensions: ['data', 'actions', 'icons'], tier: 'all', category: 'all', search: '',
      hasResult: true,
    }));
    renderRoute();
    // 进页面即按上次配置重跑：来源、运行与维度都还有效，不需要重新选。
    expect(screen.getByRole('radio', { name: '已落盘的批跑运行／导入的实际输出' })).toBeChecked();
    await waitFor(() => expect(screen.getByLabelText('真实输出来源批次')).toHaveValue('run1'));
    await screen.findByRole('heading', { name: '匹配汇总' });
    expect(fetchMock.mock.calls.map(([url]) => String(url)))
      .toContain('/debug/expect/compare?runId=run1&dimensions=data%2Cactions%2Cicons');
  });

  it('remembers the selection for the next visit', async () => {
    await openComparison(matchedCompare);
    const saved = JSON.parse(String(window.localStorage
      .getItem('ai-widget-expect-compare:v1')));
    expect(saved).toMatchObject({
      actualSource: 'session', dimensions: ['data', 'actions', 'icons'], hasResult: true,
    });
    expect(saved.sessionIds).toEqual(['call-weather-1']);
  });

  it('forgets everything when the memory is cleared', async () => {
    await openComparison(matchedCompare);
    fireEvent.click(screen.getByRole('button', { name: '清除记忆' }));
    // 清掉的是"上次跑出过结果"的标记与全部选择，不会留下会自动重跑的配置。
    expect(JSON.parse(String(window.localStorage
      .getItem('ai-widget-expect-compare:v1')))).toMatchObject({
      actualSource: 'session', actualRunId: '', sessionIds: [], hasResult: false,
    });
    expect(screen.queryByRole('heading', { name: '匹配汇总' })).toBeNull();
    expect(screen.getByRole('radio', { name: '本次会话的真实输出' })).toBeChecked();
  });

  it('keeps matched groups folded until asked, with expand and collapse controls', async () => {
    await openComparison(matchedCompare);
    // 默认只有一行摘要：没有渲染任何卡片。
    expect(document.querySelectorAll('.expect-group-expected .expect-card')).toHaveLength(0);
    // 有一个真实输出样本没有匹配到期望，它也会成一组，所以按钮不止一个。
    expect(screen.getAllByRole('button', { name: '展开对比' })[0]).toHaveAttribute(
      'aria-expanded', 'false');
    expandAll();
    expect(document.querySelectorAll('.expect-group-expected .expect-card')).toHaveLength(1);
    // 收起后回到折叠态，明细表始终在。
    fireEvent.click(screen.getByRole('button', { name: '全部收起' }));
    expect(document.querySelectorAll('.expect-group-expected .expect-card')).toHaveLength(0);
    expect(screen.getByText('配对明细表（1 对，含未匹配）')).toBeInTheDocument();
  });

  it('shows the raw field name next to its Chinese label', async () => {
    await openComparison();
    expandAll();
    const chip = screen.getAllByTitle('天气状况 · /data/weather/current/condition')[0];
    expect(within(chip as HTMLElement).getByText('天气状况')).toBeInTheDocument();
    expect(within(chip as HTMLElement).getByText('/data/weather/current/condition'))
      .toBeInTheDocument();
  });

});
