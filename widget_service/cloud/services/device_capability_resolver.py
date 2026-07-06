# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import re
from typing import Any

from jsonschema import Draft202012Validator
from packaging.version import InvalidVersion, Version

from app.logger import logger
from core.errors import ErrorCode
from models.capability import DataCapability, RemovedCapability
from models.generation import CandidateDataBinding, DeviceContext, EventAction
from services.capability_registry import CapabilityRegistry
from services.ids_client import IDSClient, IDSDeviceCapabilityState


class DeviceCapabilityResolver:
    """基于 IDS 状态和注册表依赖解析候选能力。"""

    def __init__(self, registry: CapabilityRegistry) -> None:
        """初始化设备能力解析器。

        入参：
        - registry：当前版本能力注册表。
        出参：无。
        """
        self.registry = registry
        # IDSClient 负责屏蔽 mock IDS 与未来真实 IDS 的差异，Resolver 只处理能力裁决。
        self.ids_client = IDSClient()

    def resolve_data_bindings(
        self,
        candidate_bindings: list[CandidateDataBinding],
        device: DeviceContext,
    ) -> tuple[list[CandidateDataBinding], list[DataCapability], list[RemovedCapability]]:
        """过滤候选数据绑定。

        入参：
        - candidate_bindings：主 Agent 传入的候选数据绑定。
        - device：工具层注入的设备信息，包含 romVersion 和 ohosApiVersion。
        出参：有效数据绑定、有效数据能力定义、被移除能力列表。
        """
        # 先获取设备侧真实能力快照，再用这份快照裁剪主 Agent 传入的候选能力。
        ids_state = self.ids_client.get_device_capability_state(
            device,
            "resolve-data-bindings",
        )
        logger.info(
            f"resolve_data_bindings_started candidate_count={len(candidate_bindings)} "
            f"candidates="
            f"{[item.model_dump(mode='json', exclude_none=True) for item in candidate_bindings]} "
            f"provider_count={len(ids_state.providers)} "
            f"intent_count={len(ids_state.intent_targets)}"
        )
        effective_bindings: list[CandidateDataBinding] = []
        effective_capabilities: list[DataCapability] = []
        removed: list[RemovedCapability] = []

        for binding in candidate_bindings:
            # 未注册或不可用的能力不能进入最终 CardSpec。
            logger.info(
                f"data_capability_check_started capability_id={binding.capabilityId} "
                f"arguments={binding.arguments} write_result_to={binding.writeResultTo} "
                f"update_model_keys={list(binding.updateModel.keys())}"
            )
            capability = self.registry.get_data_capability(binding.capabilityId)
            if capability is None:
                logger.warning(
                    f"data_capability_removed capability_id={binding.capabilityId} "
                    f"reason={ErrorCode.UNKNOWN_CAPABILITY.value}"
                )
                removed.append(self._removed(binding.capabilityId, ErrorCode.UNKNOWN_CAPABILITY))
                continue

            # 统一检查 ROM/App/小艺版本、安装包、provider、intent 和权限依赖。
            reason = self._check_common_dependencies(
                capability, device, ids_state
            )
            if reason is not None:
                logger.warning(
                    f"data_capability_removed capability_id={binding.capabilityId} "
                    f"reason={reason.value}"
                )
                removed.append(self._removed(binding.capabilityId, reason))
                continue

            # 参数必须符合能力注册表声明的 inputSchema，否则不允许进入最终 CardSpec。
            if not self._valid_arguments(binding.arguments, capability.inputSchema):
                logger.warning(
                    f"data_capability_removed capability_id={binding.capabilityId} "
                    f"reason={ErrorCode.INVALID_ARGUMENTS.value}"
                )
                removed.append(self._removed(binding.capabilityId, ErrorCode.INVALID_ARGUMENTS))
                continue

            # 主 Agent 可显式指定写入路径；未指定时使用能力注册表默认路径。
            write_result_to = binding.writeResultTo or capability.defaultWriteResultTo
            # CardSpec 数据写入路径必须位于 /data/ 下，方便 DSL 绑定路径可追踪。
            if write_result_to is None or not write_result_to.startswith("/data/"):
                logger.warning(
                    f"data_capability_removed capability_id={binding.capabilityId} "
                    f"reason={ErrorCode.INVALID_ARGUMENTS.value} "
                    f"write_result_to={write_result_to}"
                )
                removed.append(self._removed(binding.capabilityId, ErrorCode.INVALID_ARGUMENTS))
                continue

            # 这里重新封装 CandidateDataBinding，确保后续 CardSpec 使用的是微服务裁决后的写入路径。
            effective_bindings.append(
                CandidateDataBinding(
                    capabilityId=binding.capabilityId,
                    arguments=binding.arguments,
                    writeResultTo=write_result_to,
                    updateModel=binding.updateModel,
                )
            )
            effective_capabilities.append(capability)
            logger.info(
                f"data_capability_check_passed capability_id={binding.capabilityId} "
                f"write_result_to={write_result_to}"
            )

        # 不同能力写入同一路径会让 DataModel 覆盖，必须在最终 CardSpec 生成前剔除。
        conflict_id = self._find_write_result_conflict(effective_bindings)
        if conflict_id:
            logger.warning(
                f"data_capability_removed capability_id={conflict_id} "
                f"reason={ErrorCode.WRITE_RESULT_CONFLICT.value}"
            )
            effective_bindings = [
                item for item in effective_bindings if item.capabilityId != conflict_id
            ]
            effective_capabilities = [
                item for item in effective_capabilities if item.id != conflict_id
            ]
            removed.append(self._removed(conflict_id, ErrorCode.WRITE_RESULT_CONFLICT))

        logger.info(
            f"resolve_data_bindings_completed effective_count={len(effective_bindings)} "
            f"removed_count={len(removed)}"
        )
        return effective_bindings, effective_capabilities, removed

    def resolve_event_candidates(
        self,
        candidates: list[EventAction],
        device: DeviceContext,
    ) -> tuple[list[EventAction], list[RemovedCapability]]:
        """过滤候选事件动作。

        入参：
        - candidates：候选事件动作列表。
        - device：工具层注入的设备信息，包含 romVersion 和 ohosApiVersion。
        出参：有效事件动作列表、被移除事件能力列表。
        """
        # 事件能力和数据能力使用同一份 IDS 状态，确保能力裁决口径一致。
        ids_state = self.ids_client.get_device_capability_state(
            device,
            "resolve-event-candidates",
        )
        logger.info(
            f"resolve_event_candidates_started candidate_count={len(candidates)} "
            f"candidates="
            f"{[item.model_dump(mode='json', exclude_none=True) for item in candidates]} "
            f"intent_count={len(ids_state.intent_targets)}"
        )
        removed: list[RemovedCapability] = []
        effective: list[EventAction] = []

        for candidate in candidates:
            capability_id = candidate.id
            logger.info(
                f"event_capability_check_started capability_id={capability_id} "
                f"call={candidate.call} args={candidate.args}"
            )
            if capability_id:
                # 事件候选必须能在事件能力注册表里找到，否则不能进入 TaskSpec。
                event_capability = self.registry.get_event_capability(capability_id)
                if event_capability is None:
                    logger.warning(
                        f"event_capability_removed capability_id={capability_id} "
                        f"reason={ErrorCode.UNKNOWN_CAPABILITY.value}"
                    )
                    removed.append(
                        self._removed(capability_id, ErrorCode.UNKNOWN_CAPABILITY, "event")
                    )
                    continue
                # 事件能力同样需要经过版本、安装包、intent target 等依赖检查。
                reason = self._check_common_dependencies(
                    event_capability, device, ids_state
                )
                if reason is not None:
                    logger.warning(
                        f"event_capability_removed capability_id={capability_id} "
                        f"reason={reason.value}"
                    )
                    removed.append(self._removed(capability_id, reason, "event"))
                    continue
            # 通过过滤后的事件动作会进入模型 TaskSpec，供 DSL 绑定 onClick 行为。
            effective.append(candidate)
            logger.info(
                f"event_capability_check_passed capability_id={capability_id} "
                f"call={candidate.call}"
            )
        logger.info(
            f"resolve_event_candidates_completed effective_count={len(effective)} "
            f"removed_count={len(removed)}"
        )
        return effective, removed

    def _check_common_dependencies(
        self,
        capability: Any,
        device: DeviceContext,
        ids_state: IDSDeviceCapabilityState,
    ) -> ErrorCode | None:
        """检查能力通用依赖。

        入参：
        - capability：数据能力或事件能力定义。
        - device：工具层注入的设备信息。
        - ids_state：转换后的 IDS 状态。
        出参：不可用原因错误码；全部满足时返回 None。
        """
        dependencies = capability.dependencies
        required_packages = [
            item.model_dump(mode="json", exclude_none=True)
            for item in dependencies.requiredPackages
        ]
        logger.info(
            f"capability_dependency_check_started "
            f"capability_id={getattr(capability, 'id', '')} "
            f"min_rom_version={dependencies.minRomVersion} "
            f"min_app_version={dependencies.minAppVersion} "
            f"required_packages={required_packages} "
            f"required_providers={dependencies.requiredProviders} "
            f"required_intent_targets={dependencies.requiredIntentTargets} "
            f"required_permissions={dependencies.requiredPermissions}"
        )
        # 版本门禁先判断，避免低版本设备进入后续更重的 IDS 依赖判断。
        if dependencies.minRomVersion and not self._version_gte(
            device.romVersion, dependencies.minRomVersion
        ):
            return ErrorCode.ROM_VERSION_UNSUPPORTED
        if dependencies.minAppVersion and not self._version_gte(
            str(device.ohosApiVersion), dependencies.minAppVersion
        ):
            return ErrorCode.APP_VERSION_UNSUPPORTED

        installed_apps = ids_state.installed_apps
        for package in dependencies.requiredPackages:
            installed_version = installed_apps.get(package.packageName)
            if installed_version is None:
                return ErrorCode.PACKAGE_NOT_INSTALLED
            if package.minVersion and not self._version_gte(installed_version, package.minVersion):
                return ErrorCode.PACKAGE_VERSION_TOO_LOW

        providers = ids_state.providers
        for provider in dependencies.requiredProviders:
            if provider not in providers:
                return ErrorCode.PROVIDER_NOT_FOUND

        intent_targets = ids_state.intent_targets
        for target in dependencies.requiredIntentTargets:
            if target not in intent_targets:
                return ErrorCode.INTENT_TARGET_NOT_FOUND

        permissions = ids_state.permissions
        for permission in dependencies.requiredPermissions:
            # IDS 未返回权限时先按 GRANTED 处理，避免 mock 阶段误杀无权限声明的一方能力。
            status = permissions.get(permission, "GRANTED")
            if status == "DENIED":
                return ErrorCode.PERMISSION_DENIED
            if status == "UNKNOWN":
                return ErrorCode.PERMISSION_UNKNOWN

        logger.info(
            f"capability_dependency_check_passed "
            f"capability_id={getattr(capability, 'id', '')}"
        )
        return None

    def _valid_arguments(self, arguments: dict[str, Any], schema: dict[str, Any]) -> bool:
        """校验能力参数是否符合 inputSchema。

        入参：
        - arguments：候选数据绑定参数。
        - schema：能力注册表里的 JSON Schema。
        出参：参数合法返回 True，否则返回 False。
        """
        if not schema:
            return True
        # 使用标准 JSON Schema 校验，避免手写参数判断和注册表声明不一致。
        validator = Draft202012Validator(schema)
        return not list(validator.iter_errors(arguments))

    def _find_write_result_conflict(self, bindings: list[CandidateDataBinding]) -> str | None:
        """检查 writeResultTo 是否冲突。

        入参：
        - bindings：已通过基础过滤的数据绑定列表。
        出参：发生冲突的能力 ID；无冲突时返回 None。
        """
        # 相同路径或父子路径会在 DataModel 中互相覆盖。
        paths = [(item.capabilityId, item.writeResultTo or "") for item in bindings]
        for index, (capability_id, path) in enumerate(paths):
            normalized = path.rstrip("/")
            for other_id, other_path in paths[index + 1 :]:
                other_normalized = other_path.rstrip("/")
                # 同一路径、父路径、子路径都视为冲突，防止一个能力覆盖另一个能力的数据树。
                if (
                    normalized == other_normalized
                    or normalized.startswith(other_normalized + "/")
                    or other_normalized.startswith(normalized + "/")
                ):
                    return other_id or capability_id
        return None

    def _version_gte(self, current: str, minimum: str) -> bool:
        """比较版本号是否满足最低要求。

        入参：
        - current：当前版本。
        - minimum：最低版本。
        出参：当前版本大于等于最低版本时返回 True。
        """
        current = self._extract_version(current)
        minimum = self._extract_version(minimum)
        try:
            # 优先走 packaging.version，能正确处理常规语义化版本比较。
            return Version(current) >= Version(minimum)
        except InvalidVersion:
            # 非标准版本兜底做字符串比较，保证异常版本不会打断整条生成链路。
            return current >= minimum

    def _extract_version(self, value: str) -> str:
        """从复杂版本字符串中提取数字版本。

        入参：
        - value：原始版本字符串。
        出参：数字版本字符串；无法提取时返回 `0`。
        """
        # ROM 字符串可能类似 `ALN-AL00 7.0.0.36`，需要避开机型里的 `00`。
        dotted_matches = re.findall(r"\d+(?:\.\d+)+", value or "")
        if dotted_matches:
            return dotted_matches[-1]
        match = re.search(r"\d+", value or "")
        return match.group(0) if match else "0"

    def _removed(
        self,
        capability_id: str,
        reason: ErrorCode,
        capability_type: str = "data",
    ) -> RemovedCapability:
        """构造被移除能力对象。

        入参：
        - capability_id：能力 ID。
        - reason：移除原因错误码。
        - capability_type：能力类型，默认 data。
        出参：包含内部原因和用户可读原因的 RemovedCapability。
        """
        readable = {
            ErrorCode.UNKNOWN_CAPABILITY: "能力未注册",
            ErrorCode.ROM_VERSION_UNSUPPORTED: "系统版本不支持",
            ErrorCode.APP_VERSION_UNSUPPORTED: "应用版本不支持",
            ErrorCode.PACKAGE_NOT_INSTALLED: "依赖应用未安装",
            ErrorCode.PACKAGE_VERSION_TOO_LOW: "依赖应用版本过低",
            ErrorCode.PROVIDER_NOT_FOUND: "当前设备未提供对应数据源",
            ErrorCode.INTENT_TARGET_NOT_FOUND: "当前设备未提供对应入口",
            ErrorCode.PERMISSION_DENIED: "权限未开启",
            ErrorCode.PERMISSION_UNKNOWN: "权限状态未知",
            ErrorCode.INVALID_ARGUMENTS: "参数不合法",
            ErrorCode.WRITE_RESULT_CONFLICT: "数据写入路径冲突",
        }.get(reason, "能力不可用")
        return RemovedCapability(
            id=capability_id,
            type=capability_type,
            reason=reason.value,
            userReadableReason=readable,
        )
