import { createHash, webcrypto } from 'node:crypto';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { getBatchTraceArtifact } from './batchApi';

describe('Trace artifact integrity', () => {
  afterEach(() => { vi.restoreAllMocks(); vi.unstubAllGlobals(); });
  it.each(['中文正文', '', '{broken json'])('validates full bytes and digest of %s', async (text) => {
    vi.stubGlobal('crypto', webcrypto);
    const bytes = new TextEncoder().encode(text);
    const digest = createHash('sha256').update(bytes).digest('hex');
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({
      ok: true, arrayBuffer: async () => bytes.buffer, headers: new Headers({ 'content-type': 'text/plain' }),
    } as Response);
    expect((await getBatchTraceArtifact('run', digest, bytes.byteLength)).content).toBe(text);
  });
  it.each(['size', 'digest'])('rejects a %s mismatch', async (failure) => {
    vi.stubGlobal('crypto', webcrypto);
    const bytes = new TextEncoder().encode('content');
    vi.spyOn(globalThis, 'fetch').mockResolvedValue({ ok: true, arrayBuffer: async () => bytes.buffer } as Response);
    await expect(getBatchTraceArtifact('run', 'a'.repeat(64), failure === 'size' ? 1 : bytes.byteLength)).rejects.toThrow('不匹配');
  });
});
