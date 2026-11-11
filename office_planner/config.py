"""User settings, stored as JSON."""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import tempfile
import warnings
from dataclasses import asdict, dataclass, field, fields
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .dates import range_for_months

WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]


def default_path() -> Path:
    """~/.office_planner.json, or next to the .exe for the portable Windows build."""
    if getattr(sys, "frozen", False) and sys.platform == "win32":
        portable = Path(sys.executable).with_name("office_planner.json")
        try:  # e.g. not writable under C:\Program Files -> fall back to home
            tempfile.TemporaryFile(dir=portable.parent).close()
            return portable
        except OSError:
            pass
    return Path.home() / ".office_planner.json"


DEFAULT_PATH = default_path()

ALARM_EVENING_BEFORE = "before"
ALARM_MORNING_OF = "same"
TIME_RE = re.compile(r"([01]?\d|2[0-3]):[0-5]\d")
MAX_PERIOD_MONTHS = 36


@dataclass
class PlannerConfig:
    # Weekdays (0=Mon .. 4=Fri) that are always office days.
    office_weekdays: List[int] = field(default_factory=lambda: [0, 2])
    # Minimum share of working days per month spent in the office.
    office_share: float = 0.5
    # Order in which extra office days are chosen when the share isn't met.
    extra_preference: List[int] = field(default_factory=lambda: [1, 3, 4, 0, 2])
    # Reminder: on the evening before or on the morning of the day, at HH:MM.
    alarm_enabled: bool = True
    alarm_day: str = ALARM_EVENING_BEFORE
    alarm_time: str = "18:00"
    # Manual per-day choices: date -> "office" | "home" | "day_off".
    overrides: Dict[date, str] = field(default_factory=dict)
    # Period to plan/export: N months from today, or custom dates when 0.
    period_months: int = 12
    custom_start: Optional[date] = None
    custom_end: Optional[date] = None

    def period(self, today: date) -> Tuple[date, date]:
        if self.period_months == 0 and self.custom_start and self.custom_end:
            return self.custom_start, self.custom_end
        return range_for_months(today, self.period_months or 12)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["overrides"] = {d.isoformat(): k for d, k in sorted(self.overrides.items())}
        for key in ("custom_start", "custom_end"):
            if data[key]:
                data[key] = data[key].isoformat()
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "PlannerConfig":
        known = {f.name for f in fields(cls)}
        data = {k: v for k, v in data.items() if k in known}
        if "overrides" in data:
            data["overrides"] = {date.fromisoformat(d): k for d, k in data["overrides"].items()}
        for key in ("custom_start", "custom_end"):
            if data.get(key):
                data[key] = date.fromisoformat(data[key])
        cfg = cls(**data)
        cfg.validate()
        return cfg

    def validate(self) -> None:
        """Raise ValueError/TypeError for values the planner or GUI can't handle."""
        ok = (all(type(n) is int for n in
                  [*self.office_weekdays, *self.extra_preference, self.period_months])
              and set(self.office_weekdays) <= set(range(5))
              and set(self.extra_preference) <= set(range(5))
              and 0 <= self.office_share <= 1
              and self.alarm_day in (ALARM_EVENING_BEFORE, ALARM_MORNING_OF)
              and TIME_RE.fullmatch(self.alarm_time)
              # same strings as planner.OFFICE / HOME / DAY_OFF (planner imports config)
              and set(self.overrides.values()) <= {"office", "home", "day_off"}
              and 0 <= self.period_months <= MAX_PERIOD_MONTHS
              and not (self.custom_start and self.custom_end
                       and self.custom_end < self.custom_start))
        if not ok:
            raise ValueError("invalid settings")

    def save(self, path: Path = DEFAULT_PATH) -> None:
        # Write then rename, so a crash mid-write never leaves a half-written file.
        path = Path(path).resolve()  # a symlinked file stays a symlink
        tmp = path.with_name(path.name + ".tmp")
        tmp.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        os.replace(tmp, path)

    @classmethod
    def load(cls, path: Path = DEFAULT_PATH) -> "PlannerConfig":
        """Load settings; fall back to defaults if the file is missing or broken."""
        path = Path(path)
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            return cls()
        try:
            return cls.from_dict(json.loads(text))
        except (ValueError, TypeError, AttributeError):
            # Keep a copy: the GUI's next save would otherwise overwrite it with defaults.
            backup = path.with_name(path.name + ".broken")
            try:
                shutil.copyfile(path, backup)
            except OSError:
                backup = None
            warnings.warn(f"{path} is invalid, using default settings."
                          + (f" The old file was copied to {backup}." if backup else ""))
            return cls()
