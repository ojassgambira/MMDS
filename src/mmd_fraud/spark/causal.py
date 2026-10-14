"""Transaction graph features available after each transaction's step completes.

Same-step relationships are allowed only for this declared end-of-step offline
task. Future relationships and anonymous publisher aggregates are never inputs.
"""
from pyspark.sql import DataFrame, functions as F

FEATURES = ("in_degree", "out_degree", "total_degree", "neighbor_count",
            "past_neighbor_count", "same_step_neighbor_count")


def end_of_step_features(nodes: DataFrame, edges: DataFrame) -> DataFrame:
    # For each focal endpoint, withhold an edge if either endpoint is in its future.
    incoming = (edges.filter(F.col("available_step") <= F.col("target_step"))
                .select(F.col("target").alias("entity_id"),
                        F.col("source").alias("neighbor"),
                        F.col("source_step").alias("neighbor_step"),
                        F.col("target_step").alias("time_step"),
                        F.lit(1).alias("incoming"), F.lit(0).alias("outgoing")))
    outgoing = (edges.filter(F.col("available_step") <= F.col("source_step"))
                .select(F.col("source").alias("entity_id"),
                        F.col("target").alias("neighbor"),
                        F.col("target_step").alias("neighbor_step"),
                        F.col("source_step").alias("time_step"),
                        F.lit(0).alias("incoming"), F.lit(1).alias("outgoing")))
    visible = incoming.unionByName(outgoing)
    degrees = visible.groupBy("entity_id").agg(
        F.sum("incoming").alias("in_degree"), F.sum("outgoing").alias("out_degree"))
    neighbors = (visible.filter("entity_id != neighbor")
                 .select("entity_id", "neighbor", "neighbor_step", "time_step").distinct()
                 .groupBy("entity_id").agg(
                     F.count("neighbor").alias("neighbor_count"),
                     F.sum((F.col("neighbor_step") < F.col("time_step")).cast("int"))
                     .alias("past_neighbor_count"),
                     F.sum((F.col("neighbor_step") == F.col("time_step")).cast("int"))
                     .alias("same_step_neighbor_count")))
    return (nodes.select("entity_id", "time_step", "label")
            .join(degrees, "entity_id", "left").join(neighbors, "entity_id", "left")
            .fillna(0, [name for name in FEATURES if name != "total_degree"])
            .withColumn("total_degree", F.col("in_degree") + F.col("out_degree"))
            .withColumn("feature_cutoff_exclusive", F.col("time_step") + 1)
            .withColumn("schema_version", F.lit("end_step_v1")))
