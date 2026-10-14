"""Read advance widths from the checked-in HarmonyOS TrueType fonts.

This measures unshaped text. CSS shaping, fallback glyphs and line breaking can
still differ, so callers must keep the result advisory near a width boundary.
"""
from __future__ import annotations

from bisect import bisect_right
from functools import lru_cache
from pathlib import Path
from struct import unpack_from


_FONT_DIR = Path(__file__).resolve().parents[1] / "resources/fonts/harmony/HarmonyOS_SansSC"


@lru_cache(maxsize=3)
def _font_tables(weight: int) -> tuple[bytes, int, list[tuple[int, int, int]], list[int]]:
    name = {
        400: "HarmonyOS_SansSC_Regular.ttf",
        500: "HarmonyOS_SansSC_Medium.ttf",
        700: "HarmonyOS_SansSC_Bold.ttf",
    }[weight]
    data = (_FONT_DIR / name).read_bytes()
    table_count = unpack_from(">H", data, 4)[0]
    tables = {
        data[12 + index * 16:16 + index * 16]: unpack_from(">II", data, 20 + index * 16)
        for index in range(table_count)
    }
    units_per_em = unpack_from(">H", data, tables[b"head"][0] + 18)[0]
    metrics_count = unpack_from(">H", data, tables[b"hhea"][0] + 34)[0]
    hmtx_offset = tables[b"hmtx"][0]
    advances = [unpack_from(">H", data, hmtx_offset + index * 4)[0]
                for index in range(metrics_count)]
    cmap_offset = tables[b"cmap"][0]
    subtables = unpack_from(">H", data, cmap_offset + 2)[0]
    groups: list[tuple[int, int, int]] = []
    for index in range(subtables):
        offset = cmap_offset + unpack_from(">I", data, cmap_offset + 8 + index * 8)[0]
        if unpack_from(">H", data, offset)[0] != 12:
            continue
        count = unpack_from(">I", data, offset + 12)[0]
        groups = [unpack_from(">III", data, offset + 16 + group * 12)
                  for group in range(count)]
        break
    if not groups:
        raise ValueError(f"Unicode cmap format 12 missing from {name}")
    return data, units_per_em, groups, advances


def text_advance(value: object, font_size: float, weight: int = 400) -> float:
    """Return the sum of TrueType glyph advances in CSS px for simple text."""
    _, units_per_em, groups, advances = _font_tables(weight)
    starts = [group[0] for group in groups]
    total = 0
    for character in str(value):
        codepoint = ord(character)
        index = bisect_right(starts, codepoint) - 1
        if index < 0 or codepoint > groups[index][1]:
            raise ValueError(f"font has no glyph for U+{codepoint:04X}")
        glyph = groups[index][2] + codepoint - groups[index][0]
        total += advances[min(glyph, len(advances) - 1)]
    return total * font_size / units_per_em
