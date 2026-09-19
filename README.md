# Coding Tracker & Dashboard

A Python application for Windows that tracks time spent in your configured IDEs and displays saved coding activity in a desktop dashboard.

Monitor your daily coding time, review your history, and follow your progress toward a daily goal.

## Overview

This project is an evolution of my original [Coding Tracker Script](https://github.com/athchatzis/Coding-Tracker-Script), which used the Pixela API to visualize coding activity.

This version removes the Pixela API integration and introduces a dedicated desktop dashboard. The tracker has also been refactored from a function-based implementation toward a class-based structure: the main tracking state and behavior now live in the `Main` class, with supporting utility functions.

The project is part of my ongoing practice with Python, object-oriented programming, and desktop application development.

## Preview

<!-- Add your dashboard screenshots here after uploading them to the repository. -->
![image alt](https://github.com/athchatzis/Coding-Tracker-Dashboard/blob/bacd00415f84158cac78b425710f01f1aeb93efe/11.png)
![image alt](https://github.com/athchatzis/Coding-Tracker-Dashboard/blob/bacd00415f84158cac78b425710f01f1aeb93efe/22.png)

## Features

### Coding tracker

- Tracks time while a configured IDE is the foreground application.
- Uses keyboard and mouse activity to detect inactivity, with a 10-minute idle threshold.
- Saves tracking data locally, without a Pixela account or API token.
- Resumes the current day's saved coding time when restarted.
- Archives the previous day's total when a date change is detected.
- Supports a configurable IDE list through `user_config.json`.
- Checks for configuration changes while running.

### Desktop dashboard

- Today's saved coding time and progress toward an adjustable daily goal.
- Total coding time for the selected period.
- Average time per recorded day and number of days with coding activity.
- Minimum and maximum coding time across completed recorded days.
- Daily coding hours and cumulative recorded time charts.
- Daily history with record status.
- Period selection (5, 7, 14, 30, or 90 days), data folder selection, and CSV export.
- Demo mode with clearly labelled sample data.
- Remembers the selected data folder and daily goal between launches.

## How It Works

The tracker checks the foreground application's process name against the configured IDE list. It updates the coding counter while a matching IDE is active and the inactivity threshold has not been exceeded.

The tracker saves periodically every **45 minutes**. It also saves when it detects that the tracked IDE process has closed, when the date changes, and when stopped with `Ctrl+C` in a terminal.

The dashboard displays **saved data** and checks its data files every **5 seconds**. This refresh interval does not mean the tracker saves every five seconds. The displayed last-save timestamp also does not confirm that the tracker is currently running.

## Running from Source

The tracker requires Windows and Python. The dashboard uses **PySide6** for its interface and **Matplotlib** for charts.

The commands below assume `coding_tracker.py`, `dashboard.py`, and `tracker_data.py` are in the repository root. Copy the dashboard files out of the `coding_dashboard` folder if you are using the original ZIP package. Keep `dashboard.py` and `tracker_data.py` together. Run the commands from the repository root.

Create a virtual environment:

```powershell
py -m venv .venv
```

Install the tracker and dashboard dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install pywin32 psutil pynput "PySide6>=6.8,<7" "matplotlib>=3.9,<4"
```

Start the tracker:

```powershell
.\.venv\Scripts\python.exe coding_tracker.py
```

The tracker uses relative file paths, so its configuration and data files are read and written in the working directory. Use the same working directory on subsequent runs to continue using the same data.

### Start the dashboard

Open another terminal in the repository root and run:

```powershell
.\.venv\Scripts\python.exe dashboard.py --data-dir "."
```

If your tracker writes its files elsewhere, supply that folder instead:

```powershell
.\.venv\Scripts\python.exe dashboard.py --data-dir "C:\path\to\tracker-data"
```

You can also launch without arguments and use **Data folder** to select the folder containing `log.txt` and `last_session.json`:

```powershell
.\.venv\Scripts\python.exe dashboard.py
```

Without `--data-dir`, the dashboard uses the previously selected folder, or its own script directory if none has been saved. A packaged dashboard defaults to the directory containing its executable.

**The dashboard does not start or stop the tracker.** It reads saved tracking files independently and does not modify them. Keep the tracker running to collect new activity; the dashboard can be closed and reopened whenever needed.

### Preview with sample data

```powershell
.\.venv\Scripts\python.exe dashboard.py --demo
```

Demo mode displays clearly labelled sample data without needing tracker files. Choosing a data folder switches back to real data.

## Project Files

Suggested layout for the combined repository:

| File | Purpose |
| --- | --- |
| `coding_tracker.py` | Foreground IDE detection, activity tracking, configuration, and local saves. |
| `dashboard.py` | PySide6 interface, Matplotlib charts, controls, and CSV export. |
| `tracker_data.py` | Reads and validates tracker files, combines daily records, and formats durations. |
| `test_tracker_data.py` | Unit tests for the dashboard's data-reading logic. |

The dashboard ZIP's `requirements.txt` contains only its two dependencies: PySide6 and Matplotlib. The installation command above includes the tracker dependencies as well.

## Configuration

On first launch, the tracker creates `user_config.json` if it does not already exist:

```json
{
    "ide_to_track": [
        "pycharm64.exe",
        "Code.exe",
        "devenv.exe",
        "idea64.exe"
    ]
}
```

| IDE | Process name |
| --- | --- |
| PyCharm | `pycharm64.exe` |
| Visual Studio Code | `Code.exe` |
| Visual Studio | `devenv.exe` |
| IntelliJ IDEA | `idea64.exe` |

To track only PyCharm and Visual Studio Code, use:

```json
{
    "ide_to_track": ["pycharm64.exe", "Code.exe"]
}
```

Use the exact executable names, including capitalization and the `.exe` extension. Keep the `ide_to_track` key and its list-of-strings format intact. Valid changes to this list are picked up while the tracker is running.

## Reading the Dashboard

Select a period to review your activity and adjust **Daily goal** to set your target in hours.

- **Today · Saved time:** the latest saved total for today; today's record is a partial day.
- **Period total:** saved coding time across the selected period, including today's partial record.
- **Average / Recorded day:** the average across recorded days, including recorded days with zero hours.
- **Min / Max · Completed day:** the lowest and highest totals among recorded days before today in the selected period.
- **Days with coding activity:** the number of days with positive recorded coding time.

Days without a record are treated as **unknown**, rather than zero. Use **Export CSV** to export the selected period, and **Data folder** to choose the directory containing the tracker files. CSV exports include `date`, `seconds`, `hours`, `status`, and `demo` columns; unknown durations remain blank.

The daily goal ranges from **0.25 to 24 hours**, in 0.25-hour steps. The dashboard remembers the selected folder and saves goal changes made outside demo mode.

## Local Data

| File | Purpose |
| --- | --- |
| `user_config.json` | The list of IDE process names to track. |
| `last_session.json` | The latest saved date and coding time. |
| `log.txt` | Daily totals archived when a date change is detected. |
| `console_log.txt` | Diagnostic messages from the tracker. |

Despite its name, the `hours_coding` field stores the counter in **seconds**.

The dashboard combines `log.txt` with `last_session.json`. Repeated dates in the log are treated as daily totals, not separate sessions. If a file is temporarily unreadable, the dashboard keeps its last valid in-memory data, shows a warning, and retries on the next refresh. A fresh dashboard session cannot recover data it has never successfully read.

The tracker uses keyboard and mouse events to update an activity timestamp. Its callbacks do not save the keys you type or mouse coordinates. The supplied tracker code makes no network requests.

## Current Limitations

- Tracking is based on the active IDE and input activity; it estimates coding time rather than identifying the exact task being performed.
- The dashboard reflects saved records, so recent activity may not appear until the next save.
- Force-closing the tracker or shutting down unexpectedly may lose activity since the last save.

<!-- Before publishing: add a License section after choosing a license and adding the matching LICENSE file. -->
