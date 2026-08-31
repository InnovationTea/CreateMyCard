from __future__ import annotations

from typing import Any

try:
    from ..jsx_to_a2ui.catalog.card_sizes import (
        CARD_SIZE_DIMENSIONS,
        DEFAULT_CARD_SIZE,
        resolve_card_size,
    )
    from ..jsx_to_a2ui.exceptions import ValidationError
except ImportError:  # Support direct execution through data_processing.py.
    from jsx_to_a2ui.catalog.card_sizes import (
        CARD_SIZE_DIMENSIONS,
        DEFAULT_CARD_SIZE,  # noqa: F401 - re-exported for direct-execution imports
        resolve_card_size,
    )
    from jsx_to_a2ui.exceptions import ValidationError


def task_card_size(task: dict[str, Any] | None, *, default: str | None = None) -> str | None:
    """Return a supported semantic card size from one model-facing task."""
    value = task.get("size") if isinstance(task, dict) else None
    if value is None:
        return default
    if value not in CARD_SIZE_DIMENSIONS:
        allowed = ", ".join(repr(item) for item in CARD_SIZE_DIMENSIONS)
        raise ValueError(f"任务 size 必须是 {allowed} 之一，收到 {value!r}")
    return value


def card_dimensions(size: object) -> tuple[int | float | str, int | float | str] | None:
    """Resolve semantic presets while retaining legacy square runtime sizes."""
    dimensions = None
    try:
        _, width, height = resolve_card_size(size)
    except ValidationError:
        pass
    else:
        dimensions = (width, height)
    return dimensions
