"""Main window: settings on the left, month view and yearly summary on the right."""

from __future__ import annotations

import calendar
import subprocess
import sys
import tkinter as tk
from dataclasses import replace
from datetime import date
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Optional

from ..config import DEFAULT_PATH, PlannerConfig
from ..holidays import bulgarian_holidays
from ..ics import write_ics
from ..dates import months_in_range
from ..planner import (DAY_OFF, HOLIDAY, HOME, OFFICE, add_days_off, month_stats,
                       plan_month)
from .month_view import COLORS, MonthView
from .settings_panel import CLICK_DAY_OFF, SettingsPanel


class OfficePlannerApp:
    def __init__(self, root: tk.Tk, config_path: Path = DEFAULT_PATH,
                 today: Optional[date] = None):
        self.root = root
        self.config_path = Path(config_path)
        self.config = PlannerConfig.load(self.config_path)
        self.today = today or date.today()
        self.start, self.end = self.config.period(self.today)
        self.view_year, self.view_month = self.start.year, self.start.month
        self._build()
        self.refresh()

    # ---------- layout ----------
    def _build(self) -> None:
        self.root.title("Office Planner")
        self.root.minsize(1050, 700)
        self.root.columnconfigure(1, weight=1)
        self.root.rowconfigure(0, weight=1)

        self.settings = SettingsPanel(self.root, self)
        self.settings.grid(row=0, column=0, sticky="ns")

        right = ttk.Frame(self.root, padding=(0, 10, 10, 10))
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(2, weight=1)

        nav = ttk.Frame(right)
        nav.grid(row=0, column=0, sticky="ew")
        ttk.Button(nav, text="<", width=3, command=lambda: self.shift_month(-1)).pack(side="left")
        ttk.Button(nav, text=">", width=3, command=lambda: self.shift_month(1)).pack(side="left")
        ttk.Button(nav, text="Today", command=self.go_today).pack(side="left", padx=6)
        self.title_label = ttk.Label(nav, font=("Helvetica", 20, "bold"))
        self.title_label.pack(side="left", padx=10)

        self.stats_label = ttk.Label(right, font=("Helvetica", 13))
        self.stats_label.grid(row=1, column=0, sticky="w", pady=(6, 6))

        self.month_view = MonthView(right, on_click=self.on_day_click, on_menu=self.on_day_menu)
        self.month_view.grid(row=2, column=0, sticky="nsew")

        legend = ttk.Frame(right)
        legend.grid(row=3, column=0, sticky="w", pady=6)
        for kind, text in [(OFFICE, "Office"), (HOME, "Home office"),
                           (HOLIDAY, "Official holiday"), (DAY_OFF, "Day off")]:
            bg, fg = COLORS[kind]
            tk.Label(legend, text=f"  {text}  ", bg=bg, fg=fg, relief="solid", bd=1
                     ).pack(side="left", padx=(0, 8))

        cols = ("month", "working", "office", "home", "off", "share", "status")
        heads = ("Month", "Working", "Office", "Home", "Holidays / off", "Office %", "Target")
        table = ttk.Frame(right)
        table.grid(row=4, column=0, sticky="ew")
        table.columnconfigure(0, weight=1)
        self.summary = ttk.Treeview(table, columns=cols, show="headings", height=7,
                                    selectmode="browse")
        for c, h in zip(cols, heads):
            self.summary.heading(c, text=h)
            self.summary.column(c, width=150 if c == "month" else 90,
                                anchor="w" if c == "month" else "center")
        self.summary.tag_configure("low", foreground="#b3261e")
        self.summary.tag_configure("current", background="#e8eefc")
        scroll = ttk.Scrollbar(table, orient="vertical", command=self.summary.yview)
        self.summary.configure(yscrollcommand=scroll.set)
        self.summary.grid(row=0, column=0, sticky="ew")
        scroll.grid(row=0, column=1, sticky="ns")
        self.summary.bind("<<TreeviewSelect>>", self._on_summary_select)
        self.summary_note = ttk.Label(table, foreground="#666")
        self.summary_note.grid(row=1, column=0, sticky="w", pady=(4, 0))

        self.root.bind("<Left>", lambda e: self.shift_month(-1))
        self.root.bind("<Right>", lambda e: self.shift_month(1))

    # ---------- state changes ----------
    def refresh(self) -> None:
        y, m = self.view_year, self.view_month
        holidays = bulgarian_holidays(y)
        plan = plan_month(y, m, self.config, holidays)
        s = month_stats(y, m, plan, self.config)

        self.title_label.configure(text=f"{calendar.month_name[m]} {y}")
        target = "target met" if s.meets_target else f"below target ({s.required} needed)"
        self.stats_label.configure(
            text=f"{s.working} working days   |   Office {s.office} ({s.share:.0%})"
                 f"   |   Home {s.home}   |   {target}")
        self.month_view.show(y, m, plan, holidays, self.config.overrides, self.today,
                             period=(self.start, self.end))
        self._fill_summary()
        self.settings.refresh_days_off()
        self.settings.refresh_period_info()

    def _fill_summary(self) -> None:
        self.summary.delete(*self.summary.get_children())
        partial = False
        for y, m in months_in_range(self.start, self.end):
            s = month_stats(y, m, plan_month(y, m, self.config), self.config)
            first, last = date(y, m, 1), date(y, m, calendar.monthrange(y, m)[1])
            is_partial = first < self.start or last > self.end
            partial = partial or is_partial
            tags = []
            if not s.meets_target:
                tags.append("low")
            if (y, m) == (self.view_year, self.view_month):
                tags.append("current")
            self.summary.insert("", "end", iid=f"{y}-{m}", tags=tags, values=(
                f"{calendar.month_name[m]} {y}{' *' if is_partial else ''}",
                s.working, s.office, s.home, s.holidays + s.days_off, f"{s.share:.0%}",
                "OK" if s.meets_target else f"need {s.required}"))
        self.summary_note.configure(
            text="* only part of this month is in the period; the 50% target is "
                 "still counted over the whole month." if partial else "")

    def _on_summary_select(self, _event=None) -> None:
        sel = self.summary.selection()
        if not sel:
            return
        y, m = map(int, sel[0].split("-"))
        if (y, m) != (self.view_year, self.view_month):
            self.view_year, self.view_month = y, m
            self.refresh()

    def shift_month(self, delta: int) -> None:
        total = self.view_year * 12 + self.view_month - 1 + delta
        self.view_year, self.view_month = divmod(total, 12)
        self.view_month += 1
        self.refresh()

    def go_today(self) -> None:
        self.show_month(self.today.year, self.today.month)

    def show_month(self, year: int, month: int) -> None:
        self.view_year, self.view_month = year, month
        self.refresh()

    def set_range(self, start: date, end: date) -> None:
        """New export period; jump to its first month if the start moved."""
        moved = start != self.start
        self.start, self.end = start, end
        if moved:
            self.view_year, self.view_month = start.year, start.month
        self.settings_changed()

    def settings_changed(self) -> None:
        self.save()
        self.refresh()

    def save(self) -> None:
        try:
            self.config.save(self.config_path)
        except OSError:
            pass

    # ---------- day editing ----------
    def set_override(self, d: date, kind: Optional[str]) -> None:
        if kind is None:
            self.config.overrides.pop(d, None)
        else:
            self.config.overrides[d] = kind
        self.settings_changed()

    def auto_kind(self, d: date) -> str:
        """What the planner would choose for this day without a manual override."""
        others = {k: v for k, v in self.config.overrides.items() if k != d}
        return plan_month(d.year, d.month, replace(self.config, overrides=others))[d]

    def add_days_off(self, start: date, end: date) -> int:
        added = add_days_off(self.config, start, end)
        if added:
            self.show_month(min(start, end).year, min(start, end).month)
            self.save()
        return added

    def remove_days_off(self, days) -> None:
        for d in days:
            if self.config.overrides.get(d) == DAY_OFF:
                del self.config.overrides[d]
        self.settings_changed()

    def on_day_click(self, d: date) -> None:
        current = plan_month(d.year, d.month, self.config)[d]
        if current == HOLIDAY:
            return
        if self.settings.click_mode.get() == CLICK_DAY_OFF:
            self.set_override(d, None if current == DAY_OFF else DAY_OFF)
            return
        new = HOME if current == OFFICE else OFFICE
        self.set_override(d, None if new == self.auto_kind(d) else new)

    def on_day_menu(self, d: date, x: int, y: int) -> None:
        if d in bulgarian_holidays(d.year):
            return
        menu = tk.Menu(self.root, tearoff=0)
        menu.add_command(label="Office", command=lambda: self.set_override(d, OFFICE))
        menu.add_command(label="Home office", command=lambda: self.set_override(d, HOME))
        menu.add_command(label="Day off / vacation",
                         command=lambda: self.set_override(d, DAY_OFF))
        menu.add_separator()
        menu.add_command(label="Automatic", command=lambda: self.set_override(d, None))
        menu.tk_popup(x, y)

    def clear_month_overrides(self) -> None:
        for d in [d for d in self.config.overrides
                  if (d.year, d.month) == (self.view_year, self.view_month)]:
            del self.config.overrides[d]
        self.settings_changed()

    def clear_all_overrides(self) -> None:
        if self.config.overrides and messagebox.askyesno(
                "Clear all", "Remove all manual changes?", parent=self.root):
            self.config.overrides.clear()
            self.settings_changed()

    def reset_settings(self) -> None:
        if messagebox.askyesno("Reset", "Reset settings to defaults? "
                               "Manual day changes are kept.", parent=self.root):
            self.config = PlannerConfig(overrides=self.config.overrides)
            self.start, self.end = self.config.period(self.today)
            self.settings.load_from_app()
            self.settings_changed()

    # ---------- export ----------
    def export(self) -> None:
        path = filedialog.asksaveasfilename(
            parent=self.root, title="Export calendar", defaultextension=".ics",
            initialfile="office_schedule.ics", filetypes=[("iCalendar", "*.ics")])
        if not path:
            return
        write_ics(path, self.start, self.end, self.config)
        if sys.platform == "darwin":
            if messagebox.askyesno("Exported", f"Saved to {path}.\n\n"
                                   "Open it in Calendar now?", parent=self.root):
                subprocess.run(["open", "-a", "Calendar", path], check=False)
        else:
            messagebox.showinfo("Exported", f"Saved to {path}.", parent=self.root)


def main() -> None:
    root = tk.Tk()
    if root.tk.call("info", "patchlevel").startswith("8.5"):
        root.destroy()
        sys.exit("This Python uses Tk 8.5 (Apple's deprecated system Tk), which shows "
                 "blank windows on current macOS.\nRun the GUI with Homebrew's Python "
                 "instead:  python3.13 -m office_planner.gui\n"
                 "(install it with:  brew install python-tk@3.13)")
    OfficePlannerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
