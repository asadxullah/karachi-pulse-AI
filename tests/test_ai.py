"""Provider failures, grounded chat and UI workflows; no real credentials."""
from pathlib import Path
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch, MagicMock
import requests
from streamlit.testing.v1 import AppTest
from pulse.services import gemini_json, ai_error, available_models
from pulse.agents.assistant import AssistantOutput, assistant_reply, workspace_context
from pulse.data import report_frame


class AIIntegration(unittest.TestCase):
    def test_invalid_short_model_is_actionable(self):
        diag = {}
        self.assertIsNone(gemini_json("fake", "3.7", "", {}, AssistantOutput, diag))
        self.assertIn("complete", diag["error"])

    def test_errors_do_not_expose_provider_text(self):
        for code, fragment in [(403, "access"), (404, "Model"), (429, "quota"), (503, "temporarily")]:
            error = Exception("SECRET-provider-request")
            error.code = code
            message = ai_error(error)
            self.assertIn(fragment, message)
            self.assertNotIn("SECRET", message)

    def test_structured_success_and_invalid_response(self):
        with patch("google.genai.Client") as factory:
            client = factory.return_value.__enter__.return_value
            client.models.generate_content.return_value = SimpleNamespace(text=json.dumps({"answer":"Hello", "suggested_pages":[]}))
            self.assertEqual(gemini_json("fake", "models/gemini-test", "", {}, AssistantOutput)["answer"], "Hello")
            self.assertEqual(client.models.generate_content.call_args.kwargs["model"], "gemini-test")
            client.models.generate_content.return_value = SimpleNamespace(text="{truncated")
            diag = {}
            self.assertIsNone(gemini_json("fake", "gemini-test", "", {}, AssistantOutput, diag))
            self.assertIn("invalid", diag["error"])

    def test_model_discovery_filters_generation_models(self):
        with patch("google.genai.Client") as factory:
            factory.return_value.__enter__.return_value.models.list.return_value = [
                SimpleNamespace(name="models/gemini-test", supported_actions=["generateContent"]),
                SimpleNamespace(name="models/gemini-embed", supported_actions=["embedContent"])]
            self.assertEqual(available_models("fake"), (["gemini-test"], None))

    def test_context_and_actions_are_bounded(self):
        context = workspace_context(report_frame([]), [], {"simulated": True}, "Live", 1.5, 24)
        self.assertEqual(context["reports_total"], 0)
        incident = dict(id="I1", title="Possible issue", area="Clifton", risk=70, confidence=80,
                        signals=3, reports=3, status="Monitoring", factors={}, categories=["Drainage"],
                        inspection="Inspect near 24.12345, 67.12345", latitude=24.12345)
        safe = workspace_context(report_frame([]), [incident], {}, "Live", 1.5, 24)
        self.assertNotIn("24.12345", json.dumps(safe))
        with patch("pulse.agents.assistant.gemini_json", return_value={"answer":"Review records", "suggested_pages":["Delete everything", "Report records"]}):
            result = assistant_reply("help", [], context, "fake", "gemini-test")
        self.assertEqual(result["suggested_pages"], ["Report records"])
        offline = assistant_reply("workspace summary", [], context)
        self.assertIn("0 reports", offline["answer"])
        self.assertEqual(offline["method"], "Built-in help")

    def test_settings_discovery_selection_and_connection(self):
        with patch("pulse.services.requests.get", side_effect=requests.Timeout), patch(
            "pulse.ui.ai_settings.secret", side_effect=lambda n, default="": "fake" if n == "GEMINI_API_KEY" else default
        ), patch("pulse.ui.ai_settings.available_models", return_value=(["gemini-test"], None)), patch(
            "pulse.ui.ai_settings.test_connection", return_value=(True, None)
        ) as probe:
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30).run()
            app.text_input(key="ai_model").set_value("3.7").run()
            next(b for b in app.button if b.label == "Load available models").click().run()
            app.selectbox(key="ai_available_choice").set_value("gemini-test").run()
            self.assertEqual(app.text_input(key="ai_model").value, "gemini-test")
            app.checkbox(key="ai_consent").check().run()
            next(b for b in app.button if b.label == "Test connection").click().run()
            probe.assert_called_once_with("fake", "gemini-test")
            self.assertTrue(any("Gemini connected" in v.value for v in app.success))
            self.assertFalse(app.exception)

    def test_chat_navigation_isolation_and_clear(self):
        with patch("pulse.services.requests.get", side_effect=requests.Timeout), patch("pulse.ui.ai_settings.secret", side_effect=lambda n, default="": default):
            app = AppTest.from_file(str(Path(__file__).resolve().parents[1] / "app.py"), default_timeout=30).run()
            next(b for b in app.button if b.label == "Assistant").click().run()
            self.assertFalse(app.exception)
            app.chat_input[0].set_value("How do I submit a report?").run()
            self.assertEqual(len(app.chat_message), 2)
            next(b for b in app.button if b.label == "Open Add a report").click().run()
            self.assertEqual(app.session_state["nav_page"], "Report an Issue")
            next(b for b in app.button if b.label == "Assistant").click().run()
            app.radio(key="workspace_choice").set_value("Live").run()
            self.assertEqual(len(app.chat_message), 0)
            app.radio(key="workspace_choice").set_value("Demo").run()
            self.assertEqual(len(app.chat_message), 2)
            next(b for b in app.button if b.label == "Clear conversation").click().run()
            self.assertEqual(len(app.chat_message), 0)
            self.assertFalse(app.exception)


if __name__ == "__main__":
    unittest.main()
