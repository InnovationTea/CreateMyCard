import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Route, Routes, useLocation } from 'react-router-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  ExpectImportRoute, cardspecUserQuery, classifyContentText,
  readImportFolder, readImportSelection, sampleStem,
} from './ExpectImportRoute';

/**
 * 导入页会拉候选库、识别内容文件格式、再提交批次。
 * 识别按真实规则回 kind：JSONL／数组是 dsl，带 dataBindings 的对象是 cardspec。
 */
function mockImport(existing: { id: string; runId?: string; runName?: string }[] = []) {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    // 导入页会并发拉一次候选库；这里只满足它，导入本身仍按各用例自己的返回值处理。
    if (String(input).startsWith('/debug/expect/sample-ids')) {
      return { ok: true, json: async () => ({ items: existing.map((item) => ({
        runId: item.runId ?? 'batch_import_old',
        runName: item.runName ?? '旧期望批次',
        id: item.id,
      })) }) } as Response;
    }
    if (String(input) === '/debug/expect/options') {
      return { ok: true, json: async () => ({
        data: [{ value: '/data/weather/current/condition', label: '天气 · 当前 · 天气状况' }],
        actions: [{ value: 'clickToDeeplink:Weather_CityCode', label: '跳转链接 · 天气城市页' }],
        icons: [{ value: 'resources/base/media/bell_fill.svg', label: '通知铃铛彩色图标' }],
      }) } as Response;
    }
    if (String(input) === '/debug/expect/detect') {
      const text = String(JSON.parse(String(init?.body ?? '{}')).text ?? '');
      const kind = classifyContentText(text);
      return { ok: true, json: async () => ({
        kind,
        size: kind === 'cardspec' ? '2x2' : '',
        note: '',
        fingerprint: {
          data: ['/data/weather/current/condition'],
          actions: ['clickToDeeplink:Weather_CityCode'],
          icons: ['resources/base/media/bell_fill.svg'],
        },
      }) } as Response;
    }
    return { ok: true, json: async () => ({ runId: 'imported' }) } as Response;
  });
}

/** 只取提交批次那一次请求：候选库与格式识别都是 POST，必须按地址筛。 */
function importCall(fetchMock: ReturnType<typeof mockImport>) {
  const call = fetchMock.mock.calls.find(([url]) => String(url) === '/debug/expect/import');
  return {
    submitted: Boolean(call),
    url: String(call?.[0]),
    body: JSON.parse(String(call?.[1]?.body ?? '{}')),
  };
}

/** 拖进来的文件夹在浏览器里就是这种条目：无扩展名、体积 0、没有 MIME 类型。 */
function folder(name: string) {
  return new File([], name, { type: '' });
}

function file(path: string, content: string, type = 'application/json') {
  const value = new File([content], path.split('/').at(-1)!, { type });
  Object.defineProperties(value, {
    webkitRelativePath: { value: `dataset/${path}` },
    text: { value: async () => content },
    arrayBuffer: { value: async () => new TextEncoder().encode(content).buffer },
  });
  return value;
}

/** 选内容文件会触发一次格式识别（异步）：等到识别结果出现再往下操作。 */
async function chooseContent(input: HTMLElement, name: string, content: string) {
  fireEvent.change(input, { target: { files: [file(name, content)] } });
  await screen.findByText(/已识别：/);
}

/** 需要人工 ID 的用例先勾上复选框：默认不勾选时 ID 由后端生成。 */
function useCustomIds() {
  fireEvent.click(screen.getByLabelText('使用自定义样本 ID'));
}

