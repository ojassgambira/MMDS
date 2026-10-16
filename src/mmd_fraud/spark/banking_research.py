"""Account-day forecasting; every predictor uses transactions strictly before day t."""

from pathlib import Path
import time

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from pyspark.sql import Window, functions as F
from scipy import sparse
from scipy.sparse.csgraph import connected_components

from mmd_fraud.adapters.banking import BankingColumns
from .preprocess import banking, require_empty
from .research import pagerank

TRANSACTION = ("previous_count", "previous_volume", "previous_mean", "previous_std")
GRAPH = (
    "historical_in",
    "historical_out",
    "counterparties",
    "pagerank_in",
    "pagerank_out",
    "component_size",
    "reciprocal_fraction",
)
TEMPORAL = ("rolling_count", "rolling_volume", "volume_burst", "amount_anomaly", "active_days")
FAMILIES = {
    "transaction_only": TRANSACTION,
    "graph_only": GRAPH,
    "temporal_only": TEMPORAL,
    "combined": (*TRANSACTION, *GRAPH, *TEMPORAL),
}
COLUMNS = BankingColumns(
    "acct_id", "tran_id", "orig_acct", "bene_acct", "tran_timestamp", "base_amt"
)


def prepare(spark, source: Path, output: Path):
    for name in ("accounts.csv", "transactions.csv"):
        if (source / name).stat().st_size > 50000000:
            raise ValueError("banking file exceeds 50 MB limit")
    nodes, events, audit = banking(
        spark,
        source / "accounts.csv",
        source / "transactions.csv",
        COLUMNS,
        100000,
        50000000,
        "days_from_base_utc",
        "yyyy-MM-dd'T'HH:mm:ss'Z'",
        "2017-01-01T00:00:00+00:00",
    )
    registry = spark.read.option("header", True).csv(str(source / "accounts.csv"))
    if "open_dt" in registry.columns:
        opened = F.coalesce(
            F.try_to_timestamp("open_dt", F.lit("yyyy-MM-dd'T'HH:mm:ss'Z'")),
            F.try_to_timestamp("open_dt", F.lit("yyyyMMdd")),
        )
        require_empty(
            registry.filter(opened.isNull() | (opened > F.lit("2017-01-01").cast("timestamp"))),
            "account registry must be known at the base date; future open_dt unsupported",
        )
    if nodes.count() > 1000:
        raise ValueError("banking research account limit is 1000")
    require_empty(events.filter("time_step > 49"), "banking research requires days 0..49")
    # Read the same FAILFAST validated file; label/alert metadata never enter predictors.
    raw = (
        spark.read.option("header", True)
        .option("mode", "FAILFAST")
        .csv(str(source / "transactions.csv"))
    )
    if "is_sar" not in raw.columns:
        raise ValueError("explicit is_sar labels required; absent labels cannot become negatives")
    require_empty(
        raw.filter(F.col("is_sar").isNull() | ~F.lower("is_sar").isin("true", "false")),
        "is_sar must explicitly be true or false",
    )
    # Reject conflicting duplicate labels even if the transaction fields match.
    require_empty(
        raw.groupBy("tran_id").agg(F.countDistinct(F.lower("is_sar")).alias("n")).filter("n > 1"),
        "conflicting transaction SAR labels",
    )
    labels = raw.select(
        F.col("tran_id").alias("event_id"), (F.lower("is_sar") == "true").cast("int").alias("sar")
    ).distinct()
    events = events.join(labels, "event_id")
    rows = events.select(
        F.col("source").alias("account_id"), "time_step", "amount", "sar"
    ).unionByName(events.select(F.col("target").alias("account_id"), "time_step", "amount", "sar"))
    # Each self transfer is counted once for account activity, while graph flow retains it.
    self_rows = events.filter("source = target").select(
        F.col("source").alias("account_id"), "time_step", "amount", "sar"
    )
    rows = rows.exceptAll(self_rows)
    daily = rows.groupBy("account_id", "time_step").agg(
        F.count("*").alias("n"),
        F.sum("amount").alias("volume"),
        F.sum(F.col("amount") ** 2).alias("squared"),
        F.max("sar").alias("sar"),
    )
    grid = nodes.select(F.col("entity_id").alias("account_id")).crossJoin(
        spark.range(50).select(F.col("id").cast("int").alias("time_step"))
    )
    daily = grid.join(daily, ["account_id", "time_step"], "left").fillna(0).cache()
    order = Window.partitionBy("account_id").orderBy("time_step")
    prev, recent, reference = (
        order.rangeBetween(-1, -1),
        order.rangeBetween(-7, -1),
        order.rangeBetween(-8, -2),
    )
    frame = daily
    for col in ("n", "volume", "squared"):
        frame = frame.withColumn("prev_" + col, F.coalesce(F.sum(col).over(prev), F.lit(0.0)))
        frame = frame.withColumn("recent_" + col, F.coalesce(F.sum(col).over(recent), F.lit(0.0)))
        frame = frame.withColumn(
            "reference_" + col, F.coalesce(F.sum(col).over(reference), F.lit(0.0))
        )
    frame = (
        frame.withColumn("previous_count", F.col("prev_n"))
        .withColumn("previous_volume", F.col("prev_volume"))
        .withColumn("previous_mean", F.col("prev_volume") / F.greatest(F.col("prev_n"), F.lit(1)))
        .withColumn(
            "previous_std",
            F.sqrt(
                F.greatest(
                    F.col("prev_squared") / F.greatest(F.col("prev_n"), F.lit(1))
                    - F.col("previous_mean") ** 2,
                    F.lit(0),
                )
            ),
        )
        .withColumn("rolling_count", F.col("recent_n"))
        .withColumn("rolling_volume", F.col("recent_volume"))
        .withColumn("volume_burst", F.col("prev_volume") / (F.col("reference_volume") / 7 + 1))
        .withColumn(
            "amount_anomaly",
            F.abs(
                F.col("previous_mean")
                - F.col("reference_volume") / F.greatest(F.col("reference_n"), F.lit(1))
            )
            / (
                F.sqrt(
                    F.greatest(
                        F.col("reference_squared") / F.greatest(F.col("reference_n"), F.lit(1))
                        - (F.col("reference_volume") / F.greatest(F.col("reference_n"), F.lit(1)))
                        ** 2,
                        F.lit(0),
                    )
                )
                + 1
            ),
        )
        .withColumn(
            "active_days", F.coalesce(F.sum((F.col("n") > 0).cast("int")).over(recent), F.lit(0))
        )
        .withColumn("label", F.when(F.col("sar") > 0, "1").otherwise("2"))
        .withColumn("entity_id", F.concat_ws("@", "account_id", F.col("time_step").cast("string")))
        .withColumn("feature_cutoff_exclusive", F.col("time_step"))
        .filter("time_step >= 1")
        .select(
            "entity_id",
            "account_id",
            "time_step",
            "feature_cutoff_exclusive",
            "label",
            *TRANSACTION,
            *TEMPORAL,
        )
    )
    frame.write.parquet(str(output / "daily"))
    events.select("source", "target", "time_step", "amount").write.parquet(str(output / "events"))
    audit["account_days"] = frame.count()
    audit["daily"] = [r.asDict() for r in events.groupBy("time_step").agg(
        F.count("*").alias("events"), F.sum("amount").alias("volume"),
        F.sum("sar").alias("sar_payments")).orderBy("time_step").collect()]
    daily.unpersist()
    return audit


