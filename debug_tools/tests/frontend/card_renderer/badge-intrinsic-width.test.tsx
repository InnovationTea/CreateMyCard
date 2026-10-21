// @vitest-environment jsdom

import React from 'react';
import '@testing-library/jest-dom/vitest';
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { ExtendedText } from '../../../card_renderer/runtime/components/src/extended/ExtendedText';
import { mergeCommonStyles } from '../../../card_renderer/runtime/components/src/extended/common-styles';

afterEach(cleanup);

describe('Badge 固有宽度', () => {
  it.each(['1', '42', '1234'])('数字 %s 的完整宽度包含内边距', (value) => {
    render(<ExtendedText content={value} width="wrapContent" maxLines={1}
      height={16} padding={{ left: 6, right: 6 }} />);
    expect(screen.getByText(value)).toHaveStyle({ width: 'max-content', paddingLeft: '6px' });
  });

  it('普通固定宽度和撑满宽度仍按原合同处理', () => {
    expect(mergeCommonStyles({ width: 132 }).width).toBe(132);
    expect(mergeCommonStyles({ width: 'matchParent' }).width).toBe('100%');
    expect(mergeCommonStyles({ width: '50%' }).width).toBe('50%');
  });
});
