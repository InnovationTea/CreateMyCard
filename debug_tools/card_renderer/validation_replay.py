"""复用线上 Processor、资源映射与 ArtifactValidator 的单轮判定。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

from config.config import get_settings
from models.artifact import WidgetArtifact
from models.capability import DataCapability
from models.generation import CardSpec, TaskSpec
from pydantic import BaseModel, ConfigDict, Field, StrictBool, StrictInt, model_validator
from services.asset_url_mapper import AssetUrlMapper
from services.capability_registry import CapabilityRegistry
from services.card_validation.compact_validation.repair_guidance import RepairGuidanceContext
from services.card_validation.diagnostics import Diagnostic
from services.generation_pipeline import DesignCompactProcessor, DslProcessingContext, QualityIssue
from services.layout_theme_contract import strip_source_colors, uses_post_layout_theme
from services.protocol_registry import A2UIProtocolRegistry
from services.validator import ArtifactValidator


class ReplayContext(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifact: WidgetArtifact
    sourceKind: Literal["model", "template"]
    compactPlan: dict[str, Any] | None
    enableArtifactValidation: StrictBool
    planInformationCoverageAsWarning: StrictBool
    allowedOmittedPlanFactIndexes: list[StrictInt]
    assetMapping: dict[str, str]
    designProfileId: str = Field(pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]*$")
    layoutScope: str | None
    sourceArtifact: WidgetArtifact | None = None

    @model_validator(mode="after")
    def require_snapshot(self) -> ReplayContext:
        artifact = self.artifact
        required = {"cardSpec", "taskSpec", "effectiveCapabilities", "generationPlan", "meta"}
        if not required.issubset(artifact.model_fields_set):
            raise ValueError("请提供完整原产物，不能省略卡片、任务、有效能力、候选计划或元数据。")
        if not {"generationMode", "dslProtocolVersion"}.issubset(artifact.meta.model_fields_set):
            raise ValueError("元数据必须明确包含生成模式与协议版本。")
        plan_keys = {"candidateDataBindings", "candidateEventCandidates", "candidateAssetIds"}
        if not plan_keys.issubset(artifact.generationPlan.model_fields_set):
            raise ValueError("候选计划必须明确包含数据绑定、事件和素材集合。")
        task_keys = {
            "userQuery",
            "size",
            "appVersion",
            "dataModelSchema",
            "eventCandidates",
            "assetCandidates",
        }
        if not task_keys.issubset(artifact.taskSpec):
            raise ValueError("原任务上下文缺少必要字段；不能使用默认版本、数据声明或候选集合。")
        task = TaskSpec.model_validate(artifact.taskSpec)
        card = CardSpec.model_validate(artifact.cardSpec)
        if task.size != card.suggestSize:
            raise ValueError("原任务与卡片尺寸不一致，请提供同一次执行的上下文。")
        if not {"data", "event", "asset"}.issubset(artifact.effectiveCapabilities):
            raise ValueError("有效能力快照必须明确包含 data、event、asset 集合，包括空集合。")
        if self.sourceKind == "model" and not self.layoutScope:
            raise ValueError("模型来源必须提供当次 layoutScope，不能跳过正式布局匹配。")
        for index in self.allowedOmittedPlanFactIndexes:
            if isinstance(index, bool) or index < 0:
                raise ValueError("允许省略的事实索引必须是非负整数。")
        return self


@dataclass(frozen=True)
class PreparedReplay:
    processor_context: DslProcessingContext
    mapper: AssetUrlMapper
    protocol_profile: dict[str, Any]


def _registered_directory(group: str, name: str) -> None:
    root = get_settings().data_root / group
    known = {path.name for path in root.iterdir() if path.is_dir()}
    if name not in known:
        raise ValueError(f"当前本地缺少 {group} 注册版本：{name}；不能替换为默认版本。")


def prepare_replay(context: ReplayContext) -> PreparedReplay:
    artifact = context.artifact
    version = artifact.meta.capabilityRegistryVersion
    profile_id = artifact.meta.protocolProfileId
    _registered_directory("capabilities", version)
    _registered_directory("protocol_profiles", profile_id)
    _registered_directory("protocol_profiles", context.designProfileId)
    registry = CapabilityRegistry(version=version)
    data: list[DataCapability] = []
    for identifier in artifact.effectiveCapabilities.get("data", []):
        if not isinstance(identifier, str):
            raise ValueError("有效数据能力必须使用原产物中的 ID。")
        capability = registry.get_data_capability(identifier)
        if capability is None:
            raise ValueError(f"原注册版本中找不到数据能力：{identifier}")
        data.append(capability)
    sources: set[str] = set()
    for identifier in artifact.effectiveCapabilities.get("asset", []):
        if not isinstance(identifier, str):
            raise ValueError("有效素材必须使用原产物中的 ID。")
        asset = registry.get_asset_capability(identifier)
        if asset is None:
            raise ValueError(f"原注册版本中找不到素材：{identifier}")
        sources.add(asset.src)
    profile = A2UIProtocolRegistry(profile_id).get_profile()
    if profile.get("version") != artifact.meta.dslProtocolVersion:
        raise ValueError("本地协议版本与原产物不一致。")
    task = TaskSpec.model_validate(artifact.taskSpec)
    processor_context = DslProcessingContext(
        size=task.size,
        card_spec=artifact.cardSpec,
        task_spec=artifact.taskSpec,
        protocol_profile=profile,
        design_profile_id=context.designProfileId,
        data_capabilities=data,
        event_candidates=artifact.effectiveCapabilities.get("event", []),
        skip_compact_dsl_validation=context.sourceKind == "template",
        colorless_layout=uses_post_layout_theme(
            "generateWidgetCardCompactDsl", template_source=context.sourceKind == "template",
        ),
        layout_scope=context.layoutScope,
        compact_plan=context.compactPlan,
        plan_information_coverage_as_warning=context.planInformationCoverageAsWarning,
        allowed_omitted_plan_fact_indexes=tuple(context.allowedOmittedPlanFactIndexes),
        repair_context=RepairGuidanceContext(mode=artifact.meta.generationMode),
    )
    return PreparedReplay(processor_context, AssetUrlMapper(context.assetMapping, sources), profile)


class ReplayArtifactValidator(ArtifactValidator):
    """仅保留原校验器产生的诊断；判定、配置和调用路径仍由父类实现。"""

    def __init__(self, mapping: dict[str, str]) -> None:
        super().__init__(mapping)
        self.captured: list[Diagnostic] = []

    def _normalize_diagnostics(
        self,
        diagnostics: list[Diagnostic],
        severity: str,
    ) -> tuple[list[str], list[dict[str, Any]]]:
        if severity == "error":
            self.captured = list(diagnostics)
        return super()._normalize_diagnostics(diagnostics, severity)


def _processor_diagnostics(
    issues: tuple[QualityIssue, ...], compact_source_kind: str,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for issue in issues:
        structured = issue.prompt_context.get("compactDiagnostics")
        if isinstance(structured, list) and structured:
            for item in structured:
                result.append({**item, "stage": "compact", "sourceKind": compact_source_kind})
        else:
            result.append(
                {
                    "code": issue.code,
                    "message": issue.message,
                    "severity": issue.severity,
                    "stage": issue.stage,
                    "sourceKind": "processed",
                }
            )
    return result


def _artifact_diagnostic(item: Diagnostic) -> dict[str, Any]:
    source_kind = "context"
    if item.file_kind == "genui":
        source_kind = "genui"
    elif item.file_kind == "cardspec":
        source_kind = "cardspec"
    return {
        "code": item.code,
        "message": item.message,
        "severity": item.severity,
        "stage": f"artifact.{item.stage}",
        "sourceKind": source_kind,
        "sourceLine": item.line if source_kind != "context" else None,
        "propertyPath": item.json_pointer,
        "actual": item.actual,
        "expected": item.expected,
        "fixHint": item.fix_hint,
    }


def replay_validation(
    source: str,
    context: ReplayContext,
    prepared: PreparedReplay,
) -> dict[str, Any]:
    colorless = prepared.processor_context.colorless_layout
    artifact_stage_name = "布局产物校验" if colorless else "完整产物校验"
    result: dict[str, Any] = {
        "status": "failed",
        "valid": False,
        "complete": False,
        "validationScope": "layout" if colorless else "artifact",
        "size": prepared.processor_context.size,
        "diagnostics": [],
        "stages": [],
        "warnings": [
            "按当前本地代码、版本化规则及提供的上下文复现单轮线上判定；"
            "不调用模型修复，不保存正式产物，不代表已验证真机效果。"
        ],
        "genui": None,
        "previewError": None,
    }
    sources = {
        "original": source,
        "cardspec": json.dumps(context.artifact.cardSpec, ensure_ascii=False),
        "context": context.model_dump_json(indent=2),
    }
    stages: list[dict[str, Any]] = []
    result["sources"] = sources
    result["stages"] = stages
    processed = DesignCompactProcessor().process(source, prepared.processor_context)
    sources["processed"] = processed.source_dsl
    compact_source_kind = "layoutInput" if colorless else "original"
    diagnostics = _processor_diagnostics(processed.issues, compact_source_kind)
    if colorless and any(item.get("sourceKind") == "layoutInput" for item in diagnostics):
        # 结构化 Compact 诊断证明去色已成功；复用同一纯函数还原其行号对应的输入。
        sources["layoutInput"] = strip_source_colors(source)
    result["diagnostics"] = diagnostics
    stages.append(
        {
            "name": "线上 DSL 处理（修复、重组、计划、Compact、转换、单位）",
            "status": "failed" if processed.errors else "passed",
        }
    )
    if context.sourceKind == "template":
        stages.append(
            {
                "name": "Compact 专项校验",
                "status": "skipped",
                "reason": "模板来源，沿用线上显式跳过规则",
            }
        )
    if processed.errors:
        stages.append({"name": artifact_stage_name, "status": "skipped", "reason": "前置处理失败"})
        return result
    try:
        genui = prepared.mapper.rewrite_standard(processed.standard_dsl)
    except ValueError as exc:
        diagnostics.append(
            {
                "code": "ASSET_MAPPING_FAILED",
                "message": str(exc),
                "severity": "error",
                "stage": "mapping",
                "sourceKind": "processed",
            }
        )
        stages.append({"name": "素材地址映射", "status": "failed"})
        stages.append({"name": artifact_stage_name, "status": "skipped", "reason": "素材映射失败"})
        return result
    stages.append({"name": "素材地址映射", "status": "passed"})
    sources["genui"] = genui
    result["genui"] = genui
    if not context.enableArtifactValidation:
        result["status"] = "skipped"
        stages.append(
            {
                "name": artifact_stage_name,
                "status": "skipped",
                "reason": "原执行关闭了产物校验；不能声明完整校验通过",
            }
        )
        return result
    artifact = context.artifact.model_copy(update={"genui": genui}, deep=True)
    validator = ReplayArtifactValidator(prepared.mapper.mapping)
    if colorless:
        errors = validator.validate_layout(artifact, prepared.protocol_profile)
    else:
        errors = validator.validate(artifact, prepared.protocol_profile)
    diagnostics.extend(_artifact_diagnostic(item) for item in validator.captured)
    if errors and not any(item.severity == "error" for item in validator.captured):
        for error in errors:
            diagnostics.append(
                {
                    "code": "ARTIFACT_VALIDATION_FAILED",
                    "message": error,
                    "severity": "error",
                    "stage": "artifact",
                    "sourceKind": "genui",
                }
            )
    stages.append(
        {
            "name": artifact_stage_name,
            "status": "failed" if errors else "passed",
        }
    )
    if colorless:
        stages.append(
            {
                "name": "主题选择、填色与最终交付校验",
                "status": "skipped",
                "reason": "此回放止于单轮布局评估，不调用主题模型；布局通过不代表最终交付通过",
            }
        )
    result["complete"] = True
    result["valid"] = not errors
    result["status"] = "passed" if not errors else "failed"
    return result
