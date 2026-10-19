"""结构命名只改组件 ID 与 children，不改 Few-shot 输入、业务属性或拓扑。"""

import hashlib
import json
import re
from collections import Counter
from pathlib import Path

import pytest

SOURCE = (
    Path(__file__).resolve().parents[1]
    / "cloud/data/protocol_profiles/design-compact-dsl-fusion/prompt_source"
)
TEMPLATE_FILES = ("layouts/2x2.md", "layouts/2x4.md", "combinations/2x2.md")
EXAMPLE_FILES = ("fewshots/2x2.md", "fewshots/2x4.md")
BLOCK = re.compile(r"```genui\s*\n(.*?)```", re.DOTALL)
EXAMPLE = re.compile(r"<!-- prompt:(example-[\w-]+) -->(.*?)<!-- /prompt:\1 -->", re.DOTALL)
QUAD = ("top_left", "top_right", "bottom_left", "bottom_right")
EXPECTED_EXAMPLES = {
    "fewshots/2x2.md:example-v01":
        "a59d7fca7daa127668c3677a235833f97b8089b55b27fd388b82223f79520502",
    "fewshots/2x2.md:example-v09":
        "df15ab932fb30bb154eb273a633231387d5f7bf2342653d5b56db642ec198094",
    "fewshots/2x2.md:example-v10":
        "b6b9215d827050852ab5e40aeafadefdac203ba778d62b63b3c71918c903382f",
    "fewshots/2x2.md:example-v12":
        "08d22b87fdcd2f9d96ef608a439491bfa3a8132e618625ae46ded4d526e9ac73",
    "fewshots/2x2.md:example-v04":
        "9acc85bd31444bf5c7474a1dd77db65effb95d9f34d5393c5a03c338b89162d9",
    "fewshots/2x2.md:example-v11":
        "26d951023792e90b7aefa64cf0fc143cf60b001830696ebe73af90e44e7b6ab5",
    "fewshots/2x2.md:example-v13":
        "f9318d7b82ca5166daddf1ed96d49a8f5589eb0a42f5940ad17bb89f46c825e6",
    "fewshots/2x2.md:example-v05":
        "a82d222c831ea988ebb6ff23ce74e362e923f53631d848158551136d38e22158",
    "fewshots/2x2.md:example-v06":
        "861fecb5147f54dfd7c89380e6ea74009ffa3ad86851d03c1ba8f965b6efdd65",
    "fewshots/2x2.md:example-v02":
        "7dd97b18971b8c77e4eedd76a931ff56536ca195fe5d1affd87438943cddd6fc",
    "fewshots/2x2.md:example-v08":
        "6312bd5d2ca151b6fd0d6aac13705101afa580625101b7ecc1a1cd2f5a40e7c4",
    "fewshots/2x2.md:example-v14":
        "5960583bdd0fd58b45a1de15cea734d905fabbbce56b146fe706cd083c4e9f8b",
    "fewshots/2x2.md:example-v03":
        "1edd72116f09cb6180a40421e239e40da124e524757bacc449f860ba97d2abdb",
    "fewshots/2x2.md:example-v07":
        "d64d1db29b42efec9a23a7a701e15a3c63e955f40e7bbbba3e22d21b8081f62a",
    "fewshots/2x4.md:example-v03":
        "8aa429154796686c80319bcca36f97cbf1fd447996e93745670a0aa665d77020",
    "fewshots/2x4.md:example-v16":
        "7a749da27929c9f4ba9fc658738fb7a0302ed5068666c8e5686c92376bb58cf9",
    "fewshots/2x4.md:example-v28":
        "c1fd61046836e37a06114ddb20641bce38936f7d5a4f453b29c582cca42fdbee",
    "fewshots/2x4.md:example-v09":
        "bf27585a2d9b137ed19451dabdd940b669e6b11e92325f9539b3969afeaacf50",
    "fewshots/2x4.md:example-v08":
        "5258330397a5166a7546afbab9d870cd5d1402e29f9cc39fd36d8f84596d1684",
    "fewshots/2x4.md:example-v10":
        "d8511c5b19937e14a488156946778b30733ef951910fedf964197b8b264d06fa",
    "fewshots/2x4.md:example-v23":
        "d6940e02240e39cc9278820de4a2067ee02a7cc7a4bec2e854267afec011ed43",
    "fewshots/2x4.md:example-v06":
        "b0f1d824cb4895dc92820b14552152b047911251f897a069a8987d0dccbc770a",
    "fewshots/2x4.md:example-v19":
        "5a53bd53e3f78c7d09603812a8407c1eead76d717fb582ba031410414b4b17fc",
    "fewshots/2x4.md:example-v38":
        "e252bc6f02d127221dceb4fa494d47f699ac332c9c74e95aae7a8a98fba74088",
}
EXPECTED_TEMPLATES = {
    "layouts/2x2.md:1":
        "1c7056a187cc5170ad5b2654327c154012bd7b5adc005055c5406481cd7aefc4",
    "layouts/2x2.md:2":
        "783bb82e88b2b1e19e4daec3c96417b4fb17a60b4905a0eb01d3cc9c7bca626c",
    "layouts/2x2.md:3":
        "32f5f94a9204a94fdeb6b0d36bc9a8c1413c296a5e414089d9711417a8422f5b",
    "layouts/2x2.md:4":
        "44e123f2f588dc00598eb027505adcb0f56efe1250e07da2c4cb14fa8c0bd5f5",
    "layouts/2x2.md:5":
        "5d7254c34f68d6d5e21606c7e404dd6a0f80ffba2571ec44abc162db49b6fe81",
    "layouts/2x2.md:6":
        "cc7c79120a32fd83aebbd1b00d379539316c99c00550355fc7f419dfc918d712",
    "layouts/2x2.md:7":
        "6f18a090027ef1103bb69d7b205dc9eab7c44b395c6760f9c0d58c60d1686291",
    "layouts/2x2.md:8":
        "ebcf247f4a18b5a123d274c47e8e0060f17269b9dcfebbf3b6dbed22f75176fc",
    "layouts/2x2.md:9":
        "f7fb199a89643121d47a19a27f0374c4bbb88b3155bcaa670badd4f98c467042",
    "layouts/2x2.md:10":
        "39cecb07f0ba976c6093d4fb4e032f75cb1fe861a380de79e4bffc2e045a6dbb",
    "layouts/2x2.md:11":
        "b1481322d92c862fe087f3a6879ed735fd043ef79999e9aca4c34e4976c22242",
    "layouts/2x2.md:12":
        "7f5da60b6d01132ae926ce43d7506ad6cd534e682c8c9990ad5377aeb21ca95f",
    "layouts/2x2.md:13":
        "7f5da60b6d01132ae926ce43d7506ad6cd534e682c8c9990ad5377aeb21ca95f",
    "layouts/2x2.md:14":
        "9294d95d0c97f8227105debb1c5e5a64a743571a8de64de65ea6801131b12138",
    "layouts/2x2.md:15":
        "c9ef8e5461560a8605eb121452e94b21f23818c53c5b8ebaaef2d1bc7d1b27da",
    "layouts/2x2.md:16":
        "45b40231b9f11af8f878af7e18472e97eb99713a6460887193d947986d602ec5",
    "layouts/2x4.md:1":
        "0a15f996539bd82bf3e2b4df81b9d44ac0a4c0f0ecd9cbd78d7c0c5887ad3189",
    "layouts/2x4.md:2":
        "18b77a0fa006659cd64ba69763d6292e1d51b7d8cfa65d7532f2ddd3a370d07a",
    "layouts/2x4.md:3":
        "3566024e0b18c94dd1976f624a20a8c3436dde06b5f09f4e8a5a35ac7d28ece4",
    "layouts/2x4.md:4":
        "7446711969638a6cbd2cb08fab54f7890b436a2f10916790e018d8110c610b23",
    "layouts/2x4.md:5":
        "faf7898a7d65c4910e95bd28546887e79d2ee1226695263a0315b0667cd44226",
    "layouts/2x4.md:6":
        "e35696696c8480762224a685bff101c28467077e55a8a32a7aedc51c7a7f4a8d",
    "layouts/2x4.md:7":
        "8f25522e270d5d910bea8bfdcf5a4eaf6b736f66606191346589d928ecaa2994",
    "layouts/2x4.md:8":
        "6314d8c702cc6d23d9f7df6295b4eca64f8177fdb2fe1444fec8ef5960ad60ea",
    "layouts/2x4.md:9":
        "6771bc84bbf25c3b193d6141ea27ffe268b49ce55b66cecd6abbd7fcdefbedac",
    "layouts/2x4.md:10":
        "8a1f91f9deb030b7c9f813425d4ee66482fce68cf03e03fb0d2e5ee69455c48c",
    "layouts/2x4.md:11":
        "6341995cb629f48c07582847a7847d67cc9cffcc03105dd5875eb557eccf0be3",
    "layouts/2x4.md:12":
        "877cdb102dc4e402dbb8f097871b912b995a51b47cae2e995d87e1c0702bea53",
    "layouts/2x4.md:13":
        "9c3f2d38fe33a7f9357b2baa1a6da311e50f459e2373382501d9e9582500b3a5",
    "combinations/2x2.md:1":
        "18cbe76b8698eafc51ad9b298db53ab7a736f7126cb2178ab67e12e9aa22bcf0",
    "combinations/2x2.md:2":
        "278be0680a4ab4ad55ea6c37fe732034a846412006e4ecc64bc50f72da22350a",
    "combinations/2x2.md:3":
        "651f0027780a8c4b9332637da939f4824aa9502f3d1009c07c87699686096bda",
    "combinations/2x2.md:4":
        "41c0aaa6c5ce8b4f1b93ffd407b4419f34e4f515f970385919897eece9b88561",
}


