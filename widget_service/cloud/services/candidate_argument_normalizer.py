"""按字段提示和完整结构恢复候选；业务合法性仍由请求模型和生成预检裁决。"""

from typing import Any

from api.schemas import GenerateWidgetCardRequest, VersionedToolRequest
from app.logger import json_for_log, logger
from config.config import get_settings
from services.argument_json_recovery import DECODER, validate_recovery_depth
from services.capability_registry import CapabilityRegistry

CANDIDATE_ALIASES = {
    "candidateDataBindings": (
        "dataCapabilities", "dataCandidates", "dataBindings", "candidateDataCapabilities",
        "dataList", "data", "dataIds",
    ),
    "candidateEventCandidates": (
        "eventCapabilities", "eventCandidates", "candidateEvents", "events",
    ),
    "candidateAssetIds": (
        "assetCandidates", "assetCandidateIds", "candidateAssetCandidates", "candidateAssets",
        "assetIds", "assets",
    ),
}
_MAX_ITEM_CHARS = 131072
_KEYWORDS = {
    "data": "candidateDataBindings",
    "event": "candidateEventCandidates",
    "asset": "candidateAssetIds",
}
_PROTECTED_FIELDS = frozenset(GenerateWidgetCardRequest.model_fields) | {
    "bundleName", "functionName", "skillName", "requestId", "operation",
    "dataCapabilityIds", "eventCapabilityIds",
}


def _candidate_sources(arguments: dict[str, Any]) -> dict[str, list[str]]:
    """先收集再裁决；关键词仅识别字段类别，不推断用户业务语义。"""
    sources: dict[str, list[str]] = {}
    aliases = {}
    for target, names in CANDIDATE_ALIASES.items():
        for name in names:
            aliases[name] = target
    for name in arguments:
        if name in _PROTECTED_FIELDS:
            continue
        target = aliases.get(name)
        if target is None:
            matches = []
            for keyword, destination in _KEYWORDS.items():
                if keyword in name.lower():
                    matches.append(destination)
            if len(matches) != 1:
                continue
            target = matches[0]
        sources.setdefault(target, []).append(name)
    return sources


def _check_assets(arguments: dict[str, Any], candidates: list[Any]) -> None:
    """按生成业务相同的版本区间及回退配置核验素材，不查询设备安装状态。"""
    context = VersionedToolRequest(**arguments)
    settings = get_settings()
    device = arguments.get("device")
    source_rom = device.get("_sourceRomVersion") if isinstance(device, dict) else None
    if source_rom is not None and not isinstance(source_rom, str):
        raise ValueError("invalid_source_rom")
    rom = source_rom or context.device.romVersion or settings.default_device_rom_version
    app = context.prdVer or settings.default_prd_version
    # 版本归一化及区间未命中的回退策略与生成入口保持一致。
    CapabilityRegistry.normalize_app_version(app)
    CapabilityRegistry.normalize_rom_version(rom)
    try:
        registry = CapabilityRegistry(app_version=app, device_rom_version=rom)
    except ValueError as exc:
        logger.info(
            "candidate_asset_registry_selection_failed "
            f"exception_type={type(exc).__name__} "
            f"fallback={settings.enable_default_capability_registry_fallback}"
        )
        if not settings.enable_default_capability_registry_fallback:
            raise
        registry = CapabilityRegistry(version=settings.capability_registry_version)
    for asset_id in candidates:
        if registry.get_asset_capability(asset_id) is None:
            raise ValueError("asset_not_registered")


def _nonempty_text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _matches_candidate(value: Any, target: str) -> bool:
    if target == "candidateAssetIds":
        return _nonempty_text(value)
    if not isinstance(value, dict):
        return False
    if not _nonempty_text(value.get("capabilityId")):
        return False
    if target == "candidateDataBindings":
        return (
            isinstance(value.get("arguments"), dict)
            and _nonempty_text(value.get("writeResultTo"))
        )
    action = value.get("action")
    if not isinstance(action, dict):
        return False
    return _nonempty_text(action.get("call")) and isinstance(action.get("args"), dict)


def _decode_candidates(value: Any, target: str) -> list[Any]:
    if not isinstance(value, list) or not value:
        raise ValueError("nonempty_array_required")
    validate_recovery_depth(value)
    decoded = []
    for item in value:
        if target != "candidateAssetIds" and isinstance(item, str):
            if len(item) > _MAX_ITEM_CHARS:
                raise ValueError("encoded_item_too_large")
            item = DECODER.decode(item)
            validate_recovery_depth(item)
        if not _matches_candidate(item, target):
            raise ValueError("candidate_structure_incomplete")
        decoded.append(item)
    return decoded


def normalize_candidate_arguments(arguments: dict[str, Any]) -> dict[str, Any]:
    """不修改输入；冲突或不可确认的类别原样保留，交给严格请求校验报错。"""
    normalized = dict(arguments)
    for target, present in _candidate_sources(arguments).items():
        if target in arguments or len(present) != 1:
            logger.info(f"candidate_alias_rejected target={target} reason=field_conflict")
            continue
        source = present[0]
        source_log = json_for_log(source)
        try:
            candidates = _decode_candidates(arguments[source], target)
            if target == "candidateAssetIds":
                _check_assets(arguments, candidates)
        except (ValueError, RecursionError, OSError) as exc:
            # 严格解码异常可能含原始键或值；日志仅记录异常类型及固定原因。
            logger.info(
                f"candidate_alias_rejected source={source_log} target={target} "
                f"reason=invalid_structure_or_encoding exception_type={type(exc).__name__}"
            )
            continue
        normalized.pop(source)
        normalized[target] = candidates
        logger.info(
            f"candidate_alias_normalized source={source_log} target={target} "
            f"item_count={len(candidates)}"
        )
    return normalized
