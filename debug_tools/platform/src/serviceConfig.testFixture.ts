import type { ServiceConfigDefaults } from './batchApi';

export function configurationFixture(): ServiceConfigDefaults {
  const values: Record<string, unknown> = {
    openai_master_client: 'llmclient',
    enable_model_failure_retry: false,
    model_max_concurrency: 20,
    asset_src_url_mapping: {},
    server_port: 8855,
    unknown_legacy: null,
  };
  const names = [...Object.keys(values), 'deepseek_api_key'];
  const exposedKeys = ['openai_master_client', 'enable_model_failure_retry'];
  const types: Record<string, string> = {
    enable_model_failure_retry: 'bool', model_max_concurrency: 'int',
    asset_src_url_mapping: 'dict', server_port: 'int', unknown_legacy: 'unknown',
  };
  return {
    version: 'version-one', values, exposedKeys,
    sources: Object.fromEntries(names.map((name) => [name, '.env'])),
    fields: names.map((name) => ({
      name, displayName: name.toUpperCase(), type: types[name] ?? 'str', source: '.env',
      group: exposedKeys.includes(name) ? 'exposed' : 'defaults',
      sensitive: name === 'deepseek_api_key',
      editable: !['deepseek_api_key', 'server_port', 'unknown_legacy'].includes(name),
      readOnlyReason: '由服务端管理',
    })),
  };
}
