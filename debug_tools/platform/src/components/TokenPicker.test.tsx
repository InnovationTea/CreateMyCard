import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { TokenPicker, matchOptions, type TokenOption } from './TokenPicker';

const OPTIONS: TokenOption[] = [
  { value: '/data/weather/current/condition', label: '天气 · 当前 · 天气状况' },
  { value: '/data/weather/daily/1/rainProbabilityPercent', label: '天气 · 每日预报 · 降雨概率' },
  { value: 'resources/base/media/bell_fill.svg', label: '通知铃铛彩色图标' },
  { value: 'clickToDeeplink:Weather_CityCode', label: '跳转链接 · 天气城市页' },
];

describe('matchOptions', () => {
  it('matches Chinese labels, raw tokens and several terms at once', () => {
    // 中文标签、原始 token 一起参与匹配：动作的中文名里也有「天气」，所以这里命中三条。
    expect(matchOptions(OPTIONS, '天气').map((option) => option.value)).toEqual([
      '/data/weather/current/condition',
      '/data/weather/daily/1/rainProbabilityPercent',
      'clickToDeeplink:Weather_CityCode',
    ]);
    expect(matchOptions(OPTIONS, '天气 降雨')[0].value)
      .toBe('/data/weather/daily/1/rainProbabilityPercent');
    expect(matchOptions(OPTIONS, 'rainProbability')[0].value)
      .toBe('/data/weather/daily/1/rainProbabilityPercent');
    expect(matchOptions(OPTIONS, '铃铛')[0].value).toBe('resources/base/media/bell_fill.svg');
  });

  it('falls back to subsequence matching when nothing contains the text', () => {
    expect(matchOptions(OPTIONS, 'wthr')[0].value).toBe('/data/weather/current/condition');
  });
});

describe('TokenPicker', () => {
  afterEach(() => { cleanup(); vi.restoreAllMocks(); });

  function renderPicker(tokens: string[] = []) {
    const onChange = vi.fn();
    render(<TokenPicker legend="期望数据" options={OPTIONS} tokens={tokens}
      onChange={onChange} />);
    return onChange;
  }

  it('suggests by Chinese name and adds the raw token', () => {
    const onChange = renderPicker();
    fireEvent.change(screen.getByLabelText('期望数据'), { target: { value: '降雨' } });
    const suggestion = screen.getByRole('option', { name: /降雨概率/ });
    expect(within(suggestion).getByText('/data/weather/daily/1/rainProbabilityPercent'))
      .toBeInTheDocument();
    fireEvent.click(suggestion);
    expect(onChange).toHaveBeenCalledWith(['/data/weather/daily/1/rainProbabilityPercent']);
    expect(screen.queryByRole('listbox')).toBeNull();
  });

  it('takes the exact raw value on Enter and shows label plus raw name on the chip', () => {
    const onChange = renderPicker();
    const input = screen.getByLabelText('期望数据');
    fireEvent.change(input, { target: { value: '/data/weather/current/condition' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onChange).toHaveBeenCalledWith(['/data/weather/current/condition']);

    cleanup();
    renderPicker(['/data/weather/current/condition']);
    const chip = screen.getByTitle('天气 · 当前 · 天气状况 · /data/weather/current/condition');
    expect(within(chip).getByText('天气 · 当前 · 天气状况')).toBeInTheDocument();
    expect(within(chip).getByText('/data/weather/current/condition')).toBeInTheDocument();
  });

  it('keeps tokens outside the catalog but flags them', () => {
    const onChange = renderPicker(['/data/unknown/thing']);
    const chip = screen.getByTitle('/data/unknown/thing（不在候选库里，匹配时按原文比较）');
    expect(chip.className).toContain('is-missing');
    fireEvent.click(within(chip).getByRole('button', { name: '移除 /data/unknown/thing' }));
    expect(onChange).toHaveBeenCalledWith([]);
  });

  it('accepts hand-written tokens on Enter when nothing matches', () => {
    const onChange = renderPicker();
    const input = screen.getByLabelText('期望数据');
    fireEvent.change(input, { target: { value: 'Weather_CityCode' } });
    // 目标只有一条候选时回车取候选，这里用完全不在库里的写法验证原文兜底。
    fireEvent.change(input, { target: { value: 'zzz-自定义-字段' } });
    fireEvent.keyDown(input, { key: 'Enter' });
    expect(onChange).toHaveBeenCalledWith(['zzz-自定义-字段']);
  });
});
