# 手机电量非融球配色

手机电量的非融球场景使用独立主题 `battery-device-green`，复用现有蓝牙耳机浅绿配色。
颜色来源为 `resources/source/themes/audio-product-neutral-violet/theme.json`，不重新选色。

| 角色 | 颜色（`#AARRGGBB`） |
| --- | --- |
| 根背景 | `#FFF0FFE6`，纯色，无渐变 |
| 主文本、操作文本与操作图标 | `#FF52991F` |
| 辅助文本、环内业务图标 | `#9952991F` |
| 电量环进度 | `#FF52991F`，与耳机主题解析后的 `progressColor` 一致 |
| 进度轨道与操作背板 | `#3364BB5C` |

只变更手机电量的非融球主题路由及颜色，保留原有根布局参数、模板几何、数据绑定和事件。
新主题将 `allowTemplateActionBackgroundOverride` 设为 `false`，按钮直接使用主题背板，
不再按文字颜色重算底色。此内部主题字段默认 `true`，其它主题维持既有模板透明度覆盖规则；
电量 Hero 的源模板覆盖配置保留，避免改变融球按钮底色。
系统内存继续使用 `device-clean-blue-teal` 暖橙渐变，蓝牙耳机主题本身不改动。
融球仍使用 `fusion-battery-teal`；双业务 `TwoSupportLayout` 仍使用 `2x2-two-support`。
沿用当前模板主题的已审定浅色配置，不额外新增深色模式或运行时颜色切换。

自动化验证主题颜色与耳机一致、能力路由隔离，以及电量 Full 和充电 Hero 编译后的背景、
进度、文字及操作颜色；不将源码配色修改等同于画廊同步或设备安装。

## 维护文件

以下路径相对 `template_generation/`：

| 文件 | 用途 |
| --- | --- |
| `resources/source/themes/battery-device-green/theme.json` | 独立电量浅绿主题及按钮覆盖开关 |
| `resources/source/themes/battery-device-green/first-layer.md` | 电量主题适用范围 |
| `resources/source/themes/device-clean-blue-teal/theme.json` | 原暖橙主题仅保留系统内存能力 |
| `resources/source/themes/device-clean-blue-teal/first-layer.md` | 同步内存主题范围说明 |
| `resources/source/themes/README.md` | 登记新配色与按钮覆盖规则 |
| `engine/cardplan/models.py` | 声明兼容默认值的内部主题字段 |
| `engine/cardplan/compiler.py` | 根据主题开关选择按钮背板颜色 |
| `tests/test_battery_non_fusion_palette.py` | 颜色、路由、编译结果及融球字节一致性回归 |
| `tests/test_template_generation.py` | 更新主题清单及系统内存能力断言 |
| `docs/battery-non-fusion-palette.md` | 配色来源、边界与维护说明 |
