"""Command line: generate the .ics file and print a monthly summary."""

from __future__ import annotations

import argparse
from datetime import date

from .config import DEFAULT_PATH, PlannerConfig
from .dates import months_in_range, range_for_months
from .holidays import bulgarian_holidays
from .ics import write_ics
from .planner import month_stats, plan_month


def main(argv=None) -> None:
    today = date.today()
    p = argparse.ArgumentParser(
        prog="python3 -m office_planner",
        description="Generate an Office / Home office calendar. "
                    "Default: the next 12 months from today.")
    p.add_argument("--from", dest="start", type=date.fromisoformat,
                   help="first day, YYYY-MM-DD (default: today)")
    p.add_argument("--to", dest="end", type=date.fromisoformat,
                   help="last day, YYYY-MM-DD (default: --months after --from)")
    p.add_argument("--start-month", help="start on the 1st of a month, YYYY-MM")
    p.add_argument("--months", type=int, help="length in months (default 12)")
    p.add_argument("-o", "--output", default="office_schedule.ics")
    p.add_argument("--config", help=f"settings JSON, incl. its period (e.g. {DEFAULT_PATH})")
    args = p.parse_args(argv)

    config = PlannerConfig.load(args.config) if args.config else PlannerConfig()
    if args.start_month:
        y, m = map(int, args.start_month.split("-"))
        args.start = date(y, m, 1)

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

    write_ics(args.output, start, end, config)
    print(f"\nWritten {args.output}")


if __name__ == "__main__":
    main()
