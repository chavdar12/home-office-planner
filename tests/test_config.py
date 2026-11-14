import json
import sys
import tempfile
import unittest.mock
from datetime import date
from pathlib import Path

from office_planner.config import PlannerConfig, default_path


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
            with self.assertWarns(UserWarning):
                self.assertEqual(PlannerConfig.load(path), PlannerConfig())

    def test_save_keeps_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            real, link = Path(tmp) / "real.json", Path(tmp) / "link.json"
            real.write_text("{}")
            link.symlink_to(real)
            PlannerConfig(office_share=0.6).save(link)
            self.assertTrue(link.is_symlink())
            self.assertEqual(PlannerConfig.load(real).office_share, 0.6)

    def test_invalid_values_rejected_and_file_kept(self):
        bad = [[], {"overrides": {"2026-11-09": "holiday"}}, {"alarm_day": "x"},
               {"alarm_time": "25:00"}, {"office_share": "half"}, {"office_share": 2},
               {"extra_preference": [7]}, {"extra_preference": [1.0]},
               {"period_months": 1000}, {"period_months": 1.5},
               {"custom_start": "2027-02-01", "custom_end": "2027-01-01"}]
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "cfg.json"
            for data in bad:
                with self.subTest(data=data):
                    path.write_text(json.dumps(data))
                    with self.assertWarns(UserWarning):
                        self.assertEqual(PlannerConfig.load(path), PlannerConfig())
                    self.assertEqual((Path(tmp) / "cfg.json.broken").read_text(), json.dumps(data))

    def test_portable_windows_build_keeps_settings_next_to_exe(self):
        with tempfile.TemporaryDirectory() as tmp:
            exe = Path(tmp) / "OfficePlanner.exe"
            with unittest.mock.patch.object(sys, "frozen", True, create=True), \
                    unittest.mock.patch.object(sys, "platform", "win32"), \
                    unittest.mock.patch.object(sys, "executable", str(exe)):
                self.assertEqual(default_path(), Path(tmp) / "office_planner.json")
                with unittest.mock.patch("tempfile.TemporaryFile", side_effect=PermissionError):
                    self.assertEqual(default_path(), Path.home() / ".office_planner.json")
        self.assertEqual(default_path(), Path.home() / ".office_planner.json")

    def test_unknown_keys_ignored(self):
        cfg = PlannerConfig.from_dict({"office_share": 0.4, "something_old": 1})
        self.assertEqual(cfg.office_share, 0.4)


if __name__ == "__main__":
    unittest.main()
