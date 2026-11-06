"""User settings, stored as JSON."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field, fields
from datetime import date
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .dates import range_for_months

WEEKDAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
DEFAULT_PATH = Path.home() / ".office_planner.json"

ALARM_EVENING_BEFORE = "before"
ALARM_MORNING_OF = "same"


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
        return cls(**data)

    def save(self, path: Path = DEFAULT_PATH) -> None:
        Path(path).write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")

    @classmethod
    def load(cls, path: Path = DEFAULT_PATH) -> "PlannerConfig":
        """Load settings; fall back to defaults if the file is missing or broken."""
        try:
            return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError):
            return cls()
