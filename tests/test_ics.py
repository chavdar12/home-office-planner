import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, timezone
from pathlib import Path

from office_planner.config import PlannerConfig
from office_planner.dates import iter_months
from office_planner.ics import alarm_trigger, build_ics
from office_planner.planner import DAY_OFF, plan_month

ROOT = Path(__file__).resolve().parent.parent
STAMP = datetime(2026, 11, 6, tzinfo=timezone.utc)
NOV_1, NOV_30 = date(2026, 11, 1), date(2026, 11, 30)


class TestAlarmTrigger(unittest.TestCase):
    def test_triggers(self) -> None:
        self.assertEqual(alarm_trigger("before", "18:00"), "-PT6H0M")
        self.assertEqual(alarm_trigger("before", "20:30"), "-PT3H30M")
        self.assertEqual(alarm_trigger("same", "08:15"), "PT8H15M")


class TestBuildIcs(unittest.TestCase):
    text: str

    @classmethod
    def setUpClass(cls) -> None:
        cls.text = build_ics(date(2026, 11, 1), date(2027, 10, 31), stamp=STAMP)

    def test_calendar_wrapper_and_crlf(self) -> None:
        self.assertTrue(self.text.startswith("BEGIN:VCALENDAR\r\n"))
        self.assertTrue(self.text.endswith("END:VCALENDAR\r\n"))
        self.assertNotIn("\n", self.text.replace("\r\n", ""))

    def test_one_event_per_weekday(self) -> None:
        weekdays = sum(len(plan_month(y, m)) for y, m in iter_months(2026, 11, 12))
        self.assertEqual(self.text.count("BEGIN:VEVENT"), weekdays)
        self.assertEqual(self.text.count("END:VEVENT"), weekdays)

    def test_alarms_only_on_work_days(self) -> None:
        work = self.text.count("SUMMARY:🏢 Office") + self.text.count("SUMMARY:🏠 Home office")
        self.assertEqual(self.text.count("BEGIN:VALARM"), work)

    def test_unique_uids(self) -> None:
        uids = [line for line in self.text.split("\r\n") if line.startswith("UID:")]
        self.assertEqual(len(uids), len(set(uids)))

    def test_specific_days(self) -> None:
        self.assertIn("DTSTART;VALUE=DATE:20261228\r\nDTEND;VALUE=DATE:20261229\r\n"
                      "SUMMARY:🇧🇬 Day off", self.text)
        self.assertIn("DTSTART;VALUE=DATE:20261102\r\nDTEND;VALUE=DATE:20261103\r\n"
                      "SUMMARY:🏢 Office", self.text)


class TestIcsOptions(unittest.TestCase):
    def test_no_alarms_when_disabled(self) -> None:
        text = build_ics(NOV_1, NOV_30, PlannerConfig(alarm_enabled=False), stamp=STAMP)
        self.assertNotIn("VALARM", text)

    def test_exact_date_range(self) -> None:
        text = build_ics(date(2026, 11, 6), date(2026, 12, 2), stamp=STAMP)
        self.assertNotIn("DTSTART;VALUE=DATE:20261105", text)
        self.assertIn("DTSTART;VALUE=DATE:20261106", text)
        self.assertIn("DTSTART;VALUE=DATE:20261202", text)
        self.assertNotIn("DTSTART;VALUE=DATE:20261203", text)
        self.assertEqual(text.count("BEGIN:VEVENT"), 19)  # weekdays 6 Nov - 2 Dec

    def test_partial_month_keeps_monthly_plan(self) -> None:
        # Trimming the range must not change how the month itself is planned.
        full = build_ics(NOV_1, NOV_30, stamp=STAMP)
        part = build_ics(date(2026, 11, 16), NOV_30, stamp=STAMP)
        self.assertIn(part.split("BEGIN:VEVENT", 1)[1].rsplit("END:VCALENDAR")[0], full)

    def test_day_off_event_has_no_alarm(self) -> None:
        cfg = PlannerConfig(overrides={date(2026, 11, 10): DAY_OFF})
        text = build_ics(NOV_1, NOV_30, cfg, stamp=STAMP)
        event = text.split("DTSTART;VALUE=DATE:20261110")[1].split("END:VEVENT")[0]
        self.assertIn("SUMMARY:🌴 Day off", event)
        self.assertNotIn("VALARM", event)


class TestCli(unittest.TestCase):
    def test_cli_writes_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.ics"
            result = subprocess.run(
                [sys.executable, "-m", "office_planner", "--start-month", "2026-11",
                 "--months", "12", "-o", str(out)],
                cwd=ROOT, capture_output=True, text=True, check=True)
            self.assertIn("2026-11", result.stdout)
            self.assertIn("2027-10", result.stdout)
            self.assertTrue(out.read_text(encoding="utf-8").startswith("BEGIN:VCALENDAR"))

    def test_cli_from_to(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "out.ics"
            result = subprocess.run(
                [sys.executable, "-m", "office_planner", "--from", "2026-11-06",
                 "--to", "2026-12-02", "-o", str(out)],
                cwd=ROOT, capture_output=True, text=True, check=True)
            self.assertIn("06 Nov 2026 - 02 Dec 2026", result.stdout)
            self.assertEqual(out.read_text(encoding="utf-8").count("BEGIN:VEVENT"), 19)

    def test_cli_uses_config_period(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path, out = Path(tmp) / "cfg.json", Path(tmp) / "out.ics"
            PlannerConfig(period_months=0, custom_start=date(2027, 1, 4),
                          custom_end=date(2027, 1, 8)).save(cfg_path)
            subprocess.run(
                [sys.executable, "-m", "office_planner", "-o", str(out),
                 "--config", str(cfg_path)], cwd=ROOT, capture_output=True, check=True)
            self.assertEqual(out.read_text(encoding="utf-8").count("BEGIN:VEVENT"), 5)

    def test_cli_rejects_reversed_range(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "office_planner", "--from", "2026-12-01",
             "--to", "2026-11-01", "-o", "/dev/null"], cwd=ROOT, capture_output=True, check=False)
        self.assertNotEqual(result.returncode, 0)

    def test_cli_rejects_bad_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = str(Path(tmp) / "out.ics")
            for args in (["--months", "0"], ["--start-month", "2026-13"],
                         ["--from", "2026-01-01", "--start-month", "2026-02"],
                         ["--config", str(Path(tmp) / "missing.json")],
                         ["-o", str(Path(tmp) / "no" / "dir.ics"), "--months", "1"]):
                with self.subTest(args=args):
                    result = subprocess.run([sys.executable, "-m", "office_planner", "-o", out,
                                             *args], cwd=ROOT, capture_output=True, text=True,
                                            check=False)
                    self.assertNotEqual(result.returncode, 0)
                    self.assertNotIn("Traceback", result.stderr)

    def test_cli_uses_config_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cfg_path, out = Path(tmp) / "cfg.json", Path(tmp) / "out.ics"
            PlannerConfig(alarm_enabled=False).save(cfg_path)
            subprocess.run(
                [sys.executable, "-m", "office_planner", "--start-month", "2026-11",
                 "--months", "1", "-o", str(out), "--config", str(cfg_path)],
                cwd=ROOT, capture_output=True, check=True)
            self.assertNotIn("VALARM", out.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
