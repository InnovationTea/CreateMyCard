from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .catalog.bindings import CompileContext, materialize_binding_literals
from .catalog.display_values import merge_data_models
from .converters.registry import create_context
from .emitter.messages import build_messages
from .exceptions import A2UIProtocolOutputError, ValidationError
from .parser.jsx_parser import extract_card_functions
from .validation.protocol_validator import validate_messages


def _surface_id(card_name: str) -> str:
    value = re.sub(r"[^A-Za-z0-9]+", "-", card_name).strip("-").lower()
    return value or "card"


def compile_source(
    source: str,
    *,
    card: str | None = None,
    compile_all: bool = False,
    data_models: dict[str, dict[str, Any]] | None = None,
    compile_contexts: dict[str, CompileContext | dict[str, Any]] | None = None,
) -> dict[str, list[dict[str, Any]]]:
    cards = extract_card_functions(source)
    if card:
        if card not in cards:
            raise ValidationError(f"card function {card!r} was not found; available: {', '.join(cards)}")
        selected = {card: cards[card]}
    elif compile_all:
        selected = cards
    elif len(cards) == 1:
        selected = cards
    else:
        raise ValidationError("input contains multiple cards; pass --card NAME or --all")

    outputs: dict[str, list[dict[str, Any]]] = {}
    for name, jsx in selected.items():
        compile_context = CompileContext.from_payload((compile_contexts or {}).get(name))
        materialize_binding_literals(jsx, compile_context)
        context = create_context(name, compile_context=compile_context)
        root = context.convert(jsx)
        explicit_data_model = (data_models or {}).get(name)
        if explicit_data_model is not None and context.used_data_ids:
            raise ValidationError(
                f"card {name!r} cannot combine compile-time dataIds with an explicit data_models entry"
            )
        generated_data_model = None
        if (compile_context.data_model or context.derived_data_model) and (
            context.used_data_ids or context.used_action_ids
        ):
            generated_data_model = merge_data_models(
                compile_context.data_model,
                context.derived_data_model,
            )
        try:
            messages = build_messages(
                root,
                _surface_id(name),
                explicit_data_model if explicit_data_model is not None else generated_data_model,
            )
            validate_messages(messages)
        except ValidationError as exc:
            raise A2UIProtocolOutputError(str(exc)) from exc
        except Exception as exc:
            raise A2UIProtocolOutputError(
                f"{type(exc).__name__}: {exc}"
            ) from exc
        outputs[name] = messages
    return outputs


def compile_file(path: str | Path, **kwargs) -> dict[str, list[dict[str, Any]]]:
    source = Path(path).read_text(encoding="utf-8")
    return compile_source(source, **kwargs)
