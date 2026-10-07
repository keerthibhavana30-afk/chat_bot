"""
Unit tests for MongoDB Database Manager:
- Connection & ping verification
- Exemplar seeding and querying
- Conversation logging & retrieval
- User feedback logging
- Analytics aggregation
- Resilient fallback behavior
"""

import unittest
import sys
import os

# Add parent directory to sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from backend.database import MongoDatabaseManager

class TestMongoDatabaseManager(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Initialize a test manager instance
        cls.db = MongoDatabaseManager(db_name="test_customersupport_db")

    @classmethod
    def tearDownClass(cls):
        cls.db.close()

    def test_status_structure(self):
        """Verify that get_status returns complete telemetry."""
        status = self.db.get_status()
        self.assertIn("connected", status)
        self.assertIn("database_name", status)
        self.assertIn("pymongo_installed", status)
        self.assertTrue(status["pymongo_installed"])
        self.assertIn("counts", status)
        self.assertIn("conversations", status["counts"])
        self.assertIn("exemplars", status["counts"])

    def test_exemplar_seeding_and_retrieval(self):
        """Verify that exemplars can be seeded and filtered."""
        sample_exemplars = [
            {
                "id": "test_ex_01",
                "language": "sw",
                "intent": "order_tracking",
                "user_query": "Agizo langu liko wapi?",
                "bot_response": "Agizo lako linaendelea kusafirishwa."
            },
            {
                "id": "test_ex_02",
                "language": "en",
                "intent": "refund_cancellation",
                "user_query": "I need a refund.",
                "bot_response": "We will process your refund."
            }
        ]
        self.db.seed_exemplars(sample_exemplars)
        
        # Query all
        all_exs = self.db.get_exemplars()
        self.assertGreaterEqual(len(all_exs), 2)

        # Query by language
        sw_exs = self.db.get_exemplars(lang="sw")
        self.assertTrue(any(e["language"] == "sw" for e in sw_exs))

        # Query by intent
        refund_exs = self.db.get_exemplars(intent="refund_cancellation")
        self.assertTrue(any(e["intent"] == "refund_cancellation" for e in refund_exs))

    def test_conversation_logging_and_history(self):
        """Verify conversation persistence and history retrieval."""
        test_payload = {
            "session_id": "test_sess_101",
            "user_message": "Where is my item?",
            "response": "Your package is arriving tomorrow.",
            "target_language": {"code": "en", "name": "English"},
            "intent": "order_tracking",
            "intent_confidence": 0.95,
            "sentiment": "Neutral",
            "sentiment_score": 0.5,
            "entities": {"order_id": "#ORD-99"},
            "cot_trace": [{"step": 1, "name": "Test Step"}],
            "latency_ms": 42
        }

        conv_id = self.db.log_conversation(test_payload)
        self.assertIsNotNone(conv_id)

        history = self.db.get_conversation_history(limit=10, session_id="test_sess_101")
        self.assertGreaterEqual(len(history), 1)
        latest = history[0]
        self.assertEqual(latest["session_id"], "test_sess_101")
        self.assertEqual(latest["user_message"], "Where is my item?")
        self.assertEqual(latest["intent"], "order_tracking")

    def test_feedback_logging(self):
        """Verify feedback logging."""
        saved = self.db.log_feedback({
            "conversation_id": "conv_test_123",
            "rating": 1,
            "notes": "Excellent translation!"
        })
        self.assertTrue(saved)

    def test_analytics(self):
        """Verify analytics return valid structure."""
        analytics = self.db.get_analytics()
        self.assertIn("total_conversations", analytics)
        self.assertIn("total_exemplars", analytics)
        self.assertIn("storage", analytics)

if __name__ == "__main__":
    unittest.main()
