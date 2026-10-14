"""Dataset-free checks for the Colab handoff and real-data sample boundary."""
import ast
import csv
import json
import tempfile
import unittest
from pathlib import Path

from mmd_fraud.data.acquire import FILES
from mmd_fraud.data.sample import sample_elliptic


class ColabTests(unittest.TestCase):
    def source(self, root):
        source = root / "source"
        source.mkdir()
        rows = [
            [["1", 1] + [0] * 165, ["2", 1] + [0] * 165, ["3", 2] + [0] * 165],
            [["txId", "class"], ["1", "1"], ["2", "2"], ["3", "unknown"]],
            [["txId1", "txId2"], ["1", "3"], ["2", "3"]],
        ]
        for name, records in zip(FILES, rows):
            with (source / name).open("w", newline="") as handle:
                csv.writer(handle).writerows(records)
        return source

    def test_sample_preserves_time_unknown_and_induced_edges(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.source(root)
            destination = root / "sample"
            result = sample_elliptic(source, destination, per_step=1)
            self.assertEqual(result["sample_nodes"], 2)
            self.assertEqual(result["sample_edges_raw"], 1)
            self.assertEqual(result["source_labels"], {"1": 1, "2": 1, "unknown": 1})
            self.assertEqual(result["source_steps"], [1, 2])
            self.assertEqual((destination / FILES[1]).read_text().splitlines(),
                             ["txId,class", "1,1", "3,unknown"])
            self.assertEqual((destination / FILES[2]).read_text().splitlines(),
                             ["txId1,txId2", "1,3"])
            again = sample_elliptic(source, root / "again", per_step=1)
            self.assertEqual(result, again)
            with self.assertRaises(FileExistsError):
                sample_elliptic(source, destination)

    def test_failure_is_atomic_and_limits_are_enforced(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.source(root)
            for kwargs in ({"max_bytes": 1}, {"max_rows": 1}, {"max_sample_edges": 1}):
                with self.assertRaises(ValueError):
                    sample_elliptic(source, root / "sample", **kwargs)
                self.assertFalse((root / "sample").exists())
            (source / FILES[2]).write_text("txId1,txId2\n2,2\n")
            with self.assertRaises(ValueError):
                sample_elliptic(source, root / "sample", per_step=1)
            self.assertEqual(sorted(p.name for p in root.iterdir()), ["source"])

    def test_conflicting_labels_and_orphan_edges_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = self.source(root)
            with (source / FILES[1]).open("a") as handle:
                handle.write("1,2\n")
            with self.assertRaises(ValueError):
                sample_elliptic(source, root / "sample")
            (source / FILES[1]).write_text("txId,class\n1,1\n2,2\n3,unknown\n")
            (source / FILES[2]).write_text("txId1,txId2\n1,999\n")
            with self.assertRaises(ValueError):
                sample_elliptic(source, root / "sample")
            self.assertFalse((root / "sample").exists())

    def test_notebook_is_unexecuted_and_python_cells_parse(self):
        path = Path(__file__).resolve().parents[1] / "notebooks/MMDS_Cloud_Pipeline.ipynb"
        notebook = json.loads(path.read_text())
        self.assertEqual(notebook["nbformat"], 4)
        for cell in notebook["cells"]:
            if cell["cell_type"] == "code":
                self.assertIsNone(cell["execution_count"])
                self.assertEqual(cell["outputs"], [])
                ast.parse("".join(cell["source"]))
