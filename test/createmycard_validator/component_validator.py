"""Component field rules."""

from __future__ import annotations

try:
    from .common import ALLOWED_COMPONENTS, Finding, ValidationContext, error
    from .rule_check import RuleCheckSpec, run_rule_checks
except ImportError:
    from common import ALLOWED_COMPONENTS, Finding, ValidationContext, error  # type: ignore
    from rule_check import RuleCheckSpec, run_rule_checks  # type: ignore


def check_text_content_field(ctx: ValidationContext) -> list[Finding]:
    findings: list[Finding] = []
    for component in ctx.iter_texts():
        cid = component.get("id", "<unknown>")
        if "text" in component:
            findings.append(error("RULE_COMPONENT_001", f"Text '{cid}' must use content, not text", 5))
    return findings


def check_image_src_field(ctx: ValidationContext) -> list[Finding]:
    findings: list[Finding] = []
    for component in ctx.iter_components("Image"):
        cid = component.get("id", "<unknown>")
        if "url" in component:
            findings.append(error("RULE_COMPONENT_002", f"Image '{cid}' must use src, not url", 5))
    return findings


def check_button_label_field(ctx: ValidationContext) -> list[Finding]:
    findings: list[Finding] = []
    for component in ctx.iter_buttons():
        cid = component.get("id", "<unknown>")
        if "child" in component:
            findings.append(error("RULE_COMPONENT_003", f"Button '{cid}' must use label, not child", 5))
    return findings


def check_row_field_aliases(ctx: ValidationContext) -> list[Finding]:
    findings: list[Finding] = []
    for component in ctx.iter_components("Row"):
        cid = component.get("id", "<unknown>")
        if "justify" in component:
            findings.append(error("RULE_COMPONENT_004", f"Row '{cid}' must use justifyContent, not justify", 5))
        if "align" in component:
            findings.append(error("RULE_COMPONENT_005", f"Row '{cid}' must use alignItems, not align", 5))
    return findings


def check_component_catalog(ctx: ValidationContext) -> list[Finding]:
    findings: list[Finding] = []
    for component in ctx.components:
        cid = component.get("id", "<unknown>")
        ctype = component.get("component")
        if isinstance(ctype, str):
            if ctype.startswith("Extended."):
                findings.append(error("RULE_COMPONENT_006", f"component '{cid}' uses forbidden Extended.* prefix: {ctype}", 5))
            if ctype not in ALLOWED_COMPONENTS:
                findings.append(error("RULE_COMPONENT_007", f"component '{cid}' uses unsupported component '{ctype}'", 10))
        styles = component.get("styles")
        if "styles" in component and not isinstance(styles, dict):
            findings.append(error("RULE_COMPONENT_007", f"component '{cid}' styles must be an object", 10))
    return findings


RULE_CHECKS = [
    RuleCheckSpec("RULE_COMPONENT_001", "component", check_text_content_field),
    RuleCheckSpec("RULE_COMPONENT_002", "component", check_image_src_field),
    RuleCheckSpec("RULE_COMPONENT_003", "component", check_button_label_field),
    RuleCheckSpec("RULE_COMPONENT_004", "component", check_row_field_aliases),
    RuleCheckSpec("RULE_COMPONENT_005", "component", check_row_field_aliases),
    RuleCheckSpec("RULE_COMPONENT_006", "component", check_component_catalog),
    RuleCheckSpec("RULE_COMPONENT_007", "component", check_component_catalog),
]


def validate(ctx: ValidationContext) -> list[Finding]:
    return run_rule_checks(ctx, RULE_CHECKS)
