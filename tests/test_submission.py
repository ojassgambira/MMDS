"""Submission evidence, cloud routing and security regressions; no external datasets."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from mmd_fraud.diagnostics import redact
from mmd_fraud.evidence import ROOT, load, validate_metrics, validate_curve
from mmd_fraud.dashboard_graph import private_graph, figure

spec = importlib.util.spec_from_file_location(
    "submission_audit", ROOT / "scripts/audit_submission.py"
)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class SubmissionTests(unittest.TestCase):
    def test_submission_package_matches_evidence_and_links(self):
        result = audit.audit()
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["measured_curves"], 23)
        self.assertEqual(result["measured_spark_sizes"], 6)
        self.assertFalse(result["public_hosting_verified"])
        self.assertFalse(result["colab_execution_verified"])

    def test_missing_and_escaping_document_links_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "dashboard").mkdir()
            (root / "docs").mkdir()
            (root / "dashboard/README.md").write_text("")
            (root / "README.md").write_text("[bad](docs/missing.md) [escape](../README.md)")
            self.assertEqual(len(audit.broken_links(root)), 2)

    def metrics(self, domain="elliptic"):
        return copy.deepcopy(next(iter(load(domain)["runs"][0]["families"].values()))["test"])

    def test_invalid_matrix_and_target_semantics_fail(self):
        for bad in ([[1, -1], [2, 3]], [[True, 1], [2, 3]], [[1], [2]], [[1.0, 1], [2, 3]]):
            metrics = self.metrics()
            metrics["confusion_matrix"] = bad
            with self.assertRaises(ValueError):
                validate_metrics(metrics, "elliptic")
        metrics = self.metrics("banking")
        metrics["confusion_matrix_order"] = ["licit=0", "illicit=1"]
        with self.assertRaisesRegex(ValueError, "target/order"):
            validate_metrics(metrics, "banking")

    def test_wrong_scores_nan_and_positive_counts_fail(self):
        for key, bad in [
            ("precision", 0.12345),
            ("f1", float("nan")),
            ("pr_auc_average_precision", float("inf")),
            ("recall", True),
            ("false_positive_rate", -0.1),
            ("illicit", 1),
        ]:
            metrics = self.metrics()
            metrics[key] = bad
            with self.assertRaises(ValueError):
                validate_metrics(metrics, "elliptic")

    def test_rehashed_but_inconsistent_snapshot_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            data = load("elliptic")
            next(iter(data["runs"][0]["families"].values()))["test"]["recall"] = 0.12345
            path = root / "elliptic.json"
            path.write_text(json.dumps(data))
            (root / "manifest.json").write_text(
                json.dumps({"sha256": {path.name: hashlib.sha256(path.read_bytes()).hexdigest()}})
            )
            with self.assertRaisesRegex(ValueError, "inconsistent"):
                load("elliptic", root)

    def test_curves_reject_wrong_populations_order_and_values(self):
        item = next(iter(load("elliptic")["runs"][0]["families"].values()))
        for mutate in [
            lambda c: c.update(rows=1),
            lambda c: c.update(positive=1),
            lambda c: c.update(points=[]),
            lambda c: c["points"][0].update(precision=float("nan")),
            lambda c: c.update(
                points=[{"precision": 0.5, "recall": 0.1}, {"precision": 0.5, "recall": 0.9}]
            ),
        ]:
            curve = copy.deepcopy(item["test_curve"])
            mutate(curve)
            with self.assertRaises(ValueError):
                validate_curve(curve, item["test"], "elliptic")

    def test_json_credentials_and_space_containing_tokens_are_redacted(self):
        for key in (
            "token",
            "api_key",
            "authorization",
            "password",
            "kaggle_key",
            "access_token",
            "refresh_token",
        ):
            original = json.dumps({key: "sensitive bearer value", "message": "ACTUAL ERROR"})
            result = redact(original)
            self.assertNotIn("sensitive", result)
            self.assertIn("ACTUAL ERROR", result)
        self.assertNotIn("hidden", redact("{'token': 'hidden value'}"))

    def test_private_graph_provenance_and_endpoint_availability(self):
        nodes = [{"id": "a", "step": 1, "group": 0}, {"id": "b", "step": 2, "group": 0}]
        edges = [{"source": "a", "target": "b", "step": 2}]
        chart, _ = figure(nodes, edges, provenance="Operator-provisioned; source unverified")
        self.assertIn("source unverified", chart.data[1].hovertemplate)
        self.assertNotIn("Generated example", chart.data[1].hovertemplate)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "nodes.csv").write_text("id,step,group\na,1,0\nb,2,0\n")
            (root / "edges.csv").write_text("source,target,step\na,b,1\n")
            (root / "graph.json").write_text(
                json.dumps(
                    {
                        "domain": "elliptic",
                        "dataset_kind": "original_elliptic_release",
                        "sha256": {
                            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in root.glob("*.csv")
                        },
                    }
                )
            )
            with self.assertRaisesRegex(ValueError, "precedes endpoint"):
                private_graph(root, "elliptic")
