# Development Loop

## Fast Checks

Run after documentation-only changes:

```powershell
python --version
```

If Python is unavailable, report the blocker and inspect changed Markdown manually.

Run after Python code changes:

```powershell
python -m py_compile Automation\main.py Automation\automation\pipeline.py Automation\automation\arkts.py Automation\automation\hdc.py Automation\automation\xiaoyi.py
```

Expected success signal: no output and exit code 0.

## Behavior Checks

Smallest full pipeline check:

```powershell
python Automation\main.py one --query "测试" --qid "test"
```

Expected success signal:

- `dsl/test.jsonl` or `dsl/{safe_sn}/{safe_sn}_test.jsonl`.
- `output/test.jpeg` or `output/{safe_sn}/{safe_sn}_test.jpeg`.
- No fatal error in console/log.

Single case from query file:

```powershell
python Automation\main.py one-from-file --qid q1
```

Batch:

```powershell
python Automation\main.py batch
```

Parallel:

```powershell
python Automation\main.py parallel --devices auto
```

Scoring only:

```powershell
python Automation\main.py aesthetics --input .\output --output .\output
```

Expected success signal: `scores.jsonl` and `report.html`, unless `--skip-report` is used.

## Slow Or External Checks

These require devices, DevEco, and sometimes paid/network API access:

- Full `batch` with real queries.
- `parallel` with multiple devices.
- Aesthetic scoring with real Doubao/Volcano Ark credentials.

Ask before running checks that consume paid API quota or require secrets.

## Current Verification Caveat

Observed during risk governance: `python --version` reports Python 3.12.10 and py-compile passes. Device-backed pipeline checks are still blocked while `hdc list targets` returns `[Empty]`.

Observed CLI checks:

- Root and subcommand help load successfully.
- `aesthetics` can write a JSON failure result for a single image when API configuration is missing.
- Device-backed commands currently stop at HDC preflight because no device is online.
