"""CardTpl 格式、词法保真、编译兼容及命令行写回回归。"""

from __future__ import annotations

import io
import subprocess
import sys
from pathlib import Path

import pytest

from services.template_generation.engine.cardplan import provider_bundle
from services.template_generation.tools.format_cardtpl import (
    CardTplFormatError,
    _tokens,
    format_cardtpl,
    main,
)

_ROOT = Path(__file__).resolve().parents[1]
_FIXTURES = Path(__file__).parent / "fixtures/cardtpl_formatter"
_PROVIDERS = _ROOT / "resources/source/providers"
_SOURCE = '#Template Demo@1(props: {})\ndata = {}\nColumn({},Text("你好"))\n#End\n'


def _lexical_content(source: str) -> list[str]:
    return [token.text for token in _tokens(source) if token.kind != "newline"]


def _assert_only_commas_added(source: str, formatted: str) -> None:
    original = _lexical_content(source)
    index = 0
    for token in _lexical_content(formatted):
        if index < len(original) and original[index] == token:
            index += 1
        else:
            assert token == ","
    assert index == len(original)


def test_user_weather_example() -> None:
    source = (_FIXTURES / "weather.input.cardtpl").read_text(encoding="utf-8")
    expected = (_FIXTURES / "weather.expected.cardtpl").read_text(encoding="utf-8")
    assert format_cardtpl(source) == expected
    assert format_cardtpl(expected) == expected


@pytest.mark.parametrize("path", sorted(_PROVIDERS.rglob("*.cardtpl")), ids=lambda p: p.stem)
def test_repository_templates_preserve_tokens_and_are_idempotent(path: Path) -> None:
    source = path.read_text(encoding="utf-8")
    formatted = format_cardtpl(source)
    _assert_only_commas_added(source, formatted)
    assert format_cardtpl(formatted) == formatted


