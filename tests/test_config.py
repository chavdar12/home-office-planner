import tempfile
import unittest
from datetime import date
from pathlib import Path

from office_planner.config import PlannerConfig


class TestConfig(unittest.TestCase):
    def test_round_trip(self):
        cfg = PlannerConfig(office_weekdays=[1], office_share=0.6, alarm_day="same",
                            alarm_time="08:00", overrides={date(2026, 11, 9): "home"})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cfg.json"
            cfg.save(path)
            self.assertEqual(PlannerConfig.load(path), cfg)

    def test_period_round_trip_and_resolution(self):
        today = date(2026, 11, 6)
        cfg = PlannerConfig(period_months=0, custom_start=date(2027, 1, 1),
                            custom_end=date(2027, 3, 31))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cfg.json"
            cfg.save(path)
            loaded = PlannerConfig.load(path)
        self.assertEqual(loaded, cfg)
        self.assertEqual(loaded.period(today), (date(2027, 1, 1), date(2027, 3, 31)))
        self.assertEqual(PlannerConfig(period_months=3).period(today),
                         (today, date(2027, 2, 5)))
        # Custom without dates falls back to 12 months.
        self.assertEqual(PlannerConfig(period_months=0).period(today),
                         (today, date(2027, 11, 5)))

    def test_missing_or_broken_file_gives_defaults(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cfg.json"
            self.assertEqual(PlannerConfig.load(path), PlannerConfig())
            path.write_text("{not json")
            self.assertEqual(PlannerConfig.load(path), PlannerConfig())

    def test_unknown_keys_ignored(self):
        cfg = PlannerConfig.from_dict({"office_share": 0.4, "something_old": 1})
        self.assertEqual(cfg.office_share, 0.4)


if __name__ == "__main__":
    unittest.main()
