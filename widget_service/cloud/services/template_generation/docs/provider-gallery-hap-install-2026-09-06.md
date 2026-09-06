# Provider 画廊同步与 HAP 安装记录（2026-09-06）

## 结果

用户确认推送端侧并安装后，已将上一轮验证完成的 HTTP 画廊同步进端侧工程，构建签名 HAP，
覆盖安装到 USB 设备并成功启动。遵循 HDC 目标选择与设备验证规范，安装、启动、实机画面分别确认。

- 设备：`3AX0224A14000098`，USB Connected。
- 应用：`com.example.genuievaluation`，`EntryAbility`，版本 1.0.0 / 1000000。
- 端侧工程：`/Users/yansf/workspace/GenerateUI/genui_evaluation`。
- 源画廊：[provider_gallery_output_refresh_verified_20260906](../test/provider_gallery_output_refresh_verified_20260906/manifest.json)。
- 同步目录：端侧 `entry/src/main/resources/rawfile/provider_scenario_gallery/`；
  更新 77 份 A2UI 与 1 份 manifest，共 78 个 JSON，未修改端侧页面或 HAR。
- 显示清单：87 个展示项，77 成功、0 失败、10 个缺失占位；TwoSupport 每组只保留双操作代表，
  共 17 组，15 成功、2 个能力未注册占位。完整 0/1/2 操作矩阵仍保留在云侧自动化产物中。

## 检查与构建

1. `scripts/test_sync_provider_scenario_gallery.py`：12 项通过。
2. 77 份同步 A2UI 与源文件逐字节一致；32 个 Image 的素材均已存在于端侧 media 目录。
3. 显示分组唯一性通过；没有遗留的非代表 Support 场景文件。
4. 使用 DevEco 自带 Java 21.0.8 和 SDK 执行 `assembleHap --no-daemon`，不执行 clean；
   构建成功，用时约 4 秒，存在既有 ArkTS 警告。
5. 从签名 HAP 内直接读取并比对 78 个画廊 JSON，全部与端侧源资源相同，没有额外旧画廊 JSON。
6. 同步资源的 `git diff --check` 通过。

签名 HAP：

`/Users/yansf/workspace/GenerateUI/genui_evaluation/entry/build/default/outputs/default/entry-default-signed.hap`

- 大小：7,127,291 字节。
- SHA-256：`8a6aa9a231b301f7b222d211127188e5d3387529cc748635f4e8db9bc30ccbac`。

## 设备证据与范围

- `hdc -t 3AX0224A14000098 install -r <上述 HAP>` 返回 `install bundle successfully`，退出码 0。
- `bm dump` 中包名、版本匹配，updateTime 更新为 `1788700599879`。
- `aa start -a EntryAbility -b com.example.genuievaluation` 返回 `start ability successfully`；
  进程 PID 为 `19267`。
- 已读取本轮新截图，页面位于“Provider 场景画廊 → 双业务段落”，显示“成功 15，异常 2”，
  能看到新电量环、四种日程 Support 及对应日历图标。
- 页面还有 Surface 2001 / schemaWarning 提示；这不是画廊清单中的生成失败，本轮未定位或修改其原因。
  未逐张执行卡片业务点击，不能据此宣称全量交互或视觉验收通过。

本轮构建日志、截图及同步前备份保存在：

`/tmp/provider-gallery-hap-refresh-20260906-7vfZZQ/`

- `build.log`：构建日志。
- `launch.jpeg`：安装后应用启动截图。
- `provider_scenario_gallery_before/`：同步前完整画廊备份。
- `entry-default-signed-before.hap`：构建前签名 HAP 备份。

本轮只替换指定的生成资源目录并保留上述备份；端侧已有页面、HAR 和其它工作区改动均未回滚。
未提交代码、未推送 PR。
