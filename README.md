# Office Planner

Plans office / home-office days (Mon + Wed fixed, at least 50% office per month,
Bulgarian public holidays skipped) and exports them to Apple Calendar (`.ics`).

```
office_planner/
  holidays.py        Bulgarian holidays + Orthodox Easter
  config.py          settings (saved to ~/.office_planner.json by the GUI)
  dates.py           month arithmetic / date ranges
  planner.py         office/home decision per day, monthly stats
  ics.py             .ics export with reminders
  cli.py             command line
  gui/
    app.py           main window
    month_view.py    month grid
    settings_panel.py
tests/               unit tests (incl. GUI)
```

## Use

```bash
python3.13 -m office_planner.gui              # GUI
python3.13 -m office_planner                  # CLI: next 12 months from today
python3.13 -m office_planner --months 2       # next 2 months
python3.13 -m office_planner --from 2027-01-01 --to 2027-03-31
python3.13 -m office_planner --config ~/.office_planner.json   # CLI with GUI settings + period
python3.13 -m unittest                        # tests
```

Or install it (`pip install .`) to get the `office-planner` and
`office-planner-gui` commands. CI (`.github/workflows/ci.yml`) runs the tests on
Linux (Python 3.9/3.11/3.13, GUI tests under Xvfb) and macOS, then builds the
wheel and uploads it as an artifact.

**Release:** bump `version` in `pyproject.toml`, then `git tag v<version> && git push
origin v<version>`. `.github/workflows/release.yml` runs CI, builds a macOS `.dmg`
(Apple Silicon, drag-to-Applications window), a portable Windows `.exe` (no
installer; settings are kept in `office_planner.json` next to it, or in your home
folder if that folder isn't writable) and a Debian/Ubuntu `.deb` with PyInstaller,
and publishes them as a GitHub release. The DMG background lives in `packaging/`. The installers are unsigned: macOS needs
right-click > Open the first time, Windows shows a SmartScreen warning.

The GUI needs a Python with Tk 8.6+ (e.g. Homebrew: `brew install python-tk@3.13`).
macOS's built-in `/usr/bin/python3` ships Tk 8.5, which draws blank windows on
current macOS. The CLI and tests also work with the built-in Python.

In the GUI, click a day to switch Office/Home; right-click (or Ctrl+click) for
Day off / Automatic. The **Days off** tab adds vacation periods by date range (weekends and holidays are skipped), lists
them, and can switch clicking to
"mark day off" mode. Days off don't count as working days, so they lower that
month's office target.

**Period** (Schedule tab): next 1 / 2 / 3 / 6 / 12 months from today, or custom
From/To dates (up to 36 months). Only days inside the period are exported, but
the 50% target is always counted over whole calendar months. Manual changes are kept, and the remaining days are
re-planned to keep the monthly target.

## License

[GPL-3.0-or-later](LICENSE). Copyright (C) 2026 Chavdar Shishkov.
