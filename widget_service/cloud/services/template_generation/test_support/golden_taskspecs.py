# -*- coding: utf-8 -*-
"""Layer B taskspec 金样工具：真实服务链路的录制、回放与比对。

每个用例在 ``tests/goldens/taskspecs/<case>/`` 下固化三份文件::

    input.json   冻结的原始 WS 包络（录制时从语料库复制）
    replay.json  录制的 LLM 响应（按 prompt 摘要键索引）
    golden.json  期望的规范生成结果（status + artifact，去除易变字段）

录制走真实 LLM（需要可用额度）；回放把录制响应注入 llmclient 传输层，
preflight -> 模板引擎 -> 校验 -> artifact 的整条链路仍是真实代码路径。
prompt 摘要未命中时回放报错并提示重新录制。

用法（在 cloud/ 目录下）::

    python3 -m services.template_generation.test_support.golden_taskspecs record \\
        --corpus-dir <widget_batch_cases 目录> [--cases Q035,Q036]
    python3 -m services.template_generation.test_support.golden_taskspecs run \\
        [--cases Q035] [--declared Q035] [--diff]
    python3 -m services.template_generation.test_support.golden_taskspecs accept \\
        [--cases Q035]   # 引擎/模板侧预期变更后重新固化 golden（录制仍有效）
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import hashlib
import json
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

from api.routes import (
    _model_request_context_from_payload,
    _normalize_payload,
)
from api.schemas import GenerateWidgetCardRequest, GenerateWidgetCardResponse
from config.config import get_settings
from core.errors import GenerationStatus
from custom.llmclient import LLMClientOptions, stream_genui
from custom.model_runtime import ModelExecutionRuntime
from custom.model_transport import ModelTransportError
from models.artifact import WidgetArtifact
from models.preflight import GenerationPreflightError
from services.source_artifact_repository import SourceArtifactRepository
from services.template_generation.test_support.golden import (
    TemplateGolden,
    canonicalize,
    compare,
    render_diff,
    render_report,
)
from services.widget_generation_service import WidgetGenerationService

OPERATION = "generateWidgetCardTerseDslNested2"
GOLDEN_ROOT = Path(__file__).resolve().parents[1] / "tests" / "goldens" / "taskspecs"

_REPLAY_MISS_MARKER = "golden replay miss"


def _messages_key(messages: list[dict[str, str]]) -> str:
    """按规范化 prompt 内容计算录制键；prompt 变化即视为未命中。"""
    canonical = json.dumps(messages, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class RecordingTransport:
    """真实调用 llmclient 流式接口，同时按 prompt 摘要记录响应。

    运行时的 llmclient 传输层在工作线程里同步调用 ``generate``；
    线程内没有事件循环，可以用 ``asyncio.run`` 聚合流式输出。
    """

    def __init__(self) -> None:
        self.recordings: dict[str, str] = {}

    def generate(
        self,
        messages: list[dict[str, str]],
        request_context: Any = None,
    ) -> str:
        return asyncio.run(self._generate(list(messages)))

    async def _generate(self, messages: list[dict[str, str]]) -> str:
        chunks = [chunk async for chunk in stream_genui(LLMClientOptions(), messages)]
        response = "".join(chunks)
        self.recordings[_messages_key(messages)] = response
        return response


class ReplayingTransport:
    """按 prompt 摘要返回录制响应；未命中时给出可定位的错误。"""

    def __init__(self, recordings: dict[str, str]) -> None:
        self.recordings = recordings
        self.missed_keys: list[str] = []
        self.calls = 0

    def generate(
        self,
        messages: list[dict[str, str]],
        request_context: Any = None,
    ) -> str:
        self.calls += 1
        key = _messages_key(list(messages))
        if key not in self.recordings:
            self.missed_keys.append(key)
            raise ModelTransportError(
                f"{_REPLAY_MISS_MARKER} for prompt key {key[:16]}...; "
                "the prompt changed or the recording is incomplete - re-record this case",
                code="GOLDEN_REPLAY_MISS",
            )
        return self.recordings[key]


def freeze_json(payload: Any) -> str:
    """冻结用例输入：保持键的原有顺序（键序会影响下游 prompt 逐字节内容）。"""
    return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def build_generation_request(payload: dict[str, Any]) -> GenerateWidgetCardRequest:
    """按 routes 的 WS 处理顺序把原始包络转换为生成请求。"""
    _request_id, arguments = _normalize_payload(payload, OPERATION)
    device_arguments = arguments.get("device")
    source_rom_version = None
    if isinstance(device_arguments, dict):
        source_rom_version = device_arguments.pop("_sourceRomVersion", None)
    request = GenerateWidgetCardRequest(**arguments)
    request.device._sourceRomVersion = source_rom_version
    request._raw_request_body = json.dumps(payload, ensure_ascii=False)
    request._model_request_context = _model_request_context_from_payload(
        payload,
        request,
    )
    return request


def _status_text(status: Any) -> str:
    return status.value if hasattr(status, "value") else str(status)


def canonical_result(
    case_id: str,
    response: GenerateWidgetCardResponse,
    artifact: WidgetArtifact | None,
) -> dict[str, Any]:
    """规范化生成结果：剥离 artifactId/createdAt 等易变字段。"""
    if artifact is None:
        return {
            "artifact": None,
            "caseId": case_id,
            "errorCode": response.errorCode,
            "message": response.message,
            "status": _status_text(response.status),
            "suggestSize": response.suggestSize,
        }
    meta = artifact.meta.model_dump(mode="json")
    meta.pop("artifactId", None)
    meta.pop("createdAt", None)
    return {
        "artifact": {
            "cardSpec": artifact.cardSpec,
            "effectiveCapabilities": artifact.effectiveCapabilities,
            "generationPlan": artifact.generationPlan.model_dump(mode="json"),
            "genuiMessages": [
                json.loads(line)
                for line in artifact.genui.splitlines()
                if line.strip()
            ],
            "meta": meta,
            "removedCapabilities": [
                item.model_dump(mode="json", exclude_none=True)
                for item in artifact.removedCapabilities
            ],
            "schemaVersion": artifact.schemaVersion,
            "taskSpec": artifact.taskSpec,
        },
        "caseId": case_id,
        "status": _status_text(response.status),
        "suggestSize": response.suggestSize,
    }


@contextlib.contextmanager
def _golden_settings_pin(enabled: bool):
    """离线回放期间把全局配置单例固定到录制时的路由与离线条件。

    回放必须与录制走完全相同的模型路由（唯一的录制后端是注入的 llmclient
    传输层），并保证本地联调配置或环境变量的漂移不会让请求逃逸到真实模型
    后端。字段值必须与录制基线所用条件一致；路由类配置上游变更时需同步
    更新这里。录制路径（RecordingTransport）不经过本固定，仍用真实配置。
    """
    if not enabled:
        yield
        return
    workspace_root = Path(tempfile.mkdtemp(prefix="golden-taskspec-workspace-"))
    overrides: dict[str, Any] = {
        # 路由固定：录制/回放唯一一致的后端是注入的 llmclient 传输层。
        "openai_master_client": "llmclient",
        "openai_fallback_client": "llmclient",
        "enable_openai_fallback": False,
        "enable_model_failure_retry": False,
        "enable_a2ui_model_mock": False,
        "design_compact_model_backend": "openai",
        # 凭据清空：任何绕过固定路由的路径都在本地立即失败，而非访问网络。
        "deepseek_api_key": "",
        "deepseek_platform_access_key": "",
        "deepseek_platform_ws_url": "",
        # 离线与内容确定性：阻断回放路径上的真实网络副作用。
        "enable_artifact_download_mock": True,
        "ai_widget_data_huashan_enable": False,
        "asset_src_url_mapping": {},
        # 存储隔离：artifact 落到临时目录（canonical_result 不含路径，零金样漂移）。
        "WORKSPACE_ROOT": workspace_root,
    }
    settings = get_settings()
    saved = {name: getattr(settings, name) for name in overrides}
    for name, value in overrides.items():
        # Settings 未开 validate_assignment：setattr 不做校验，字段名拼错会在
        # 上一行 getattr 处直接 AttributeError。
        setattr(settings, name, value)
    try:
        yield
    finally:
        for name, value in saved.items():
            setattr(settings, name, value)
        shutil.rmtree(workspace_root, ignore_errors=True)


async def execute_case(
    case_id: str,
    payload: dict[str, Any],
    transport: Any,
) -> tuple[dict[str, Any], GenerateWidgetCardResponse | None]:
    """用注入的传输层跑完整生成链路，返回规范化结果与原始响应。

    三种确定性基线都规范化为结果字典：成功（含 artifact）、失败
    （FAILED/UNSUPPORTED 响应）、preflight 拒绝（服务抛出异常）。
    回放（ReplayingTransport）在整个用例（含 artifact 读取）外包一层
    配置固定与后端护栏；录制（RecordingTransport）按原样使用真实配置。
    """
    replay = isinstance(transport, ReplayingTransport)
    with _golden_settings_pin(enabled=replay):
        runtime = ModelExecutionRuntime(get_settings(), llmclient_transport=transport)
        if replay:
            # 双保险：即使配置固定失效，也绝不允许路由到其他模型后端。
            original_execute_provider = runtime._execute_provider

            async def _reject_foreign_provider(
                provider: Any,
                messages: list[dict[str, str]],
                request_context: Any,
            ) -> str:
                if provider != "llmclient":
                    raise ModelTransportError(
                        f"golden replay reached model provider {provider!r}; "
                        "the offline settings pin failed",
                        code="GOLDEN_PROVIDER_ESCAPE",
                    )
                return await original_execute_provider(
                    provider,
                    messages,
                    request_context,
                )

            runtime._execute_provider = _reject_foreign_provider
        try:
            service = WidgetGenerationService(model_runtime=runtime)
            request = build_generation_request(payload)
            try:
                response = await service.generate_widget_card_terse_dsl_nested2(request)
            except GenerationPreflightError as exc:
                return canonical_preflight_rejection(case_id, exc), None
            except Exception as exc:  # 基线异常同样固化；瞬态失败会被回放自检拦截。
                return canonical_unhandled_error(case_id, exc), None
        finally:
            await runtime.aclose()
        artifact = None
        if response.status == GenerationStatus.SUCCESS and response.artifactUrl:
            # load() 内部使用 asyncio.run，必须放到无事件循环的工作线程执行。
            load_result = await asyncio.to_thread(
                SourceArtifactRepository().load,
                response.artifactUrl,
            )
            artifact = load_result.artifact
    # transport.calls 供排查用：为 0 说明录制已不被当前链路消费（如第二层
    # 转为全确定性），属可重录的陈旧录制，而非路由逃逸——后者已由上方
    # 后端护栏与清空凭据在本地立即失败。
    return canonical_result(case_id, response, artifact), response


def canonical_preflight_rejection(case_id: str, exc: Any) -> dict[str, Any]:
    return {
        "artifact": None,
        "blockingIssues": [
            issue.model_dump(mode="json", exclude_none=True)
            for issue in exc.result.blocking_issues
        ],
        "caseId": case_id,
        "errorCode": getattr(exc, "error_code", ""),
        "status": "preflight_rejected",
    }


def canonical_unhandled_error(case_id: str, exc: Exception) -> dict[str, Any]:
    return {
        "artifact": None,
        "caseId": case_id,
        "exceptionType": type(exc).__name__,
        "message": str(exc)[:500],
        "status": "unhandled_error",
    }


async def replay_case_text(case_id: str) -> tuple[str, bool]:
    """回放单个已固化用例，返回（生成结果规范文本，是否回放未命中）。"""
    case_dir = GOLDEN_ROOT / case_id
    payload = json.loads((case_dir / "input.json").read_text(encoding="utf-8"))
    replay_payload = json.loads(
        (case_dir / "replay.json").read_text(encoding="utf-8")
    )
    recordings = {
        item["key"]: item["response"] for item in replay_payload["recordings"]
    }
    transport = ReplayingTransport(recordings)
    result, _response = await execute_case(case_id, payload, transport)
    return canonicalize(result), bool(transport.missed_keys)


def blessed_case_ids() -> list[str]:
    if not GOLDEN_ROOT.is_dir():
        return []
    return sorted(
        path.name
        for path in GOLDEN_ROOT.iterdir()
        if (path / "golden.json").is_file()
    )


def blessed_case_ids() -> list[str]:
    if not GOLDEN_ROOT.is_dir():
        return []
    return sorted(
        path.name
        for path in GOLDEN_ROOT.iterdir()
        if (path / "golden.json").is_file()
    )


def capture_selected_templates(case_id: str) -> dict:
    """离线回放单个用例并捕获实际选中的模板（不修改任何金样文件）。

    Layer B 金样不记录最终选中的模板（canonical artifact 已剥离）；
    这里在 facade 的引擎入口包一层，把 ``TemplateEngineOutput.template_ids``
    捕获下来。生成失败的用例返回空列表。
    """
    import services.template_generation.facade as facade_module

    case_dir = GOLDEN_ROOT / case_id
    payload = json.loads((case_dir / "input.json").read_text(encoding="utf-8"))
    replay_payload = json.loads((case_dir / "replay.json").read_text(encoding="utf-8"))
    recordings = {
        item["key"]: item["response"] for item in replay_payload["recordings"]
    }
    transport = ReplayingTransport(recordings)
    captured: list[str] = []
    original = facade_module.generate_template_engine_a2ui

    async def capture(*args: Any, **kwargs: Any):
        output = await original(*args, **kwargs)
        captured.extend(output.template_ids)
        return output

    facade_module.generate_template_engine_a2ui = capture
    try:
        result, _response = asyncio.run(execute_case(case_id, payload, transport))
    finally:
        facade_module.generate_template_engine_a2ui = original
    return {
        "case": case_id,
        "status": result["status"],
        "errorCode": result.get("errorCode", ""),
        "selected": sorted(set(captured)),
        "replayMissed": bool(transport.missed_keys),
    }


_SELECTION_CACHE: dict[str, dict] = {}


def capture_selected_templates_cached(case_id: str) -> dict:
    """``capture_selected_templates`` 的进程内 memo 版本（一用例只回放一次）。

    模板级 Layer B 归因需要对候选用例逐个回放取真实选中集；同一次 CLI
    调用里多个模板/多张表共享这份缓存，避免重复回放。
    """
    if case_id not in _SELECTION_CACHE:
        _SELECTION_CACHE[case_id] = capture_selected_templates(case_id)
    return _SELECTION_CACHE[case_id]


def record_case(corpus_dir: Path, case_id: str) -> tuple[int, str, str | None]:
    """录制单个用例并固化 input/replay/golden。

    成功、失败响应与 preflight 拒绝都是可固化的确定性基线。
    返回（录制条数, 基线状态, 错误）；固化后立即回放自检。
    """
    corpus_path = corpus_dir / f"{case_id}.json"
    if not corpus_path.is_file():
        return 0, "missing", f"corpus case not found: {corpus_path}"
    payload = json.loads(corpus_path.read_text(encoding="utf-8"))
    transport = RecordingTransport()
    result, _response = asyncio.run(execute_case(case_id, payload, transport))
    status = str(result["status"])
    case_dir = GOLDEN_ROOT / case_id
    case_dir.mkdir(parents=True, exist_ok=True)
    (case_dir / "input.json").write_text(freeze_json(payload), encoding="utf-8")
    (case_dir / "replay.json").write_text(
        canonicalize(
            {
                "recordings": [
                    {"key": key, "response": response}
                    for key, response in sorted(transport.recordings.items())
                ]
            }
        ),
        encoding="utf-8",
    )
    (case_dir / "golden.json").write_text(canonicalize(result), encoding="utf-8")
    replay_text, missed = asyncio.run(replay_case_text(case_id))
    if missed:
        return len(transport.recordings), status, "replay missed immediately after recording"
    if replay_text != canonicalize(result):
        return len(transport.recordings), status, "replay diverged immediately after recording"
    return len(transport.recordings), status, None


def _split_ids(raw: str) -> frozenset[str]:
    return frozenset(item.strip() for item in raw.split(",") if item.strip())


def re_bless_cases(case_ids: list[str]) -> tuple[list[str], list[str]]:
    """把当前回放结果固化为新 golden（录制仍有效）。

    返回（已重新固化, 回放未命中需重录）。
    """
    accepted: list[str] = []
    missed: list[str] = []
    for case_id in case_ids:
        text, is_missed = asyncio.run(replay_case_text(case_id))
        if is_missed:
            missed.append(case_id)
            continue
        (GOLDEN_ROOT / case_id / "golden.json").write_text(text, encoding="utf-8")
        accepted.append(case_id)
    return accepted, missed


def _cmd_accept(args: argparse.Namespace) -> int:
    """把当前回放结果固化为新 golden（录制仍有效；用于引擎/模板侧预期变更）。"""
    case_ids = blessed_case_ids()
    selected = _split_ids(args.cases)
    if selected:
        case_ids = [case_id for case_id in case_ids if case_id in selected]
    if not case_ids:
        print("No recorded taskspec goldens matched.", file=sys.stderr)
        return 1
    accepted, missed = re_bless_cases(case_ids)
    for case_id in accepted:
        print(f"{case_id} OK (golden re-blessed from replay)")
    for case_id in missed:
        print(f"{case_id} SKIP (replay missed; re-record instead)", file=sys.stderr)
    return 0


def _cmd_record(args: argparse.Namespace) -> int:
    corpus_dir = Path(args.corpus_dir)
    if not corpus_dir.is_dir():
        print(f"corpus dir not found: {corpus_dir}", file=sys.stderr)
        return 1
    if args.cases.strip():
        case_ids = [item.strip() for item in args.cases.split(",") if item.strip()]
    else:
        case_ids = sorted(path.stem for path in corpus_dir.glob("Q*.json"))
    if not case_ids:
        print(f"no Q*.json cases under {corpus_dir}", file=sys.stderr)
        return 1
    failures = 0
    for case_id in case_ids:
        count, status, error = record_case(corpus_dir, case_id)
        if error is None:
            print(f"{case_id} OK (status={status}, recorded {count} llm call(s))")
        else:
            failures += 1
            print(f"{case_id} FAILED (status={status}): {error}")
    print(f"recorded={len(case_ids) - failures}/{len(case_ids)} failed={failures}")
    return 1 if failures else 0


def _cmd_run(args: argparse.Namespace) -> int:
    case_ids = blessed_case_ids()
    selected = _split_ids(args.cases)
    if selected:
        case_ids = [case_id for case_id in case_ids if case_id in selected]
    if not case_ids:
        print(
            "No recorded taskspec goldens matched. Record with:\n"
            "  python3 -m services.template_generation.test_support.golden_taskspecs "
            "record --corpus-dir <widget_batch_cases 目录>",
            file=sys.stderr,
        )
        return 1
    generated: dict[str, TemplateGolden] = {}
    blessed: dict[str, str] = {}
    replay_missed: list[str] = []
    for case_id in case_ids:
        text, missed = asyncio.run(replay_case_text(case_id))
        generated[case_id] = TemplateGolden(template_id=case_id, meta={}, text=text)
        blessed[case_id] = (GOLDEN_ROOT / case_id / "golden.json").read_text(
            encoding="utf-8"
        )
        if missed:
            replay_missed.append(case_id)
    comparison = compare(
        generated,
        blessed,
        declared=_split_ids(args.declared),
        declare_all=args.declare_all,
    )
    print(render_report(comparison, title="Taskspec golden comparison:"))
    if replay_missed:
        print(
            "Replay missed recorded prompts (prompt changed since recording?): "
            + ", ".join(replay_missed)
        )
        print(
            "  re-record: python3 -m "
            "services.template_generation.test_support.golden_taskspecs record "
            f"--corpus-dir <dir> --cases {','.join(replay_missed)}"
        )
    if args.diff:
        for case_id in comparison.changed_ids:
            text = render_diff(case_id, generated, blessed)
            if text:
                print(text)
    return 0 if not comparison.has_undeclared_divergence else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="golden_taskspecs",
        description="Layer B taskspec golden tool (record/replay the real generation chain).",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    record_parser = sub.add_parser(
        "record",
        help="run the real service with the real LLM and bless recordings + golden",
    )
    record_parser.add_argument(
        "--corpus-dir",
        required=True,
        help="directory containing the Q*.json widget batch cases",
    )
    record_parser.add_argument(
        "--cases", default="", help="comma-separated case ids; default all Q*.json"
    )

    run_parser = sub.add_parser(
        "run", help="replay recorded responses and compare with the blessed goldens"
    )
    run_parser.add_argument("--cases", default="", help="limit to comma-separated ids")
    run_parser.add_argument(
        "--declared", default="", help="comma-separated case ids whose change is expected"
    )
    run_parser.add_argument(
        "--declare-all",
        action="store_true",
        help="treat every divergence as declared (engine-wide change review)",
    )
    run_parser.add_argument(
        "--diff", action="store_true", help="print unified diffs for changed cases"
    )

    accept_parser = sub.add_parser(
        "accept",
        help="re-bless golden.json from current replay (recordings stay valid)",
    )
    accept_parser.add_argument("--cases", default="", help="limit to comma-separated ids")

    args = parser.parse_args(argv)
    if args.command == "record":
        return _cmd_record(args)
    if args.command == "accept":
        return _cmd_accept(args)
    return _cmd_run(args)


if __name__ == "__main__":
    sys.exit(main())