@pytest.mark.parametrize(
    "manifest", sorted(_PROVIDERS.glob("*/provider.json")), ids=lambda p: p.parent.name
)
def test_formatted_templates_compile_identically(
    manifest: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = provider_bundle.load_provider_bundle(manifest.parent)
    read_bytes = provider_bundle._bounded_file_bytes

    def formatted_bytes(path: Path) -> bytes:
        content = read_bytes(path)
        if path.suffix == ".cardtpl":
            content = format_cardtpl(content.decode("utf-8")).encode("utf-8")
        return content

    monkeypatch.setattr(provider_bundle, "_bounded_file_bytes", formatted_bytes)
    formatted = provider_bundle.load_provider_bundle(manifest.parent)
    assert formatted.templates == original.templates


@pytest.mark.parametrize(
    "body",
    (
        'Text("逗号, 冒号: 括号(){}[] // #if", {"value": $theme(\'primaryColor\')})',
        r'''Text("转义\"与\\", {"value": [1, {"nested": [2, 3]}]})''',
        'Text(`第一行\n#if 不是指令\n${data.value},第二行`)',
        'Text(#Expr(data.a ? data.a : (props.b ? props.b : "未知")), {"maxLines": 1})',
        'Text(Expr(data.a + "," + data.b), {"constraintSize": {"minWidth": 0}})',
        '#if props.a\nText("a")\n#elseif props.b\nText("b")\n#else\n'
        '#if props.c\nText("c")\n#end\n#endif',
        '#match present(\n data.a, (data.b => `B:${data.b}`)\n) as items\n'
        '#case 0\nText("空")\n#default\nText(items[0])\n#end',
        '// 独立注释\nText("a"), // 行尾注释\n/* 多行\n注释 */\nText("b")',
        'Text("a", {"size": {"min": 0, // 嵌套注释\n"max": 1}})',
        'Text("a") // 逗号在下一行\n, Text("b")',
        'Text("a" /* 注释在参数间 */, {"size": 12})',
    ),
)
def test_expressions_directives_and_comments_are_preserved(body: str) -> None:
    source = f"#Template Demo@1(props: {{}})\nColumn(\n{body}\n)\n#End\n"
    formatted = format_cardtpl(source)
    _assert_only_commas_added(source, formatted)
    assert format_cardtpl(formatted) == formatted


@pytest.mark.parametrize(
    "body,expected",
    (
        ('Text("a")\nText("b")', 'Text("a"),\nText("b")'),
        ('Text("a"),\nText("b"),', 'Text("a"),\nText("b"),'),
        ('#if props.a\nText("a")\n#endif\nText("b")',
         '#if props.a\nText("a"),\n#endif\nText("b")'),
        ('#if props.a\nText("a")\n#elseif props.b\nText("b")\n#endif',
         '#if props.a\nText("a"),\n#elseif props.b\nText("b")\n#endif'),
        ('#if props.a\nText("a")\n#endif', '#if props.a\nText("a")\n#endif'),
        ('Text("a") // 注释\nText("b")', 'Text("a"),\n// 注释\nText("b")'),
        ('Text("a") // 注释\n, Text("b")', 'Text("a")\n// 注释\n,\nText("b")'),
        ('Text("a,b")\n#if props.a\n#endif', 'Text("a,b")\n#if props.a\n#endif'),
        ('#match present(data.a) as items\n#case 0\nText("a")\n#default\n'
         'Text("b")\n#end',
         '#match present(data.a) as items\n#case 0\nText("a"),\n#default\n'
         'Text("b")\n#end'),
    ),
)
def test_component_separators(body: str, expected: str) -> None:
    source = f"#Template Demo@1(props: {{}})\nColumn(\n{body}\n)\n#End\n"
    formatted = format_cardtpl(source)
    indented = "\n".join("    " + line for line in expected.splitlines())
    assert formatted == f"#Template Demo@1(props: {{}})\nColumn(\n{indented}\n)\n#End\n"
    _assert_only_commas_added(source, formatted)
    assert format_cardtpl(formatted) == formatted


@pytest.mark.parametrize(
    "body",
    (
        '#if props.a\nText("a")\n#endif\nText("tail")',
        '#if props.a\nText("a")\n#elseif props.b\nText("b")\n#else\nText("c")\n#endif',
        '#if props.a\n#if props.b\nText("inner")\n#endif\nText("a")\n#endif\nText("tail")',
        '#if props.a\n#elseif props.b\nText("b")\n#else\n#endif\nText("tail")',
    ),
)
def test_conditional_separators_keep_compiled_structure(body: str) -> None:
    original_body = f"Column(\n{body}\n)"
    source = f"#Template Demo@1(props: {{}})\n{original_body}\n#End\n"
    _, formatted_body = format_cardtpl(source).split("\n", 1)
    formatted_body = formatted_body.removesuffix("\n#End\n")
    assert provider_bundle._parse_component_body(formatted_body) == (
        provider_bundle._parse_component_body(original_body)
    )


@pytest.mark.parametrize(
    "source,message",
    (
        ('#Template Demo@1(props: {})\nText("未闭合)\n#End', "字符串未闭合"),
        ("#Template Demo@1(props: {})\nColumn(\n#End", "括号.*未闭合"),
        ("#Template Demo@1(props: {})\nColumn({])\n#End", "闭括号"),
        ("#Template Demo@1(props: {})\nColumn()", "缺少 #End"),
        ("#Template Demo@1(props: {})\n#if props.a\nText(1)\n#End", "#if 未闭合"),
        ("#Template Demo@1(props: {})\n#else\n#End", "缺少对应"),
        ("#Template Demo@1(props: {})\n/* 未闭合", "块注释未闭合"),
        ("#End", "缺少模板声明"),
        ("garbage", "预期 #Template"),
        ("#Template Demo@1", "模板声明不完整"),
        ("#Template Demo@1(props: {})\n#Template Other@1(props: {})", "缺少 #End"),
    ),
)
def test_invalid_source_has_location(source: str, message: str) -> None:
    with pytest.raises(CardTplFormatError, match=message) as error:
        format_cardtpl(source)
    assert "行，第" in str(error.value)


def test_formatter_keeps_template_declaration_on_one_line() -> None:
    header = '#Template Layout@1(props: { title: string }, ...children)'
    source = header + '\n'
    source += 'data = {}\nColumn({}, Text(props.title), children)\n#End\n'
    formatted = format_cardtpl(source)
    assert formatted.splitlines()[0] == header
    assert formatted.splitlines()[1] == 'data = {}'


def test_empty_bom_and_crlf() -> None:
    assert format_cardtpl(" \n\t") == ""
    formatted = format_cardtpl("\ufeff" + _SOURCE.replace("\n", "\r\n"))
    assert formatted == "\ufeff" + format_cardtpl(_SOURCE)


def test_runtime_expression_keeps_exact_internal_whitespace() -> None:
    expression = 'Expr(  data.a  ? "a"  :\n  data.b  )'
    source = f'#Template Demo@1(props: {{}})\nText({expression}, {{"maxLines": 1}})\n#End'
    assert expression in format_cardtpl(source)


def test_cli_preview_check_write_and_idempotence(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / "example.cardtpl"
    path.write_text(_SOURCE, encoding="utf-8")
    assert main([str(path)]) == 0
    assert capsys.readouterr().out == format_cardtpl(_SOURCE)
    assert path.read_text(encoding="utf-8") == _SOURCE
    assert main(["--check", str(path)]) == 1
    assert "需要格式化" in capsys.readouterr().out
    assert main(["--write", str(tmp_path), str(path)]) == 0
    assert capsys.readouterr().err.count("已格式化") == 1
    assert path.read_text(encoding="utf-8") == format_cardtpl(_SOURCE)
    stamp = path.stat().st_mtime_ns
    assert main(["--write", str(path)]) == 0
    assert path.stat().st_mtime_ns == stamp
    assert main(["--check", str(tmp_path)]) == 0


def test_cli_batch_parse_failure_does_not_write(tmp_path: Path) -> None:
    good = tmp_path / "a.cardtpl"
    bad = tmp_path / "b.cardtpl"
    good.write_text(_SOURCE, encoding="utf-8")
    bad.write_text(_SOURCE + "Text(", encoding="utf-8")
    assert main(["--write", str(tmp_path)]) == 2
    assert good.read_text(encoding="utf-8") == _SOURCE


def test_cli_recursive_and_ignores_other_extensions(tmp_path: Path) -> None:
    nested = tmp_path / "nested"
    nested.mkdir()
    path = nested / "demo.cardtpl"
    path.write_text(_SOURCE, encoding="utf-8")
    other = tmp_path / "ignore.txt"
    other.write_text("ignored", encoding="utf-8")
    assert main(["--write", str(tmp_path)]) == 0
    assert path.read_text(encoding="utf-8") == format_cardtpl(_SOURCE)
    assert other.read_text(encoding="utf-8") == "ignored"


def test_cli_invalid_paths_and_modes(tmp_path: Path) -> None:
    assert main([str(tmp_path)]) == 2
    assert main([str(tmp_path / "missing.cardtpl")]) == 2
    assert main(["--write", "-"]) == 2
    assert main(["-", str(tmp_path)]) == 2
    for name in ("a.cardtpl", "b.cardtpl"):
        (tmp_path / name).write_text(_SOURCE, encoding="utf-8")
    assert main([str(tmp_path)]) == 2
    (tmp_path / "bad.cardtpl").write_bytes(b"\xff")
    assert main(["--check", str(tmp_path)]) == 2


def test_cli_stdin(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO(_SOURCE))
    assert main(["-"]) == 0
    assert capsys.readouterr().out == format_cardtpl(_SOURCE)
    monkeypatch.setattr(sys, "stdin", io.StringIO(_SOURCE))
    assert main(["--check", "-"]) == 1


def test_standalone_script_requires_no_service_imports() -> None:
    result = subprocess.run(
        [sys.executable, "-I", "-S", str(_ROOT / "tools/format_cardtpl.py"), "-"],
        input=_SOURCE,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == format_cardtpl(_SOURCE)
