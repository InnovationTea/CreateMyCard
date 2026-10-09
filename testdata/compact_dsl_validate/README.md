# validate_compact_dsl 校验数据

范围按 compact_dsl_validator.py 中 153 个 errors.append 源码位置统计。这些位置由 validate_compact_dsl 及其检查函数执行；不把解析器异常和双动作校验的内部原因重复计数。

149 个位置有单错误样例；3 个位置因校验条件存在逻辑包含关系而必然伴随其他错误；1 个位置不可从公开入口触发。152 个可触发位置都通过完整 validate_compact_dsl 入口验证，并用执行跟踪确认实际命中目标 errors.append。

按检查函数分目录，每组包含 sample_compact.dsl、sample_task_spec.json、sample_card_spec.json。expected.json 仅记录预期错误、异常类型和输入文件校验和；coverage.json 记录完整的 153 个源码错误点及其样例目录。

## 使用

在项目根目录运行：

```powershell
D:\ProgramFiles\anaconda3\envs\CreateMyCard\python.exe testdata\compact_dsl_validate\verify_cases.py
```

脚本直接调用完整校验入口，核对异常类型、完整错误列表和文件校验和。修改样例或校验器后如回放失败，需要重新核对 expected.json。

## 验证记录

逐组完整入口回放：153 通过、0 失败。新回放脚本 Ruff 通过，git diff --check 通过。
收集项目测试输入时执行相关 7 个测试文件：408 通过、6 失败。失败来自当前工作区原有测试预期与校验器不一致：1 个模板空容器被解析器提前拦截、3 个格式化读数目前被接受、2 个 W9 样例直接显示布尔字段。此次仅新增数据与回放脚本，未修改生产代码。

## 逐错误位置索引

