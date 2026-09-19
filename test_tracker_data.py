import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from tracker_data import TrackerReader, duration


class DataTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name)
        self.reader = TrackerReader(self.path)
        self.today = date(2026, 9, 13)

    def write(self, name, text):
        (self.path / name).write_text(text, encoding="utf-8")

    def session(self, day, value):
        self.write("last_session.json", json.dumps({"date": day, "hours_coding": value}))

    def test_units_duplicates_and_unknown_dates(self):
        self.write("log.txt", "2026:09:11 : 100\n2026:09:11 : 3600\n2026:09:12 : 0\n")
        self.session("2026:09:13", 7200)
        snap = self.reader.read(self.today)
        self.assertEqual(snap.period(5, self.today)[0][1], None)
        self.assertEqual(sum(snap.days.values()), 10800)
        self.assertEqual(duration(snap.days[self.today]), "2h 00m")
        self.assertEqual(snap.days[date(2026, 9, 12)], 0)

    def test_stale_historical_session_does_not_replace_finalized_total(self):
        self.write("log.txt", "2026:09:12 : 4000\n")
        self.session("2026:09:12", 3000)
        self.assertEqual(self.reader.read(self.today).days[date(2026, 9, 12)], 4000)

    def test_live_session_wins_without_double_counting(self):
        self.write("log.txt", "2026:09:13 : 4000\n")
        self.session("2026:09:13", 3900)
        self.assertEqual(self.reader.read(self.today).days[self.today], 3900)

    def test_partial_json_keeps_last_good_then_recovers(self):
        self.session("2026:09:13", 3600)
        self.reader.read(self.today)
        self.write("last_session.json", '{"date":')
        snap = self.reader.read(self.today)
        self.assertEqual(snap.days[self.today], 3600)
        self.assertTrue(snap.warnings)
        self.session("2026:09:13", 3700)
        self.assertEqual(self.reader.read(self.today).days[self.today], 3700)

    def test_partial_log_does_not_discard_previous_history(self):
        self.write("log.txt", "2026:09:11 : 3600\n")
        self.reader.read(self.today)
        self.write("log.txt", "2026:09:11 : 3600\n2026:09:")
        self.assertEqual(len(self.reader.read(self.today).days), 1)

    def test_invalid_duration_and_future_dates_are_rejected(self):
        for value in (-1, float("nan"), float("inf"), True, 86401):
            self.session("2026:09:13", value)
            self.assertEqual(self.reader.read(self.today).days, {})
        self.session("2026:09:14", 100)
        self.assertEqual(self.reader.read(self.today).days, {})

    def test_midnight_and_missing_files(self):
        self.assertFalse(self.reader.read(self.today).days)
        self.session("2026:09:13", 3600)
        snap = self.reader.read(date(2026, 9, 14))
        self.assertEqual(snap.days[self.today], 3600)
        self.assertIsNone(snap.period(5, date(2026, 9, 14))[-1][1])


if __name__ == "__main__":
    unittest.main()
