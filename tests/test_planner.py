from __future__ import annotations

import math
import unittest
from datetime import date

from office_planner.config import PlannerConfig
from office_planner.dates import add_months, iter_months, months_in_range, range_for_months
from office_planner.holidays import bulgarian_holidays
from office_planner.planner import (
    DAY_OFF,
    HOLIDAY,
    HOME,
    OFFICE,
    add_days_off,
    day_off_periods,
    month_stats,
    plan_month,
    plan_range,
)

MONTHS = [(y, m) for y in range(2026, 2031) for m in range(1, 13)]


def plan(y: int, m: int, config: PlannerConfig | None = None) -> dict[date, str]:
    return plan_month(y, m, config, bulgarian_holidays(y))


class TestDefaultPlan(unittest.TestCase):
    def test_covers_all_weekdays_only(self) -> None:
        for y, m in MONTHS:
            for d in plan(y, m):
                self.assertLess(d.weekday(), 5)
                self.assertEqual((d.year, d.month), (y, m))

    def test_holidays_are_never_office(self) -> None:
        for y, m in MONTHS:
            hol = bulgarian_holidays(y)
            for d, kind in plan(y, m).items():
                self.assertEqual(kind == HOLIDAY, d in hol, d)

    def test_monday_and_wednesday_are_office(self) -> None:
        for y, m in MONTHS:
            for d, kind in plan(y, m).items():
                if d.weekday() in (0, 2) and kind != HOLIDAY:
                    self.assertEqual(kind, OFFICE, d)

    def test_at_least_half_office_and_not_more_than_needed(self) -> None:
        for y, m in MONTHS:
            with self.subTest(month=f"{y}-{m:02d}"):
                p = plan(y, m)
                working = [d for d, k in p.items() if k != HOLIDAY]
                office = [d for d, k in p.items() if k == OFFICE]
                mandatory = [d for d in working if d.weekday() in (0, 2)]
                required = math.ceil(len(working) / 2)
                self.assertEqual(len(office), max(required, len(mandatory)))

    def test_regular_week_pattern(self) -> None:
        p = plan(2026, 11)
        week = {d.weekday(): p[d] for d in p if 9 <= d.day <= 13}
        self.assertEqual(week, {0: OFFICE, 1: OFFICE, 2: OFFICE, 3: HOME, 4: HOME})

    def test_full_weeks_get_at_most_one_extra_day(self) -> None:
        for y, m in MONTHS:
            weeks: dict[tuple[int, int], list[str]] = {}
            for d, k in plan(y, m).items():
                weeks.setdefault(d.isocalendar()[:2], []).append(k)
            for wk, kinds in weeks.items():
                if len(kinds) == 5 and HOLIDAY not in kinds:
                    with self.subTest(month=f"{y}-{m:02d}", week=wk):
                        self.assertLessEqual(kinds.count(OFFICE), 3)


class TestCustomConfig(unittest.TestCase):
    def test_different_fixed_days_and_preference(self) -> None:
        cfg = PlannerConfig(office_weekdays=[1, 3], extra_preference=[4, 0, 2])
        p = plan(2026, 11, cfg)
        week = {d.weekday(): p[d] for d in p if 9 <= d.day <= 13}
        self.assertEqual(week, {0: HOME, 1: OFFICE, 2: HOME, 3: OFFICE, 4: OFFICE})

    def test_share(self) -> None:
        for share in (0, 0.25, 0.6, 1):
            cfg = PlannerConfig(office_weekdays=[], office_share=share)
            s = month_stats(2026, 11, plan(2026, 11, cfg), cfg)
            self.assertEqual(s.office, math.ceil(s.working * share))

    def test_override_home_on_monday_is_compensated(self) -> None:
        cfg = PlannerConfig(overrides={date(2026, 11, 9): HOME})
        p = plan(2026, 11, cfg)
        self.assertEqual(p[date(2026, 11, 9)], HOME)
        self.assertGreaterEqual(month_stats(2026, 11, p, cfg).share, 0.5)

    def test_override_office_reduces_extra_days(self) -> None:
        default = month_stats(2026, 11, plan(2026, 11))
        cfg = PlannerConfig(overrides={date(2026, 11, 13): OFFICE})  # a Friday
        p = plan(2026, 11, cfg)
        self.assertEqual(p[date(2026, 11, 13)], OFFICE)
        self.assertEqual(month_stats(2026, 11, p, cfg).office, default.office)

    def test_day_off_reduces_working_days(self) -> None:
        cfg = PlannerConfig(overrides={date(2026, 11, 10): DAY_OFF})
        s = month_stats(2026, 11, plan(2026, 11, cfg), cfg)
        self.assertEqual((s.working, s.days_off), (20, 1))

    def test_override_on_holiday_is_ignored(self) -> None:
        cfg = PlannerConfig(overrides={date(2026, 12, 24): OFFICE})
        self.assertEqual(plan(2026, 12, cfg)[date(2026, 12, 24)], HOLIDAY)