describe('ExpectImportRoute', () => {
  afterEach(() => { cleanup(); vi.restoreAllMocks(); });

  it('accepts the legacy delivery manifest and preserves source checksums and batch identity', async () => {
    const { samples } = await readImportFolder([
      file('dataset-manifest.json', JSON.stringify({ cards: [{ key: 'Astra/Q001', query: '天气', size: '2x2', files: [
        { role: 'dsl', path: 'dsl/a.genui.jsonl', sha256: 'a'.repeat(64) },
        { role: 'image', path: 'images/a.png', sha256: 'b'.repeat(64) },
      ] }] })), file('dsl/a.genui.jsonl', '\ufeff[]\r\n'), file('images/a.png', 'test-png', 'image/png'),
    ]);
    expect(samples[0]).toMatchObject({ id: 'Astra__Q001', query: '天气', dsl: '\ufeff[]\r\n',
      sourceSha256: 'a'.repeat(64), imageSha256: 'b'.repeat(64) });
    expect(samples[0].imageBase64).toBe(btoa('test-png'));
  });

  it('reports bad entries in the failure list while keeping manifest-level errors hard', async () => {
    const row = { id: 'a', query: '天气', size: '2x2', dsl: 'a.jsonl', image: 'a.png' };
    const manifest = (samples: unknown[]) => file(
      'quality-import.json', JSON.stringify({ samples }),
    );
    // 清单声明了截图却没给到文件：只让这一条进失败清单，清单本身的问题才是硬错误。
    const missing = await readImportFolder([manifest([row]), file('a.jsonl', '[]')]);
    expect(missing.samples).toEqual([]);
    expect(missing.failures).toEqual([{ name: 'a', reason: '缺少文件：a.png' }]);
    await expect(readImportFolder([
      manifest([{ ...row, dsl: '../a' }]),
    ])).rejects.toThrow('相对路径');
    await expect(readImportFolder([
      file('quality-import.json', '{}'), file('dataset-manifest.json', '{}'),
    ])).rejects.toThrow('清单只能有一份');
    const badSize = await readImportFolder([
      manifest([{ ...row, size: '4x4', image: undefined }]), file('a.jsonl', '[]'),
    ]);
    expect(badSize.failures[0].reason).toMatch(/2x2 与 2x4/);
    // 清单把 CardSpec 标成 dsl：只让这一条失败，并说清怎么改。
    const mislabeled = await readImportFolder([
      manifest([{ id: 'a', dsl: 'a.jsonl' }]),
      file('a.jsonl', JSON.stringify({ dataBindings: [{ writeResultTo: '/data/x' }] })),
    ]);
    expect(mislabeled.samples).toEqual([]);
    expect(mislabeled.failures[0].reason).toMatch(/其实是 CardSpec/);
  });

  it('imports manifest rows without query, screenshot or id and never drops them', async () => {
    const { samples } = await readImportFolder([
      file('quality-import.json', JSON.stringify({ samples: [
        { dsl: 'dsl/Q001.genui.jsonl' },
        { id: 'Q002', dsl: 'dsl/Q002.genui.jsonl', category: '电量' },
      ] })),
      file('dsl/Q001.genui.jsonl', '["root","Layout",{}]\n'),
      file('dsl/Q002.genui.jsonl', '[]'),
    ]);
    // ID 缺失时按 DSL 文件主干补齐，Query 留空，截图不填也照样成一条用例。
    expect(samples.map((item) => item.id)).toEqual(['Q001', 'Q002']);
    expect(samples[0]).toMatchObject({ query: '', category: undefined });
    expect(samples[0].imageBase64).toBeUndefined();
    expect(samples[1]).toMatchObject({ category: '电量' });
  });

  it('groups a folder without a manifest by file stem and reads cardspec by content', async () => {
    const { samples } = await readImportFolder([
      file('Q001.genui.jsonl', '["root","Layout",{}]\n'),
      file('Q001.png', 'pixels', 'image/png'),
      file('Q002.genui.jsonl', '[]'),
      file('Q002.cardspec.json', JSON.stringify({
        suggestSize: '2x2', dataBindings: [{ writeResultTo: '/data/battery' }],
      })),
    ]);
    expect(samples.map((item) => item.id)).toEqual(['Q001', 'Q002']);
    expect(samples[0]).toMatchObject({ query: '' });
    expect(samples[0].imageBase64).toBe(btoa('pixels'));
    // CardSpec 由内容识别，不靠文件名；主干名相同就归到同一条用例。
    expect(samples[1].cardSpec).toMatchObject({ suggestSize: '2x2' });
    expect(samples[1].dsl).toBe('[]');
    expect(samples[1].imageBase64).toBeUndefined();
  });

  it('imports a whole folder by preferring the render screenshot and skipping helper JSON', async () => {
    const plan = await readImportFolder([
      file('dsl/Q001.jsonl', '["root","Layout",{}]\n'),
      file('renders/Q001.png', 'render', 'image/png'),
      file('screenshots/Q001.png', 'ratio', 'image/png'),
      file('import/payload.json', JSON.stringify({ name: 'x', imageSource: 'web', samples: [] })),
      file('import/render-manifest.json', JSON.stringify([{ id: 'Q001', file: '../dsl/Q001.jsonl' }])),
      file('cards/Q001.md', '# 说明'),
      file('README.md', '# 数据集'),
    ]);
    // 整目录可导：渲染截图优先、辅助 JSON 与说明文档忽略，只留真样本。
    expect(plan.failures).toEqual([]);
    expect(plan.samples.map((item) => item.id)).toEqual(['Q001']);
    expect(plan.samples[0].imageBase64).toBe(btoa('render'));
    expect(plan.notices.map((item) => item.name).sort())
      .toEqual(['Q001', 'payload', 'render-manifest'].sort());
    // 只看路径字典序，不认目录名：renders/Q001.png 排在 screenshots/Q001.png 之前。
    expect(plan.notices.find((item) => item.name === 'Q001')?.detail)
      .toBe('有 2 张同名截图，取 renders/Q001.png，未使用 screenshots/Q001.png');
    expect(plan.notices.find((item) => item.name === 'payload')?.detail)
      .toMatch(/不像 genui DSL/);
  });

  it('names the failing case in the failure list when a folder group has no DSL or has two', async () => {
    const noDsl = await readImportFolder([file('Q001.png', 'pixels', 'image/png')]);
    expect(noDsl.samples).toEqual([]);
    expect(noDsl.failures[0]).toEqual({
      name: 'Q001', reason: '缺少 genui DSL：只有 CardSpec 或截图不能参与对比',
    });
    const twoDsl = await readImportFolder([
      file('Q001.genui.jsonl', '[]'), file('Q001.dsl.jsonl', '[]'),
    ]);
    expect(twoDsl.failures[0]).toMatchObject({ name: 'Q001' });
    expect(twoDsl.failures[0].reason).toMatch(/有多份 DSL/);
    // 同名多张截图只取一张并留提示（截图不进指纹），不再是失败。
    const twoShots = await readImportFolder([
      file('Q001.genui.jsonl', '[]'), file('Q001.png', 'p', 'image/png'),
      file('Q001.jpg', 'q', 'image/jpeg'),
    ]);
    expect(twoShots.failures).toEqual([]);
    expect(twoShots.samples.map((item) => item.id)).toEqual(['Q001']);
    expect(twoShots.notices[0].detail).toBe('有 2 张同名截图，取 Q001.jpg，未使用 Q001.png');
  });

  it('groups multi-selected files by name stem and fills Query from the CardSpec', async () => {
    const plan = await readImportSelection({
      dsl: [file('Q001.genui.jsonl', '["root","Layout",{}]\n'), file('Q002.genui.jsonl', '[]')],
      images: [file('Q001.png', 'pixels', 'image/png')],
      specs: [file('Q001.cardspec.json', JSON.stringify({ userQuery: '西湖天气' }))],
    });
    expect(plan.failures).toEqual([]);
    expect(plan.samples.map((item) => item.id)).toEqual(['Q001', 'Q002']);
    // Query 留空时从 CardSpec 的 userQuery 补，两侧才能按 Query 配对。
    expect(plan.samples[0]).toMatchObject({ query: '西湖天气' });
    expect(plan.samples[0].imageBase64).toBe(btoa('pixels'));
    expect(plan.samples[1]).toMatchObject({ query: '', imageBase64: undefined });
  });

  it('keeps the good samples when a multi-file batch has bad files', async () => {
    const plan = await readImportSelection({
      dsl: [file('Q001.genui.jsonl', '[]'), file('Q002.genui.jsonl', '[]'),
        file('Q003.genui.jsonl', '[]')],
      images: [file('Q002.png', 'p', 'image/png'), file('Q002.jpg', 'q', 'image/jpeg'),
        file('Q009.png', 'p', 'image/png')],
      specs: [],
    });
    // 同名多张截图只取一张并留提示（截图不进指纹），缺 DSL 才是失败。
    expect(plan.samples.map((item) => item.id)).toEqual(['Q001', 'Q002', 'Q003']);
    expect(plan.failures.map((item) => item.name)).toEqual(['Q009']);
    expect(plan.failures[0].reason).toMatch(/没有同名 DSL/);
    expect(plan.notices.map((item) => item.name)).toEqual(['Q002']);
    expect(plan.notices[0].detail).toMatch(/有 2 张同名截图，取 Q002\.jpg/);
    await expect(readImportSelection({ dsl: [], images: [], specs: [] }))
      .rejects.toThrow('至少要有一个 DSL 文件');
  });

  it('derives the pairing stem from the file name, dropping role suffixes', () => {
    expect(sampleStem('dsl/Q001.genui.jsonl')).toBe('Q001');
    expect(sampleStem('Q001.cardspec.json')).toBe('Q001');
    expect(sampleStem('Q001.png')).toBe('Q001');
    expect(classifyContentText('  \uFEFF ')).toBe('empty');
    expect(classifyContentText('{"suggestSize":"2x2","dataBindings":[]}')).toBe('cardspec');
    // 组件树字段出现时按 DSL 处理，即使同一层也有 suggestSize 这类字段名。
    expect(classifyContentText('{"suggestSize":"2x2","component":"Text"}')).toBe('dsl');
    expect(classifyContentText('["root","Layout",{}]\n')).toBe('dsl');
    expect(classifyContentText('not json at all')).toBe('unknown');
    // CardSpec 顶层的 userQuery 就是用户原话；缺失或不是字符串时按空处理。
    expect(cardspecUserQuery({ userQuery: ' 帮我做个天气卡片 ' })).toBe('帮我做个天气卡片');
    expect(cardspecUserQuery({ userQuery: 42 })).toBe('');
    expect(cardspecUserQuery(undefined)).toBe('');
  });

  it('only offers 2x2 and 2x4, defaults to auto judgement and drops the declared size', async () => {
    const fetchMock = mockImport();
    render(<MemoryRouter initialEntries={['/expect/import']}><Routes>
      <Route path="/expect/import" element={<ExpectImportRoute />} />
      <Route path="/expect" element={<p>落地期望对比</p>} />
    </Routes></MemoryRouter>);
    const size = screen.getByLabelText('尺寸');
    // 协议只有 2x2／2x4；缺省时由后端按 DSL＋截图判定，因此默认不提交尺寸。
    expect(within(size).getAllByRole('option').map((node) => node.textContent))
      .toEqual(['自动判定（2x2／2x4）', '2x2', '2x4']);
    expect(size).toHaveValue('');
    fireEvent.change(screen.getByLabelText('数据分类'), { target: { value: '天气' } });
    fireEvent.change(screen.getByLabelText('Query（可选）'), { target: { value: '天气' } });
    await chooseContent(screen.getByLabelText('导入 DSL（可选）'), 'card.jsonl', '[]');
    fireEvent.change(screen.getByLabelText('导入截图'), { target: { files: [file('card.png', 'pixels', 'image/png')] } });
    fireEvent.submit(screen.getByRole('button', { name: '导入并前往期望对比' }).closest('form')!);
    await screen.findByText('落地期望对比');
    const { url, body } = importCall(fetchMock);
    expect(url).toBe('/debug/expect/import');
    expect(body.category).toBe('天气');
    expect(body.samples[0]).not.toHaveProperty('size');
    fireEvent.change(size, { target: { value: '2x4' } });
    expect(size).toHaveValue('2x4');
  });

  it('trims a custom data category before submitting it with the batch', async () => {
    const fetchMock = mockImport();
    render(<MemoryRouter initialEntries={['/expect/import']}><Routes>
      <Route path="/expect/import" element={<ExpectImportRoute />} />
      <Route path="/expect" element={<p>落地期望对比</p>} />
    </Routes></MemoryRouter>);
    fireEvent.change(screen.getByLabelText('数据分类'), { target: { value: '__custom__' } });
    fireEvent.change(screen.getByLabelText('自定义分类'), { target: { value: '  通勤  ' } });
    fireEvent.change(screen.getByLabelText('Query（可选）'), { target: { value: '通勤卡片' } });
    await chooseContent(
      screen.getByLabelText('导入 DSL（可选）'), 'card.jsonl', '[]');
    fireEvent.change(screen.getByLabelText('导入截图'),
      { target: { files: [file('shot.png', 'pixels', 'image/png')] } });
    fireEvent.submit(screen.getByRole('button', { name: '导入并前往期望对比' }).closest('form')!);
    await screen.findByText('落地期望对比');
    expect(importCall(fetchMock).body.category).toBe('通勤');
  });

  it('routes the content file by detected format and fills the requirement tokens', async () => {
    const fetchMock = mockImport();
    render(<MemoryRouter initialEntries={['/expect/import']}><Routes>
      <Route path="/expect/import" element={<ExpectImportRoute />} />
      <Route path="/expect" element={<p>落地期望对比</p>} />
    </Routes></MemoryRouter>);
    useCustomIds();
    await chooseContent(
      screen.getByLabelText('导入 DSL（可选）'), 'card.genui.jsonl', '[]');
    // 识别结果按文件说明格式，并把自动提取到的数据／动作／图标填进需求项。
    expect(await screen.findByText(/card\.genui\.jsonl→genui DSL/)).toBeInTheDocument();
    // 自动识别的 token 必须带候选库中文名，否则一眼看不出对错。
    const preview = within(screen.getByLabelText('自动识别结果'));
    expect(preview.getByText('天气 · 当前 · 天气状况')).toBeInTheDocument();
    expect(preview.getByText('通知铃铛彩色图标')).toBeInTheDocument();
    expect(preview.getByText('跳转链接 · 天气城市页')).toBeInTheDocument();
    // 中文名与原始 token 并排给出：中文看对错，token 看具体值。
    expect(preview.getByText('resources/base/media/bell_fill.svg')).toBeInTheDocument();
    expect(screen.getByLabelText('期望数据')).toHaveValue('');
    fireEvent.change(screen.getByLabelText('导入截图'),
      { target: { files: [file('shot.png', 'pixels', 'image/png')] } });
    fireEvent.submit(screen.getByRole('button', { name: '导入并前往期望对比' }).closest('form')!);
    await screen.findByText('落地期望对比');
    const { body } = importCall(fetchMock);
    expect(body.purpose).toBe('expect');
    expect(body.samples[0]).toMatchObject({
      id: 'Q001', dsl: '[]',
      expectedData: ['/data/weather/current/condition'],
      expectedActions: ['clickToDeeplink:Weather_CityCode'],
      expectedIcons: ['resources/base/media/bell_fill.svg'],
    });
    // 截图是必填项：提交里必须带上它。
    expect(body.samples[0].imageBase64).toBeTruthy();
  });

  it('imports with only an ID and a screenshot, keeping the slots separate', async () => {
    const fetchMock = mockImport();
    render(<MemoryRouter initialEntries={['/expect/import']}><Routes>
      <Route path="/expect/import" element={<ExpectImportRoute />} />
      <Route path="/expect" element={<p>落地期望对比</p>} />
    </Routes></MemoryRouter>);
    useCustomIds();
    const spec = { dataBindings: [{ writeResultTo: '/data/phoneBattery' }] };
    await chooseContent(
      screen.getByLabelText('导入 CardSpec（可选）'),
      'card.cardspec.json', JSON.stringify(spec));
    expect(await screen.findByText(/card\.cardspec\.json→CardSpec/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('样本 ID'), { target: { value: 'Q700' } });
    fireEvent.change(screen.getByLabelText('导入截图'),
      { target: { files: [file('shot.png', 'pixels', 'image/png')] } });
    fireEvent.submit(screen.getByRole('button', { name: '导入并前往期望对比' }).closest('form')!);
    await screen.findByText('落地期望对比');
    // 只有 ID＋截图＋CardSpec 也能导入：DSL 留空是合法输入。
    const { body } = importCall(fetchMock);
    expect(body.samples[0]).toMatchObject({ id: 'Q700', dsl: '' });
    expect(body.samples[0].imageBase64).toBeTruthy();
  });

  it('refuses a submit without a screenshot', async () => {
    const fetchMock = mockImport();
    render(<MemoryRouter initialEntries={['/expect/import']}><Routes>
      <Route path="/expect/import" element={<ExpectImportRoute />} />
    </Routes></MemoryRouter>);
    useCustomIds();
    fireEvent.change(screen.getByLabelText('样本 ID'), { target: { value: 'Q701' } });
    fireEvent.submit(screen.getByRole('button', { name: '导入并前往期望对比' }).closest('form')!);
    expect(await screen.findByText(/请选择截图/)).toBeInTheDocument();
    expect(importCall(fetchMock).submitted).toBe(false);
  });

  it('refuses a CardSpec dropped into the DSL slot and points at the right slot', async () => {
    mockImport();
    render(<MemoryRouter initialEntries={['/expect/import']}><Routes>
      <Route path="/expect/import" element={<ExpectImportRoute />} />
    </Routes></MemoryRouter>);
    // 槽位放错时不会出现识别预览，直接读报错文案。
    fireEvent.change(screen.getByLabelText('导入 DSL（可选）'),
      { target: { files: [file('card.cardspec.json',
        JSON.stringify({ dataBindings: [{ writeResultTo: '/data/phoneBattery' }] }))] } });
    expect(await screen.findByText(/其实是 CardSpec：请放到 CardSpec 槽位/))
      .toBeInTheDocument();
    expect(screen.queryByText(/已识别：/)).toBeNull();
  });

  it('fills Query from the CardSpec userQuery when Query is still empty', async () => {
    const fetchMock = mockImport();
    render(<MemoryRouter initialEntries={['/expect/import']}><Routes>
      <Route path="/expect/import" element={<ExpectImportRoute />} />
      <Route path="/expect" element={<p>落地期望对比</p>} />
    </Routes></MemoryRouter>);
    useCustomIds();
    await chooseContent(screen.getByLabelText('导入 CardSpec（可选）'), 'card.cardspec.json',
      JSON.stringify({ userQuery: '帮我做个南京天气卡',
        dataBindings: [{ writeResultTo: '/data/weather' }] }));
    // CardSpec 带的 userQuery 就是用户原话，Query 空着时直接补上。
    expect(screen.getByLabelText('Query（可选）')).toHaveValue('帮我做个南京天气卡');
    await chooseContent(screen.getByLabelText('导入 DSL（可选）'), 'card.genui.jsonl', '[]');
    fireEvent.change(screen.getByLabelText('导入截图'),
      { target: { files: [file('shot.png', 'pixels', 'image/png')] } });
    fireEvent.submit(screen.getByRole('button', { name: '导入并前往期望对比' }).closest('form')!);
    await screen.findByText('落地期望对比');
    expect(importCall(fetchMock).body.samples[0]).toMatchObject({
      id: 'Q001', query: '帮我做个南京天气卡', dsl: '[]',
      cardSpec: { userQuery: '帮我做个南京天气卡',
        dataBindings: [{ writeResultTo: '/data/weather' }] },
    });
  });

  it('stays on the page and lists the failing files after a multi-file import', async () => {
    const fetchMock = mockImport();
    render(<MemoryRouter initialEntries={['/expect/import']}><Routes>
      <Route path="/expect/import" element={<ExpectImportRoute />} />
      <Route path="/expect" element={<p>落地期望对比</p>} />
    </Routes></MemoryRouter>);
    useCustomIds();
    fireEvent.change(screen.getByLabelText('导入方式'), { target: { value: 'files' } });
    fireEvent.change(screen.getByLabelText('导入 DSL（可多选）'),
      { target: { files: [file('Q001.genui.jsonl', '[]')] } });
    fireEvent.change(screen.getByLabelText('导入截图（可多选）'),
      { target: { files: [file('Q009.png', 'p', 'image/png')] } });
    fireEvent.submit(screen.getByRole('button', { name: '导入并前往期望对比' }).closest('form')!);
    // 有失败文件就留在本页：批次已经导入，失败清单要能当场看到。
    expect(await screen.findByText('失败文件：1 个条目没有导入')).toBeInTheDocument();
    expect(screen.getByText(/Q009：没有同名 DSL 文件/)).toBeInTheDocument();
    expect(screen.queryByText('落地期望对比')).toBeNull();
    expect(importCall(fetchMock).body.samples.map((item: { id: string }) => item.id)).toEqual(['Q001']);
  });

  it('imports real outputs as an actual batch without requirement fields', async () => {
    const fetchMock = mockImport();
    function Landing() {
      const location = useLocation();
      return <p>{`落地 ${location.pathname}`}</p>;
    }
    render(<MemoryRouter initialEntries={['/expect/actual-import']}><Routes>
      <Route path="/expect/actual-import" element={<ExpectImportRoute purpose="actual" />} />
      <Route path="/expect" element={<Landing />} />
    </Routes></MemoryRouter>);
    expect(screen.getByRole('heading', { name: '导入实际输出' })).toBeInTheDocument();
    // 实际侧不声明需求项：期望项一律来自左侧，填了也不生效，所以页面不给输入框。
    expect(screen.queryByLabelText('期望数据')).toBeNull();
    expect(screen.getByRole('link', { name: '导入期望输出' })).toHaveAttribute('href', '/expect/import');
    await chooseContent(
      screen.getByLabelText('导入 DSL（可选）'), 'card.genui.jsonl', '[]');
    fireEvent.change(screen.getByLabelText('导入截图'),
      { target: { files: [file('shot.png', 'pixels', 'image/png')] } });
    fireEvent.submit(screen.getByRole('button', { name: '导入并前往期望对比' }).closest('form')!);
    await screen.findByText('落地 /expect');
    const { body } = importCall(fetchMock);
    expect(body.purpose).toBe('actual');
    expect(body.name).toMatch(/^实际导入 · \d{4}\/\d{2}\/\d{2} \d{2}:\d{2}$/);
    expect(body.samples[0]).not.toHaveProperty('expectedData');
    expect(body.samples[0]).not.toHaveProperty('expectedActions');
    expect(body.samples[0]).not.toHaveProperty('expectedIcons');
    // Query 留空时提交空串：后端只按样本 ID 配对。
    expect(body.samples[0].query).toBe('');
  });

  it('does nothing on entry; importing from quality saves inputs and returns to scoring selection', async () => {
    const fetchMock = mockImport();
    render(<MemoryRouter initialEntries={['/quality/import']}><Routes>
      <Route path="/quality/import" element={<ExpectImportRoute origin="quality" />} />
      <Route path="/quality" element={<p>选择评分样本</p>} />
    </Routes></MemoryRouter>);
    useCustomIds();
    // 进页面只拉候选库，不提交任何导入。
    // 识别接口没有被自动调用：只有用户选了文件才识别。
    expect(fetchMock.mock.calls.every(([url]) => (
      url === '/debug/expect/options'
      || String(url).startsWith('/debug/expect/sample-ids')))).toBe(true);
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'POST')).toBe(false);
    fireEvent.change(screen.getByLabelText('Query（可选）'), { target: { value: '天气' } });
    await chooseContent(
      screen.getByLabelText('导入 DSL（可选）'), 'card.jsonl', '[]');
    fireEvent.change(screen.getByLabelText('导入截图'),
      { target: { files: [file('card.png', 'pixels', 'image/png')] } });
    // jsdom 的 file change 不更新原生 value；真实浏览器上传另做联调。
    fireEvent.submit(screen.getByRole('button', { name: '导入并选择评分样本' }).closest('form')!);
    await screen.findByText('选择评分样本');
    await waitFor(() => expect(fetchMock.mock.calls
      .some(([url]) => url === '/debug/expect/import')).toBe(true));
    const [url, init] = fetchMock.mock.calls
      .find(([item]) => item === '/debug/expect/import')!;
    expect(url).toBe('/debug/expect/import');
    expect(JSON.parse(String(init?.body)).samples[0]).toMatchObject({ id: 'Q001', query: '天气', dsl: '[]' });
  });

  it('imports from the gallery and returns to the gallery after saving', async () => {
    const fetchMock = mockImport();
    function Landing() {
      const location = useLocation();
      return <p>{`落地 ${location.pathname}${location.search}`}</p>;
    }
    render(<MemoryRouter initialEntries={['/expect/gallery/import']}><Routes>
      <Route path="/expect/gallery/import" element={<ExpectImportRoute origin="gallery" />} />
      <Route path="/expect/gallery" element={<Landing />} />
    </Routes></MemoryRouter>);
    expect(screen.getByRole('link', { name: '返回画廊' }))
      .toHaveAttribute('href', '/expect/gallery');
    await chooseContent(
      screen.getByLabelText('导入 DSL（可选）'), 'card.jsonl', '[]');
    fireEvent.change(screen.getByLabelText('导入截图'),
      { target: { files: [file('shot.png', 'pixels', 'image/png')] } });
    fireEvent.submit(screen.getByRole('button', { name: '导入并返回画廊' }).closest('form')!);
    const landed = await screen.findByText(/^落地 /);
    expect(landed.textContent).toBe('落地 /expect/gallery?imported=imported');
    expect(fetchMock.mock.calls.some(([url]) => url === '/debug/expect/import')).toBe(true);
  });

  it('imports from the expect module and hands the new batch to the comparison page', async () => {
    const fetchMock = mockImport();
    function Landing() {
      const location = useLocation();
      return <p>{`落地 ${location.pathname}${location.search}`}</p>;
    }
    render(<MemoryRouter initialEntries={['/expect/import']}><Routes>
      <Route path="/expect/import" element={<ExpectImportRoute />} />
      <Route path="/expect" element={<Landing />} />
    </Routes></MemoryRouter>);
    await chooseContent(
      screen.getByLabelText('导入 DSL（可选）'), 'card.jsonl', '[]');
    fireEvent.change(screen.getByLabelText('导入截图'),
      { target: { files: [file('shot.png', 'pixels', 'image/png')] } });
    fireEvent.submit(screen.getByRole('button', { name: '导入并前往期望对比' }).closest('form')!);
    const landed = await screen.findByText(/^落地 /);
    // 对比页不再按批次筛选，导入完直接过去，新批次自动进期望池。
    expect(landed.textContent).toBe('落地 /expect');
    expect(fetchMock.mock.calls.some(([url]) => url === '/debug/expect/import')).toBe(true);
  });

  it('imports without an ID, letting the backend generate a hash ID', async () => {
    const fetchMock = mockImport();
    render(<MemoryRouter initialEntries={['/expect/import']}><Routes>
      <Route path="/expect/import" element={<ExpectImportRoute />} />
      <Route path="/expect" element={<p>落地期望对比</p>} />
    </Routes></MemoryRouter>);
    // 默认不勾选复选框：页面上没有 ID 输入框，提交里 id 为空，由后端按内容哈希生成。
    expect(screen.queryByLabelText('样本 ID')).toBeNull();
    fireEvent.change(screen.getByLabelText('Query（可选）'), { target: { value: '做个天气卡' } });
    fireEvent.change(screen.getByLabelText('导入截图'),
      { target: { files: [file('shot.png', 'pixels', 'image/png')] } });
    fireEvent.submit(screen.getByRole('button', { name: '导入并前往期望对比' }).closest('form')!);
    await screen.findByText('落地期望对比');
    expect(importCall(fetchMock).body.samples[0].id).toBe('');
  });

  it('names the batch automatically and never asks for it', async () => {
    const fetchMock = mockImport();
    render(<MemoryRouter initialEntries={['/expect/import']}><Routes>
      <Route path="/expect/import" element={<ExpectImportRoute />} />
      <Route path="/expect" element={<p>落地期望对比</p>} />
    </Routes></MemoryRouter>);
    // 页面上没有批次名称输入框：批次名由导入时间生成，只服务画廊分组与整批删除。
    expect(screen.queryByLabelText('批次名称')).toBeNull();
    await chooseContent(
      screen.getByLabelText('导入 DSL（可选）'), 'card.jsonl', '[]');
    fireEvent.change(screen.getByLabelText('导入截图'),
      { target: { files: [file('shot.png', 'pixels', 'image/png')] } });
    fireEvent.submit(screen.getByRole('button', { name: '导入并前往期望对比' }).closest('form')!);
    await waitFor(() => expect(importCall(fetchMock).url).toBe('/debug/expect/import'));
    expect(importCall(fetchMock).body.name)
      .toMatch(/^期望导入 · \d{4}\/\d{2}\/\d{2} \d{2}:\d{2}$/);
  });

  it('edits one expectation in place: prefills the sample and saves with PUT', async () => {
    const sample = {
      runId: 'batch_import_a', runName: '期望导入 · 2026/10/18', sampleId: 'Q001',
      title: 'Q001', query: '原来的说法', size: '2x2', sizeSource: 'declared',
      category: '天气', attempt: 'input',
      genui: '["root","Layout",{"layout":"S-center"},["display"]]',
      imageUrl: '/debug/expect/runs/batch_import_a/samples/Q001/input-image',
      explicit: {
        data: ['/data/weather/current/condition'],
        actions: ['clickToDeeplink:Weather_CityCode'],
        icons: ['resources/base/media/bell_fill.svg'],
      },
      fingerprint: { data: [], actions: [], icons: [] },
    };
    const fetchMock = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = String(input);
      if (url.startsWith('/debug/expect/sample-ids')) {
        return { ok: true, json: async () => ({ items: [] }) } as Response;
      }
      if (url === '/debug/expect/options') {
        return { ok: true, json: async () => ({ data: [], actions: [], icons: [] }) } as Response;
      }
      if (url === '/debug/expect/runs/batch_import_a/samples/Q001') {
        return { ok: true, json: async () => (init?.method === 'PUT' ? sample : sample) } as Response;
      }
      throw new Error(`unexpected request: ${url}`);
    });
    render(<MemoryRouter initialEntries={['/expect/import?runId=batch_import_a&sampleId=Q001']}>
      <Routes>
        <Route path="/expect/import" element={<ExpectImportRoute />} />
        <Route path="/expect/gallery" element={<p>落地画廊</p>} />
      </Routes></MemoryRouter>);

    // 回填：Query、尺寸、分类、三类期望项都来自这条样本，ID 只读。
    await waitFor(() => expect(screen.getByLabelText('Query（可选）')).toHaveValue('原来的说法'));
    expect(screen.getByLabelText('样本 ID')).toHaveValue('Q001');
    expect(screen.getByLabelText('样本 ID')).toHaveAttribute('readonly');
    expect(screen.getByLabelText('尺寸')).toHaveValue('2x2');
    expect(screen.getByLabelText('数据分类')).toHaveValue('天气');
    expect(screen.getByText('/data/weather/current/condition')).toBeInTheDocument();
    expect(screen.getByText('clickToDeeplink:Weather_CityCode')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '查看' }))
      .toHaveAttribute('href', '/debug/expect/runs/batch_import_a/samples/Q001/input-image');
    // 编辑模式截图可留空：提示写明留空即保留原截图。
    expect(screen.getByText('导入截图（留空保留原截图）')).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('Query（可选）'), { target: { value: '改后的说法' } });
    fireEvent.submit(screen.getByRole('button', { name: '导入并前往期望对比' }).closest('form')!);
    await screen.findByText('落地画廊');

    const put = fetchMock.mock.calls.find(([, init]) => init?.method === 'PUT');
    expect(String(put?.[0])).toBe('/debug/expect/runs/batch_import_a/samples/Q001');
    const body = JSON.parse(String(put?.[1]?.body));
    expect(body.query).toBe('改后的说法');
    expect(body.expectedData).toEqual(['/data/weather/current/condition']);
    // 没重新上传截图时不带 imageBase64：后端按保留处理，改文字不会丢截图。
    expect(body).not.toHaveProperty('imageBase64');
    expect(body).not.toHaveProperty('id');
    // 编辑不新建批次：不该出现导入调用。
    expect(fetchMock.mock.calls.some(([url]) => String(url) === '/debug/expect/import')).toBe(false);
  });

  it('keeps only the expect-module jumps and leaves 质量评分 to the left sidebar',
    async () => {
      render(<MemoryRouter initialEntries={['/expect/import']}><Routes>
        <Route path="/expect/import" element={<ExpectImportRoute />} />
      </Routes></MemoryRouter>);
      const nav = screen.getByRole('navigation', { name: '期望对比工具' });
      expect(within(nav).getByRole('link', { name: '期望对比' })).toHaveAttribute('href', '/expect');
      expect(within(nav).getByRole('link', { name: '导入实际输出' }))
        .toHaveAttribute('href', '/expect/actual-import');
      expect(within(nav).getByRole('link', { name: '期望数据画廊' }))
        .toHaveAttribute('href', '/expect/gallery');
      expect(within(nav).queryByRole('link', { name: /质量评分|返回评分/ })).toBeNull();
      expect(within(nav).queryByRole('link', { name: '返回画廊' })).toBeNull();
    });

  it('refuses a dropped folder instead of reading it as a sample', async () => {
    const fetchMock = mockImport();
    render(<MemoryRouter initialEntries={['/expect/import']}><Routes>
      <Route path="/expect/import" element={<ExpectImportRoute />} />
      <Route path="/expect" element={<p>落地期望对比</p>} />
    </Routes></MemoryRouter>);
    useCustomIds();
    fireEvent.change(screen.getByLabelText('导入方式'), { target: { value: 'files' } });
    fireEvent.change(screen.getByLabelText('导入 DSL（可多选）'),
      { target: { files: [folder('dsl'), folder('screenshots')] } });
    fireEvent.submit(screen.getByRole('button', { name: '导入并前往期望对比' }).closest('form')!);
    // 文件夹不是样本：说清怎么改，而不是拿系统级报错或「没有同名 DSL」糊过去。
    expect(await screen.findByText(/没有可用的 DSL 文件/)).toBeInTheDocument();
    expect(importCall(fetchMock).submitted).toBe(false);

    const mixed = mockImport();
    fireEvent.change(screen.getByLabelText('导入 DSL（可多选）'),
      { target: { files: [file('Q001.genui.jsonl', '[]')] } });
    fireEvent.change(screen.getByLabelText('导入截图（可多选）'),
      { target: { files: [folder('screenshots')] } });
    fireEvent.submit(screen.getByRole('button', { name: '导入并前往期望对比' }).closest('form')!);
    // 坏条目只进失败清单，好文件照常导入，而且原因写的是文件夹。
    expect(await screen.findByText(/失败文件：1 个条目没有导入/)).toBeInTheDocument();
    expect(screen.getByText(/「screenshots」是文件夹而不是文件/)).toBeInTheDocument();
    expect(importCall(mixed).body.samples.map((item: { id: string }) => item.id))
      .toEqual(['Q001']);
  });

  it('turns an unreadable file into a readable reason', async () => {
    mockImport();
    render(<MemoryRouter initialEntries={['/expect/import']}><Routes>
      <Route path="/expect/import" element={<ExpectImportRoute />} />
    </Routes></MemoryRouter>);
    const broken = new File(['[]'], 'Q001.genui.jsonl', { type: 'application/json' });
    Object.defineProperties(broken, {
      arrayBuffer: { value: async () => { throw new Error('A requested file or directory could not be found'); } },
    });
    fireEvent.change(screen.getByLabelText('导入 DSL（可选）'), { target: { files: [broken] } });
    // 读不出来时把原始报错包进上下文，而不是让它裸露给用户。
    expect(await screen.findByText(/无法读取「Q001\.genui\.jsonl」/)).toBeInTheDocument();
  });

  it('warns about an existing sample with the same ID before importing', async () => {
    const fetchMock = mockImport([{ id: 'Q001' }]);
    render(<MemoryRouter initialEntries={['/expect/import']}><Routes>
      <Route path="/expect/import" element={<ExpectImportRoute />} />
      <Route path="/expect" element={<p>落地期望对比</p>} />
    </Routes></MemoryRouter>);
    useCustomIds();
    // 该侧已有同 ID 样本：提示两种处理方式，但不阻断「用同 ID 重新导入修正」这条路。
    expect(await screen.findByText(/该侧已有同 ID 样本/)).toBeInTheDocument();
    expect(screen.getByText(/同名按最新批次生效/)).toBeInTheDocument();
    expect(screen.getByText(/要让两条并存请更换 ID/)).toBeInTheDocument();

    await chooseContent(screen.getByLabelText('导入 DSL（可选）'), 'card.genui.jsonl', '[]');
    fireEvent.change(screen.getByLabelText('样本 ID'), { target: { value: 'Q900' } });
    expect(screen.queryByText(/该侧已有同 ID 样本/)).toBeNull();
    fireEvent.change(screen.getByLabelText('导入截图'),
      { target: { files: [file('shot.png', 'pixels', 'image/png')] } });
    fireEvent.submit(screen.getByRole('button', { name: '导入并前往期望对比' }).closest('form')!);
    await screen.findByText('落地期望对比');
    expect(importCall(fetchMock).body.samples[0].id).toBe('Q900');
  });

  it('lists same-name samples and stays on the page after a multi-file import', async () => {
    const fetchMock = mockImport([{ id: 'Q001' }]);
    render(<MemoryRouter initialEntries={['/expect/import']}><Routes>
      <Route path="/expect/import" element={<ExpectImportRoute />} />
      <Route path="/expect" element={<p>落地期望对比</p>} />
    </Routes></MemoryRouter>);
    useCustomIds();
    // 单条模式先等「已有样本 ID」索引到位，再切到批量，避免时序抖动。
    expect(await screen.findByText(/该侧已有同 ID 样本/)).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText('导入方式'), { target: { value: 'files' } });
    fireEvent.change(screen.getByLabelText('导入 DSL（可多选）'),
      { target: { files: [file('Q001.genui.jsonl', '[]')] } });
    fireEvent.change(screen.getByLabelText('导入截图（可多选）'),
      { target: { files: [file('shot.png', 'pixels', 'image/png')] } });
    fireEvent.submit(screen.getByRole('button', { name: '导入并前往期望对比' }).closest('form')!);
    // 同名会盖住旧样本：留在本页把同名清单摆出来，让用户决定换 ID 还是覆盖。
    expect(await screen.findByText(/其中 1 个样本 ID 与该侧已有样本同名：Q001/)).toBeInTheDocument();
    expect(screen.queryByText('落地期望对比')).toBeNull();
    expect(importCall(fetchMock).body.samples.map((item: { id: string }) => item.id))
      .toEqual(['Q001']);
  });
});
