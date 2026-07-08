# Change Recipes

## Add Or Change A CLI Argument

Files:

- `Automation/main.py`
- `Automation/automation/config.py` if automation behavior changes
- `visual_aesthetics/config.py` if scoring behavior changes
- `README.md`
- `agents.d/01-commands.md`

Checks:

```powershell
python -m py_compile Automation\main.py
python Automation\main.py --help
```

Review notes: keep root parser and subparser defaults consistent.

## Fix Current Pipeline Runtime Risks

Files:

- `Automation/automation/pipeline.py`
- `Automation/automation/arkts.py`
- `Automation/automation/hdc.py`
- `Automation/automation/xiaoyi.py`
- `Automation/automation/logger.py`

Checks:

```powershell
python -m py_compile Automation\main.py Automation\automation\pipeline.py Automation\automation\arkts.py Automation\automation\hdc.py Automation\automation\xiaoyi.py
```

Then run the smallest device-backed command only when HDC/DevEco/device are ready:

```powershell
python Automation\main.py one --query "测试" --qid "test"
```

Review notes: do not hide exceptions without preserving enough context for `output/{SN}/pipeline.log`.

## Change DSL Extraction

Files:

- `Automation/automation/xiaoyi.py`
- `Automation/automation/dsl.py`
- `Automation/automation/ui_tree.py`
- `queries.jsonl` only when adding test cases

Checks:

```powershell
python -m py_compile Automation\automation\xiaoyi.py Automation\automation\dsl.py Automation\automation\ui_tree.py
python Automation\main.py one --query "测试" --qid "test"
```

Review notes: preserve retry/scroll fallback behavior and duplicate DSL fingerprint protection.

## Change ArkTS Render Or Install

Files:

- `Automation/automation/arkts.py`
- `Automation/automation/config.py`
- `Automation/automation/hdc.py`

Checks:

```powershell
python -m py_compile Automation\automation\arkts.py Automation\automation\hdc.py
python Automation\main.py one-from-file --qid <known-qid>
```

Review notes: do not edit `ArkTs/` without approval. Confirm render writes generated `sample.jsonl` into `Automation/.work/.../ArkTs`, not the source template.

## Change Aesthetic Scoring

Files:

- `visual_aesthetics/config.py`
- `visual_aesthetics/judge.py`
- `visual_aesthetics/models/`
- `visual_aesthetics/reports/`
- `agents.d/04-scoring-rules.md` if scoring rubric changes

Checks:

```powershell
python -m py_compile visual_aesthetics\config.py visual_aesthetics\judge.py
python Automation\main.py aesthetics --input .\output --output .\output
```

Review notes: ask before running real API scoring if credentials or paid quota are involved.

## Update Runbooks

Files:

- `AGENTS.md`
- Relevant `agents.d/*.md`
- `CLAUDE.md` when platform entry point changes

Checks:

- Confirm no secret values were written.
- Confirm source labels are present for owner-confirmed or repo-observed facts.
- Run fresh-agent dry run: bootstrap, tool selection, development loop, debug, risk, and handoff.