def graph_snapshots(ids, source, target, days, cutoffs=range(1, 50)):
    """Counts preserve repeated events; neighbor topology and components use unique pairs."""
    if len(ids) > 1000 or len(source) > 100000 or len(ids) != len(set(ids)):
        raise ValueError("bounded banking graph identity/size violation")
    index = {v: i for i, v in enumerate(ids)}
    if len(source) != len(target) or len(source) != len(days):
        raise ValueError("unaligned banking graph input")
    if any(v not in index for v in (*source, *target)):
        raise ValueError("missing banking account endpoint")
    u, v = (
        np.array([index[a] for a in source], dtype=int),
        np.array([index[b] for b in target], dtype=int),
    )
    days = np.asarray(days)
    result, benchmarks = [], []
    for cutoff in cutoffs:
        began = time.monotonic()
        mask = days < cutoff
        matrix = sparse.csr_matrix(
            (np.ones(mask.sum()), (u[mask], v[mask])), shape=(len(ids), len(ids))
        )
        topology = matrix.astype(bool).astype(float)
        neighbors = (topology + topology.T).astype(bool).astype(float)
        neighbors.setdiag(0)
        neighbors.eliminate_zeros()
        counts = np.asarray(neighbors.sum(axis=1)).ravel()
        reciprocal = topology.multiply(topology.T)
        reciprocal.setdiag(0)
        _, components = connected_components(topology, directed=True, connection="weak")
        values = np.column_stack(
            (
                np.asarray(matrix.sum(axis=0)).ravel(),
                np.asarray(matrix.sum(axis=1)).ravel(),
                counts,
                pagerank(matrix),
                pagerank(matrix.T.tocsr()),
                np.bincount(components)[components],
                np.asarray(reciprocal.sum(axis=1)).ravel() / np.maximum(counts, 1),
            )
        )
        for i, name in enumerate(ids):
            result.append({"entity_id": f"{name}@{cutoff}", **dict(zip(GRAPH, values[i]))})
        benchmarks.append(
            {
                "cutoff_day": int(cutoff),
                "accounts": len(ids),
                "events": int(mask.sum()),
                "unique_directed_pairs": int(topology.nnz),
                "seconds": time.monotonic() - began,
            }
        )
    return pa.Table.from_pylist(result), benchmarks


def add_graph(daily_path, events_path, output):
    table = pq.ParquetDataset(daily_path).read()
    events = pq.ParquetDataset(events_path).read()
    ids = sorted(set(table["account_id"].to_pylist()))
    graph, benchmarks = graph_snapshots(
        ids,
        events["source"].to_pylist(),
        events["target"].to_pylist(),
        events["time_step"].to_numpy(),
    )
    order = {v: i for i, v in enumerate(graph["entity_id"].to_pylist())}
    idx = pa.array([order[v] for v in table["entity_id"].to_pylist()])
    graph = graph.take(idx)
    for name in GRAPH:
        table = table.append_column(name, graph[name])
    for name in (*TRANSACTION, *GRAPH, *TEMPORAL):
        if not np.isfinite(table[name].to_numpy()).all():
            raise ValueError("nonfinite banking feature")
    pq.write_table(table, output)
    if not pq.read_table(output).equals(table):
        raise ValueError("banking feature round-trip failed")
    return benchmarks
