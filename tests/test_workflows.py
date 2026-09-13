"""Run with: python -m unittest discover -s tests -v"""
import json
import time
from io import BytesIO
from PIL import Image
import streamlit as st
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import requests
from streamlit.testing.v1 import AppTest

from pulse.agents.correlation import correlation_agent
from pulse.agents.risk import risk_agent
from pulse.agents.signal import signal_agent
from pulse.data import export_reports, import_reports, make_report, report_frame
from pulse.demo import demo_data
from pulse.services import live_weather, simulated_weather

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = [
    ("The sewer is overflowing by the clinic entrance.", "Sewage"),
    ("The drain outlet near the market is blocked.", "Drainage"),
    ("Garbage has piled up across the culvert entrance.", "Garbage"),
]


class CoreWorkflows(unittest.TestCase):
    def setUp(self):
        self.clock = datetime.now(timezone.utc)
        self.rows = [make_report(text, "Gulshan-e-Iqbal", self.clock-timedelta(minutes=5-i),
                                category, 3, source="Citizen web report",
                                lat=24.9234+i*.001, lon=67.0920)
                     for i, (text, category) in enumerate(EXAMPLES)]

    def incidents(self, rows, rain=False):
        return [risk_agent(inc, simulated_weather(rain), self.clock, 1.5)
                for inc in correlation_agent(report_frame(rows), self.clock, 1.5, 24)]

    def test_reports_need_related_nearby_signals(self):
        self.assertEqual(self.incidents(self.rows[:1]), [])
        self.assertEqual(self.incidents(self.rows[:2]), [])
        self.assertEqual(self.incidents(self.rows)[0]["kind"], "drain")
        far = [dict(r) for r in self.rows]
        far[-1]["latitude"] += .1
        self.assertEqual(self.incidents(far), [])
        stale = [dict(r) for r in self.rows]
        stale[-1]["timestamp"] -= timedelta(days=3)
        self.assertEqual(self.incidents(stale), [])

    def test_duplicates_do_not_inflate_risk_or_confidence(self):
        repeated = list(self.rows)
        for i in range(20):
            duplicate = dict(self.rows[-1])
            duplicate.update(report_id=f"R-DUP{i:08d}", timestamp=self.clock)
            repeated.append(duplicate)
        base, result = self.incidents(self.rows)[0], self.incidents(repeated)[0]
        self.assertEqual((base["risk"], base["confidence"]), (result["risk"], result["confidence"]))
        self.assertEqual(result["reports"], 23)
        self.assertEqual(result["signals"], 3)

    def test_forecast_changes_risk(self):
        dry, wet = self.incidents(self.rows)[0], self.incidents(self.rows, True)[0]
        self.assertGreaterEqual(wet["risk"]-dry["risk"], 17)
        self.assertEqual(wet["confidence"], dry["confidence"])

    def test_multilingual_fallback(self):
        for text, category in [("Gali mein gutter overflow ho raha hai.", "Sewage"),
                               ("نالی بند ہے", "Drainage"),
                               ("Garbage has not been collected for three days.", "Garbage")]:
            self.assertEqual(signal_agent(text)["category"], category)

    def test_backups_validate_and_merge_without_duplicates(self):
        backup = export_reports(self.rows, "Live")
        restored, count = import_reports(backup, [], "Live", self.clock)
        self.assertEqual(count, 3)
        self.assertEqual(self.incidents(restored)[0]["risk"], self.incidents(self.rows)[0]["risk"])
        merged, count = import_reports(backup, restored, "Live", self.clock)
        self.assertEqual((len(merged), count), (3, 0))
        for invalid in [b"{}", b"{bad", b"[]"]:
            with self.assertRaises(ValueError):
                import_reports(invalid, [], "Live", self.clock)
        with self.assertRaises(ValueError):
            import_reports(backup, [], "Demo", self.clock)

    def test_demo_has_moderate_and_high_incidents(self):
        self.assertEqual(sorted(i["level"] for i in self.incidents(demo_data(self.clock))),
                         ["High", "Moderate"])

    def test_weather_failure_uses_labelled_fallback(self):
        live_weather.clear()
        with patch("pulse.services.requests.get", side_effect=requests.Timeout):
            weather = live_weather()
        self.assertTrue(weather["simulated"])
        self.assertIn("unavailable", weather["source"])
        live_weather.clear()


