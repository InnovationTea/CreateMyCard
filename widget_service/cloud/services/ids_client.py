# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import base64
import binascii
import hashlib
import hmac
import json
import time
import traceback
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import requests

from app.logger import logger
from config.config import get_settings
from models.generation import DeviceContext
from models.service import (
    IDSHttpRequest,
    IDSInstalledAppsQueryBody,
    IDSNamespaceQuery,
    IDSQueryKeys,
    IDSQueryRequestData,
    IDSRequestHeaders,
)
from services.json_loader import load_json


@dataclass(frozen=True)
class IDSDeviceCapabilityState:
    """微服务内部使用的 IDS 能力状态快照。

    入参：
    - installed_apps：设备已安装应用，key 为包名，value 为版本号。
    - providers：设备当前可用的数据 provider ID 集合。
    - intent_targets：设备当前可用的意图入口 ID 集合。
    - permissions：设备权限状态，key 为权限名，value 为 GRANTED、DENIED 或 UNKNOWN。
    出参：不可变数据对象，供能力过滤流程读取。
    """

    installed_apps: dict[str, str] = field(default_factory=dict)
    providers: set[str] = field(default_factory=set)
    intent_targets: set[str] = field(default_factory=set)
    permissions: dict[str, str] = field(default_factory=dict)


