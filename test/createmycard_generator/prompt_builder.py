"""Prompt assembly helpers for A2UI generation."""

from __future__ import annotations

import re
import sys
from pathlib import Path

REFERENCE_FILES = [
    "reference/capability.md",
    "reference/card-composition-rules.md",
    "reference/card-design.md",
    "reference/guide.md",
    "reference/component-catalog.md",
    "reference/data-binding.md",
    "reference/visual-interaction.md",
    "reference/spacing-elevation.md",
    "reference/expressiveness-toolkit.md",
    "reference/design-review.md",
    "reference/review-validation.md",
]

EXAMPLE_HEADER = (
    "以下是完整的桌面卡片示例（JSONL 格式，每行一条消息，"
    "createSurface / updateComponents / updateDataModel 各一行）："
)


def read_file_text(filepath: Path) -> str:
    try:
        return filepath.read_text(encoding="utf-8")
    except OSError as exc:
        print(f"警告：无法读取 {filepath}：{exc}", file=sys.stderr)
        return ""


def assemble_system_prompt(skill_dir: Path) -> str:
    parts: list[str] = []
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.exists():
        sys.exit(f"错误：SKILL.md 缺失，路径：{skill_md}")
    content = read_file_text(skill_md)
    parts.append(f"--- [SECTION: SKILL.md] ---\n\n{content}")

    for ref_file in REFERENCE_FILES:
        ref_path = skill_dir / ref_file
        if not ref_path.exists():
            print(f"警告：参考文档缺失：{ref_path}", file=sys.stderr)
            continue
        content = read_file_text(ref_path)
        parts.append(f"\n--- [SECTION: {ref_file}] ---\n\n{content}")

    example_path = skill_dir / "reference" / "widget-examples.jsonl"
    if example_path.exists():
        content = read_file_text(example_path)
        parts.append(
            f"\n--- [SECTION: widget-examples.jsonl] ---\n\n"
            f"{EXAMPLE_HEADER}\n\n{content}"
        )
    else:
        print(f"警告：示例文件缺失：{example_path}", file=sys.stderr)
    return "\n".join(parts)


def load_few_shot(skill_dir: Path) -> str:
    few_shot_path = skill_dir / "reference" / "few-shot-examples.txt"
    if few_shot_path.exists():
        return few_shot_path.read_text(encoding="utf-8")
    return ""


def build_user_prompt(
    query: str,
    extract_keywords: bool,
    few_shot: str = "",
    last_errors: list[str] | None = None,
    last_dsl: str | None = None,
) -> str:
    """构建用户 Prompt（集中管理，方便维护）。"""
    if last_errors:
        err_str = "\n".join([f"  - {e}" for e in last_errors[:5]])
        prompt = f"""
【重要 - 必须严格遵守！】
上次生成的 DSL 有以下致命错误：
{err_str}
"""
        if last_dsl:
            prompt += f"""
上次生成的 DSL（请在此基础上修正，不要完全重写）：
{last_dsl}
"""
        prompt += f"""
请立即修正，重新生成完整的 3 行 DSL，绝对不能缺少任何一行：
  1. createSurface      <- 必须有
  2. updateComponents   <- 必须有！这是最常见的缺失错误！绝对不能少！
  3. updateDataModel    <- 必须有

用户需求：
{query}
"""
    else:
        prompt = query

    if few_shot:
        prompt += f"\n\n{few_shot}"

    prompt += """
【生成规则 - 必须严格遵守】
1. 不要输出任何布局分析、设计理由、改进说明等文本
2. 直接输出 3 行 DSL 即可，不要任何前置或后置的解释文字
3. 不需要写 markdown 标题或分隔线
4. 3 行 DSL 必须完整：createSurface -> updateComponents -> updateDataModel
"""
    if extract_keywords:
        prompt += "\n5. 最后输出一行关键词 KEYWORDS: 词1,词2,词3... （只从用户需求原文提取）"
    return prompt


def extract_keywords(raw_text: str, query_text: str) -> list[str]:
    keyword_match = re.search(r"KEYWORDS[\s:：]*(.+)", raw_text, re.IGNORECASE)
    if keyword_match:
        line = keyword_match.group(1).strip().split("\n")[0].strip()
        return [k.strip() for k in line.split(",") if k.strip()]
    keywords = re.findall(r"[一-龥]{2,}|[a-zA-Z0-9°%]+", query_text)
    seen = set()
    return [k for k in keywords if k not in seen and not seen.add(k)]
