"""模板 Provider 与单模板禁用配置。"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

_DEFAULT_CONFIG_PATH = Path(__file__).with_name("config") / "template_controls.json"


class TemplateControls(BaseModel):
    """模板模块内部的只读细粒度管控配置。"""

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)

    schema_version: Literal["template-controls/1"] = Field(alias="schemaVersion")
    disabled_provider_ids: tuple[str, ...] = Field(
        default=(),
        alias="disabledProviderIds",
    )
    disabled_template_ids: tuple[str, ...] = Field(
        default=(),
        alias="disabledTemplateIds",
    )
    first_layer_component_selector: Literal["search", "llm"] = Field(
        default="search",
        alias="firstLayerComponentSelector",
    )

    @model_validator(mode="after")
    def disabled_ids_are_unique(self) -> TemplateControls:
        if len(self.disabled_provider_ids) != len(set(self.disabled_provider_ids)):
            raise ValueError("disabled Template Provider IDs must be unique")
        if len(self.disabled_template_ids) != len(set(self.disabled_template_ids)):
            raise ValueError("disabled Template IDs must be unique")
        return self


@lru_cache(maxsize=4)
def load_template_controls(path: Path | None = None) -> TemplateControls:
    """读取并严格校验模板模块内的管控配置。"""
    config_path = path or _DEFAULT_CONFIG_PATH
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"Template controls config is unavailable: {config_path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Template controls config must be a JSON object")
    try:
        return TemplateControls.model_validate(payload)
    except ValidationError as exc:
        raise ValueError("Template controls config is invalid") from exc


__all__ = ["TemplateControls", "load_template_controls"]
