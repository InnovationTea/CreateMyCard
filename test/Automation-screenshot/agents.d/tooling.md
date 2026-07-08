# Tooling Inventory

## Approved Skills

| Skill | Use when | Required inputs | Expected output | Safety level |
| --- | --- | --- | --- | --- |
| `agent-runbook-distiller` | Updating `AGENTS.md`, `agents.d/`, platform files, or durable project onboarding knowledge. | Target root and owner knowledge. | Updated runbooks with source labels and fresh-agent dry run. | Autonomous for scan/read; ask before install/code changes. |

## Project CLI

| Tool | Path | Use when | Command | Success signal | Safety level |
| --- | --- | --- | --- | --- | --- |
| Automation CLI | `Automation/main.py` | Running Xiaoyi DSL extraction, ArkTS render, screenshot, scoring, or reports. | `python Automation\main.py <subcommand>` | Printed paths, generated artifacts, reports. | Autonomous when environment ready. |
| HDC | external executable `hdc` | Device discovery, UI dumps, input, file transfer, install/start, screenshots. | `hdc list targets` for discovery. | Device SN list. | Non-mutating discovery autonomous; disruptive actions only as part of requested pipeline. |
| DevEco/Hvigor | `ArkTs/hvigorw*` or PATH fallback | Building signed HAP. | Invoked by `Automation/automation/arkts.py`. | Signed HAP under ArkTS build output. | Run only through pipeline unless debugging build. |
| Aesthetic judge | `visual_aesthetics/judge.py` via CLI | Scoring existing screenshots or pipeline outputs. | `python Automation\main.py aesthetics --input <path> --output <path>` | `scores.jsonl`, `report.html`. | Ask before paid/API/secret-bearing runs. |

## Internal Modules

| Module | Purpose | Notes |
| --- | --- | --- |
| `Automation/automation/config.py` | Paths, timeouts, artifact naming, safe SN isolation. | Source of truth for generated output paths. |
| `Automation/automation/hdc.py` | HDC wrapper and screenshot retry logic. | Logger injection has been wired; still needs Python/device verification. |
| `Automation/automation/xiaoyi.py` | Xiaoyi UI readiness, query send, DSL wait/extract. | Send-button and timing risks have been remediated; still needs single-query verification. |
| `Automation/automation/dsl.py` | DSL extraction, repair, save. | Read before changing DSL parsing. |
| `Automation/automation/arkts.py` | Copy DSL to rawfile, build HAP, install/start app, screenshot. | Logger and working-copy isolation have been wired; still needs render verification. |
| `Automation/automation/pipeline.py` | Orchestrates one/batch pipeline and optional scoring. | Batch summary counters and failure logging have been remediated; still needs Python verification. |
| `visual_aesthetics/` | Doubao scoring, cache, model adapter, report generation. | Do not hardcode API keys. |

## Dependency Tooling

Owner-confirmed: a complete local dependency list exists.

Rule: ask for the canonical dependency list before installing. Nested requirement files under `Aesthetic-test/` and `aesthetic-v4-vlm-judge-package-20260624/` are not automatically the root project dependency source.

## Platform Files

- `AGENTS.md`: portable entry point for Codex/OpenCode-style agents.
- `CLAUDE.md`: generated concise Claude Code entry point.
- No project-local `.opencode/` or `GEMINI.md` was generated in this pass.
