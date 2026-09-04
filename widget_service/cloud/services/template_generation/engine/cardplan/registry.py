"""Read-only registry and metadata validation for trusted CardPlan assets."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import TypeVar

from jsonschema import Draft202012Validator

from app.logger import logger
from services.template_generation.controls import load_template_controls
from services.template_generation.engine.advanced.models import (
    UX_LAYOUT_COMPONENT_IDS,
    UxLayoutComponentCapability,
)

from .models import BusinessTemplateGroup, TemplateDefinition, TemplateVariant, ThemeDefinition
from .provider_bundle import (
    LoadedProviderBundle,
    load_provider_bundles,
    provider_template_layout_kind,
)
from .retrieval_index import (
    TemplateVariantSearchRecord,
    build_template_variant_search_records,
)
from .theme_bundle import load_theme_resources

_WIRE_ID_RE = re.compile(r"^[A-Za-z][A-Za-z0-9-]{0,63}@[1-9][0-9]*$")
_DATA_ROOT_TOKEN_RE = re.compile(r"\{\{dataRoot:([A-Za-z][A-Za-z0-9._-]{0,127})\}\}")
_NamedCapability = TypeVar(
    "_NamedCapability",
    BusinessTemplateGroup,
    UxLayoutComponentCapability,
)


class CardPlanRegistry:
    """Load CardPlan sources and validate generated protocol metadata."""

    def __init__(
        self,
        source_root: Path | None = None,
        *,
        disabled_provider_ids: tuple[str, ...] = (),
        disabled_template_ids: tuple[str, ...] = (),
        enable_fusion_ball: bool = False,
    ) -> None:
        if not isinstance(enable_fusion_ball, bool):
            raise ValueError("enable_fusion_ball must be boolean")
        bundled_source_root = Path(__file__).resolve().parents[2] / "resources" / "source"
        self.source_root = source_root or bundled_source_root
        self.disabled_provider_ids = frozenset(disabled_provider_ids)
        self.disabled_template_ids = frozenset(disabled_template_ids)
        generated_root = Path(__file__).with_name("generated")
        self.manifest_path = generated_root / "prompt-manifest.json"
        self.manifest = json.loads(self.manifest_path.read_text(encoding="utf-8"))
        self._validate_manifest_metadata()
        provider_bundles = load_provider_bundles(self.source_root / "providers")
        provider_templates = tuple(
            definition for bundle in provider_bundles for definition in bundle.templates
        )
        theme_resources = load_theme_resources(self.source_root / "themes")
        visible_themes = tuple(
            theme
            for theme in theme_resources.themes
            if enable_fusion_ball or theme.fusion_ball_style is None
        )
        self.templates = self._unique_by_wire_id(provider_templates)
        self.template_variant_search_records: tuple[TemplateVariantSearchRecord, ...] = (
            build_template_variant_search_records(self.templates)
        )
        self.provider_template_ids = tuple(item.wire_id for item in provider_templates)
        self.provider_bundles = self._provider_bundles_by_id(provider_bundles)
        self._validate_template_controls()
        if self.disabled_provider_ids or self.disabled_template_ids:
            logger.info(
                "[Template Control] registry_filter_loaded "
                f"disabled_provider_ids={json.dumps(sorted(self.disabled_provider_ids))} "
                f"disabled_template_ids={json.dumps(sorted(self.disabled_template_ids))}"
            )
        self.themes = self._unique_themes(visible_themes)
        self.theme_first_layer_rules = {
            theme_id: theme_resources.first_layer_rules[theme_id]
            for theme_id in self.themes
        }
        provider_business_components = tuple(
            component
            for bundle in provider_bundles
            for component in bundle.business_groups
        )
        provider_layout_components = tuple(
            (component, bundle.manifest.provider_id)
            for bundle in provider_bundles
            for component in bundle.manifest.layout_components
        )
        ux_business_components = provider_business_components
        ux_layout_components = tuple(item[0] for item in provider_layout_components)
        self.ux_business_components = self._unique_by_name(
            ux_business_components,
            "UX Business Component",
        )
        self.ux_business_component_provider_ids = {
            component.name: component.provider_id
            for component in provider_business_components
        }
        self.ux_layout_components = self._unique_by_name(
            ux_layout_components,
            "UX Layout Component",
        )
        self.ux_layout_component_provider_ids = {
            component.name: provider_id
            for component, provider_id in provider_layout_components
        }
        self.ux_size_budgets = {
            item.size: item for item in theme_resources.base.size_budgets
        }
        self.ux_tokens = dict(theme_resources.base.ux_tokens)
        self.content_color_properties = dict(
            theme_resources.base.content_color_properties
        )
        self.theme_reference_paths = theme_resources.base.theme_reference_paths
        self.palette_scene_theme_ids = self._palette_scene_themes(
            visible_themes
        )
        self._validate_distributed_resources()

    def _validate_manifest_metadata(self) -> None:
        if self.manifest.get("catalogId") != "ohos.a2ui.extended.catalog.form":
            raise ValueError("CardPlan bundle Catalog mismatch")
        if self.manifest.get("a2uiWireVersion") != "v0.9":
            raise ValueError("CardPlan bundle wire version mismatch")
        expected_versions = {
            "providerBundleVersion": "card-provider-bundle/1",
            "themeBaseVersion": "theme-base/2",
            "themeBundleVersion": "card-theme/2",
        }
        for key, expected in expected_versions.items():
            if self.manifest.get(key) != expected:
                raise ValueError(f"CardPlan bundle {key} mismatch")

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

    @staticmethod
    def _provider_bundles_by_id(
        bundles: tuple[LoadedProviderBundle, ...],
    ) -> dict[str, LoadedProviderBundle]:
        result: dict[str, LoadedProviderBundle] = {}
        for bundle in bundles:
            provider_id = bundle.manifest.provider_id
            if provider_id in result:
                raise ValueError(f"duplicate Provider Bundle: {provider_id}")
            result[provider_id] = bundle
        return result

    def _validate_template_controls(self) -> None:
        unknown_provider_ids = self.disabled_provider_ids - set(self.provider_bundles)
        if unknown_provider_ids:
            raise ValueError(
                "disabled Template Provider IDs are unknown: "
                + ", ".join(sorted(unknown_provider_ids))
            )
        unknown_template_ids = self.disabled_template_ids - set(self.templates)
        if unknown_template_ids:
            raise ValueError(
                "disabled Template IDs are unknown: "
                + ", ".join(sorted(unknown_template_ids))
            )

    def template_is_enabled(self, wire_id: str) -> bool:
        """Return whether one trusted Template remains eligible for LLM exposure."""
        definition = self.require_template(wire_id)
        provider_disabled = definition.provider_id in self.disabled_provider_ids
        template_disabled = wire_id in self.disabled_template_ids
        return not provider_disabled and not template_disabled

    def enabled_template_ids(self, wire_ids: tuple[str, ...]) -> tuple[str, ...]:
        """Filter trusted Template IDs while preserving their declared order."""
        return tuple(wire_id for wire_id in wire_ids if self.template_is_enabled(wire_id))

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

    def theme_reference_values(self, theme_id: str) -> dict[str, object]:
        """Return the closed set of deterministic values available to `$theme`."""
        values = self.require_theme(theme_id).reference_values
        if tuple(values) != self.theme_reference_paths:
            raise ValueError(f"Theme reference values are incomplete: {theme_id}")
        return values

    def hero_content_theme_owner(
        self,
        template_ids: tuple[str, ...],
    ) -> TemplateDefinition | None:
        """仅双业务 HeroTitle/HeroContent 组合由内容位置拥有全局主题。"""
        owners: dict[str, TemplateDefinition] = {}
        for template_id in template_ids:
            definition = self.require_template(template_id)
            if definition.business_id is None:
                continue
            layout_kind = provider_template_layout_kind(template_id)
            if layout_kind not in {"HeroTitle", "HeroContent"}:
                return None
            previous = owners.get(layout_kind)
            if previous is not None and previous.business_id != definition.business_id:
                return None
            owners[layout_kind] = definition
        title = owners.get("HeroTitle")
        content = owners.get("HeroContent")
        if title is None or content is None:
            return None
        if title.business_id == content.business_id:
            return None
        return content

    def hero_content_theme_id(
        self,
        template_ids: tuple[str, ...],
        requested_theme_id: str,
    ) -> str | None:
        """按主业务及已过滤的版本能力确定主题，不借用标题业务的融球。"""
        owner = self.hero_content_theme_owner(template_ids)
        if owner is None or owner.business_id is None:
            return None
        theme_ids = self.first_layer_theme_ids((owner.business_id,))
        if not theme_ids:
            raise ValueError(f"HeroContent business has no available Theme: {owner.business_id}")
        return requested_theme_id if requested_theme_id in theme_ids else theme_ids[0]

    def layout_theme_ids(
        self,
        layout_id: str,
        capability_ids: tuple[str, ...],
    ) -> tuple[str, ...]:
        """Return layout-scoped Themes that cover every selected capability."""
        required_capabilities = set(capability_ids)
        compatible_theme_ids: list[str] = []
        for theme_id, theme in self.themes.items():
            if layout_id not in theme.supported_layout_ids:
                continue
            supported_capabilities = set(theme.supported_capability_ids)
            if required_capabilities <= supported_capabilities:
                compatible_theme_ids.append(theme_id)
        return tuple(compatible_theme_ids)

    def require_layout_theme(
        self,
        layout_id: str,
        capability_ids: tuple[str, ...],
    ) -> str:
        """Resolve one deterministic Theme for a layout-specific composition."""
        theme_ids = self.layout_theme_ids(layout_id, capability_ids)
        if len(theme_ids) != 1:
            raise ValueError(
                "CardPlan layout requires exactly one compatible Theme: "
                f"{layout_id}/{sorted(capability_ids)}"
            )
        return theme_ids[0]

    def provider_first_layer_rules(
        self,
        component_ids: tuple[str, ...],
        data_roots: dict[str, str],
    ) -> tuple[dict[str, str], ...]:
        """Return only candidate Providers' first-layer rules with TaskSpec roots resolved."""
        return tuple(
            {
                "providerId": bundle.manifest.provider_id,
                "content": self._render_provider_data_roots(
                    self._without_disabled_template_references(bundle, bundle.first_layer_rule),
                    data_roots,
                ),
            }
            for bundle in self._provider_bundles_for_components(component_ids)
        )

    def provider_second_layer_rules(
        self,
        component_ids: tuple[str, ...],
    ) -> tuple[dict[str, str], ...]:
        """Return only selected Providers' second-layer variant and parameter rules."""
        return tuple(
            {
                "providerId": bundle.manifest.provider_id,
                "content": self._without_disabled_template_references(
                    bundle,
                    bundle.second_layer_rule,
                ),
            }
            for bundle in self._provider_bundles_for_components(component_ids)
        )

    def provider_second_layer_guidance(
        self,
        component_ids: tuple[str, ...],
    ) -> tuple[dict[str, str], ...]:
        """Return Provider guidance without repeating the full Template catalog."""
        return tuple(
            {
                "providerId": bundle.manifest.provider_id,
                "content": self._without_template_catalog(
                    self._without_disabled_template_references(
                        bundle,
                        bundle.second_layer_rule,
                    )
                ),
            }
            for bundle in self._provider_bundles_for_components(component_ids)
        )

    def provider_data_domains_for_components(
        self,
        component_ids: tuple[str, ...],
    ) -> dict[str, str]:
        """Return Provider-owned absolute TaskSpec roots for candidate components."""
        domains: dict[str, str] = {}
        for bundle in self._provider_bundles_for_components(component_ids):
            for capability in bundle.manifest.capabilities:
                if capability.capability_id is None or capability.data_domain is None:
                    continue
                existing = domains.get(capability.capability_id)
                if existing is not None and existing != capability.data_domain:
                    raise ValueError(
                        "Provider capability has conflicting dataDomain declarations: "
                        f"{capability.capability_id}"
                    )
                domains[capability.capability_id] = capability.data_domain
        return domains

    def theme_first_layer_rule_documents(
        self,
        theme_ids: tuple[str, ...],
    ) -> tuple[dict[str, str], ...]:
        """Return only candidate Theme documents needed by the first-layer selector."""
        return tuple(
            {"theme": theme_id, "content": self.theme_first_layer_rules[theme_id]}
            for theme_id in dict.fromkeys(theme_ids)
        )

    def first_layer_theme_ids(
        self,
        component_ids: tuple[str, ...],
    ) -> tuple[str, ...]:
        """Return business-scoped Themes, preferring Fusion by candidate construction."""
        components: list[BusinessTemplateGroup] = []
        for component_id in dict.fromkeys(component_ids):
            components.append(self.require_ux_business_component(component_id))
        capability_ids: set[str] = set()
        for component in components:
            capability_ids.update(component.data_capability_ids)
        if not capability_ids:
            return ()

        requested_business_ids = {component.name for component in components}
        normal_theme_ids: list[str] = []
        fusion_theme_ids: list[str] = []
        for theme in self.themes.values():
            if theme.supported_layout_ids:
                continue
            if capability_ids.isdisjoint(theme.supported_capability_ids):
                continue
            fusion = theme.fusion_ball_style
            if fusion is None:
                normal_theme_ids.append(theme.theme_profile_id)
                continue
            if requested_business_ids.isdisjoint(fusion.business_ids):
                continue
            fusion_theme_ids.append(theme.theme_profile_id)
        if fusion_theme_ids:
            return tuple(fusion_theme_ids)
        return tuple(normal_theme_ids)

    def _provider_bundles_for_components(
        self,
        component_ids: tuple[str, ...],
    ) -> tuple[LoadedProviderBundle, ...]:
        provider_ids = []
        for component_id in component_ids:
            provider_id = self.ux_business_component_provider_ids[component_id]
            if provider_id not in self.disabled_provider_ids:
                provider_ids.append(provider_id)
        return tuple(
            self.provider_bundles[provider_id] for provider_id in dict.fromkeys(provider_ids)
        )

    def _without_disabled_template_references(
        self,
        bundle: LoadedProviderBundle,
        content: str,
    ) -> str:
        disabled_ids = tuple(
            definition.wire_id
            for definition in bundle.templates
            if not self.template_is_enabled(definition.wire_id)
        )
        if not disabled_ids:
            return content
        visible_lines = (
            line
            for line in content.splitlines()
            if not any(template_id in line for template_id in disabled_ids)
        )
        return "\n".join(visible_lines).strip()

    @staticmethod
    def _without_template_catalog(content: str) -> str:
        """Remove the generated available-Template list from second-layer Markdown."""
        visible_lines: list[str] = []
        skipping_catalog = False
        for line in content.splitlines():
            if line.strip() == "- 可用模板：":
                skipping_catalog = True
                continue
            if skipping_catalog:
                if re.match(r"^- `[^`]+@\d+`", line):
                    continue
                if not line.startswith("- "):
                    continue
                skipping_catalog = False
            visible_lines.append(line)
        return "\n".join(visible_lines).strip()

    @staticmethod
    def _render_provider_data_roots(content: str, data_roots: dict[str, str]) -> str:
        missing: set[str] = set()

        def replace(match: re.Match[str]) -> str:
            capability_id = match.group(1)
            root = data_roots.get(capability_id)
            if root is None:
                missing.add(capability_id)
                return match.group(0)
            return root.rstrip("/")

        rendered = _DATA_ROOT_TOKEN_RE.sub(replace, content)
        if missing:
            raise ValueError(
                "Provider first-layer rule has no TaskSpec data root: " + ", ".join(sorted(missing))
            )
        return rendered

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
    def _palette_scene_themes(
        themes: tuple[ThemeDefinition, ...],
    ) -> dict[str, tuple[str, ...]]:
        result: dict[str, list[str]] = {}
        for theme in themes:
            for scene_id in theme.palette_scene_ids:
                result.setdefault(scene_id, []).append(theme.theme_profile_id)
        return {scene_id: tuple(theme_ids) for scene_id, theme_ids in result.items()}

    def _validate_distributed_resources(self) -> None:
        if set(self.ux_size_budgets) != {"2x2", "2x4"}:
            raise ValueError("Theme base size budgets are incomplete")
        if len(self.ux_layout_components) != len(UX_LAYOUT_COMPONENT_IDS):
            raise ValueError("Layout Provider family count is incomplete")
        if not self.ux_business_components:
            raise ValueError("Provider Template business index must not be empty")
        known_layouts = set(self.ux_layout_components)
        if known_layouts != set(UX_LAYOUT_COMPONENT_IDS):
            raise ValueError("Layout Provider registry IDs are incomplete")
        for layout in self.ux_layout_components.values():
            Draft202012Validator.check_schema(layout.parameters_schema)
        if "generic" not in self.palette_scene_theme_ids:
            raise ValueError("Theme bundles must provide the generic palette scene")
        for theme in self.themes.values():
            if len(theme.supported_layout_ids) != len(set(theme.supported_layout_ids)):
                raise ValueError(
                    f"Theme supportedLayoutIds must be unique: {theme.theme_profile_id}"
                )
            unknown_layout_ids = set(theme.supported_layout_ids) - known_layouts
            if unknown_layout_ids:
                raise ValueError(
                    "Theme references unknown Layouts: "
                    f"{theme.theme_profile_id}/{sorted(unknown_layout_ids)}"
                )
            fusion = theme.fusion_ball_style
            if fusion is None:
                continue
            if len(fusion.business_ids) != len(set(fusion.business_ids)):
                raise ValueError(
                    f"Fusion Theme businessIds must be unique: {theme.theme_profile_id}"
                )
            for business_id in fusion.business_ids:
                business = self.ux_business_components.get(business_id)
                if business is None:
                    raise ValueError(f"Fusion Theme references unknown business: {business_id}")
                if set(business.data_capability_ids).isdisjoint(theme.supported_capability_ids):
                    raise ValueError(
                        "Fusion Theme business is outside supported capabilities: "
                        f"{theme.theme_profile_id}/{business_id}"
                    )
        for capability in self.ux_business_components.values():
            provider_id = self.ux_business_component_provider_ids[capability.name]
            provider_capability_ids = {
                item.capability_id
                for item in self.provider_bundles[provider_id].manifest.capabilities
                if item.capability_id is not None
            }
            if not set(capability.data_capability_ids).issubset(provider_capability_ids):
                raise ValueError(
                    "UX Business Component references a capability outside its Provider: "
                    f"{capability.name}"
                )
            for wire_id in capability.local_template_ids:
                definition = self.require_template(wire_id)
                if definition.business_id != capability.name:
                    raise ValueError(
                        "Provider Template businessId does not match its derived group: "
                        f"{wire_id}"
                    )
                if definition.provider_id != provider_id:
                    raise ValueError(f"Provider Template is outside its business owner: {wire_id}")
        for layout in self.ux_layout_components.values():
            provider_id = self.ux_layout_component_provider_ids[layout.name]
            definition = self.require_template(f"{layout.name}@1")
            if definition.provider_id != provider_id:
                raise ValueError(f"UX Layout Component is outside its Provider: {layout.name}")

    def require_ux_business_component(
        self,
        component_id: str,
    ) -> BusinessTemplateGroup:
        try:
            return self.ux_business_components[component_id]
        except KeyError as exc:
            raise ValueError(f"unknown UX Business Component: {component_id}") from exc

    def require_ux_layout_component(self, component_id: str) -> UxLayoutComponentCapability:
        try:
            return self.ux_layout_components[component_id]
        except KeyError as exc:
            raise ValueError(f"unknown UX Layout Component: {component_id}") from exc


@lru_cache(maxsize=2)
def get_cardplan_registry(enable_fusion_ball: bool = False) -> CardPlanRegistry:
    controls = load_template_controls()
    return CardPlanRegistry(
        disabled_provider_ids=controls.disabled_provider_ids,
        disabled_template_ids=controls.disabled_template_ids,
        enable_fusion_ball=enable_fusion_ball,
    )
