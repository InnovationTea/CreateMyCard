#!/usr/bin/env python3
"""保留源码词法内容的 CardTpl 格式化器及独立命令行入口。"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path

_TOKEN = re.compile(r"[A-Za-z_$#][\w$@-]*|\d+(?:\.\d+)?|[^\s]", re.UNICODE)
_DIRECTIVES = frozenset(
    {"#if", "#elseif", "#else", "#endif", "#end", "#match", "#case", "#default", "#End"}
)
_CLOSERS = {"(": ")", "{": "}", "[": "]"}


class CardTplFormatError(ValueError):
    """源码结构不完整，无法安全格式化。"""


@dataclass(frozen=True)
class _Token:
    text: str
    start: int
    spaced: bool = False
    kind: str = "token"


@dataclass(frozen=True)
class _Group:
    opening: _Token
    items: tuple[_Node, ...]
    closing: _Token
    source: str


@dataclass(frozen=True)
class _Directive:
    items: tuple[_Node, ...]


type _Node = _Token | _Group | _Directive


def _error(source: str, start: int, message: str) -> CardTplFormatError:
    line = source.count("\n", 0, start) + 1
    column = start - source.rfind("\n", 0, start)
    return CardTplFormatError(f"第 {line} 行，第 {column} 列：{message}")


def _quoted_end(source: str, start: int) -> int:
    quote = source[start]
    index = start + 1
    while index < len(source):
        if source[index] == "\\":
            index += 2
            continue
        if source[index] == quote:
            return index + 1
        index += 1
    raise _error(source, start, "字符串未闭合")


def _tokens(source: str) -> list[_Token]:
    result: list[_Token] = []
    index = 0
    spaced = False
    while index < len(source):
        char = source[index]
        if char.isspace():
            if char == "\n":
                result.append(_Token("\n", index, kind="newline"))
            spaced = True
            index += 1
            continue
        kind = "token"
        if char in "\"'`":
            end = _quoted_end(source, index)
            kind = "string"
        elif source.startswith("//", index):
            end = source.find("\n", index)
            if end < 0:
                end = len(source)
            kind = "comment"
        elif source.startswith("/*", index):
            closing = source.find("*/", index + 2)
            if closing < 0:
                raise _error(source, index, "块注释未闭合")
            end = closing + 2
            kind = "comment"
        else:
            match = _TOKEN.match(source, index)
            if match is None:
                raise _error(source, index, "无法识别字符")
            end = match.end()
        result.append(_Token(source[slice(index, end)], index, spaced, kind))
        index = end
        spaced = False
    return result


class _Parser:
    def __init__(self, source: str) -> None:
        self.source = source
        self.tokens = _tokens(source)
        self.index = 0

    def parse(self) -> tuple[_Node, ...]:
        items: list[_Node] = []
        while self.index < len(self.tokens):
            if self.tokens[self.index].kind == "newline":
                self.index += 1
                continue
            items.append(self._node())
        return tuple(items)

    def _node(self) -> _Node:
        token = self.tokens[self.index]
        self.index += 1
        node: _Node = token
        if token.text in _CLOSERS:
            node = self._group(token)
        elif token.text in _CLOSERS.values():
            raise _error(self.source, token.start, f"多余的闭括号 {token.text}")
        elif token.text in _DIRECTIVES:
            items: list[_Node] = [token]
            while self.index < len(self.tokens):
                if self.tokens[self.index].kind == "newline":
                    break
                items.append(self._node())
            node = _Directive(tuple(items))
        return node

    def _group(self, opening: _Token) -> _Group:
        closing = _CLOSERS.get(opening.text)
        assert closing is not None
        items: list[_Node] = []
        while self.index < len(self.tokens):
            token = self.tokens[self.index]
            if token.text == closing:
                self.index += 1
                raw = self.source[slice(opening.start, token.start + 1)]
                return _Group(opening, tuple(items), token, raw)
            if token.kind == "newline":
                self.index += 1
                continue
            items.append(self._node())
        raise _error(self.source, opening.start, f"括号 {opening.text} 未闭合")


def _first(node: _Node) -> _Token:
    result: _Token
    if isinstance(node, _Token):
        result = node
    elif isinstance(node, _Group):
        result = node.opening
    else:
        result = _first(node.items[0])
    return result


def _is_token(node: _Node, text: str) -> bool:
    return isinstance(node, _Token) and node.text == text


def _inline(items: tuple[_Node, ...], *, signature: bool = False) -> str:
    result = ""
    previous = ""
    for node in items:
        token = _first(node)
        if isinstance(node, _Group):
            if node.opening.text == "(":
                # 非组件调用的参数属于表达式，连同内部空白原样保留。
                text = node.source
            else:
                content = _inline(node.items, signature=signature)
                if signature and node.opening.text == "{" and content:
                    content = f" {content} "
                text = node.opening.text + content + node.closing.text
        elif isinstance(node, _Directive):
            text = _inline(node.items, signature=signature)
        else:
            text = node.text
            if node.kind == "comment" and text.startswith("//"):
                text += "\n"
        separator = " " if token.spaced or previous in {",", ":"} else ""
        if token.text in {",", ":"}:
            separator = ""
        result += (separator if result else "") + text
        previous = token.text
    return result


def _chunks(items: tuple[_Node, ...]) -> list[tuple[_Node, ...]]:
    """只按当前层逗号分段，字符串和嵌套表达式始终是完整节点。"""
    chunks: list[tuple[_Node, ...]] = []
    current: list[_Node] = []
    for node in items:
        current.append(node)
        if _is_token(node, ","):
            chunks.append(tuple(current))
            current = []
    if current:
        chunks.append(tuple(current))
    return chunks


def _component_at(items: tuple[_Node, ...], index: int) -> bool:
    if index + 1 >= len(items):
        return False
    name, group = items[index], items[index + 1]
    if not isinstance(name, _Token) or not isinstance(group, _Group):
        return False
    return (
        group.opening.text == "("
        and name.text[0].isupper()
        and name.text not in {"Expr", "Bind", "Param", "Asset", "EventAction"}
    )


def _validate_directives(items: tuple[_Node, ...], source: str) -> None:
    stack: list[tuple[str, _Token, bool]] = []
    for node in items:
        if isinstance(node, _Group):
            _validate_directives(node.items, source)
        if not isinstance(node, _Directive):
            continue
        token = _first(node)
        name = token.text
        if name in {"#if", "#match"}:
            stack.append((name, token, False))
            continue
        if name == "#End":
            continue
        if not stack:
            raise _error(source, token.start, f"{name} 缺少对应的开始指令")
        opening, start, fallback = stack[-1]
        if name == "#end" or (name == "#endif" and opening == "#if"):
            stack.pop()
        elif name in {"#else", "#elseif"} and opening == "#if" and not fallback:
            stack[-1] = (opening, start, name == "#else")
        elif name in {"#case", "#default"} and opening == "#match" and not fallback:
            stack[-1] = (opening, start, name == "#default")
        else:
            raise _error(source, token.start, f"{name} 与 {opening} 的分支结构不匹配")
    if stack:
        name, token, _ = stack[-1]
        raise _error(source, token.start, f"{name} 未闭合")


class _Printer:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def line(self, text: str, indent: int) -> None:
        self.lines.append("    " * indent + text)

    def object(self, group: _Group, indent: int, prefix: str = "") -> None:
        if not group.items:
            self.line(prefix + "{}", indent)
            return
        self.line(prefix + "{", indent)
        for chunk in _chunks(group.items):
            self.inline_lines(chunk, indent + 1)
        self.line("}", indent)

    def inline_lines(self, items: tuple[_Node, ...], indent: int) -> None:
        pending: list[_Node] = []
        for node in items:
            if isinstance(node, _Token) and node.kind == "comment":
                if pending:
                    self.line(_inline(tuple(pending)), indent)
                    pending = []
                self.line(node.text, indent)
            else:
                pending.append(node)
        if pending:
            self.line(_inline(tuple(pending)), indent)

    def component(self, name: _Token, group: _Group, indent: int) -> None:
        chunks = _chunks(group.items)
        first: tuple[_Node, ...] = chunks[0] if chunks else ()
        simple_first = bool(first) and not isinstance(first[0], (_Group, _Directive))
        inline_first = simple_first and not _component_at(first, 0)
        if inline_first:
            inline_first = not any(_first(node).kind == "comment" for node in first)
        if inline_first:
            suffix = _inline(first)
            if len(first) == len(group.items) and not _is_token(first[-1], ","):
                self.line(f"{name.text}({suffix})", indent)
                return
            self.line(f"{name.text}({suffix}", indent)
            self.sequence(group.items[slice(len(first), None)], indent + 1)
        else:
            self.line(f"{name.text}(", indent)
            self.sequence(group.items, indent + 1)
        self.line(")", indent)

    def sequence(self, items: tuple[_Node, ...], indent: int) -> None:
        index = 0
        while index < len(items):
            node = items[index]
            if _is_token(node, ","):
                if not self.lines or self.lines[-1].lstrip().startswith("//"):
                    self.line(",", indent)
                else:
                    self.lines[-1] += ","
                index += 1
            elif isinstance(node, _Directive):
                self.line(_inline(node.items), indent)
                index += 1
            elif _component_at(items, index):
                name, group = items[index], items[index + 1]
                assert isinstance(name, _Token) and isinstance(group, _Group)
                self.component(name, group, indent)
                index += 2
            elif isinstance(node, _Group) and node.opening.text == "{":
                self.object(node, indent)
                index += 1
            elif isinstance(node, _Token) and node.kind == "comment":
                self.line(node.text, indent)
                index += 1
            else:
                end = index + 1
                while end < len(items):
                    if isinstance(items[end], _Directive) or _component_at(items, end):
                        break
                    if _is_token(items[end - 1], ","):
                        break
                    end += 1
                self.inline_lines(items[slice(index, end)], indent)
                index = end


def format_cardtpl(source: str) -> str:
    """格式化完整 CardTpl 文件；保留所有非空白词法内容，结构错误时抛出异常。"""
    bom = "\ufeff" if source.startswith("\ufeff") else ""
    source = source.removeprefix("\ufeff")
    items = _Parser(source).parse()
    _validate_directives(items, source)
    printer = _Printer()
    index = 0
    in_template = False
    while index < len(items):
        node = items[index]
        if isinstance(node, _Token) and node.kind == "comment":
            printer.line(node.text, 0)
            index += 1
            continue
        if _is_token(node, "#Template"):
            if in_template or index + 2 >= len(items):
                raise _error(source, _first(node).start, "模板声明不完整或缺少 #End")
            name, signature = items[index + 1], items[index + 2]
            if not isinstance(signature, _Group) or signature.opening.text != "(":
                raise _error(source, _first(name).start, "模板声明缺少参数括号")
            if printer.lines and printer.lines[-1] == "#End":
                printer.lines.append("")
            parameters = _inline(signature.items, signature=True)
            printer.line(f"#Template {_inline((name,))}({parameters})", 0)
            index += 3
            in_template = True
            continue
        if isinstance(node, _Directive) and _first(node).text == "#End":
            if not in_template:
                raise _error(source, _first(node).start, "#End 缺少模板声明")
            printer.line(_inline(node.items), 0)
            index += 1
            in_template = False
            continue
        if not in_template:
            raise _error(source, _first(node).start, "预期 #Template 声明")
        if _is_token(node, "data") and index + 2 < len(items):
            equals, group = items[index + 1], items[index + 2]
            if _is_token(equals, "=") and isinstance(group, _Group):
                printer.object(group, 0, "data = ")
                index += 3
                continue
        end = index + 1
        while end < len(items):
            following = items[end]
            if isinstance(following, _Directive) and _first(following).text == "#End":
                break
            if _is_token(following, "#Template"):
                break
            end += 1
        printer.sequence(items[slice(index, end)], 0)
        index = end
    if in_template:
        raise _error(source, len(source), "模板缺少 #End")
    formatted = "\n".join(printer.lines) + ("\n" if printer.lines else "")
    original_tokens = [token.text for token in _tokens(source) if token.kind != "newline"]
    formatted_tokens = [token.text for token in _tokens(formatted) if token.kind != "newline"]
    if original_tokens != formatted_tokens:
        raise _error(source, 0, "当前语法无法在保留词法内容的前提下格式化")
    return bom + formatted


def _paths(arguments: list[str]) -> list[Path]:
    paths: list[Path] = []
    seen: set[Path] = set()
    for argument in arguments:
        path = Path(argument)
        candidates = sorted(path.rglob("*.cardtpl")) if path.is_dir() else [path]
        if not candidates:
            raise ValueError(f"目录内没有 .cardtpl 文件：{path}")
        for candidate in candidates:
            if not candidate.is_file() or candidate.suffix != ".cardtpl":
                raise ValueError(f"不是 .cardtpl 文件：{candidate}")
            resolved = candidate.resolve()
            if resolved not in seen:
                paths.append(resolved)
                seen.add(resolved)
    return paths


def main(argv: list[str] | None = None) -> int:
    """返回 0 表示成功，1 表示存在格式差异，2 表示输入或读写错误。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", help=".cardtpl 文件、目录，或 -（标准输入）")
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument("--write", "-w", action="store_true", help="原地写回")
    modes.add_argument("--check", action="store_true", help="只检查格式")
    args = parser.parse_args(argv)
    status = 0
    try:
        if "-" in args.paths:
            if args.paths != ["-"] or args.write:
                raise ValueError("标准输入不能与文件路径或 --write 混用")
            source = sys.stdin.read()
            formatted = format_cardtpl(source)
            if args.check:
                status = int(source != formatted)
            else:
                sys.stdout.write(formatted)
        else:
            paths = _paths(args.paths)
            if len(paths) != 1 and not (args.check or args.write):
                raise ValueError("批量格式化请使用 --write 或 --check")
            outputs: list[tuple[Path, str, bool]] = []
            for path in paths:
                try:
                    source = path.read_bytes().decode("utf-8")
                    formatted = format_cardtpl(source)
                except (OSError, UnicodeError, CardTplFormatError) as exc:
                    raise ValueError(f"{path}: {exc}") from exc
                outputs.append((path, formatted, source != formatted))
            for path, formatted, changed in outputs:
                if args.check and changed:
                    print(f"需要格式化：{path}")
                    status = 1
                elif args.write and changed:
                    path.write_bytes(formatted.encode("utf-8"))
                    print(f"已格式化：{path}", file=sys.stderr)
                elif not args.check and not args.write:
                    sys.stdout.write(formatted)
    except (OSError, ValueError, RecursionError) as exc:
        print(f"格式化失败：{exc}", file=sys.stderr)
        status = 2
    return status


if __name__ == "__main__":
    raise SystemExit(main())
