# Bootstrap

## Fresh Checkout Checklist

Source: repo-confirmed from README and source code, owner-confirmed where noted.

1. Open the repository root.
2. Confirm Python is available:

```powershell
python --version
```

Success signal: prints Python version. If PowerShell says `python` is not recognized, stop and report an environment blocker.

3. Confirm HDC sees devices:

```powershell
hdc list targets
```

Success signal: at least one target SN for device-backed pipeline runs. Empty output means device/emulator setup is incomplete.

4. Confirm DevEco paths exist, or pass overrides:

```powershell
python Automation\main.py batch --deveco-sdk-home "D:\DevEco Studio\sdk" --java-home "D:\DevEco Studio\jbr"
```

Use this as a run command only when devices and dependencies are ready.

5. Confirm query cases exist:

```powershell
Get-Content .\queries.jsonl
```

Expected format per line:

```json
{"qid": "weather_card_01", "query": "帮我生成一个天气预报卡片"}
```

## Dependencies

Owner-confirmed: a complete local dependency list exists.

Repo-observed: no root `requirements.txt` was found during this scan. Requirements files exist in nested packages, but do not assume they install the root automation project.

Rule: ask the owner for the canonical dependency file before running `pip install`.

## Environment Variables

Optional DevEco overrides:

```powershell
$env:DEVECO_SDK_HOME = "D:/DevEco Studio/sdk"
$env:JAVA_HOME = "D:/DevEco Studio/jbr"
```

Optional scoring variables:

```powershell
$env:AESTHETICS_BASE_URL = "<volcano-ark-url>"
$env:AESTHETICS_API_KEY = "<secret>"
$env:AESTHETICS_MODEL = "doubao-seed-2-0-lite"
```

Never write real secret values into repository files.

## First Useful Run

Smallest full pipeline run:

```powershell
python Automation\main.py one --query "测试" --qid "test"
```

Expected success signals:

- DSL file exists under `dsl/`.
- Screenshot exists under `output/`.
- Console prints `DSL=<path> SCREENSHOT=<path>`.
- If a device SN is used, `output/{safe_sn}/pipeline.log` has no fatal `ERROR`.

## Known Bootstrap Blocker

Observed during this run: `python` was not available in the current PowerShell environment. Since the owner chose `python` as the canonical validation command, future agents should not silently switch to `py`; they should report the missing command or ask the owner to update PATH.
