import assert from 'node:assert/strict';
import { test } from 'vitest';
import { compileMiniDsl } from '../src/runtime/mini-renderer';

const handler = { call: 'clickToIntent', args: { intentName: 'SetSettingSwitch' } };
const actionProps = {
  label: '打开省电模式',
  actionSurface: '#331F4799',
  actionInk: '#FF1F4799',
  fontSize: 14,
  fontWeight: 500,
  onClick: [handler],
};

function source(type: string, props: Record<string, unknown>) {
  return [
    ['root', 'Column', { width: 'matchParent', height: 'matchParent' }, ['cta']],
    ['cta', type, props],
  ].map(row => JSON.stringify(row)).join('\n');
}

for (const size of ['2x2', '2x4'] as const) {
  test(`${size} 图文按钮保留图标、指定颜色、自然文字高度和点击动作`, () => {
    const icon = 'resources/base/media/battery_leaf_fill.svg';
    const { graph, expandedCount } = compileMiniDsl(
      source('PillButton', { ...actionProps, icon }), { size },
    );
    assert.equal(expandedCount, 4);
    const row = graph.getNode('cta');
    assert.equal(row?.type, 'Extended.Row');
    assert.deepEqual(row?.children, ['cta_icon', 'cta_text']);
    assert.deepEqual(row?.props.action, [{ functionCall: handler }]);
    const styles = row?.props.styles as Record<string, unknown>;
    assert.equal(styles.height, 36);
    assert.equal(styles.backgroundColor, actionProps.actionSurface);
    assert.equal(styles.alignItems, 'center');
    assert.equal(styles.justifyContent, 'center');
    const image = graph.getNode('cta_icon');
    assert.equal(image?.type, 'Extended.Image');
    assert.equal(image?.props.src, icon);
    assert.deepEqual(image?.props.styles, {
      width: 20, height: 20, objectFit: 'contain', flexShrink: 0,
      fillColor: actionProps.actionInk,
    });
    const text = graph.getNode('cta_text');
    assert.equal(text?.type, 'Extended.Text');
    assert.equal(text?.props.content, actionProps.label);
    const textStyles = text?.props.styles as Record<string, unknown>;
    assert.equal(textStyles.fontColor, actionProps.actionInk);
    assert.equal(textStyles.maxWidth, 96);
    assert.equal(textStyles.maxLines, 1);
    assert.equal(Object.hasOwn(textStyles, 'height'), false);
  });

  test(`${size} 纯文字按钮转换颜色字段并保留基础 Button`, () => {
    const { graph, expandedCount } = compileMiniDsl(source('PillButton', actionProps), { size });
    assert.equal(expandedCount, 2);
    const button = graph.getNode('cta');
    assert.equal(button?.type, 'Extended.Button');
    assert.equal(button?.props.label, actionProps.label);
    const styles = button?.props.styles as Record<string, unknown>;
    assert.equal(styles.backgroundColor, actionProps.actionSurface);
    assert.equal(styles.fontColor, actionProps.actionInk);
    assert.equal(styles.fontSize, 14);
    assert.equal(styles.height, 36);
    assert.equal(Object.hasOwn(styles, 'actionSurface'), false);
    assert.equal(Object.hasOwn(styles, 'actionInk'), false);
    assert.deepEqual(button?.props.action, [{ functionCall: handler }]);
  });
}

test('圆形按钮按当前 Recipe 展开 Stack 和居中的已着色图标', () => {
  const accessibility = { label: '打开设置' };
  const input = [
    ['root', 'Column', { width: 'matchParent', height: 'matchParent' }, ['slot']],
    ['slot', 'Stack', { width: 40, height: 40, alignContent: 'center' }, ['cta']],
    ['cta', 'CircleButton', {
      icon: 'resources/base/media/house_fill.svg', accessibility,
      actionSurface: actionProps.actionSurface, actionInk: actionProps.actionInk,
      onClick: [handler],
    }],
  ].map(row => JSON.stringify(row)).join('\n');
  const { graph } = compileMiniDsl(input, { size: '2x2' });
  const button = graph.getNode('cta');
  assert.equal(button?.type, 'Extended.Stack');
  assert.deepEqual(button?.children, ['cta_icon']);
  assert.deepEqual(button?.props.accessibility, accessibility);
  assert.deepEqual(button?.props.action, [{ functionCall: handler }]);
  const styles = button?.props.styles as Record<string, unknown>;
  assert.equal(styles.width, 40);
  assert.equal(styles.height, 40);
  assert.equal(styles.alignContent, 'center');
  assert.equal(styles.clip, true);
  assert.equal(styles.backgroundColor, actionProps.actionSurface);
  const icon = graph.getNode('cta_icon');
  assert.equal((icon?.props.styles as Record<string, unknown>).fillColor, actionProps.actionInk);
  assert.equal((icon?.props.styles as Record<string, unknown>).width, 20);
});

test('图文按钮展开后的节点 ID 冲突仍拒绝', () => {
  const input = source('PillButton', {
    ...actionProps, icon: 'resources/base/media/house_fill.svg',
  }) + '\n["cta_icon","Text",{"content":"已有节点"}]';
  assert.throws(() => compileMiniDsl(input), /ID.*冲突/);
});
