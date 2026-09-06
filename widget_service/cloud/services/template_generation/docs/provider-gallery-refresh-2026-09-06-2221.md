# Provider 画廊重新生成与端侧同步（2026-09-06 22:26）

## 本轮结果

保留用户最新模板、配置及其它工作区修改，使用当前源文件重新执行全量真实 HTTP 生成，
没有复用上一轮 A2UI。没有修改模板、业务代码或测试断言，也未提交或推送 PR。

- 模板来源：`/Users/yansf/workspace/GenerateUI/.codex-worktrees/provider-gallery-two-support-20260906`。
- 模型：`deepseek_http / deepseek-v4-flash`，mock=false、fallback=false。
- 输入版本：`11.7.5.206`；只保留高版本外观，双业务段落使用非融球布局。
- 完整场景：121 项，107 成功、0 失败、14 个既有缺失占位。
- 原子预览：96 个，85 个 2x2、11 个 2x4，其中 17 个 Support。
- 端侧显示清单：87 项，77 成功、0 失败、10 个缺失占位。
- 双业务按每组一张显示：17 组，15 成功、2 个未注册能力占位。
  0/1/2 操作的完整矩阵保留在云侧自动化产物中。

## 文件及用途

| 文件或目录 | 用途 |
| --- | --- |
| [输入 manifest](../test/provider_gallery_20260906_2221_tT9WIN_inputs/manifest.json) 及同目录请求文件 | 从当前模板重建全量模拟请求 |
| [输出 manifest](../test/provider_gallery_20260906_2221_tT9WIN_output/manifest.json) 及同目录 107 份 A2UI | 全量 HTTP 实际生成结果，所有成功用例均为本轮新生成 |
| `test/provider_gallery_20260906_2221_tT9WIN_preview/` | 不调用模型的 96 个原子模板编译预览 |
| `docs/provider-gallery-refresh-2026-09-06-2221.md` | 本轮文件用途、测试结果和设备证据 |
| 端侧 `entry/src/main/resources/rawfile/provider_scenario_gallery/manifest.json` | 每组一张的端侧展示清单 |
| 同一端侧目录中的 77 份 A2UI | 由同步脚本从本轮成功用例复制；其中 14 份内容相对安装前发生变化 |
| 端侧 `entry/build/default/outputs/default/entry-default-signed.hap` | 重新构建并安装的签名应用包 |

端侧工程绝对路径：`/Users/yansf/workspace/GenerateUI/genui_evaluation`。

相对上次生成的源文件哈希快照，本轮实际内容变化覆盖电量、耳机、日程、天气和
活动/心率/睡眠/运动记录的 8 个模板文件。倒计时文件修改时间更新，但内容哈希未变化。
生成前后共 79 份源配置与模板文件哈希一致，生成期间没有观察到并发改动。

## 验证结果与限制

- 107 份成功 A2UI：JSON 可解析、三条 v0.9 消息、组件 ID 唯一、child 引用存在。
- 59 个 Image 引用全部在正式素材注册表及端侧 media 中存在；未发现天气温度计资源。
- 45 个成功双业务场景的 90 个槽位：等权 Row、39 个业务图标及 0/1/2 操作分配检查通过。
- 端侧同步测试：12 项通过，用时 0.30 秒。
- 同步的 77 份 A2UI 与源文件逐字节一致；17 个双业务显示分组唯一；没有孤立旧 JSON。
- HAP 内 78 个画廊 JSON 与端侧源资源逐字节一致，无多余画廊 JSON。
- `build_cardplan_bundle.py --check`、云侧及端侧画廊资源的 `git diff --check` 通过。
- 本轮未修改 Python 源码，因此未新增 Ruff 检查范围。
- 全量模板测试：657 项，653 通过、4 失败，83.15 秒；不能描述为全量测试通过。

四项失败逐项记录：

1. `test_provider_component_markers.py::test_charging_summary_guards_every_optional_status[names2]`：
   已知基线问题，断言期待 3 个 Text，模板实际为 2 个。
