"""Small date helpers."""

from __future__ import annotations

import calendar
from datetime import date, timedelta
from typing import Iterator, List, Tuple


def iter_months(year: int, month: int, count: int) -> Iterator[Tuple[int, int]]:
    for _ in range(count):
        yield year, month
        month += 1
        if month > 12:
            year, month = year + 1, 1


def add_months(d: date, n: int) -> date:
    """Same day n months later (clamped to the month's last day)."""
    y, m = divmod(d.year * 12 + d.month - 1 + n, 12)
    m += 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def range_for_months(start: date, months: int) -> Tuple[date, date]:
    """E.g. 6 Nov + 1 month -> 6 Nov .. 5 Dec."""
    return start, add_months(start, months) - timedelta(days=1)


def months_in_range(start: date, end: date) -> List[Tuple[int, int]]:
    count = (end.year - start.year) * 12 + end.month - start.month + 1
    return list(iter_months(start.year, start.month, max(count, 0)))
