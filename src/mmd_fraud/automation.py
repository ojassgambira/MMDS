"""Cloud-only bounded acquisition → Spark → baselines → resumable evidence."""
import hashlib
import importlib.metadata
import importlib.util
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from mmd_fraud.data.acquire import FILES, acquire, outside_repo, sha256, verify_acquisition
from mmd_fraud.cloud_config import validate_config, validate_paths
from mmd_fraud.diagnostics import record_failure, redact, tail
from mmd_fraud.runtime import is_colab


def cloud_runtime() -> str:
    if is_colab():
        return "colab"
    if Path("/etc/codex/network-policy.json").is_file():
        return "codex_cloud"
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return "github_ci"
    raise RuntimeError("Execute only in Codex Cloud, Google Colab or GitHub CI; no device workloads")


def write_json(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")
    temporary.replace(path)


def inventory(directory: Path) -> dict:
    return {str(p.relative_to(directory)): sha256(p)
            for p in sorted(directory.rglob("*")) if p.is_file()}


def verified(directory: Path, hashes: dict) -> bool:
    return directory.is_dir() and inventory(directory) == hashes and bool(hashes)


def archive(source: Path, destination: Path) -> None:
    """Publish verified immutable snapshots; a partial copy never counts as complete."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    hashes = inventory(source)
    if destination.exists():
        if not verified(destination, hashes):
            raise ValueError("existing cloud checkpoint differs; refusing overwrite")
        return
    with tempfile.TemporaryDirectory(dir=destination.parent, prefix="mmds-copy-") as temp:
        stage = Path(temp) / "payload"
        shutil.copytree(source, stage)
        if not verified(stage, hashes):
            raise ValueError("cloud checkpoint copy hash mismatch")
        stage.rename(destination)


def report(directory: Path, state: dict) -> None:
    lines = ["# MMDS cloud execution report", "", f"Status: **{state['status']}**",
             f"Dataset kind: `{state['dataset_kind']}`", f"Runtime: `{state['runtime']}`",
             f"Code commit: `{state['git_commit']}`", "",
             "This is a measured run, not a claim of Colab verification from another runtime.",
             "Anonymous publisher neighborhood aggregates are excluded. Historical label context",
             "uses only strictly earlier training labels when research is enabled. Unknown labels",
             "are excluded from supervised fitting and evaluation. Features are available",
             "after each source step completes; same-step information is included. The label",
             "availability assumption is offline; live availability is unverified.", "",
             "## Stages", "", "| Stage | Seconds | Checkpoint |",
             "| --- | ---: | --- |"]
    for name, stage in state["stages"].items():
        lines.append(f"| {name} | {stage['seconds']:.3f} | hash-verified |")
    if state.get("acquisition"):
        item = state["acquisition"]
        lines.append(f"| acquisition + integrity verification | {item['seconds']:.3f} | "
                     f"{'private cache' if item['cached'] else 'new acquisition'} |")
    if state.get("provenance"):
        lines += ["", f"Source: `{state['provenance']['source']}`."]
        if "elapsed_seconds" in state["provenance"]:
            lines.append(f"Original acquisition seconds: {state['provenance']['elapsed_seconds']:.3f} "
                         "(cached acquisitions are not repeated).")
    if (directory / "preprocess/run.json").exists():
        run = json.loads((directory / "preprocess/run.json").read_text())
        lines += ["", "## Data validation", "", "```json",
                  json.dumps(run.get("validation", {}), indent=2), "```"]
    if (directory / "models/metrics.json").exists():
        metrics = json.loads((directory / "models/metrics.json").read_text())
        lines += ["", "## Baseline evaluation", "",
                  f"Train steps 1–{metrics['train_end']}; validation "
                  f"{metrics['train_end'] + 1}–{metrics['validation_end']}; test "
                  f"{metrics['validation_end'] + 1}–49.",
                  f"Unknown labels excluded: {metrics['unknown_excluded']}.",
                  f"Selected on validation average precision: `{metrics['selected_model']}`.",
                  "Threshold fixed at 0.5; PR-AUC is average precision (not trapezoidal area).",
                  "Confusion matrices use rows=true, columns=predicted, order [licit, illicit].",
                  "", "| Model | Period | Precision | Recall | F1 | PR-AUC (AP) | FPR | Matrix |",
                  "| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |"]
        for name, periods in metrics["models"].items():
            for period, m in periods.items():
                lines.append(f"| {name} | {period} | {m['precision']:.4f} | {m['recall']:.4f} "
                             f"| {m['f1']:.4f} | {m['pr_auc_average_precision']:.4f} "
                             f"| {m['false_positive_rate']:.4f} | {m['confusion_matrix']} |")
        lines += ["", "### Split counts", "", "```json",
                  json.dumps(metrics["split_counts"], indent=2), "```"]
    if state.get("error"):
        lines += ["", "## Failure", "", state["error"]]
    lines += ["", "## Limits", "", "Small samples are induced subgraphs, not population estimates.",
              "Free CPU timing is not multi-machine speedup. Dataset/model artifacts stay private.",
              "Logs: `execution.log`; versions/configuration/checkpoint hashes: `execution.json`.",
              "A completed checkpoint resumes only with matching code, configuration and inputs."]
    (directory / "report.md").write_text("\n".join(lines) + "\n")


def run_workflow(repo: Path, workspace: Path, config: dict, storage: Path | None = None,
                 run_tests: bool = True) -> Path:
    runtime = cloud_runtime()
    repo = repo.resolve()
    config = validate_config(config)
    workspace, storage = validate_paths(workspace, storage)
    source_mode = config.get("source", "pyg")
    if source_mode not in {"pyg", "existing", "generated_test_fixture"}:
        raise ValueError("unsupported source")
    if config.get("data_mode", "full") not in {"full", "sample"}:
        raise ValueError("unsupported data mode")
    if config.get("master", "local[2]") != "local[2]":
        raise ValueError("initial baselines are limited to two cloud CPU workers")
    train_end, validation_end = config.get("train_end", 34), config.get("validation_end", 39)
    if not (isinstance(train_end, int) and isinstance(validation_end, int)
            and 1 <= train_end < validation_end < 49):
        raise ValueError("invalid chronological split boundaries")
    workspace.mkdir(parents=True, exist_ok=True)
    dependencies = {d.metadata["Name"]: d.version for d in importlib.metadata.distributions()}
    identity = {"config": config, "git_commit": subprocess.check_output(
        ["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip(),
        "git_dirty": bool(subprocess.check_output(
            ["git", "-C", str(repo), "status", "--porcelain"], text=True).strip()),
        "python": platform.python_version(), "dependencies": dependencies}
    # Dirty development trees also need a code fingerprint to prevent stale resumption.
    code = [p for folder in ("src", "scripts", "tests", "configs")
            for p in (repo / folder).rglob("*") if p.suffix in {".py", ".json"}]
    identity["code_hashes"] = {str(p.relative_to(repo)): sha256(p) for p in sorted(code)}
    if source_mode != "pyg":
        raw = outside_repo(Path(config["input_directory"]))
        if sum((raw / n).stat().st_size for n in FILES) > config["max_expanded_bytes"]:
            raise ValueError("provided source exceeds configured expanded byte budget")
        identity["provided_inputs"] = {n: sha256(raw / n) for n in FILES}
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()[:20]
    directory = workspace / "runs" / key
    remote = storage / "runs" / key if storage else None
    if remote and (remote / "execution.json").is_file():
        saved = json.loads((remote / "execution.json").read_text())
        for name, stage in saved["stages"].items():
            if not verified(remote / name, stage["hashes"]):
                raise ValueError("corrupt stored checkpoint")
        if not directory.exists():
            shutil.copytree(remote, directory)
    directory.mkdir(parents=True, exist_ok=True)
    (workspace / "active-run.txt").write_text(str(directory))
    state_file = directory / "execution.json"
    state = json.loads(state_file.read_text()) if state_file.exists() else {
        **identity, "runtime": runtime, "dataset_kind":
        "generated_test_fixture" if source_mode == "generated_test_fixture" else
        "real_elliptic_induced_sample" if config.get("data_mode") == "sample" else
        "original_elliptic_release", "stages": {}, "status": "running"}
    state["runtime"] = runtime
    state.setdefault("started_utc", time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))
    state["java_version"] = subprocess.run(
        ["java", "-version"], capture_output=True, text=True, check=True).stderr.strip()
    state["status"] = "running"
    state["active_stage"] = "storage"
    state.pop("error", None)
    env = {**os.environ, "SPARK_LOCAL_IP": "127.0.0.1", "PYSPARK_PYTHON": sys.executable,
           "PYTHONPATH": str(repo / "src"), "OMP_NUM_THREADS": "2",
           "OPENBLAS_NUM_THREADS": "2", "PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
    def save():
        for name in ("bootstrap.log", "runtime.log"):
            if (workspace / name).exists():
                shutil.copy2(workspace / name, directory / name)
        write_json(state_file, state)
        report(directory, state)
        if remote:
            try:
                remote.mkdir(parents=True, exist_ok=True)
                committed = (json.loads((remote / "execution.json").read_text())["stages"]
                             if (remote / "execution.json").is_file() else {})
                for name, stage_info in state["stages"].items():
                    target = remote / name
                    if (target.exists() and name not in committed
                            and not verified(target, stage_info["hashes"])):
                        # A stage copy without a published manifest was never committed.
                        shutil.rmtree(target)
                    archive(directory / name, target)
                for name in ("report.md", "execution.log", "bootstrap.log", "runtime.log"):
                    if (directory / name).exists():
                        shutil.copy2(directory / name, remote / name)
                write_json(remote / "execution.json", state)
            except Exception:
                state["active_stage"] = "storage"
                raise
    def command(args):
        with (directory / "execution.log").open("a") as log:
            log.write(json.dumps(args) + "\n")
            log.flush()
            try:
                subprocess.run(args, cwd=repo, env=env, stdout=log, stderr=log,
                               check=True, timeout=1200)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
                log.flush()
                raise RuntimeError(f"Check command failed: {args}\n{tail(directory / 'execution.log')}") from exc
    def stage(name, action):
        state["active_stage"] = name
        if name in state["stages"]:
            if not verified(directory / name, state["stages"][name]["hashes"]):
                raise ValueError(f"corrupt {name} checkpoint; use a fresh workspace")
            print(f"Reusing verified checkpoint: {name}", flush=True)
            return
        target = directory / name
        if target.exists():
            # Only incomplete stage directories inside this generated run are replaceable.
            shutil.rmtree(target)
        print(f"Running stage: {name}", flush=True)
        began = time.monotonic()
        # Publish active stage locally before work: process termination may bypass except.
        write_json(state_file, state)
        try:
            action(target)
        except Exception:
            state["failed_stage_seconds"] = time.monotonic() - began
            raise
        state.pop("failed_stage_seconds", None)
        state["stages"][name] = {"seconds": time.monotonic() - began,
                                 "hashes": inventory(target)}
        save()
    try:
        save()
        if run_tests:
            state.pop("tests", None)
            def checks(target):
                target.mkdir()
                for args in ([sys.executable, "-m", "ruff", "check", "."],
                             [sys.executable, "-m", "pytest", "-q"],
                             [sys.executable, "scripts/spark_smoke.py"]):
                    command(args)
                write_json(target / "checks.json", {"status": "passed",
                           "commands": ["ruff check .", "pytest -q", "spark_smoke.py"]})
            stage("checks", checks)
        else:
            state["tests"] = "skipped explicitly by caller; development integration only"
        if source_mode == "pyg":
            state["active_stage"] = "acquisition"
            acquisition_started = time.monotonic()
            raw = workspace / "raw" / "elliptic"
            cached = raw.exists()
            raw_remote = storage / "raw" / "elliptic" if storage else None
            if not raw.exists() and raw_remote and raw_remote.exists():
                shutil.copytree(raw_remote, raw)
            if not raw.exists():
                if runtime == "codex_cloud":
                    raise RuntimeError("Dataset downloads from Codex Cloud are disabled. "
                                       "Run the same workflow in Colab, or provide authorized CSVs.")
                acquire(raw, config["max_download_bytes"], config["max_expanded_bytes"],
                        config["acquisition_seconds"])
            provenance = verify_acquisition(raw, config["max_download_bytes"],
                                            config["max_expanded_bytes"])
            state["acquisition"] = {"seconds": time.monotonic() - acquisition_started,
                                    "cached": cached or bool(raw_remote and raw_remote.exists())}
            if raw_remote:
                state["active_stage"] = "storage"
                archive(raw, raw_remote)
                state["active_stage"] = "acquisition"
        else:
            provenance = {"source": source_mode, "files": identity["provided_inputs"]}
        hashes = {n: sha256(raw / n) for n in FILES}
        if "raw_hashes" in state and state["raw_hashes"] != hashes:
            raise ValueError("input changed since checkpoint; use a fresh workspace")
        state["raw_hashes"] = hashes
        state["provenance"] = provenance
        save()
        input_dir = raw
        if config.get("data_mode") == "sample":
            from mmd_fraud.data.sample import sample_elliptic
            stage("sample", lambda target: sample_elliptic(
                raw, target, per_step=config.get("sample_per_step", 200),
                max_bytes=config["max_expanded_bytes"]))
            audit = json.loads((directory / "sample/sample.json").read_text())
            if source_mode != "generated_test_fixture" and (
                    audit["source_nodes"] != 203769 or audit["source_edges_raw"] != 234355
                    or audit["source_labels"] != {"1": 4545, "2": 42019, "unknown": 157205}
                    or audit["source_steps"] != list(range(1, 50))):
                raise ValueError("source release count/label/time audit failed")
            input_dir = directory / "sample"
        profile_name = "small" if config.get("data_mode") == "sample" else "medium"
        profile = json.loads((repo / "configs/profiles.json").read_text())[profile_name]
        profile["max_input_bytes"] = min(profile["max_input_bytes"], config["max_expanded_bytes"])
        def preprocess(target):
            from mmd_fraud.spark.pipeline import run
            # Existing pipeline preserves source arrays for audit, never model predictors.
            current = Path.cwd()
            try:
                os.chdir(repo)
                run({"directory": str(input_dir), "dataset_kind": state["dataset_kind"],
                     "require_original_counts": source_mode != "generated_test_fixture"
                     and config.get("data_mode") != "sample"}, profile, target, cutoffs=())
            finally:
                os.chdir(current)
        stage("preprocess", preprocess)
        def causal(target):
            from mmd_fraud.spark.pipeline import session
            from mmd_fraud.spark.causal import end_of_step_features
            from pyspark.sql import functions as F
            target.mkdir()
            spark = session(profile, directory / "spark-checkpoints")
            try:
                nodes = spark.read.parquet(str(directory / "preprocess/nodes"))
                edges = spark.read.parquet(str(directory / "preprocess/edges"))
                features = end_of_step_features(nodes, edges)
                features.write.mode("errorifexists").parquet(str(target / "transactions"))
                checked = spark.read.parquet(str(target / "transactions"))
                count = checked.count()
                if count != nodes.count() or checked.select("entity_id").distinct().count() != count:
                    raise ValueError("causal features changed transaction identities")
                if checked.filter(F.col("feature_cutoff_exclusive") != F.col("time_step") + 1).count():
                    raise ValueError("invalid feature temporal boundary")
                write_json(target / "validation.json", {"rows": count, "schema": "end_step_v1"})
            finally:
                spark.stop()
        stage("causal", causal)
        def models(target):
            from mmd_fraud.training.baselines import train
            train(directory / "causal/transactions", target,
                  config.get("train_end", 34), config.get("validation_end", 39),
                  config.get("seed", 0))
        stage("models", models)
        if config["experiments"]:
            def expanded(target):
                from mmd_fraud.spark.experiments import experiment_features, FAMILIES
                from mmd_fraud.spark.pipeline import session
                from pyspark.sql import functions as F
                target.mkdir()
                spark = session(profile, directory / "experiment-spark-checkpoints")
                try:
                    nodes = spark.read.parquet(str(directory / "preprocess/nodes"))
                    edges = spark.read.parquet(str(directory / "preprocess/edges"))
                    frame = experiment_features(nodes, edges)
                    frame.write.mode("errorifexists").parquet(str(target / "transactions"))
                    checked = spark.read.parquet(str(target / "transactions"))
                    count = checked.count()
                    if count != nodes.count() or checked.select("entity_id").distinct().count() != count:
                        raise ValueError("experiment features changed transaction identities")
                    names = list(dict.fromkeys(c for v in FAMILIES.values() for c in v))
                    bad = [F.col(c).isNull() | F.isnan(c) | (F.abs(F.col(c)) == float('inf')) for c in names]
                    if checked.filter(F.exists(F.array(*bad), lambda x: x)).limit(1).count():
                        raise ValueError("invalid experiment features")
                    write_json(target / "validation.json", {"rows": count, "schema": "comparison_v1"})
                finally:
                    spark.stop()
            stage("experiment_features", expanded)
            def comparison(target):
                from mmd_fraud.training.comparison import train_comparison
                train_comparison(directory / "experiment_features/transactions", target,
                                 directory / "comparison-trials", train_end, validation_end,
                                 config["seed"])
            stage("comparison", comparison)
        if config["research"]:
            def research_features(target):
                from mmd_fraud.spark.research import build_research
                target.mkdir()
                audit = build_research(directory / "experiment_features/transactions",
                                       directory / "preprocess/edges", target / "transactions.parquet", train_end)
                write_json(target / "audit.json", audit)
            stage("research_features", research_features)
            def research(target):
                from mmd_fraud.spark.research import RESEARCH_FAMILIES
                from mmd_fraud.training.comparison import train_comparison
                from mmd_fraud.training.research import research_report
                train_comparison(directory / "research_features/transactions.parquet", target,
                                 directory / "research-trials", train_end, validation_end,
                                 config["seed"], families=RESEARCH_FAMILIES,
                                 preserve_baseline=True, export_scores=True)
                research_report(target, json.loads((directory / "research_features/audit.json").read_text()))
            stage("research", research)
        state["status"] = "success"
        state["active_stage"] = "complete"
        save()
        (workspace / "failure.json").unlink(missing_ok=True)
    except Exception as exc:
        state["status"] = "failed"
        state["error"] = redact(f"{type(exc).__name__}: {exc}")
        record_failure(workspace, exc, state["active_stage"])
        try:
            save()
        except Exception as storage_error:
            state["persistence_error"] = redact(f"{type(storage_error).__name__}: {storage_error}")
            write_json(state_file, state)
            try:
                report(directory, state)
            except (OSError, ValueError, KeyError):
                pass  # The independent failure.json remains readable even with corrupt report inputs.
        raise
    print(f"Completed report: {directory / 'report.md'}", flush=True)
    return directory
