"""Reproduce hidden exceptions and interrupted storage without external datasets."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from mmd_fraud.cloud_config import validate_config, validate_paths
from mmd_fraud.diagnostics import failure_details, record_failure, redact, tail
from mmd_fraud.automation import run_workflow
from test_automation import generated_source

REPO = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("mmds_cloud_entry", REPO / "scripts/run_cloud.py")
entry = importlib.util.module_from_spec(spec)
spec.loader.exec_module(entry)


class DiagnosticTests(unittest.TestCase):
    def test_default_config_and_invalid_types(self):
        config = json.loads((REPO / "configs/cloud-pipeline.json").read_text())
        self.assertEqual(validate_config(config), config)
        for bad in ({"seed": True}, {"seed": -1}, {"train_end": "34"},
                    {"validation_end": 34}, {"sample_per_step": 201},
                    {"source": "kaggle"}, {"source": "existing"}, {"extra": 1}):
            with self.assertRaises(ValueError):
                validate_config(bad)

    def test_setup_error_is_not_masked_by_previous_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            record_failure(root, ValueError("OLD DEPENDENCY FAILURE"), "dependencies")
            result = failure_details(root, RuntimeError("NEW DRIVE AUTH ERROR"), prefer_recorded=False)
            self.assertIn("NEW DRIVE AUTH ERROR", result)
            self.assertNotIn("OLD DEPENDENCY FAILURE", result)

    def test_paths_reject_unmounted_drive_overlap_and_write_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch("os.path.ismount", return_value=False):
                with self.assertRaisesRegex(ValueError, "not mounted"):
                    validate_paths(root, Path("/content/drive/MyDrive/MMDS/automated"))
            with self.assertRaisesRegex(ValueError, "separate"):
                validate_paths(root, root / "storage")
            with patch("tempfile.TemporaryFile", side_effect=PermissionError("write denied")):
                with self.assertRaisesRegex(OSError, "not writable"):
                    validate_paths(root, None)

    def test_mounted_default_drive_path_probe(self):
        with tempfile.TemporaryDirectory() as temp, patch("os.path.ismount", return_value=True), \
                patch.object(Path, "is_dir", return_value=True), patch.object(Path, "mkdir"), \
                patch("tempfile.TemporaryFile") as probe, patch("os.fsync"):
            probe.return_value.__enter__.return_value.read.return_value = b"MMDS write probe"
            destination = Path("/content/drive/MyDrive/MMDS/automated")
            _, storage = validate_paths(Path(temp), destination)
            self.assertEqual(storage, destination)
            self.assertEqual(probe.call_args.kwargs["dir"], destination)

    def test_notebook_reports_setup_error_without_generic_exception(self):
        notebook = json.loads((REPO / "notebooks/MMDS_Cloud_Pipeline.ipynb").read_text())
        source = "".join(next(c for c in notebook["cells"] if c["cell_type"] == "code")["source"])
        fake_colab = types.ModuleType("google.colab")
        fake_colab.drive = types.SimpleNamespace(mount=lambda path: None)
        fake_display = types.ModuleType("IPython.display")
        fake_display.Markdown = lambda value: value
        fake_display.display = lambda value: None
        error = subprocess.CalledProcessError(1, ["git", "clone"], stderr="ACTUAL GIT NETWORK FAILURE")
        namespace = {}
        with patch.dict(sys.modules, {"google": types.ModuleType("google"),
                                     "google.colab": fake_colab,
                                     "IPython": types.ModuleType("IPython"),
                                     "IPython.display": fake_display}), patch.dict(os.environ), \
                patch.object(Path, "is_dir", return_value=True), \
                patch.object(Path, "exists", return_value=False), \
                patch("subprocess.run", side_effect=error), \
                contextlib.redirect_stdout(io.StringIO()) as display:
            exec(compile(source, "notebook", "exec"), namespace)
        self.assertFalse(namespace["pipeline_succeeded"])
        self.assertIn("ACTUAL GIT NETWORK FAILURE", display.getvalue())
        self.assertIn("Pipeline status: FAILED", display.getvalue())

    def test_bounded_tails_redaction_and_execution_log(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run = root / "runs/current"
            run.mkdir(parents=True)
            (root / "active-run.txt").write_text(str(run))
            (root / "bootstrap.log").write_text("x" * 1000000 + "\nFINAL PIP ERROR token=secret\n")
            (run / "execution.log").write_text("FAILED: graph validation error\n")
            result = failure_details(root, RuntimeError("worker failed"))
            self.assertIn("FINAL PIP ERROR", result)
            self.assertIn("graph validation error", result)
            self.assertIn("log unavailable", result)
            self.assertNotIn("token=secret", result)
            self.assertLess(len(tail(root / "bootstrap.log")), 8100)
            self.assertNotIn("sensitive", redact("Authorization: Bearer sensitive"))
            (root / "failure.json").write_text("[]")
            self.assertIn("real current cause", failure_details(root, ValueError("real current cause")))

    def test_pip_failure_is_actionable_and_logged(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            def failed(command, **kwargs):
                if command[:2] == ["java", "-version"]:
                    return subprocess.CompletedProcess(command, 0, "", 'openjdk version "21.0.1"')
                kwargs["stderr"].write("ERROR: dependency wheel unavailable\n")
                raise subprocess.CalledProcessError(1, command)
            with patch.object(entry, "require_cloud"), patch.object(entry.venv, "create"), \
                    patch.object(entry.subprocess, "run", side_effect=failed), \
                    contextlib.redirect_stderr(io.StringIO()) as display:
                code = entry.main(["--workspace", str(root)])
            self.assertEqual(code, 1)
            self.assertIn("dependency wheel unavailable", display.getvalue())
            self.assertEqual(json.loads((root / "failure.json").read_text())["stage"], "dependencies")

    def test_worker_traceback_remains_in_runtime_log(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(entry, "require_cloud"), \
                    patch.object(entry.subprocess, "run", return_value=subprocess.CompletedProcess(
                        [], 0, "", 'openjdk version "21.0.1"')), \
                    patch("mmd_fraud.automation.run_workflow", side_effect=ValueError("ROOT SPARK ERROR")), \
                    contextlib.redirect_stderr(io.StringIO()) as display:
                code = entry.main(["--workspace", str(root), "--worker"])
            self.assertEqual(code, 1)
            self.assertIn("ValueError: ROOT SPARK ERROR", (root / "runtime.log").read_text())
            self.assertEqual(display.getvalue(), "")  # The parent/notebook presents one summary.
            self.assertFalse((root / "latest-report.txt").exists())

    def test_config_failure_happens_before_pip(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            bad = root / "bad.json"
            bad.write_text('{"train_end": "34"}')
            with patch.object(entry, "require_cloud"), patch.object(entry.subprocess, "run") as call, \
                    contextlib.redirect_stderr(io.StringIO()) as display:
                self.assertEqual(entry.main(["--workspace", str(root), "--config", str(bad)]), 1)
            call.assert_not_called()
            self.assertIn("train_end must be an integer", display.getvalue())

    def test_authorization_instruction_and_no_retry(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            error = HTTPError("https://data.pyg.org/datasets/elliptic/file", 403, "denied", {}, None)
            with patch("mmd_fraud.automation.cloud_runtime", return_value="colab"), \
                    patch("mmd_fraud.automation.acquire", side_effect=error) as fetch:
                with self.assertRaises(HTTPError):
                    run_workflow(REPO, root, {"source": "pyg"}, run_tests=False)
            self.assertEqual(fetch.call_count, 1)
            status = json.loads((root / "failure.json").read_text())
            self.assertEqual(status["stage"], "acquisition")
            self.assertIn("official Elliptic Kaggle release", status["instruction"])

    def test_preprocessing_failure_preserves_root_and_incomplete_remote_resumes(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            raw = root / "fixture"
            generated_source(raw)
            config = {"source": "generated_test_fixture", "input_directory": str(raw)}
            for attempt in range(2):
                with patch("mmd_fraud.spark.pipeline.run", side_effect=ValueError("bad source schema")) as run:
                    with self.assertRaisesRegex(ValueError, "bad source schema"):
                        run_workflow(REPO, root / "workspace", config, root / "store", run_tests=False)
                self.assertEqual(run.call_count, 1)
                status = json.loads((root / "workspace/failure.json").read_text())
                self.assertEqual(status["stage"], "preprocess")
                # Reproduce interruption before publishing the remote execution.json.
                for manifest in (root / "store/runs").glob("*/execution.json"):
                    manifest.unlink()

    def test_check_failure_exposes_execution_log_without_acquiring_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            real_run = subprocess.run
            def fail(command, **kwargs):
                if command[0] == "git":
                    return real_run(command, **kwargs)
                if command[:2] == ["java", "-version"]:
                    return subprocess.CompletedProcess(command, 0, "", 'openjdk version "21.0.1"')
                kwargs["stderr"].write("UNDERLYING TEST FAILURE: graph schema mismatch\n")
                raise subprocess.CalledProcessError(1, command)
            with patch("mmd_fraud.automation.subprocess.run", side_effect=fail), \
                    patch("mmd_fraud.automation.acquire") as download:
                with self.assertRaisesRegex(RuntimeError, "graph schema mismatch"):
                    run_workflow(REPO, root, {"source": "pyg"})
            download.assert_not_called()
            result = failure_details(root)
            self.assertIn("UNDERLYING TEST FAILURE", result)
            self.assertIn("Stage: checks", result)
