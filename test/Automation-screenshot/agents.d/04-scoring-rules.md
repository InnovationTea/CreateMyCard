# Aesthetic Scoring Rules

## Authoritative Source

Owner-confirmed: scoring must strictly follow `aesthetic-v4-vlm-judge-package-20260624`.

This repository's `visual_aesthetics/` module is a reuse/adaptation of that package. When scoring behavior, prompts, weights, report fields, acceptance logic, or terminology differ, treat `aesthetic-v4-vlm-judge-package-20260624` as the source of truth and update the adapted module or docs to match it.

Primary evidence to inspect before changing scoring:

- `aesthetic-v4-vlm-judge-package-20260624/docs/AESTHETIC_V4_WORKFLOW.md`
- `aesthetic-v4-vlm-judge-package-20260624/pipeline/scripts/*judge*.py`
- `aesthetic-v4-vlm-judge-package-20260624/pipeline/scripts/build_aesthetic_v4_report.py`
- `aesthetic-v4-vlm-judge-package-20260624/acceptance/DELIVERY_REVIEW.md`
- `visual_aesthetics/core/rubric.py`
- `visual_aesthetics/judge.py`

## Current aesthetic-v4 Rubric

The adapted implementation currently matches the aesthetic-v4 six-axis weighting in `visual_aesthetics/core/rubric.py`.

| Axis id | Display name | Weight |
| --- | --- | --- |
| `visual_impact_originality` | visual impact / originality | 30% |
| `composition_hierarchy` | composition / hierarchy | 20% |
| `typography` | typography | 15% |
| `color_material` | color / material | 15% |
| `detail_finish` | detail / finish | 15% |
| `basic_usability` | basic usability | 5% |

Score scale:

- Axis scores use a 0-8 scale.
- Final score is converted to 0-100.
- Prompt/profile naming should remain aligned with `aesthetic-v4`.

## Deprecated Legacy Rubric

The older five-axis runbook rubric is deprecated and must not be used for new scoring work:

| Deprecated axis | Deprecated weight |
| --- | --- |
| basic usability as primary category | 25% |
| visual consistency | 20% |
| information hierarchy | 20% |
| interaction reasonability | 15% |
| originality and design sense | 20% |

Do not reintroduce this five-axis rubric unless the owner explicitly asks to create a separate scoring profile.

## Agent Rules

1. Before changing scoring, inspect the aesthetic-v4 package files listed above.
2. Keep `visual_aesthetics/core/rubric.py` aligned with the aesthetic-v4 package.
3. If README, old runbooks, or comments conflict with aesthetic-v4, update the docs; do not change scoring to match stale docs.
4. Preserve the six-axis weights unless the owner explicitly changes the aesthetic-v4 source profile.
5. Never include real API keys in examples, configs, reports, or committed artifacts.
