import re
from datetime import datetime

MAX_AMOUNT = 10_000_000  # 1 crore — reject anything above as a likely parse error

_DATE_FORMATS = ("%d/%m/%Y", "%d-%m-%Y", "%d/%m/%y", "%d-%m-%y", "%d %B %Y", "%d %b %Y")


def parse_amount(val) -> float | None:
    if not val:
        return None
    cleaned = str(val).replace(",", "").strip()
    try:
        v = float(cleaned)
        return v if 0 < v <= MAX_AMOUNT else None
    except ValueError:
        return None


def parse_date(val) -> datetime | None:
    if not val:
        return None
    raw = str(val).strip()
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(raw, fmt)
        except ValueError:
            continue
    return None
