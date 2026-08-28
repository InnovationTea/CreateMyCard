"""模板渲染所需的候选字段依赖，只影响模板路由。"""

from __future__ import annotations

from dataclasses import dataclass

from models.generation import CandidateDataBinding


@dataclass(frozen=True)
class TemplateFieldDependency:
    trigger_fields: tuple[str, ...]
    auto_include_fields: tuple[str, ...]


_FIELD_DEPENDENCIES: dict[str, tuple[TemplateFieldDependency, ...]] = {
    "GetPhoneBatteryInfo": (
        TemplateFieldDependency(
            trigger_fields=(
                "batterySOCText",
                "batteryCapacityLevelDesc",
                "chargingStatusDesc",
            ),
            auto_include_fields=("batterySOC",),
        ),
    ),
}


def enrich_template_bindings(
    bindings: list[CandidateDataBinding],
) -> list[CandidateDataBinding]:
    """稳定补齐模板内部依赖字段，不改变 dev 的通用能力解析逻辑。"""
    enriched_bindings: list[CandidateDataBinding] = []
    for binding in bindings:
        fields = list(binding.candidateOutputFields)
        normalized_fields = {field.lstrip("/") for field in fields}
        for dependency in _FIELD_DEPENDENCIES.get(binding.capabilityId, ()):
            if not any(
                trigger.lstrip("/") in normalized_fields
                for trigger in dependency.trigger_fields
            ):
                continue
            for field in dependency.auto_include_fields:
                normalized = field.lstrip("/")
                if normalized in normalized_fields:
                    continue
                fields.append(f"/{normalized}")
                normalized_fields.add(normalized)
        enriched_bindings.append(
            binding.model_copy(update={"candidateOutputFields": fields})
        )
    return enriched_bindings
