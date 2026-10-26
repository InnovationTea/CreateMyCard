"""Current boolean text must remain a restricted, non-executing resolver."""

import pytest

from services.display_text import concatenated_display_text, current_display_text


@pytest.mark.parametrize("condition,expected", [(True, "Battery 80%"), (False, "Offline")])
def test_boolean_conditional_preserves_binding_concatenation(condition, expected):
    data = {"/connected": condition, "/battery": 80}
    value = "{{ ${/connected} ? 'Battery ' + ${/battery} + '%' : 'Offline' }}"
    assert current_display_text(value, data.get) == expected
    assert concatenated_display_text(value, data.get) is None


def test_conditional_only_requires_current_branch_values():
    value = '{{ ${/connected} ? "OK: ?" : ${/missing} }}'
    assert current_display_text(value, {"/connected": True}.get) == "OK: ?"
    assert current_display_text(value, {"/connected": False}.get) is None


@pytest.mark.parametrize("value", [
    "{{ ${/connected} ? 'OK' : danger() }}",
    "{{ ${/connected} ? danger() : 'NO' }}",
    "{{ ${/connected} ? 'OK' }}",
    "{{ ${/connected} ? 'OK' : 'NO' }} trailing",
    "{{ ${/connected} ? 'OK' : 'NO' + }}",
    "{{ ${/connected} ? 'OK' : ${/battery} + ${/battery} }}",
    "{{ ${/battery} > 0 ? 'OK' : 'NO' }}",
    "{{ ${/connected} ? 'OK' : ${/other} ? 'YES' : 'NO' }}",
])
def test_unsupported_or_malformed_expressions_are_not_executed(value):
    assert current_display_text(value, {"/connected": False, "/battery": 80}.get) is None


@pytest.mark.parametrize("value,expected", [
    ("Static", "Static"), ("", ""),
    ("{{ ${/battery} + '%' }}", "80%"),
    ("{{ 'Battery ' + ${/battery} }}", "Battery 80"),
    ("{{ ${/battery} + ${/battery} }}", None),
    ("{{ ${/missing} }}", None),
    (None, None),
])
def test_existing_concatenation_contract_is_unchanged(value, expected):
    assert current_display_text(value, {"/battery": 80}.get) == expected
    assert concatenated_display_text(value, {"/battery": 80}.get) == expected


@pytest.mark.parametrize("value,expected", [
    ("{{ 'Today ' + (${/condition} + ' ' + ${/range}) }}", "Today Cloudy 25 / 32"),
    ("{{ (('Battery ' + (${/battery}))) + '%' }}", "Battery 80%"),
    ("{{ (${/battery}) }}", "80"),
    ("{{ (${/battery} + '%') + (' / ' + (${/battery} + '%')) }}", "80% / 80%"),
    ("{{ 'Battery ' + (${/battery}) + ${/battery} }}", "Battery 8080"),
    ("{{ ('' + '') }}", ""),
    ("{{ '(' + (${/condition} + ') + ? :') }}", "(Cloudy) + ? :"),
    (r"{{ 'First\n' + ('Second' + '\nThird') }}", "First\nSecond\nThird"),
    (r"""{{ ('it\'s ' + "\"quoted\"") }}""", 'it\'s "quoted"'),
])
def test_grouped_concatenation_is_enabled_only_for_current_theme_text(value, expected):
    data = {"/battery": 80, "/condition": "Cloudy", "/range": "25 / 32"}
    assert current_display_text(value, data.get) == expected
    assert concatenated_display_text(value, data.get) is None


@pytest.mark.parametrize("value", [
    "{{ () }}",
    "{{ ('A' }}",
    "{{ 'A') }}",
    "{{ ('A')) }}",
    "{{ ('A') ('B') }}",
    "{{ ('A' 'B') }}",
    "{{ ('A') ${/battery} }}",
    "{{ 'A' ('B') }}",
    "{{ ('A' +) }}",
    "{{ (+ 'A') }}",
    "{{ ('A' ++ 'B') }}",
    "{{ ('A' - 'B') }}",
    "{{ (1 + 'A') }}",
    "{{ ('A' + ${/missing}) }}",
    "{{ ('A' + ${/flag}) }}",
    "{{ ('A' + ${/items}) }}",
    "{{ ('A' + ${/object}) }}",
    "{{ ('A' + (${/battery} + ${/battery})) }}",
    "{{ (${/battery} + ${/battery}) + '%' }}",
    "{{ (danger()) }}",
    "{{ ('A').upper() }}",
    "{{ ('A') }} trailing",
    "{{ (${ /battery}) }}",
])
def test_invalid_grouped_expression_still_fails_closed(value):
    data = {"/battery": 80, "/flag": True, "/items": [], "/object": {}}
    assert current_display_text(value, data.get) is None
    assert concatenated_display_text(value, data.get) is None


def test_deep_grouping_does_not_recurse():
    value = "{{ " + "(" * 1200 + "'Text'" + ")" * 1200 + " }}"
    assert current_display_text(value, {}.get) == "Text"
