"""Distributed CSV validation; original anonymous features are not causal features."""
import csv
from datetime import datetime
from pathlib import Path
from pyspark.sql import DataFrame, SparkSession, functions as F, types as T
from mmd_fraud.adapters.elliptic import EllipticConfig
from mmd_fraud.adapters.banking import BankingColumns
from mmd_fraud.validation import ValidationError


def require_empty(frame: DataFrame, message: str) -> None:
    if frame.limit(1).count():
        raise ValidationError(message)


def bounded_count(frame: DataFrame, limit: int, name: str) -> int:
    count = frame.limit(limit + 1).count()
    if not count or count > limit:
        raise ValidationError(f"{name} empty or exceeds row limit {limit}")
    return count


def csv_frame(spark: SparkSession, path: Path, names: list[str], header: bool,
              max_bytes: int) -> DataFrame:
    if path.stat().st_size > max_bytes:
        raise ValidationError("CSV exceeds byte limit")
    if header:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            if next(csv.reader(handle), []) != names:
                raise ValidationError(f"unexpected header in {path.name}")
    schema = T.StructType([T.StructField(name, T.StringType()) for name in names])
    # FAILFAST catches short/long records before pruning; avoid Spark's permissive truncation.
    spark.conf.set("spark.sql.csv.parser.columnPruning.enabled", "false")
    return (spark.read.schema(schema).option("header", header).option("mode", "FAILFAST")
            .option("enforceSchema", "false").csv(str(path)))


def deduplicate(frame: DataFrame, keys: list[str], name: str) -> tuple[DataFrame, int]:
    distinct = frame.dropDuplicates()
    require_empty(distinct.groupBy(*keys).count().filter("count > 1"),
                  f"conflicting {name} rows for same key")
    removed = frame.count() - distinct.count()
    return distinct, removed


def invalid_id(name: str):
    col = F.col(name)
    return col.isNull() | (F.trim(col) == "") | (col != F.trim(col))


def invalid_number(col):
    return col.isNull() | F.isnan(col) | (F.abs(col) == float("inf"))


def elliptic(spark: SparkSession, config: EllipticConfig,
             missing_policy: str = "reject") -> tuple[DataFrame, DataFrame, dict]:
    if missing_policy not in {"reject", "zero"}:
        raise ValueError("missing_policy must be reject or zero")
    columns = [f"f_{i:03}" for i in range(config.numeric_feature_count)]
    raw = csv_frame(spark, config.directory / config.features_file,
                    ["entity_id", "step_raw", *columns], False, config.max_file_bytes)
    counts = {"feature_rows_raw": bounded_count(raw, config.max_rows, "features")}
    require_empty(raw.filter(invalid_id("entity_id") | ~F.col("entity_id").rlike(r"^[0-9]+$")),
                  "invalid transaction ID")
    raw = raw.withColumn("time_step", F.expr("try_cast(step_raw as int)"))
    require_empty(raw.filter(F.col("time_step").isNull() | ~F.col("time_step").between(1, 49)
                             | ~F.col("step_raw").rlike(r"^[0-9]+$")), "invalid time step")
    converted = [F.expr(f"try_cast(`{c}` as double)") for c in columns]
    missing = [F.col(c).isNull() | (F.trim(F.col(c)) == "") for c in columns]
    checks = [invalid_number(value) & (~m if missing_policy == "zero" else F.lit(True))
              for value, m in zip(converted, missing)]
    raw = raw.withColumn("_bad_numeric", F.exists(F.array(*checks), lambda x: x))
    require_empty(raw.filter("_bad_numeric"), "missing, nonnumeric or nonfinite feature")
    counts["missing_numeric_values"] = raw.select(
        F.sum(F.aggregate(F.array(*missing), F.lit(0),
                          lambda n, x: n + x.cast("int"))).alias("missing")).first().missing or 0
    features = raw.select("entity_id", "time_step",
                          F.array(*[F.coalesce(v, F.lit(0.0)) if missing_policy == "zero" else v
                                    for v in converted]).alias("source_features"))
    features, counts["feature_duplicates_removed"] = deduplicate(features, ["entity_id"], "feature")
    classes = csv_frame(spark, config.directory / config.classes_file,
                        ["txId", "class"], True, config.max_file_bytes)
    counts["class_rows_raw"] = bounded_count(classes, config.max_rows, "classes")
    require_empty(classes.filter(invalid_id("txId") | F.col("class").isNull()
                                  | ~F.col("class").isin("1", "2", "unknown")), "invalid label")
    classes = classes.select(F.col("txId").alias("entity_id"), F.col("class").alias("label"))
    classes, counts["class_duplicates_removed"] = deduplicate(classes, ["entity_id"], "class")
    require_empty(features.join(classes, "entity_id", "left_anti"), "missing class ID")
    require_empty(classes.join(features, "entity_id", "left_anti"), "orphan class ID")
    nodes = features.join(classes, "entity_id").withColumn("domain", F.lit("bitcoin_transaction"))
    edges = csv_frame(spark, config.directory / config.edges_file,
                      ["txId1", "txId2"], True, config.max_file_bytes)
    counts["edge_rows_raw"] = bounded_count(edges, config.max_rows, "edges")
    edges = edges.select(F.col("txId1").alias("source"), F.col("txId2").alias("target"))
    require_empty(edges.filter(invalid_id("source") | invalid_id("target")), "invalid edge ID")
    edges, counts["edge_duplicates_removed"] = deduplicate(edges, ["source", "target"], "edge")
    for endpoint in ("source", "target"):
        require_empty(edges.join(nodes.select(F.col("entity_id").alias(endpoint)),
                                 endpoint, "left_anti"), "dangling edge")
    times = nodes.select("entity_id", "time_step")
    edges = (edges.join(times.select(F.col("entity_id").alias("source"),
                                    F.col("time_step").alias("source_step")), "source")
             .join(times.select(F.col("entity_id").alias("target"),
                                F.col("time_step").alias("target_step")), "target")
             .withColumn("available_step", F.greatest("source_step", "target_step")))
    counts["nodes"] = nodes.count()
    counts["edges"] = edges.count()
    counts["labels"] = {r.label: r['count'] for r in nodes.groupBy("label").count().collect()}
    counts["steps"] = [r.time_step for r in nodes.select("time_step").distinct()
                       .orderBy("time_step").collect()]
    return nodes, edges, counts


