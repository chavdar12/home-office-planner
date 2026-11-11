"""Command line: generate the .ics file and print a monthly summary."""

from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from .config import DEFAULT_PATH, PlannerConfig
from .dates import months_in_range, range_for_months
from .holidays import bulgarian_holidays
from .ics import write_ics
from .planner import month_stats, plan_month


def positive_int(text: str) -> int:
    n = int(text)
    if n < 1:
        raise ValueError
    return n


def year_month(text: str) -> date:
    return date.fromisoformat(text + "-01")


def main(argv=None) -> None:
    today = date.today()
    p = argparse.ArgumentParser(
        prog="python3 -m office_planner",
        description="Generate an Office / Home office calendar. "
                    "Default: the next 12 months from today.")
    start = p.add_mutually_exclusive_group()
    start.add_argument("--from", dest="start", type=date.fromisoformat,
                       help="first day, YYYY-MM-DD (default: today)")
    start.add_argument("--start-month", type=year_month,
                       help="start on the 1st of a month, YYYY-MM")
    p.add_argument("--to", dest="end", type=date.fromisoformat,
                   help="last day, YYYY-MM-DD (default: --months after --from)")
    p.add_argument("--months", type=positive_int, help="length in months (default 12)")
    p.add_argument("-o", "--output", default="office_schedule.ics")
    p.add_argument("--config", help=f"settings JSON, incl. its period (e.g. {DEFAULT_PATH})")
    args = p.parse_args(argv)

    config = PlannerConfig()
    if args.config:  # unlike the GUI, don't silently fall back to defaults
        try:
            config = PlannerConfig.from_dict(
                json.loads(Path(args.config).read_text(encoding="utf-8")))
        except (OSError, ValueError, TypeError, AttributeError) as e:
            p.error(f"cannot use --config {args.config}: {e}")
    args.start = args.start or args.start_month

    if args.start or args.end or args.months:
        start = args.start or today
        end = args.end or range_for_months(start, args.months or 12)[1]
    else:
        start, end = config.period(today)
    if end < start:
        p.error("--to must not be before --from")

    print(f"Period: {start:%d %b %Y} - {end:%d %b %Y}\n")
    print(f"{'Month':<9}{'Work':>6}{'Office':>8}{'Home':>6}{'Off':>5}{'Office%':>9}")
    for y, m in months_in_range(start, end):
        s = month_stats(y, m, plan_month(y, m, config, bulgarian_holidays(y)), config)
        print(f"{y}-{m:02d}  {s.working:>6}{s.office:>8}{s.home:>6}"
              f"{s.holidays + s.days_off:>5}{s.share:>9.0%}")

    try:
        write_ics(args.output, start, end, config)
    except OSError as e:
        p.exit(1, f"Cannot write {args.output}: {e}\n")
    print(f"\nWritten {args.output}")


if __name__ == "__main__":
    main()
