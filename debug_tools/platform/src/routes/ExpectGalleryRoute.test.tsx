import {
  cleanup, fireEvent, render, screen, waitFor, within,
} from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { MemoryRouter } from 'react-router-dom';
import { ExpectGalleryRoute } from './ExpectGalleryRoute';
import type { ExpectGallery } from '../batchApi';

const DSL = JSON.stringify({ version: 'v0.9', createSurface: { surfaceId: 's', catalogId: 'c' } })
  + '\n' + JSON.stringify({ version: 'v0.9', updateComponents: { surfaceId: 's', root: 'root',
    components: [{ id: 'root', component: 'Text', content: '天气' }] } });

const gallery: ExpectGallery = {
  items: [{
    runId: 'batch_import_weather', runName: '天气批次', sampleId: 'Q001',
    title: '天气样本', query: '做个天气卡片', size: '2x2', sizeSource: 'derived',
    category: '天气', attempt: 'input', genui: DSL,
    imageUrl: '/debug/expect/runs/batch_import_weather/samples/Q001/input-image',
    fingerprint: {
      data: ['/data/weather/current/condition'],
      actions: ['clickToDeeplink:Weather'],
      icons: [],
    },
    labels: {
      data: { '/data/weather/current/condition': '天气状况' },
      actions: { 'clickToDeeplink:Weather': '跳转链接 · 天气' },
      icons: {},
    },
  }, {
    runId: 'batch_import_weather', runName: '天气批次', sampleId: 'Q002',
    title: '电量样本', query: '显示电量', size: '2x2', sizeSource: 'declared',
    category: '电量', attempt: 'input', genui: DSL,
    fingerprint: {
      data: ['/data/battery/level'], actions: [], icons: ['battery_level.svg'],
    },
    labels: { data: { '/data/battery/level': '电量等级' }, icons: { 'battery_level.svg': '电量图标' } },
  }, {
    runId: 'batch_import_schedule', runName: '日程批次', sampleId: 'Q003',
    title: '日程样本', query: '今天日程', size: '2x4', sizeSource: 'derived',
    category: '日程', attempt: 'input', genui: DSL,
    fingerprint: {
      data: ['/data/calendar/events'],
      actions: ['clickToIntent:Calendar'],
      icons: ['calendar_today.svg'],
    },
    labels: { actions: { 'clickToIntent:Calendar': '打开页面 · 日程' } },
  }],
  categories: ['天气', '电量', '日程'],
  batches: [
    { runId: 'batch_import_weather', name: '天气批次', category: '天气',
      sampleCount: 2, startedAt: '2026-10-18T08:00:00.000Z' },
    { runId: 'batch_import_schedule', name: '日程批次', category: '',
      sampleCount: 1, startedAt: '2026-10-17T08:00:00.000Z' },
  ],
  total: 3,
  warnings: [],
};

function response(body: unknown, status = 200): Response {
  return { ok: status < 400, status, json: async () => body } as Response;
}

function mockApi() {
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input);
    if (url === '/debug/expect/samples') return response(gallery);
    if (url.startsWith('/debug/expect/runs/') && init?.method === 'PUT') {
      const body = JSON.parse(String(init?.body ?? '{}'));
      return response(url.endsWith('/category')
        ? { runId: 'batch_import_weather', category: body.category ?? '', sampleCount: 2 }
        : { runId: 'batch_import_weather', sampleId: 'Q001', category: body.category ?? '' });
    }
    if (url.startsWith('/debug/expect/runs/') && init?.method === 'DELETE') {
      return response({ deleted: url.includes('/samples/') ? 'sample' : 'run',
        runId: 'batch_import_weather' });
    }
    throw new Error(`unexpected request: ${url}`);
  });
}

function renderRoute() {
  return render(<MemoryRouter><ExpectGalleryRoute /></MemoryRouter>);
}

