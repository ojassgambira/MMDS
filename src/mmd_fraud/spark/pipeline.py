"""Bounded cloud runner with disk checkpoints, immutable run dirs and JSON evidence."""
import json
import platform
import resource
import shutil
import subprocess
import time
from pathlib import Path
from pyspark import __version__ as spark_version
from pyspark.sql import SparkSession
from mmd_fraud.adapters.elliptic import EllipticConfig
from mmd_fraud.adapters.banking import BankingColumns
from mmd_fraud.data.acquire import FILES, outside_repo, sha256
from .preprocess import elliptic, banking
from .graph import statistics, historical


def session(profile: dict, checkpoint: Path, master: str = "local[2]") -> SparkSession:
    builder = (SparkSession.builder.appName("mmd-phase2-preprocessing").master(master)
               .config("spark.driver.memory", profile["driver_memory"])
               .config("spark.sql.shuffle.partitions", str(profile["partitions"]))
               .config("spark.sql.adaptive.enabled", "false")
               .config("spark.sql.codegen.wholeStage", "false")
               .config("spark.sql.parquet.compression.codec", "snappy")
               .config("spark.sql.files.maxRecordsPerFile", "100000")
               .config("spark.ui.enabled", "false"))
    if master.startswith("local"):
        builder = builder.config("spark.driver.host", "127.0.0.1").config(
            "spark.driver.bindAddress", "127.0.0.1")
    spark = builder.getOrCreate()
    spark.sparkContext.setLogLevel("ERROR")
    spark.sparkContext.setCheckpointDir(str(checkpoint))
    return spark


def run(config: dict, profile: dict, output: Path, domain: str = "bitcoin",
        master: str = "local[2]", cutoffs: tuple[int, ...] = (2, 35, 50)) -> dict:
    output = outside_repo(output)
    if output.exists():
        raise FileExistsError("use a new run directory; existing checkpoints are never overwritten")
    if domain not in {"bitcoin", "banking"}:
        raise ValueError("unsupported domain")
    if domain == "bitcoin" and (len(cutoffs) > profile["max_cutoffs"]
                                or len(set(cutoffs)) != len(cutoffs)
                                or any(not 1 <= c <= 50 for c in cutoffs)):
        raise ValueError("invalid or excessive cutoffs")
    paths = ([Path(config["directory"]) / name for name in FILES] if domain == "bitcoin"
             else [Path(config["accounts"]), Path(config["transactions"])])
    for path in paths:
        outside_repo(path)
    input_bytes = sum(p.stat().st_size for p in paths)
    if input_bytes > profile["max_input_bytes"]:
        raise ValueError("total input bytes exceeds profile")
    output.parent.mkdir(parents=True, exist_ok=True)
    if shutil.disk_usage(output.parent).free < max(input_bytes * 4, 100_000_000):
        raise ValueError("insufficient disk reserve for output and checkpointing")
    output.mkdir()
    start = time.monotonic()
    manifest = {"status": "running", "domain": domain, "profile": profile,
                "dataset_kind": config.get("dataset_kind", "unspecified"),
                "configuration": config, "cutoffs_exclusive": list(cutoffs) if domain == "bitcoin" else [],
                "master": master, "python_version": platform.python_version(),
                "spark_version": spark_version,
                "git_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                "git_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], text=True)),
                "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "inputs": [{"file": p.name, "bytes": p.stat().st_size, "sha256": sha256(p)}
                           for p in paths], "stages": {}}
    def save():
        manifest["elapsed_seconds"] = time.monotonic() - start
        manifest["python_peak_rss_bytes"] = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        try:
            manifest["cgroup_current_memory_bytes"] = int(
                Path("/sys/fs/cgroup/memory.current").read_text())
            manifest["cgroup_peak_memory_bytes"] = int(
                Path("/sys/fs/cgroup/memory.peak").read_text())
        except (OSError, ValueError):
            pass
        (output / "run.json").write_text(json.dumps(manifest, indent=2) + "\n")
    save()
    spark = None
    def persist(name, frame, partition=None):
        began = time.monotonic()
        partitions = profile["partitions"]
        frame = frame.repartition(partitions)
        rows = frame.count()
        writer = frame.write.mode("errorifexists")
        if partition:
            writer = writer.partitionBy(partition)
        writer.parquet(str(output / name))
        reloaded = spark.read.parquet(str(output / name))
        if reloaded.count() != rows:
            raise AssertionError("Parquet round-trip row count mismatch")
        manifest["stages"][name] = {"rows": rows, "requested_partitions": partitions,
                                   "read_partitions": reloaded.rdd.getNumPartitions(),
                                   "parquet_files": len(list((output / name).rglob("*.parquet"))),
                                   "elapsed_seconds": time.monotonic() - began}
        save()
        return reloaded
    try:
        spark = session(profile, output / "checkpoints", master)
        began = time.monotonic()
        if domain == "bitcoin":
            cfg = EllipticConfig(Path(config["directory"]), max_rows=profile["max_rows"],
                                 max_file_bytes=profile["max_input_bytes"])
            nodes, edges, validation = elliptic(spark, cfg, config.get("missing_policy", "reject"))
        else:
            nodes, edges, validation = banking(
                spark, Path(config["accounts"]), Path(config["transactions"]),
                BankingColumns(**config.get("columns", {})), profile["max_rows"],
                profile["max_input_bytes"], config.get("time_unit", "simulation_step"),
                config.get("timestamp_format"), config.get("base_date"),
                config.get("step_seconds", 86400))
        manifest["validation"] = validation
        manifest["validation_seconds"] = time.monotonic() - began
        if domain == "bitcoin" and config.get("require_original_counts", False):
            if validation["nodes"] != 203769 or validation["edges"] != 234355:
                raise ValueError("original release row count mismatch")
            if validation["labels"] != {"1": 4545, "2": 42019, "unknown": 157205}:
                raise ValueError("original release label count mismatch")
            if validation["steps"] != list(range(1, 50)):
                raise ValueError("original release step coverage mismatch")
        save()
        if domain == "bitcoin":
            nodes = persist("nodes", nodes, "time_step")
            edges = persist("edges", edges, "available_step")
            persist("graph_features_descriptive", statistics(nodes, edges))
            for cutoff in cutoffs:
                # Cutoff 1 has no visible nodes; retain a valid empty Parquet checkpoint.
                frame = historical(nodes, edges, cutoff)
                persist(f"historical_features_{cutoff}", frame, "cutoff_step" if cutoff > 1 else None)
        else:
            persist("accounts", nodes)
            persist("events", edges, "time_step")
        manifest["status"] = "success"
        save()
        return manifest
    except Exception as exc:
        manifest["status"] = "failed"
        manifest["error_type"] = type(exc).__name__
        save()
        raise
    finally:
        if spark:
            spark.stop()