def _rows(source):
    return [json.loads(line) for line in source.splitlines() if line.strip()]


def _roles(row):
    kind, props, children = row[1], row[2], row[3]
    if kind == "Layout":
        layout = props.get("layout")
        if layout in ("S-quad-content", "W-four-slots"):
            return QUAD
        if layout == "W-top-bottom":
            return ("primary", "details") if len(children) == 2 else ("title", "primary", "details")
        if layout == "S-content-dual-action":
            roles = ("first_action", "second_action")
            return roles if props.get("variant") == "actions-only" else ("content", *roles)
        mapping = {
            "S-center": ("content",),
            "S-title-content": ("title", "content"),
            "S-title-dual-content": ("title", "primary", "support"),
            "S-title-content-action": ("title", "content", "action"),
            "S-title-primary-secondary-action": ("title", "primary", "support", "action"),
            "S-title-anchor": ("title", "primary", "support", "action"),
            "S-title-dual-column-action": ("title", "left", "right", "action")[:len(children)],
            "S-dual-info": ("first", "second"),
            "W-split-panels": ("left", "right"),
            "W-content-side-slots": ("content", "upper", "lower"),
        }
        roles = mapping.get(layout)
    else:
        variant = props.get("variant")
        if kind == "Region":
            if variant in ("four-ratios", "four-items"):
                return QUAD
            mapping = {
                "center": ("primary",),
                "title-content": ("title", "body"),
                "title-hero-support": ("title", "primary", "support"),
                "title-content-action": ("title", "body", "action"),
                "title-hero-support-action": ("title", "primary", "support", "action"),
                "title-two-ratios": ("title", "left", "right", "action")[:len(children)],
            }
        else:
            assert kind == "Group"
            if variant == "supporting-items":
                return tuple(f"item_{index + 1}" for index in range(len(children)))
            mapping = {
                "hero-support": ("primary", "support"),
                "label-value": ("label", "value"),
                "peer-pair": ("left", "right"),
                "title-count": ("title", "count"),
            }
        roles = mapping.get(variant)
    assert roles is not None, row
    return roles


