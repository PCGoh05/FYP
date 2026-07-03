"""User-facing formatting for internal measurement values."""

import re
from typing import Any


INCH_VALUE_PATTERN = re.compile(r"(?<![\w.])(-?\d+(?:\.\d+)?)\s*in\b", re.IGNORECASE)


def _format_number(value: float) -> str:
    """Format a number without unnecessary trailing zeros."""
    text = f"{value:.2f}".rstrip("0").rstrip(".")
    return text if text else "0"


def _inch_to_cm_display(inches: float) -> str:
    """Return a Word-friendly centimetre display for an inch value."""
    # The JIWE reference hanging indent is stored in Word XML as 640 twips,
    # which Word displays as 1.13 cm. The profile stores the equivalent rule
    # as 0.44 in for readability, so display the Word-rounded value here.
    if abs(inches - 0.44) <= 0.005:
        return "1.13"
    return f"{inches * 2.54:.2f}"


def format_user_value(value: Any) -> str:
    """Return a clearer user-facing label for raw checker or auto-fix values."""
    if value is None:
        return "Not available"

    text = str(value)
    if text == "(inherited)":
        return "Uses Word style"

    def replace_inches(match: re.Match) -> str:
        raw_number = match.group(1)
        inches = float(raw_number)
        return f"{_format_number(inches)} in ({_inch_to_cm_display(inches)} cm)"

    return INCH_VALUE_PATTERN.sub(replace_inches, text)
