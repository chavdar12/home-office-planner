"""Canvas widget that draws one month as a Mon-Sun grid."""

from __future__ import annotations

import calendar
import tkinter as tk
from datetime import date
from typing import Callable, Dict, Optional, Tuple

from ..planner import DAY_OFF, HOLIDAY, HOME, OFFICE

# kind -> (background, text colour)
COLORS = {
    OFFICE: ("#d4e3ff", "#1d4c9c"),
    HOME: ("#d9f2d9", "#1f6b29"),
    HOLIDAY: ("#fbdcd7", "#a3281a"),
    DAY_OFF: ("#fff0c0", "#8a6100"),
}
LABELS = {OFFICE: "Office", HOME: "Home office", DAY_OFF: "Day off"}
WEEKEND_BG, OUTSIDE_BG, GRID = "#eeeeee", "#fafafa", "#c9c9c9"
HEADER_H = 28


class MonthView(tk.Canvas):
    def __init__(self, master, on_click: Callable[[date], None],
                 on_menu: Callable[[date, int, int], None], **kw):
        super().__init__(master, bg="white", highlightthickness=0, **kw)
        self.on_click, self.on_menu = on_click, on_menu
        self.year = self.month = None
        self.plan: Dict[date, str] = {}
        self.holidays: Dict[date, str] = {}
        self.overrides: Dict[date, str] = {}
        self.today = date.today()
        self.period: Optional[Tuple[date, date]] = None
        self._cells = []  # (x0, y0, x1, y1, date) for clickable cells

        self.bind("<Configure>", lambda e: self.redraw())
        self.bind("<Button-1>", self._click)
        # Right click: Button-2 on macOS, Button-3 elsewhere, or Ctrl+click.
        for seq in ("<Button-2>", "<Button-3>", "<Control-Button-1>"):
            self.bind(seq, self._menu)

    def show(self, year: int, month: int, plan, holidays, overrides,
             today: Optional[date] = None,
             period: Optional[Tuple[date, date]] = None) -> None:
        self.year, self.month = year, month
        self.plan, self.holidays, self.overrides = plan, holidays, overrides
        self.today = today or date.today()
        self.period = period
        self.redraw()

    def in_period(self, d: date) -> bool:
        return self.period is None or self.period[0] <= d <= self.period[1]

    def redraw(self) -> None:
        self.delete("all")
        self._cells = []
        if self.year is None:
            return
        w = max(self.winfo_width(), 560)
        h = max(self.winfo_height(), 360)
        weeks = calendar.Calendar(firstweekday=0).monthdatescalendar(self.year, self.month)
        cw, ch = w / 7, (h - HEADER_H) / len(weeks)

        for c, name in enumerate(calendar.day_abbr):
            self.create_text(c * cw + cw / 2, HEADER_H / 2, text=name,
                             font=("Helvetica", 12, "bold"),
                             fill="#555" if c < 5 else "#999")

        for r, week in enumerate(weeks):
            for c, d in enumerate(week):
                x0, y0 = c * cw, HEADER_H + r * ch
                x1, y1 = x0 + cw, y0 + ch
                self._draw_cell(d, x0, y0, x1, y1, cw)

    def _draw_cell(self, d: date, x0, y0, x1, y1, cw) -> None:
        in_month = d.month == self.month
        kind = self.plan.get(d) if in_month else None

        if kind is None:
            bg, fg, label = (WEEKEND_BG if in_month else OUTSIDE_BG), "#a0a0a0", ""
        else:
            bg, fg = COLORS[kind]
            label = self.holidays.get(d, "Holiday") if kind == HOLIDAY else LABELS[kind]
            if not self.in_period(d):  # planned, but not exported
                bg, fg = OUTSIDE_BG, "#9a9a9a"
                label += "\n(outside period)"
            self._cells.append((x0, y0, x1, y1, d))

        self.create_rectangle(x0, y0, x1, y1, fill=bg, outline=GRID)
        if d == self.today:
            self.create_rectangle(x0 + 2, y0 + 2, x1 - 2, y1 - 2, outline="#222", width=2)
        self.create_text(x0 + 7, y0 + 5, anchor="nw", text=str(d.day),
                         font=("Helvetica", 12, "bold"),
                         fill=fg if in_month else "#cccccc")
        if label:
            self.create_text((x0 + x1) / 2, (y0 + y1) / 2 + 6, text=label, fill=fg,
                             width=cw - 12, justify="center", font=("Helvetica", 12))
        if in_month and d in self.overrides and kind != HOLIDAY:
            self.create_text(x1 - 6, y1 - 4, anchor="se", text="manual", fill=fg,
                             font=("Helvetica", 9, "italic"))

    def date_at(self, x: float, y: float) -> Optional[date]:
        for x0, y0, x1, y1, d in self._cells:
            if x0 <= x < x1 and y0 <= y < y1:
                return d
        return None

    def _click(self, event) -> None:
        d = self.date_at(event.x, event.y)
        if d:
            self.on_click(d)

    def _menu(self, event) -> None:
        d = self.date_at(event.x, event.y)
        if d:
            self.on_menu(d, event.x_root, event.y_root)
