# Safety And Permission Rules

## Source Labels

- Repo-confirmed: `.gitignore`, `Automation/automation/config.py`, and CLI source.
- Owner-confirmed: approval boundaries and `python` as the canonical validation command.
- Risk judgment: device, secret, and template-protection rules.

## Hard Rules

1. Do not modify `ArkTs/` directly without explicit owner approval.
2. Do not hardcode API keys, passwords, access tokens, endpoint secrets, or private account identifiers.
3. Do not commit generated files from `dsl/`, `output/`, `Automation/.work/`, logs, archives, or Python caches.
4. Do not run destructive cleanup outside generated directories without approval.
5. Do not push git changes without approval.
6. Do not claim pipeline readiness when the current environment cannot run `python` or when validation was skipped.

## Permission Matrix

| Action | Safety level | Rule |
| --- | --- | --- |
| Read project files | Autonomous | Stay inside repository root unless user asks otherwise. |
| Run `python --version` | Autonomous | Report if missing. |
| Run `hdc list targets` | Autonomous | Non-mutating device check. |
| Run pipeline commands | Autonomous when environment is ready | Generates ignored artifacts under `dsl/`, `output/`, and `Automation/.work/`. |
| Run scoring with API key | Ask first unless user supplied task requires it | Never expose or store key. |
| Install dependencies | Ask first | Owner says a complete local dependency list exists; ask for the canonical file. |
| Modify `Automation/` or `visual_aesthetics/` code | Ask first if the task is only runbook work; otherwise follow user request | Keep changes scoped. |
| Modify `ArkTs/` | Ask first, explicit approval required | Treat template as protected. |
| Delete generated artifacts | Ask first unless user requests cleanup | Never delete outside generated directories without approval. |
| Git commit/push | Ask first | Follow user's exact git request. |

## Isolation Invariants

- Device-specific outputs use `safe_sn` from `Automation/automation/config.py`.
- DSL path with SN: `dsl/{safe_sn}/{safe_sn}_{qid}.jsonl`.
- Screenshot path with SN: `output/{safe_sn}/{safe_sn}_{qid}.jpeg`.
- Multi-device ArkTS workspace: `Automation/.work/devices/{safe_sn}/ArkTs`.
- Single-device/no-SN mode now uses `Automation/.work/ArkTs`; SN mode uses `Automation/.work/devices/{safe_sn}/ArkTs`. Treat `ArkTs/` as a source template only.

## Secret Handling

- Accept API keys only through CLI arguments, environment variables, or the user's active shell.
- Do not write real keys into docs, code, `.env`, logs, or reports.
- `visual_aesthetics/.env` is ignored by git, but do not create or modify it unless asked.

## Escalation Triggers

Stop and ask when:

- The dependency source is unclear.
- A fix requires changing `ArkTs/`.
- HDC/device recovery would disrupt a user's active device session.
- A command requires network, paid API calls, credentials, or external services not already supplied.
- Repo evidence conflicts with owner instructions or README behavior.
