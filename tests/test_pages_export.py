"""Public-only static export, reproducibility and preservation of frozen evidence."""

import copy
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from mmd_fraud.evidence import load

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("pages_export", ROOT / "scripts/export_pages_data.py")
exporter = importlib.util.module_from_spec(spec)
spec.loader.exec_module(exporter)


class PagesExportTests(unittest.TestCase):
    def test_unknown_source_fields_never_enter_public_dto(self):
        source = copy.deepcopy(load("elliptic"))
        source["private_predictions"] = ["DO_NOT_PUBLISH"]
        source["stats"]["labels"]["private"] = "DO_NOT_PUBLISH"
        run = source["runs"][0]
        run["raw_records"] = ["DO_NOT_PUBLISH"]
        run["intervals"]["private"] = {"raw": {"lower_95": "DO_NOT_PUBLISH"}}
        family = next(iter(run["families"].values()))
        family["models"] = "DO_NOT_PUBLISH"
        family["test"]["scores"] = ["DO_NOT_PUBLISH"]
        family["test_curve"]["points"][0]["entity_id"] = "DO_NOT_PUBLISH"
        public = exporter.project(source)
        self.assertNotIn("DO_NOT_PUBLISH", json.dumps(public))
        self.assertEqual(public["runs"][0]["split_counts"], source["runs"][0]["split_counts"])

    def test_publication_is_bounded_and_byte_reproducible(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            a, b = root / "a", root / "b"
            first, second = exporter.export(a), exporter.export(b)
            self.assertEqual(first, second)
            self.assertEqual(set(p.name for p in a.iterdir()), exporter.FILES | {"manifest.json"})
            self.assertTrue(all(p.stat().st_size < 2_000_000 for p in a.iterdir()))
            for domain in ("elliptic", "banking"):
                original = load(domain)
                public = json.loads((a / f"{domain}.json").read_text())
                for old, new in zip(original["runs"], public["runs"]):
                    self.assertEqual(old["selected_family"], new["selected_family"])
                    for family, result in new["families"].items():
                        self.assertEqual(result["test"], old["families"][family]["test"])
                        self.assertEqual(
                            result["test_curve"], old["families"][family]["test_curve"]
                        )
            graphs = json.loads((a / "graphs.json").read_text())
            self.assertTrue(
                all(g["dataset_kind"] == "generated_illustration" for g in graphs.values())
            )
            self.assertEqual(len(graphs["elliptic"]["nodes"]), 80)
            (a / "banking.json").write_text("{}")
            with self.assertRaisesRegex(ValueError, "invalid static"):
                exporter.verify(a)

    def test_unexpected_files_and_symlinks_are_refused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            private = root / "private.joblib"
            private.write_text("private")
            with self.assertRaisesRegex(ValueError, "unexpected"):
                exporter.export(root)
            private.unlink()
            target = root / "elliptic.json"
            target.symlink_to(ROOT / "README.md")
            with self.assertRaisesRegex(ValueError, "unexpected"):
                exporter.export(root)
