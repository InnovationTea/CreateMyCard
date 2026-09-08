# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
import json
import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Any

import yaml

_logger = logging.getLogger(__name__)
_FILE_REFERENCE_PREFIX = "@file:"
_MISSING = object()


class ConfigHelper:
    """优先读取绿区 spec 配置，缺失时回退到蓝区默认配置。"""

    def __init__(self, env: str = "local"):
        if env not in {"local", "cloud"}:
            raise ValueError("env must be 'local' or 'cloud'")

        self.env = env
        self.config_file = self._select_config_file()
        self.config = self._read_config(self.config_file)
        environment = self.get("ENVIRONMENT", env)
        _logger.info("加载环境：%s，配置文件：%s", environment, self.config_file)

    def _select_config_file(self) -> Path:
        spec_path = self._get_spec_config_file()
        if spec_path.is_file():
            return spec_path

        default_path = Path(__file__).with_name("default_config.yaml")
        if not default_path.is_file():
            raise FileNotFoundError(
                f"spec 配置文件不存在：{spec_path}；默认配置文件也不存在：{default_path}"
            )

        _logger.info("spec 配置文件不存在，使用默认配置：%s", default_path)
        return default_path

    def _get_spec_config_file(self) -> Path:
        if self.env == "cloud":
            return Path("/opt/huawei/app/nuwa/service-config/normal/user-config.properties")

        repository_root = Path(__file__).resolve().parents[3]
        return repository_root / (
            "iac3.0/iacpatch/HAG/GenUIAgentService/specs/"
            "cn_dev_default/config/spec_records.yaml"
        )

    def _read_config(self, config_file: Path) -> dict[str, Any]:
        suffix = config_file.suffix.lower()
        with config_file.open("r", encoding="utf-8") as file:
            if suffix in {".yaml", ".yml"}:
                loaded = yaml.safe_load(file)
            elif suffix == ".json":
                loaded = json.load(file)
            else:
                content = file.read()
                if content.lstrip().startswith("{"):
                    loaded = json.loads(content)
                else:
                    loaded = self._read_properties(content.splitlines())

        if not isinstance(loaded, dict):
            raise ValueError(f"配置文件顶层必须是对象：{config_file}")

        normalized = self._normalize_config_value(loaded, config_file.parent)
        if not isinstance(normalized, dict):
            raise ValueError(f"配置文件顶层必须是对象：{config_file}")
        return normalized

    @staticmethod
    def _read_properties(lines: Iterable[str]) -> dict[str, str]:
        properties: dict[str, str] = {}
        for line_number, original_line in enumerate(lines, start=1):
            line = original_line.strip()
            if not line or line.startswith(("#", "!")):
                continue

            key, separator, value = line.partition("=")
            if not separator:
                key, separator, value = line.partition(":")
            if not separator:
                raise ValueError(f"properties 第 {line_number} 行缺少分隔符")
            properties[key.strip()] = value.strip()
        return properties

    def _normalize_config_value(self, value: Any, config_dir: Path) -> Any:
        if isinstance(value, dict):
            return {
                key: self._normalize_config_value(item, config_dir)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [self._normalize_config_value(item, config_dir) for item in value]
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, str) and value.startswith(_FILE_REFERENCE_PREFIX):
            referenced_path = value.removeprefix(_FILE_REFERENCE_PREFIX).strip()
            return (config_dir / referenced_path).resolve().read_text(encoding="utf-8")
        return value

    def _find_value(self, key: str) -> Any:
        if key in self.config:
            return self.config[key]

        value: Any = self.config
        for part in key.split("."):
            if not isinstance(value, dict) or part not in value:
                return _MISSING
            value = value[part]
        return value

    def get(self, key: str, default: Any = _MISSING) -> Any:
        """获取配置值；未提供默认值时，缺失配置会立即报错。"""
        value = self._find_value(key)
        if value is not _MISSING:
            return value
        if default is not _MISSING:
            return default
        raise KeyError(f"config key does not exist: {key}")

    def __getitem__(self, key: str) -> Any:
        return self.get(key)

    def __contains__(self, key: str) -> bool:
        return self._find_value(key) is not _MISSING