class InterfaceWorkflows(unittest.TestCase):
    def setUp(self):
        self.weather_patch = patch("pulse.services.requests.get", side_effect=requests.Timeout)
        self.weather_patch.start()
        self.key_patch = patch("pulse.ui.sidebar.secret", side_effect=lambda name, default="": default)
        self.key_patch.start()
        self.location_patch = patch("pulse.ui.reports.capture_location", side_effect=lambda **kwargs: {
            "status": "ok", "latitude": 24.9234, "longitude": 67.0920,
            "accuracy": 15, "timestamp": time.time()*1000})
        self.location_patch.start()
        live_weather.clear()
        self.app = AppTest.from_file(str(ROOT / "app.py"), default_timeout=30).run()
        self.check()

    def tearDown(self):
        self.weather_patch.stop()
        self.key_patch.stop()
        self.location_patch.stop()
        live_weather.clear()

    def check(self):
        self.assertEqual([e.message for e in self.app.exception], [])

    def button(self, label):
        next(b for b in self.app.button if b.label == label).click().run()
        self.check()

    def page(self, value):
        names = {"Command Center": "Overview", "Report an Issue": "Add a report", "Emerging Incidents": "Incidents",
                 "Reports": "Report records", "City Map": "City map", "Analytics": "Trends", "AI Intelligence": "How it works"}
        self.button(names[value])
        self.check()

    def mode(self, value):
        self.app.radio(key="workspace_choice").set_value(value).run()
        self.check()

    def submit(self, text, category):
        self.page("Report an Issue")
        self.app.text_area[0].set_value(text)
        next(s for s in self.app.selectbox if s.label == "Category").set_value(category)
        self.button("Analyze & add signal")

    def metric(self, label):
        return next(m.value for m in self.app.metric if m.label == label)

    def test_live_report_records_map_and_review_lifecycle(self):
        self.mode("Live")
        for text, category in EXAMPLES:
            self.submit(text, category)
            self.assertIn(text, self.app.dataframe[0].value["Description"].tolist())
        self.page("Command Center")
        self.assertEqual((self.metric("Active Reports"), self.metric("Emerging Incidents")), ("3", "1"))
        iid = next(iter(self.app.session_state["registry"]))
        before = self.app.session_state["registry"][iid]["last"]["risk"]
        self.submit(*EXAMPLES[-1])
        self.assertEqual(self.app.session_state["registry"][iid]["last"]["risk"], before)
        self.page("City Map")
        chart = json.loads(self.app.get("plotly_chart")[0].proto.spec)
        garbage = next(t for t in chart["data"] if t["name"] == "Garbage")
        self.assertIn("2 Garbage report(s)", str(garbage["text"]))
        self.assertTrue(any(t["name"] == "Emerging incidents" for t in chart["data"]))
        self.page("Emerging Incidents")
        next(s for s in self.app.selectbox if s.label == "Human review status").set_value("Resolved")
        self.button("Save review status")
        self.assertTrue(all(r["status"] == "Resolved" for r in self.app.session_state["reports"]))
        self.page("Command Center")
        self.assertEqual(self.metric("Emerging Incidents"), "0")
        self.page("Reports")
        for rid in [r["report_id"] for r in self.app.session_state["reports"]]:
            self.app.selectbox(key="records_report").set_value(rid).run()
            next(s for s in self.app.selectbox if s.label == "Status").set_value("Open")
            self.button("Save report changes")
        self.page("Command Center")
        self.assertEqual(self.metric("Emerging Incidents"), "1")
        self.button("Refresh overview")
        self.assertEqual(len(self.app.session_state["reports"]), 4)

    def test_modes_demo_and_all_screens(self):
        self.mode("Live")
        self.submit(*EXAMPLES[0])
        self.mode("Demo")
        self.page("Command Center")
        for _ in range(6):
            self.button("Simulate Incoming City Signals")
        self.assertEqual(self.app.session_state["stage"], 6)
        for name in ["Reports", "Report an Issue", "City Map", "Analytics", "AI Intelligence", "Emerging Incidents"]:
            self.page(name)
        self.mode("Live")
        self.assertEqual(len(self.app.session_state["reports"]), 1)
        self.assertEqual(self.app.session_state["offset"], 0)
        for name in ["Command Center", "Reports", "City Map", "Analytics", "AI Intelligence", "Emerging Incidents"]:
            self.page(name)

    def test_review_button_opens_selected_incident_and_survives_rerun(self):
        self.page("Command Center")
        button = next(b for b in self.app.button if b.label == "Review incident →")
        iid = button.key.removeprefix("review_")
        button.click().run()
        self.check()
        self.assertEqual(self.app.session_state["nav_page"], "Emerging Incidents")
        self.assertEqual(self.app.selectbox(key="selected_review_incident").value, iid)
        self.button("Refresh overview")
        self.assertEqual(self.app.selectbox(key="selected_review_incident").value, iid)

    def test_location_failure_preserves_draft_and_does_not_submit(self):
        self.mode("Live")
        with patch("pulse.ui.reports.capture_location", return_value={"status": "error"}):
            self.submit(*EXAMPLES[0])
            self.assertEqual(len(self.app.session_state["reports"]), 0)
            self.assertEqual(self.app.text_area[0].value, EXAMPLES[0][0])
            self.assertTrue(any("Allow location" in e.value for e in self.app.error))

    def test_photo_is_saved_with_captured_coordinates(self):
        self.mode("Live")
        image = BytesIO()
        Image.new("RGB", (64, 64), "green").save(image, format="PNG")
        original = st.file_uploader
        def uploader(label, *args, **kwargs):
            return BytesIO(image.getvalue()) if label == "Add a photo (optional)" else original(label, *args, **kwargs)
        with patch("pulse.ui.reports.st.file_uploader", side_effect=uploader):
            self.submit(*EXAMPLES[0])
            report = self.app.session_state["reports"][0]
            self.assertTrue(report["photo"]["base64"])
            self.assertEqual(report["latitude"], 24.9234)
            self.assertIn("Browser location", report["location_basis"])
            with patch("pulse.ui.reports.st.image", wraps=st.image) as rendered:
                self.page("Reports")
                self.assertTrue(any(call.kwargs.get("caption") == "Attached report photo" for call in rendered.call_args_list))


if __name__ == "__main__":
    unittest.main()
