import csv
import importlib.util
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from mmd_fraud.adapters.banking import BankingColumns, load_banking
from mmd_fraud.adapters.elliptic import EllipticConfig, load_elliptic
from mmd_fraud.contracts import Domain, Edge, GraphDataset, Node
from mmd_fraud.features import DegreeFeatures
from mmd_fraud.validation import ValidationError, validate


class EllipticTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = EllipticConfig(self.root)
        self.write("elliptic_txs_features.csv", [["10", 1] + [0.1] * 165,
                                                ["11", 2] + [0.2] * 165])
        self.write("elliptic_txs_classes.csv", [["txId", "class"], ["11", "unknown"], ["10", "1"]])
        self.write("elliptic_txs_edgelist.csv", [["txId1", "txId2"], ["10", "11"]])

    def write(self, name, records):
        with (self.root / name).open("w", newline="") as handle:
            csv.writer(handle).writerows(records)

    def test_id_join_and_unknown_label(self):
        graph = load_elliptic(self.config)
        self.assertEqual([n.label for n in graph.nodes], ["illicit", "unknown"])
        self.assertEqual(len(graph.nodes[0].features), 165)
        self.assertEqual(graph.domain, Domain.BITCOIN)

    def test_future_node_excluded(self):
        records = DegreeFeatures().extract(load_elliptic(self.config), 1)
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0].values["out_degree"], 0)

    def test_bad_width(self):
        self.write("elliptic_txs_features.csv", [["10", 1, 0.1]])
        with self.assertRaises(ValidationError):
            load_elliptic(self.config)

    def test_duplicate_id(self):
        self.write("elliptic_txs_features.csv", [["10", 1] + [0.1] * 165] * 2)
        with self.assertRaises(ValidationError):
            load_elliptic(self.config)

    def test_nonfinite(self):
        self.write("elliptic_txs_features.csv", [["10", 1] + ["nan"] * 165,
                                                ["11", 2] + [0.1] * 165])
        with self.assertRaises(ValidationError):
            load_elliptic(self.config)

    def test_invalid_labels_and_headers(self):
        for label in ("0", "", "fraud"):
            self.write("elliptic_txs_classes.csv", [["txId", "class"], ["10", label]])
            with self.assertRaises(ValidationError):
                load_elliptic(self.config)

    def test_limits(self):
        for config in (replace(self.config, max_rows=1), replace(self.config, max_file_bytes=1)):
            with self.assertRaises(ValidationError):
                load_elliptic(config)

    def test_dangling_endpoint(self):
        self.write("elliptic_txs_edgelist.csv", [["txId1", "txId2"], ["10", "missing"]])
        with self.assertRaises(ValidationError):
            load_elliptic(self.config)

    def test_missing_class(self):
        self.write("elliptic_txs_classes.csv", [["txId", "class"], ["10", "2"]])
        with self.assertRaises(ValidationError):
            load_elliptic(self.config)

    def test_bad_time(self):
        self.write("elliptic_txs_features.csv", [["10", 50] + [0.1] * 165,
                                                ["11", 2] + [0.1] * 165])
        with self.assertRaises(ValidationError):
            load_elliptic(self.config)


class BankingTests(unittest.TestCase):
    def setUp(self):
        self.graph = GraphDataset(Domain.BANKING, (Node("a"), Node("b")),
                                  (Edge("a", "b", "t1", 0, 10.0),
                                   Edge("a", "b", "t2", 2, 20.0)), "simulation_step")

    def test_parallel_edges_and_cutoff(self):
        validate(self.graph)
        extractor = DegreeFeatures()
        self.assertEqual(extractor.extract(self.graph, 0)[0].values["out_degree"], 1)
        self.assertEqual(extractor.extract(self.graph, 2)[0].values["out_degree"], 2)
        self.assertEqual(extractor.extract(self.graph, 2)[0].domain, Domain.BANKING)

    def test_bad_events(self):
        for edge in (Edge("a", "b", "t", 0, -1), Edge("a", "b", "t", -1, 1),
                     Edge("a", "b", None, 0, 1), Edge("a", "x", "t", 0, 1),
                     Edge("a", "b", "t", 0, float("inf"))):
            with self.assertRaises(ValidationError):
                validate(replace(self.graph, edges=(edge,)))

    def test_duplicate_event(self):
        with self.assertRaises(ValidationError):
            validate(replace(self.graph, edges=(self.graph.edges[0],) * 2))

    def test_configurable_csv(self):
        with tempfile.TemporaryDirectory() as directory:
            accounts, events = Path(directory) / "accounts.csv", Path(directory) / "events.csv"
            accounts.write_text("id\na\nb\n")
            events.write_text("transaction_id,source_account,target_account,step,amount\nt,a,b,0,1\n")
            graph = load_banking(accounts, events, BankingColumns(account_id="id"))
            self.assertEqual(graph.edges[0].amount, 1)
            with self.assertRaises(ValidationError):
                load_banking(accounts, events)
            with self.assertRaises(ValidationError):
                load_banking(accounts, events, BankingColumns(account_id="id"), max_rows=0)

    def test_negative_cutoff(self):
        with self.assertRaises(ValueError):
            DegreeFeatures().extract(self.graph, -1)


@unittest.skipUnless(importlib.util.find_spec("pyspark"), "PySpark not installed")
class SparkTests(unittest.TestCase):
    def test_generated_transactions(self):
        from mmd_fraud.spark.smoke import run_smoke
        self.assertEqual(run_smoke(), {"records": 4, "cutoff_step": 2, "source_accounts": 2})
