"""Generated data only: leakage, failure, checkpoint and full workflow checks."""
import csv
import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

import joblib
import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from mmd_fraud.automation import archive, inventory, run_workflow, verified
from mmd_fraud.data.acquire import FILES
from mmd_fraud.spark.causal import FEATURES
from mmd_fraud.training.baselines import chronological_split, evaluate, train


def generated_source(directory):
    directory.mkdir()
    features, classes, edges = [], [["txId", "class"]], [["txId1", "txId2"]]
    for step in range(1, 50):
        for offset, label in enumerate(("1", "2", "2", "unknown")):
            txid = (step - 1) * 4 + offset + 1
            features.append([str(txid), step, *([0.0] * 165)])
            classes.append([str(txid), label])
            if txid > 1:
                edges.append([str(txid - 1), str(txid)])
    for name, rows in zip(FILES, (features, classes, edges)):
        with (directory / name).open("w", newline="") as handle:
            csv.writer(handle).writerows(rows)


def generated_features():
    return [{"entity_id": f"{step}-{label}", "time_step": step, "label": label,
             "feature_cutoff_exclusive": step + 1,
             **{name: (step % 3 + int(label == "1")) for name in FEATURES}}
            for step in range(1, 50) for label in ("1", "2", "unknown")]


class AutomationTests(unittest.TestCase):
    def test_chronological_unknown_and_boundary_guards(self):
        rows = generated_features()
        result = chronological_split(rows, 34, 39)
        self.assertEqual(result["unknown_excluded"], 49)
        self.assertEqual(len(result["groups"]["train"]), 68)
        self.assertEqual(min(r["time_step"] for r in result["groups"]["test"]), 40)
        with self.assertRaises(ValueError):
            chronological_split(rows + rows[:1], 34, 39)
        rows[0]["feature_cutoff_exclusive"] = 50
        with self.assertRaises(ValueError):
            chronological_split(rows, 34, 39)
        with self.assertRaises(ValueError):
            chronological_split([r for r in generated_features() if r["label"] != "1"], 34, 39)

    def test_known_metrics(self):
        result = evaluate(np.array([0, 0, 1, 1]), np.array([0.1, 0.6, 0.4, 0.9]))
        self.assertEqual(result["confusion_matrix"], [[1, 1], [1, 1]])
        self.assertEqual(result["precision"], 0.5)
        self.assertEqual(result["recall"], 0.5)
        self.assertAlmostEqual(result["pr_auc_average_precision"], 5 / 6)

    def test_training_scaler_and_selection_do_not_see_test(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rows = generated_features()
            pq.write_table(pa.Table.from_pylist(rows), root / "features.parquet")
            first = train(root / "features.parquet", root / "first")
            model = joblib.load(root / "first/logistic_regression.joblib")
            expected = np.mean([[r[c] for c in FEATURES] for r in rows
                                if r["time_step"] <= 34 and r["label"] != "unknown"], axis=0)
            np.testing.assert_allclose(model[0].mean_, expected)
            for row in rows:
                if row["time_step"] >= 40:
                    for name in FEATURES:
                        row[name] += 10000
            pq.write_table(pa.Table.from_pylist(rows), root / "changed.parquet")
            second = train(root / "changed.parquet", root / "second")
            self.assertEqual(first["selected_model"], second["selected_model"])
            for name in first["models"]:
                self.assertEqual(first["models"][name]["validation"],
                                 second["models"][name]["validation"])

    def test_archive_detects_corruption(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source"
            source.mkdir()
            (source / "value").write_text("one")
            archive(source, root / "store")
            self.assertTrue(verified(root / "store", inventory(source)))
            (root / "store/value").write_text("two")
            with self.assertRaises(ValueError):
                archive(source, root / "store")

    def test_failed_acquisition_records_failure_without_retry(self):
        with tempfile.TemporaryDirectory() as temp, patch(
                "mmd_fraud.automation.cloud_runtime", return_value="colab"), patch(
                "mmd_fraud.automation.acquire", side_effect=OSError("source unavailable")) as fetch:
            root = Path(temp)
            with self.assertRaises(OSError):
                run_workflow(Path(__file__).resolve().parents[1], root,
                             {"source": "pyg"}, run_tests=False)
            self.assertEqual(fetch.call_count, 1)
            state = json.loads(next(root.glob("runs/*/execution.json")).read_text())
            self.assertEqual(state["status"], "failed")
            self.assertNotIn("models", state["stages"])

    def test_full_generated_workflow_and_restore(self):
        with tempfile.TemporaryDirectory() as temp, patch.dict(os.environ, {
                "SPARK_LOCAL_IP": "127.0.0.1"}):
            root = Path(temp)
            raw = root / "generated"
            generated_source(raw)
            config = {"source": "generated_test_fixture", "input_directory": str(raw),
                      "data_mode": "full", "train_end": 34, "validation_end": 39, "experiments": True, "research": True}
            repo = Path(__file__).resolve().parents[1]
            with patch("mmd_fraud.automation.archive", side_effect=OSError("Drive quota exhausted")):
                with self.assertRaisesRegex(OSError, "Drive quota exhausted"):
                    run_workflow(repo, root / "workspace", config, root / "store", run_tests=False)
            storage_failure = json.loads((root / "workspace/failure.json").read_text())
            self.assertEqual(storage_failure["stage"], "storage")
            with patch("mmd_fraud.training.baselines.train", side_effect=ValueError("training blocked")):
                with self.assertRaisesRegex(ValueError, "training blocked"):
                    run_workflow(repo, root / "workspace", config, root / "store", run_tests=False)
            failure = json.loads((root / "workspace/failure.json").read_text())
            self.assertEqual(failure["stage"], "models")
            with patch("mmd_fraud.spark.pipeline.run", side_effect=AssertionError("reprocessed checkpoint")):
                output = run_workflow(repo, root / "workspace", config, root / "store", run_tests=False)
            self.assertFalse((root / "workspace/failure.json").exists())
            state = json.loads((output / "execution.json").read_text())
            self.assertEqual(state["status"], "success")
            self.assertEqual(state["dataset_kind"], "generated_test_fixture")
            self.assertEqual(json.loads((output / "preprocess/run.json").read_text())
                             ["validation"]["nodes"], 196)
            # Only generated-fixture reports may be exported from this test.
            evidence = os.environ.get("MMDS_TEST_REPORT_DIRECTORY")
            if evidence:
                evidence = Path(evidence)
                evidence.mkdir(parents=True, exist_ok=True)
                for name in ("report.md", "execution.json"):
                    shutil.copy2(output / name, evidence / f"generated-{name}")
            comparison = json.loads((output / "comparison/comparison.json").read_text())
            self.assertEqual(set(comparison["families"]),
                             {"transaction_only", "graph_only", "temporal", "combined"})
            self.assertEqual(comparison["unknown_excluded"], 49)
            research = json.loads((output / "research/research.json").read_text())
            self.assertEqual(len(research["families"]), 8)
            self.assertEqual(research["split_counts"], comparison["split_counts"])
            self.assertTrue((output / "research/research-results.png").is_file())
            research_hashes = inventory(output / "research")
            model_hashes = inventory(output / "models")
            shutil.rmtree(root / "workspace")
            restored = run_workflow(repo, root / "workspace", config,
                                    root / "store", run_tests=False)
            self.assertEqual(inventory(restored / "models"), model_hashes)
            self.assertEqual(inventory(restored / "research"), research_hashes)
            self.assertTrue((restored / "report.md").is_file())
            (restored / "models/metrics.json").write_text("corruption")
            with self.assertRaises(ValueError):
                run_workflow(repo, root / "workspace", config, root / "store", run_tests=False)