describe('ExpectGalleryRoute', () => {

  it('links each sample to the in-place edit page', async () => {
    mockApi();
    render(<MemoryRouter initialEntries={['/expect/gallery']}><ExpectGalleryRoute /></MemoryRouter>);
    const cards = await screen.findAllByRole('link', { name: '编辑' });
    // 就地编辑：带上批次与样本 ID，保存后不会出现同 ID 的第二条。
    expect(cards[0]).toHaveAttribute(
      'href', '/expect/import?runId=batch_import_weather&sampleId=Q001');
  });
  afterEach(() => {
    cleanup();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  it('lists imported samples grouped by batch with labels and an import entry', async () => {
    const fetchMock = mockApi();
    renderRoute();
    expect(await screen.findByRole('heading', { name: '期望数据画廊' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: '导入添加' }))
      .toHaveAttribute('href', '/expect/gallery/import');
    expect(await screen.findByRole('heading', { name: '天气批次' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: '日程批次' })).toBeInTheDocument();
    expect(screen.getByText('天气状况')).toBeInTheDocument();
    expect(screen.getByText('跳转链接 · 天气')).toBeInTheDocument();
    expect(screen.getByText('电量等级')).toBeInTheDocument();
    expect(screen.getByText('3/3 条')).toBeInTheDocument();
    expect(fetchMock.mock.calls.map(([url]) => String(url)))
      .toContain('/debug/expect/samples');
  });

  it('changes one image category from its card, only sending the category', async () => {
    const fetchMock = mockApi();
    renderRoute();
    const select = await screen.findByLabelText('图片分类 Q001');
    fireEvent.change(select, { target: { value: '电量' } });
    await waitFor(() => expect(fetchMock.mock.calls
      .some(([, init]) => init?.method === 'PUT')).toBe(true));
    const put = fetchMock.mock.calls.find(([, init]) => init?.method === 'PUT')!;
    expect(String(put[0])).toBe('/debug/expect/runs/batch_import_weather/samples/Q001');
    // 局部更新：只发分类，Query／DSL／期望项与截图都不动。
    expect(JSON.parse(String(put[1]?.body))).toEqual({ category: '电量' });
  });

  it('creates a custom category from a card', async () => {
    const fetchMock = mockApi();
    const prompt = vi.spyOn(window, 'prompt').mockReturnValue('  通勤  ');
    renderRoute();
    const select = await screen.findByLabelText('图片分类 Q001');
    fireEvent.change(select, { target: { value: '__new__' } });
    await waitFor(() => expect(fetchMock.mock.calls
      .some(([, init]) => init?.method === 'PUT')).toBe(true));
    const put = fetchMock.mock.calls.find(([, init]) => init?.method === 'PUT')!;
    expect(JSON.parse(String(put[1]?.body))).toEqual({ category: '通勤' });
    prompt.mockRestore();
  });

  it('changes the whole batch category at once, custom names included', async () => {
    const fetchMock = mockApi();
    const prompt = vi.spyOn(window, 'prompt').mockReturnValue('自定分类');
    renderRoute();
    const select = await screen.findByLabelText('整批分类 batch_import_weather');
    fireEvent.change(select, { target: { value: '__new__' } });
    await waitFor(() => expect(fetchMock.mock.calls
      .some(([url]) => String(url).endsWith('/category'))).toBe(true));
    const put = fetchMock.mock.calls.find(([url]) => String(url).endsWith('/category'))!;
    expect(String(put[0])).toBe('/debug/expect/runs/batch_import_weather/category');
    expect(JSON.parse(String(put[1]?.body))).toEqual({ category: '自定分类' });
    prompt.mockRestore();
  });

  it('filters locally by category, data, action and icon without refetching', async () => {
    const fetchMock = mockApi();
    renderRoute();
    await screen.findByRole('heading', { name: '天气批次' });

    fireEvent.change(screen.getByLabelText('数据分类'), { target: { value: '电量' } });
    expect(screen.getByText('电量样本')).toBeInTheDocument();
    expect(screen.queryByText('天气样本')).toBeNull();
    expect(screen.getByText('1/3 条')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '清空筛选' }));

    fireEvent.change(screen.getByLabelText('数据'), { target: { value: '电量 等级' } });
    expect(screen.getByText('电量样本')).toBeInTheDocument();
    expect(screen.queryByText('天气样本')).toBeNull();
    expect(screen.queryByText('日程样本')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '清空筛选' }));

    fireEvent.change(screen.getByLabelText('动作'), { target: { value: '跳转链接' } });
    expect(screen.getByText('天气样本')).toBeInTheDocument();
    expect(screen.queryByText('电量样本')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: '清空筛选' }));

    fireEvent.change(screen.getByLabelText('图标'), { target: { value: 'battery' } });
    expect(screen.getByText('电量样本')).toBeInTheDocument();
    expect(screen.queryByText('天气样本')).toBeNull();
    expect(fetchMock.mock.calls.filter(([url]) =>
      String(url) === '/debug/expect/samples')).toHaveLength(1);
  });

  it('deletes a single sample after confirmation and reloads the gallery', async () => {
    const fetchMock = mockApi();
    const confirm = vi.fn(() => true);
    vi.stubGlobal('confirm', confirm);
    renderRoute();
    await screen.findByText('天气样本');
    const card = screen.getByText('天气样本').closest('.expect-gallery-card') as HTMLElement;
    fireEvent.click(within(card).getByRole('button', { name: '删除样本' }));
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining('Q001'));
    expect(fetchMock.mock.calls.some(([url, init]) =>
      String(url) === '/debug/expect/runs/batch_import_weather/samples/Q001'
      && init?.method === 'DELETE')).toBe(true);
    await waitFor(() => {
      expect(fetchMock.mock.calls.filter(([url]) =>
        String(url) === '/debug/expect/samples')).toHaveLength(2);
    });
  });

  it('deletes a whole batch after confirmation', async () => {
    const fetchMock = mockApi();
    const confirm = vi.fn(() => true);
    vi.stubGlobal('confirm', confirm);
    renderRoute();
    await screen.findByRole('heading', { name: '日程批次' });
    const batch = screen.getByRole('heading', { name: '日程批次' })
      .closest('.expect-gallery-batch') as HTMLElement;
    fireEvent.click(within(batch).getByRole('button', { name: '删除批次' }));
    expect(confirm).toHaveBeenCalledWith(expect.stringContaining('日程批次'));
    expect(fetchMock.mock.calls.some(([url, init]) =>
      String(url) === '/debug/expect/runs/batch_import_schedule'
      && init?.method === 'DELETE')).toBe(true);
  });

  it('shows the raw DSL on demand and keeps the upload screenshot by default', async () => {
    mockApi();
    renderRoute();
    const card = await screen.findByText('天气样本');
    const container = card.closest('.expect-gallery-card') as HTMLElement;
    expect(within(container).getByRole('img', { name: 'Q001 上传截图' }))
      .toHaveAttribute('src',
        '/debug/expect/runs/batch_import_weather/samples/Q001/input-image');
    fireEvent.click(within(container).getByRole('button', { name: '查看 DSL' }));
    expect(within(container).getByText(/"createSurface"/)).toBeInTheDocument();
    fireEvent.click(within(container).getByRole('button', { name: '收起 DSL' }));
    expect(within(container).queryByText(/"createSurface"/)).toBeNull();
  });

  it('shows an empty state with an import link when nothing was imported', async () => {
    vi.spyOn(globalThis, 'fetch').mockResolvedValue(response({
      ...gallery, items: [], total: 0, batches: [], categories: [],
    }));
    renderRoute();
    expect(await screen.findByText(/还没有导入的期望数据/)).toBeInTheDocument();
    expect(screen.getAllByRole('link', { name: '导入添加' })
      .every((link) => link.getAttribute('href') === '/expect/gallery/import')).toBe(true);
  });

  it('surfaces delete failures as alerts', async () => {
    vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
      const url = String(input);
      if (url === '/debug/expect/samples') return response(gallery);
      if (init?.method === 'DELETE') return response({ detail: '删除失败，文件可能被占用' }, 409);
      throw new Error(`unexpected request: ${url}`);
    });
    vi.stubGlobal('confirm', () => true);
    renderRoute();
    await screen.findByText('天气样本');
    const card = screen.getByText('天气样本').closest('.expect-gallery-card') as HTMLElement;
    fireEvent.click(within(card).getByRole('button', { name: '删除样本' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('删除失败');
  });
});
