import { describe, expect, it } from 'vitest';
import { buildToolSocketUrl } from '../src/transport';

describe('buildToolSocketUrl', () => {
  it('appends an operation to a BFF path', () => {
    expect(buildToolSocketUrl('/debug/tools', 'getDataCapabilitySchemas'))
      .toBe('ws://127.0.0.1:8888/debug/tools/getDataCapabilitySchemas');
  });

  it('supports a full ws URL and an operation template', () => {
    expect(buildToolSocketUrl('wss://localhost:8888/debug/tools/{operation}', 'generateWidgetCardCompactDsl'))
      .toBe('wss://localhost:8888/debug/tools/generateWidgetCardCompactDsl');
  });

  it('does not append an operation twice', () => {
    expect(buildToolSocketUrl('ws://localhost:8855/api/v1/ws/tools/getWidgetCapabilityOverview', 'getWidgetCapabilityOverview'))
      .toBe('ws://localhost:8855/api/v1/ws/tools/getWidgetCapabilityOverview');
  });

  it('converts http and normalizes an expanded operation with a trailing slash', () => {
    expect(buildToolSocketUrl('https://localhost:8855/api/v1/ws/tools/getDataCapabilitySchemas/', 'getDataCapabilitySchemas'))
      .toBe('wss://localhost:8855/api/v1/ws/tools/getDataCapabilitySchemas');
  });

  it('supports an operation template in the query string', () => {
    expect(buildToolSocketUrl('ws://localhost:8855/tools?operation={operation}', 'generateWidgetCardCompactDsl'))
      .toBe('ws://localhost:8855/tools?operation=generateWidgetCardCompactDsl');
  });

  it('rejects explicit empty addresses and URL fragments', () => {
    expect(() => buildToolSocketUrl('', 'getDataCapabilitySchemas')).toThrow('不能为空');
    expect(() => buildToolSocketUrl('ws://localhost:8855/tools#fragment', 'getDataCapabilitySchemas'))
      .toThrow('hash');
  });
});
