# -*- coding: utf-8 -*-
# Copyright (c) Huawei Technologies Co., Ltd. 2026-2026. All rights reserved.
"""Load the versioned visual recipes used by Compact high-level components."""

from __future__ import annotations

import copy
import json
from functools import lru_cache
from pathlib import Path
from typing import Any

VISUAL_RECIPE_VERSION = "visual-recipes-v1"
_CONTRACT_PATH = (
    Path(__file__).resolve().parents[1]
    / "data"
    / "protocol_profiles"
    / "design-compact-dsl-fusion"
    / "runtime"
    / "visual-recipes-v1.json"
)
_ALIGNMENT_VALUES = frozenset({"aligned", "adapted", "native"})


class CompactComponentRuntimeError(ValueError):
    """Raised when the visual recipe contract is unavailable or malformed."""


@lru_cache(maxsize=1)
def _load_contract() -> dict[str, Any]:
    try:
        payload = json.loads(_CONTRACT_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CompactComponentRuntimeError(
            f"Unable to load Compact visual recipe contract: {_CONTRACT_PATH}"
        ) from exc
    _validate_contract(payload)
    return payload


def load_visual_recipe_contract() -> dict[str, Any]:
    """Return an isolated copy of the complete visual recipe contract."""
    return copy.deepcopy(_load_contract())


def component_visual_recipe(
    component_name: str,
    *,
    size: str | None = None,
    variant: str | None = None,
) -> dict[str, Any]:
    """Resolve one component recipe with size and variant overrides applied."""
    components = _load_contract()["components"]
    recipe = components.get(component_name)
    if not isinstance(recipe, dict):
        raise CompactComponentRuntimeError(f"Visual recipe is not registered for {component_name}.")
    resolved = copy.deepcopy(recipe)
    if size is not None:
        size_recipes = recipe.get("sizes", {})
        if not isinstance(size_recipes, dict):
            raise CompactComponentRuntimeError(
                f"Visual recipe sizes must be an object for {component_name}."
            )
        size_recipe = size_recipes.get(size)
        if isinstance(size_recipe, dict):
            resolved = _deep_merge(resolved, size_recipe)
    if variant is not None:
        variants = recipe.get("variants", {})
        if not isinstance(variants, dict):
            raise CompactComponentRuntimeError(
                f"Visual recipe variants must be an object for {component_name}."
            )
        variant_recipe = variants.get(variant)
        if not isinstance(variant_recipe, dict):
            raise CompactComponentRuntimeError(
                f"Visual recipe variant {variant} is not registered for {component_name}."
            )
        resolved = _deep_merge(resolved, variant_recipe)
    return resolved


def visual_recipe_part(
    component_name: str,
    part_name: str,
    *,
    size: str | None = None,
    variant: str | None = None,
) -> tuple[str, dict[str, Any]]:
    """Return the base component type and styles for one named recipe part."""
    recipe = component_visual_recipe(component_name, size=size, variant=variant)
    parts = recipe.get("parts")
    part = parts.get(part_name) if isinstance(parts, dict) else None
    if not isinstance(part, dict):
        raise CompactComponentRuntimeError(
            f"Visual recipe part {component_name}.{part_name} is not registered."
        )
    component_type = part.get("component")
    styles = part.get("styles")
    if not isinstance(component_type, str) or not component_type:
        raise CompactComponentRuntimeError(
            f"Visual recipe part {component_name}.{part_name} has no component type."
        )
    if not isinstance(styles, dict):
        raise CompactComponentRuntimeError(
            f"Visual recipe part {component_name}.{part_name} has invalid styles."
        )
    output_styles = copy.deepcopy(styles)
    output_styles["_visualRecipe"] = f"{VISUAL_RECIPE_VERSION}:{component_name}.{part_name}"
    return component_type, output_styles


def _validate_contract(payload: Any) -> None:
    if not isinstance(payload, dict) or payload.get("version") != VISUAL_RECIPE_VERSION:
        raise CompactComponentRuntimeError(
            f"Compact visual recipe contract must use version {VISUAL_RECIPE_VERSION}."
        )
    components = payload.get("components")
    if not isinstance(components, dict) or not components:
        raise CompactComponentRuntimeError(
            "Compact visual recipe contract must declare components."
        )
    for component_name, recipe in components.items():
        if not isinstance(component_name, str) or not isinstance(recipe, dict):
            raise CompactComponentRuntimeError(
                "Compact visual recipe components must be named objects."
            )
        if recipe.get("alignment") not in _ALIGNMENT_VALUES:
            raise CompactComponentRuntimeError(
                f"Visual recipe {component_name} has an invalid alignment classification."
            )
        parts = recipe.get("parts")
        if not isinstance(parts, dict):
            raise CompactComponentRuntimeError(
                f"Visual recipe {component_name}.parts must be an object."
            )


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    merged = copy.deepcopy(base)
    for key, value in override.items():
        existing = merged.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            merged[key] = _deep_merge(existing, value)
            continue
        merged[key] = copy.deepcopy(value)
    return merged
