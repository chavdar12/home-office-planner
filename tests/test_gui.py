import tempfile
import unittest
from datetime import date
from pathlib import Path

from office_planner.config import PlannerConfig
from office_planner.planner import DAY_OFF, HOME, OFFICE

# One Tk root for the whole module: Tk 9 on macOS crashes if a second Tk()
# is created after the first one was destroyed. Each test uses a Toplevel.
try:
    import tkinter as tk

    ROOT = tk.Tk()
    ROOT.withdraw()
except Exception:  # no tkinter or no display
    ROOT = None


@unittest.skipIf(ROOT is None, "Tk display not available")
class TestGui(unittest.TestCase):
    def setUp(self):
        from office_planner.gui.app import OfficePlannerApp
        self.tmp = tempfile.TemporaryDirectory()
        self.cfg_path = Path(self.tmp.name) / "cfg.json"
        self.root = tk.Toplevel(ROOT)
        self.root.withdraw()
        self.app = OfficePlannerApp(self.root, self.cfg_path, today=date(2026, 11, 6))
        self.root.update()

    def tearDown(self):
        self.root.destroy()
        self.tmp.cleanup()

    def test_initial_view(self):
        self.assertEqual(self.app.title_label.cget("text"), "November 2026")
        # Default: 12 months from today -> 6 Nov 2026 .. 5 Nov 2027 (13 months touched).
        self.assertEqual((self.app.start, self.app.end), (date(2026, 11, 6), date(2027, 11, 5)))
        self.assertEqual(len(self.app.summary.get_children()), 13)
        self.assertIn("Office 11", self.app.stats_label.cget("text"))
        self.assertIn("only part of this month", self.app.summary_note.cget("text"))

    def test_navigation(self):
        self.app.shift_month(2)
        self.assertEqual(self.app.title_label.cget("text"), "January 2027")
        self.app.shift_month(-3)
        self.assertEqual(self.app.title_label.cget("text"), "October 2026")
        self.app.go_today()
        self.assertEqual((self.app.view_year, self.app.view_month), (2026, 11))

    def test_click_toggles_and_saves(self):
        monday = date(2026, 11, 9)
        self.app.on_day_click(monday)
        self.assertEqual(self.app.config.overrides[monday], HOME)
        self.assertEqual(PlannerConfig.load(self.cfg_path).overrides[monday], HOME)
        self.app.on_day_click(monday)  # back to automatic -> override removed
        self.assertNotIn(monday, self.app.config.overrides)

    def test_click_on_holiday_does_nothing(self):
        self.app.on_day_click(date(2026, 12, 24))
        self.assertEqual(self.app.config.overrides, {})

    def test_clear_month(self):
        self.app.set_override(date(2026, 11, 10), DAY_OFF)
        self.app.set_override(date(2026, 12, 1), OFFICE)
        self.app.clear_month_overrides()
        self.assertEqual(list(self.app.config.overrides), [date(2026, 12, 1)])

    def test_settings_panel_updates_config(self):
        panel = self.app.settings
        panel.weekday_vars[4].set(True)  # Friday
        panel.share_var.set("60")
        self.assertEqual(self.app.config.office_weekdays, [0, 2, 4])
        self.assertAlmostEqual(self.app.config.office_share, 0.6)
        panel.share_var.set("")  # half-typed value is ignored
        self.assertAlmostEqual(self.app.config.office_share, 0.6)

    def test_presets(self):
        panel = self.app.settings
        for name, end, rows in [("Next month", date(2026, 12, 5), 2),
                                ("Next 2 months", date(2027, 1, 5), 3),
                                ("Next 6 months", date(2027, 5, 5), 7)]:
            with self.subTest(preset=name):
                panel.preset_var.set(name)
                self.assertEqual((self.app.start, self.app.end), (date(2026, 11, 6), end))
                self.assertEqual(panel.to_var.get(), end.isoformat())
                self.assertEqual(len(self.app.summary.get_children()), rows)
        self.assertEqual(PlannerConfig.load(self.cfg_path).period_months, 6)

    def test_custom_dates(self):
        panel = self.app.settings
        panel.from_var.set("01.01.2027")
        panel.to_var.set("2027-03-31")
        self.assertEqual(panel.preset_var.get(), "Custom dates")
        self.assertEqual((self.app.start, self.app.end), (date(2027, 1, 1), date(2027, 3, 31)))
        self.assertEqual(self.app.title_label.cget("text"), "January 2027")
        self.assertEqual(len(self.app.summary.get_children()), 3)
        self.assertEqual(self.app.summary_note.cget("text"), "")  # whole months
        self.assertIn("Fri 01 Jan 2027 - Wed 31 Mar 2027", panel.period_info.cget("text"))
        saved = PlannerConfig.load(self.cfg_path)
        self.assertEqual((saved.period_months, saved.custom_start, saved.custom_end),
                         (0, date(2027, 1, 1), date(2027, 3, 31)))

    def test_invalid_custom_dates_are_ignored(self):
        panel = self.app.settings
        before = (self.app.start, self.app.end)
        panel.to_var.set("2026-10-01")  # before start
        self.assertEqual((self.app.start, self.app.end), before)
        self.assertIn("must not be before", panel.period_info.cget("text"))
        panel.to_var.set("2030-01-01")  # too long
        self.assertIn("at most 36 months", panel.period_info.cget("text"))
        panel.to_var.set("garbage")
        self.assertIn("Enter dates", panel.period_info.cget("text"))
        self.assertEqual((self.app.start, self.app.end), before)

    def test_period_restored_on_restart(self):
        self.app.settings.preset_var.set("Next 3 months")
        from office_planner.gui.app import OfficePlannerApp
        again = OfficePlannerApp(tk.Toplevel(ROOT), self.cfg_path, today=date(2026, 11, 6))
        self.assertEqual(again.end, date(2027, 2, 5))
        self.assertEqual(again.settings.preset_var.get(), "Next 3 months")
        again.root.destroy()

    def test_days_outside_period_are_dimmed(self):
        view = self.app.month_view
        self.assertFalse(view.in_period(date(2026, 11, 5)))
        self.assertTrue(view.in_period(date(2026, 11, 6)))
        texts = [view.itemcget(i, "text") for i in view.find_all()
                 if view.type(i) == "text"]
        self.assertEqual(sum("outside period" in t for t in texts), 4)  # 2-5 Nov

    def test_add_days_off_from_panel(self):
        panel = self.app.settings
        panel.off_from_var.set("21.12.2026")
        panel.off_to_var.set("2026-12-31")
        panel.add_days_off()
        self.assertEqual(sum(v == DAY_OFF for v in self.app.config.overrides.values()), 6)
        self.assertEqual(self.app.title_label.cget("text"), "December 2026")
        self.assertEqual(panel.periods_list.size(), 1)
        self.assertIn("6 days", panel.periods_list.get(0))
        self.assertEqual(panel.off_from_var.get(), "")
        self.assertEqual(len(PlannerConfig.load(self.cfg_path).overrides), 6)

    def test_add_single_day_and_invalid_input(self):
        panel = self.app.settings
        panel.off_from_var.set("2026-11-20")
        panel.add_days_off()
        self.assertEqual(self.app.config.overrides, {date(2026, 11, 20): DAY_OFF})
        panel.off_from_var.set("not a date")
        panel.add_days_off()
        self.assertIn("valid date", panel.off_message.cget("text"))
        panel.off_from_var.set("2026-11-21")  # a Saturday
        panel.add_days_off()
        self.assertIn("No new working days", panel.off_message.cget("text"))

    def test_remove_period(self):
        panel = self.app.settings
        self.app.set_override(date(2026, 11, 9), HOME)
        self.app.add_days_off(date(2026, 11, 16), date(2026, 11, 18))
        panel.periods_list.selection_set(0)
        panel.remove_selected_period()
        self.assertEqual(self.app.config.overrides, {date(2026, 11, 9): HOME})
        self.assertEqual(panel.periods_list.size(), 0)

    def test_click_mode_day_off(self):
        self.app.settings.click_mode.set("day_off")
        d = date(2026, 11, 10)
        self.app.on_day_click(d)
        self.assertEqual(self.app.config.overrides[d], DAY_OFF)
        # One working day fewer; the planner re-picks to keep 50% office.
        self.assertIn("20 working days", self.app.stats_label.cget("text"))
        self.assertIn("Office 10 (50%)", self.app.stats_label.cget("text"))
        self.app.on_day_click(d)
        self.assertNotIn(d, self.app.config.overrides)

    def test_month_view_hit_test(self):
        view = self.app.month_view
        view.configure(width=700, height=500)
        self.root.update()
        view.redraw()
        x0, y0, x1, y1, d = view._cells[0]
        self.assertEqual(view.date_at((x0 + x1) / 2, (y0 + y1) / 2), d)


if __name__ == "__main__":
    unittest.main()
