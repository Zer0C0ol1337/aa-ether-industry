"""Template-Filter für die Anzeige von ISK und Dauer."""

from django import template

register = template.Library()


@register.filter
def isk(value, decimals=2):
    """Formatiert Zahlen deutsch: 1.234.567,89."""
    try:
        text = f"{float(value):,.{int(decimals)}f}"
    except (TypeError, ValueError):
        return "–"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


@register.filter
def duration(seconds):
    """Formatiert Sekunden als „2d 3h 15m“."""
    try:
        seconds = int(seconds)
    except (TypeError, ValueError):
        return "–"
    days, rest = divmod(seconds, 86400)
    hours, rest = divmod(rest, 3600)
    minutes = rest // 60
    parts = [f"{days}d"] if days else []
    if hours or days:
        parts.append(f"{hours}h")
    parts.append(f"{minutes}m")
    return " ".join(parts)
