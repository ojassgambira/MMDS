"""Read-only dashboard, provenance boundaries, real PR calculation and public HTTP smoke."""

import json
import hashlib
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request

import numpy as np
from sklearn.metrics import precision_recall_curve
from streamlit.testing.v1 import AppTest

from mmd_fraud.evidence import load, load_benchmarks, verify_artifact, ROOT
from mmd_fraud.dashboard_graph import example, figure, private_graph
from mmd_fraud.training.curves import pr_curve


class DashboardTests(unittest.TestCase):
    def test_all_pages_both_domains_and_bank_seed_switch(self):
        app = AppTest.from_file(str(ROOT / "dashboard/app.py"), default_timeout=30).run()
        for domain in ("Elliptic Bitcoin", "Synthetic banking"):
            app.sidebar.selectbox[0].select(domain).run()
            for page in (
                "Overview",
                "Transaction graph",
                "Temporal patterns",
                "Models & PR curves",
                "Scalability",
                "Research report",
            ):
                app.sidebar.radio[0].set_value(page).run()
                self.assertFalse(app.exception, f"{domain}/{page}: {app.exception}")
            if domain == "Synthetic banking":
                app.sidebar.selectbox[1].select(2).run()
                self.assertFalse(app.exception)
        app.sidebar.radio[0].set_value("Transaction graph").run()
        app.slider[0].set_value(20).run()
        self.assertFalse(app.exception)

    def test_evidence_domains_populations_and_corruption_rejected(self):
        real, bank = load("elliptic"), load("banking")
        self.assertEqual(real["stats"]["nodes"], 203769)
        self.assertEqual(bank["stats"]["nodes"], 500)
        self.assertNotEqual(real["dataset_kind"], bank["dataset_kind"])
        with self.assertRaises(ValueError):
            load("../banking")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "elliptic.json").write_text("{}")
            (root / "manifest.json").write_text(json.dumps({"sha256": {"elliptic.json": "0" * 64}}))
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                load("elliptic", root)
            (root / "training-evidence-manifest.json").write_text(
                json.dumps({"sha256": {"secret.joblib": "0" * 64}})
            )
            with self.assertRaisesRegex(ValueError, "unexpected evidence"):
                verify_artifact(root, "training-evidence-manifest.json")

    def test_pr_points_measured_bounded_and_no_threshold_or_record_leak(self):
        y = np.tile([0, 1], 500)
        scores = np.linspace(0.001, 0.999, 1000)
        curve = pr_curve(y, scores)
        self.assertLessEqual(len(curve["points"]), 101)
        self.assertEqual(curve["rows"], 1000)
        self.assertEqual(curve["positive"], 500)
        p, r, _ = precision_recall_curve(y, scores)
        for point in curve["points"]:
            self.assertEqual(set(point), {"precision", "recall"})
            self.assertTrue(
                any(a == point["precision"] and b == point["recall"] for a, b in zip(p, r))
            )
        self.assertFalse({"scores", "thresholds", "entity_id"} & set(curve))
        with self.assertRaises(ValueError):
            pr_curve(np.zeros(2), np.ones(2))

    def test_graphs_are_bounded_generated_domains_and_directed(self):
        for domain in ("elliptic", "banking"):
            nodes, edges = example(domain, 40)
            ids = {n["id"] for n in nodes}
            self.assertTrue(all(e["source"] in ids and e["target"] in ids for e in edges))
            chart, count = figure(nodes, edges, 49, nodes[0]["id"])
            self.assertGreaterEqual(count, 0)
            self.assertLessEqual(len(chart.layout.annotations), 150)
            self.assertNotIn("fraud", json.dumps(nodes))
        with self.assertRaises(ValueError):
            example("elliptic", 10000)

    def test_benchmarks_are_measured_single_machine_and_private_graph_is_domain_checked(self):
        bench = load_benchmarks()
        self.assertEqual(bench["configuration"]["master"], "local[2]")
        self.assertFalse(bench["configuration"]["distributed_multi_worker_verified"])
        self.assertEqual(len(bench["measurements"]), 6)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "nodes.csv").write_text("id,step,group\na,1,0\nb,1,0\n")
            (root / "edges.csv").write_text("source,target,step\na,b,1\na,b,2\n")
            manifest = {
                "domain": "elliptic",
                "dataset_kind": "original_elliptic_release",
                "sha256": {
                    n: hashlib.sha256((root / n).read_bytes()).hexdigest()
                    for n in ("nodes.csv", "edges.csv")
                },
            }
            (root / "graph.json").write_text(json.dumps(manifest))
            nodes, edges = private_graph(
                root, "elliptic"
            )  # generated contract fixture, not real data
            self.assertEqual((len(nodes), len(edges)), (2, 2))
            with self.assertRaisesRegex(ValueError, "domain mismatch"):
                private_graph(root, "banking")
            (root / "edges.csv").write_text("tampered")
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                private_graph(root, "elliptic")

    def test_http_server_health_and_html_in_cloud(self):
        with socket.socket() as available:
            available.bind(("127.0.0.1", 0))
            port = available.getsockname()[1]
        with tempfile.TemporaryFile(mode="w+") as log:
            process = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "streamlit",
                    "run",
                    str(ROOT / "dashboard/app.py"),
                    "--server.address=127.0.0.1",
                    f"--server.port={port}",
                    "--server.headless=true",
                    "--browser.gatherUsageStats=false",
                ],
                cwd=ROOT,
                stdout=log,
                stderr=log,
            )
            try:
                for _ in range(40):
                    try:
                        with urllib.request.urlopen(
                            f"http://127.0.0.1:{port}/_stcore/health", timeout=1
                        ) as reply:
                            self.assertEqual(reply.read(), b"ok")
                        break
                    except OSError:
                        if process.poll() is not None:
                            self.fail("Streamlit server exited before readiness")
                        time.sleep(0.25)
                else:
                    self.fail("Streamlit health timeout")
                with urllib.request.urlopen(f"http://127.0.0.1:{port}", timeout=2) as reply:
                    self.assertIn("streamlit", reply.read().decode().lower())
            finally:
                process.terminate()
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=5)
