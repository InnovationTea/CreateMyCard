import { describe, expect, it } from 'vitest';
import {
  buildDefaultArguments,
  buildOutputFieldPaths,
  buildSelectedSubset,
  extractArtifact,
  parseLegacyToolResponse,
  parsePythonRepr,
} from '../src/parser';

describe('parsePythonRepr', () => {
  it('parses regular JSON without changing values', () => {
    expect(parsePythonRepr('{"ok":true,"count":2}')).toEqual({ ok: true, count: 2 });
  });

  it('parses Python literals and data= wrappers without eval', () => {
    expect(parsePythonRepr("ToolResponse(data={'ok': True, 'reason': None})"))
      .toEqual({ ok: true, reason: null });
  });

  it('parses fenced JSON output', () => {
    expect(parsePythonRepr('prefix\n```json\n{"items":[1,2]}\n```')).toEqual({ items: [1, 2] });
  });
});

describe('schema helpers', () => {
  const schema = {
    type: 'object',
    required: ['city'],
    properties: {
      city: { type: 'string', sampleValue: 'Shanghai' },
      limit: { type: 'integer' },
      optional: { type: 'boolean' },
    },
  };

  it('builds required and optional argument placeholders', () => {
    expect(buildDefaultArguments(schema)).toEqual({ city: 'Shanghai' });
    expect(buildDefaultArguments(schema, true)).toEqual({ city: 'Shanghai', limit: 0, optional: false });
  });

  it('expands output schema paths with JSON pointer escaping', () => {
    expect(buildOutputFieldPaths({
      type: 'object',
      properties: { 'a/b': { type: 'string' }, list: { type: 'array', items: { type: 'number' } } },
    }, (path) => path === 'properties.list' ? 2 : 1)).toEqual(['/a~1b', '/list/0', '/list/1']);
  });

  it('builds a nested subset while retaining array indexes', () => {
    const source = { data: [{ id: 'a', value: 1 }, { id: 'b', value: 2 }] };
    const subset = buildSelectedSubset(source, [
      { historyId: 1, operation: 'getWidgetCapabilityOverview', path: 'data.1.value', key: 'value', value: 2 },
    ]);
    expect(subset).toEqual({ data: [undefined, { value: 2 }] });
  });

  it('unwraps legacy stream data for renderer hand-off', () => {
    const artifact = extractArtifact({ data: { genui: '{"version":"1"}', artifactUrl: 'https://example.invalid/a' } }, 'generateWidgetCardCompactDsl', 'run-1');
    expect(artifact.genui).toContain('version');
    expect(artifact.raw).toEqual({ genui: '{"version":"1"}', artifactUrl: 'https://example.invalid/a' });
  });

  it('normalizes artifact_reference URLs for renderer hand-off', () => {
    const artifact = extractArtifact({
      data: { artifact_reference: { url: 'mock://artifact-card.md' } },
    }, 'generateWidgetCardCompactDsl', 'run-2');
    expect(artifact.artifactUrl).toBe('mock://artifact-card.md');
  });

  it('parses Pydantic-style final payloads', () => {
    const parsed = parsePythonRepr(
      "GenerateWidgetCardResponse(status='success', artifactUrl='mock://artifact-card.md', artifactDigest='sha256:test')",
    );
    expect(parsed).toEqual({
      status: 'success',
      artifactUrl: 'mock://artifact-card.md',
      artifactDigest: 'sha256:test',
    });
  });

  it('unwraps Pydantic-style payloads inside a legacy final frame', () => {
    const parsed = parseLegacyToolResponse(
      "type='final' tool='widgetCardService' operation='generateWidgetCardCompactDsl' "
      + "requestId='session&interaction' data=GenerateWidgetCardResponse(status='success', "
      + "artifactUrl='mock://artifact-card.md') status='success' errorCode='' error=None",
    );
    expect(parsed?.data).toEqual({ status: 'success', artifactUrl: 'mock://artifact-card.md' });
  });

  it('preserves validation details containing Python tuple paths', () => {
    const parsed = parseLegacyToolResponse(
      "type='error' tool='widgetCardService' operation='generateWidgetCardCompactDsl' "
      + "requestId='session&interaction' data={} status='failed' "
      + "errorCode='INVALID_ARGUMENTS' error={'message': 'Invalid arguments.', "
      + "'details': [{'type': 'missing', 'loc': ('title',), 'msg': 'Field required'}]}",
    );

    expect(parsed?.error).toEqual({
      message: 'Invalid arguments.',
      details: [{ type: 'missing', loc: ['title'], msg: 'Field required' }],
    });
  });
});
