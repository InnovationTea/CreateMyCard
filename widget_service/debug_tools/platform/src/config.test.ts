import { describe, expect, it } from 'vitest';
import { defaultDebugConfig, normalizeDebugConfig, selectedToolWsBaseUrl } from './config';

describe('microservice connection selection', () => {
  it('defaults to the deployed service', () => {
    const config = normalizeDebugConfig({});
    expect(config.microserviceMode).toBe('deployed');
    expect(selectedToolWsBaseUrl(config)).toBe(defaultDebugConfig.toolWsBaseUrl);
  });

  it('uses the managed endpoint when managed mode is selected', () => {
    const config = normalizeDebugConfig({
      microserviceMode: 'managed',
      managedServiceWsUrl: 'ws://127.0.0.1:9000/api/v1/ws/tools',
    });
    expect(selectedToolWsBaseUrl(config)).toBe('ws://127.0.0.1:9000/api/v1/ws/tools');
  });
});