class IDSClient:
    """IDS 查询客户端。

    优先读取 mock IDS 响应文件；没有 mock 文件时会按 Postman 样例结构真实请求 IDS。
    `DeviceCapabilityResolver` 始终消费稳定的 `IDSDeviceCapabilityState`。
    """

    def __init__(self, mock_response_path: Path | None = None) -> None:
        """初始化 IDS 客户端。

        入参：
        - mock_response_path：可选 mock IDS 响应路径；不传时读取全局配置。
        出参：无。
        """
        self.settings = get_settings()
        # 测试和本地调试可显式传入文件路径；路径不存在时自动走真实 IDS 查询。
        self.mock_response_path = (
            mock_response_path or self.settings.resolved_mock_ids_response_path
        )

    def build_installed_apps_query(
        self,
        device: DeviceContext,
        request_id: str,
    ) -> IDSHttpRequest:
        """构造 IDS 已安装应用查询请求。

        入参：
        - device：工具层注入的设备信息，优先使用 odid，兜底使用 deviceId。
        - request_id：本次 IDS 查询请求 ID。
        出参：结构化 IDS HTTP 请求定义；后续真实 HTTP 调用可直接使用。
        """
        # 请求结构来自一次性 Postman 导出样例，代码内固化成实体对象后不再依赖 collection 文件。
        odid = device.odid or device.deviceId or ""
        body = IDSInstalledAppsQueryBody(
            requestId=request_id,
            callingUid=self.settings.ids_calling_uid,
            nameSpaces=[
                IDSNamespaceQuery(
                    dataType="t_ids_kv_ohos_installed_apps",
                    queryRequestData=[
                        IDSQueryRequestData(keys=IDSQueryKeys(odid=odid)),
                    ],
                )
            ],
        )
        ids_sign = self.build_ids_sign(
            timestamp_ms=int(time.time() * 1000),
        )
        logger.info(
            f"ids_installed_apps_query_built request_id={request_id} odid={odid} "
            f"body={body.model_dump(mode='json')} ids_sign_preview={ids_sign[:8]}"
        )
        return IDSHttpRequest(
            method="POST",
            url=self.settings.ids_query_url,
            headers=IDSRequestHeaders(
                **{
                    "Content-Type": "application/json",
                    "devFakeId": self.settings.ids_dev_fake_id,
                    "idsSign": ids_sign,
                }
            ),
            body=body,
        )

    def build_ids_sign(
        self,
        timestamp_ms: int | None = None,
    ) -> str:
        """生成 IDS 请求签名。

        入参：
        - timestamp_ms：毫秒时间戳；不传时使用当前时间。
        出参：`accessKey;timestamp;sign` 格式的 IDS 签名字符串。
        """
        # 对齐 ids.json 的 Postman 前置脚本：
        # idsSign = accessKey + ";" + ts + ";" + sign，
        # sign = Base64(HMAC-SHA256(accessKey + ts, Base64(secretKey)))。
        ts = timestamp_ms or int(time.time() * 1000)
        access_key = self.settings.ids_access_key
        secret_key_bytes = self._decode_ids_secret_key(self.settings.ids_secret_key)
        sign_source = f"{access_key}{ts}".encode()
        digest = hmac.new(secret_key_bytes, sign_source, hashlib.sha256).digest()
        sign = base64.b64encode(digest).decode("utf-8")
        return f"{access_key};{ts};{sign}"

    def _decode_ids_secret_key(self, secret_key: str) -> bytes:
        """解析 IDS secretKey。

        入参：
        - secret_key：配置中的 secretKey，按 Postman 脚本约定优先视为 Base64。
        出参：HMAC 使用的 key bytes。
        """
        try:
            padding = "=" * (-len(secret_key) % 4)
            return base64.b64decode(secret_key + padding, validate=True)
        except (ValueError, binascii.Error):
            # 本地 dummy 配置可能不是合法 Base64；兜底使用原始字符串，避免本地启动直接失败。
            return secret_key.encode("utf-8")

    def get_device_capability_state(
        self,
        device: DeviceContext,
        request_id: str,
    ) -> IDSDeviceCapabilityState:
        """获取设备能力状态。

        入参：
        - device：工具层注入的设备信息，用于构造 IDS 查询条件。
        - request_id：本次 IDS 查询请求 ID。
        出参：标准化后的 IDSDeviceCapabilityState，供数据能力和事件能力过滤使用。
        """
        # get_device_capability_state 与 build_installed_apps_query 是同一条链路：
        # 先根据 device 生成 IDS 查询请求，再决定走 mock 文件还是真实 IDS 请求。
        ids_query = self.build_installed_apps_query(device, request_id)
        logger.info(
            f"ids_device_capability_query_prepared request_id={request_id} "
            f"method={ids_query.method} url={ids_query.url} "
            f"headers={self._safe_headers_for_log(ids_query)} "
            f"body={ids_query.body.model_dump(mode='json')}"
        )
        if self.mock_response_path.exists():
            # mock 文件沿用 docs/ids_res.txt 的原始 IDS JSON 结构。
            logger.info(f"ids_mock_response_loading path={self.mock_response_path}")
            payload = load_json(self.mock_response_path)
        else:
            # 没有 mock 文件时发起真实 IDS 请求；真实返回结构应与 mock 文件一致。
            logger.info(
                f"ids_mock_response_not_found_use_remote path={self.mock_response_path} "
                f"url={ids_query.url}"
            )
            payload = self._query_remote_ids(ids_query, request_id)
        state = self._parse_ids_payload(payload)
        logger.info(
            f"ids_device_capability_state_loaded request_id={request_id} "
            f"installed_app_count={len(state.installed_apps)} "
            f"provider_count={len(state.providers)} "
            f"intent_count={len(state.intent_targets)} "
            f"permission_count={len(state.permissions)}"
        )
        return state

    def _query_remote_ids(
        self,
        ids_query: IDSHttpRequest,
        request_id: str,
    ) -> dict[str, Any]:
        """真实请求 IDS 查询接口。

        入参：
        - ids_query：结构化 IDS HTTP 请求定义。
        - request_id：本次 IDS 查询请求 ID。
        出参：IDS 原始 JSON 响应；请求失败时返回空 nameSpaces，避免生成流程异常中断。
        """
        # URL 若仍保留 Postman 占位符，说明部署环境还没配置真实 IDS 地址。
        if "{{" in ids_query.url or "}}" in ids_query.url:
            logger.error(
                f"ids_remote_query_url_not_configured request_id={request_id} "
                f"url={ids_query.url}"
            )
            return {"nameSpaces": []}

        try:
            logger.info(
                f"ids_remote_query_started request_id={request_id} "
                f"method={ids_query.method} url={ids_query.url} "
                f"timeout_seconds={self.settings.ids_request_timeout_seconds}"
            )
            response = requests.request(
                method=ids_query.method,
                url=ids_query.url,
                json=ids_query.body.model_dump(mode="json"),
                timeout=self.settings.ids_request_timeout_seconds,
                headers=ids_query.headers.model_dump(mode="json", by_alias=True),
                stream=False,
                verify=False,
                allow_redirects=False,
            )
            logger.info(
                f"ids_remote_query_response_received request_id={request_id} "
                f"status_code={response.status_code} response_bytes={len(response.content)}"
            )
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, dict):
                logger.error(
                    f"ids_remote_query_invalid_response_type request_id={request_id} "
                    f"response_type={type(payload).__name__}"
                )
                return {"nameSpaces": []}
            logger.debug(
                f"ids_remote_query_payload_loaded request_id={request_id} "
                f"namespace_count={len(payload.get('nameSpaces', []))}"
            )
            return payload
        except (requests.RequestException, json.JSONDecodeError, ValueError) as exc:
            logger.error(
                f"ids_remote_query_failed request_id={request_id} error={exc} "
                f"exception_type={type(exc).__name__} exception={exc!r} "
                f"traceback={traceback.format_exc()}"
            )
            return {"nameSpaces": []}

    def _safe_headers_for_log(self, ids_query: IDSHttpRequest) -> dict[str, Any]:
        """生成可打印的 IDS 请求头。

        入参：
        - ids_query：结构化 IDS HTTP 请求定义。
        出参：脱敏后的请求头字典。
        """
        headers = ids_query.headers.model_dump(mode="json", by_alias=True)
        if "idsSign" in headers:
            headers["idsSign"] = f"{headers['idsSign'][:8]}***"
        return headers

    def _parse_ids_payload(self, payload: dict[str, Any]) -> IDSDeviceCapabilityState:
        """解析 IDS 原始响应。

        入参：
        - payload：IDS 原始 JSON 响应。
        出参：转换后的设备能力状态。
        """
        installed_apps: dict[str, str] = {}
        providers: set[str] = set()
        intent_targets: set[str] = set()
        permissions: dict[str, str] = {}

        for namespace in payload.get("nameSpaces", []):
            # dataType 决定当前 namespace 存的是安装应用、provider、intent 还是权限。
            data_type = namespace.get("dataType", "")
            values = namespace.get("values", [])

            if data_type == "t_ids_kv_ohos_installed_apps":
                # 安装应用列表需要转成 packageName -> versionName，供依赖版本检查使用。
                installed_apps.update(self._collect_installed_apps(values))
            elif "provider" in data_type.lower():
                # provider ID 是数据能力可用性的关键依据。
                providers.update(self._collect_ids(values, "provider"))
            elif "intent" in data_type.lower():
                # intent target 是点击事件能力可用性的关键依据。
                intent_targets.update(self._collect_ids(values, "intent"))
            elif "permission" in data_type.lower():
                # 权限状态影响后续是否允许生成需要授权的数据能力。
                permissions.update(self._collect_permissions(values))

        logger.debug(
            f"ids_payload_parsed installed_app_count={len(installed_apps)} "
            f"provider_count={len(providers)} intent_count={len(intent_targets)} "
            f"permission_count={len(permissions)}"
        )
        return IDSDeviceCapabilityState(
            installed_apps=installed_apps,
            providers=providers | self._default_providers(),
            intent_targets=intent_targets | self._default_intents(),
            permissions=permissions,
        )

    def _collect_installed_apps(self, values: list[dict[str, Any]]) -> dict[str, str]:
        """从 IDS values 中收集已安装应用。

        入参：
        - values：安装应用 namespace 下的 values 列表。
        出参：包名到版本号的映射。
        """
        installed_apps: dict[str, str] = {}
        for value in values:
            data = value.get("data", {})
            bundle_name = data.get("bundleName")
            version_name = data.get("versionName", "0.0.0")
            if bundle_name:
                installed_apps[bundle_name] = version_name
        return installed_apps

    def _collect_permissions(self, values: list[dict[str, Any]]) -> dict[str, str]:
        """从 IDS values 中收集权限状态。

        入参：
        - values：权限 namespace 下的 values 列表。
        出参：权限名到权限状态的映射。
        """
        permissions: dict[str, str] = {}
        for value in values:
            data = value.get("data", {})
            permission = data.get("permission") or data.get("name")
            status = data.get("status")
            if permission and status:
                permissions[permission] = status
        return permissions

    def _collect_ids(self, values: list[dict[str, Any]], key_hint: str) -> set[str]:
        """从 IDS values 中按字段名特征收集 ID。

        入参：
        - values：IDS 命名空间下的 values 列表。
        - key_hint：字段名关键词，例如 provider 或 intent。
        出参：收集到的 ID 集合。
        """
        result: set[str] = set()
        for value in values:
            data = value.get("data", {})
            for key, item in data.items():
                # IDS 字段命名可能有 providerId、providerName、intentName 等差异，所以按关键词匹配。
                if key_hint.lower() in key.lower() and isinstance(item, str):
                    result.add(item)
        return result

    def _default_providers(self) -> set[str]:
        """获取 mock 阶段默认可用的一方 provider。

        入参：无。
        出参：默认 provider ID 集合。
        """
        # mock 数据不一定覆盖所有一方系统 provider，先补充一期链路需要的稳定 provider。
        return {
            "UG.weather.current",
            "UG.weather.forecast",
            "UG.calendar.events.search",
            "UG.system.battery.status",
            "UG.health.sleep.summary",
        }

    def _default_intents(self) -> set[str]:
        """获取 mock 阶段默认可用的一方 intent target。

        入参：无。
        出参：默认 intent target 集合。
        """
        # mock 数据不一定覆盖所有一方系统入口，先补充一期链路需要的稳定入口。
        return {
            "OpenWeather",
            "ViewCalendarEvent",
            "StartNavigate",
            "SetSettingSwitch",
            "OpenPowerSaving",
            "OpenHealth",
        }
