"""Single cloud entry point for bounded independent synthetic banking research."""

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import time
import traceback

import numpy as np

from .automation import cloud_runtime, inventory, verified, write_json
from .cloud_job import require_free_hosted_ci, resource_check
from .data.acquire import outside_repo, sha256
from .data.banking_synthetic import generate
from .spark.banking_research import FAMILIES, prepare, add_graph
from .spark.pipeline import session
from .training.comparison import train_comparison
from .training.banking import anomaly, report
from .training.research import paired_intervals


def execute(workspace: Path, config: dict, input_directory=None):
    runtime = cloud_runtime()
    if runtime == "github_ci":
        require_free_hosted_ci()
    if set(config) != {"accounts", "daily_events", "seeds"} or not isinstance(
        config["seeds"], list
    ):
        raise ValueError("banking configuration requires accounts, daily_events, seeds")
    if not 1 <= len(config["seeds"]) <= 3 or len(set(config["seeds"])) != len(config["seeds"]):
        raise ValueError("one to three distinct predeclared dataset seeds required")
    for key, low, high in [("accounts", 50, 1000), ("daily_events", 50, 1200)]:
        if type(config[key]) is not int or not low <= config[key] <= high:
            raise ValueError("bounded banking configuration violated")
    if any(type(v) is not int or not 0 <= v < 2**32 for v in config["seeds"]):
        raise ValueError("seeds must be uint32 integers")
    workspace = outside_repo(workspace)
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "result.json").unlink(missing_ok=True)
    repo = Path(__file__).resolve().parents[2]
    external = outside_repo(Path(input_directory)) if input_directory else None
    if external and len(config["seeds"]) != 1:
        raise ValueError("external input accepts one run, not synthetic seed replicas")
    identity = {
        "config": config,
        "runtime": runtime,
        "git_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo, text=True
        ).strip(),
        "git_dirty": bool(
            subprocess.check_output(["git", "status", "--porcelain"], cwd=repo, text=True)
        ),
        "code": {
            str(p.relative_to(repo)): sha256(p)
            for base in ("src", "scripts", "configs")
            for p in sorted((repo / base).rglob("*"))
            if p.suffix in (".py", ".json")
        },
        "dependencies": {
            n: importlib.metadata.version(n)
            for n in ("numpy", "scipy", "scikit-learn", "pyarrow", "pyspark", "matplotlib")
        },
        "lock": sha256(repo / "requirements-cloud.lock"),
        "external": {n: sha256(external / n) for n in ("accounts.csv", "transactions.csv")}
        if external
        else None,
    }
    key = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    run = workspace / key
    run.mkdir(exist_ok=True)
    write_json(workspace / "active.json", {"run": key, "identity": identity})
    started = time.monotonic()
    results = []
    for seed in config["seeds"]:
        directory = run / f"seed-{seed}"
        directory.mkdir(exist_ok=True)
        state_path = directory / "state.json"
        state = json.loads(state_path.read_text()) if state_path.exists() else {"stages": {}}

        def stage(name, action):
            resource_check(workspace, started)
            target = directory / name
            if name in state["stages"]:
                if not verified(target, state["stages"][name]["hashes"]):
                    state.update(status="failed", active_stage=name, error_type="ValueError")
                    write_json(state_path, state)
                    raise ValueError(f"corrupt banking checkpoint: {name}")
                print(f"Restored seed {seed} stage {name}", flush=True)
                return
            if target.exists():
                shutil.rmtree(target)  # only uncommitted partial stage in run-owned workspace
            state.update(status="running", active_stage=name)
            write_json(state_path, state)
            began = time.monotonic()
            print(f"Running seed {seed} stage {name}", flush=True)
            try:
                action(target)
                resource_check(workspace, started)
                state["stages"][name] = {
                    "seconds": time.monotonic() - began,
                    "hashes": inventory(target),
                }
                write_json(state_path, state)
            except Exception as exc:
                state.update(
                    status="failed",
                    error_type=type(exc).__name__,
                    frames=[
                        {"file": Path(f.filename).name, "line": f.lineno, "function": f.name}
                        for f in traceback.extract_tb(exc.__traceback__)[-5:]
                    ],
                )
                write_json(state_path, state)
                raise  # full original traceback in private execution log

        def source(target):
            if external:
                target.mkdir()
                for name in ("accounts.csv", "transactions.csv"):
                    if (external / name).stat().st_size > 50000000:
                        raise ValueError("banking file exceeds 50 MB limit")
                    shutil.copyfile(external / name, target / name)
                    if sha256(target / name) != identity["external"][name]:
                        raise ValueError("external input changed during copy")
                write_json(
                    target / "provenance.json",
                    {
                        "dataset_kind": "external_amlsim_compatible_unverified",
                        "official_amlsim_output": False,
                        "real_data_verified": False,
                        "files": {
                            n: sha256(target / n) for n in ("accounts.csv", "transactions.csv")
                        },
                    },
                )
            else:
                generate(target, config["accounts"], config["daily_events"], seed)

        stage("source", source)

        def preprocess(target):
            target.mkdir()
            spark = session(
                {"driver_memory": "1g", "partitions": 2}, directory / "spark-checkpoints"
            )
            try:
                audit = prepare(spark, directory / "source", target)
                write_json(target / "validation.json", audit)
            finally:
                spark.stop()

        stage("preprocess", preprocess)

        def features(target):
            target.mkdir()
            benchmarks = add_graph(
                directory / "preprocess/daily",
                directory / "preprocess/events",
                target / "features.parquet",
            )
            write_json(target / "benchmarks.json", {"snapshots": benchmarks})

        stage("features", features)

        def models(target):
            train_comparison(
                directory / "features/features.parquet",
                target,
                directory / "trials",
                families=FAMILIES,
                cutoff_offset=0,
                export_scores=True,
                source_policy="banking account-day forecasts; all predictors strictly before target day",
            )
            anomaly(directory / "features/features.parquet", target)

        stage("models", models)
        comparison = json.loads((directory / "models/comparison.json").read_text())

        def statistics(target):
            target.mkdir()
            base = np.load(directory / "models/transaction_only-private-scores.npz")
            intervals = {}
            for name in FAMILIES:
                if name == "transaction_only":
                    continue
                current = np.load(directory / f"models/{name}-private-scores.npz")
                if not np.array_equal(current["y"], base["y"]) or not np.array_equal(
                    current["step"], base["step"]
                ):
                    raise ValueError("banking paired populations differ")
                intervals[name] = paired_intervals(
                    base["y"],
                    base["step"],
                    base["score"],
                    current["score"],
                    comparison["families"]["transaction_only"]["threshold"],
                    comparison["families"][name]["threshold"],
                )
            write_json(target / "intervals.json", intervals)

        stage("statistics", statistics)
        state.update(status="success", active_stage="complete")
        write_json(state_path, state)
        results.append(
            {
                "seed": seed,
                "provenance": json.loads((directory / "source/provenance.json").read_text()),
                "validation": json.loads((directory / "preprocess/validation.json").read_text()),
                "comparison": comparison,
                "anomaly": json.loads((directory / "models/anomaly.json").read_text()),
                "graph_benchmarks": json.loads(
                    (directory / "features/benchmarks.json").read_text()
                )["snapshots"],
                "paired_intervals": json.loads(
                    (directory / "statistics/intervals.json").read_text()
                ),
                "stages": state["stages"],
            }
        )
    public = run / "public"
    if public.exists():
        shutil.rmtree(public)  # regenerate only the allowlisted aggregate export, not checkpoints
    report(results, json.loads((repo / "configs/elliptic-reference.json").read_text()), public)
    summary = json.loads((public / "banking-summary.json").read_text())
    summary["identity"] = identity
    write_json(public / "banking-summary.json", summary)
    write_json(public / "banking-evidence-manifest.json", {"sha256": inventory(public)})
    write_json(workspace / "result.json", {"public": str(public)})
    return public


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--config", type=Path, default=Path("configs/banking-research.json"))
    parser.add_argument(
        "--input", type=Path, help="AMLSim-compatible CSV directory; provenance remains unverified"
    )
    args = parser.parse_args(argv)
    try:
        public = execute(args.workspace, json.loads(args.config.read_text()), args.input)
    except Exception:
        # Stage state and private original traceback remain available; no synthetic success fallback.
        raise
    print("Verified banking evidence:", public, flush=True)
    return 0
