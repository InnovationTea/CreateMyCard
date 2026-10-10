// 验证正式编译预览的动态文案，覆盖同一组件的连接状态刷新。
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const fixture = JSON.parse(fs.readFileSync(path.join(__dirname,
  '../fixtures/ear123_connection_examples.json'), 'utf8'));
const files = process.argv.slice(2);
assert.equal(files.length, 2, '提供已连接、未连接的两份编译预览');

function renderHeader(content, value) {
  assert.ok(content.startsWith('{{ ') && content.endsWith(' }}'));
  const expression = content.slice(3, -3).replace(/\$\{([^}]+)\}/g, (_, pointer) => {
    assert.ok(pointer.startsWith('/'));
    let current = value;
    for (const key of pointer.slice(1).split('/')) {
      assert.ok(Object.hasOwn(current, key), pointer);
      current = current[key];
    }
    return JSON.stringify(current);
  });
  return vm.runInNewContext(expression, Object.create(null), { timeout: 1000 });
}

let sharedHeader;
let connectedValue;
for (let index = 0; index < files.length; index++) {
  const example = fixture.examples[index];
  const messages = JSON.parse(fs.readFileSync(files[index], 'utf8'));
  const components = messages.flatMap(message => message.updateComponents?.components || []);
  const header = components.find(node => node.content?.includes('/isConnected'));
  assert.ok(header, example.id);
  const value = messages.find(message => message.updateDataModel)?.updateDataModel.value;
  assert.deepEqual(value.data.earphone, example.earphoneData);
  assert.equal(renderHeader(header.content, value), example.expectedHeader);
  assert.equal(components.filter(node => node.onClick).length, 1);
  if (index === 0) {
    sharedHeader = header.content;
    connectedValue = structuredClone(value);
  } else {
    assert.equal(header.content, sharedHeader, '两种首帧数据应保留同一运行时表达式');
  }
  console.log(`${example.label}：${example.expectedHeader}，通过`);
}

connectedValue.data.earphone.isConnected = false;
assert.equal(renderHeader(sharedHeader, connectedValue), '未连接');
connectedValue.data.earphone.isConnected = true;
connectedValue.data.earphone.earphoneName = 'FreeBuds Pro 4';
assert.equal(renderHeader(sharedHeader, connectedValue), '已连接 FreeBuds Pro 4');
console.log('连接转断开、重新连接：通过；动态文案验证共4项通过');
