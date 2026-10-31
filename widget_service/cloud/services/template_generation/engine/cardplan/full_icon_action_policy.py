"""FullIconActionLayout 的同源视觉验收白名单。"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from .models import TemplateDefinition

LAYOUT_ID = "FullIconActionLayout@1"
ACTION_ID = "IconAction@1"


def template_digest(definition: TemplateDefinition) -> str:
    """绑定模板定义而非文件时间，源内容变化后旧验收自动失效。"""
    payload = definition.model_dump(mode="json", by_alias=True)
    source = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(source.encode("utf-8")).hexdigest()


def load_full_icon_action_allowlist(
    source_root: Path, templates: dict[str, TemplateDefinition],
) -> frozenset[str]:
    path = source_root / "full-icon-action-allowlist.json"
    if not path.is_file():
        return frozenset()
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schemaVersion") != "full-icon-action-allowlist/1":
        raise ValueError("Unsupported FullIconActionLayout allowlist version")
    for key, template_id in (("layoutDigest", LAYOUT_ID), ("actionDigest", ACTION_ID)):
        definition = templates.get(template_id)
        if definition is None or payload.get(key) != template_digest(definition):
            return frozenset()
    approved: set[str] = set()
    for record in payload.get("templates", []):
        template_id = record.get("templateId")
        definition = templates.get(template_id)
        if definition is None or record.get("status") != "passed":
            continue
        if not definition.template_id.endswith("Full"):
            continue
        if definition.template_id.endswith("WideFull"):
            continue
        if record.get("templateDigest") != template_digest(definition):
            continue
        sizes = definition.variants[0].supported_card_sizes
        if sizes and "2x2" not in sizes:
            continue
        if not record.get("evidence"):
            continue
        approved.add(template_id)
    return frozenset(approved)
