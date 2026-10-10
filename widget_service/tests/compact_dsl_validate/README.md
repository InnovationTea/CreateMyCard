# validate_compact_dsl 校验数据

范围按 compact_dsl_validator.py 中 153 个 errors.append 源码位置统计。这些位置由 validate_compact_dsl 及其检查函数执行；不把解析器异常和双动作校验的内部原因重复计数。

149 个位置有单错误样例；3 个位置因校验条件存在逻辑包含关系而必然伴随其他错误；1 个位置不可从公开入口触发。152 个可触发位置都通过完整 validate_compact_dsl 入口验证，并用执行跟踪确认实际命中目标 errors.append。

按检查函数分目录，每组包含 sample_compact.dsl、sample_task_spec.json、sample_card_spec.json。expected.json 仅记录预期错误、异常类型和输入文件校验和；coverage.json 记录完整的 153 个源码错误点及其样例目录。

## 使用

在项目根目录运行：

```powershell
D:\ProgramFiles\anaconda3\envs\CreateMyCard\python.exe widget_service\tests\compact_dsl_validate\verify_cases.py
```

脚本直接调用完整校验入口，核对异常类型、完整错误列表和文件校验和。校验和在统一 CRLF、CR 为 LF 后计算，不受 Git 检出换行格式影响。修改样例或校验器后如回放失败，需要重新核对 expected.json。

## 验证记录

逐组完整入口回放：LF 与 CRLF 两种换行格式均为 153 通过、0 失败。清除 PYTHONPATH 且不传 `--cloud` 的默认入口 smoke 回放为 153 通过、0 失败。新回放脚本 Ruff 通过，git diff --check 通过。
收集项目测试输入时执行相关 7 个测试文件：408 通过、6 失败。失败来自当前工作区原有测试预期与校验器不一致：1 个模板空容器被解析器提前拦截、3 个格式化读数目前被接受、2 个 W9 样例直接显示布尔字段。此次仅新增数据与回放脚本，未修改生产代码。

## 逐错误位置索引

