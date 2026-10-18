"""Load distributed Theme bundles and the shared Theme base contract."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from services.template_generation.engine.advanced.models import UxCardSizeBudget
from services.template_generation.engine.theme_reference import THEME_REFERENCE_PATHS

from .models import ThemeDefinition

_FORBIDDEN_KEYS = frozenset({"__proto__", "prototype", "constructor"})
_MAX_THEME_FILE_BYTES = 262_144
_CONTENT_COLOR_FIELDS = {
    "Button": "fontColor",
    "Checkbox": "selectedColor",
    "Divider": "color",
    "Image": "fillColor",
    "Progress": "color",
    "Text": "fontColor",
}


class ThemeBaseDefinition(BaseModel):
    """Shared style capabilities that are identical for every Theme."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    theme_base_version: Literal["theme-base/2"] = Field(alias="themeBaseVersion")
    ux_tokens: dict[str, int] = Field(alias="uxTokens")
    size_budgets: tuple[UxCardSizeBudget, ...] = Field(alias="sizeBudgets")
    content_color_properties: dict[str, str] = Field(alias="contentColorProperties")
    theme_reference_paths: tuple[str, ...] = Field(alias="themeReferencePaths")

    @field_validator("ux_tokens")
    @classmethod
    def valid_ux_tokens(cls, value: dict[str, int]) -> dict[str, int]:
        if not value or any(not key or item < 0 for key, item in value.items()):
            raise ValueError("Theme base UX Tokens must contain non-negative integers")
        return value

    @field_validator("content_color_properties")
    @classmethod
    def valid_content_color_properties(cls, value: dict[str, str]) -> dict[str, str]:
        if value != _CONTENT_COLOR_FIELDS:
            raise ValueError("Theme base content color properties are incomplete")
        return value

    @field_validator("theme_reference_paths")
    @classmethod
    def valid_theme_reference_paths(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if value != THEME_REFERENCE_PATHS:
            raise ValueError("Theme base reference paths are incomplete")
        return value


@dataclass(frozen=True)
class LoadedThemeResources:
    base: ThemeBaseDefinition
    themes: tuple[ThemeDefinition, ...]
    first_layer_rules: dict[str, str]


def load_theme_resources(themes_root: Path) -> LoadedThemeResources:
    """Load the shared base and every self-contained ``themes/*/theme.json``."""
    root = themes_root.resolve()
    base = ThemeBaseDefinition.model_validate(
        _read_object(root / "base" / "theme-base.json")
    )
    themes: list[ThemeDefinition] = []
    first_layer_rules: dict[str, str] = {}
    for manifest_path in sorted(root.glob("*/theme.json")):
        theme_root = manifest_path.parent.resolve()
        theme = ThemeDefinition.model_validate(_read_object(manifest_path))
        if theme_root.name != theme.theme_profile_id:
            raise ValueError("Theme directory must match themeProfileId")
        if not theme.root_style:
            raise ValueError(f"Theme rootStyle must not be empty: {theme.theme_profile_id}")
        if theme.theme_profile_id in first_layer_rules:
            raise ValueError(f"duplicate CardPlan Theme: {theme.theme_profile_id}")
        first_layer_rules[theme.theme_profile_id] = _load_rule_document(
            theme_root,
            theme.first_layer_rule.path,
        )
        themes.append(theme)
    if not themes:
        raise ValueError("Theme bundle must contain at least one Theme")
    return LoadedThemeResources(base, tuple(themes), first_layer_rules)


def _read_object(path: Path) -> dict[str, Any]:
    payload = json.loads(_bounded_file_bytes(path))
    if not isinstance(payload, dict):
        raise ValueError(f"Theme source must be an object: {path}")
    _reject_forbidden_keys(payload)
    return payload


def _load_rule_document(theme_root: Path, relative_path: str) -> str:
    relative = Path(relative_path)
    if relative.is_absolute() or ".." in relative.parts or relative.suffix.lower() != ".md":
        raise ValueError("Theme first-layer rule path is invalid")
    path = (theme_root / relative).resolve()
    if theme_root not in path.parents or not path.is_file():
        raise ValueError(f"Theme first-layer rule is unavailable: {relative_path}")
    content = _bounded_file_bytes(path).decode("utf-8").strip()
    if not content:
        raise ValueError("Theme first-layer rule must not be empty")
    return content


def _bounded_file_bytes(path: Path) -> bytes:
    if not path.is_file() or path.stat().st_size > _MAX_THEME_FILE_BYTES:
        raise ValueError(f"Theme source is unavailable or too large: {path}")
    return path.read_bytes()


def _reject_forbidden_keys(value: Any) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in _FORBIDDEN_KEYS:
                raise ValueError(f"forbidden Theme source key: {key}")
            _reject_forbidden_keys(child)
    elif isinstance(value, list):
        for child in value:
            _reject_forbidden_keys(child)


__all__ = ["LoadedThemeResources", "ThemeBaseDefinition", "load_theme_resources"]
