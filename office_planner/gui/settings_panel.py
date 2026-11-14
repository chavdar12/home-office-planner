"""Left-hand settings panel (tabs). Every change is applied immediately."""

from __future__ import annotations

import tkinter as tk
from datetime import date, datetime
from tkinter import ttk
from typing import Iterable, Optional, Protocol

from ..config import (ALARM_EVENING_BEFORE, ALARM_MORNING_OF, MAX_PERIOD_MONTHS, TIME_RE,
                      PlannerConfig, WEEKDAY_NAMES)
from ..dates import add_months, range_for_months
from ..planner import HOME, OFFICE, day_off_periods, plan_range


CUSTOM = "Custom dates"
PRESETS = {"Next month": 1, "Next 2 months": 2, "Next 3 months": 3,
           "Next 6 months": 6, "Next 12 months": 12, CUSTOM: 0}
MAX_MONTHS = MAX_PERIOD_MONTHS
ALARM_CHOICES = {"Evening before": ALARM_EVENING_BEFORE, "Morning of": ALARM_MORNING_OF}
DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y", "%d.%m.%y", "%d/%m/%Y")

CLICK_SWITCH = "switch"
CLICK_DAY_OFF = "day_off"


def parse_date(text: str) -> Optional[date]:
    text = text.strip()
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def fmt_period(start: date, end: date, count: int) -> str:
    days = f"{count} day{'s' if count != 1 else ''}"
    if start == end:
        return f"{start:%a %d %b %Y}  ({days})"
    return f"{start:%d %b} - {end:%d %b %Y}  ({days})"


class PlannerApp(Protocol):
    """What the panel needs from OfficePlannerApp; typed here so the panel doesn't import app.py back."""

    config: PlannerConfig
    today: date
    start: date
    end: date

    def show_month(self, year: int, month: int) -> None: ...
    def set_range(self, start: date, end: date) -> None: ...
    def settings_changed(self) -> None: ...
    def add_days_off(self, start: date, end: date) -> int: ...
    def remove_days_off(self, days: Iterable[date]) -> None: ...
    def clear_month_overrides(self) -> None: ...
    def clear_all_overrides(self) -> None: ...
    def reset_settings(self) -> None: ...
    def export(self) -> None: ...


