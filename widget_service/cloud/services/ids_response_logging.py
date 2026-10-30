"""IDS 响应的有界诊断摘要，不记录完整设备安装清单。"""

from typing import Any

_STATUS_KEYS = (
    "retCode", "description", "code", "message", "errorCode", "errorMsg", "status", "success"
)
_INSTALLED_APPS_TYPE = "t_ids_kv_ohos_installed_apps"
_MAX_NAMESPACES = 20
_MAX_TEXT_LENGTH = 512


def _status_fields(value: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key in _STATUS_KEYS:
        if key not in value:
            continue
        item = value.get(key)
        if isinstance(item, str):
            result[key] = item[:_MAX_TEXT_LENGTH]
            if len(item) > _MAX_TEXT_LENGTH:
                result[f"{key}Truncated"] = True
        elif item is None or isinstance(item, (bool, int, float)):
            result[key] = item
        else:
            result[key] = {"type": type(item).__name__}
    return result


def _namespace_summary(namespace: Any) -> dict[str, Any]:
    result: dict[str, Any] = {"type": type(namespace).__name__}
    if not isinstance(namespace, dict):
        return result
    result["status"] = _status_fields(namespace)
    data_type = namespace.get("dataType")
    result["dataType"] = data_type[:_MAX_TEXT_LENGTH] if isinstance(data_type, str) else None
    result["dataTypeType"] = type(data_type).__name__
    values = namespace.get("values")
    result["valuesPresent"] = "values" in namespace
    result["valuesType"] = type(values).__name__
    if not isinstance(values, list):
        return result
    result["valuesCount"] = len(values)
    bundle_records = 0
    malformed_records = 0
    for value in values:
        if not isinstance(value, dict):
            malformed_records += 1
            continue
        data = value.get("data")
        if not isinstance(data, dict):
            malformed_records += 1
            continue
        bundle_name = data.get("bundleName")
        if isinstance(bundle_name, str) and bundle_name:
            bundle_records += 1
        else:
            malformed_records += 1
    result["bundleRecordCount"] = bundle_records
    result["missingOrInvalidBundleRecordCount"] = malformed_records
    return result


def ids_response_diagnostic(payload: Any) -> dict[str, Any]:
    """仅描述响应形态与状态原值，不将未知业务状态码解释为成功或失败。"""
    result: dict[str, Any] = {"payloadType": type(payload).__name__}
    if not isinstance(payload, dict):
        result["reason"] = "payload_not_object"
        return result
    result["status"] = _status_fields(payload)
    namespaces = payload.get("nameSpaces")
    result["nameSpacesPresent"] = "nameSpaces" in payload
    result["nameSpacesType"] = type(namespaces).__name__
    if "nameSpaces" not in payload:
        result["reason"] = "namespaces_missing"
    elif not isinstance(namespaces, list):
        result["reason"] = "namespaces_not_list"
    else:
        summaries = []
        installed_namespace_count = 0
        for index, namespace in enumerate(namespaces):
            if isinstance(namespace, dict):
                if namespace.get("dataType") == _INSTALLED_APPS_TYPE:
                    installed_namespace_count += 1
            if index < _MAX_NAMESPACES:
                summaries.append(_namespace_summary(namespace))
        result["namespaceCount"] = len(namespaces)
        result["installedNamespaceCount"] = installed_namespace_count
        result["namespaces"] = summaries
        result["namespacesTruncated"] = len(namespaces) > _MAX_NAMESPACES
        result["reason"] = "installed_namespace_found"
        if not namespaces:
            result["reason"] = "namespaces_empty"
        elif not installed_namespace_count:
            result["reason"] = "installed_namespace_missing"
    return result
