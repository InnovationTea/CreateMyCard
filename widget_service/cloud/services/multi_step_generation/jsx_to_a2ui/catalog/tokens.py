from ..exceptions import ValidationError


COLORS = {
    "blue": "#FF0A59F7",
    "green": "#FF64BB5C",
    "red": "#FFE84026",
    "orange": "#FFED6F21",
    "yellow": "#FFF7CE00",
    "purple": "#FFAC49F5",
    "pink": "#FFE64566",
    "cyan": "#FF61CFBE",
    "secondary": "#FF454545",
    "white": "#FFFFFFFF",
    "black": "#FF000000",
}

LIGHT_COLORS = {
    "blue": "#1A0A59F7",
    "green": "#1A64BB5C",
    "red": "#1AE84026",
    "orange": "#1AED6F21",
    "yellow": "#1AF7CE00",
    "purple": "#1AAC49F5",
    "pink": "#1AE64566",
    "cyan": "#1A61CFBE",
    "secondary": "#1A000000",
}

BUTTON_COLOR_ALIASES = {
    "primary": "blue",
    "secondary": "secondary",
    "success": "green",
    "discovery": "purple",
    "danger": "red",
    "warning": "orange",
    "caution": "yellow",
}


def normalize_color(value: str) -> str:
    color = str(value)
    if color.startswith("#") and len(color) == 7:
        return "#FF" + color[1:].upper()
    if color.startswith("#") and len(color) == 9:
        return color.upper()
    raise ValidationError(f"A2UI colors must use #RRGGBB or #AARRGGBB: {value!r}")


def solid_color(name: str) -> str:
    return COLORS.get(name, COLORS["blue"])


def light_color(name: str) -> str:
    return LIGHT_COLORS.get(name, LIGHT_COLORS["blue"])
