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
