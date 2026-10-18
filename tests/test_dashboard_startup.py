"""Hosting failure states must be useful and must never invent metrics."""

from pathlib import Path
import unittest
from unittest.mock import patch
from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


class StartupTests(unittest.TestCase):
    def test_missing_snapshots_show_only_explicit_illustrations_in_both_domains(self):
        with patch(
            "mmd_fraud.evidence.load", side_effect=FileNotFoundError("public snapshot absent")
        ):
            with self.assertLogs("mmds.dashboard", level="ERROR") as logs:
                app = AppTest.from_file(str(ROOT / "dashboard/app.py")).run()
                for domain in ("Elliptic Bitcoin", "Synthetic banking"):
                    app.sidebar.selectbox[0].select(domain).run()
                    self.assertFalse(app.exception)
                    self.assertEqual(len(app.metric), 0)
                    self.assertTrue(any("Illustrative mode" in w.value for w in app.warning))
                    self.assertTrue(any("Generated example only" in c.value for c in app.caption))
                    self.assertEqual(len(app.slider), 2)
                    self.assertEqual(len(app.get("plotly_chart")), 1)
            self.assertIn("FileNotFoundError: public snapshot absent", "\n".join(logs.output))

    def test_corruption_is_logged_and_fails_closed_without_sample_or_metrics(self):
        with patch("mmd_fraud.evidence.load", side_effect=ValueError("hash mismatch")):
            with self.assertLogs("mmds.dashboard", level="ERROR") as logs:
                app = AppTest.from_file(str(ROOT / "dashboard/app.py")).run()
            self.assertFalse(app.exception)
            self.assertEqual(len(app.metric), 0)
            self.assertEqual(len(app.get("plotly_chart")), 0)
            self.assertTrue(any("No metrics are substituted" in e.value for e in app.error))
            self.assertIn("ValueError: hash mismatch", "\n".join(logs.output))

    def test_entrypoint_requirements_resolve_to_the_existing_ui_lock(self):
        entry = ROOT / "dashboard/requirements.txt"
        requirement = next(s for s in entry.read_text().splitlines() if s.startswith("-r "))
        self.assertEqual(
            (entry.parent / requirement[3:]).resolve(), ROOT / "requirements-dashboard.lock"
        )
        self.assertEqual(
            (ROOT / "requirements.txt").read_text().splitlines()[-1],
            "-r requirements-dashboard.lock",
        )
