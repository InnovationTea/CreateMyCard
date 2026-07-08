# Command Reference

Source: repo-confirmed from `Automation/main.py` and root `README.md`.

Run commands from the repository root. Use `python`, not `py`, as the canonical command name.

## Common Arguments

| Argument | Default | Use |
| --- | --- | --- |
| `--project-root` | repository root | Override project root. |
| `--hdc` | `hdc` | Override HDC executable. |
| `--sn` | none | Target one device SN. |
| `--ready-timeout` | `60` | Wait for Xiaoyi chat UI readiness. |
| `--extract-delay` | `30` | Delay used around DSL extraction. |
| `--reply-timeout` | `120` | Timeout waiting for Xiaoyi readiness/reply behavior. |
| `--post-query-wait` | `30` | Wait after sending query before extraction loop. |
| `--query-attempt-timeout` | `90` | Per-attempt query timeout. |
| `--query-max-attempts` | `3` | Retry count for DSL collection. |
| `--build-timeout` | `300` | HAP build/install timeout. |
| `--render-wait` | `5` | Wait after app start before screenshot. |
| `--deveco-sdk-home` | `D:/DevEco Studio/sdk` | DevEco SDK path. |
| `--java-home` | `D:/DevEco Studio/jbr` | DevEco JDK path. |
| `--bundle-name` | `yyx.test.test` | HarmonyOS bundle name. |
| `--ability-name` | `EntryAbility` | Ability to start. |
| `--module-name` | `entry` | ArkTS module name. |
| `--screenshot-min-bytes` | `1000` | Minimum valid screenshot size. |
| `--screenshot-retries` | `3` | Screenshot retry count. |
| `--screenshot-write-wait` | `1` | Wait for remote screenshot write. |
| `--debug` | off | Enable debug logging where implemented. |

## Aesthetic Arguments

| Argument | Default | Use |
| --- | --- | --- |
| `--enable-aesthetics` | off | Score screenshots after pipeline runs. |
| `--aesthetics-base-url` | none | Volcano Ark/Doubao API endpoint. |
| `--aesthetics-api-key` | none | API key. Do not commit. |
| `--aesthetics-model` | `doubao-seed-2-0-lite` | Scoring model. |
| `--aesthetics-output-mode` | `full` | `full` or `score-only`. |
| `--aesthetics-timeout` | `360` | API timeout in seconds. |
| `--aesthetics-max-retries` | `3` | API retry count. |
| `--aesthetics-max-tokens` | `1200` | Max model output tokens. |
| `--aesthetics-temperature` | `0.0` | Model temperature. |
| `--aesthetics-disable-cache` | true by parser default | Keeps cache disabled; omit only if code/config changes enable caching. |
| `--aesthetics-max-workers` | `2` | Scoring concurrency. |
| `--aesthetics-fail-fast` | off | Stop pipeline when scoring fails. |

## Subcommands

### `one`

Use for one manual query.

```powershell
python Automation\main.py one --qid test_weather --query "帮我生成一个天气预报卡片"
```

Success signal: command prints DSL and screenshot paths; files exist under `dsl/` and `output/`.

### `one-from-file`

Use to reproduce one query from `queries.jsonl`.

```powershell
python Automation\main.py one-from-file --qid q1
```

Optional: `--queries <path>`.

### `batch`

Use for all queries in a query file on one selected/default device.

```powershell
python Automation\main.py batch
```

Optional: `--queries <path>`.

### `parallel`

Use when multiple connected devices should each run the full batch.

```powershell
python Automation\main.py parallel --devices auto
python Automation\main.py parallel --devices "SN1,SN2" --max-workers 2
```

Success signal: each device reports completion or isolated failure; outputs are separated by safe SN.

### `aesthetics`

Use to score existing screenshots without running Xiaoyi/ArkTS.

```powershell
python Automation\main.py aesthetics --input .\output --output .\output
```

Success signal: `scores.jsonl` and, unless `--skip-report` is set, `report.html`.

## Verification Commands

```powershell
python --version
python -m py_compile Automation\main.py Automation\automation\pipeline.py Automation\automation\arkts.py Automation\automation\hdc.py Automation\automation\xiaoyi.py
```

If `python` is missing, stop and report the environment blocker.
