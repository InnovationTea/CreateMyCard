"""天气能力的两个易混读数使用原绑定；其它读数不新增标签。"""
import json
from pathlib import Path

import pytest

from services.card_validation import CompactDslValidationError, validate_compact_dsl
from services.compact_weather_readouts import selected_weather_readouts
from services.theme_style_roles import layout_phase


@pytest.mark.parametrize("mode", ["bare", "inline", "items", "swapped"])
@pytest.mark.parametrize("wind,probability", [(2, 20), (3, 40)])
def test_weather_readouts_share_their_label_with_the_correct_value(mode, wind, probability):
    root = "/data/forecast"
    paths = [root + "/current/windLevel", root + "/daily/0/rainProbabilityPercent"]
    values = [f"{{{{ ${{{paths[0]}}} + '级' }}}}", f"{{{{ ${{{paths[1]}}} + '%' }}}}"]
    items = [{"value": value} for value in values]
    for index, label in enumerate(["风力", "降水概率"]):
        if mode == "items":
            items[index]["label"] = label
        elif mode == "inline":
            items[index]["value"] = values[index].replace("{{ ", "{{ '" + label + " ' + ")
        elif mode == "swapped":
            items[1 - index]["label"] = label
    rows = [
        ["root", "Column", {}, ["main", "support"]],
        ["main", "EmphasizedData", {"value": {"path": "/data/battery"}, "unit": "%"}],
        ["support", "SecondaryBody", {"items": items, "columns": 1}],
        [paths[0], wind], [paths[1], probability], ["/data/battery", 80],
    ]
    spec = {"size": "2x4", "dataModelSchema": {"data": {
        "forecast": {"current": {"windLevel": {"type": "integer", "sampleValue": wind}},
                     "daily": [{"rainProbabilityPercent": {
                         "type": "number", "sampleValue": probability,
                     }}]},
        "battery": {"type": "integer", "sampleValue": 80},
    }}}
    card = {"suggestSize": "2x4", "dataBindings": [
        {"capabilityId": "ViewWeather", "writeResultTo": root},
    ]}
    plan = {"info_required": [{"dataId": path} for path in [*paths, "/data/battery"]]}
    source = "\n".join(json.dumps(row, ensure_ascii=False) for row in rows)
    with layout_phase():
        if mode in {"bare", "swapped"}:
            with pytest.raises(CompactDslValidationError) as error:
                validate_compact_dsl(source, task_spec=spec, card_spec=card, compact_plan=plan)
            assert "须在同一项显示“风力”" in str(error.value)
            assert "须在同一项显示“降水概率”" in str(error.value)
        else:
            validate_compact_dsl(source, task_spec=spec, card_spec=card, compact_plan=plan)


def test_only_selected_viewweather_fields_receive_directions():
    bindings = [{"capabilityId": "ViewWeather", "writeResultTo": "/data/today"},
                {"capabilityId": "Other", "writeResultTo": "/data/other"}]
    paths = ["/data/today/daily/2/rainProbabilityPercent", "/data/today/current/temperatureText",
             "/data/other/current/windLevel"]
    plan = {"info_required": [{"dataId": path} for path in paths]}
    assert selected_weather_readouts({"dataBindings": bindings}, plan) == {
        paths[0]: ("降水概率", "降雨概率"),
    }


def test_q037_generation_prompt_only_identifies_the_two_weather_fields():
    from models.generation import TaskSpec
    from services.prompt_builder import PromptBuilder

    fixture = Path(__file__).resolve().parents[2] / "debug_tools/Datasets/online_updated/Q037.json"
    request = json.loads(fixture.read_text(encoding="utf-8"))
    bindings = request.get("candidateDataBindings")
    assert bindings
    facts = []
    for binding in bindings:
        for pointer in binding.get("candidateOutputFields", []):
            facts.append({"dataId": binding.get("writeResultTo") + pointer, "priority": "must"})
    plan = {"info_required": facts, "layoutHints": []}
    task = TaskSpec(userQuery=request.get("userQuery"), size="2x4", dataModelSchema={"data": {}})
    roles = ("system", "user", "user", "assistant")
    conversation = [{"role": role, "content": "test"} for role in roles]
    messages = PromptBuilder.build_compact_dsl_continuation(
        conversation, task, plan, card_spec={"dataBindings": bindings},
    )
    hints = [line for line in messages[-1]["content"].splitlines() if "的可见读数须" in line]
    assert len(hints) == 2
    wind_instruction = "/data/weather/current/windLevel 的可见读数须在同一项说明“风力”"
    assert any(wind_instruction in hint for hint in hints)
    assert any("/data/weather/daily/0/rainProbabilityPercent" in hint for hint in hints)
