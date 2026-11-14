"""Decide which working days are office days and which are home-office days."""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

from .config import PlannerConfig
from .dates import months_in_range
from .holidays import bulgarian_holidays

OFFICE, HOME, HOLIDAY, DAY_OFF = "office", "home", "holiday", "day_off"
NON_WORKING = {HOLIDAY, DAY_OFF}


def plan_range(start: date, end: date,
               config: Optional[PlannerConfig] = None) -> Dict[date, str]:
    """Plan of every weekday from start to end (inclusive).

    Whole months are planned (the office target is monthly), then trimmed.
    """
    out = {}
    for y, m in months_in_range(start, end):
        for d, kind in plan_month(y, m, config).items():
            if start <= d <= end:
                out[d] = kind
    return out


def weekdays_of_month(year: int, month: int) -> List[date]:
    d, out = date(year, month, 1), []
    while d.month == month:
        if d.weekday() < 5:
            out.append(d)
        d += timedelta(days=1)
    return out


def required_office_days(working_days: int, share: float) -> int:
    return math.ceil(round(working_days * share, 6))


def plan_month(year: int, month: int, config: Optional[PlannerConfig] = None,
               holidays: Optional[Dict[date, str]] = None) -> Dict[date, str]:
    """Return {date: kind} for every weekday (Mon-Fri) of the month.

    1. Official holidays are non-working.
    2. Manual overrides from the config are kept as they are.
    3. The configured office weekdays are office days.
    4. If the office share is still below target, extra office days are added,
       first in the weeks with the fewest office days, then by weekday preference.
    """
    config = config or PlannerConfig()
    if holidays is None:
        holidays = bulgarian_holidays(year)

    plan, locked = {}, set()
    for d in weekdays_of_month(year, month):
        if d in holidays:
            plan[d] = HOLIDAY
            locked.add(d)
        elif d in config.overrides:
            plan[d] = config.overrides[d]
            locked.add(d)
        else:
            plan[d] = OFFICE if d.weekday() in config.office_weekdays else HOME

    working = [d for d, k in plan.items() if k not in NON_WORKING]
    required = required_office_days(len(working), config.office_share)
    office = sum(plan[d] == OFFICE for d in working)

    pref = list(config.extra_preference)
    rank = lambda wd: pref.index(wd) if wd in pref else len(pref)
    week = lambda d: d.isocalendar()[:2]

    while office < required:
        candidates = [d for d in working if plan[d] == HOME and d not in locked]
        if not candidates:
            break
        per_week = Counter(week(d) for d in working if plan[d] == OFFICE)
        best = min(candidates, key=lambda d: (per_week[week(d)], rank(d.weekday()), d))
        plan[best] = OFFICE
        office += 1
    return plan


def is_workday(d: date) -> bool:
    return d.weekday() < 5 and d not in bulgarian_holidays(d.year)


def add_days_off(config: PlannerConfig, start: date, end: date) -> int:
    """Mark every working day from start to end (inclusive) as a day off."""
    if end < start:
        start, end = end, start
    added, d = 0, start
    while d <= end:
        if is_workday(d) and config.overrides.get(d) != DAY_OFF:
            config.overrides[d] = DAY_OFF
            added += 1
        d += timedelta(days=1)
    return added


def day_off_periods(config: PlannerConfig) -> List[Tuple[date, date, List[date]]]:
    """Group days off into periods; weekends/holidays in between don't split them."""
    periods: List[Tuple[date, date, List[date]]] = []
    for d in sorted(k for k, v in config.overrides.items() if v == DAY_OFF):
        if periods:
            start, end, days = periods[-1]
            gap = end + timedelta(days=1)
            while gap < d and not is_workday(gap):
                gap += timedelta(days=1)
            if gap == d:
                periods[-1] = (start, d, days + [d])
                continue
        periods.append((d, d, [d]))
    return periods


@dataclass(frozen=True)
class MonthStats:
    year: int
    month: int
    working: int
    office: int
    home: int
    holidays: int
    days_off: int
    required: int

    @property
    def share(self) -> float:
        return self.office / self.working if self.working else 0.0

    @property
    def meets_target(self) -> bool:
        return self.office >= self.required


def month_stats(year: int, month: int, plan: Dict[date, str],
                config: Optional[PlannerConfig] = None) -> MonthStats:
    config = config or PlannerConfig()
    counts = Counter(plan.values())
    working = counts[OFFICE] + counts[HOME]
    return MonthStats(year, month, working, counts[OFFICE], counts[HOME],
                      counts[HOLIDAY], counts[DAY_OFF],
                      required_office_days(working, config.office_share))
