"""从批跑 Trace 提取全部校验失败历史并生成浏览器渲染截图。"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import shutil
import tempfile
from collections import Counter
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import quote

GalleryCapture = Callable[[str, Path], Awaitable[dict[str, Any]]]
_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$")
_ATTEMPT_DIR = re.compile(r"^attempt_(\d+)$")
_CAPTURE_BATCH_SIZE = 20
_ERROR_CODE_BY_ARTIFACT = {
    "plan_coverage_errors": "COMPACT_PLAN_COVERAGE_FAILED",
    "compact_validation_errors": "COMPACT_DSL_VALIDATION_FAILED",
}


@dataclass
class ValidationEvaluation:
    """一次实际执行的校验评估。"""

    capture_id: str
    execution_attempt: int
    interface_attempt: int
    validation_attempt: int
    status: str
    dsl: str
    errors: list[dict[str, Any]]


@dataclass
class SampleAnalysis:
    """一个批跑样本在全部执行尝试中的校验分析。"""

    sample_id: str
    title: str
    query: str
    size: str
    sequence: int
    final_status: str
    interface_retry_count: int
    validation_failure_count: int
    repair_attempt_count: int
    validations: list[ValidationEvaluation]


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


def _artifact_reference(record: dict[str, Any] | None, name: str) -> dict[str, Any] | None:
    if record is None:
        return None
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


def _attempt_value(record: dict[str, Any], name: str) -> int:
    attempts = record.get("attempts")
    value = attempts.get(name) if isinstance(attempts, dict) else None
    return value if isinstance(value, int) and value > 0 else 1


def _validation_key(record: dict[str, Any]) -> tuple[int, int]:
    return _attempt_value(record, "interface"), _attempt_value(record, "validation")


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


def _processing_errors(run_dir: Path, record: dict[str, Any] | None) -> list[dict[str, Any]]:
    reference = _artifact_reference(record, "dsl_processing_issues")
    if reference is None:
        return _fallback_processing_errors(run_dir, record)
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
        errors.append({"code": code, "message": message, "location": _error_location(item)})
    return errors


def _fallback_processing_errors(
    run_dir: Path,
    record: dict[str, Any] | None,
) -> list[dict[str, Any]]:
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
                errors.append({"code": code, "message": message, "location": ""})
    return errors


def _artifact_validation_errors(
    run_dir: Path,
    record: dict[str, Any] | None,
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
                {"code": code, "message": message, "location": _error_location(item)}
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
                "code": code if separator else "ARTIFACT_VALIDATION_FAILED",
                "message": detail.strip() if separator else message,
                "location": "",
            }
        )
    return errors


def _deduplicate_errors(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    seen: set[tuple[object, object, object]] = set()
    for error in errors:
        identity = (error.get("code"), error.get("message"), error.get("location"))
        if identity in seen:
            continue
        seen.add(identity)
        result.append(error)
    return result


def _validation_dsl(
    run_dir: Path,
    processing_record: dict[str, Any] | None,
    artifact_record: dict[str, Any] | None,
) -> str:
    artifact_input = _artifact_reference(artifact_record, "artifact_validation_input")
    if artifact_input is not None:
        value = json.loads(_read_blob(run_dir, artifact_input))
        genui = value.get("genui") if isinstance(value, dict) else None
        if isinstance(genui, str):
            return genui
    processing_input = _artifact_reference(processing_record, "dsl_processing_input")
    return _read_blob(run_dir, processing_input) if processing_input is not None else ""


def _error_rows(evaluation: ValidationEvaluation) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for error in evaluation.errors:
        row = {
            "执行尝试": f"第 {evaluation.execution_attempt} 次",
            "接口调用": (
                f"第 {evaluation.interface_attempt} 次"
                f"（重试 {evaluation.interface_attempt - 1} 次）"
            ),
            "校验评估": f"第 {evaluation.validation_attempt} 次",
            "错误类型": str(error.get("code") or "VALIDATION_FAILED"),
            "错误信息": str(error.get("message") or "校验失败"),
        }
        location = error.get("location")
        if isinstance(location, str) and location:
            row["位置"] = location
        rows.append(row)
    return rows


class ValidationFailureGalleryManager:
    """读取全部失败校验，并通过调试平台 CardRenderer 截图。"""

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
        analyses = self._analyze_run(run_id)
        return [self._capture_item(item) for item in analyses if item.validation_failure_count > 0]

    def _analyze_run(self, run_id: str) -> list[SampleAnalysis]:
        run_dir = self._safe_run_dir(run_id)
        summary = _read_object(run_dir / "summary.json")
        analyses: list[SampleAnalysis] = []
        for sample in list(summary.get("samples") or []):
            if isinstance(sample, dict):
                analyses.append(self._analyze_sample(run_dir, sample))
        return analyses

    def _analyze_sample(
        self,
        run_dir: Path,
        sample: dict[str, Any],
    ) -> SampleAnalysis:
        sample_id = str(sample.get("id") or "")
        if not _SAFE_ID.fullmatch(sample_id):
            raise ValueError("样本标识无效")
        state = _read_object(run_dir / sample_id / "result.json")
        final_status = str(state.get("status") or sample.get("status") or "failed")
        validations: list[ValidationEvaluation] = []
        interface_retry_count = 0
        repair_attempt_count = 0
        for execution_index, trace_path in self._trace_paths(run_dir, sample_id):
            records = _read_trace(trace_path)
            trace_validations, trace_retries, trace_repairs = self._analyze_trace(
                run_dir,
                sample_id,
                execution_index,
                records,
            )
            validations.extend(trace_validations)
            interface_retry_count += trace_retries
            repair_attempt_count += trace_repairs
        validation_failure_count = sum(item.status == "failed" for item in validations)
        sequence = sample.get("sequence")
        return SampleAnalysis(
            sample_id=sample_id,
            title=str(sample.get("title") or sample_id),
            query=str(sample.get("query") or ""),
            size=str(sample.get("size") or "2x2"),
            sequence=sequence if isinstance(sequence, int) else 0,
            final_status=final_status,
            interface_retry_count=interface_retry_count,
            validation_failure_count=validation_failure_count,
            repair_attempt_count=repair_attempt_count,
            validations=validations,
        )

    @staticmethod
    def _trace_paths(run_dir: Path, sample_id: str) -> list[tuple[int, Path]]:
        result: list[tuple[int, Path]] = []
        sample_dir = run_dir / sample_id
        for attempt_dir in sample_dir.iterdir():
            match = _ATTEMPT_DIR.fullmatch(attempt_dir.name)
            if not attempt_dir.is_dir() or match is None:
                continue
            trace_path = attempt_dir / "trace" / "source" / "trace.jsonl"
            if trace_path.is_file():
                result.append((int(match.group(1)), trace_path))
        return sorted(result, key=lambda item: item[0])

    @staticmethod
    def _analyze_trace(
        run_dir: Path,
        sample_id: str,
        execution_index: int,
        records: list[dict[str, Any]],
    ) -> tuple[list[ValidationEvaluation], int, int]:
        processing: dict[tuple[int, int], dict[str, Any]] = {}
        artifact_validation: dict[tuple[int, int], dict[str, Any]] = {}
        evaluations: list[dict[str, Any]] = []
        interfaces: set[int] = set()
        repair_attempt_count = 0
        for record in records:
            interface_attempt = _attempt_value(record, "interface")
            interfaces.add(interface_attempt)
            operation = record.get("operation")
            if operation == "dsl.processing":
                processing[_validation_key(record)] = record
            elif operation == "artifact_validation.completed":
                artifact_validation[_validation_key(record)] = record
            elif operation == "validation.evaluate":
                evaluations.append(record)
            elif operation == "repair.attempt":
                repair_attempt_count += 1
        results: list[ValidationEvaluation] = []
        for evaluation in evaluations:
            interface_attempt, validation_attempt = _validation_key(evaluation)
            key = (interface_attempt, validation_attempt)
            processing_record = processing.get(key)
            artifact_record = artifact_validation.get(key)
            errors: list[dict[str, Any]] = []
            if processing_record is not None and processing_record.get("status") == "failed":
                errors.extend(_processing_errors(run_dir, processing_record))
            if artifact_record is not None and artifact_record.get("status") == "failed":
                errors.extend(_artifact_validation_errors(run_dir, artifact_record))
            capture_id = (
                f"{sample_id}-e{execution_index + 1}"
                f"-i{interface_attempt}-v{validation_attempt}"
            )
            results.append(
                ValidationEvaluation(
                    capture_id=capture_id,
                    execution_attempt=execution_index + 1,
                    interface_attempt=interface_attempt,
                    validation_attempt=validation_attempt,
                    status=str(evaluation.get("status") or "failed"),
                    dsl=_validation_dsl(run_dir, processing_record, artifact_record),
                    errors=_deduplicate_errors(errors),
                )
            )
        interface_retry_count = max(interfaces, default=1) - 1
        return results, interface_retry_count, repair_attempt_count

    @staticmethod
    def _capture_item(item: SampleAnalysis) -> dict[str, Any]:
        validations: list[dict[str, Any]] = []
        for validation in item.validations:
            validations.append(
                {
                    "captureId": validation.capture_id,
                    "executionAttempt": validation.execution_attempt,
                    "interfaceAttempt": validation.interface_attempt,
                    "validationAttempt": validation.validation_attempt,
                    "status": validation.status,
                    "errorTypes": [
                        str(error.get("code") or "VALIDATION_FAILED")
                        for error in validation.errors
                    ],
                    "dsl": validation.dsl,
                }
            )
        return {
            "id": item.sample_id,
            "title": item.title,
            "query": item.query,
            "size": item.size,
            "sequence": item.sequence,
            "finalStatus": item.final_status,
            "interfaceRetryCount": item.interface_retry_count,
            "validationFailureCount": item.validation_failure_count,
            "repairAttemptCount": item.repair_attempt_count,
            "validations": validations,
        }

    async def run(
        self,
        run_id: str,
        plugin_dir: Path,
    ) -> dict[str, Any]:
        analyses = self._analyze_run(run_id)
        gallery_samples = [item for item in analyses if item.validation_failure_count > 0]
        capture_base_url = (
            f"{self.capture_base_url}/batch/runs/{quote(run_id, safe='')}"
            "/validation-failure-capture"
        )
        owners: dict[str, str] = {}
        for sample in gallery_samples:
            for validation in sample.validations:
                owners[validation.capture_id] = sample.sample_id
        captures: dict[str, dict[str, str]] = {}
        with tempfile.TemporaryDirectory(prefix="validation-gallery-", dir=plugin_dir) as name:
            temporary_dir = Path(name)
            for offset in range(0, len(owners), _CAPTURE_BATCH_SIZE):
                capture_url = (
                    f"{capture_base_url}?offset={offset}&limit={_CAPTURE_BATCH_SIZE}"
                )
                batch_dir = temporary_dir / f"batch-{offset:04d}"
                batch_dir.mkdir()
                capture_result = await self.capture(capture_url, batch_dir)
                captures.update(
                    self._persist_captures(
                        plugin_dir,
                        capture_result,
                        batch_dir,
                        owners,
                    )
                )
        return self._plugin_result(run_id, plugin_dir, analyses, gallery_samples, captures)

    @staticmethod
    def _persist_captures(
        plugin_dir: Path,
        capture_result: dict[str, Any],
        temporary_dir: Path,
        owners: dict[str, str],
    ) -> dict[str, dict[str, str]]:
        captures: dict[str, dict[str, str]] = {}
        for item in list(capture_result.get("items") or []):
            if not isinstance(item, dict):
                continue
            capture_id = str(item.get("id") or "")
            sample_id = owners.get(capture_id)
            if sample_id is None or not _SAFE_ID.fullmatch(capture_id):
                continue
            result = {"status": "failed", "error": str(item.get("error") or "渲染失败")}
            file_name = item.get("file")
            if isinstance(file_name, str) and file_name:
                source = (temporary_dir / file_name).resolve()
                if source.is_relative_to(temporary_dir.resolve()) and source.is_file():
                    target_dir = plugin_dir / "samples" / sample_id
                    target_dir.mkdir(parents=True, exist_ok=True)
                    target_name = f"{capture_id}.png"
                    shutil.copy2(source, target_dir / target_name)
                    result = {"status": "success", "error": "", "file": target_name}
            captures[capture_id] = result
        return captures

    @staticmethod
    def _plugin_result(
        run_id: str,
        plugin_dir: Path,
        analyses: list[SampleAnalysis],
        gallery_samples: list[SampleAnalysis],
        captures: dict[str, dict[str, str]],
    ) -> dict[str, Any]:
        execution_id = plugin_dir.parent.parent.name
        sample_results: list[dict[str, Any]] = []
        type_counts: Counter[str] = Counter()
        rendered = 0
        expected_renders = 0
        for analysis in analyses:
            for validation in analysis.validations:
                for error in validation.errors:
                    type_counts.update([str(error.get("code") or "VALIDATION_FAILED")])
        for item in gallery_samples:
            error_rows: list[dict[str, Any]] = []
            render_items: list[dict[str, Any]] = []
            sample_rendered = 0
            for validation in item.validations:
                error_rows.extend(_error_rows(validation))
                expected_renders += 1
                capture = captures.get(
                    validation.capture_id,
                    {"status": "failed", "error": "未生成截图"},
                )
                label = (
                    f"执行尝试 {validation.execution_attempt} · "
                    f"接口调用 {validation.interface_attempt} · "
                    f"校验评估 {validation.validation_attempt}"
                )
                error_types = [
                    str(error.get("code") or "VALIDATION_FAILED")
                    for error in validation.errors
                ]
                render_item: dict[str, Any] = {
                    "label": label,
                    "status": "校验通过" if validation.status == "success" else "校验失败",
                    "errorTypes": error_types,
                }
                if capture.get("status") == "success":
                    sample_rendered += 1
                    rendered += 1
                    file_name = str(capture.get("file") or "")
                    render_item["url"] = (
                        f"/debug/batch/runs/{quote(run_id, safe='')}/postprocess/"
                        f"{quote(execution_id, safe='')}/assets/validation-failure-gallery/"
                        f"samples/{quote(item.sample_id, safe='')}/"
                        f"{quote(file_name, safe='')}"
                    )
                    render_item["alt"] = f"{item.sample_id} {label} DSL 渲染结果"
                else:
                    render_item["error"] = str(capture.get("error") or "浏览器渲染失败")
                render_items.append(render_item)
            sample_complete = sample_rendered == len(item.validations)
            sample_results.append(
                {
                    "sampleId": item.sample_id,
                    "status": "success" if sample_complete else "partial",
                    "summary": (
                        f"最终执行{'成功' if item.final_status == 'success' else '失败'}；"
                        f"发现 {item.validation_failure_count} 次校验失败"
                    ),
                    "facts": {
                        "finalStatus": "成功" if item.final_status == "success" else "失败",
                        "interfaceRetryCount": item.interface_retry_count,
                        "validationFailureCount": item.validation_failure_count,
                        "repairAttemptCount": item.repair_attempt_count,
                    },
                    "artifacts": [
                        {"key": "validation-query", "data": item.query},
                        {"key": "validation-errors", "data": error_rows},
                        {"key": "validation-renders", "data": render_items},
                    ],
                }
            )
        total = len(analyses)
        successful = sum(item.final_status == "success" for item in analyses)
        without_failures = sum(item.validation_failure_count == 0 for item in analyses)
        repair_and_retry_total = sum(
            item.repair_attempt_count + item.interface_retry_count for item in analyses
        )
        validation_failure_total = sum(item.validation_failure_count for item in analyses)
        plugin_complete = rendered == expected_renders
        return {
            "status": "success" if plugin_complete else "partial",
            "sampleResults": sample_results,
            "datasetResult": {
                "status": "success" if plugin_complete else "partial",
                "summary": (
                    f"{total} 个样本中有 {len(gallery_samples)} 个出现过校验失败；"
                    f"已渲染 {rendered}/{expected_renders} 次校验"
                ),
                "facts": {
                    "samples": total,
                    "validationFailureSamples": len(gallery_samples),
                    "validationEvaluations": expected_renders,
                },
                "artifacts": [
                    {
                        "key": "validation-overview",
                        "data": [
                            {
                                "label": "执行成功率",
                                "value": round(successful * 100 / total, 2) if total else 0.0,
                                "unit": "%",
                            },
                            {
                                "label": "无校验失败比例",
                                "value": (
                                    round(without_failures * 100 / total, 2) if total else 0.0
                                ),
                                "unit": "%",
                            },
                            {
                                "label": "平均修复 + 重试次数",
                                "value": (
                                    round(repair_and_retry_total / total, 2) if total else 0.0
                                ),
                            },
                            {
                                "label": "平均校验失败次数",
                                "value": (
                                    round(validation_failure_total / total, 2) if total else 0.0
                                ),
                            },
                        ],
                    },
                    {
                        "key": "validation-error-types",
                        "data": [
                            {"错误类型": key, "出现次数": value}
                            for key, value in sorted(type_counts.items())
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
    """执行校验失败分析与逐次校验截图。"""

    return await manager.run(run_id, output_dir)
