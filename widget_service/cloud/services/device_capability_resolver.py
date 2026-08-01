# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
from typing import Any

from jsonschema import Draft202012Validator

from app.logger import json_for_log, logger
from config.config import get_settings
from core.errors import ErrorCode
from core.json_pointer import parse_json_pointer
from models.capability import (
    AssetCapability,
    DataCapability,
    EventCapability,
    RemovedCapability,
)
from models.generation import CandidateDataBinding, DeviceContext
from services.capability_registry import CapabilityRegistry
from services.ids_client import IDSClient, IDSDeviceCapabilityState

_MODULE = "[Device Resolver]"


class DeviceCapabilityResolver:
    """基于 IDS 已安装包名和注册表依赖解析能力。"""

    def __init__(self, registry: CapabilityRegistry) -> None:
        """初始化设备能力解析器。"""
        self.registry = registry
        self.ids_client = IDSClient()
        self.settings = get_settings()
        self.ids_installation_filter_package_names = frozenset(
            package_name
            for package_name in self.settings.ids_installation_filter_package_names
            if package_name
        )

    def resolve_capability_overview(
        self,
        device: DeviceContext,
        ids_state: IDSDeviceCapabilityState | None = None,
    ) -> tuple[
        list[DataCapability],
        list[EventCapability],
        list[AssetCapability],
        list[RemovedCapability],
    ]:
        """按配置范围内的依赖包名过滤能力，供第一个接口返回。"""
        registered_data_capabilities = self.registry.list_data_capabilities()
        registered_event_capabilities = self.registry.list_event_capabilities()
        registered_capabilities = [
            *registered_data_capabilities,
            *registered_event_capabilities,
        ]
        ids_query_status = "provided"
        ids_source = "provided"
        if ids_state is None:
            if self._has_ids_filtered_dependency(registered_capabilities):
                ids_state = self.ids_client.get_device_capability_state(
                    device,
                    "get-widget-capability-overview",
                )
                ids_query_status = "queried"
                ids_source = "mock" if self.settings.enable_ids_mock else "remote"
            else:
                ids_state = IDSDeviceCapabilityState()
                ids_query_status = "skipped_no_dependency_in_filter_scope"
                ids_source = "none"
        data_capabilities: list[DataCapability] = []
        event_capabilities: list[EventCapability] = []
        removed: list[RemovedCapability] = []

        for capability in registered_data_capabilities:
            reason = self._check_required_packages(capability, ids_state)
            if reason is None:
                data_capabilities.append(capability)
            else:
                removed.append(self._removed(capability.id, reason, "data"))

        for capability in registered_event_capabilities:
            reason = self._check_required_packages(capability, ids_state)
            if reason is None:
                event_capabilities.append(capability)
            else:
                removed.append(self._removed(capability.id, reason, "event"))

        # 素材不依赖应用安装状态；本阶段不执行版本过滤。
        asset_capabilities = self.registry.list_asset_capabilities()
        checked_capabilities = [
            capability
            for capability in registered_capabilities
            if self._checked_required_package_names(capability)
        ]
        checked_package_names = {
            package_name
            for capability in checked_capabilities
            for package_name in self._checked_required_package_names(capability)
        }
        installed_package_names = set(ids_state.installed_apps)
        dependency_filter_result = {
            "idsSource": ids_source,
            "idsQueryStatus": ids_query_status,
            "filterPackages": sorted(self.ids_installation_filter_package_names),
            "checkedCapabilityIds": [
                capability.id for capability in checked_capabilities
            ],
            "checkedPackages": sorted(checked_package_names),
            "matchedPackages": sorted(
                checked_package_names & installed_package_names
            ),
            "missingPackages": sorted(
                checked_package_names - installed_package_names
            ),
            "installedPackageCount": len(installed_package_names),
            "availableDataCapabilityCount": len(data_capabilities),
            "availableEventCapabilityCount": len(event_capabilities),
            "availableAssetCapabilityCount": len(asset_capabilities),
            "removedCapabilities": [
                {
                    "id": capability.id,
                    "type": capability.type,
                    "reason": capability.reason,
                }
                for capability in removed
                if capability.reason == ErrorCode.PACKAGE_NOT_INSTALLED.value
            ],
        }
        logger.info(
            f"{_MODULE} capability_package_dependency_checked "
            f"result={json_for_log(dependency_filter_result)}"
        )
        return data_capabilities, event_capabilities, asset_capabilities, removed

    def resolve_generation_data_bindings(
        self,
        candidate_bindings: list[CandidateDataBinding],
    ) -> tuple[list[CandidateDataBinding], list[DataCapability], list[RemovedCapability]]:
        """在生成阶段只校验绑定结构，不重复执行设备依赖可用性过滤。"""
        effective_bindings: list[CandidateDataBinding] = []
        effective_capabilities: list[DataCapability] = []
        removed: list[RemovedCapability] = []

        for binding in candidate_bindings:
            capability = self.registry.get_data_capability(binding.capabilityId)
            if capability is None:
                removed.append(self._removed(binding.capabilityId, ErrorCode.UNKNOWN_CAPABILITY))
                continue
            if not self._valid_arguments(binding.arguments, capability.inputSchema):
                removed.append(self._removed(binding.capabilityId, ErrorCode.INVALID_ARGUMENTS))
                continue
            write_result_to = binding.writeResultTo
            write_parts = parse_json_pointer(write_result_to or "")
            if write_parts is None or len(write_parts) < 2 or write_parts[0] != "data":
                removed.append(self._removed(binding.capabilityId, ErrorCode.INVALID_ARGUMENTS))
                continue
            effective_bindings.append(
                CandidateDataBinding(
                    capabilityId=binding.capabilityId,
                    arguments=binding.arguments,
                    writeResultTo=write_result_to,
                    candidateOutputFields=binding.candidateOutputFields,
                )
            )
            effective_capabilities.append(capability)

        conflict_id = self._find_write_result_conflict(effective_bindings)
        if conflict_id:
            effective_bindings = [
                item for item in effective_bindings if item.capabilityId != conflict_id
            ]
            effective_capabilities = [
                item for item in effective_capabilities if item.id != conflict_id
            ]
            removed.append(self._removed(conflict_id, ErrorCode.WRITE_RESULT_CONFLICT))

        return effective_bindings, effective_capabilities, removed

    def _check_required_packages(
        self,
        capability: DataCapability | EventCapability,
        ids_state: IDSDeviceCapabilityState,
    ) -> ErrorCode | None:
        """仅精确匹配配置范围内的依赖包名。"""
        checked_package_names = self._checked_required_package_names(capability)
        installed_package_names = set(ids_state.installed_apps)
        missing_package_names = [
            package_name
            for package_name in checked_package_names
            if package_name not in installed_package_names
        ]
        if missing_package_names:
            return ErrorCode.PACKAGE_NOT_INSTALLED
        return None

    def _checked_required_package_names(
        self,
        capability: DataCapability | EventCapability,
    ) -> list[str]:
        """返回当前配置范围内需要 IDS 精确匹配的依赖包名。"""
        return [
            package.packageName
            for package in capability.dependencies.requiredPackages
            if package.packageName in self.ids_installation_filter_package_names
        ]

    def _has_ids_filtered_dependency(
        self,
        capabilities: list[DataCapability | EventCapability],
    ) -> bool:
        """判断当前注册表是否存在需要 IDS 安装校验的依赖包。"""
        return any(
            package.packageName in self.ids_installation_filter_package_names
            for capability in capabilities
            for package in capability.dependencies.requiredPackages
        )

    def _valid_arguments(self, arguments: dict[str, Any], schema: dict[str, Any]) -> bool:
        """校验能力参数是否符合 inputSchema。"""
        if not schema:
            return True
        validator = Draft202012Validator(schema)
        return not list(validator.iter_errors(arguments))

    def _find_write_result_conflict(self, bindings: list[CandidateDataBinding]) -> str | None:
        """检查 writeResultTo 是否相同或互为父子路径。"""
        paths = [(item.capabilityId, item.writeResultTo or "") for item in bindings]
        for index, (capability_id, path) in enumerate(paths):
            normalized = path.rstrip("/")
            for other_id, other_path in paths[index + 1:]:
                other_normalized = other_path.rstrip("/")
                if (
                    normalized == other_normalized
                    or normalized.startswith(other_normalized + "/")
                    or other_normalized.startswith(normalized + "/")
                ):
                    return other_id or capability_id
        return None

    def _removed(
        self,
        capability_id: str,
        reason: ErrorCode,
        capability_type: str = "data",
    ) -> RemovedCapability:
        """构造被移除能力对象。"""
        readable = {
            ErrorCode.UNKNOWN_CAPABILITY: "能力未注册",
            ErrorCode.PACKAGE_NOT_INSTALLED: "依赖应用未安装",
            ErrorCode.INVALID_ARGUMENTS: "参数不合法",
            ErrorCode.WRITE_RESULT_CONFLICT: "数据写入路径冲突",
        }.get(reason, "能力不可用")
        return RemovedCapability(
            id=capability_id,
            type=capability_type,
            reason=reason.value,
            userReadableReason=readable,
        )