2. `test_template_generation.py::test_form_validator_allows_empty_stack_children_but_rejects_empty_column_children`：
   已知空 Stack 校验兼容性问题。
3. `test_template_generation.py::test_business_artwork_and_monochrome_icons_keep_explicit_color_policies`：
   本轮用户样式修改已给图标指定 `supportContentColor`，旧断言仍要求没有 `fillColor`。
4. `test_template_generation.py::test_new_support_templates_follow_two_line_contract[ScheduleOverviewTimeSupport@1-params0]`：
   本轮日程主文字调整为 14，旧断言仍要求 16。

后两项与本轮用户模板样式调整有关，不是既有两项基线失败；本次仅执行重新生成/同步，
保留用户模板和测试现状，没有回改样式或放宽断言。正式 HTTP 生成与结构、资源、操作校验均通过。

## 构建与安装

使用 DevEco 自带 Java 21.0.8 和 SDK 执行 `assembleHap --no-daemon`，
不执行 clean；构建成功，3.905 秒，存在既有 ArkTS 警告。

签名包：

`/Users/yansf/workspace/GenerateUI/genui_evaluation/entry/build/default/outputs/default/entry-default-signed.hap`

- 大小：7,123,185 字节。
- SHA-256：`94636f95fd1fafcc917dd22c4e33f0ab0442952f668598225587bcf60a2b863b`。
- 设备：`3AX0224A14000098`，USB Connected；安装前只读探测成功。
- 应用：`com.example.genuievaluation`，版本 1.0.0 / 1000000。
- `install -r` 返回 `install bundle successfully`，退出码 0。
- 安装后 updateTime：`1788704735104`。
- `aa start -a EntryAbility -b com.example.genuievaluation` 返回启动成功；PID `50949`。
- 按 HDC 操作与设备自验技能分别验证目标、安装、启动及新截图；未卸载、重启或执行卡片业务事件。
- 已进入“双业务段落”画廊，实机显示成功 15、异常 2，与两个未注册能力占位一致；
  电量、日程与天气的新样式可见。仍存在既有 Surface 2001 / schemaWarning 提示，
  本轮未定位该提示，未执行逐卡业务点击，不能据此宣称全量交互验收通过。

## 可恢复备份及日志

证据目录：`/tmp/provider-gallery-20260906-2221-tT9WIN/`。

- `provider_scenario_gallery_before/`：同步前完整画廊。
- `entry-default-signed-before.hap`：构建前 HAP。
- `http.log`、`tests.log`、`preview.log`、`build.log`、`install.log`。
- `source-sha256.json`：本轮源配置与模板哈希快照。
- `verify_gallery.rb`：本轮结构、素材和双业务操作分配检查脚本。
- `launch.jpeg`：安装后应用首页截图。
- `support-final.jpeg`：本轮安装后的双业务段落完整加载截图。

只替换指定画廊生成资源目录，旧文件可通过上述备份恢复；未改动端侧页面、HAR、素材和其它工作区文件。

## PR256 提交前复核

用户确认显示验证 OK 后，本次提交保留已验收模板样式，并将模板、配套配置、规则、测试及验证记录
一并更新到 PR256。提交范围为 `template_generation/` 内 43 个文件，不包含原工作区的 HTTP
客户端、传输/路由、环境配置和对应服务测试，也不包含独立端侧仓库的资源与 HAP。

- 本次重跑全量模板测试：657 项，653 通过、4 失败，85.91 秒；失败项与上文完全一致。
- 13 个修改或新增的 Python 文件 Ruff 全部通过；5 个修改的 JSON 配置均可解析。
- Bundle `--check` 和暂存差异空白检查通过；79 份模板/配置与上述生成快照的 SHA-256 一致。
- 本次未重新生成或安装 HAP，采用上文已安装并由用户确认的版本；未把显示验收等同于自动化全绿。
- 提交前发现协议文档 Registry 总数仍为 103，修正为 105（96 业务 + 7 布局 + 2 动作）；
  同时修正画廊场景计数说明的空格，不改变模板和运行时实现。
- 本次测试日志：`/tmp/provider-gallery-pr256-tests-20260906.log`。
