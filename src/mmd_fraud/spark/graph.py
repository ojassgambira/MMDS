"""Degree/neighborhood statistics at explicit historical observation boundaries."""
from pyspark.sql import DataFrame, functions as F


def degrees(nodes: DataFrame, edges: DataFrame) -> DataFrame:
    incoming = edges.groupBy("target").count().select(
        F.col("target").alias("entity_id"), F.col("count").alias("in_degree"))
    outgoing = edges.groupBy("source").count().select(
        F.col("source").alias("entity_id"), F.col("count").alias("out_degree"))
    return (nodes.select("entity_id").join(incoming, "entity_id", "left")
            .join(outgoing, "entity_id", "left").fillna(0, ["in_degree", "out_degree"])
            .withColumn("total_degree", F.col("in_degree") + F.col("out_degree")))


def statistics(nodes: DataFrame, edges: DataFrame) -> DataFrame:
    degree = degrees(nodes, edges)
    # Unique undirected neighbors; directed degrees remain directed. Self edges count in
    # degree but do not create a neighbor of oneself.
    neighbors = (edges.select(F.col("source").alias("entity_id"), F.col("target").alias("neighbor"))
                 .union(edges.select(F.col("target").alias("entity_id"),
                                     F.col("source").alias("neighbor")))
                 .filter("entity_id != neighbor").dropDuplicates())
    neighbor_degree = degree.select(F.col("entity_id").alias("neighbor"),
                                    F.col("total_degree").alias("neighbor_degree"))
    summary = neighbors.join(neighbor_degree, "neighbor").groupBy("entity_id").agg(
        F.count("neighbor").alias("neighbor_count"),
        F.avg("neighbor_degree").alias("neighbor_mean_degree"),
        F.max("neighbor_degree").alias("neighbor_max_degree"))
    return degree.join(summary, "entity_id", "left").fillna(
        0, ["neighbor_count", "neighbor_mean_degree", "neighbor_max_degree"])


def historical(nodes: DataFrame, edges: DataFrame, cutoff_step: int) -> DataFrame:
    if not 1 <= cutoff_step <= 50:
        raise ValueError("cutoff must be 1..50 (exclusive)")
    # At start of cutoff step: do not use anything from that step or later.
    visible_nodes = nodes.filter(F.col("time_step") < cutoff_step)
    visible_edges = edges.filter(F.col("available_step") < cutoff_step)
    previous = visible_edges.filter(F.col("available_step") == cutoff_step - 1)
    recent = degrees(visible_nodes, previous).select(
        "entity_id", F.col("in_degree").alias("previous_step_in_degree"),
        F.col("out_degree").alias("previous_step_out_degree"))
    return (statistics(visible_nodes, visible_edges).join(recent, "entity_id")
            .join(visible_nodes.select("entity_id", "time_step"), "entity_id")
            .withColumn("age_steps", F.lit(cutoff_step) - F.col("time_step"))
            .withColumn("cutoff_step", F.lit(cutoff_step))
            .withColumn("domain", F.lit("bitcoin_transaction"))
            .withColumn("time_unit", F.lit("elliptic_step"))
            .withColumn("schema_version", F.lit("2")))
