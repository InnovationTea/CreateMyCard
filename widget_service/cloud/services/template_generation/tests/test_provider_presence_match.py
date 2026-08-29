"""CardTemplate v2 有序可选项匹配与守卫转换（已场景金样化，Layer C）。

原 8 个测试函数（35 个参数化用例）全部转为场景金样：

- ``provider_presence__parser_contracts``：``_presence_reference`` 的 16 组
  输入→元组契约（合法 ``(data|props, name)`` 以列表冻结，非法输入为 null）；
- ``provider_presence__cardinality_selection``：``#match present`` 按可用
  字段数 0-3 选择 Text/Text/Row/Column 布局并保持有序文本（8 组可用性组合）；
- ``provider_presence__guard_transform``：``(guard => value)`` 转换后的
  运行时绑定完整字符串与 cardtpl/2 源格式，以及经磁盘清单往返
  （provider.json + templates/*.cardtpl）后 Provider Bundle 仍传播 cardtpl/2；
- ``provider_presence__props_presence``：``props.label`` 按存在性（缺失 /
  空串 / 有值）而非真值选择分支的文本网格；
- ``provider_presence__rejections``：8 条确定性拒绝规则（6 条 ``#match``
  结构规则 + cardtpl/1 要求 + 转换借用缺失可选项）的错误类型与完整文案。

错误断言按惯例冻结 ``{"errorType", "message"}``（未抛错为
``{"error": "NO_ERROR"}``）。本文件不保留独立断言用例，仅保留金样入口
测试；引擎或解析规则改动后按 golden 工作流 ``check --diff`` /
``bless --declared`` 复核。
"""

from __future__ import annotations

import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from services.template_generation.engine.cardplan.compiler import _instantiate_blueprint
from services.template_generation.engine.cardplan.models import TemplateDefinition
from services.template_generation.engine.cardplan.provider_bundle import (
    _parse_component_body,
    _presence_reference,
    compile_card_template,
    load_provider_bundle,
)
from services.template_generation.engine.tersel_converter import Nested2Node
from services.template_generation.test_support.golden_scenarios import (
    assert_golden_scenario,
    scenario,
)

_NAMES = ("city", "temperature", "uv")


def _definition(
    body: str,
    *,
    template_language: Literal["cardtpl/1", "cardtpl/2"] = "cardtpl/2",
) -> TemplateDefinition:
    source = (
        "#Template PresenceFull@1(props: { label?: string })\n"
        "data = {\n"
        '  city: $optionalPath("/city"),\n'
        '  temperature: $optionalPath("/temperature"),\n'
        '  uv: $optionalPath("/uv")\n'
        "}\n"
        "Column({},\n"
        f"{body}\n"
        ")\n"
        "#End"
    )
    return compile_card_template(
        source,
        template_language=template_language,
        provider_id="example.presence",
        business_id="Presence",
        expected_wire_id="PresenceFull@1",
        expected_capability_id="GetPresenceData",
        data_domain="/data/context",
        description="有序可选字段测试",
        supported_card_sizes=("2x2",),
        primary_data=(),
        secondary_data=(),
        optional_data=tuple(f"/{name}" for name in _NAMES),
        output_schema={
            "type": "object",
            "properties": {name: {"type": "string"} for name in _NAMES},
        },
    )


def _match_body() -> str:
    return """#match present(
  data.city,
  data.temperature,
  (data.uv => `紫外线等级${data.uv}`)
) as items
#case 0
  Text("暂无数据")
#case 1
  Text(items[0])
#case 2
  Row({"itemMargin": 4},
    Text(items[0]),
    Text(items[1])
  )
#default
  Column({"itemMargin": 2},
    Text(items[0]),
    Text(items[1]),
    Text(items[2])
  )
#end"""


def _bindings(names: tuple[str, ...]) -> dict[str, str]:
    return {name: "${data.context." + name + "}" for name in names}


def _texts(node: Nested2Node) -> list[object]:
    values: list[object] = []
    if node.component_type == "Text":
        values.append(node.values[0])
    for child in node.children:
        values.extend(_texts(child))
    return values


def _error(build: Callable[[], Any]) -> dict[str, str]:
    """执行构建并冻结错误类型与报错文案；未抛错时返回哨兵。"""
    try:
        build()
    except Exception as exc:  # noqa: BLE001 - 错误本身就是被冻结的产物
        return {"errorType": type(exc).__name__, "message": str(exc)}
    return {"error": "NO_ERROR"}


_PARSER_REFERENCE_CASES: tuple[tuple[str, str], ...] = (
    ("data_city", "data.city"),
    ("props_label", "props.label"),
    ("data_underscore_city2", "data._city2"),
    ("props_capital_label2", "props.Label2"),
    ("empty_source", ""),
    ("bare_domain", "data"),
    ("props_trailing_dot", "props."),
    ("digit_leading_name", "data.1city"),
    ("foreign_domain", "other.city"),
    ("three_segments", "data.city.name"),
    ("optional_chained", "props?.label"),
    ("leading_space", " data.city"),
    ("trailing_space", "props.label "),
    ("trailing_newline", "data.city\n"),
    ("cjk_name", "data.城市"),
    ("call_suffix", "data.city()"),
)


@scenario("provider_presence__parser_contracts")
def _build_parser_contracts() -> dict[str, Any]:
    contracts: dict[str, Any] = {}
    for key, source in _PARSER_REFERENCE_CASES:
        reference = _presence_reference(source)
        contracts[key] = list(reference) if reference is not None else None
    return contracts


