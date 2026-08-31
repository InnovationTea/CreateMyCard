from __future__ import annotations

from ..exceptions import ValidationError


CARD_SIZE_DIMENSIONS: dict[str, tuple[int, int]] = {
    "2x2": (160, 160),
    "2x4": (320, 160),
}

DEFAULT_CARD_SIZE = "2x2"


def resolve_card_size(size: object | None) -> tuple[str | None, int | float, int | float]:
    """Resolve semantic sizes while retaining positive numeric legacy squares."""
    value = DEFAULT_CARD_SIZE if size is None else size
    if isinstance(value, str):
        dimensions = CARD_SIZE_DIMENSIONS.get(value)
        if dimensions is None:
            allowed = ", ".join(repr(item) for item in CARD_SIZE_DIMENSIONS)
            raise ValidationError(f"Card.size must be one of {allowed}, or a positive legacy number")
        return value, dimensions[0], dimensions[1]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value <= 0:
        raise ValidationError("Card.size must be a semantic size or a positive legacy number")
    return None, value, value