| 检查函数 | 源码行 | 样例目录 | 状态 | 实际错误数 |
| --- | ---: | --- | --- | ---: |
| `_collect_asset_source_errors` | 292 | [_collect_asset_source_errors/01](_collect_asset_source_errors/01/expected.json) | 单错误 | 1 |
| `_collect_asset_color_errors` | 334 | [_collect_asset_color_errors/01](_collect_asset_color_errors/01/expected.json) | 单错误 | 1 |
| `_collect_hero_value_errors` | 393 | [_collect_hero_value_errors/01](_collect_hero_value_errors/01/expected.json) | 单错误 | 1 |
| `_collect_hero_value_errors` | 408 | [_collect_hero_value_errors/03](_collect_hero_value_errors/03/expected.json) | 单错误 | 1 |
| `_collect_hero_value_errors` | 427 | [_collect_hero_value_errors/02](_collect_hero_value_errors/02/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_weather_date_errors` | 463 | [_collect_two_by_two_weather_date_errors/01](_collect_two_by_two_weather_date_errors/01/expected.json) | 单错误 | 1 |
| `_collect_adjacent_display_unit_errors` | 765 | [_collect_adjacent_display_unit_errors/02](_collect_adjacent_display_unit_errors/02/expected.json) | 伴随错误 | 2 |
| `_collect_adjacent_display_unit_errors` | 827 | [_collect_adjacent_display_unit_errors/03](_collect_adjacent_display_unit_errors/03/expected.json) | 单错误 | 1 |
| `_collect_adjacent_display_unit_errors` | 838 | [_collect_adjacent_display_unit_errors/01](_collect_adjacent_display_unit_errors/01/expected.json) | 单错误 | 1 |
| `_collect_mixed_font_row_alignment_errors` | 1132 | [_collect_mixed_font_row_alignment_errors/01](_collect_mixed_font_row_alignment_errors/01/expected.json) | 单错误 | 1 |
| `_collect_mixed_font_row_alignment_errors` | 1156 | [_collect_mixed_font_row_alignment_errors/02](_collect_mixed_font_row_alignment_errors/02/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_small_backboard_errors` | 1205 | [_collect_two_by_four_small_backboard_errors/01](_collect_two_by_four_small_backboard_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_small_backboard_errors` | 1216 | [_collect_two_by_four_small_backboard_errors/03](_collect_two_by_four_small_backboard_errors/03/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_small_backboard_errors` | 1223 | [_collect_two_by_four_small_backboard_errors/02](_collect_two_by_four_small_backboard_errors/02/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_small_backboard_errors` | 1229 | [_collect_two_by_four_small_backboard_errors/04](_collect_two_by_four_small_backboard_errors/04/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_action_backboard_errors` | 1322 | [_collect_two_by_four_action_backboard_errors/01](_collect_two_by_four_action_backboard_errors/01/expected.json) | 伴随错误 | 2 |
| `_collect_two_by_four_action_backboard_errors` | 1330 | [_collect_two_by_four_action_backboard_errors/02](_collect_two_by_four_action_backboard_errors/02/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_action_backboard_errors` | 1339 | [_collect_two_by_four_action_backboard_errors/03](_collect_two_by_four_action_backboard_errors/03/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_action_backboard_errors` | 1346 | [_collect_two_by_four_action_backboard_errors/04](_collect_two_by_four_action_backboard_errors/04/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_action_backboard_errors` | 1351 | [_collect_two_by_four_action_backboard_errors/05](_collect_two_by_four_action_backboard_errors/05/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_action_backboard_errors` | 1356 | [_collect_two_by_four_action_backboard_errors/06](_collect_two_by_four_action_backboard_errors/06/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_action_row_errors` | 1376 | [_collect_two_by_four_action_row_errors/01](_collect_two_by_four_action_row_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_narrow_graphical_action_errors` | 1425 | [_collect_two_by_two_narrow_graphical_action_errors/01](_collect_two_by_two_narrow_graphical_action_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_full_width_action_errors` | 1456 | [_collect_two_by_four_full_width_action_errors/01](_collect_two_by_four_full_width_action_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_full_width_action_errors` | 1466 | [_collect_two_by_four_full_width_action_errors/02](_collect_two_by_four_full_width_action_errors/02/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_full_width_action_errors` | 1475 | [_collect_two_by_four_full_width_action_errors/03](_collect_two_by_four_full_width_action_errors/03/expected.json) | 单错误 | 1 |
| `_collect_raw_boolean_text_errors` | 1566 | [_collect_raw_boolean_text_errors/01](_collect_raw_boolean_text_errors/01/expected.json) | 单错误 | 1 |
| `_collect_progress_value_errors` | 1592 | [_collect_progress_value_errors/01](_collect_progress_value_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_density_errors` | 1731 | [_collect_two_by_four_w9_density_errors/01](_collect_two_by_four_w9_density_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_density_errors` | 1738 | [_collect_two_by_four_w9_density_errors/02](_collect_two_by_four_w9_density_errors/02/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_density_errors` | 1744 | [_collect_two_by_four_w9_density_errors/03](_collect_two_by_four_w9_density_errors/03/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_content_errors` | 1816 | [_collect_two_by_four_w9_content_errors/04](_collect_two_by_four_w9_content_errors/04/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_content_errors` | 1844 | [_collect_two_by_four_w9_content_errors/05](_collect_two_by_four_w9_content_errors/05/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_content_errors` | 1853 | [_collect_two_by_four_w9_content_errors/06](_collect_two_by_four_w9_content_errors/06/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_content_errors` | 1877 | [_collect_two_by_four_w9_content_errors/08](_collect_two_by_four_w9_content_errors/08/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_content_errors` | 1896 | [_collect_two_by_four_w9_content_errors/09](_collect_two_by_four_w9_content_errors/09/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_content_errors` | 1901 | [_collect_two_by_four_w9_content_errors/07](_collect_two_by_four_w9_content_errors/07/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_content_errors` | 1921 | [_collect_two_by_four_w9_content_errors/10](_collect_two_by_four_w9_content_errors/10/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_content_errors` | 1947 | [_collect_two_by_four_w9_content_errors/14](_collect_two_by_four_w9_content_errors/14/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_content_errors` | 1957 | [_collect_two_by_four_w9_content_errors/13](_collect_two_by_four_w9_content_errors/13/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_content_errors` | 1962 | [_collect_two_by_four_w9_content_errors/11](_collect_two_by_four_w9_content_errors/11/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_content_errors` | 1971 | [_collect_two_by_four_w9_content_errors/12](_collect_two_by_four_w9_content_errors/12/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_content_errors` | 1978 | [_collect_two_by_four_w9_content_errors/01](_collect_two_by_four_w9_content_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_content_errors` | 1983 | [_collect_two_by_four_w9_content_errors/02](_collect_two_by_four_w9_content_errors/02/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_content_errors` | 2011 | [_collect_two_by_four_w9_content_errors/03](_collect_two_by_four_w9_content_errors/03/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_s4_text_errors` | 2034 | [_collect_two_by_two_s4_text_errors/01](_collect_two_by_two_s4_text_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_s4_text_errors` | 2041 | [_collect_two_by_two_s4_text_errors/03](_collect_two_by_two_s4_text_errors/03/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_s4_text_errors` | 2058 | [_collect_two_by_two_s4_text_errors/04](_collect_two_by_two_s4_text_errors/04/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_s4_text_errors` | 2071 | [_collect_two_by_two_s4_text_errors/05](_collect_two_by_two_s4_text_errors/05/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_s4_text_errors` | 2089 | [_collect_two_by_two_s4_text_errors/06](_collect_two_by_two_s4_text_errors/06/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_s4_text_errors` | 2101 | [_collect_two_by_two_s4_text_errors/02](_collect_two_by_two_s4_text_errors/02/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_s4_vertical_alignment_errors` | 2132 | [_collect_two_by_two_s4_vertical_alignment_errors/02](_collect_two_by_two_s4_vertical_alignment_errors/02/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_s4_vertical_alignment_errors` | 2149 | [_collect_two_by_two_s4_vertical_alignment_errors/01](_collect_two_by_two_s4_vertical_alignment_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_ring_group_alignment_errors` | 2193 | [_collect_two_by_two_ring_group_alignment_errors/01](_collect_two_by_two_ring_group_alignment_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_s4_palette_errors` | 2237 | [_collect_two_by_two_s4_palette_errors/01](_collect_two_by_two_s4_palette_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_aux_icon_errors` | 2328 | [_collect_two_by_four_aux_icon_errors/01](_collect_two_by_four_aux_icon_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_alignment_errors` | 2394 | [_collect_two_by_four_w1_focus_alignment_errors/01](_collect_two_by_four_w1_focus_alignment_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_alignment_errors` | 2403 | [_collect_two_by_four_w1_focus_alignment_errors/02](_collect_two_by_four_w1_focus_alignment_errors/02/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_alignment_errors` | 2410 | [_collect_two_by_four_w1_focus_alignment_errors/03](_collect_two_by_four_w1_focus_alignment_errors/03/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_alignment_errors` | 2432 | [_collect_two_by_four_w1_focus_alignment_errors/04](_collect_two_by_four_w1_focus_alignment_errors/04/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_alignment_errors` | 2439 | [_collect_two_by_four_w1_focus_alignment_errors/05](_collect_two_by_four_w1_focus_alignment_errors/05/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_aux_errors` | 2471 | [_collect_two_by_four_w1_focus_aux_errors/01](_collect_two_by_four_w1_focus_aux_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_aux_errors` | 2493 | [_collect_two_by_four_w1_focus_aux_errors/02](_collect_two_by_four_w1_focus_aux_errors/02/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_aux_errors` | 2506 | [_collect_two_by_four_w1_focus_aux_errors/03](_collect_two_by_four_w1_focus_aux_errors/03/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_aux_errors` | 2512 | [_collect_two_by_four_w1_focus_aux_errors/04](_collect_two_by_four_w1_focus_aux_errors/04/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_aux_errors` | 2528 | [_collect_two_by_four_w1_focus_aux_errors/05](_collect_two_by_four_w1_focus_aux_errors/05/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_aux_errors` | 2543 | [_collect_two_by_four_w1_focus_aux_errors/07](_collect_two_by_four_w1_focus_aux_errors/07/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_aux_errors` | 2573 | [_collect_two_by_four_w1_focus_aux_errors/08](_collect_two_by_four_w1_focus_aux_errors/08/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_aux_errors` | 2611 | [_collect_two_by_four_w1_focus_aux_errors/06](_collect_two_by_four_w1_focus_aux_errors/06/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_aux_errors` | 2643 | [_collect_two_by_four_w1_focus_aux_errors/09](_collect_two_by_four_w1_focus_aux_errors/09/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_aux_errors` | 2653 | [_collect_two_by_four_w1_focus_aux_errors/10](_collect_two_by_four_w1_focus_aux_errors/10/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_aux_errors` | 2675 | [_collect_two_by_four_w1_focus_aux_errors/11](_collect_two_by_four_w1_focus_aux_errors/11/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_aux_errors` | 2681 | [_collect_two_by_four_w1_focus_aux_errors/12](_collect_two_by_four_w1_focus_aux_errors/12/expected.json) | 伴随错误 | 2 |
| `_collect_two_by_four_w1_focus_aux_errors` | 2694 | [_collect_two_by_four_w1_focus_aux_errors/15](_collect_two_by_four_w1_focus_aux_errors/15/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_aux_errors` | 2704 | [_collect_two_by_four_w1_focus_aux_errors/13](_collect_two_by_four_w1_focus_aux_errors/13/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w1_focus_aux_errors` | 2724 | [_collect_two_by_four_w1_focus_aux_errors/14](_collect_two_by_four_w1_focus_aux_errors/14/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_weather_triplet_errors` | 2759 | [_collect_two_by_four_w9_weather_triplet_errors/01](_collect_two_by_four_w9_weather_triplet_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_weather_triplet_errors` | 2768 | [_collect_two_by_four_w9_weather_triplet_errors/02](_collect_two_by_four_w9_weather_triplet_errors/02/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_weather_triplet_errors` | 2776 | [_collect_two_by_four_w9_weather_triplet_errors/03](_collect_two_by_four_w9_weather_triplet_errors/03/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_weather_triplet_errors` | 2783 | [_collect_two_by_four_w9_weather_triplet_errors/04](_collect_two_by_four_w9_weather_triplet_errors/04/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_weather_triplet_errors` | 2789 | [_collect_two_by_four_w9_weather_triplet_errors/05](_collect_two_by_four_w9_weather_triplet_errors/05/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_centered_hero_errors` | 3133 | [_collect_two_by_two_centered_hero_errors/01](_collect_two_by_two_centered_hero_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_centered_hero_errors` | 3141 | [_collect_two_by_two_centered_hero_errors/02](_collect_two_by_two_centered_hero_errors/02/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_centered_hero_errors` | 3153 | [_collect_two_by_two_centered_hero_errors/05](_collect_two_by_two_centered_hero_errors/05/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_centered_hero_errors` | 3158 | [_collect_two_by_two_centered_hero_errors/06](_collect_two_by_two_centered_hero_errors/06/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_centered_hero_errors` | 3180 | [_collect_two_by_two_centered_hero_errors/03](_collect_two_by_two_centered_hero_errors/03/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_centered_hero_errors` | 3197 | [_collect_two_by_two_centered_hero_errors/04](_collect_two_by_two_centered_hero_errors/04/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_content_density_errors` | 3268 | [_collect_two_by_two_content_density_errors/02](_collect_two_by_two_content_density_errors/02/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_content_density_errors` | 3275 | [_collect_two_by_two_content_density_errors/03](_collect_two_by_two_content_density_errors/03/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_content_density_errors` | 3281 | [_collect_two_by_two_content_density_errors/04](_collect_two_by_two_content_density_errors/04/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_content_density_errors` | 3298 | [_collect_two_by_two_content_density_errors/01](_collect_two_by_two_content_density_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_two_content_density_errors` | 3312 | [_collect_two_by_two_content_density_errors/05](_collect_two_by_two_content_density_errors/05/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_detached_unit_errors` | 3380 | [_collect_two_by_four_detached_unit_errors/01](_collect_two_by_four_detached_unit_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_weather_calendar_alignment_errors` | 3421 | [_collect_two_by_four_weather_calendar_alignment_errors/01](_collect_two_by_four_weather_calendar_alignment_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_countdown_backboard_errors` | 3457 | [_collect_two_by_four_countdown_backboard_errors/01](_collect_two_by_four_countdown_backboard_errors/01/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_countdown_backboard_errors` | 3471 | [_collect_two_by_four_countdown_backboard_errors/02](_collect_two_by_four_countdown_backboard_errors/02/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_countdown_backboard_errors` | 3481 | [_collect_two_by_four_countdown_backboard_errors/03](_collect_two_by_four_countdown_backboard_errors/03/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_countdown_backboard_errors` | 3490 | [_collect_two_by_four_countdown_backboard_errors/04](_collect_two_by_four_countdown_backboard_errors/04/expected.json) | 单错误 | 1 |
| `_collect_layout_route_errors` | 3597 | [_collect_layout_route_errors/05](_collect_layout_route_errors/05/expected.json) | 单错误 | 1 |
| `_collect_layout_route_errors` | 3616 | [_collect_layout_route_errors/10](_collect_layout_route_errors/10/expected.json) | 单错误 | 1 |
| `_collect_layout_route_errors` | 3628 | [_collect_layout_route_errors/06](_collect_layout_route_errors/06/expected.json) | 单错误 | 1 |
| `_collect_layout_route_errors` | 3636 | [_collect_layout_route_errors/11](_collect_layout_route_errors/11/expected.json) | 单错误 | 1 |
| `_collect_layout_route_errors` | 3662 | [_collect_layout_route_errors/02](_collect_layout_route_errors/02/expected.json) | 单错误 | 1 |
| `_collect_layout_route_errors` | 3676 | [_collect_layout_route_errors/07](_collect_layout_route_errors/07/expected.json) | 单错误 | 1 |
| `_collect_layout_route_errors` | 3687 | [_collect_layout_route_errors/08](_collect_layout_route_errors/08/expected.json) | 单错误 | 1 |
| `_collect_layout_route_errors` | 3700 | [_collect_layout_route_errors/03](_collect_layout_route_errors/03/expected.json) | 单错误 | 1 |
| `_collect_layout_route_errors` | 3745 | [_collect_layout_route_errors/09](_collect_layout_route_errors/09/expected.json) | 单错误 | 1 |
| `_collect_layout_route_errors` | 3753 | [_collect_layout_route_errors/04](_collect_layout_route_errors/04/expected.json) | 单错误 | 1 |
| `_collect_layout_route_errors` | 3771 | [_collect_layout_route_errors/01](_collect_layout_route_errors/01/expected.json) | 单错误 | 1 |
| `_collect_2x2_countdown_group_errors` | 3802 | [_collect_2x2_countdown_group_errors/01](_collect_2x2_countdown_group_errors/01/expected.json) | 单错误 | 1 |
| `_collect_2x2_countdown_group_errors` | 3836 | [_collect_2x2_countdown_group_errors/04](_collect_2x2_countdown_group_errors/04/expected.json) | 单错误 | 1 |
| `_collect_2x2_countdown_group_errors` | 3844 | [_collect_2x2_countdown_group_errors/05](_collect_2x2_countdown_group_errors/05/expected.json) | 单错误 | 1 |
| `_collect_2x2_countdown_group_errors` | 3852 | [_collect_2x2_countdown_group_errors/06](_collect_2x2_countdown_group_errors/06/expected.json) | 单错误 | 1 |
| `_collect_2x2_countdown_group_errors` | 3858 | [_collect_2x2_countdown_group_errors/07](_collect_2x2_countdown_group_errors/07/expected.json) | 单错误 | 1 |
| `_collect_2x2_countdown_group_errors` | 3862 | [_collect_2x2_countdown_group_errors/08](_collect_2x2_countdown_group_errors/08/expected.json) | 单错误 | 1 |
| `_collect_2x2_countdown_group_errors` | 3871 | [_collect_2x2_countdown_group_errors/02](_collect_2x2_countdown_group_errors/02/expected.json) | 单错误 | 1 |
| `_collect_2x2_countdown_group_errors` | 3881 | [_collect_2x2_countdown_group_errors/03](_collect_2x2_countdown_group_errors/03/expected.json) | 单错误 | 1 |
| `_collect_two_by_four_w9_sparse_layout_errors` | 3911 | [_collect_two_by_four_w9_sparse_layout_errors/01](_collect_two_by_four_w9_sparse_layout_errors/01/expected.json) | 单错误 | 1 |
| `_collect_fusion_composition_errors` | 4032 | [_collect_fusion_composition_errors/01](_collect_fusion_composition_errors/01/expected.json) | 单错误 | 1 |
| `_collect_semantic_text_errors` | 4118 | [_collect_semantic_text_errors/01](_collect_semantic_text_errors/01/expected.json) | 单错误 | 1 |
| `_collect_semantic_text_errors` | 4141 | [_collect_semantic_text_errors/02](_collect_semantic_text_errors/02/expected.json) | 单错误 | 1 |
| `_collect_semantic_text_errors` | 4155 | [_collect_semantic_text_errors/03](_collect_semantic_text_errors/03/expected.json) | 单错误 | 1 |
| `_collect_semantic_text_errors` | 4165 | [_collect_semantic_text_errors/04](_collect_semantic_text_errors/04/expected.json) | 单错误 | 1 |
| `_collect_unbound_action_hint_errors` | 4209 | [_collect_unbound_action_hint_errors/01](_collect_unbound_action_hint_errors/01/expected.json) | 单错误 | 1 |
| `_collect_ambiguous_metric_text_errors` | 4287 | [_collect_ambiguous_metric_text_errors/01](_collect_ambiguous_metric_text_errors/01/expected.json) | 单错误 | 1 |
| `_collect_component_contract_errors` | 4304 | [_collect_component_contract_errors/01](_collect_component_contract_errors/01/expected.json) | 单错误 | 1 |
| `_collect_component_contract_errors` | 4308 | [_collect_component_contract_errors/02](_collect_component_contract_errors/02/expected.json) | 单错误 | 1 |
| `_collect_component_parent_errors` | 4326 | [_collect_component_parent_errors/02](_collect_component_parent_errors/02/expected.json) | 入口不可触发：解析器去重 | 0 |
| `_collect_component_parent_errors` | 4338 | [_collect_component_parent_errors/01](_collect_component_parent_errors/01/expected.json) | 单错误 | 1 |
| `_collect_container_errors` | 4353 | [_collect_container_errors/01](_collect_container_errors/01/expected.json) | 单错误 | 1 |
| `_collect_height_budget_errors` | 4385 | [_collect_height_budget_errors/01](_collect_height_budget_errors/01/expected.json) | 单错误 | 1 |
| `_collect_action_unit_errors` | 4529 | [_collect_action_unit_errors/01](_collect_action_unit_errors/01/expected.json) | 单错误 | 1 |
| `_collect_action_unit_errors` | 4534 | [_collect_action_unit_errors/02](_collect_action_unit_errors/02/expected.json) | 单错误 | 1 |
| `_collect_action_unit_errors` | 4536 | [_collect_action_unit_errors/03](_collect_action_unit_errors/03/expected.json) | 单错误 | 1 |
| `_collect_action_unit_errors` | 4545 | [_collect_action_unit_errors/05](_collect_action_unit_errors/05/expected.json) | 单错误 | 1 |
| `_collect_action_unit_errors` | 4556 | [_collect_action_unit_errors/04](_collect_action_unit_errors/04/expected.json) | 单错误 | 1 |
| `_collect_required_non_empty_string` | 4566 | [_collect_required_non_empty_string/01](_collect_required_non_empty_string/01/expected.json) | 单错误 | 1 |
| `_collect_on_click_errors` | 4579 | [_collect_on_click_errors/01](_collect_on_click_errors/01/expected.json) | 单错误 | 1 |
| `_collect_on_click_errors` | 4583 | [_collect_on_click_errors/02](_collect_on_click_errors/02/expected.json) | 单错误 | 1 |
| `_collect_on_click_errors` | 4586 | [_collect_on_click_errors/03](_collect_on_click_errors/03/expected.json) | 单错误 | 1 |
| `_collect_on_click_errors` | 4591 | [_collect_on_click_errors/04](_collect_on_click_errors/04/expected.json) | 单错误 | 1 |
| `_collect_on_click_errors` | 4594 | [_collect_on_click_errors/05](_collect_on_click_errors/05/expected.json) | 单错误 | 1 |
| `_collect_on_click_errors` | 4597 | [_collect_on_click_errors/06](_collect_on_click_errors/06/expected.json) | 单错误 | 1 |
| `_collect_expression_context` | 4685 | [_collect_expression_context/01](_collect_expression_context/01/expected.json) | 单错误 | 1 |
| `_collect_expression_context` | 4694 | [_collect_expression_context/02](_collect_expression_context/02/expected.json) | 单错误 | 1 |
| `_collect_expression_context` | 4703 | [_collect_expression_context/04](_collect_expression_context/04/expected.json) | 单错误 | 1 |
| `_collect_expression_context` | 4710 | [_collect_expression_context/03](_collect_expression_context/03/expected.json) | 单错误 | 1 |
| `_collect_expression_context` | 4714 | [_collect_expression_context/05](_collect_expression_context/05/expected.json) | 单错误 | 1 |
| `_collect_path_binding` | 4764 | [_collect_path_binding/01](_collect_path_binding/01/expected.json) | 单错误 | 1 |
| `_collect_data_context_errors` | 4778 | [_collect_data_context_errors/02](_collect_data_context_errors/02/expected.json) | 单错误 | 1 |
| `_collect_data_context_errors` | 4782 | [_collect_data_context_errors/01](_collect_data_context_errors/01/expected.json) | 单错误 | 1 |
| `_collect_undeclared_data_path_error` | 4802 | [_collect_undeclared_data_path_error/01](_collect_undeclared_data_path_error/01/expected.json) | 单错误 | 1 |
| `_collect_data_type_error` | 4826 | [_collect_data_type_error/01](_collect_data_type_error/01/expected.json) | 单错误 | 1 |

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
