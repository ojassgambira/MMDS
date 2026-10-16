"""Measured single-machine Spark processing on labeled generated fixtures only."""

import csv
import importlib.metadata
import json
from pathlib import Path
import platform
import subprocess
import time

from pyspark.sql import functions as F
from .pipeline import session
from .preprocess import elliptic, banking
from .graph import statistics
from mmd_fraud.adapters.elliptic import EllipticConfig
from mmd_fraud.adapters.banking import BankingColumns
from mmd_fraud.automation import cloud_runtime
from mmd_fraud.data.acquire import outside_repo
from mmd_fraud.data.banking_synthetic import generate


def bitcoin_fixture(path, count):
    path.mkdir()
    files = [
        (
            "elliptic_txs_features.csv",
            None,
            [[str(i), 1 + i * 49 // count, *([float(i % 7)] * 165)] for i in range(count)],
        ),
        (
            "elliptic_txs_classes.csv",
            ["txId", "class"],
            [[str(i), "unknown"] for i in range(count)],
        ),
        (
            "elliptic_txs_edgelist.csv",
            ["txId1", "txId2"],
            [[str(i), str(i + 1)] for i in range(count - 1)],
        ),
    ]
    for name, header, rows in files:
        with (path / name).open("w", newline="") as f:
            writer = csv.writer(f)
            if header:
                writer.writerow(header)
            writer.writerows(rows)


def run_benchmarks(workspace, sizes=(100, 500, 1000)):
    runtime = cloud_runtime()
    workspace = outside_repo(Path(workspace))
    workspace.mkdir()
    spark = session({"driver_memory": "1g", "partitions": 2}, workspace / "checkpoints")
    measurements = []
    try:
        configuration = {
            "runtime": runtime,
            "master": spark.sparkContext.master,
            "driver_memory": spark.sparkContext.getConf().get("spark.driver.memory"),
            "shuffle_partitions": spark.conf.get("spark.sql.shuffle.partitions"),
            "default_parallelism": spark.sparkContext.defaultParallelism,
            "spark": spark.version,
            "python": platform.python_version(),
            "java": subprocess.check_output(
                ["java", "-version"], stderr=subprocess.STDOUT, text=True
            ).splitlines()[0],
            "cpu_count_visible": __import__("os").cpu_count(),
            "machines": 1,
            "distributed_multi_worker_verified": False,
            "order": "Bitcoin sizes ascending, then banking sizes ascending; first measured run includes cold work",
            "repetitions": 1,
            "scope": "CSV validation + graph statistics + Parquet write/read/count; excludes source generation and Spark startup",
            "versions": {n: importlib.metadata.version(n) for n in ("numpy", "pyarrow", "pyspark")},
        }
        for domain in ("bitcoin_generated_fixture", "independent_synthetic_banking"):
            for count in sizes:
                if not 50 <= count <= 1000:
                    raise ValueError("benchmark sizes must be 50..1000")
                source = workspace / f"{domain}-{count}"
                if domain == "bitcoin_generated_fixture":
                    bitcoin_fixture(source, count)
                else:
                    generate(source, accounts=count, daily_events=count, seed=0)
                input_bytes = sum(p.stat().st_size for p in source.glob("*.csv"))
                start = time.monotonic()
                if domain == "bitcoin_generated_fixture":
                    nodes, edges, _ = elliptic(spark, EllipticConfig(directory=source))
                else:
                    nodes, edges, _ = banking(
                        spark,
                        source / "accounts.csv",
                        source / "transactions.csv",
                        BankingColumns(
                            "acct_id",
                            "tran_id",
                            "orig_acct",
                            "bene_acct",
                            "tran_timestamp",
                            "base_amt",
                        ),
                        100000,
                        50000000,
                        "days_from_base_utc",
                        "yyyy-MM-dd'T'HH:mm:ss'Z'",
                        "2017-01-01T00:00:00+00:00",
                    )
                nodes = nodes.cache()
                edges = edges.cache()
                n, e = nodes.count(), edges.count()
                target = workspace / f"{domain}-{count}-stats"
                statistics(nodes, edges).write.parquet(str(target))
                checked = spark.read.parquet(str(target))
                if checked.count() != n or checked.filter(F.col("total_degree") < 0).count():
                    raise ValueError("Spark benchmark intermediate validation failed")
                elapsed = time.monotonic() - start
                measurements.append(
                    {
                        "domain": domain,
                        "nodes": n,
                        "events": e,
                        "input_bytes": input_bytes,
                        "seconds": elapsed,
                        "output_rows": n,
                    }
                )
                nodes.unpersist()
                edges.unpersist()
    finally:
        spark.stop()
    result = {"configuration": configuration, "measurements": measurements}
    (workspace / "spark-benchmarks.json").write_text(json.dumps(result, indent=2) + "\n")
    return result
