"""
utils/date_utils.py – Date helpers
====================================
"""

from datetime import date


def next_month_str() -> str:
    """Return YYYY-MM string for the month after today."""
    today = date.today()
    if today.month == 12:
        return f"{today.year + 1}-01"
    return f"{today.year}-{today.month + 1:02d}"


def current_month_str() -> str:
    """Return YYYY-MM string for the current month."""
    today = date.today()
    return f"{today.year}-{today.month:02d}"


def month_label(yyyymm: str) -> str:
    """Convert 'YYYY-MM' to a human-readable label like 'April 2025'."""
    from datetime import datetime
    dt = datetime.strptime(yyyymm, "%Y-%m")
    return dt.strftime("%B %Y")
