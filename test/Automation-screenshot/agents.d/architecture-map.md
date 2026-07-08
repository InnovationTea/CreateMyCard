# Architecture Map

## End-To-End Data Flow

```text
queries.jsonl or CLI query
  -> Automation/main.py
  -> AutomationPipeline
  -> XiaoyiClient collects DSL through HDC UI tree/input
  -> DslExtractor saves JSON/JSONL artifact
  -> ArkTsRunner copies DSL into ArkTS rawfile
  -> hvigor builds signed HAP
  -> HDC installs/starts app
  -> HDC captures screenshot
  -> VisualAestheticsJudge optionally scores screenshots
  -> scores.jsonl/report.html
```

## Entry Points

- `Automation/main.py`: argparse setup, common arguments, subcommands, parallel dispatch, standalone scoring.
- `Automation/automation/pipeline.py`: `run_one` and `run_batch` orchestration.
- `visual_aesthetics/judge.py`: scoring interface used by CLI and pipeline.

## Module Boundaries

| Area | Files | Boundary |
| --- | --- | --- |
| CLI/config | `Automation/main.py`, `Automation/automation/config.py`, `visual_aesthetics/config.py` | Add new flags here and keep README/runbook synced. |
| Device control | `Automation/automation/hdc.py` | HDC command construction, target selection, screenshots. |
| Xiaoyi interaction | `Automation/automation/xiaoyi.py`, `ui_tree.py` | UI readiness, input/send controls, reply state, scroll fallback. |
| DSL | `Automation/automation/dsl.py` | Extraction, validation/repair, JSONL save. |
| ArkTS render | `Automation/automation/arkts.py`, `ArkTs/` | Build/install/start screenshot path. Do not edit `ArkTs/` without approval. |
| Scoring | `visual_aesthetics/` | API calls, cache, score schema, report generation. |
| Documentation | `AGENTS.md`, `agents.d/`, `CLAUDE.md`, `README.md` | Keep command and risk facts consistent with source code. |

## Files That Change Together

- CLI argument changes: `Automation/main.py`, relevant config dataclass, README, `agents.d/01-commands.md`.
- Output path changes: `Automation/automation/config.py`, README output section, `AGENTS.md`, risk/debug docs.
- Scoring behavior changes: `visual_aesthetics/config.py`, `visual_aesthetics/judge.py`, `agents.d/04-scoring-rules.md`, CLI docs.
- HDC or screenshot changes: `Automation/automation/hdc.py`, `Automation/automation/arkts.py`, debug playbook.
- Xiaoyi control changes: `xiaoyi.py`, `ui_tree.py`, DSL extraction tests or manual single-query validation.

## Generated And Protected Boundaries

- Generated: `dsl/`, `output/`, `Automation/.work/`.
- Protected template: `ArkTs/`.
- Multi-device working copy: `Automation/.work/devices/{safe_sn}/ArkTs`.

Risk governance update: `AutomationConfig.arkts_dir` now always points to a working copy under `Automation/.work/`. Treat `ArkTs/` as a source template only.
