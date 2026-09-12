from __future__ import annotations

from dataclasses import dataclass, replace

from ..exceptions import ValidationError


@dataclass(frozen=True, slots=True)
class Appearance:
    name: str
    background: str
    gradient: dict | None
    shadow: dict | None
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


def _palette(name: str, background: str, content: str, stops: tuple[str, ...] = ()) -> Appearance:
    primary = f"#FF{content}"
    secondary = f"#99{content}"
    tertiary = f"#1A{content}"
    gradient = None
    if stops:
        gradient = {
            "angle": 180,
            "colors": [[f"#FF{color}", offset] for color, offset in zip(stops, (0, 0.68, 1), strict=True)],
            "repeating": False,
        }
    return Appearance(
        name=name, background=f"#FF{background}", gradient=gradient, shadow=None,
        primary=primary, secondary=secondary,
        action_background=tertiary, action_text=primary, action_icon=primary,
        circle_background=tertiary, circle_text=primary, circle_icon=primary,
        progress_track=f"#33{content}", progress_bar=primary, progress_icon=secondary,
    )


# A2UI-only orb fallback: retain the source palette as a linear approximation.
# JSX uses the authored ellipse layers and backdrop blur, not these gradients.
APPEARANCES: dict[str, Appearance] = {
    "solid-white": _palette("solid-white", "FFFFFF", "000000"),
    "solid-blue": _palette("solid-blue", "E5EDFE", "1F4799"),
    "solid-orange": _palette("solid-orange", "FFF3E6", "99661F"),
    "solid-green": _palette("solid-green", "F0FFE6", "52991F"),
    "solid-cyan": _palette("solid-cyan", "E6FDFF", "1F8F99"),
    "solid-purple": _palette("solid-purple", "EDE6FF", "401F99"),
    "orb-orange": _palette("orb-orange", "BF3F26", "FFFFFF", ("BF3F26", "FF8E3E", "FAA89E")),
    "orb-blue": _palette("orb-blue", "121E59", "FFFFFF", ("121E59", "8FA2D9", "52CCCC")),
    "orb-purple": _palette("orb-purple", "1B1259", "FFFFFF", ("1B1259", "5761D9", "B398D9")),
    "orb-green": _palette("orb-green", "17734C", "FFFFFF", ("17734C", "26BFA6", "60BF98")),
}

APPEARANCE_ALIASES = {
    "neutral-soft": "solid-white",
    "blue-soft": "solid-blue",
    "pink-soft": "solid-orange",
    "yellow-soft": "solid-orange",
    "green-soft": "solid-green",
    "cyan-soft": "solid-cyan",
    "sunny-gradient": "orb-blue",
    "cloudy-gradient": "orb-blue",
    "slate-gradient": "orb-blue",
    "purple-gradient": "orb-purple",
    "orange-gradient": "orb-orange",
    "type0-gradient": "orb-orange",
}
APPEARANCES.update({
    alias: replace(APPEARANCES[target], name=alias)
    for alias, target in APPEARANCE_ALIASES.items()
})


def get_appearance(name: str | None) -> Appearance:
    key = name or "blue-soft"
    try:
        return APPEARANCES[key]
    except KeyError as exc:
        raise ValidationError(f"unknown Card appearance {key!r}") from exc


def resolve_appearance_name(name: str | None, size: str | None = None) -> str:
    canonical = APPEARANCE_ALIASES.get(name, name) or "solid-white"
    get_appearance(canonical)
    if size == "2x4" and canonical.startswith("orb-"):
        return canonical.replace("orb-", "solid-", 1)
    return canonical