def banking(spark: SparkSession, accounts: Path, transactions: Path,
            columns: BankingColumns, max_rows: int, max_bytes: int,
            time_unit: str = "simulation_step", timestamp_format: str | None = None,
            base_date: str | None = None, step_seconds: int = 86400
            ) -> tuple[DataFrame, DataFrame, dict]:
    # AMLSim output varies by conf/schema. Extra source columns are allowed here.
    def read(path, required):
        with path.open(newline="", encoding="utf-8-sig") as handle:
            names = next(csv.reader(handle), [])
        if len(names) != len(set(names)) or not set(required).issubset(names):
            raise ValidationError("missing or duplicate banking header columns")
        return csv_frame(spark, path, names, True, max_bytes)
    raw_nodes = read(accounts, [columns.account_id]).select(
        F.col(columns.account_id).alias("entity_id"))
    count_nodes = bounded_count(raw_nodes, max_rows, "accounts")
    require_empty(raw_nodes.filter(invalid_id("entity_id")), "invalid account ID")
    nodes = raw_nodes.dropDuplicates().withColumn("domain", F.lit("banking_account"))
    raw = read(transactions, [columns.event_id, columns.source, columns.target,
                              columns.step, columns.amount])
    count_events = bounded_count(raw, max_rows, "banking events")
    spark.conf.set("spark.sql.session.timeZone", "UTC")
    if timestamp_format:
        if not base_date or step_seconds <= 0:
            raise ValueError("timestamp mapping requires UTC base_date and positive step_seconds")
        base = datetime.fromisoformat(base_date)
        if base.tzinfo is None or base.utcoffset().total_seconds() != 0:
            raise ValueError("base_date must explicitly specify UTC")
        timestamp = F.try_to_timestamp(F.col(columns.step), F.lit(timestamp_format))
        time_value = F.floor((timestamp.cast("long") - F.lit(int(base.timestamp())))
                             / step_seconds).cast("int")
    else:
        time_value = F.expr(f"try_cast(`{columns.step}` as int)")
    events = raw.select(F.col(columns.event_id).alias("event_id"),
                        F.col(columns.source).alias("source"),
                        F.col(columns.target).alias("target"),
                        time_value.alias("time_step"),
                        F.expr(f"try_cast(`{columns.amount}` as double)").alias("amount"),
                        F.col(columns.step).alias("step_raw"))
    require_empty(events.filter(invalid_id("event_id") | invalid_id("source")
                                 | invalid_id("target") | F.col("time_step").isNull()
                                 | (F.col("time_step") < 0)
                                 | (F.lit(False) if timestamp_format else
                                    ~F.col("step_raw").rlike(r"^[0-9]+$"))
                                 | invalid_number(F.col("amount")) | (F.col("amount") < 0)),
                  "invalid banking event")
    events, removed = deduplicate(events.drop("step_raw"), ["event_id"], "banking event")
    for endpoint in ("source", "target"):
        require_empty(events.join(nodes.select(F.col("entity_id").alias(endpoint)),
                                  endpoint, "left_anti"), "dangling account")
    events = events.withColumn("time_unit", F.lit(time_unit))
    return nodes, events, {"account_rows_raw": count_nodes, "event_rows_raw": count_events,
                           "nodes": nodes.count(), "events": events.count(),
                           "event_duplicates_removed": removed}
