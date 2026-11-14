"""Export a plan as an iCalendar (.ics) file that Apple Calendar can import."""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from .config import ALARM_EVENING_BEFORE, PlannerConfig
from .holidays import bulgarian_holidays
from .planner import DAY_OFF, HOLIDAY, HOME, OFFICE, plan_range

SUMMARIES = {OFFICE: "🏢 Office", HOME: "🏠 Home office", DAY_OFF: "🌴 Day off"}
DESCRIPTIONS = {
    OFFICE: "Office day",
    HOME: "Home office day",
    DAY_OFF: "Day off",
    HOLIDAY: "Official non-working day in Bulgaria",
}


def ics_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")


def alarm_trigger(alarm_day: str, alarm_time: str) -> str:
    """Trigger relative to the start (00:00) of an all-day event."""
    hours, minutes = map(int, alarm_time.split(":"))
    offset = hours * 60 + minutes
    if alarm_day == ALARM_EVENING_BEFORE:
        offset -= 24 * 60
    sign = "-" if offset < 0 else ""
    offset = abs(offset)
    return f"{sign}PT{offset // 60}H{offset % 60}M"


def make_event(day: date, summary: str, description: str, stamp: str,
               trigger: str | None) -> list[str]:
    lines = [
        "BEGIN:VEVENT",
        f"UID:{uuid.uuid5(uuid.NAMESPACE_URL, f'office-plan-{day}')}",
        f"DTSTAMP:{stamp}",
        f"DTSTART;VALUE=DATE:{day:%Y%m%d}",
        f"DTEND;VALUE=DATE:{day + timedelta(days=1):%Y%m%d}",
        f"SUMMARY:{ics_escape(summary)}",
        f"DESCRIPTION:{ics_escape(description)}",
        "TRANSP:TRANSPARENT",
    ]
    if trigger:
        lines += [
            "BEGIN:VALARM",
            "ACTION:DISPLAY",
            f"DESCRIPTION:{ics_escape(summary)}",
            f"TRIGGER:{trigger}",
            "END:VALARM",
        ]
    lines.append("END:VEVENT")
    return lines


def build_ics(start: date, end: date, config: PlannerConfig | None = None,
              stamp: datetime | None = None) -> str:
    """Calendar with one all-day event per weekday from start to end (inclusive)."""
    config = config or PlannerConfig()
    stamp_s = (stamp or datetime.now(timezone.utc)).strftime("%Y%m%dT%H%M%SZ")
    trigger = alarm_trigger(config.alarm_day, config.alarm_time) if config.alarm_enabled else None

    out = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//office-plan//EN",
        "CALSCALE:GREGORIAN",
        "X-WR-CALNAME:Office / Home office",
    ]
    for day, kind in sorted(plan_range(start, end, config).items()):
        if kind == HOLIDAY:
            name = bulgarian_holidays(day.year)[day]
            out += make_event(day, f"🇧🇬 {name}", DESCRIPTIONS[HOLIDAY], stamp_s, None)
        else:
            out += make_event(day, SUMMARIES[kind], DESCRIPTIONS[kind], stamp_s,
                              None if kind == DAY_OFF else trigger)
    out.append("END:VCALENDAR")
    return "\r\n".join(out) + "\r\n"


def write_ics(path: str | Path, start: date, end: date, config: PlannerConfig | None = None,
              stamp: datetime | None = None) -> None:
    with Path(path).open("w", encoding="utf-8", newline="") as f:
        f.write(build_ics(start, end, config, stamp))
