# Risk Areas

## Protected Template Risk

`ArkTs/` is the source template for rendering. Do not modify it without explicit owner approval.

Risk governance update: `AutomationConfig.arkts_dir` now always points to a working copy under `Automation/.work/ArkTs` or `Automation/.work/devices/{safe_sn}/ArkTs`. The template should be read as source input only. During the next device-backed render, confirm `sample.jsonl` is written under `.work`, not under `ArkTs/`.

## Device And HDC Risk

HDC commands can affect connected devices by sending input, installing apps, force-stopping apps, and capturing screenshots. Run them only for requested pipeline/debug work. Use `hdc list targets` as the safe discovery command.

## Build And Install Risk

The ArkTS flow runs hvigor, pushes a signed HAP, installs it with `bm install`, and starts an ability. Risks include SDK/JDK mismatch, signing failure, device storage, and package conflicts. Ask before uninstalling packages or performing disruptive device cleanup.

## Secrets And Cost Risk

Aesthetic scoring may use paid/network API calls and requires API credentials. Do not store keys in the repository. Ask before running scoring when credentials or quota are involved.

## Generated Artifact Risk

Generated directories are ignored:

- `dsl/`
- `output/`
- `Automation/.work/`

Do not commit screenshots, reports, logs, caches, zips, or generated DSL unless the owner explicitly requests a fixture and confirms it is safe.

## Runtime Verification Risk

The previously observed Python runtime risks have been remediated in code and py-compile now passes. Treat the pipeline behavior as unverified until `hdc list targets` shows a connected device and the smallest behavior run passes.

## Documentation Drift Risk

The root README, `Automation/README.md`, source code, and older runbook files have drifted. Prefer source code for exact CLI flags and current artifact paths; record conflicts in handoff. Scoring rules are owner-confirmed to follow `aesthetic-v4-vlm-judge-package-20260624`.

## Dependency Risk

Owner confirmed a complete local dependency list exists, but no root dependency file was found in this scan. Do not install from nested package requirement files unless the owner confirms they are canonical for this project.
