import tempfile
import unittest
from pathlib import Path

from bug_reports import Reports
from conversation_service import requires_research, text_revision
from language_understanding import contextual_followup, question_form


class PublicHelperTests(unittest.TestCase):
    def test_question_normalization(self):
        self.assertEqual(question_form("What's DNS?"), "what is DNS?")
        self.assertTrue(contextual_followup("Can you explain that again?"))

    def test_research_gate(self):
        self.assertTrue(requires_research("Look up the latest release"))
        self.assertFalse(requires_research("Tell me a joke"))

    def test_revision_gate(self):
        self.assertTrue(text_revision("Revise your previous report"))
        self.assertFalse(text_revision("Revise your report and deploy it"))

    def test_bug_report_redaction_and_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            store = Reports(Path(tmp))
            payload = {
                "request_id": "a" * 20,
                "summary": "Example failure",
                "steps": "Open the panel",
                "expected": "A result",
                "actual": "Blank output",
                "diagnostics": "token=example-private-value",
            }
            result = store.submit("tester", payload)
            self.assertTrue(result["id"].startswith("BUG-"))
            self.assertNotIn("example-private-value", str(store.list("tester")))
            self.assertEqual(store.path.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
