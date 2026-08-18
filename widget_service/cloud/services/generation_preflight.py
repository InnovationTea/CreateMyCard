# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import json
from collections.abc import Iterable
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import ValidationError as JsonSchemaValidationError

from api.schemas import CandidateEventCandidate, GenerateWidgetCardRequest
from app.logger import json_for_log, logger
from core.errors import ErrorCode
from core.json_pointer import parse_json_pointer
from models.capability import AssetCapability, DataCapability, RemovedCapability
from models.generation import CandidateDataBinding, EventAction
from models.preflight import (
    AgentAction,
    GenerationPreflightResult,
    PreflightIssue,
)
from services.capability_registry import CapabilityRegistry
from services.card_spec_builder import CardSpecBuilder
from services.card_validation.base import expression_references
from services.task_spec_builder import TaskSpecBuilder

_MODULE = "[Generation Preflight]"
_MISSING = object()
_DATA_INPUT_SOURCE = "getDataCapabilitySchemas.dataCapabilities[].inputSchema"
_DATA_OUTPUT_SOURCE = "getDataCapabilitySchemas.dataCapabilities[].outputSchema"
_EVENT_SOURCE = "getWidgetCapabilityOverview.eventCapabilities[].actionTemplate"
_ASSET_SOURCE = "getWidgetCapabilityOverview.assetCandidates[]"
_LEGACY_WEATHER_URI = (
    "hww://www.huawei.com/totemweather?enterType=share&cityCode="
)


