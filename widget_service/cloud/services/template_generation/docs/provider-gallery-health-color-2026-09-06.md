# 画廊重新生成、运动健康图标颜色刷新与安装（2026-09-06 21:54）

## 交付结果与范围

本轮先按用户的最新模板重建全量画廊，期间用户再次调整运动健康图标颜色，
后续模型调用缩小为运动健康单业务及所有包含该业务的双业务组合。

- 最新运动健康 HTTP 生成：40 / 40 成功，0 失败、0 缺失；其中单业务 19 项，双业务操作矩阵 21 项。
- 端侧运动健康相关显示：19 张单业务卡片、7 组双业务卡片；每组只展示一张。
- 完整交付清单：121 项，107 成功、0 失败、14 个既有缺失占位。
- 端侧去重显示清单：87 项，77 成功、0 失败、10 个既有缺失占位；双业务段落 17 组，
  15 组成功、2 组能力未注册占位。
- 77 份 A2UI 和 1 份 manifest 已同步、打包，并覆盖安装到 USB 设备；
  没有修改端侧页面、HAR 或业务事件实现。未提交代码、未推送 PR。

本轮最新颜色来自用户修改的：

- `resources/source/providers/health-sport/templates/activity-overview.cardtpl`：
  活动 Support 图标使用 `supportContentColor`。
- `resources/source/providers/health-sport/templates/workout-overview.cardtpl`：
  运动记录 Support 图标使用 `supportContentColor`。

这两个模板由用户编辑，本轮保留原样并重新生成；最终 15 个自动化槽位的图标均编译为
`#991F4595`，没有残留模板颜色引用。生成前后 79 份源配置/模板文件哈希一致，
确认本轮运动健康产物包含最后一次已保存的修改。

## 本轮补齐文件

以下路径相对于 `template_generation/`。这些修正发生在用户要求全量重新生成阶段，
没有回改用户模板样式。

| 文件 | 用途 |
| --- | --- |
| `resources/source/providers/battery/provider.json` | 对齐数值电量必选声明，更新 32vp 环描述；带单位文本保持可选 |
| `resources/source/providers/battery/layer-docs/first-layer.md` | 明确数值电量和充电状态必需，文本不能替代数值绑定 |
| `resources/source/providers/battery/layer-docs/second-layer.md` | 同步 32vp 电量环、12vp 内部图标和数据要求 |
| `resources/source/providers/earphone/provider.json` | 耳机盒 Support 环尺寸描述由 44vp 更新为 32vp |
| `resources/source/providers/earphone/layer-docs/second-layer.md` | 同步耳机盒 32vp 环使用说明 |
| `docs/provider-template-capability-checklist.md` | 同步电量 Support 字段覆盖与 32vp 尺寸 |
| `docs/provider-template-contract.md` | 明确 Support 可使用 32～44vp 电量环 |
| `docs/provider-template-e2e-gallery.md` | 同步数值电量必选和 32vp 环检查说明 |
| `tests/test_template_preview_dataset.py` | 更新电量 Support 预览元数据断言 |
| `tests/test_support_template_refresh.py` | 缺少必选数值绑定应失败；数值绑定存在时使用 32vp 环 |
| `tests/test_template_generation.py` | 按用户日程样式校验 4vp 间距、16/14 字号与自适应行高 |
| `docs/provider-gallery-health-color-2026-09-06.md` | 本轮生成、同步、构建和设备验证记录 |

临时选择/合并脚本位于 `/tmp/provider-gallery-rebuild-20260906-pMau4S/refresh_health.py`；
仅调用现有生成器、筛选本轮范围并按完整用例复制验证通过的产物，没有手工改写 A2UI 内容。

## 产物与来源

- 最新运动健康输出：
  [40 项清单](../test/provider_gallery_output_health_color_20260906_pMau4S/manifest.json)。
- 最终合并交付输出：
  [121 项清单](../test/provider_gallery_output_rebuild_20260906_pMau4S_delivery/manifest.json)。
- 最新原子模板预览：
  `test/template_preview_health_color_20260906_pMau4S/`，96 个：
  85 个 2x2、11 个 2x4，其中 17 个 Support。
- 端侧目录：
  `/Users/yansf/workspace/GenerateUI/genui_evaluation/entry/src/main/resources/rawfile/provider_scenario_gallery/`。

合并规则：

1. 以本轮全量 HTTP 成功输出
   `test/provider_gallery_output_rebuild_20260906_pMau4S_verified/` 为基线。
2. 使用最新的 40 项运动健康输出替换同 caseId 项。
3. 全量生成中发现天气 Hero 随机选择了端侧未包含的温度计，且不符合此前天气状态图标要求。
   用户随后要求只刷新运动健康，因此没有继续扩大天气代码修改；该 **1 项天气 Hero**
   保留此前 `test/provider_gallery_output_refresh_verified_20260906/` 中的完整有效用例及文件，
   没有发布本轮不合适的结果。其它业务保留本轮已验证产物。
