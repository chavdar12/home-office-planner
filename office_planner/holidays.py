"""Official Bulgarian non-working days."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Dict

# Fixed-date public holidays (month, day): name
FIXED_HOLIDAYS = {
    (1, 1): "New Year's Day",
    (3, 3): "Liberation Day",
    (5, 1): "Labour Day",
    (5, 6): "St. George's Day / Army Day",
    (5, 24): "Day of Bulgarian Culture and Literacy",
    (9, 6): "Unification Day",
    (9, 22): "Independence Day",
    (12, 24): "Christmas Eve",
    (12, 25): "Christmas Day",
    (12, 26): "Christmas (2nd day)",
}


def orthodox_easter(year: int) -> date:
    """Orthodox Easter (Gregorian date), Meeus Julian algorithm. Valid 1900-2099."""
    a, b, c = year % 4, year % 7, year % 19
    d = (19 * c + 15) % 30
    e = (2 * a + 4 * b - d + 34) % 7
    month = (d + e + 114) // 31
    day = (d + e + 114) % 31 + 1
    return date(year, month, day) + timedelta(days=13)


def bulgarian_holidays(year: int) -> Dict[date, str]:
    """All official non-working days of a year, including moved days off.

    A fixed holiday falling on a weekend moves to the next working day
    (Labour Code, art. 154(2)). Easter days themselves are not moved, but a
    fixed holiday coinciding with Holy Saturday (e.g. May 1, 2027) is.
    """
    hol = {date(year, m, d): n for (m, d), n in FIXED_HOLIDAYS.items()}
    fixed = set(hol)

    easter = orthodox_easter(year)
    easter_days = {
        easter - timedelta(days=2): "Good Friday",
        easter - timedelta(days=1): "Holy Saturday",
        easter: "Easter Sunday",
        easter + timedelta(days=1): "Easter Monday",
    }
    for d, n in easter_days.items():
        hol[d] = f"{hol[d]} / {n}" if d in hol else n

    moved = {}
    for d in sorted(hol):
        if d not in fixed or d.weekday() < 5:
            continue
        nxt = d + timedelta(days=1)
        while nxt.weekday() >= 5 or nxt in hol or nxt in moved:
            nxt += timedelta(days=1)
        moved[nxt] = f"Day off (moved from {hol[d].split(' / ')[0]})"
    hol.update(moved)
    return hol
