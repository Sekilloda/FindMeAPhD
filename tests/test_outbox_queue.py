import os
import sys
import json
import glob
import unittest

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from core.mailer import Mailer, OUTBOX_DIR, SENT_DIR

class TestOutboxQueue(unittest.TestCase):
    def setUp(self):
        # Clean test files in outbox
        for f in glob.glob(os.path.join(OUTBOX_DIR, "test_*.json")):
            os.remove(f)
        for f in glob.glob(os.path.join(SENT_DIR, "test_*.json")):
            os.remove(f)

    def tearDown(self):
        for f in glob.glob(os.path.join(OUTBOX_DIR, "test_*.json")):
            os.remove(f)
        for f in glob.glob(os.path.join(SENT_DIR, "test_*.json")):
            os.remove(f)

    def test_queue_and_stats(self):
        initial_stats = Mailer.get_outbox_stats()
        
        test_offering = {
            "id": "test_101",
            "title": "PhD in Quantum Witness Circuits",
            "institution": "Lund University",
            "deadline": "2026-11-20",
            "url": "https://example.com/phd"
        }
        test_eval = {
            "total_score": 9.2,
            "score_academic": 9.5,
            "score_geography": 10.0,
            "score_financial": 9.0,
            "evaluation_summary": "Top match."
        }
        
        queued_path = Mailer.queue_alert(
            offering=test_offering,
            evaluation=test_eval,
            guide_text="Test guide",
            subject="Test Alert",
            plain_body="Plain text body",
            html_body="<p>HTML body</p>"
        )
        
        self.assertTrue(os.path.exists(queued_path))
        with open(queued_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        self.assertEqual(data["offering_id"], "test_101")
        self.assertEqual(data["status"], "pending")
        self.assertEqual(data["subject"], "Test Alert")
        
        stats_after = Mailer.get_outbox_stats()
        self.assertEqual(stats_after["pending"], initial_stats["pending"] + 1)

    def test_deadline_calculation(self):
        self.assertIsNone(Mailer.get_days_until_deadline("unspecified"))
        self.assertIsNone(Mailer.get_days_until_deadline(None))
        days = Mailer.get_days_until_deadline("2026-11-05")
        self.assertIsInstance(days, int)

if __name__ == "__main__":
    unittest.main()
