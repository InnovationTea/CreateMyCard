"""Validator module registry."""

from __future__ import annotations

try:
    from . import component_validator, data_validator, design_validator, json_validator, protocol_validator, surface_validator, tree_validator
except ImportError:
    import component_validator  # type: ignore
    import data_validator  # type: ignore
    import design_validator  # type: ignore
    import json_validator  # type: ignore
    import protocol_validator  # type: ignore
    import surface_validator  # type: ignore
    import tree_validator  # type: ignore

MODULE_REGISTRY = {
    "json": json_validator,
    "protocol": protocol_validator,
    "surface": surface_validator,
    "tree": tree_validator,
    "component": component_validator,
    "data": data_validator,
    "design": design_validator,
}

DEFAULT_PROFILE = "train"
DEFAULT_MODULES = ["json", "protocol", "surface", "tree", "component", "data", "design"]
