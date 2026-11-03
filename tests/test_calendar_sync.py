import os
import sys
import unittest
from datetime import date

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from core.calendar_sync import CalendarSync


class TestCalendarSync(unittest.TestCase):
    def test_parse_deadline_various_formats(self):
        cases = [
            ("2026-12-10", date(2026, 12, 10)),
            ("03.Nov.2026", date(2026, 11, 3)),
            ("Monday, September 28, 2026", date(2026, 9, 28)),
            ("Sunday, October 4, 2026", date(2026, 10, 4)),
            ("2026-11-27", date(2026, 11, 27)),
            ("2026-12-15", date(2026, 12, 15)),
            ("Unspecified", None),
            ("unspecified", None),
            (None, None),
            ("", None),
        ]
        for raw, expected in cases:
            with self.subTest(raw=raw):
                parsed = CalendarSync.parse_deadline(raw)
                self.assertEqual(parsed, expected)

    def test_build_event_body(self):
        sample_offering = {
            "id": 80,
            "title": "PhD Student in Theoretical Physics: Quantum Sensing with Anharmonic Systems",
            "institution": "Stockholm University",
            "location": "Stockholm, Sweden",
            "deadline": "2026-11-03",
            "url": "https://example.com/stockholm-job"
        }
        sample_eval = {
            "total_score": 9.1,
            "score_academic": 9.5,
            "score_geography": 10.0,
            "score_financial": 8.0,
            "evaluation_summary": "Strong synergy with non-perturbative quantum models."
        }
        event = CalendarSync.build_event_body(sample_offering, sample_eval)
        self.assertIsNotNone(event)
        self.assertEqual(event["start"]["date"], "2026-11-03")
        self.assertEqual(event["end"]["date"], "2026-11-04") # Google Calendar all-day exclusive end
        self.assertIn("Stockholm University", event["summary"])
        self.assertIn("9.1/10", event["summary"])
        self.assertEqual(event["colorId"], "11")
        self.assertEqual(event["extendedProperties"]["private"]["hypatia_offering_id"], "80")

    def test_build_event_body_unspecified_deadline(self):
        sample = {
            "id": 67,
            "title": "Research Fellowship: Theoretical Physics",
            "institution": "CERN",
            "deadline": "Unspecified"
        }
        event = CalendarSync.build_event_body(sample)
        self.assertIsNone(event)


if __name__ == "__main__":
    unittest.main()
