# Review Handoff

## Required Evidence

Every agent handoff should include:

- Files changed and the reason for each group.
- Source labels for new runbook facts: repo-confirmed, owner-confirmed, observed during run, risk judgment, or unknown.
- Commands run and concise result summary.
- Commands skipped and exact blocker.
- Generated artifacts inspected or intentionally not generated.
- Remaining risks, especially device/API/DevEco/Python environment blockers.

## Verification Checklist

For docs-only changes:

- Run or attempt `python --version`.
- Manually inspect Markdown for stale commands, wrong paths, and secret values.
- Run fresh-agent dry run for affected slices.

For Python changes:

```powershell
python -m py_compile Automation\main.py Automation\automation\pipeline.py Automation\automation\arkts.py Automation\automation\hdc.py Automation\automation\xiaoyi.py
```

For behavior changes, add the smallest relevant command:

```powershell
python Automation\main.py one --query "测试" --qid "test"
```

For scoring changes:

```powershell
python Automation\main.py aesthetics --input .\output --output .\output
```

## Reviewer Focus Areas

- `ArkTs/` was not modified without approval.
- No secrets or real API keys were added.
- Generated artifacts are not staged.
- Multi-device outputs remain isolated by safe SN.
- CLI docs match `Automation/main.py`.
- Current code risks in `agents.d/debug-playbook.md` are either fixed or explicitly carried as risks.
- Skipped checks are explained with concrete blockers.

## Done Criteria

A change is ready for human review when:

- The smallest relevant verification command has passed, or the blocker is documented.
- The agent can point to expected success signals.
- Any generated DSL/screenshots/reports are ignored by git and not committed.
- Remaining questions are listed in the final response instead of hidden in prose.
