"""Read the existing tracker format. All internal durations are SECONDS."""
from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

LOG_LINE = re.compile(r"^(\d{4}:\d{2}:\d{2})\s*:\s*(\S+)\s*$")


def seconds(value):
    if isinstance(value, bool):
        raise ValueError("Boolean duration")
    value = float(value)
    if not math.isfinite(value) or not 0 <= value <= 86400:
        raise ValueError("Duration must be between 0 and 86400 seconds")
    return value


def parse_date(value):
    return datetime.strptime(value, "%Y:%m:%d").date()


def duration(value):
    if value is None:
        return "—"
    value = int(value)
    return f"{value // 3600}h {(value % 3600) // 60:02d}m"


@dataclass
class Snapshot:
    days: dict[date, float]
    warnings: list[str]
    saved_at: float | None = None

    def period(self, count, today=None):
        today = today or date.today()
        return [(today - timedelta(days=i), self.days.get(today - timedelta(days=i)))
                for i in reversed(range(count))]


class TrackerReader:
    """Keep last good reads if a file is temporarily incomplete during writing.

    Missing days remain unknown. Repeated log dates are daily totals, not sessions.
    A finalized historical log entry wins over a stale last_session entry.
    """
    def __init__(self, folder):
        self.folder = Path(folder)
        self.cache = {}
        self.signatures = {}
        self.saved_at = None

    def read(self, today=None):
        today = today or date.today()
        warnings = []
        for name in ("log.txt", "last_session.json"):
            path = self.folder / name
            try:
                stat = path.stat()
                signature = (stat.st_mtime_ns, stat.st_size)
                if self.signatures.get(name) == signature:
                    continue
                raw = path.read_text(encoding="utf-8-sig")
                parsed = {}
                if name.endswith("json"):
                    obj = json.loads(raw)
                    parsed[parse_date(obj["date"])] = seconds(obj["hours_coding"])
                else:
                    for line in raw.splitlines():
                        if not line.strip():
                            continue
                        match = LOG_LINE.fullmatch(line.strip())
                        if not match:
                            raise ValueError("Unexpected log line")
                        parsed[parse_date(match[1])] = seconds(match[2])
                if any(day > today for day in parsed):
                    raise ValueError("Future date")
                # Do not accept data that changed while it was read.
                after = path.stat()
                if signature != (after.st_mtime_ns, after.st_size):
                    raise ValueError("File changed during read")
                self.cache[name] = parsed
                self.signatures[name] = signature
                if name.endswith("json"):
                    self.saved_at = stat.st_mtime
            except FileNotFoundError:
                warnings.append(f"{name}: file not found. " +
                                ("Showing the previous successful read." if name in self.cache else ""))
            except (OSError, ValueError, KeyError, TypeError) as exc:
                warnings.append(f"{name}: unable to read ({type(exc).__name__}). "
                                "Keeping the last valid data; retrying in 5s.")
        days = dict(self.cache.get("log.txt", {}))
        for day, value in self.cache.get("last_session.json", {}).items():
            if day == today or day not in days:
                days[day] = value
        return Snapshot(days, warnings, self.saved_at)


def demo_snapshot():
    today = date.today()
    values = [2.4, 3.1, 1.8, 0, 4.2, 2.7, 3.6, 1.2, 2.9, 3.4,
              0.8, 4.6, 2.1, 3.8, 2.5, 1.7, 0, 3.2, 4.1, 2.8,
              3.5, 1.9, 2.6, 4.3, 3.0, 2.2, 3.7, 1.4, 4.0, 2.35]
    return Snapshot({today - timedelta(days=29-i): v * 3600
                     for i, v in enumerate(values)}, [], datetime.now().timestamp())