class GenerationPreflight:
    """在 Prompt 和模型调用之前完成生成请求的确定性裁决。"""

    def __init__(self, registry: CapabilityRegistry) -> None:
        self.registry = registry

    def run(self, request: GenerateWidgetCardRequest) -> GenerationPreflightResult:
        """校验候选计划并在通过后一次性构造 CardSpec 与 TaskSpec。"""
        if request.size is None or request.title is None or request.description is None:
            raise ValueError("generation request must be normalized before preflight")
        candidate_bindings = request.candidateDataBindings or []
        candidate_events = request.candidateEventCandidates or []
        candidate_asset_ids = request.candidateAssetIds or []
        issues: list[PreflightIssue] = []
        warnings: list[PreflightIssue] = []
        removed: list[RemovedCapability] = []

        effective_bindings, data_capabilities = self._resolve_data_bindings(
            candidate_bindings,
            issues,
        )
        effective_events = self._resolve_events(
            candidate_events,
            effective_bindings,
            data_capabilities,
            issues,
            warnings,
            removed,
        )
        effective_assets = self._resolve_assets(candidate_asset_ids, issues)

        card_spec = None
        task_spec = None
        if not issues:
            card_spec = CardSpecBuilder().build(
                request.size,
                effective_bindings,
                request.title,
                request.description,
            )
            task_spec = TaskSpecBuilder().build(
                request.userQuery,
                request.size,
                effective_bindings,
                data_capabilities,
                effective_events,
                effective_assets,
            )

        result = GenerationPreflightResult(
            effective_bindings=tuple(effective_bindings),
            effective_data_capabilities=tuple(data_capabilities),
            effective_events=tuple(effective_events),
            effective_assets=tuple(effective_assets),
            removed_capabilities=tuple(removed),
            blocking_issues=tuple(issues),
            warnings=tuple(warnings),
            card_spec=card_spec,
            task_spec=task_spec,
        )
        logger.info(
            f"{_MODULE} completed blocking_issue_count={len(issues)} "
            f"warning_count={len(warnings)} "
            "blocking_issues="
            f"{json_for_log([item.model_dump(mode='json') for item in issues])}"
        )
        return result

    def _resolve_data_bindings(
        self,
        candidate_bindings: list[CandidateDataBinding],
        issues: list[PreflightIssue],
    ) -> tuple[list[CandidateDataBinding], list[DataCapability]]:
        effective_bindings: list[CandidateDataBinding] = []
        capabilities: list[DataCapability] = []
        for index, binding in enumerate(candidate_bindings):
            base_path = f"/candidateDataBindings/{index}"
            capability = self.registry.get_data_capability(binding.capabilityId)
            if capability is None:
                issues.append(
                    self._unknown_issue(
                        f"{base_path}/capabilityId",
                        binding.capabilityId,
                        "数据能力未在当前注册表中声明。",
                        reference_source="getWidgetCapabilityOverview.dataCapabilities[]",
                    )
                )
                continue
            binding_issue_count = len(issues)
            self._append_schema_issues(
                binding.arguments,
                capability.inputSchema,
                f"{base_path}/arguments",
                binding.capabilityId,
                "DATA_ARGUMENT_SCHEMA_INVALID",
                issues,
            )
            for relative_path in self._binding_value_paths(binding.arguments):
                issues.append(
                    self._invalid_issue(
                        "DATA_ARGUMENT_BINDING_FORBIDDEN",
                        f"{base_path}/arguments{relative_path}",
                        "数据能力入参必须是静态值，不能包含 DSL 表达式或绑定对象。",
                        "符合 inputSchema 的静态 JSON 值",
                        binding.capabilityId,
                        repair_instruction=(
                            "删除表达式或绑定对象，按本轮 inputSchema 填写静态 JSON 值；"
                            "无法从用户需求确定时先询问用户。"
                        ),
                        reference_source=_DATA_INPUT_SOURCE,
                    )
                )
            write_parts = parse_json_pointer(binding.writeResultTo)
            valid_write_root = write_parts is not None and len(write_parts) >= 2
            valid_write_root = valid_write_root and write_parts[0] == "data"
            if not valid_write_root:
                issues.append(
                    self._invalid_issue(
                        "WRITE_RESULT_PATH_INVALID",
                        f"{base_path}/writeResultTo",
                        "数据写入路径必须是 /data 下的严格 JSON Pointer。",
                        capability.defaultWriteResultTo,
                        binding.capabilityId,
                        repair_instruction=(
                            "优先改为本轮数据 schema 返回的 defaultWriteResultTo；"
                            "多个数据候选必须使用互不重叠的 /data 路径。"
                        ),
                        reference_source=(
                            "getDataCapabilitySchemas.dataCapabilities[].defaultWriteResultTo"
                        ),
                    )
                )
            self._append_output_field_issues(binding, capability, base_path, issues)
            if len(issues) == binding_issue_count:
                effective_bindings.append(binding)
                capabilities.append(capability)

        self._append_write_conflicts(candidate_bindings, issues)
        return effective_bindings, capabilities

    def _append_output_field_issues(
        self,
        binding: CandidateDataBinding,
        capability: DataCapability,
        base_path: str,
        issues: list[PreflightIssue],
    ) -> None:
        builder = TaskSpecBuilder()
        for index, pointer in enumerate(binding.candidateOutputFields):
            if builder.resolve_output_leaf(capability.outputSchema, pointer) is not None:
                continue
            issues.append(
                self._invalid_issue(
                    "OUTPUT_FIELD_PATH_INVALID",
                    f"{base_path}/candidateOutputFields/{index}",
                    "候选展示字段不是对应 outputSchema 中的规范叶子路径。",
                    "outputSchema 中存在的叶子 JSON Pointer；数组元素使用数字下标",
                    binding.capabilityId,
                    actual_value=pointer,
                    repair_instruction=(
                        "从本轮 outputSchema 重新选择准确的叶子 JSON Pointer；"
                        "数组元素可使用 /0、/1、/2 等数字下标。"
                    ),
                    reference_source=_DATA_OUTPUT_SOURCE,
                )
            )

    def _append_write_conflicts(
        self,
        bindings: list[CandidateDataBinding],
        issues: list[PreflightIssue],
    ) -> None:
        for index, binding in enumerate(bindings):
            if parse_json_pointer(binding.writeResultTo) is None:
                continue
            for other_index in range(index + 1, len(bindings)):
                other = bindings[other_index]
                if not self._paths_conflict(binding.writeResultTo, other.writeResultTo):
                    continue
                issues.append(
                    PreflightIssue(
                        code=ErrorCode.WRITE_RESULT_CONFLICT.value,
                        path=f"/candidateDataBindings/{other_index}/writeResultTo",
                        message=(
                            "数据写入路径与另一候选路径相同、互为父子或相互覆盖。"
                        ),
                        expected=(
                            "与 "
                            f"/candidateDataBindings/{index}/writeResultTo 不重叠的 /data 路径"
                        ),
                        actualType="string",
                        agentAction=AgentAction.FIX_AND_RETRY,
                        retryable=True,
                        capabilityId=other.capabilityId,
                        repairInstruction=(
                            "使用各数据 schema 的 defaultWriteResultTo 重建写入路径；"
                            "若仍冲突，为后一个候选选择独立且不嵌套的 /data 根路径。"
                        ),
                        referenceSource=(
                            "getDataCapabilitySchemas.dataCapabilities[].defaultWriteResultTo"
                        ),
                    )
                )

    def _resolve_events(
        self,
        candidate_events: list[CandidateEventCandidate],
        effective_bindings: list[CandidateDataBinding],
        data_capabilities: list[DataCapability],
        issues: list[PreflightIssue],
        warnings: list[PreflightIssue],
        removed: list[RemovedCapability],
    ) -> list[EventAction]:
        effective_events: list[EventAction] = []
        capability_by_root: dict[str, DataCapability] = {}
        binding_capability_pairs = zip(
            effective_bindings,
            data_capabilities,
            strict=True,
        )
        for binding, capability in binding_capability_pairs:
            capability_by_root[binding.writeResultTo] = capability
        for index, candidate in enumerate(candidate_events):
            base_path = f"/candidateEventCandidates/{index}"
            capability_id = candidate.capabilityId
            capability = self.registry.get_event_capability(capability_id)
            if capability is None:
                issues.append(
                    self._unknown_issue(
                        f"{base_path}/capabilityId",
                        capability_id,
                        "事件能力未在当前注册表中声明。",
                        reference_source=(
                            "getWidgetCapabilityOverview.eventCapabilities[]"
                        ),
                    )
                )
                continue
            event_issue_count = len(issues)
            action = candidate.action
            if action.call != capability.actionTemplate.call:
                issues.append(
                    self._invalid_issue(
                        "EVENT_CALL_MISMATCH",
                        f"{base_path}/action/call",
                        "事件 call 与注册表动作模板不一致。",
                        capability.actionTemplate.call,
                        capability_id,
                        actual_value=action.call,
                        repair_instruction=(
                            "从本轮能力概述重新完整复制该事件的 actionTemplate 到 action；"
                            "不要自行改写 call 或固定参数。"
                        ),
                        reference_source=_EVENT_SOURCE,
                    )
                )
            self._append_schema_issues(
                action.args,
                capability.parametersSchema,
                f"{base_path}/action/args",
                capability_id,
                "EVENT_ARGUMENT_SCHEMA_INVALID",
                issues,
            )
            template_reference_locations = self._data_reference_locations(
                capability.actionTemplate.args
            )
            template_data_paths = {
                path for path, _location in template_reference_locations
            }
            actual_reference_locations = self._data_reference_locations(action.args)
            actual_reference_locations.extend(
                self._legacy_event_reference_locations(
                    capability_id,
                    action.args,
                    template_reference_locations,
                )
            )
            allowed_actual_paths = self._append_event_reference_issues(
                template_reference_locations,
                actual_reference_locations,
                base_path,
                capability_id,
                issues,
            )
            data_paths = set(template_data_paths)
            data_paths.update(allowed_actual_paths)
            dependency_state = self._event_dependency_state(
                data_paths,
                capability_by_root,
            )
            if dependency_state == "missing":
                removed.append(
                    self._removed_event(
                        capability_id,
                        ErrorCode.NO_EFFECTIVE_CAPABILITY,
                    )
                )
                warnings.append(
                    PreflightIssue(
                        code="EVENT_DATA_DEPENDENCY_REMOVED",
                        path=base_path,
                        message="事件依赖的数据路径没有有效数据绑定，已从本轮候选中移除。",
                        expected="先提供支撑该事件数据路径的有效数据绑定",
                        agentAction=AgentAction.REMOVE_OPTIONAL_CANDIDATE,
                        retryable=True,
                        capabilityId=capability_id,
                        repairInstruction=(
                            "若点击动作是次要需求，删除该事件候选；若是核心需求，"
                            "先修复或补充支撑其数据路径的数据候选，再重新检查权限。"
                        ),
                        referenceSource=f"{_EVENT_SOURCE} + {_DATA_OUTPUT_SOURCE}",
                    )
                )
                continue
            if dependency_state == "invalid":
                issues.append(
                    self._invalid_issue(
                        "EVENT_DATA_PATH_INVALID",
                        f"{base_path}/action/args",
                        "事件引用的数据路径不属于对应数据能力的 outputSchema。",
                        "writeResultTo 与 outputSchema 可推导的数据叶子路径",
                        capability_id,
                        repair_instruction=(
                            "重新复制事件 actionTemplate，并确保其 /data 路径由有效数据候选"
                            "的 writeResultTo 和 outputSchema 支撑。"
                        ),
                        reference_source=f"{_EVENT_SOURCE} + {_DATA_OUTPUT_SOURCE}",
                    )
                )
            if len(issues) == event_issue_count:
                effective_events.append(
                    EventAction(
                        id=capability_id,
                        description=capability.description,
                        call=action.call,
                        args=action.args,
                    )
                )
        return effective_events

    def _append_event_reference_issues(
        self,
        template_references: list[tuple[str, str]],
        actual_references: list[tuple[str, str]],
        base_path: str,
        capability_id: str,
        issues: list[PreflightIssue],
    ) -> list[str]:
        allowed_actual_paths = []
        template_paths = [path for path, _location in template_references]
        for data_path, relative_path in actual_references:
            path_is_allowed = any(
                self._event_reference_matches(data_path, template_path)
                for template_path in template_paths
            )
            if path_is_allowed:
                allowed_actual_paths.append(data_path)
                continue
            issues.append(
                self._invalid_issue(
                    "EVENT_DATA_PATH_INVALID",
                    f"{base_path}/action/args{relative_path}",
                    "事件动态参数引用了注册动作模板未声明的数据路径。",
                    "actionTemplate 动态参数声明的数据路径",
                    capability_id,
                    actual_value=data_path,
                    repair_instruction=(
                        "从本轮能力概述重新复制完整 actionTemplate；"
                        "只允许按 dynamicArguments 描述修改已声明的动态参数。"
                    ),
                    reference_source=_EVENT_SOURCE,
                )
            )

        for template_path, relative_path in template_references:
            references_at_location = [
                actual_path
                for actual_path, actual_location in actual_references
                if actual_location == relative_path
            ]
            has_matching_reference = any(
                self._event_reference_matches(actual_path, template_path)
                for actual_path in references_at_location
            )
            if has_matching_reference or references_at_location:
                continue
            issues.append(
                self._invalid_issue(
                    "EVENT_DATA_REFERENCE_MISSING",
                    f"{base_path}/action/args{relative_path}",
                    "事件动态参数缺少注册动作模板要求的数据引用。",
                    "完整保留 actionTemplate 中声明的数据引用",
                    capability_id,
                    repair_instruction=(
                        "从本轮能力概述重新完整复制 actionTemplate 到 action；"
                        "不要把动态 URI 或数据引用改成不完整的静态字符串。"
                    ),
                    reference_source=_EVENT_SOURCE,
                )
            )
        return allowed_actual_paths

    @staticmethod
    def _legacy_event_reference_locations(
        capability_id: str,
        actual_args: dict[str, Any],
        template_references: list[tuple[str, str]],
    ) -> list[tuple[str, str]]:
        is_weather_event = capability_id == "event.open.weather"
        uses_legacy_uri = actual_args.get("uri") == _LEGACY_WEATHER_URI
        if not is_weather_event or not uses_legacy_uri:
            return []
        return [
            (data_path, relative_path)
            for data_path, relative_path in template_references
            if relative_path == "/uri"
        ]

    def _resolve_assets(
        self,
        asset_ids: list[str],
        issues: list[PreflightIssue],
    ) -> list[AssetCapability]:
        assets: list[AssetCapability] = []
        for index, asset_id in enumerate(asset_ids):
            asset = self.registry.get_asset_capability(asset_id)
            if asset is None:
                issues.append(
                    self._unknown_issue(
                        f"/candidateAssetIds/{index}",
                        asset_id,
                        "素材 ID 未在当前注册表中声明。",
                        reference_source=_ASSET_SOURCE,
                    )
                )
                continue
            assets.append(asset)
        return assets

    def _append_schema_issues(
        self,
        instance: Any,
        schema: dict[str, Any],
        base_path: str,
        capability_id: str,
        issue_code: str,
        issues: list[PreflightIssue],
    ) -> None:
        if not schema:
            return
        validator = Draft202012Validator(schema)
        errors = sorted(validator.iter_errors(instance), key=self._schema_error_key)
        for error in errors:
            locations = self._schema_error_locations(error)
            for location in locations:
                actual_value = _MISSING if error.validator == "required" else error.instance
                schema_node = self._schema_error_node(error, location)
                issues.append(
                    self._invalid_issue(
                        issue_code,
                        f"{base_path}{self._parts_pointer(location)}",
                        self._schema_error_message(error),
                        self._schema_error_expected(error, schema_node),
                        capability_id,
                        actual_value=actual_value,
                        repair_instruction=self._schema_repair_instruction(
                            error,
                            issue_code,
                            location,
                        ),
                        reference_source=self._schema_reference_source(issue_code),
                    )
                )

    @staticmethod
    def _schema_error_key(error: JsonSchemaValidationError) -> tuple[str, str]:
        return "/".join(str(part) for part in error.absolute_path), str(error.validator)

    @staticmethod
    def _schema_error_locations(error: JsonSchemaValidationError) -> list[tuple[Any, ...]]:
        path = tuple(error.absolute_path)
        if error.validator == "required" and isinstance(error.instance, dict):
            required = error.validator_value
            missing = [name for name in required if name not in error.instance]
            return [(*path, name) for name in missing]
        if error.validator == "additionalProperties" and isinstance(error.instance, dict):
            properties = error.schema.get("properties", {})
            extra = sorted(set(error.instance) - set(properties))
            return [(*path, name) for name in extra]
        return [path]

    @staticmethod
    def _schema_error_message(error: JsonSchemaValidationError) -> str:
        messages = {
            "required": "缺少 inputSchema 或参数 schema 声明的必填字段。",
            "additionalProperties": "包含 schema 未声明的字段。",
            "type": "字段类型不符合 schema。",
            "enum": "字段取值不在 schema 允许范围内。",
            "const": "固定事件参数与注册表动作模板不一致。",
            "minimum": "数值小于 schema 允许的最小值。",
            "maximum": "数值大于 schema 允许的最大值。",
            "minLength": "字符串长度小于 schema 允许的最小长度。",
            "maxLength": "字符串长度超过 schema 允许的最大长度。",
            "pattern": "字符串格式不符合 schema 约束。",
        }
        return messages.get(str(error.validator), "字段不符合注册表 schema 约束。")

    @staticmethod
    def _schema_error_node(
        error: JsonSchemaValidationError,
        location: tuple[Any, ...],
    ) -> dict[str, Any]:
        if error.validator == "required" and location:
            properties = error.schema.get("properties", {})
            node = properties.get(str(location[-1]), {})
            return node if isinstance(node, dict) else {}
        return error.schema if isinstance(error.schema, dict) else {}

    @staticmethod
    def _schema_error_expected(
        error: JsonSchemaValidationError,
        schema_node: dict[str, Any],
    ) -> str:
        validator = str(error.validator)
        if validator == "additionalProperties":
            return "仅包含 schema properties 声明的字段"
        expectations = []
        schema_type = schema_node.get("type")
        if schema_type:
            expectations.append(f"JSON 类型 {schema_type}")
        if "const" in schema_node:
            value = json.dumps(
                schema_node["const"],
                ensure_ascii=False,
                separators=(",", ":"),
            )
            expectations.append(f"固定值 {value}")
        elif "enum" in schema_node:
            value = json.dumps(
                schema_node["enum"],
                ensure_ascii=False,
                separators=(",", ":"),
            )
            expectations.append(f"允许值 {value}")
        minimum = schema_node.get("minimum")
        maximum = schema_node.get("maximum")
        if minimum is not None and maximum is not None:
            expectations.append(f"取值范围 {minimum} 至 {maximum}")
        elif minimum is not None:
            expectations.append(f"最小值 {minimum}")
        elif maximum is not None:
            expectations.append(f"最大值 {maximum}")
        min_length = schema_node.get("minLength")
        max_length = schema_node.get("maxLength")
        if min_length is not None:
            expectations.append(f"最小长度 {min_length}")
        if max_length is not None:
            expectations.append(f"最大长度 {max_length}")
        pattern = schema_node.get("pattern")
        if pattern:
            expectations.append(f"匹配格式 {pattern}")
        description = schema_node.get("description")
        if description:
            expectations.append(str(description))
        if expectations:
            return "；".join(expectations)
        value = error.validator_value
        return f"满足 schema 的 {validator}={value} 约束"

    @staticmethod
    def _schema_repair_instruction(
        error: JsonSchemaValidationError,
        issue_code: str,
        location: tuple[Any, ...],
    ) -> str:
        if issue_code == "EVENT_ARGUMENT_SCHEMA_INVALID":
            return (
                "从本轮能力概述重新完整复制该事件的 actionTemplate 到 action，"
                "再仅按 dynamicArguments 描述填写动态字段；固定字段不得改写。"
            )
        field_name = str(location[-1]) if location else "对应字段"
        validator = str(error.validator)
        if validator == "required":
            return (
                f"在 arguments 中补充 {field_name}；优先从原始用户需求提取，"
                "无法唯一确定时询问用户，不要用相邻字段代替。"
            )
        if validator == "additionalProperties":
            return (
                f"删除未声明字段 {field_name}；若本意是其它参数，"
                "改用 inputSchema.properties 中的准确字段名。"
            )
        if validator == "type":
            return (
                "按 inputSchema 改为正确 JSON 类型；不要把数字、布尔值、数组或对象"
                "转换成字符串。"
            )
        if validator in {"enum", "const"}:
            return "使用 expected 中的允许值；固定值不得自由改写。"
        if validator in {"minimum", "maximum"}:
            return (
                "将参数调整到 expected 范围；若这会改变用户核心要求，"
                "停止生成并说明当前能力范围，不要静默降级。"
            )
        return "按 expected 和本轮 inputSchema 修正该字段；无法可靠确定时停止并询问用户。"

    @staticmethod
    def _schema_reference_source(issue_code: str) -> str:
        if issue_code == "EVENT_ARGUMENT_SCHEMA_INVALID":
            return (
                "getWidgetCapabilityOverview.eventCapabilities[].actionTemplate/"
                "dynamicArguments"
            )
        return _DATA_INPUT_SOURCE

    @classmethod
    def _binding_value_paths(
        cls,
        value: Any,
        parts: tuple[Any, ...] = (),
    ) -> list[str]:
        if isinstance(value, str):
            has_binding_marker = "{{" in value or "}}" in value or "${" in value
            return [cls._parts_pointer(parts)] if has_binding_marker else []
        if isinstance(value, dict):
            is_path_binding = set(value) == {"path"}
            is_format_call = value.get("call") == "formatString"
            if is_path_binding or is_format_call:
                return [cls._parts_pointer(parts)]
            paths = []
            for name, child in value.items():
                paths.extend(cls._binding_value_paths(child, (*parts, name)))
            return paths
        if isinstance(value, list):
            paths = []
            for index, child in enumerate(value):
                paths.extend(cls._binding_value_paths(child, (*parts, index)))
            return paths
        return []

    @classmethod
    def _data_reference_locations(
        cls,
        value: Any,
        parts: tuple[Any, ...] = (),
    ) -> list[tuple[str, str]]:
        if isinstance(value, str):
            location = cls._parts_pointer(parts)
            return [
                (path, location)
                for path in expression_references(value)
                if path.startswith("/data/")
            ]
        if isinstance(value, dict):
            path = value.get("path") if set(value) == {"path"} else None
            if isinstance(path, str) and path.startswith("/data/"):
                return [(path, cls._parts_pointer(parts))]
            references = []
            for name, child in value.items():
                references.extend(
                    cls._data_reference_locations(child, (*parts, name))
                )
            return references
        if isinstance(value, list):
            references = []
            for index, child in enumerate(value):
                references.extend(
                    cls._data_reference_locations(child, (*parts, index))
                )
            return references
        return []

    @staticmethod
    def _event_reference_matches(actual: str, template: str) -> bool:
        actual_parts = parse_json_pointer(actual)
        template_parts = parse_json_pointer(template)
        if actual_parts is None or template_parts is None:
            return False
        if len(actual_parts) != len(template_parts):
            return False
        for actual_part, template_part in zip(
            actual_parts,
            template_parts,
            strict=True,
        ):
            template_is_array_placeholder = template_part == "i"
            actual_is_array_index = actual_part.isdigit()
            if actual_part != template_part and not (
                template_is_array_placeholder and actual_is_array_index
            ):
                return False
        return True

    @classmethod
    def _event_dependency_state(
        cls,
        paths: Iterable[str],
        capability_by_root: dict[str, DataCapability],
    ) -> str:
        for path in paths:
            match = cls._matching_root(path, capability_by_root)
            if match is None:
                return "missing"
            root, capability = match
            relative_path = path.removeprefix(root)
            if not relative_path:
                continue
            if not cls._schema_path_exists(capability.outputSchema, relative_path):
                return "invalid"
        return "valid"

    @staticmethod
    def _matching_root(
        path: str,
        capability_by_root: dict[str, DataCapability],
    ) -> tuple[str, DataCapability] | None:
        matches = [
            (root, capability)
            for root, capability in capability_by_root.items()
            if path == root or path.startswith(f"{root.rstrip('/')}/")
        ]
        if not matches:
            return None
        return max(matches, key=lambda item: len(item[0]))

    @staticmethod
    def _schema_path_exists(schema: dict[str, Any], pointer: str) -> bool:
        parts = parse_json_pointer(pointer)
        if not parts:
            return False
        current = schema
        for part in parts:
            schema_type = current.get("type")
            if schema_type == "object":
                child = current.get("properties", {}).get(part)
                if not isinstance(child, dict):
                    return False
                current = child
                continue
            if schema_type == "array":
                valid_array_part = part == "i" or part.isdigit()
                items = current.get("items")
                if not valid_array_part or not isinstance(items, dict):
                    return False
                current = items
                continue
            return False
        return current.get("type") not in {"object", "array"}

    @staticmethod
    def _paths_conflict(first: str, second: str) -> bool:
        first_path = first.rstrip("/")
        second_path = second.rstrip("/")
        return (
            first_path == second_path
            or first_path.startswith(f"{second_path}/")
            or second_path.startswith(f"{first_path}/")
        )

    @staticmethod
    def _parts_pointer(parts: tuple[Any, ...]) -> str:
        return "".join(
            "/" + str(part).replace("~", "~0").replace("/", "~1")
            for part in parts
        )

    @staticmethod
    def _actual_type(value: Any) -> str:
        if value is _MISSING:
            return ""
        if value is None:
            return "null"
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, str):
            return "string"
        if isinstance(value, int):
            return "integer"
        if isinstance(value, float):
            return "number"
        if isinstance(value, list):
            return "array"
        if isinstance(value, dict):
            return "object"
        return type(value).__name__

    @classmethod
    def _invalid_issue(
        cls,
        code: str,
        path: str,
        message: str,
        expected: str,
        capability_id: str,
        *,
        actual_value: Any = _MISSING,
        repair_instruction: str = "",
        reference_source: str = "",
    ) -> PreflightIssue:
        return PreflightIssue(
            code=code,
            path=path,
            message=message,
            expected=expected,
            actualType=cls._actual_type(actual_value),
            agentAction=AgentAction.FIX_AND_RETRY,
            retryable=True,
            capabilityId=capability_id,
            repairInstruction=repair_instruction,
            referenceSource=reference_source,
        )

    @staticmethod
    def _unknown_issue(
        path: str,
        capability_id: str,
        message: str,
        *,
        reference_source: str,
    ) -> PreflightIssue:
        return PreflightIssue(
            code=ErrorCode.UNKNOWN_CAPABILITY.value,
            path=path,
            message=message,
            expected="重新获取能力概述，并只使用本轮返回的 ID",
            actualType="string",
            agentAction=AgentAction.REFRESH_CAPABILITIES,
            retryable=True,
            capabilityId=capability_id,
            repairInstruction=(
                "重新调用本轮能力概述；只从 referenceSource 对应列表选择 ID。"
                "数据候选变化后重新加载 schema 并检查权限。"
            ),
            referenceSource=reference_source,
        )

    @staticmethod
    def _removed_event(
        capability_id: str,
        reason: ErrorCode,
    ) -> RemovedCapability:
        return RemovedCapability(
            id=capability_id,
            type="event",
            reason=reason.value,
            userReadableReason="依赖的数据能力不可用",
        )
