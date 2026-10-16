import { cleanup, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { WorkbenchProvider } from '../context';
import { configurationFixture } from '../serviceConfig.testFixture';
import { DEBUG_CONFIG_STORAGE_KEY } from '../config';
import { SettingsPanel } from './SettingsPanel';

function mockApi(fail = false, localConfigExists = true) {
  const fixture = configurationFixture();
  fixture.localConfigExists = localConfigExists;
  return vi.spyOn(globalThis, 'fetch').mockImplementation(async (input, init) => {
    const url = String(input);
    let body: unknown = { checks: [], status: [] };
    let status = 200;
    if (url.endsWith('/connections/status')) body = { mainAgent: { available: true, detail: 'ok' }, deployedService: { available: true, detail: 'ok' }, managedService: { available: false, detail: '未启动' } };
    if (url.endsWith('/service-config/defaults')) {
      if (init?.method === 'PATCH') {
        if (fail) { body = { detail: '配置文件已变化，请重新加载后再保存' }; status = 409; }
        else {
          const changes = JSON.parse(String(init.body)).changes;
          Object.assign(fixture.values, changes);
          fixture.fields.forEach((field) => { if (field.name in changes) field.source = 'debug_tool.yaml'; });
          fixture.version = 'version-two';
          body = fixture;
        }
      } else body = fixture;
    }
    return { ok: status === 200, status, json: async () => body } as Response;
  });
}

async function openManaged() {
  render(<WorkbenchProvider><SettingsPanel /></WorkbenchProvider>);
  await userEvent.click(screen.getByRole('radio', { name: '使用本地受管微服务' }));
  await screen.findByLabelText('MODEL_MAX_CONCURRENCY');
  await waitFor(() => expect(screen.getByRole('button', { name: '保存配置' })).not.toBeDisabled());
}

describe('SettingsPanel', () => {
  afterEach(() => { cleanup(); localStorage.clear(); vi.restoreAllMocks(); });

  it('places all status widgets together in order and refreshes every ten seconds', async () => {
    mockApi();
    const intervalSpy = vi.spyOn(window, 'setInterval');
    render(<WorkbenchProvider><SettingsPanel /></WorkbenchProvider>);
    const backend = screen.getByLabelText('后端服务状态');
    const toolchain = screen.getByLabelText('本机工具链状态');
    const device = screen.getByLabelText('设备环境状态');
    expect(backend.nextElementSibling).toBe(toolchain);
    expect(toolchain.nextElementSibling).toBe(device);
    for (const widget of [backend, toolchain, device]) {
      expect(widget).toHaveClass('backend-status-widget', 'settings-toolchain-status');
    }
    await waitFor(() => expect(screen.getAllByText('每 10 秒自动检查')).toHaveLength(3));
    expect(intervalSpy.mock.calls.filter(([, delay]) => delay === 10_000)).toHaveLength(2);
  });

  it('hides setup instructions when the local config exists', async () => {
    mockApi();
    await openManaged();
    expect(screen.queryByRole('region', { name: '首次使用配置说明' })).not.toBeInTheDocument();
  });

  it('shows setup instructions only after confirming the local config is missing', async () => {
    mockApi(false, false);
    render(<WorkbenchProvider><SettingsPanel /></WorkbenchProvider>);
    expect(screen.queryByRole('region', { name: '首次使用配置说明' })).not.toBeInTheDocument();
    expect(await screen.findByRole('region', { name: '首次使用配置说明' })).toBeInTheDocument();
    expect(screen.getByRole('alert')).toHaveTextContent('未找到本机 debug_tool.yaml，平台已使用默认配置启动');
    mockApi(false, true);
    await userEvent.click(screen.getByRole('button', { name: '重新加载已保存配置' }));
    await waitFor(() => expect(screen.queryByRole('region', { name: '首次使用配置说明' })).not.toBeInTheDocument());
  });

  it('groups all fields dynamically, shows sources and keeps sensitive fields read-only', async () => {
    mockApi();
    await openManaged();
    expect(screen.getByText('批跑可临时调整的默认参数')).toBeInTheDocument();
    expect(screen.getByText('其余受管微服务默认参数')).toBeInTheDocument();
    expect(screen.getByText('MODEL_MAX_CONCURRENCY').closest('section')).not.toBe(screen.getByText('OPENAI_MASTER_CLIENT').closest('section'));
    expect(screen.getByText('DEEPSEEK_API_KEY')).toBeInTheDocument();
    expect(screen.queryByLabelText('DEEPSEEK_API_KEY')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('SERVER_PORT')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('UNKNOWN_LEGACY')).not.toBeInTheDocument();
    expect(screen.getAllByText('.env')).toHaveLength(7);
  });

  it('saves only changed values to server and refreshes their sources', async () => {
    const fetchMock = mockApi();
    localStorage.setItem(DEBUG_CONFIG_STORAGE_KEY, JSON.stringify({ config: { managedServiceConfig: { model_max_concurrency: 99 } } }));
    await openManaged();
    const input = screen.getByLabelText('MODEL_MAX_CONCURRENCY');
    expect(input).toHaveValue(20);
    await userEvent.clear(input);
    await userEvent.type(input, '25');
    await userEvent.click(screen.getByRole('button', { name: '保存配置' }));
    await screen.findByRole('status');
    const patch = fetchMock.mock.calls.find(([, init]) => init?.method === 'PATCH');
    expect(JSON.parse(String(patch?.[1]?.body))).toEqual({ version: 'version-one', changes: { model_max_concurrency: 25 } });
    expect(screen.getByText('debug_tool.yaml')).toBeInTheDocument();
    const stored = JSON.parse(localStorage.getItem(DEBUG_CONFIG_STORAGE_KEY) ?? '{}');
    expect(stored.config.managedServiceConfig).toEqual({});
  });

  it('retains edits and reports a failed save without success notice', async () => {
    mockApi(true);
    await openManaged();
    await userEvent.click(screen.getByLabelText('ENABLE_MODEL_FAILURE_RETRY'));
    await userEvent.click(screen.getByRole('button', { name: '保存配置' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('配置文件已变化');
    expect(screen.getByLabelText('ENABLE_MODEL_FAILURE_RETRY')).toBeChecked();
    expect(screen.queryByRole('status')).not.toBeInTheDocument();
  });

  it('validates JSON and reloads saved configuration without writing files', async () => {
    const fetchMock = mockApi();
    await openManaged();
    const input = screen.getByLabelText('ASSET_SRC_URL_MAPPING');
    await userEvent.clear(input);
    expect(screen.getByRole('button', { name: '保存配置' })).toBeDisabled();
    await userEvent.click(screen.getByRole('button', { name: '重新加载已保存配置' }));
    await userEvent.click(screen.getByRole('radio', { name: '使用本地受管微服务' }));
    await waitFor(() => expect(screen.getByLabelText('ASSET_SRC_URL_MAPPING')).toHaveValue('{}'));
    expect(fetchMock.mock.calls.some(([, init]) => init?.method === 'PATCH')).toBe(false);
    await userEvent.clear(screen.getByLabelText('ASSET_SRC_URL_MAPPING'));
    await userEvent.paste('{"icon":"local"}');
    await userEvent.click(screen.getByRole('button', { name: '保存配置' }));
    await screen.findByRole('status');
    const patch = fetchMock.mock.calls.find(([, init]) => init?.method === 'PATCH');
    expect(JSON.parse(String(patch?.[1]?.body)).changes).toEqual({ asset_src_url_mapping: { icon: 'local' } });
  });
});
