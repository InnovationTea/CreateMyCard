"""从批跑 Trace 提取校验失败信息并生成浏览器渲染截图。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import shutil
import tempfile
from collections import Counter
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any
from urllib.parse import quote

GalleryCapture = Callable[[str, Path], Awaitable[dict[str, Any]]]
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
_ERROR_CODE_BY_ARTIFACT = {
    "plan_coverage_errors": "COMPACT_PLAN_COVERAGE_FAILED",
    "compact_validation_errors": "COMPACT_DSL_VALIDATION_FAILED",
}
_STAGE_LABELS = {
    "dsl.planCoverageValidation": "计划覆盖校验",
    "dsl.compactValidation": "Compact DSL 校验",
    "dsl.processing": "DSL 处理与校验",
    "artifactValidation": "Artifact 校验",
}
_ERROR_STAGE_LABELS = {
    "COMPACT_PLAN_COVERAGE_FAILED": "计划覆盖校验",
    "COMPACT_DSL_VALIDATION_FAILED": "Compact DSL 校验",
}
_VALIDATOR_STAGE_LABELS = {
    "hard": "硬规则",
    "semantic": "语义",
    "quality": "质量",
}


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON 根节点必须是对象: {path.name}")
    return value


def _read_trace(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw_line.strip():
            continue
        try:
            value = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Trace 第 {line_number} 行不是合法 JSON") from exc
        if isinstance(value, dict):
            records.append(value)
    return records


def _artifact_reference(record: dict[str, Any], name: str) -> dict[str, Any] | None:
    artifacts = record.get("artifacts")
    if not isinstance(artifacts, dict):
        return None
    value = artifacts.get(name)
    return value if isinstance(value, dict) else None


def _read_blob(run_dir: Path, reference: dict[str, Any]) -> str:
    digest = reference.get("sha256")
    expected_bytes = reference.get("bytes")
    if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
        raise ValueError("Trace 附件摘要无效")
    path = run_dir / "trace_blobs" / digest
    content = path.read_bytes()
    if isinstance(expected_bytes, int) and len(content) != expected_bytes:
        raise ValueError("Trace 附件字节数不匹配")
    if hashlib.sha256(content).hexdigest() != digest:
        raise ValueError("Trace 附件摘要校验失败")
    return content.decode("utf-8")


def _validation_round(record: dict[str, Any]) -> int:
    attempts = record.get("attempts")
    value = attempts.get("validation") if isinstance(attempts, dict) else None
    return value if isinstance(value, int) else 0


def _stage_label(record: dict[str, Any], issue: dict[str, Any] | None = None) -> str:
    stage = str(record.get("stage") or "")
    if stage == "artifactValidation" and issue is not None:
        validator_stage = issue.get("validatorStage")
        if isinstance(validator_stage, str) and validator_stage:
            label = _VALIDATOR_STAGE_LABELS.get(validator_stage, validator_stage)
            return f"Artifact {label}校验"
    return _STAGE_LABELS.get(stage, stage or "校验")


def _normalized_processing_errors(
    run_dir: Path,
    record: dict[str, Any],
) -> list[dict[str, Any]]:
    reference = _artifact_reference(record, "dsl_processing_issues")
    if reference is None:
        return []
    value = json.loads(_read_blob(run_dir, reference))
    if not isinstance(value, list):
        return []
    errors: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, dict):
            continue
        code = item.get("code")
        message = item.get("message")
        if not isinstance(code, str) or not isinstance(message, str):
            continue
        errors.append(
            {
                "round": _validation_round(record),
                "stage": _ERROR_STAGE_LABELS.get(code, _stage_label(record)),
                "code": code,
                "message": message,
            }
        )
    return errors


def _artifact_validation_errors(
    run_dir: Path,
    record: dict[str, Any],
) -> list[dict[str, Any]]:
    reference = _artifact_reference(record, "artifact_validation_result")
    if reference is None:
        return []
    value = json.loads(_read_blob(run_dir, reference))
    if not isinstance(value, dict):
        return []
    contexts = value.get("promptContexts")
    errors: list[dict[str, Any]] = []
    if isinstance(contexts, list):
        for item in contexts:
            if not isinstance(item, dict):
                continue
            code = item.get("code")
            message = item.get("message")
            if not isinstance(code, str) or not isinstance(message, str):
                continue
            errors.append(
                {
                    "round": _validation_round(record),
                    "stage": _stage_label(record, item),
                    "code": code,
                    "message": message,
                    "location": _error_location(item),
                }
            )
    if errors:
        return errors
    raw_errors = value.get("errors")
    if not isinstance(raw_errors, list):
        return []
    for message in raw_errors:
        if not isinstance(message, str):
            continue
        code, separator, detail = message.partition(":")
        errors.append(
            {
                "round": _validation_round(record),
                "stage": _stage_label(record),
                "code": code if separator else "ARTIFACT_VALIDATION_FAILED",
                "message": detail.strip() if separator else message,
            }
        )
    return errors


def _error_location(item: dict[str, Any]) -> str:
    file_kind = item.get("fileKind")
    line = item.get("line")
    pointer = item.get("jsonPointer")
    parts: list[str] = []
    if isinstance(file_kind, str) and file_kind:
        parts.append(file_kind)
    if isinstance(line, int):
        parts.append(f"第 {line} 行")
    if isinstance(pointer, str) and pointer:
        parts.append(pointer)
    return " · ".join(parts)


def _fallback_errors(run_dir: Path, record: dict[str, Any]) -> list[dict[str, Any]]:
    errors: list[dict[str, Any]] = []
    for artifact_name, code in _ERROR_CODE_BY_ARTIFACT.items():
        reference = _artifact_reference(record, artifact_name)
        if reference is None:
            continue
        value = json.loads(_read_blob(run_dir, reference))
        if not isinstance(value, list):
            continue
        for message in value:
            if isinstance(message, str):
                errors.append(
                    {
                        "round": _validation_round(record),
                        "stage": _stage_label(record),
                        "code": code,
                        "message": message,
                    }
                )
    return errors


def _record_errors(run_dir: Path, record: dict[str, Any]) -> list[dict[str, Any]]:
    stage = record.get("stage")
    if stage == "dsl.processing":
        return _normalized_processing_errors(run_dir, record)
    if stage == "artifactValidation":
        return _artifact_validation_errors(run_dir, record)
    return _fallback_errors(run_dir, record)


def _validation_input(run_dir: Path, record: dict[str, Any]) -> str:
    if record.get("stage") == "artifactValidation":
        reference = _artifact_reference(record, "artifact_validation_input")
        if reference is None:
            return ""
        value = json.loads(_read_blob(run_dir, reference))
        genui = value.get("genui") if isinstance(value, dict) else None
        return genui if isinstance(genui, str) else ""
    reference = _artifact_reference(record, "dsl_processing_input")
    return _read_blob(run_dir, reference) if reference is not None else ""


def _candidate_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    preferred = [
        record
        for record in records
        if record.get("status") == "failed"
        and record.get("stage") in {"dsl.processing", "artifactValidation"}
    ]
    if preferred:
        return preferred
    return [
        record
        for record in records
        if record.get("status") == "failed"
        and record.get("stage")
        in {"dsl.planCoverageValidation", "dsl.compactValidation"}
    ]


def _deduplicate_errors(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[object, object, object, object]] = set()
    for error in errors:
        identity = (
            error.get("round"),
            error.get("stage"),
            error.get("code"),
            error.get("message"),
        )
        if identity in seen:
            continue
        seen.add(identity)
        result.append(error)
    return result


class ValidationFailureGalleryManager:
    """读取失败 Trace，并通过调试平台 CardRenderer 截图。"""

    def __init__(
        self,
        output_root: Path,
        capture_base_url: str,
        *,
        capture: GalleryCapture | None = None,
    ) -> None:
        self.output_root = output_root.resolve()
        self.capture_base_url = capture_base_url.rstrip("/")
        self.capture = capture or self._capture_with_browser

    def items(self, run_id: str) -> list[dict[str, Any]]:
        run_dir = self._safe_run_dir(run_id)
        summary = _read_object(run_dir / "summary.json")
        items: list[dict[str, Any]] = []
        for sample in list(summary.get("samples") or []):
            if not isinstance(sample, dict) or sample.get("errorCode") != "VALIDATION_FAILED":
                continue
            items.append(self._analyze_sample(run_dir, sample))
        return items

    def _analyze_sample(
        self,
        run_dir: Path,
        sample: dict[str, Any],
    ) -> dict[str, Any]:
        sample_id = str(sample.get("id") or "")
        if not _SAFE_ID.fullmatch(sample_id):
            raise ValueError("样本标识无效")
        state = _read_object(run_dir / sample_id / "result.json")
        final_attempt = state.get("finalAttempt")
        if not isinstance(final_attempt, int) or final_attempt < 0:
            raise ValueError(f"样本 {sample_id} 缺少最终 attempt")
        trace_path = (
            run_dir
            / sample_id
            / f"attempt_{final_attempt:03d}"
            / "trace"
            / "source"
            / "trace.jsonl"
        )
        candidates = _candidate_records(_read_trace(trace_path))
        error_rows: list[dict[str, Any]] = []
        selected_record: dict[str, Any] | None = None
        selected_dsl = ""
        for record in candidates:
            record_errors = _record_errors(run_dir, record)
            if not record_errors:
                continue
            error_rows.extend(record_errors)
            dsl = _validation_input(run_dir, record)
            current_key = (_validation_round(record), int(record.get("sequence") or 0))
            selected_key = (
                _validation_round(selected_record),
                int(selected_record.get("sequence") or 0),
            ) if selected_record is not None else (-1, -1)
            if dsl and current_key >= selected_key:
                selected_record = record
                selected_dsl = dsl
        errors = _deduplicate_errors(error_rows)
        if selected_record is None or not selected_dsl or not errors:
            raise ValueError(f"样本 {sample_id} 的 Trace 缺少可分析的校验失败记录")
        final_round = _validation_round(selected_record)
        final_errors = [error for error in errors if error.get("round") == final_round]
        error_types = list(dict.fromkeys(str(error.get("code") or "") for error in final_errors))
        stages = list(dict.fromkeys(str(error.get("stage") or "") for error in final_errors))
        return {
            "id": sample_id,
            "title": str(sample.get("title") or sample_id),
            "query": str(sample.get("query") or ""),
            "size": str(sample.get("size") or "2x2"),
            "validationRound": final_round,
            "validationStage": "、".join(stages),
            "errorTypes": error_types,
            "errors": errors,
            "dsl": selected_dsl,
        }

    async def run(
        self,
        run_id: str,
        plugin_dir: Path,
    ) -> dict[str, Any]:
        items = self.items(run_id)
        capture_url = (
            f"{self.capture_base_url}/batch/runs/{quote(run_id, safe='')}"
            "/validation-failure-capture"
        )
        with tempfile.TemporaryDirectory(prefix="validation-gallery-", dir=plugin_dir) as name:
            temporary_dir = Path(name)
            capture_result = await self.capture(capture_url, temporary_dir)
            captures = self._persist_captures(plugin_dir, capture_result, temporary_dir)
        return self._plugin_result(run_id, plugin_dir, items, captures)

    @staticmethod
    def _persist_captures(
        plugin_dir: Path,
        capture_result: dict[str, Any],
        temporary_dir: Path,
    ) -> dict[str, dict[str, str]]:
        captures: dict[str, dict[str, str]] = {}
        for item in list(capture_result.get("items") or []):
            if not isinstance(item, dict):
                continue
            sample_id = str(item.get("id") or "")
            if not _SAFE_ID.fullmatch(sample_id):
                continue
            result = {"status": "failed", "error": str(item.get("error") or "渲染失败")}
            file_name = item.get("file")
            if isinstance(file_name, str) and file_name:
                source = (temporary_dir / file_name).resolve()
                if source.is_relative_to(temporary_dir.resolve()) and source.is_file():
                    target_dir = plugin_dir / "samples" / sample_id
                    target_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, target_dir / "render.png")
                    result = {"status": "success", "error": ""}
            captures[sample_id] = result
        return captures

    @staticmethod
    def _plugin_result(
        run_id: str,
        plugin_dir: Path,
        items: list[dict[str, Any]],
        captures: dict[str, dict[str, str]],
    ) -> dict[str, Any]:
        execution_id = plugin_dir.parent.parent.name
        sample_results: list[dict[str, Any]] = []
        type_counts: Counter[str] = Counter()
        stage_counts: Counter[str] = Counter()
        rendered = 0
        for item in items:
            sample_id = str(item.get("id") or "")
            error_types = [str(value) for value in list(item.get("errorTypes") or [])]
            type_counts.update(error_types)
            final_round = item.get("validationRound")
            final_errors = [
                error
                for error in list(item.get("errors") or [])
                if isinstance(error, dict) and error.get("round") == final_round
            ]
            sample_stages = {
                str(error.get("stage") or "")
                for error in final_errors
                if error.get("stage")
            }
            stage_counts.update(sample_stages)
            capture = captures.get(sample_id, {"status": "failed", "error": "未生成截图"})
            artifacts: list[dict[str, Any]] = [
                {"key": "validation-query", "data": item.get("query", "")},
                {"key": "validation-errors", "data": item.get("errors", [])},
                {"key": "pre-validation-dsl", "data": item.get("dsl", "")},
            ]
            if capture.get("status") == "success":
                rendered += 1
                url = (
                    f"/debug/batch/runs/{quote(run_id, safe='')}/postprocess/"
                    f"{quote(execution_id, safe='')}/assets/validation-failure-gallery/"
                    f"samples/{quote(sample_id, safe='')}/render.png"
                )
                artifacts.append(
                    {
                        "key": "dsl-browser-render",
                        "url": url,
                        "alt": f"{sample_id} 校验前 DSL 浏览器渲染结果",
                    }
                )
            else:
                artifacts.append(
                    {
                        "key": "dsl-browser-render-error",
                        "data": str(capture.get("error") or "浏览器渲染失败"),
                    }
                )
            sample_results.append(
                {
                    "sampleId": sample_id,
                    "status": "success" if capture.get("status") == "success" else "partial",
                    "summary": (
                        f"最终在{item.get('validationStage')}报错：{'、'.join(error_types)}"
                    ),
                    "facts": {
                        "validationStage": str(item.get("validationStage") or ""),
                        "errorTypes": error_types,
                        "validationRound": int(final_round or 0),
                        "renderStatus": str(capture.get("status") or "failed"),
                    },
                    "artifacts": artifacts,
                }
            )
        total = len(items)
        return {
            "status": "success" if rendered == total else "partial",
            "sampleResults": sample_results,
            "datasetResult": {
                "status": "success" if rendered == total else "partial",
                "summary": f"分析 {total} 个 VALIDATION_FAILED 样本，成功渲染 {rendered} 个",
                "facts": {"validationFailed": total, "rendered": rendered},
                "artifacts": [
                    {
                        "key": "validation-overview",
                        "data": [
                            {"label": "校验失败样本", "value": total},
                            {"label": "成功渲染", "value": rendered},
                            {"label": "渲染失败", "value": total - rendered},
                        ],
                    },
                    {
                        "key": "validation-error-types",
                        "data": [
                            {"错误类型": key, "样本数": value}
                            for key, value in sorted(type_counts.items())
                        ],
                    },
                    {
                        "key": "validation-stages",
                        "data": [
                            {"报错环节": key, "样本数": value}
                            for key, value in sorted(stage_counts.items())
                        ],
                    },
                ],
            },
        }

    async def _capture_with_browser(self, capture_url: str, output_dir: Path) -> dict[str, Any]:
        node = shutil.which("node")
        if node is None:
            raise RuntimeError("未找到 Node.js，无法生成卡片截图")
        script = Path(__file__).resolve().parents[2] / "scripts" / "capture_batch_gallery.mjs"
        process = await asyncio.create_subprocess_exec(
            node,
            str(script),
            "--url",
            capture_url,
            "--output",
            str(output_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=script.parents[1],
        )
        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=900.0)
        except TimeoutError as exc:
            process.kill()
            await process.communicate()
            raise RuntimeError("校验失败画廊截图超时") from exc
        if process.returncode != 0:
            detail = stderr.decode("utf-8", errors="replace").strip()
            if not detail:
                detail = stdout.decode("utf-8", errors="replace").strip()
            raise RuntimeError(detail or "校验失败画廊截图进程失败")
        return _read_object(output_dir / "capture.json")

    def _safe_run_dir(self, run_id: str) -> Path:
        if not _SAFE_ID.fullmatch(run_id):
            raise KeyError(run_id)
        path = (self.output_root / run_id).resolve()
        if not path.is_relative_to(self.output_root) or not path.is_dir():
            raise KeyError(run_id)
        return path


async def run_builtin(
    manager: ValidationFailureGalleryManager,
    run_id: str,
    output_dir: Path,
    _config: dict[str, Any],
) -> dict[str, Any]:
    """执行校验失败分析与截图。"""

    return await manager.run(run_id, output_dir)