4. 同步脚本仍按每组双操作代表去重展示；0/1/2 操作完整矩阵仅留在云侧自动化结果中。

天气 Hero 的可选图标约束仍是后续待补齐项，不能把复用有效产物视为该生成问题已经修复。
两个已知全量测试基线问题同样未作顺带修复。

## 实际验证

- 电量/预览针对性测试：28 项通过。
- 日程样式针对性测试：2 项通过。
- 全量模板子系统回归：657 项，655 通过、2 个已知基线失败。
  这是运动健康最后一次颜色调整之前的完整回归。
- 最新颜色调整后相关回归：71 项通过，覆盖 Support、原子预览、素材语义、对比度和 Planner。
- 端侧同步脚本：12 项通过。
- 本轮修改的 3 份 Python 测试文件 Ruff 通过；
  `build_cardplan_bundle.py --check`、云侧与端侧资源 `git diff --check` 均通过。
- 最新运动健康真实 HTTP 请求：40 项全部成功，关闭 mock 和 fallback，
  模型 `deepseek-v4-flash`，输入版本 `11.7.5.206`。
- 完整交付的 107 份 A2UI：JSON、三条 v0.9 消息、组件 ID 唯一性及 child 引用检查通过。
- 60 个 Image 引用均在正式素材注册表及端侧 media 中存在。
- 45 个成功双业务自动化场景的 90 个槽位：等权 Row、业务独立素材及 0/1/2 操作分配检查通过；
  39 个双业务图标引用、6 个 32vp 电量环、15 个最新运动图标颜色检查通过。
- 同步后 77 份 A2UI 与来源逐字节一致；双业务显示组无重复；总共 78 个 JSON，没有遗留孤立文件。
- 签名 HAP 内 78 个画廊 JSON 再次逐字节比对通过，没有多余旧画廊 JSON。

全量回归的两项已知失败：

1. `test_provider_component_markers.py::test_charging_summary_guards_every_optional_status[names2]`：
   既有断言期待 3 个 Text，而当前模板为 2 个。
2. `test_template_generation.py::test_form_validator_allows_empty_stack_children_but_rejects_empty_column_children`：
   已知空 Stack 兼容性断言失败。

初次重建还暴露电量必选声明与配置不一致，导致模板注册表无法加载；对齐配置后已恢复。
日程旧字号/间距断言也已按用户模板更新。失败产物留在独立诊断目录，没有同步到端侧。

## HAP 与设备证据

使用 DevEco 自带 Java 21.0.8、SDK 执行 `assembleHap --no-daemon`，未执行 clean。
构建成功，用时 4.037 秒；既有 ArkTS 警告未扩展整改。

签名文件：

`/Users/yansf/workspace/GenerateUI/genui_evaluation/entry/build/default/outputs/default/entry-default-signed.hap`

- 大小：7,123,188 字节。
- SHA-256：`b87371820511fe67045876d95cfbecd406e2d90b562928d04014e2d41576383a`。
- 目标设备：`3AX0224A14000098`，USB Connected；安装前只读探测成功。
- 包名：`com.example.genuievaluation`，版本 1.0.0 / 1000000。
- `install -r` 返回 `install bundle successfully`，退出码 0。
- 安装后 updateTime：`1788702838692`。
- 启动 `EntryAbility` 返回成功，进程 PID：`36097`。
- 按 HDC 操作与设备自验规范，设备目标、安装、启动和新截图分别验证；未卸载、重启或执行卡片业务事件。
- 已进入“Provider 场景画廊 → 运动健康”，实机显示“成功 19、异常 0”，可见活动与心率卡片。
  双业务段落页面显示“成功 15、异常 2”，与清单中的两个未注册能力占位一致。
  页面仍有既有 Surface 2001 / schemaWarning 提示；本轮未定位该提示，也未逐张执行业务交互，
  不据此宣称全量视觉或交互验收完成。

本轮日志、截图及可恢复备份：

`/tmp/provider-gallery-rebuild-20260906-pMau4S/`

- `build.log`、`install.log`、`health-http.log`、`health-tests.log`。
- `tests-final.log`：655 通过 / 2 个基线失败的全量回归。
- `launch.jpeg`：安装后应用首页。
- `health-gallery.jpeg`：本轮安装后的运动健康画廊截图。
- `two-support.jpeg`：本轮安装后的双业务段落画廊截图。
- `support-colors.jpeg`：活动、心率、睡眠等双业务卡片实机截图，活动图标已使用辅助内容色。
- `provider_scenario_gallery_before/`：同步前完整画廊备份。
- `entry-default-signed-before.hap`：构建前签名 HAP 备份。

只替换了指定生成资源目录中的旧产物，可从上述备份恢复；端侧原有页面、HAR 及其它脏工作区改动均保留。