_AVAILABILITY_CASES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("none", ()),
    ("city", ("city",)),
    ("temperature", ("temperature",)),
    ("uv", ("uv",)),
    ("city_temperature", ("city", "temperature")),
    ("city_uv", ("city", "uv")),
    ("temperature_uv", ("temperature", "uv")),
    ("city_temperature_uv", ("city", "temperature", "uv")),
)


@scenario("provider_presence__cardinality_selection")
def _build_cardinality_selection() -> dict[str, Any]:
    definition = _definition(_match_body())
    payload: dict[str, Any] = {}
    for key, available in _AVAILABILITY_CASES:
        root = _instantiate_blueprint(
            definition.variants[0].root,
            {},
            _bindings(available),
        )
        selected = root.children[0]
        payload[key] = {
            "cardinality": len(available),
            "layout": selected.component_type,
            "texts": _texts(selected),
        }
    return payload


@scenario("provider_presence__guard_transform")
def _build_guard_transform() -> dict[str, Any]:
    definition = _definition(_match_body())
    root = _instantiate_blueprint(
        definition.variants[0].root,
        {},
        _bindings(("uv",)),
    )
    return {
        "sourceFormat": definition.source_format,
        "transformedValue": root.children[0].values[0],
        "bundleRoundTripSourceFormat": _bundle_round_trip_source_format(),
    }


_BUNDLE_MANIFEST = """{
  "bundleFormat": "card-provider-bundle/1",
  "providerId": "example.layout",
  "providerVersion": "1.0.0",
  "templates": [{
    "templateId": "SingleFocusLayout@1",
    "description": "CardTemplate v2 manifest propagation test.",
    "entry": "templates/layout.cardtpl"
  }],
  "compatibility": {
    "templateLanguage": "cardtpl/2",
    "catalogId": "ohos.a2ui.extended.catalog.form",
    "a2uiWireVersion": "v0.9"
  }
}"""

_BUNDLE_MATCH_BODY = """#Template SingleFocusLayout@1(props: { label?: string })
data = {
}
Column({},
  #match present(props.label) as items
  #case 0
    Text("缺失")
  #case 1
    Text(items[0])
  #end
)
#End
"""


def _bundle_round_trip_source_format() -> str:
    """经磁盘清单往返后 Provider Bundle 仍解析为 cardtpl/2。"""
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "provider.json").write_text(_BUNDLE_MANIFEST, encoding="utf-8")
        templates_root = root / "templates"
        templates_root.mkdir()
        (templates_root / "layout.cardtpl").write_text(
            _BUNDLE_MATCH_BODY, encoding="utf-8"
        )
        bundle = load_provider_bundle(root)
        return bundle.templates[0].source_format


_PROPS_PRESENCE_CASES: tuple[tuple[str, dict[str, str]], ...] = (
    ("missing", {}),
    ("present_empty_string", {"label": ""}),
    ("present_value", {"label": "深圳"}),
)

_PROPS_PRESENCE_BODY = """#match present(props.label) as items
#case 0
  Text("缺失")
#case 1
  Text(items[0])
#end"""


@scenario("provider_presence__props_presence")
def _build_props_presence() -> dict[str, Any]:
    definition = _definition(_PROPS_PRESENCE_BODY)
    return {
        key: {"texts": _texts(_instantiate_blueprint(definition.variants[0].root, params))}
        for key, params in _PROPS_PRESENCE_CASES
    }


_REJECTED_BODIES: tuple[tuple[str, str], ...] = (
    (
        "items_index_out_of_range",
        """#match present(data.city) as items
#case 1
  Text(items[1])
#end""",
    ),
    (
        "default_items_index_out_of_range",
        """#match present(data.city, data.temperature) as items
#case 1
  Text(items[0])
#default
  Text(items[0])
#end""",
    ),
    (
        "duplicate_guards",
        """#match present(data.city, data.city) as items
#case 2
  Text(items[0])
#end""",
    ),
    (
        "unguarded_transform",
        """#match present(data.city => `城市${data.city}`) as items
#case 1
  Text(items[0])
#end""",
    ),
    (
        "case_exceeds_present",
        """#match present(data.city) as items
#case 2
  Text(items[0])
#end""",
    ),
    (
        "four_item_limit_exceeded",
        """#match present(
  data.first,
  data.second,
  data.third,
  data.fourth,
  data.fifth
) as items
#case 0
  Text("empty")
#end""",
    ),
)

_TRANSFORM_BORROW_BODY = """#match present(
  (data.city => `${data.city} ${data.temperature}`)
) as items
#case 1
  Text(items[0])
#end"""


@scenario("provider_presence__rejections")
def _build_rejections() -> dict[str, dict[str, str]]:
    rejections: dict[str, dict[str, str]] = {}
    for key, body in _REJECTED_BODIES:
        rejections[f"parse:{key}"] = _error(
            lambda body=body: _parse_component_body(
                body, template_language="cardtpl/2"
            ),
        )
    rejections["compile:match_requires_cardtpl2"] = _error(
        lambda: _definition(_match_body(), template_language="cardtpl/1"),
    )
    rejections["compile:transform_borrows_missing_optional"] = _error(
        lambda: _definition(_TRANSFORM_BORROW_BODY),
    )
    return rejections


def test_presence_match_contracts_match_golden_scenarios() -> None:
    for scenario_id in (
        "provider_presence__parser_contracts",
        "provider_presence__cardinality_selection",
        "provider_presence__guard_transform",
        "provider_presence__props_presence",
        "provider_presence__rejections",
    ):
        assert_golden_scenario(scenario_id)
