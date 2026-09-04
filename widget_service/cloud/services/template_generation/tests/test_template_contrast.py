"""模板编译、公共 A2UI 校验和预览产物的对比度边界回归。"""

import json

import pytest

from services.card_validation import validate_card
from services.protocol_registry import A2UI_FORM_PROTOCOL_PROFILE_ID, A2UIProtocolRegistry
from services.template_generation.engine.cardplan.compiler import (
    _compile_ux_layout_shell,
    _serialize_node,
)
from services.template_generation.engine.cardplan.fusion_ball_background import (
    FusionBallPalette,
    apply_fusion_ball_background,
)
from services.template_generation.engine.cardplan.models import HybridBodyContract
from services.template_generation.engine.cardplan.preview_dataset import (
    build_template_preview_cases,
)
from services.template_generation.engine.cardplan.registry import get_cardplan_registry
from services.template_generation.engine.tersel_converter import Nested2Node, convert_tersel_to_a2ui


@pytest.mark.parametrize(("size", "fusion"), [("2x2", False), ("2x4", False), ("2x2", True)])
def test_compiled_template_skips_only_marked_content_contrast(size: str, fusion: bool) -> None:
    content = Nested2Node(
        "Column",
        ("section",),
        (Nested2Node("Text", ("模板对比度回归", {"fontColor": "#FFFFFFFF"}), ()),),
    )
    contract = HybridBodyContract.model_construct(theme_profile_id="family-weather-care-blue")
    card = _compile_ux_layout_shell(content, contract, get_cardplan_registry(True))
    if fusion:
        card = apply_fusion_ball_background(
            card,
            size=size,
            palette=FusionBallPalette(large="#FF17734C", medium="#FF26BFA6", small="#FF60BF98"),
        )
    a2ui = convert_tersel_to_a2ui(
        _serialize_node(card) + ";",
        size=size,
        protocol_profile=A2UIProtocolRegistry(A2UI_FORM_PROTOCOL_PROFILE_ID).get_profile(),
    )

    assert '"template_root"' in a2ui
    assert not validate_card(dsl_text=a2ui).has_code("VISUAL.CONTRAST")
    # 同时重命名组件 ID 和 children 引用；未标记的相同低对比度内容仍必须被检出。
    unmarked = a2ui.replace('"template_root"', '"unmarked_content"')
    assert validate_card(dsl_text=unmarked).has_code("VISUAL.CONTRAST")


def test_all_template_previews_keep_contrast_exemption() -> None:
    cases = build_template_preview_cases()
    assert len(cases) == 69
    for case in cases:
        a2ui = "\n".join(json.dumps(message) for message in case.messages)
        assert not validate_card(dsl_text=a2ui).has_code("VISUAL.CONTRAST")