def _normalized_rows(source):
    """按首次出现顺序消去组件名，保留全部 Props、数据、定义顺序和有序边。"""
    names = {}

    def identifier(value):
        if value not in names:
            names[value] = f"node_{len(names)}"
        return names.get(value)

    normalized = []
    for row in _rows(source):
        if len(row) == 2:
            normalized.append(row)
            continue
        value = [identifier(row[0]), row[1], row[2]]
        if len(row) == 4:
            value.append([identifier(child) for child in row[3]])
        normalized.append(value)
    return normalized


def _digest(value):
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode()).hexdigest()


def _example_payload(section):
    input_match = re.search(r"```json\s*\n(.*?)```", section, re.DOTALL)
    output_match = BLOCK.search(section)
    assert input_match is not None and output_match is not None
    return json.loads(input_match.group(1)), output_match.group(1)


def _examples():
    examples = []
    for filename in EXAMPLE_FILES:
        for match in EXAMPLE.finditer((SOURCE / filename).read_text(encoding="utf-8")):
            examples.append(pytest.param(filename, match.group(1), match.group(2),
                                         id=f"{filename}-{match.group(1)}"))
    return examples


def _templates():
    templates = []
    for filename in TEMPLATE_FILES:
        for index, match in enumerate(BLOCK.finditer(
            (SOURCE / filename).read_text(encoding="utf-8")), 1
        ):
            templates.append(pytest.param(filename, index, match.group(1),
                                          id=f"{filename}-{index}"))
    return templates


