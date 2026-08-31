from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from typing import Any

from .config import (
    JSX_VALIDATOR_PATH,
    PLATFORM_REPOSITORY_ROOT,
    PLATFORM_RESOURCE_ROOT,
    PLAYWRIGHT_BROWSERS_ROOT,
    REPO_ROOT,
)


class ValidatorInfrastructureError(RuntimeError):
    """The JSX browser validator could not execute reliably."""


_BROWSER_RUNTIME_FILES = (
    REPO_ROOT / "node_modules" / "react" / "umd" / "react.production.min.js",
    REPO_ROOT / "node_modules" / "react-dom" / "umd" / "react-dom.production.min.js",
    REPO_ROOT / "node_modules" / "@babel" / "standalone" / "babel.min.js",
)


def browser_runtime_missing_files() -> list[Path]:
    """Return deterministic local browser-runtime dependencies that are absent."""
    return [path for path in _BROWSER_RUNTIME_FILES if not path.is_file()]


async def _validate_generated_card_once(
    *,
    payload: bytes,
    command: list[str],
    timeout_seconds: float,
) -> dict[str, Any]:
    environment = os.environ.copy()
    environment["GENUI_PLATFORM_ROOT"] = str(PLATFORM_REPOSITORY_ROOT)
    environment["GENUI_RESOURCE_ROOT"] = str(PLATFORM_RESOURCE_ROOT)
    # 本地自带 playwright-browsers/ 时优先使用；不存在则不覆盖，让 Playwright 走系统默认路径
    if PLAYWRIGHT_BROWSERS_ROOT.is_dir():
        environment["PLAYWRIGHT_BROWSERS_PATH"] = str(PLAYWRIGHT_BROWSERS_ROOT)
    try:
        process = await asyncio.create_subprocess_exec(
            *command,
            cwd=str(REPO_ROOT),
            env=environment,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as exc:
        raise ValidatorInfrastructureError(f"无法启动 JSX 校验器：{exc}") from exc
    try:
        stdout, stderr = await asyncio.wait_for(process.communicate(payload), timeout=timeout_seconds)
    except TimeoutError as exc:
        process.kill()
        await process.wait()
        raise ValidatorInfrastructureError(f"JSX 校验超过 {timeout_seconds:g} 秒") from exc

    output = stdout.decode("utf-8", errors="replace").strip()
    error_output = stderr.decode("utf-8", errors="replace").strip()
    try:
        report = json.loads(output)
    except json.JSONDecodeError as exc:
        detail = error_output or output or "validator produced no output"
        raise ValidatorInfrastructureError(f"JSX 校验器未返回合法 JSON：{detail[:1000]}") from exc
    if not isinstance(report, dict):
        raise ValidatorInfrastructureError("JSX 校验器返回值必须是 JSON object")
    if process.returncode not in {0, 1} or report.get("kind") == "infrastructure":
        details = report.get("findings") or error_output or f"exit={process.returncode}"
        raise ValidatorInfrastructureError(f"JSX 校验器运行失败：{details}")
    if bool(report.get("ok")) != (process.returncode == 0):
        raise ValidatorInfrastructureError(f"JSX 校验器状态不一致：exit={process.returncode}, ok={report.get('ok')!r}")
    return report


async def validate_generated_card(
    *,
    source: str,
    task: dict[str, Any],
    component_name: str,
    browser: bool = True,
    validator_path: Path = JSX_VALIDATOR_PATH,
    timeout_seconds: float = 90.0,
    infrastructure_retries: int = 2,
) -> dict[str, Any]:
    if not validator_path.is_file():
        raise ValidatorInfrastructureError(f"缺少 JSX 校验器：{validator_path}")
    if infrastructure_retries < 0:
        raise ValueError("infrastructure_retries must be non-negative")
    payload = json.dumps(
        {
            "source": source,
            "task": task,
            "componentName": component_name,
        },
        ensure_ascii=False,
    ).encode("utf-8")
    command = ["node", str(validator_path), "--stdin"]
    if not browser:
        command.append("--no-browser")

    for attempt in range(infrastructure_retries + 1):
        try:
            return await _validate_generated_card_once(
                payload=payload,
                command=command,
                timeout_seconds=timeout_seconds,
            )
        except ValidatorInfrastructureError as exc:
            if attempt >= infrastructure_retries:
                if infrastructure_retries:
                    raise ValidatorInfrastructureError(f"JSX 校验基础设施连续 {attempt + 1} 次失败：{exc}") from exc
                raise
            await asyncio.sleep(min(0.5 * (2**attempt), 2.0))

    raise AssertionError("unreachable")


_BROWSER_LAYOUT_CODES = frozenset(
    {
        "browser-height-overflow",
        "browser-overflow",
        "browser-edge-spacing",
        "browser-vertical-clipping",
        "browser-semantic-overlap",
        "browser-semantic-content-overflow",
    }
)


def _error_findings(report: dict[str, Any]) -> list[dict[str, Any]]:
    findings = report.get("findings")
    if not isinstance(findings, list):
        return []
    return [item for item in findings if isinstance(item, dict) and item.get("severity") == "error"]


def browser_layout_fingerprints(report: dict[str, Any]) -> frozenset[str]:
    """Return stable identities for browser-layout failures across repairs."""

    fingerprints: set[str] = set()
    for item in _error_findings(report):
        code = str(item.get("code") or "")
        if code not in _BROWSER_LAYOUT_CODES:
            continue
        components = item.get("components")
        if isinstance(components, list):
            owners = sorted(str(value) for value in components if value)
        else:
            owner = item.get("component")
            owners = [str(owner)] if owner else []
        evidence = item.get("evidence")
        axis = ""
        if code == "browser-semantic-overlap" and isinstance(evidence, dict):
            overlap = evidence.get("overlap")
            if isinstance(overlap, dict):
                try:
                    width = float(overlap.get("width") or 0)
                    height = float(overlap.get("height") or 0)
                except (TypeError, ValueError):
                    width = height = 0
                axis = "vertical" if height <= width else "horizontal"
        fingerprints.add("|".join([code, ",".join(owners), axis]))
    return frozenset(fingerprints)


def browser_layout_needs_restructure(
    report: dict[str, Any],
    *,
    previous_fingerprints: frozenset[str] = frozenset(),
) -> tuple[bool, list[str]]:
    """Decide when local nudging should be replaced by a layout rewrite."""

    current = browser_layout_fingerprints(report)
    repeated = sorted(current & previous_fingerprints)
    layout_errors = [item for item in _error_findings(report) if str(item.get("code") or "") in _BROWSER_LAYOUT_CODES]
    has_total_overflow = any(item.get("code") == "browser-height-overflow" for item in layout_errors)
    return bool(repeated or has_total_overflow or len(layout_errors) >= 2), repeated


def _compact_finding(item: dict[str, Any]) -> dict[str, Any]:
    entry = {
        "severity": "error",
        "code": item.get("code"),
        "message": item.get("message"),
    }
    for field in (
        "component",
        "componentText",
        "components",
        "componentTexts",
        "evidence",
        "likelyCause",
        "suggestion",
        "details",
    ):
        value = item.get(field)
        if value is None:
            continue
        encoded = json.dumps(value, ensure_ascii=False, default=str)
        entry[field] = value if len(encoded) <= 3000 else encoded[:3000] + "…"
    return entry


def _aggregate_layout_findings(
    findings: list[dict[str, Any]],
    *,
    structural_repair: bool,
) -> dict[str, Any]:
    components: list[str] = []
    evidence: list[dict[str, Any]] = []
    for item in findings[:6]:
        owners = item.get("components")
        if not isinstance(owners, list):
            owners = [item.get("component")]
        for owner in owners:
            value = str(owner or "").strip()
            if value and value not in components:
                components.append(value)
        compact_evidence = item.get("evidence")
        encoded_evidence = json.dumps(
            compact_evidence,
            ensure_ascii=False,
            default=str,
        )
        if len(encoded_evidence) > 1200:
            compact_evidence = encoded_evidence[:1200] + "…"
        evidence.append(
            {
                "code": item.get("code"),
                "message": item.get("message"),
                **({"evidence": compact_evidence} if compact_evidence is not None else {}),
            }
        )
    if structural_repair:
        suggestion = (
            "当前不是单个组件的轻微偏移。请重新分配整个正文区域：减少真正可舍弃的"
            "次要内容，重新分组组件并调整共同父级的 flex/height/basis/gap；不要继续逐个"
            "移动组件，也不得删除必需的 dataIds、actionId 或把动态值改成静态文本。"
        )
    else:
        suggestion = (
            "根据 evidence 调整这些组件的共同父级布局，一次解决全部冲突；不要通过裁剪、隐藏或删除必需信息规避问题。"
        )
    return {
        "severity": "error",
        "code": "browser-layout-conflict",
        "message": f"浏览器在同一张卡片中检测到 {len(findings)} 项相互关联的布局错误",
        "components": components,
        "evidence": {
            "findings": evidence,
            **({"omittedCount": len(findings) - len(evidence)} if len(findings) > len(evidence) else {}),
        },
        "likelyCause": "当前内容总量、组件固定尺寸和父级槽位分配不兼容。",
        "suggestion": suggestion,
    }


def compact_validation_feedback(
    report: dict[str, Any],
    *,
    limit: int = 12,
    structural_repair: bool = False,
) -> list[dict[str, Any]]:
    compact: list[dict[str, Any]] = []
    findings = _error_findings(report)
    layout_findings = [item for item in findings if str(item.get("code") or "") in _BROWSER_LAYOUT_CODES]
    layout_aggregated = len(layout_findings) >= 2
    for item in findings:
        if item in layout_findings:
            if not layout_aggregated:
                compact.append(_compact_finding(item))
            continue
        compact.append(_compact_finding(item))
    if layout_aggregated:
        compact.append(
            _aggregate_layout_findings(
                layout_findings,
                structural_repair=structural_repair,
            )
        )
    elif structural_repair and layout_findings:
        layout_code = layout_findings[0].get("code")
        entry = next(item for item in compact if item.get("code") == layout_code)
        entry["suggestion"] = (
            "同类布局错误在修复后再次出现。不要继续局部移动组件；请重新分配整个正文区域，"
            "保持必需 dataIds/actionId，并只省略真正可舍弃的信息。"
        )
        entry["repeated"] = True
    over_limit_with_layout = len(compact) > limit and layout_aggregated and limit > 0
    has_layout_tail = False
    if over_limit_with_layout:
        has_layout_tail = compact[-1].get("code") == "browser-layout-conflict"
    if over_limit_with_layout and has_layout_tail:
        compact = [*compact[: max(0, limit - 1)], compact[-1]]
    else:
        compact = compact[:limit]
    return compact