| 检查函数 | 源码行 | 样例目录 | 状态 | 实际错误数 |
| --- | ---: | --- | --- | ---: |
| `_collect_asset_source_errors` | 290 | [_collect_asset_source_errors/01](_collect_asset_source_errors/01/expected.json) | 单错误 | 1 |
| `_collect_asset_color_errors` | 332 | [_collect_asset_color_errors/01](_collect_asset_color_errors/01/expected.json) | 单错误 | 1 |
| `_collect_hero_value_errors` | 391 | [_collect_hero_value_errors/01](_collect_hero_value_errors/01/expected.json) | 单错误 | 1 |
| `_collect_hero_value_errors` | 406 | [_collect_hero_value_errors/03](_collect_hero_value_errors/03/expected.json) | 单错误 | 1 |
| `_collect_hero_value_errors` | 425 | [_collect_hero_value_errors/02](_collect_hero_value_errors/02/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_weather_date_errors` | 461 | [_collect_two_by_two_weather_date_errors/01](_collect_two_by_two_weather_date_errors/01/expected.json) | 单错误 | 1 |
| `_collect_adjacent_display_unit_errors` | 763 | [_collect_adjacent_display_unit_errors/02](_collect_adjacent_display_unit_errors/02/expected.json) | 伴随错误 | 2 |
| `_collect_adjacent_display_unit_errors` | 825 | [_collect_adjacent_display_unit_errors/03](_collect_adjacent_display_unit_errors/03/expected.json) | 单错误 | 1 |
| `_collect_adjacent_display_unit_errors` | 836 | [_collect_adjacent_display_unit_errors/01](_collect_adjacent_display_unit_errors/01/expected.json) | 单错误 | 1 |
| `_collect_mixed_font_row_alignment_errors` | 1130 | [_collect_mixed_font_row_alignment_errors/01](_collect_mixed_font_row_alignment_errors/01/expected.json) | 单错误 | 1 |
| `_collect_mixed_font_row_alignment_errors` | 1154 | [_collect_mixed_font_row_alignment_errors/02](_collect_mixed_font_row_alignment_errors/02/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_small_backboard_errors` | 1203 | [_collect_two_by_four_small_backboard_errors/01](_collect_two_by_four_small_backboard_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_small_backboard_errors` | 1214 | [_collect_two_by_four_small_backboard_errors/03](_collect_two_by_four_small_backboard_errors/03/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_small_backboard_errors` | 1221 | [_collect_two_by_four_small_backboard_errors/02](_collect_two_by_four_small_backboard_errors/02/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_small_backboard_errors` | 1227 | [_collect_two_by_four_small_backboard_errors/04](_collect_two_by_four_small_backboard_errors/04/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_action_backboard_errors` | 1320 | [_collect_two_by_four_action_backboard_errors/01](_collect_two_by_four_action_backboard_errors/01/expected.json) | 伴随错误 | 2 |
| `_collect_two_by_four_action_backboard_errors` | 1328 | [_collect_two_by_four_action_backboard_errors/02](_collect_two_by_four_action_backboard_errors/02/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_action_backboard_errors` | 1337 | [_collect_two_by_four_action_backboard_errors/03](_collect_two_by_four_action_backboard_errors/03/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_action_backboard_errors` | 1344 | [_collect_two_by_four_action_backboard_errors/04](_collect_two_by_four_action_backboard_errors/04/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_action_backboard_errors` | 1349 | [_collect_two_by_four_action_backboard_errors/05](_collect_two_by_four_action_backboard_errors/05/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_action_backboard_errors` | 1354 | [_collect_two_by_four_action_backboard_errors/06](_collect_two_by_four_action_backboard_errors/06/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_action_row_errors` | 1374 | [_collect_two_by_four_action_row_errors/01](_collect_two_by_four_action_row_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_narrow_graphical_action_errors` | 1423 | [_collect_two_by_two_narrow_graphical_action_errors/01](_collect_two_by_two_narrow_graphical_action_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_full_width_action_errors` | 1454 | [_collect_two_by_four_full_width_action_errors/01](_collect_two_by_four_full_width_action_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_full_width_action_errors` | 1464 | [_collect_two_by_four_full_width_action_errors/02](_collect_two_by_four_full_width_action_errors/02/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_full_width_action_errors` | 1473 | [_collect_two_by_four_full_width_action_errors/03](_collect_two_by_four_full_width_action_errors/03/expected.json) | 单错误 | 1 |
| `_collect_raw_boolean_text_errors` | 1564 | [_collect_raw_boolean_text_errors/01](_collect_raw_boolean_text_errors/01/expected.json) | 单错误 | 1 |
| `_collect_progress_value_errors` | 1590 | [_collect_progress_value_errors/01](_collect_progress_value_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_density_errors` | 1729 | [_collect_two_by_four_w9_density_errors/01](_collect_two_by_four_w9_density_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_density_errors` | 1736 | [_collect_two_by_four_w9_density_errors/02](_collect_two_by_four_w9_density_errors/02/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_density_errors` | 1742 | [_collect_two_by_four_w9_density_errors/03](_collect_two_by_four_w9_density_errors/03/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_content_errors` | 1814 | [_collect_two_by_four_w9_content_errors/04](_collect_two_by_four_w9_content_errors/04/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_content_errors` | 1842 | [_collect_two_by_four_w9_content_errors/05](_collect_two_by_four_w9_content_errors/05/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_content_errors` | 1851 | [_collect_two_by_four_w9_content_errors/06](_collect_two_by_four_w9_content_errors/06/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_content_errors` | 1875 | [_collect_two_by_four_w9_content_errors/08](_collect_two_by_four_w9_content_errors/08/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_content_errors` | 1894 | [_collect_two_by_four_w9_content_errors/09](_collect_two_by_four_w9_content_errors/09/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_content_errors` | 1899 | [_collect_two_by_four_w9_content_errors/07](_collect_two_by_four_w9_content_errors/07/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_content_errors` | 1919 | [_collect_two_by_four_w9_content_errors/10](_collect_two_by_four_w9_content_errors/10/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_content_errors` | 1945 | [_collect_two_by_four_w9_content_errors/14](_collect_two_by_four_w9_content_errors/14/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_content_errors` | 1955 | [_collect_two_by_four_w9_content_errors/13](_collect_two_by_four_w9_content_errors/13/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_content_errors` | 1960 | [_collect_two_by_four_w9_content_errors/11](_collect_two_by_four_w9_content_errors/11/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_content_errors` | 1969 | [_collect_two_by_four_w9_content_errors/12](_collect_two_by_four_w9_content_errors/12/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_content_errors` | 1976 | [_collect_two_by_four_w9_content_errors/01](_collect_two_by_four_w9_content_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_content_errors` | 1981 | [_collect_two_by_four_w9_content_errors/02](_collect_two_by_four_w9_content_errors/02/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_content_errors` | 2009 | [_collect_two_by_four_w9_content_errors/03](_collect_two_by_four_w9_content_errors/03/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_s4_text_errors` | 2032 | [_collect_two_by_two_s4_text_errors/01](_collect_two_by_two_s4_text_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_s4_text_errors` | 2039 | [_collect_two_by_two_s4_text_errors/03](_collect_two_by_two_s4_text_errors/03/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_s4_text_errors` | 2056 | [_collect_two_by_two_s4_text_errors/04](_collect_two_by_two_s4_text_errors/04/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_s4_text_errors` | 2069 | [_collect_two_by_two_s4_text_errors/05](_collect_two_by_two_s4_text_errors/05/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_s4_text_errors` | 2087 | [_collect_two_by_two_s4_text_errors/06](_collect_two_by_two_s4_text_errors/06/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_s4_text_errors` | 2099 | [_collect_two_by_two_s4_text_errors/02](_collect_two_by_two_s4_text_errors/02/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_s4_vertical_alignment_errors` | 2130 | [_collect_two_by_two_s4_vertical_alignment_errors/02](_collect_two_by_two_s4_vertical_alignment_errors/02/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_s4_vertical_alignment_errors` | 2147 | [_collect_two_by_two_s4_vertical_alignment_errors/01](_collect_two_by_two_s4_vertical_alignment_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_ring_group_alignment_errors` | 2191 | [_collect_two_by_two_ring_group_alignment_errors/01](_collect_two_by_two_ring_group_alignment_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_s4_palette_errors` | 2235 | [_collect_two_by_two_s4_palette_errors/01](_collect_two_by_two_s4_palette_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_aux_icon_errors` | 2326 | [_collect_two_by_four_aux_icon_errors/01](_collect_two_by_four_aux_icon_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_alignment_errors` | 2392 | [_collect_two_by_four_w1_focus_alignment_errors/01](_collect_two_by_four_w1_focus_alignment_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_alignment_errors` | 2401 | [_collect_two_by_four_w1_focus_alignment_errors/02](_collect_two_by_four_w1_focus_alignment_errors/02/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_alignment_errors` | 2408 | [_collect_two_by_four_w1_focus_alignment_errors/03](_collect_two_by_four_w1_focus_alignment_errors/03/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_alignment_errors` | 2430 | [_collect_two_by_four_w1_focus_alignment_errors/04](_collect_two_by_four_w1_focus_alignment_errors/04/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_alignment_errors` | 2437 | [_collect_two_by_four_w1_focus_alignment_errors/05](_collect_two_by_four_w1_focus_alignment_errors/05/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_aux_errors` | 2469 | [_collect_two_by_four_w1_focus_aux_errors/01](_collect_two_by_four_w1_focus_aux_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_aux_errors` | 2491 | [_collect_two_by_four_w1_focus_aux_errors/02](_collect_two_by_four_w1_focus_aux_errors/02/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_aux_errors` | 2504 | [_collect_two_by_four_w1_focus_aux_errors/03](_collect_two_by_four_w1_focus_aux_errors/03/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_aux_errors` | 2510 | [_collect_two_by_four_w1_focus_aux_errors/04](_collect_two_by_four_w1_focus_aux_errors/04/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_aux_errors` | 2526 | [_collect_two_by_four_w1_focus_aux_errors/05](_collect_two_by_four_w1_focus_aux_errors/05/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_aux_errors` | 2541 | [_collect_two_by_four_w1_focus_aux_errors/07](_collect_two_by_four_w1_focus_aux_errors/07/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_aux_errors` | 2571 | [_collect_two_by_four_w1_focus_aux_errors/08](_collect_two_by_four_w1_focus_aux_errors/08/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_aux_errors` | 2609 | [_collect_two_by_four_w1_focus_aux_errors/06](_collect_two_by_four_w1_focus_aux_errors/06/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_aux_errors` | 2641 | [_collect_two_by_four_w1_focus_aux_errors/09](_collect_two_by_four_w1_focus_aux_errors/09/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_aux_errors` | 2651 | [_collect_two_by_four_w1_focus_aux_errors/10](_collect_two_by_four_w1_focus_aux_errors/10/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_aux_errors` | 2673 | [_collect_two_by_four_w1_focus_aux_errors/11](_collect_two_by_four_w1_focus_aux_errors/11/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_aux_errors` | 2679 | [_collect_two_by_four_w1_focus_aux_errors/12](_collect_two_by_four_w1_focus_aux_errors/12/expected.json) | 伴随错误 | 2 |
| `_collect_two_by_four_w1_focus_aux_errors` | 2692 | [_collect_two_by_four_w1_focus_aux_errors/15](_collect_two_by_four_w1_focus_aux_errors/15/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_aux_errors` | 2702 | [_collect_two_by_four_w1_focus_aux_errors/13](_collect_two_by_four_w1_focus_aux_errors/13/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_aux_errors` | 2722 | [_collect_two_by_four_w1_focus_aux_errors/14](_collect_two_by_four_w1_focus_aux_errors/14/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_weather_triplet_errors` | 2757 | [_collect_two_by_four_w9_weather_triplet_errors/01](_collect_two_by_four_w9_weather_triplet_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_weather_triplet_errors` | 2766 | [_collect_two_by_four_w9_weather_triplet_errors/02](_collect_two_by_four_w9_weather_triplet_errors/02/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_weather_triplet_errors` | 2774 | [_collect_two_by_four_w9_weather_triplet_errors/03](_collect_two_by_four_w9_weather_triplet_errors/03/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_weather_triplet_errors` | 2781 | [_collect_two_by_four_w9_weather_triplet_errors/04](_collect_two_by_four_w9_weather_triplet_errors/04/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_weather_triplet_errors` | 2787 | [_collect_two_by_four_w9_weather_triplet_errors/05](_collect_two_by_four_w9_weather_triplet_errors/05/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_centered_hero_errors` | 3131 | [_collect_two_by_two_centered_hero_errors/01](_collect_two_by_two_centered_hero_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_centered_hero_errors` | 3139 | [_collect_two_by_two_centered_hero_errors/02](_collect_two_by_two_centered_hero_errors/02/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_centered_hero_errors` | 3151 | [_collect_two_by_two_centered_hero_errors/05](_collect_two_by_two_centered_hero_errors/05/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_centered_hero_errors` | 3156 | [_collect_two_by_two_centered_hero_errors/06](_collect_two_by_two_centered_hero_errors/06/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_centered_hero_errors` | 3178 | [_collect_two_by_two_centered_hero_errors/03](_collect_two_by_two_centered_hero_errors/03/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_centered_hero_errors` | 3195 | [_collect_two_by_two_centered_hero_errors/04](_collect_two_by_two_centered_hero_errors/04/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_content_density_errors` | 3266 | [_collect_two_by_two_content_density_errors/02](_collect_two_by_two_content_density_errors/02/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_content_density_errors` | 3273 | [_collect_two_by_two_content_density_errors/03](_collect_two_by_two_content_density_errors/03/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_content_density_errors` | 3279 | [_collect_two_by_two_content_density_errors/04](_collect_two_by_two_content_density_errors/04/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_content_density_errors` | 3296 | [_collect_two_by_two_content_density_errors/01](_collect_two_by_two_content_density_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_content_density_errors` | 3310 | [_collect_two_by_two_content_density_errors/05](_collect_two_by_two_content_density_errors/05/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_detached_unit_errors` | 3378 | [_collect_two_by_four_detached_unit_errors/01](_collect_two_by_four_detached_unit_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_weather_calendar_alignment_errors` | 3419 | [_collect_two_by_four_weather_calendar_alignment_errors/01](_collect_two_by_four_weather_calendar_alignment_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_countdown_backboard_errors` | 3455 | [_collect_two_by_four_countdown_backboard_errors/01](_collect_two_by_four_countdown_backboard_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_countdown_backboard_errors` | 3469 | [_collect_two_by_four_countdown_backboard_errors/02](_collect_two_by_four_countdown_backboard_errors/02/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_countdown_backboard_errors` | 3479 | [_collect_two_by_four_countdown_backboard_errors/03](_collect_two_by_four_countdown_backboard_errors/03/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_countdown_backboard_errors` | 3488 | [_collect_two_by_four_countdown_backboard_errors/04](_collect_two_by_four_countdown_backboard_errors/04/expected.json) | 单错误 | 1 |
| `_collect_layout_route_errors` | 3595 | [_collect_layout_route_errors/05](_collect_layout_route_errors/05/expected.json) | 单错误 | 1 |
| `_collect_layout_route_errors` | 3614 | [_collect_layout_route_errors/10](_collect_layout_route_errors/10/expected.json) | 单错误 | 1 |
| `_collect_layout_route_errors` | 3626 | [_collect_layout_route_errors/06](_collect_layout_route_errors/06/expected.json) | 单错误 | 1 |
| `_collect_layout_route_errors` | 3634 | [_collect_layout_route_errors/11](_collect_layout_route_errors/11/expected.json) | 单错误 | 1 |
| `_collect_layout_route_errors` | 3660 | [_collect_layout_route_errors/02](_collect_layout_route_errors/02/expected.json) | 单错误 | 1 |
| `_collect_layout_route_errors` | 3674 | [_collect_layout_route_errors/07](_collect_layout_route_errors/07/expected.json) | 单错误 | 1 |
| `_collect_layout_route_errors` | 3685 | [_collect_layout_route_errors/08](_collect_layout_route_errors/08/expected.json) | 单错误 | 1 |
| `_collect_layout_route_errors` | 3698 | [_collect_layout_route_errors/03](_collect_layout_route_errors/03/expected.json) | 单错误 | 1 |
| `_collect_layout_route_errors` | 3743 | [_collect_layout_route_errors/09](_collect_layout_route_errors/09/expected.json) | 单错误 | 1 |
| `_collect_layout_route_errors` | 3751 | [_collect_layout_route_errors/04](_collect_layout_route_errors/04/expected.json) | 单错误 | 1 |
| `_collect_layout_route_errors` | 3769 | [_collect_layout_route_errors/01](_collect_layout_route_errors/01/expected.json) | 单错误 | 1 |
| `_collect_2x2_countdown_group_errors` | 3800 | [_collect_2x2_countdown_group_errors/01](_collect_2x2_countdown_group_errors/01/expected.json) | 单错误 | 1 |
| `_collect_2x2_countdown_group_errors` | 3834 | [_collect_2x2_countdown_group_errors/04](_collect_2x2_countdown_group_errors/04/expected.json) | 单错误 | 1 |
| `_collect_2x2_countdown_group_errors` | 3842 | [_collect_2x2_countdown_group_errors/05](_collect_2x2_countdown_group_errors/05/expected.json) | 单错误 | 1 |
| `_collect_2x2_countdown_group_errors` | 3850 | [_collect_2x2_countdown_group_errors/06](_collect_2x2_countdown_group_errors/06/expected.json) | 单错误 | 1 |
| `_collect_2x2_countdown_group_errors` | 3856 | [_collect_2x2_countdown_group_errors/07](_collect_2x2_countdown_group_errors/07/expected.json) | 单错误 | 1 |
| `_collect_2x2_countdown_group_errors` | 3860 | [_collect_2x2_countdown_group_errors/08](_collect_2x2_countdown_group_errors/08/expected.json) | 单错误 | 1 |
| `_collect_2x2_countdown_group_errors` | 3869 | [_collect_2x2_countdown_group_errors/02](_collect_2x2_countdown_group_errors/02/expected.json) | 单错误 | 1 |
| `_collect_2x2_countdown_group_errors` | 3879 | [_collect_2x2_countdown_group_errors/03](_collect_2x2_countdown_group_errors/03/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_sparse_layout_errors` | 3909 | [_collect_two_by_four_w9_sparse_layout_errors/01](_collect_two_by_four_w9_sparse_layout_errors/01/expected.json) | 单错误 | 1 |
| `_collect_fusion_composition_errors` | 4030 | [_collect_fusion_composition_errors/01](_collect_fusion_composition_errors/01/expected.json) | 单错误 | 1 |
| `_collect_semantic_text_errors` | 4116 | [_collect_semantic_text_errors/01](_collect_semantic_text_errors/01/expected.json) | 单错误 | 1 |
| `_collect_semantic_text_errors` | 4139 | [_collect_semantic_text_errors/02](_collect_semantic_text_errors/02/expected.json) | 单错误 | 1 |
| `_collect_semantic_text_errors` | 4153 | [_collect_semantic_text_errors/03](_collect_semantic_text_errors/03/expected.json) | 单错误 | 1 |
| `_collect_semantic_text_errors` | 4163 | [_collect_semantic_text_errors/04](_collect_semantic_text_errors/04/expected.json) | 单错误 | 1 |
| `_collect_unbound_action_hint_errors` | 4207 | [_collect_unbound_action_hint_errors/01](_collect_unbound_action_hint_errors/01/expected.json) | 单错误 | 1 |
| `_collect_ambiguous_metric_text_errors` | 4285 | [_collect_ambiguous_metric_text_errors/01](_collect_ambiguous_metric_text_errors/01/expected.json) | 单错误 | 1 |
| `_collect_component_contract_errors` | 4302 | [_collect_component_contract_errors/01](_collect_component_contract_errors/01/expected.json) | 单错误 | 1 |
| `_collect_component_contract_errors` | 4306 | [_collect_component_contract_errors/02](_collect_component_contract_errors/02/expected.json) | 单错误 | 1 |
| `_collect_component_parent_errors` | 4324 | [_collect_component_parent_errors/02](_collect_component_parent_errors/02/expected.json) | 入口不可触发：解析器去重 | 0 |
| `_collect_component_parent_errors` | 4336 | [_collect_component_parent_errors/01](_collect_component_parent_errors/01/expected.json) | 单错误 | 1 |
| `_collect_container_errors` | 4351 | [_collect_container_errors/01](_collect_container_errors/01/expected.json) | 单错误 | 1 |
| `_collect_height_budget_errors` | 4383 | [_collect_height_budget_errors/01](_collect_height_budget_errors/01/expected.json) | 单错误 | 1 |
| `_collect_action_unit_errors` | 4527 | [_collect_action_unit_errors/01](_collect_action_unit_errors/01/expected.json) | 单错误 | 1 |
| `_collect_action_unit_errors` | 4532 | [_collect_action_unit_errors/02](_collect_action_unit_errors/02/expected.json) | 单错误 | 1 |
| `_collect_action_unit_errors` | 4534 | [_collect_action_unit_errors/03](_collect_action_unit_errors/03/expected.json) | 单错误 | 1 |
| `_collect_action_unit_errors` | 4543 | [_collect_action_unit_errors/05](_collect_action_unit_errors/05/expected.json) | 单错误 | 1 |
| `_collect_action_unit_errors` | 4554 | [_collect_action_unit_errors/04](_collect_action_unit_errors/04/expected.json) | 单错误 | 1 |
| `_collect_required_non_empty_string` | 4564 | [_collect_required_non_empty_string/01](_collect_required_non_empty_string/01/expected.json) | 单错误 | 1 |
| `_collect_on_click_errors` | 4577 | [_collect_on_click_errors/01](_collect_on_click_errors/01/expected.json) | 单错误 | 1 |
| `_collect_on_click_errors` | 4581 | [_collect_on_click_errors/02](_collect_on_click_errors/02/expected.json) | 单错误 | 1 |
| `_collect_on_click_errors` | 4584 | [_collect_on_click_errors/03](_collect_on_click_errors/03/expected.json) | 单错误 | 1 |
| `_collect_on_click_errors` | 4589 | [_collect_on_click_errors/04](_collect_on_click_errors/04/expected.json) | 单错误 | 1 |
| `_collect_on_click_errors` | 4592 | [_collect_on_click_errors/05](_collect_on_click_errors/05/expected.json) | 单错误 | 1 |
| `_collect_on_click_errors` | 4595 | [_collect_on_click_errors/06](_collect_on_click_errors/06/expected.json) | 单错误 | 1 |
| `_collect_expression_context` | 4683 | [_collect_expression_context/01](_collect_expression_context/01/expected.json) | 单错误 | 1 |
| `_collect_expression_context` | 4692 | [_collect_expression_context/02](_collect_expression_context/02/expected.json) | 单错误 | 1 |
| `_collect_expression_context` | 4701 | [_collect_expression_context/04](_collect_expression_context/04/expected.json) | 单错误 | 1 |
| `_collect_expression_context` | 4708 | [_collect_expression_context/03](_collect_expression_context/03/expected.json) | 单错误 | 1 |
| `_collect_expression_context` | 4712 | [_collect_expression_context/05](_collect_expression_context/05/expected.json) | 单错误 | 1 |
| `_collect_path_binding` | 4762 | [_collect_path_binding/01](_collect_path_binding/01/expected.json) | 单错误 | 1 |
| `_collect_data_context_errors` | 4776 | [_collect_data_context_errors/02](_collect_data_context_errors/02/expected.json) | 单错误 | 1 |
| `_collect_data_context_errors` | 4780 | [_collect_data_context_errors/01](_collect_data_context_errors/01/expected.json) | 单错误 | 1 |
| `_collect_undeclared_data_path_error` | 4800 | [_collect_undeclared_data_path_error/01](_collect_undeclared_data_path_error/01/expected.json) | 单错误 | 1 |
| `_collect_data_type_error` | 4824 | [_collect_data_type_error/01](_collect_data_type_error/01/expected.json) | 单错误 | 1 |

## 逻辑上无法隔离的伴随错误样例

以下3个目标条件在当前校验逻辑中会必然满足另一条错误条件，单靠调整输入无法构造单错误样例。
若要求它们独立触发，需要修改生产校验规则的条件或去重/合并错误。

### _collect_adjacent_display_unit_errors，源码第 765 行

- component value_row: large primary Text steps binds non-numeric field /data/healthSport/calorieText and must occupy its own row; do not append unit as a unit or label.
- component steps: fontSize 30 requires a pure number/integer or a supported primary value. A directly bound measurement with a declared unit may use 20/24fp in a full-width area or 2x4 large panel when its text budget fits; ordinary names, dates, times, and statuses remain at most 18fp.

### _collect_two_by_four_action_backboard_errors，源码第 1322 行

- 2x4 large backboard weatherZone must place its action as the final direct child.
- 2x4 large backboard weatherZone content must be a Column.

### _collect_two_by_four_w1_focus_aux_errors，源码第 2681 行

- 2x4 W1-focus-aux cell cell1 displays two dynamic facts in one Text. Use two single-line Text nodes, one fact per line, instead of joining them with '|'.
- 2x4 W1-focus-aux cell cell1 must place each of its two dynamic facts in a separate complete Text line. Do not put both labels on one line and both values on the other line.