class SettingsPanel(ttk.Frame):
    def __init__(self, master, app: PlannerApp):
        super().__init__(master, padding=10)
        self.app = app
        self._loading = False
        self._periods = []
        self.click_mode = tk.StringVar(value=CLICK_SWITCH)
        self._build()
        self.load_from_app()

    # ---------- layout ----------
    @staticmethod
    def _section(parent, title: str) -> ttk.LabelFrame:
        frame = ttk.LabelFrame(parent, text=title, padding=8)
        frame.pack(fill="x", pady=(0, 8))
        return frame

    def _build(self) -> None:
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True)
        for title, builder in [("Schedule", self._build_schedule),
                               ("Days off", self._build_days_off),
                               ("Reminder & export", self._build_export)]:
            tab = ttk.Frame(self.tabs, padding=8)
            self.tabs.add(tab, text=title)
            builder(tab)

        for var in [self.share_var, self.alarm_on_var, self.alarm_day_var,
                    self.alarm_time_var, *self.weekday_vars]:
            var.trace_add("write", lambda *_: self._changed())

    def _build_schedule(self, tab) -> None:
        f = self._section(tab, "Period")
        self.preset_var = tk.StringVar()
        self.from_var = tk.StringVar()
        self.to_var = tk.StringVar()
        ttk.Combobox(f, textvariable=self.preset_var, values=list(PRESETS),
                     state="readonly", width=16).grid(row=0, column=0, columnspan=2,
                                                      sticky="w")
        ttk.Label(f, text="From").grid(row=1, column=0, sticky="w", pady=(6, 0))
        ttk.Entry(f, textvariable=self.from_var, width=12
                  ).grid(row=1, column=1, sticky="w", padx=4, pady=(6, 0))
        ttk.Label(f, text="To").grid(row=2, column=0, sticky="w", pady=(4, 0))
        ttk.Entry(f, textvariable=self.to_var, width=12
                  ).grid(row=2, column=1, sticky="w", padx=4, pady=(4, 0))
        self.period_info = ttk.Label(f, text="", justify="left")
        self.period_info.grid(row=3, column=0, columnspan=2, sticky="w", pady=(6, 0))
        self.preset_var.trace_add("write", lambda *_: self._preset_changed())
        self.from_var.trace_add("write", lambda *_: self._dates_changed())
        self.to_var.trace_add("write", lambda *_: self._dates_changed())

        f = self._section(tab, "Always in the office")
        self.weekday_vars = []
        for i, name in enumerate(WEEKDAY_NAMES):
            var = tk.BooleanVar()
            ttk.Checkbutton(f, text=name, variable=var).grid(row=i, column=0, sticky="w")
            self.weekday_vars.append(var)

        f = self._section(tab, "Monthly office target")
        self.share_var = tk.StringVar()
        ttk.Spinbox(f, from_=0, to=100, increment=5, textvariable=self.share_var, width=5
                    ).pack(side="left")
        ttk.Label(f, text="% of working days").pack(side="left", padx=4)

        f = self._section(tab, "Extra office days - preference")
        self.pref_list = tk.Listbox(f, height=5, width=14, exportselection=False,
                                    activestyle="none")
        self.pref_list.grid(row=0, column=0, rowspan=2)
        ttk.Button(f, text="Up", width=6, command=lambda: self._move_pref(-1)
                   ).grid(row=0, column=1, padx=6, sticky="s")
        ttk.Button(f, text="Down", width=6, command=lambda: self._move_pref(1)
                   ).grid(row=1, column=1, padx=6, sticky="n")

    def _build_days_off(self, tab) -> None:
        f = self._section(tab, "Add days off")
        self.off_from_var = tk.StringVar()
        self.off_to_var = tk.StringVar()
        ttk.Label(f, text="From").grid(row=0, column=0, sticky="w")
        from_entry = ttk.Entry(f, textvariable=self.off_from_var, width=12)
        from_entry.grid(row=0, column=1, padx=4, sticky="w")
        ttk.Label(f, text="To").grid(row=1, column=0, sticky="w", pady=(4, 0))
        to_entry = ttk.Entry(f, textvariable=self.off_to_var, width=12)
        to_entry.grid(row=1, column=1, padx=4, pady=(4, 0), sticky="w")
        ttk.Button(f, text="Add", command=self.add_days_off
                   ).grid(row=0, column=2, rowspan=2, padx=(4, 0), sticky="ns")
        for entry in (from_entry, to_entry):
            entry.bind("<Return>", lambda e: self.add_days_off())
        ttk.Label(f, text="e.g. 2026-12-21 or 21.12.2026. Leave \"To\" empty\n"
                          "for one day. Weekends and holidays are skipped.",
                  foreground="#666").grid(row=2, column=0, columnspan=3, sticky="w",
                                          pady=(6, 0))
        self.off_message = ttk.Label(f, text="", foreground="#b3261e")
        self.off_message.grid(row=3, column=0, columnspan=3, sticky="w")

        f = self._section(tab, "Your days off")
        self.periods_list = tk.Listbox(f, height=9, width=34, exportselection=False,
                                       activestyle="none")
        self.periods_list.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.periods_list.bind("<Double-Button-1>", lambda e: self._show_selected_period())
        ttk.Button(f, text="Show", command=self._show_selected_period
                   ).grid(row=1, column=0, sticky="ew", pady=(6, 0), padx=(0, 3))
        ttk.Button(f, text="Remove", command=self.remove_selected_period
                   ).grid(row=1, column=1, sticky="ew", pady=(6, 0), padx=(3, 0))
        self.off_total = ttk.Label(f, text="", foreground="#666")
        self.off_total.grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))

        f = self._section(tab, "Clicking a day in the calendar")
        ttk.Radiobutton(f, text="Switches Office / Home", value=CLICK_SWITCH,
                        variable=self.click_mode).pack(anchor="w")
        ttk.Radiobutton(f, text="Marks / unmarks a day off", value=CLICK_DAY_OFF,
                        variable=self.click_mode).pack(anchor="w")
        ttk.Label(f, text="Right-click (or Ctrl+click) a day for all options.",
                  foreground="#666").pack(anchor="w", pady=(4, 0))

    def _build_export(self, tab) -> None:
        f = self._section(tab, "Reminder")
        self.alarm_on_var = tk.BooleanVar()
        self.alarm_day_var = tk.StringVar()
        self.alarm_time_var = tk.StringVar()
        ttk.Checkbutton(f, text="Add reminder", variable=self.alarm_on_var
                        ).grid(row=0, column=0, columnspan=3, sticky="w")
        ttk.Combobox(f, textvariable=self.alarm_day_var, values=list(ALARM_CHOICES),
                     state="readonly", width=13).grid(row=1, column=0, pady=(4, 0))
        ttk.Label(f, text="at").grid(row=1, column=1, padx=4, pady=(4, 0))
        ttk.Entry(f, textvariable=self.alarm_time_var, width=6
                  ).grid(row=1, column=2, pady=(4, 0))

        f = self._section(tab, "Manual changes")
        ttk.Button(f, text="Clear this month", command=self.app.clear_month_overrides
                   ).pack(fill="x")
        ttk.Button(f, text="Clear all", command=self.app.clear_all_overrides
                   ).pack(fill="x", pady=(4, 0))

        f = self._section(tab, "Export")
        ttk.Label(f, text="Exports the period set on the Schedule tab.",
                  foreground="#666").pack(anchor="w")
        ttk.Button(f, text="Export to Calendar (.ics)...", command=self.app.export
                   ).pack(fill="x", pady=(6, 0))
        ttk.Button(f, text="Reset settings to defaults", command=self.app.reset_settings
                   ).pack(fill="x", pady=(4, 0))

    # ---------- sync with app ----------
    def load_from_app(self) -> None:
        app, cfg = self.app, self.app.config
        self._loading = True
        try:
            self.preset_var.set(next((k for k, v in PRESETS.items()
                                      if v == cfg.period_months), CUSTOM))
            self._set_dates(app.start, app.end)
            for i, var in enumerate(self.weekday_vars):
                var.set(i in cfg.office_weekdays)
            self.share_var.set(str(round(cfg.office_share * 100)))
            self._fill_pref(cfg.extra_preference)
            self.alarm_on_var.set(cfg.alarm_enabled)
            self.alarm_day_var.set(next(k for k, v in ALARM_CHOICES.items()
                                        if v == cfg.alarm_day))
            self.alarm_time_var.set(cfg.alarm_time)
        finally:
            self._loading = False
        self.refresh_days_off()

    def refresh_days_off(self) -> None:
        """Re-list day-off periods (called by the app after every change)."""
        self._periods = day_off_periods(self.app.config)
        self.periods_list.delete(0, "end")
        for start, end, days in self._periods:
            self.periods_list.insert("end", fmt_period(start, end, len(days)))
        total = sum(len(days) for _, _, days in self._periods)
        self.off_total.configure(text=f"Total: {total} working day{'s' if total != 1 else ''}"
        if total else "No days off yet.")

    # ---------- period ----------
    def _set_dates(self, start: date, end: date) -> None:
        was_loading, self._loading = self._loading, True
        try:
            self.from_var.set(start.isoformat())
            self.to_var.set(end.isoformat())
        finally:
            self._loading = was_loading

    def _preset_changed(self) -> None:
        if self._loading:
            return
        cfg = self.app.config
        months = PRESETS[self.preset_var.get()]
        cfg.period_months = months
        if months:
            start, end = range_for_months(self.app.today, months)
            self._set_dates(start, end)
            self.app.set_range(start, end)
        else:  # switching to custom keeps the current dates
            cfg.custom_start, cfg.custom_end = self.app.start, self.app.end
            self.app.settings_changed()

    def _dates_changed(self) -> None:
        if self._loading:
            return
        start, end = parse_date(self.from_var.get()), parse_date(self.to_var.get())
        error = None
        if start is None or end is None:
            error = "Enter dates like 2026-12-01 or 01.12.2026."
        elif end < start:
            error = "\"To\" must not be before \"From\"."
        elif end >= add_months(start, MAX_MONTHS):
            error = f"The period can be at most {MAX_MONTHS} months."
        if error:
            self.period_info.configure(text=error, foreground="#b3261e")
            return
        if self.preset_var.get() != CUSTOM:
            self._loading = True
            self.preset_var.set(CUSTOM)
            self._loading = False
        cfg = self.app.config
        cfg.period_months, cfg.custom_start, cfg.custom_end = 0, start, end
        self.app.set_range(start, end)

    def refresh_period_info(self) -> None:
        start, end = self.app.start, self.app.end
        kinds = list(plan_range(start, end, self.app.config).values())
        work = kinds.count(OFFICE) + kinds.count(HOME)
        self.period_info.configure(
            foreground="", text=f"{start:%a %d %b %Y} - {end:%a %d %b %Y}\n"
                                f"{work} working days: {kinds.count(OFFICE)} office, "
                                f"{kinds.count(HOME)} home")

    # ---------- days off ----------
    def add_days_off(self) -> None:
        start = parse_date(self.off_from_var.get())
        end_text = self.off_to_var.get().strip()
        end = parse_date(end_text) if end_text else start
        if start is None or end is None:
            self.off_message.configure(text="Please enter a valid date.")
            return
        added = self.app.add_days_off(start, end)
        self.off_message.configure(text="" if added else "No new working days in that range.")
        if added:
            self.off_from_var.set("")
            self.off_to_var.set("")

    def _selected_period(self):
        sel = self.periods_list.curselection()
        return self._periods[sel[0]] if sel else None

    def _show_selected_period(self) -> None:
        period = self._selected_period()
        if period:
            self.app.show_month(period[0].year, period[0].month)

    def remove_selected_period(self) -> None:
        period = self._selected_period()
        if period:
            self.app.remove_days_off(period[2])

    # ---------- schedule settings ----------
    def _fill_pref(self, order) -> None:
        full = list(order) + [d for d in range(5) if d not in order]
        self.pref_list.delete(0, "end")
        for d in full:
            self.pref_list.insert("end", WEEKDAY_NAMES[d])

    def _move_pref(self, delta: int) -> None:
        sel = self.pref_list.curselection()
        if not sel:
            return
        i, j = sel[0], sel[0] + delta
        if not 0 <= j < self.pref_list.size():
            return
        item = self.pref_list.get(i)
        self.pref_list.delete(i)
        self.pref_list.insert(j, item)
        self.pref_list.selection_set(j)
        self._changed()

    def _changed(self) -> None:
        """Read all fields; ignore the change while a field is half-typed."""
        if self._loading:
            return
        try:
            share = float(self.share_var.get())
        except ValueError:
            return
        time = self.alarm_time_var.get().strip()
        if not (0 <= share <= 100 and TIME_RE.fullmatch(time)):
            return

        cfg = self.app.config
        cfg.office_weekdays = [i for i, v in enumerate(self.weekday_vars) if v.get()]
        cfg.office_share = share / 100
        cfg.extra_preference = [WEEKDAY_NAMES.index(n) for n in self.pref_list.get(0, "end")]
        cfg.alarm_enabled = self.alarm_on_var.get()
        cfg.alarm_day = ALARM_CHOICES[self.alarm_day_var.get()]
        h, m = time.split(":")
        cfg.alarm_time = f"{int(h):02d}:{m}"
        self.app.settings_changed()
