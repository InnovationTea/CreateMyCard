# Debug Playbook

## Remediated Code Risks Pending Verification

Source: repo-observed risks remediated during risk governance. `python --version` now reports Python 3.12.10 and py-compile passes; device-backed validation remains blocked while `hdc list targets` returns `[Empty]`.

Observed CLI validation:

- `python Automation\main.py --help` passes.
- `python Automation\main.py one --help`, `one-from-file --help`, `batch --help`, `parallel --help`, and `aesthetics --help` pass.
- `aesthetics` single-image JSON output path writes a structured failure result when API config is missing.
- `one`, `one-from-file`, and `batch` now fail early with a clear no-device message when HDC has no targets.
- `parallel --devices auto` fails clearly with no HDC devices.

| Area | Previous risk | Governance change | Remaining verification |
| --- | --- | --- | --- |
| `Automation/automation/arkts.py` | `self._log` used without initialization. | Wired `get_logger("arkts", ...)` in `ArkTsRunner`. | Render-backed run with a connected HDC device. |
| `Automation/automation/hdc.py` | Screenshot retry path used `self._log.warning` without initialization. | Added optional logger injection and default logger fallback in `HdcClient`. | Force or observe screenshot retry path. |
| `Automation/automation/xiaoyi.py` | `self._log` and `t0` were undefined. | Wired `get_logger("xiaoyi", ...)` and initialized `t0` at collection start. | Single-query run through DSL extraction. |
| `Automation/automation/xiaoyi.py` | Send-button `RuntimeError` appeared outside the `if not send` block. | Moved raise into the missing-send branch so normal flow can click send. | Single-query run that locates and clicks send. |
| `Automation/automation/pipeline.py` | Undefined `t0`, `dsl_fail`, `build_fail`, and non-Python `"=".repeat(60)`. | Rebuilt batch summary with initialized counters, valid Python string repeat, and render failure logging. | Small batch run with a connected HDC device. |
| `Automation/automation/config.py` | No-SN render path could write to protected `ArkTs/`. | `arkts_dir` now always points to `Automation/.work/.../ArkTs`; `ArkTs/` remains source template only. | Confirm generated rawfile is under `.work` during a render run. |

Verified command:

```powershell
python -m py_compile Automation\main.py Automation\automation\pipeline.py Automation\automation\arkts.py Automation\automation\hdc.py Automation\automation\xiaoyi.py
```

Remaining behavior check:

```powershell
hdc list targets
python Automation\main.py one --query "test" --qid "test"
```

## Environment Symptoms

| Symptom | Diagnostic | Recovery |
| --- | --- | --- |
| `python` not recognized | `python --version` | Stop and report PATH/Python installation blocker. Owner chose `python` as canonical command. |
| No HDC devices | `hdc list targets` | Verify USB debugging/emulator, reconnect device, or ask owner before restarting HDC service. |
| DevEco path missing | Check `D:\DevEco Studio\sdk` and `D:\DevEco Studio\jbr` | Pass `--deveco-sdk-home` and `--java-home`, or set environment variables. |
| Dependency import failure | Run the failing command and capture missing module | Ask owner for canonical local dependency list before installing. |

## Pipeline Symptoms

| Symptom | Diagnostic | Recovery |
| --- | --- | --- |
| Xiaoyi chat UI not ready | Inspect timeout from `wait_ready`; rerun with larger `--reply-timeout` only if device/app is expected to be slow. | Confirm Xiaoyi is open, device awake, and UI tree can be dumped. |
| Text input not found | Check `_ensure_input` path and UI tree dump under work dir. | Verify keyboard toggle/input locator rules in `ui_tree.py`. |
| Send button not found | Inspect `send_query` and UI tree control names. | Fix locator or update UI tree control mapping; then single-query test. |
| DSL not found | Check `query-max-attempts`, `query-attempt-timeout`, scroll fallback, and latest UI tree. | Increase timeout only when slow response is expected; otherwise inspect DSL keywords/extractor. |
| Build fails | Inspect hvigor stdout/stderr and `Automation/.work/devices/{SN}/ArkTs/build` or `Automation/.work/ArkTs/build`. | Verify DevEco SDK/JDK, signing, storage, and ArkTS template health. |
| HAP install fails | Check `bm install` output and bundle name. | Verify device storage/compatibility; ask before uninstalling existing packages unless user requested. |
| Screenshot too small/missing | Inspect `snapshot_display` command result and file size. | Increase `--screenshot-retries` or `--screenshot-write-wait`; verify app rendered. |
| Scoring API fails | Check `scores.jsonl` result error and console output. | Verify endpoint/key/model access externally; optionally increase timeout/retries. |

## Logs And Artifacts

- Pipeline log: `output/{safe_sn}/pipeline.log` for SN runs, or `output/pipeline.log` for no-SN runs.
- DSL output: `dsl/` or `dsl/{safe_sn}/`.
- Screenshots: `output/` or `output/{safe_sn}/`.
- ArkTS working copy: `Automation/.work/ArkTs` or `Automation/.work/devices/{safe_sn}/ArkTs`.
- Temporary UI tree/work files: `Automation/.work/`.

Do not commit generated debug artifacts.