class TestDaysOff(unittest.TestCase):
    def test_add_range_skips_weekends_and_holidays(self) -> None:
        cfg = PlannerConfig()
        # Dec 21 2026 (Mon) - Jan 1 2027 (Fri): 24-28 Dec and 1 Jan are holidays.
        added = add_days_off(cfg, date(2026, 12, 21), date(2027, 1, 1))
        self.assertEqual(added, 6)
        self.assertEqual(sorted(cfg.overrides), [
            date(2026, 12, 21), date(2026, 12, 22), date(2026, 12, 23),
            date(2026, 12, 29), date(2026, 12, 30), date(2026, 12, 31)])
        self.assertTrue(all(v == DAY_OFF for v in cfg.overrides.values()))

    def test_add_reversed_range_and_no_duplicates(self) -> None:
        cfg = PlannerConfig()
        self.assertEqual(add_days_off(cfg, date(2026, 11, 13), date(2026, 11, 9)), 5)
        self.assertEqual(add_days_off(cfg, date(2026, 11, 9), date(2026, 11, 13)), 0)

    def test_add_replaces_office_override(self) -> None:
        cfg = PlannerConfig(overrides={date(2026, 11, 10): OFFICE})
        self.assertEqual(add_days_off(cfg, date(2026, 11, 10), date(2026, 11, 10)), 1)
        self.assertEqual(cfg.overrides[date(2026, 11, 10)], DAY_OFF)

    def test_periods_bridge_weekends_and_holidays(self) -> None:
        cfg = PlannerConfig()
        add_days_off(cfg, date(2026, 12, 21), date(2027, 1, 1))  # spans Christmas
        add_days_off(cfg, date(2027, 1, 4), date(2027, 1, 5))  # continues after weekend
        add_days_off(cfg, date(2027, 2, 10), date(2027, 2, 10))  # separate
        periods = day_off_periods(cfg)
        self.assertEqual([(s, e, len(days)) for s, e, days in periods], [
            (date(2026, 12, 21), date(2027, 1, 5), 8),
            (date(2027, 2, 10), date(2027, 2, 10), 1)])

    def test_gap_of_one_working_day_splits_periods(self) -> None:
        cfg = PlannerConfig()
        add_days_off(cfg, date(2026, 11, 9), date(2026, 11, 9))
        add_days_off(cfg, date(2026, 11, 11), date(2026, 11, 11))
        self.assertEqual(len(day_off_periods(cfg)), 2)

    def test_other_overrides_not_listed(self) -> None:
        cfg = PlannerConfig(overrides={date(2026, 11, 9): HOME})
        self.assertEqual(day_off_periods(cfg), [])


class TestDateRange(unittest.TestCase):
    def test_add_months_clamps_day(self) -> None:
        self.assertEqual(add_months(date(2026, 11, 6), 1), date(2026, 12, 6))
        self.assertEqual(add_months(date(2026, 11, 6), 12), date(2027, 11, 6))
        self.assertEqual(add_months(date(2027, 1, 31), 1), date(2027, 2, 28))

    def test_range_for_months(self) -> None:
        today = date(2026, 11, 6)
        self.assertEqual(range_for_months(today, 1), (today, date(2026, 12, 5)))
        self.assertEqual(range_for_months(today, 2), (today, date(2027, 1, 5)))
        self.assertEqual(range_for_months(today, 12), (today, date(2027, 11, 5)))

    def test_months_in_range(self) -> None:
        self.assertEqual(months_in_range(date(2026, 11, 6), date(2027, 1, 5)),
                         [(2026, 11), (2026, 12), (2027, 1)])
        self.assertEqual(months_in_range(date(2026, 11, 6), date(2026, 11, 20)),
                         [(2026, 11)])

    def test_plan_range_trims_but_plans_whole_months(self) -> None:
        start, end = date(2026, 11, 16), date(2026, 12, 4)
        p = plan_range(start, end)
        self.assertEqual(min(p), start)
        self.assertEqual(max(p), end)
        full_nov = plan(2026, 11)
        for d, kind in p.items():
            if d.month == 11:
                self.assertEqual(kind, full_nov[d])


class TestHelpers(unittest.TestCase):
    def test_iter_months_wraps_year(self) -> None:
        self.assertEqual(list(iter_months(2026, 11, 4)),
                         [(2026, 11), (2026, 12), (2027, 1), (2027, 2)])

    def test_stats(self) -> None:
        s = month_stats(2027, 5, plan(2027, 5))
        self.assertEqual((s.working, s.office, s.home, s.holidays), (17, 9, 8, 4))
        self.assertTrue(s.meets_target)


if __name__ == "__main__":
    unittest.main()
