from __future__ import annotations

from dataclasses import dataclass

from ..exceptions import ValidationError


@dataclass(frozen=True, slots=True)
class Appearance:
    name: str
    background: str
    gradient: dict | None
    shadow: dict
    primary: str
    secondary: str
    action_background: str
    action_text: str
    action_icon: str
    circle_background: str
    circle_text: str
    circle_icon: str
    progress_track: str
    progress_bar: str
    progress_icon: str


_SOFT_SHADOW = {"offsetX": 0, "offsetY": 2, "radius": 8, "color": "#1A000000"}
_STRONG_SHADOW = {"offsetX": 0, "offsetY": 2, "radius": 8, "color": "#2E000000"}


def _gradient(*stops: tuple[str, float]) -> dict:
    return {"angle": 180, "colors": [[color, offset] for color, offset in stops], "repeating": False}


def _soft(name: str, accent: str) -> Appearance:
    return Appearance(
        name=name,
        background="#FFFFFFFF",
        gradient=_gradient((f"#1A{accent}", 0), ("#00FFFFFF", 1)),
        shadow=_SOFT_SHADOW,
        primary="#FF000000",
        secondary="#99000000",
        action_background=f"#1A{accent}",
        action_text=f"#FF{accent}",
        action_icon=f"#FF{accent}",
        circle_background=f"#FF{accent}",
        circle_text="#FFFFFFFF",
        circle_icon="#FFFFFFFF",
        progress_track="#1A000000",
        progress_bar="#FF64BB5C",
        progress_icon="#99000000",
    )


def _dark(name: str, gradient: dict, action_accent: str, *, background: str) -> Appearance:
    return Appearance(
        name=name,
        background=background,
        gradient=gradient,
        shadow=_STRONG_SHADOW,
        primary="#FFFFFFFF",
        secondary="#99FFFFFF",
        action_background="#FFFFFFFF",
        action_text=action_accent,
        action_icon=action_accent,
        circle_background="#FFFFFFFF",
        circle_text=action_accent,
        circle_icon=action_accent,
        progress_track="#1AFFFFFF",
        progress_bar="#FFFFFFFF",
        progress_icon="#99FFFFFF",
    )


APPEARANCES: dict[str, Appearance] = {
    "blue-soft": _soft("blue-soft", "0A59F7"),
    "green-soft": _soft("green-soft", "64BB5C"),
    "neutral-soft": _soft("neutral-soft", "000000"),
    "pink-soft": _soft("pink-soft", "E64566"),
    "yellow-soft": _soft("yellow-soft", "F7CE00"),
    "cyan-soft": _soft("cyan-soft", "46B1E3"),
    "sunny-gradient": _dark(
        "sunny-gradient",
        _gradient(("#FF317AF7", 0), ("#FF46B1E3", 1)),
        "#FF317AF7",
        background="#FF317AF7",
    ),
    # A2UI v0.9 has one linearGradient per component. The runtime's three
    # ellipse layers therefore lower to their documented linear fallback.
    "cloudy-gradient": _dark(
        "cloudy-gradient",
        _gradient(("#FF2B3242", 0), ("#FF7486A0", 0.68), ("#FF5A6C84", 1)),
        "#FF2B3242",
        background="#FF2B3242",
    ),
    "slate-gradient": _dark(
        "slate-gradient",
        _gradient(("#FF173573", 0), ("#FF008FBF", 0.68), ("#FF4174D9", 1)),
        "#FF173573",
        background="#FF173573",
    ),
    "purple-gradient": _dark(
        "purple-gradient",
        _gradient(("#FFAC49F5", 0), ("#FFC386F0", 1)),
        "#FFAC49F5",
        background="#FFAC49F5",
    ),
    "orange-gradient": _dark(
        "orange-gradient",
        _gradient(("#FFED6F21", 0), ("#FFF9A01E", 1)),
        "#FFED6F21",
        background="#FFED6F21",
    ),
    "type0-gradient": _dark(
        "type0-gradient",
        _gradient(("#FFBF3F26", 0), ("#FFFF8E3E", 0.68), ("#FFFAA89E", 1)),
        "#FFBF3F26",
        background="#FFBF3F26",
    ),
}


def get_appearance(name: str | None) -> Appearance:
    key = name or "blue-soft"
    try:
        return APPEARANCES[key]
    except KeyError as exc:
        raise ValidationError(f"unknown Card appearance {key!r}") from exc
