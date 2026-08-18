"""Read-only registry and manifest validation for trusted CardPlan assets."""

from __future__ import annotations

import hashlib
import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, TypeVar

from jsonschema import Draft202012Validator

from app.logger import logger
from services.template_generation.engine.advanced.models import (
    UX_LAYOUT_COMPONENT_IDS,
    AdaptiveTemplateFamily,
    AdvancedComponentCapability,
    CardSizeContentBudget,
    UxBusinessComponentCapability,
    UxCardSizeBudget,
    UxLayoutComponentCapability,
)

from .models import TemplateDefinition, TemplateVariant, ThemeDefinition
from .provider_bundle import load_provider_templates

_WIRE_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9-]{0,63}@[1-9][0-9]*$")
_FORBIDDEN_KEYS = frozenset({"__proto__", "prototype", "constructor"})
_NamedCapability = TypeVar(
    "_NamedCapability",
    AdvancedComponentCapability,
    UxBusinessComponentCapability,
    UxLayoutComponentCapability,
)


class CardPlanRegistry:
    """Load the generated TypeScript baseline and fail closed on drift."""

    def __init__(self, source_root: Path | None = None) -> None:
        bundled_source_root = Path(__file__).resolve().parents[2] / "resources" / "source"
        self.source_root = source_root or bundled_source_root
        generated_root = Path(__file__).with_name("generated")
        self.manifest_path = generated_root / "prompt-manifest.json"
        self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        self._verify_manifest()
        template_payload = self._load_json("template-registry.json")
        theme_payload = self._load_json("theme-profiles.json")
        advanced_payload = self._load_json("advanced-component-registry.json")
        ux_advanced_payload = self._load_json("advanced-component-ux-registry.json")
        if template_payload.get("registryVersion") != "terse-template-registry/0.7":
            raise ValueError("unsupported CardPlan Template Registry version")
        templates = tuple(
            TemplateDefinition.model_validate(item)
            for item in template_payload.get("templates", [])
        )
        provider_templates = load_provider_templates(self.source_root / "providers")
        themes = tuple(
            ThemeDefinition.model_validate(item) for item in theme_payload.get("themes", [])
        )
        self.templates = self._unique_by_wire_id((*templates, *provider_templates))
        self.provider_template_ids = tuple(item.wire_id for item in provider_templates)
        self.themes = self._unique_themes(themes)
        advanced_version = "advanced-component-registry/1"
        if self.manifest.get("advancedComponentRegistryVersion") != advanced_version:
            raise ValueError("Advanced Component Manifest version mismatch")
        if advanced_payload.get("registryVersion") != advanced_version:
            raise ValueError("unsupported Advanced Component Registry version")
        components = tuple(
            AdvancedComponentCapability.model_validate(item)
            for item in advanced_payload.get("components", [])
        )
        adaptive_templates = tuple(
            AdaptiveTemplateFamily.model_validate(item)
            for item in advanced_payload.get("adaptiveTemplates", [])
        )
        size_budgets = tuple(
            CardSizeContentBudget.model_validate(item)
            for item in advanced_payload.get("sizeBudgets", [])
        )
        self.advanced_registry_version = str(advanced_payload["registryVersion"])
        self.advanced_components = self._unique_by_name(components, "Advanced Component")
        self.adaptive_templates = self._unique_by_template_id(adaptive_templates)
        self.size_budgets = {item.size: item for item in size_budgets}
        self.domain_groups = self._domain_groups(advanced_payload.get("domainGroups"))
        self._validate_advanced_registry()
        ux_version = "advanced-component-ux-registry/1"
        if self.manifest.get("uxAdvancedComponentRegistryVersion") != ux_version:
            raise ValueError("UX Advanced Component Manifest version mismatch")
        if ux_advanced_payload.get("registryVersion") != ux_version:
            raise ValueError("unsupported UX Advanced Component Registry version")
        ux_business_components = tuple(
            UxBusinessComponentCapability.model_validate(item)
            for item in ux_advanced_payload.get("businessComponents", [])
        )
        ux_layout_components = tuple(
            UxLayoutComponentCapability.model_validate(item)
            for item in ux_advanced_payload.get("layoutComponents", [])
        )
        ux_size_budgets = tuple(
            UxCardSizeBudget.model_validate(item)
            for item in ux_advanced_payload.get("sizeBudgets", [])
        )
        self.ux_advanced_registry_version = ux_version
        self.ux_business_components = self._unique_by_name(
            ux_business_components,
            "UX Business Component",
        )
        self.ux_layout_components = self._unique_by_name(
            ux_layout_components,
            "UX Layout Component",
        )
        self.ux_size_budgets = {item.size: item for item in ux_size_budgets}
        self.ux_tokens = self._ux_tokens(ux_advanced_payload.get("uxTokens"))
        self.palette_scene_theme_ids = self._palette_scene_themes(
            ux_advanced_payload.get("paletteSceneThemeIds")
        )
        self._validate_ux_advanced_registry()

    def _load_json(self, relative_path: str) -> dict[str, Any]:
        value = json.loads((self.source_root / relative_path).read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise ValueError(f"CardPlan source must be an object: {relative_path}")
        self._reject_forbidden_keys(value)
        return value

    def _verify_manifest(self) -> None:
        if self.manifest.get("catalogId") != "ohos.a2ui.extended.catalog.form":
            raise ValueError("CardPlan bundle Catalog mismatch")
        if self.manifest.get("a2uiWireVersion") != "v0.9":
            raise ValueError("CardPlan bundle wire version mismatch")
        files = self.manifest.get("files")
        if not isinstance(files, dict):
            raise ValueError("CardPlan bundle file manifest is missing")
        for relative_path, expected in files.items():
            path = self.source_root / relative_path
            if not path.is_file():
                message = (
                    "[CardPlan Registry] bundle_file_missing "
                    f"relative_path={relative_path!r} absolute_path={str(path)!r} "
                    f"source_root={str(self.source_root)!r}"
                )
                print(message, flush=True)
                logger.error(message)
                raise ValueError(f"CardPlan bundle file is missing: {relative_path}")
            actual = "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()
            if actual != expected:
                message = (
                    "[CardPlan Registry] bundle_file_drift "
                    f"relative_path={relative_path!r} absolute_path={str(path)!r} "
                    f"expected_sha256={expected!r} actual_sha256={actual!r}"
                )
                print(message, flush=True)
                logger.error(message)
                raise ValueError(f"CardPlan bundle file drift: {relative_path}")

    @staticmethod
    def _reject_forbidden_keys(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                if key in _FORBIDDEN_KEYS:
                    raise ValueError(f"forbidden CardPlan source key: {key}")
                CardPlanRegistry._reject_forbidden_keys(child)
        elif isinstance(value, list):
            for child in value:
                CardPlanRegistry._reject_forbidden_keys(child)

    @staticmethod
    def _unique_by_wire_id(
        templates: tuple[TemplateDefinition, ...],
    ) -> dict[str, TemplateDefinition]:
        result: dict[str, TemplateDefinition] = {}
        for definition in templates:
            if not _WIRE_ID_RE.fullmatch(definition.wire_id):
                raise ValueError(f"invalid Template wire ID: {definition.wire_id}")
            if definition.wire_id in result:
                raise ValueError(f"duplicate Template wire ID: {definition.wire_id}")
            variant_names = [item.size for item in definition.variants]
            if len(variant_names) != len(set(variant_names)):
                raise ValueError(f"duplicate Template variant: {definition.wire_id}")
            for variant in definition.variants:
                properties = variant.parameters_schema.get("properties", {})
                for relation in variant.parameter_relations:
                    number_schema = properties.get(relation.number_parameter, {})
                    text_schema = properties.get(relation.text_parameter, {})
                    if number_schema.get("type") != "number":
                        raise ValueError(
                            "Template relation numberParameter must reference a number: "
                            f"{definition.wire_id}/{variant.size}"
                        )
                    if text_schema.get("type") != "string":
                        raise ValueError(
                            "Template relation textParameter must reference a string: "
                            f"{definition.wire_id}/{variant.size}"
                        )
                    if not relation.allowed_suffixes:
                        raise ValueError(
                            "Template relation allowedSuffixes must not be empty: "
                            f"{definition.wire_id}/{variant.size}"
                        )
            result[definition.wire_id] = definition
        return result

    @staticmethod
    def _unique_themes(themes: tuple[ThemeDefinition, ...]) -> dict[str, ThemeDefinition]:
        result: dict[str, ThemeDefinition] = {}
        for theme in themes:
            if theme.theme_profile_id in result:
                raise ValueError(f"duplicate CardPlan theme: {theme.theme_profile_id}")
            result[theme.theme_profile_id] = theme
        return result

    def require_template(self, wire_id: str) -> TemplateDefinition:
        if not _WIRE_ID_RE.fullmatch(wire_id):
            raise ValueError(f"invalid Template wire ID: {wire_id}")
        try:
            return self.templates[wire_id]
        except KeyError as exc:
            raise ValueError(f"unknown Template: {wire_id}") from exc

    def require_variant(self, wire_id: str, size: str) -> TemplateVariant:
        definition = self.require_template(wire_id)
        for variant in definition.variants:
            if variant.size == size:
                return variant
        raise ValueError(f"unknown Template variant: {wire_id}/{size}")

    def require_theme(self, theme_id: str) -> ThemeDefinition:
        try:
            return self.themes[theme_id]
        except KeyError as exc:
            raise ValueError(f"unknown CardPlan theme: {theme_id}") from exc

    @staticmethod
    def _unique_by_name(
        values: tuple[_NamedCapability, ...],
        label: str,
    ) -> dict[str, _NamedCapability]:
        result: dict[str, _NamedCapability] = {}
        for value in values:
            if value.name in result:
                raise ValueError(f"duplicate {label}: {value.name}")
            result[value.name] = value
        return result

    @staticmethod
    def _unique_by_template_id(
        values: tuple[AdaptiveTemplateFamily, ...],
    ) -> dict[str, AdaptiveTemplateFamily]:
        result: dict[str, AdaptiveTemplateFamily] = {}
        for value in values:
            if value.template_id in result:
                raise ValueError(f"duplicate Adaptive Template: {value.template_id}")
            result[value.template_id] = value
        return result

    @staticmethod
    def _domain_groups(value: Any) -> dict[str, tuple[str, ...]]:
        if not isinstance(value, dict):
            raise ValueError("Advanced Component domainGroups must be an object")
        result: dict[str, tuple[str, ...]] = {}
        for group_id, domains in value.items():
            if not isinstance(group_id, str) or not isinstance(domains, list):
                raise ValueError("invalid Advanced Component domain group")
            if any(not isinstance(domain, str) for domain in domains):
                raise ValueError("invalid Advanced Component domain")
            result[group_id] = tuple(domains)
        return result

    def _validate_advanced_registry(self) -> None:
        if set(self.size_budgets) != {"2x2", "2x4"}:
            raise ValueError("Advanced Component size budgets are incomplete")
        domain_ids: set[str] = set()
        for capability in self.advanced_components.values():
            if capability.domain_id in domain_ids:
                raise ValueError(f"duplicate Advanced Component domain: {capability.domain_id}")
            domain_ids.add(capability.domain_id)
            if not capability.local_template_ids:
                raise ValueError(f"Advanced Component has no Template: {capability.name}")
            field_groups = capability.field_priorities
            if not field_groups.get("mustShow"):
                raise ValueError(f"Advanced Component has no mustShow field: {capability.name}")
            flattened = [field for group in field_groups.values() for field in group]
            if len(flattened) != len(set(flattened)):
                raise ValueError(f"Advanced Component field priorities overlap: {capability.name}")
            for wire_id in capability.local_template_ids:
                self.require_template(wire_id)
        known_domains = {domain for domains in self.domain_groups.values() for domain in domains}
        if not domain_ids.issubset(known_domains):
            missing = sorted(domain_ids - known_domains)
            raise ValueError(f"Advanced Component domains have no composition group: {missing}")

    @staticmethod
    def _ux_tokens(value: Any) -> dict[str, int]:
        if not isinstance(value, dict) or not value:
            raise ValueError("UX Advanced Component tokens must be a non-empty object")
        invalid = any(
            not isinstance(key, str) or not isinstance(item, int) for key, item in value.items()
        )
        if invalid:
            raise ValueError("UX Advanced Component tokens must contain integer values")
        return dict(value)

    @staticmethod
    def _palette_scene_themes(value: Any) -> dict[str, tuple[str, ...]]:
        if not isinstance(value, dict):
            raise ValueError("UX paletteSceneThemeIds must be an object")
        result: dict[str, tuple[str, ...]] = {}
        for scene, theme_ids in value.items():
            if not isinstance(scene, str) or not isinstance(theme_ids, list):
                raise ValueError("invalid UX palette scene mapping")
            if not theme_ids or any(not isinstance(theme_id, str) for theme_id in theme_ids):
                raise ValueError("invalid UX palette scene theme IDs")
            result[scene] = tuple(theme_ids)
        return result

    def _validate_ux_advanced_registry(self) -> None:
        if set(self.ux_size_budgets) != {"2x2", "2x4"}:
            raise ValueError("UX Advanced Component size budgets are incomplete")
        if len(self.ux_layout_components) != 10:
            raise ValueError("UX Advanced Component layout registry must contain 10 families")
        if len(self.ux_business_components) != 18:
            raise ValueError("UX Advanced Component business registry must contain 18 families")
        known_layouts = set(self.ux_layout_components)
        if known_layouts != set(UX_LAYOUT_COMPONENT_IDS):
            raise ValueError("UX Advanced Component layout registry IDs are incomplete")
        for layout in self.ux_layout_components.values():
            Draft202012Validator.check_schema(layout.parameters_schema)
        known_themes = set(self.themes)
        for theme_ids in self.palette_scene_theme_ids.values():
            if not set(theme_ids).issubset(known_themes):
                raise ValueError("UX palette scene references an unknown Theme")
        for capability in self.ux_business_components.values():
            if not set(capability.supported_layouts).issubset(known_layouts):
                raise ValueError(f"UX Business Component has an unknown layout: {capability.name}")
            if not set(capability.palette_scenes).issubset(self.palette_scene_theme_ids):
                raise ValueError(f"UX Business Component has an unknown palette: {capability.name}")
            for wire_id in capability.local_template_ids:
                self.require_template(wire_id)

    def require_advanced_component(self, component_id: str) -> AdvancedComponentCapability:
        try:
            return self.advanced_components[component_id]
        except KeyError as exc:
            raise ValueError(f"unknown Advanced Component: {component_id}") from exc

    def require_adaptive_template(self, template_id: str) -> AdaptiveTemplateFamily:
        try:
            return self.adaptive_templates[template_id]
        except KeyError as exc:
            raise ValueError(f"unknown Adaptive Template: {template_id}") from exc

    def require_ux_business_component(
        self,
        component_id: str,
    ) -> UxBusinessComponentCapability:
        try:
            return self.ux_business_components[component_id]
        except KeyError as exc:
            raise ValueError(f"unknown UX Business Component: {component_id}") from exc

    def require_ux_layout_component(self, component_id: str) -> UxLayoutComponentCapability:
        try:
            return self.ux_layout_components[component_id]
        except KeyError as exc:
            raise ValueError(f"unknown UX Layout Component: {component_id}") from exc


@lru_cache(maxsize=1)
def get_cardplan_registry() -> CardPlanRegistry:
    return CardPlanRegistry()