def _assert_structural_names(rows):
    for row in rows:
        if len(row) != 4:
            continue
        expected = _roles(row)
        prefix = "" if row[0] == "root" else f"{row[0]}_"
        assert row[3] == [f"{prefix}{role}" for role in expected]


@pytest.mark.parametrize("filename,case,section", _examples())
def test_complete_examples_only_change_component_names(filename, case, section):
    input_value, source = _example_payload(section)
    expected = EXPECTED_EXAMPLES.get(f"{filename}:{case}")
    assert expected is not None
    assert _digest([input_value, _normalized_rows(source)]) == expected


@pytest.mark.parametrize("filename,case,section", _examples())
def test_complete_examples_are_closed_and_structurally_named(filename, case, section):
    _input_value, source = _example_payload(section)
    rows = [row for row in _rows(source) if len(row) >= 3]
    assert rows[0][0] == "root" and rows[0][1] == "Layout"
    nodes = {row[0]: row for row in rows}
    assert len(nodes) == len(rows)
    _assert_structural_names(rows)
    incoming = Counter()
    for row in rows:
        for child in row[3] if len(row) == 4 else []:
            assert child in nodes
            incoming[child] += 1
    for identifier in nodes:
        assert incoming.get(identifier, 0) == (0 if identifier == "root" else 1)
    pending, reached = ["root"], set()
    while pending:
        identifier = pending.pop()
        assert identifier not in reached
        reached.add(identifier)
        row = nodes.get(identifier)
        assert row is not None
        pending.extend(row[3] if len(row) == 4 else [])
    assert reached == set(nodes)


@pytest.mark.parametrize("filename,index,source", _templates())
def test_template_structure_unchanged_except_component_names(filename, index, source):
    expected = EXPECTED_TEMPLATES.get(f"{filename}:{index}")
    assert expected is not None
    assert _digest(_normalized_rows(source)) == expected
    _assert_structural_names(_rows(source))


def test_core_owns_reference_rules_and_only_complete_demonstration():
    assert len(_examples()) == 24 and len(_templates()) == 33
    core = (SOURCE / "core.md").read_text(encoding="utf-8")
    assert "children 中每个 ID 必须与本次输出某一组件行的第一项逐字一致" in core
    assert "组件 ID 引用不同于显示值的数据路径绑定" in core
    assert "不按设备、城市、指标或动作等业务名称改名" in core
    output = re.search(r"<!-- prompt:output -->(.*?)<!-- /prompt:output -->", core, re.DOTALL)
    assert output is not None
    example = BLOCK.search(output.group(1))
    assert example is not None
    _assert_structural_names(_rows(example.group(1)))
