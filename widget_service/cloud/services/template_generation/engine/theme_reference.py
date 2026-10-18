"""Closed `$theme(...)` reference syntax shared by CardTpl and Tersel."""

from __future__ import annotations

import io
import tokenize

THEME_REFERENCE_PATHS = (
    "primaryColor",
    "supportContentColor",
    "progressColor",
    "progressBackgroundColor",
    "actionStyle.backgroundColor",
    "actionStyle.contentColor",
    "supportContentStyle.backgroundColor",
    "supportContentStyle.borderRadius",
)


class ThemeReferenceSyntaxError(ValueError):
    """Raised when `$theme(...)` does not use the closed call syntax."""


def translate_theme_reference_calls(source: str, internal_name: str) -> str:
    """Translate `$theme(...)` into one parser-private direct call outside strings."""
    try:
        tokens = list(tokenize.generate_tokens(io.StringIO(source).readline))
    except tokenize.TokenError as exc:
        message = f"Theme reference tokenization failed: {exc.args[0]}"
        raise ThemeReferenceSyntaxError(message) from exc
    translated: list[tokenize.TokenInfo] = []
    index = 0
    while index < len(tokens):
        token = tokens[index]
        if token.type == tokenize.NAME and token.string == internal_name:
            raise ThemeReferenceSyntaxError("Theme reference uses a reserved internal name")
        if token.type == tokenize.OP and token.string == "$":
            translated.append(_translate_theme_token(tokens, index, internal_name))
            index += 2
            continue
        translated.append(token)
        index += 1
    return tokenize.untokenize(translated)


def _translate_theme_token(
    tokens: list[tokenize.TokenInfo],
    index: int,
    internal_name: str,
) -> tokenize.TokenInfo:
    if index + 2 >= len(tokens):
        raise ThemeReferenceSyntaxError("Theme reference is incomplete")
    dollar = tokens[index]
    name = tokens[index + 1]
    opening = tokens[index + 2]
    is_theme_name = name.type == tokenize.NAME and name.string == "theme"
    is_direct_name = dollar.end == name.start
    is_call = opening.type == tokenize.OP and opening.string == "("
    if not is_theme_name or not is_direct_name or not is_call:
        raise ThemeReferenceSyntaxError("Only direct `$theme(...)` references are allowed")
    return tokenize.TokenInfo(
        tokenize.NAME,
        internal_name,
        dollar.start,
        name.end,
        dollar.line,
    )


__all__ = [
    "THEME_REFERENCE_PATHS",
    "ThemeReferenceSyntaxError",
    "translate_theme_reference_calls",
]
