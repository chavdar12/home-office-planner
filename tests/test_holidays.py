import unittest
from datetime import date

from office_planner.holidays import bulgarian_holidays, orthodox_easter


class TestOrthodoxEaster(unittest.TestCase):
    def test_known_dates(self):
        known = {
            2021: date(2021, 5, 2), 2022: date(2022, 4, 24),
            2023: date(2023, 4, 16), 2024: date(2024, 5, 5),
            2025: date(2025, 4, 20), 2026: date(2026, 4, 12),
            2027: date(2027, 5, 2), 2028: date(2028, 4, 16),
            2100: date(2100, 5, 2),  # Julian-Gregorian gap grows to 14 days
        }
        for year, expected in known.items():
            with self.subTest(year=year):
                self.assertEqual(orthodox_easter(year), expected)


class TestBulgarianHolidays(unittest.TestCase):
    def test_fixed_holidays_present(self):
        hol = bulgarian_holidays(2027)
        for m, d in [(1, 1), (3, 3), (5, 1), (5, 6), (5, 24),
                     (9, 6), (9, 22), (12, 24), (12, 25), (12, 26)]:
            self.assertIn(date(2027, m, d), hol)

    def test_easter_days(self):
        hol = bulgarian_holidays(2027)
        for d in (date(2027, 4, 30), date(2027, 5, 1), date(2027, 5, 2), date(2027, 5, 3)):
            self.assertIn(d, hol)
        self.assertIn("Holy Saturday", hol[date(2027, 5, 1)])

    def test_moved_days_off(self):
        cases = [
            date(2021, 5, 4),  # May 1 on Holy Saturday
            date(2022, 1, 3),  # Jan 1 on Saturday
            date(2022, 12, 27),  # Dec 24 (Sat) / Dec 25 (Sun)
            date(2022, 12, 28),
            date(2024, 9, 23),  # Sep 22 on Sunday
            date(2026, 12, 28),  # Dec 26 on Saturday
            date(2027, 5, 4),  # May 1 on Saturday
        ]
        for d in cases:
            with self.subTest(day=d):
                hol = bulgarian_holidays(d.year)
                self.assertIn(d, hol)
                self.assertTrue(hol[d].startswith("Day off"))

    def test_easter_sunday_not_moved(self):
        self.assertNotIn(date(2026, 4, 14), bulgarian_holidays(2026))

    def test_no_moved_day_when_holiday_on_weekday(self):
        self.assertNotIn(date(2027, 3, 4), bulgarian_holidays(2027))


if __name__ == "__main__":
    unittest.main()
