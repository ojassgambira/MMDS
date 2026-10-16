"""Independent banking provenance, account-day availability and repeatable cloud execution."""

import csv
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pyarrow.parquet as pq

from mmd_fraud.banking_job import execute
from mmd_fraud.data.banking_synthetic import generate
from mmd_fraud.spark.banking_research import graph_snapshots, prepare, TRANSACTION, TEMPORAL
from mmd_fraud.spark.pipeline import session
from mmd_fraud.training.baselines import chronological_split


class BankingTests(unittest.TestCase):
    def test_seeded_generator_reproducible_and_never_official_or_real(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            a = generate(root / "a", 50, 50, 7)
            b = generate(root / "b", 50, 50, 7)
            c = generate(root / "c", 50, 50, 8)
            self.assertEqual(a, b)
            self.assertNotEqual(a["files"], c["files"])
            self.assertFalse(a["official_amlsim_output"])
            self.assertEqual(a["dataset_kind"], "independent_synthetic_banking")
            self.assertEqual(a["events"], 6100)
            with self.assertRaises(ValueError):
                generate(root / "too_big", 1001, 50, 0)
            with self.assertRaises(FileExistsError):
                generate(root / "a", 50, 50, 7)

    def test_graph_multiplicity_direction_and_strict_future_exclusion(self):
        a, audit = graph_snapshots(
            ["a", "b", "c"], ["a", "a", "b"], ["b", "b", "c"], [0, 0, 2], [1, 2, 3]
        )
        rows = {v["entity_id"]: v for v in a.to_pylist()}
        self.assertEqual(rows["a@1"]["historical_out"], 2)
        self.assertEqual(rows["a@1"]["counterparties"], 1)
        self.assertEqual(rows["b@1"]["historical_in"], 2)
        self.assertEqual(rows["c@2"]["historical_in"], 0)
        self.assertEqual(rows["c@3"]["historical_in"], 1)
        self.assertEqual(audit[0]["events"], 2)
        changed, _ = graph_snapshots(
            ["a", "b", "c"], ["a", "a", "c"], ["b", "b", "a"], [0, 0, 2], [1, 2, 3]
        )
        other = {v["entity_id"]: v for v in changed.to_pylist()}
        for name in ("a@1", "b@1", "c@1", "a@2", "b@2", "c@2"):
            self.assertEqual(rows[name], other[name])
        with self.assertRaises(ValueError):
            graph_snapshots(["a"], ["b"], ["a"], [0], [1])

    def test_banking_boundary_is_distinct_from_elliptic_completed_step(self):
        rows = [
            {
                "entity_id": f"{day}-{label}",
                "time_step": day,
                "label": label,
                "feature_cutoff_exclusive": day,
            }
            for day in range(1, 50)
            for label in ("1", "2")
        ]
        self.assertEqual(chronological_split(rows, 34, 39, cutoff_offset=0)["unknown_excluded"], 0)
        with self.assertRaises(ValueError):
            chronological_split(rows, 34, 39)

    def test_full_generated_banking_workflow_resume_and_corruption(self):
        with (
            tempfile.TemporaryDirectory() as tmp,
            patch("mmd_fraud.banking_job.cloud_runtime", return_value="codex_cloud"),
        ):
            root = Path(tmp)
            config = {"accounts": 50, "daily_events": 50, "seeds": [0]}
            output = execute(root, config)
            summary = json.loads((output / "banking-summary.json").read_text())
            self.assertEqual(summary["dataset_kind"], "independent_synthetic_banking")
            self.assertFalse(summary["real_banking_fraud_verified"])
            run = summary["runs"][0]
            self.assertEqual(run["validation"]["events"], 6100)
            self.assertEqual(run["validation"]["account_days"], 2450)
            self.assertEqual(len(run["comparison"]["families"]), 4)
            self.assertEqual(run["comparison"]["cutoff_offset"], 0)
            self.assertIn("sar_positive", run["comparison"]["split_counts"]["test"])
            self.assertNotIn("illicit", json.dumps(run["comparison"]))
            self.assertIn("python", summary["identity"])
            self.assertEqual(
                summary["elliptic_reference"]["baseline"]["confusion_matrix_order"],
                ["licit=0", "illicit=1"],
            )
            self.assertEqual(
                set(p.name for p in output.iterdir()),
                {
                    "banking-summary.json",
                    "banking-report.md",
                    "banking-results.png",
                    "banking-evidence-manifest.json",
                },
            )
            with patch("mmd_fraud.banking_job.prepare", side_effect=AssertionError("reprocessing")):
                restored = execute(root, config)
            self.assertEqual(restored, output)
            raw = output.parent / "seed-0/source/transactions.csv"
            raw.write_text("corrupt")
            with self.assertRaisesRegex(ValueError, "corrupt banking checkpoint"):
                execute(root, config)
            self.assertFalse((root / "result.json").exists())
            state = json.loads((output.parent / "seed-0/state.json").read_text())
            self.assertEqual(state["status"], "failed")


class BankingSparkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.tmp.name)
        cls.spark = session({"driver_memory": "1g", "partitions": 2}, cls.root / "checkpoints")

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()
        cls.tmp.cleanup()

    def test_current_labels_and_future_transactions_cannot_change_predictors(self):
        source = self.root / "source"
        generate(source, 50, 50, 0)
        one = self.root / "one"
        one.mkdir()
        prepare(self.spark, source, one)
        a = pq.ParquetDataset(one / "daily").read().to_pylist()
        path = source / "transactions.csv"
        with path.open() as handle:
            reader = csv.DictReader(handle)
            names = reader.fieldnames
            rows = list(reader)
        for row in rows:
            if row["tran_timestamp"] >= "2017-02-10":  # day 40 and later
                row["base_amt"] = "999999.00"
                row["is_sar"] = "false" if row["is_sar"] == "true" else "true"
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=names)
            writer.writeheader()
            writer.writerows(rows)
        two = self.root / "two"
        two.mkdir()
        prepare(self.spark, source, two)
        b = {r["entity_id"]: r for r in pq.ParquetDataset(two / "daily").read().to_pylist()}
        for row in a:
            if row["time_step"] <= 40:
                np.testing.assert_allclose(
                    [row[c] for c in (*TRANSACTION, *TEMPORAL)],
                    [b[row["entity_id"]][c] for c in (*TRANSACTION, *TEMPORAL)],
                )
        self.assertTrue(
            any(row["label"] != b[row["entity_id"]]["label"] for row in a if row["time_step"] == 40)
        )
        # Conflicting duplicate labels must not silently turn into a duplicated model row.
        with path.open("a", newline="") as handle:
            duplicate = {**rows[0], "is_sar": "false" if rows[0]["is_sar"] == "true" else "true"}
            csv.DictWriter(handle, fieldnames=names).writerow(duplicate)
        bad = self.root / "bad"
        bad.mkdir()
        with self.assertRaisesRegex(ValueError, "conflicting transaction SAR labels"):
            prepare(self.spark, source, bad)

        with path.open("w", newline="") as handle:
            rows[0]["is_sar"] = ""
            writer = csv.DictWriter(handle, fieldnames=names)
            writer.writeheader()
            writer.writerows(rows)
        missing = self.root / "missing-label"
        missing.mkdir()
        with self.assertRaisesRegex(ValueError, "is_sar must explicitly"):
            prepare(self.spark, source, missing)
        with (source / "accounts.csv").open("w", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(["acct_id", "open_dt"])
            writer.writerows([[f"A{i:05}", "20170102"] for i in range(50)])
        future = self.root / "future-account"
        future.mkdir()
        with self.assertRaisesRegex(ValueError, "registry must be known"):
            prepare(self.spark, source, future)
