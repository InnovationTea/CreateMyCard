from datetime import datetime, timezone


def parse_iso_timestamp_ms(iso: str) -> int:
    if len(iso) < 20:
        raise ValueError(f"invalid timestamp: {iso}")

    normalized = iso.replace("Z", "+00:00")
    if "." in normalized:
        base, rest = normalized.split(".", 1)
        frac = rest.split("+")[0]
        tz_part = "+" + rest.split("+", 1)[1] if "+" in rest else ""
        frac = (frac + "000")[:3]
        normalized = f"{base}.{frac}{tz_part}"

    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def format_duration_ms(ms: int) -> str:
    if ms < 0:
        return "N/A"
    if ms < 1000:
        return f"{ms} ms"
    return f"{ms / 1000:.2f} s"
