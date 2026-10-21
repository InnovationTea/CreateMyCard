const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { test } = require('node:test');
const ts = require('../../node_modules/typescript');

const source = fs.readFileSync(path.join(__dirname,
  '../../a2ui_render/entry/src/main/ets/runner/DesktopBridge.ets'), 'utf8');
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;

async function run(change = {}) {
  const forms = [2, 3].map((dimension) => ({
    formId: String(dimension), dimension, formName: 'DebugCard', formLocation: 0,
  }));
  const envelope = { runId: 'run', sampleId: 'sample', revision: 1,
    digest: 'digest', size: '2x2', dsl: '{}' };
  const command = { commandId: 'command', operation: 'replace', formId: '2', envelope,
    expectedForms: structuredClone(forms), expectedDisplay: [1000, 1000, 2, 0],
    expectedRectPx: { left: 0, top: 0, width: 400, height: 400 } };
  const display = { width: 1000, height: 1000, densityPixels: 2, rotation: 0 };
  if (change.halfPixel) {
    display.densityPixels = 2.5;
    command.expectedDisplay[2] = 2.5;
    command.expectedRectPx.width = 502;
    command.expectedRectPx.height = 500;
  }
  const calls = [];
  let reply;
  let reads = 0;
  let queries = 0;
  const provider = {
    async getPublishedRunningFormInfos() {
      queries++;
      return change.forms ? change.forms(queries, forms) : forms;
    },
    async getFormRect() {
      reads++;
      calls.push('rect');
      if (change.displayAt === reads) display.rotation = 1;
      return { left: change.movedAt === reads ? 10 : 0, top: 0,
        width: change.halfPixel ? 201 : 200, height: 200 };
    },
    async updateForm() {
      calls.push('update');
      if (change.updateFailure) throw new Error('update failed');
    },
  };
  const modules = {
    '@kit.AbilityKit': { bundleManager: { BundleFlag: { GET_BUNDLE_INFO_DEFAULT: 0 },
      getBundleInfoForSelfSync: () => ({ versionName: '1' }) } },
    '@kit.FormKit': { formInfo: { FormLocation: { DESKTOP: 0 } }, formProvider: provider,
      formBindingData: { createFormBindingData: (value) => value } },
    '@kit.CoreFileKit': { fileIo: { readTextSync: () => JSON.stringify(command),
      unlinkSync: () => calls.push('cleanup') } },
    '@kit.PerformanceAnalysisKit': { hilog: {
      info: (...args) => { reply = JSON.parse(args[3].replace('A2UI_DESKTOP ', '')); },
      error: (...args) => { reply = JSON.parse(args[3].replace('A2UI_DESKTOP ', '')); },
    } },
    '@kit.ArkUI': { display: { getDefaultDisplaySync: () => display } },
    '@kit.LocalizationKit': { i18n: { System: { getSystemLocaleInstance: () => 'zh-CN' } } },
    './A2UIProtocol': { isSafeSampleFile: () => true },
    './DesktopProtocol': { DESKTOP_FORM_NAME: 'DebugCard',
      readDesktopEnvelope: () => JSON.stringify(envelope),
      async saveDesktopEnvelope() {
        calls.push('save');
        if (change.invalidDigest) throw new Error('digest mismatch');
      } },
  };
  const module = { exports: {} };
  vm.runInNewContext(compiled, { exports: module.exports, module,
    require(name) { assert.ok(Object.hasOwn(modules, name), name); return modules[name]; } });
  await module.exports.executeDesktopCommand({ getApplicationContext: () => ({ filesDir: '/files' }) },
    'command.json');
  return { reply, calls };
}

test('replacement keeps before, staged, updated and confirmed rect checks in order', async () => {
  const { reply, calls } = await run();
  assert.equal(reply.state, 'OK');
  assert.deepEqual(calls, ['rect', 'save', 'rect', 'update', 'rect', 'rect', 'cleanup']);
  assert.equal(reply.digest, 'digest');
  assert.equal(reply.revision, 1);
  assert.equal(reply.desktopBatchUpdate, true);
});

test('fractional density uses the same half-pixel rounding as Python', async () => {
  const { reply } = await run({ halfPixel: true });
  assert.equal(reply.state, 'OK');
});

for (const [name, changes] of [
  ['missing form', { forms: (_index, forms) => forms.slice(0, 1) }],
  ['replaced form after staging', { forms: (index, forms) => index >= 3 ? [] : forms }],
  ['moved before save', { movedAt: 1 }],
  ['moved after save', { movedAt: 2 }],
  ['display changed before update', { displayAt: 2 }],
  ['invalid digest', { invalidDigest: true }],
]) {
  test(`${name} prevents update`, async () => {
    const { reply, calls } = await run(changes);
    assert.equal(reply.state, 'FAILED');
    assert.ok(!calls.includes('update'));
    assert.ok(!calls.includes('cleanup'));
  });
}

for (const [name, changes] of [
  ['update failure', { updateFailure: true }],
  ['moved after update', { movedAt: 3 }],
  ['moved at confirmation', { movedAt: 4 }],
]) {
  test(`${name} cannot return success`, async () => {
    const { reply, calls } = await run(changes);
    assert.equal(reply.state, 'FAILED');
    assert.equal(calls.filter((value) => value === 'update').length, 1);
  });
}
