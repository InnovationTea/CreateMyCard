# A2UI Render Runner

该工程用于在 HarmonyOS 模拟器或真机上批量渲染 A2UI 样本，并通过 HDC 获取整屏截图和容器裁剪图。App 每个批次只构建、安装一次；每个样本通过应用沙箱动态推送，不需要重新编译 HAP。

本目录是 Debug Tools 自带的独立运行依赖。正常使用由 `device_debug` 共享 Render Session 调用，无需配置
外部工程路径；独立脚本仅用于排障和真机链路验收。固定 HAR 及校验值见 `DEPENDENCIES.md`，本地工具链、
签名材料、依赖目录和构建产物不得提交。

## 运行批处理

```powershell
.\scripts\run-a2ui-batch.ps1 `
  -SamplesDir D:\samples `
  -OutputDir D:\a2ui-output `
  -Width 150 `
  -Height 150 `
  -TargetType Emulator
```

可选参数：

- `-DeviceId`：存在多个 HDC 目标时指定目标 ID。
- `-TargetType Auto|Emulator|Device`：默认自动识别。网络连接或无法可靠识别的目标必须显式指定。
- `-TimeoutSeconds`：每个样本等待终态的秒数，默认 20。
- `-HdcPath`：无法自动发现 DevEco SDK 时显式指定 `hdc.exe`。

模拟器可以安装构建产生的 unsigned debug HAP。真机只接受 signed HAP；如果工程没有配置调试签名，脚本会在处理样本前退出并给出错误。不要将证书、Profile、密码或其他签名材料提交到工程。

输出目录包含：

- `screens/`：HDC 获取的整屏 PNG。
- `crops/`：根据 App 返回的物理像素边界裁剪出的 A2UI 容器 PNG。
- `results.jsonl`：逐样本状态、错误、警告和耗时。
- `summary.json`：本批次成功、警告、失败数量。

脚本退出码为 `0`（全部成功或仅有警告）、`1`（存在样本失败或超时）、`2`（设备、构建、签名或安装失败）。

## 手动执行单个样本

App 必须是已启动的 debug 应用，HDC 才能通过 `-b` 写入应用沙箱：

```powershell
hdc shell aa start -a EntryAbility -b com.example.myapplication -m entry
hdc shell -b com.example.myapplication mkdir -p data/storage/el2/base/files/a2ui
hdc file send -b com.example.myapplication .\sample.json data/storage/el2/base/files/a2ui/current.json
hdc shell aa start -a EntryAbility -b com.example.myapplication -m entry `
  --ps runId manual-001 `
  --ps sampleFile current.json `
  --pi width 300 `
  --pi height 150
hdc hilog -x -T A2UIRunner -e manual-001 -v wrap
```

终态为 `READY`、`READY_WITH_WARNINGS` 或 `FAILED`。`READY` 日志中的 `cropPx` 是相对物理屏幕的裁剪矩形。直接点击启动 App 时，会在默认 `150×150vp` 容器中加载 `resources/rawfile/test.json`。

## 图片素材

本工程的 `entry/src/main/resources/base/media/` 按微服务能力清单同步，源图片来自仓库根目录 `resources/`。
在仓库根目录运行 `.\.venv\Scripts\python.exe debug_tools/scripts/sync_assets.py --sync`，
再运行相同脚本的 `--check`，同时核对浏览器共享素材和本工程文件的 SHA-256。
登记的 141 张素材原样复制，保留原始路径和大小写，不删除清单外的工程图标。
更新资源后重新执行截图会重新构建并安装 HAP；历史截图不会自动更新。
