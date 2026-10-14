"""Generated banking events exercise Python workers, shuffle and temporal filtering."""
def run_smoke() -> dict[str, int]:
    from pyspark.sql import SparkSession, functions as F
    spark = (SparkSession.builder.master("local[2]").appName("mmd-phase1-smoke")
             .config("spark.ui.enabled", "false")
             .config("spark.sql.shuffle.partitions", "2")
             .config("spark.driver.host", "127.0.0.1")
             .config("spark.driver.bindAddress", "127.0.0.1").getOrCreate())
    try:
        spark.sparkContext.setLogLevel("ERROR")
        records = [("t1", "a", "b", 0, 10.0), ("t2", "a", "c", 1, 20.0),
                   ("t3", "b", "a", 2, 5.0), ("t4", "a", "b", 3, 7.0)]
        frame = spark.createDataFrame(records, "event_id string, source string, target string, "
                                      "step int, amount double").repartition(2)
        actual = {r.source: (r.events, r.total) for r in
                  frame.filter(F.col("step") <= 2).groupBy("source")
                  .agg(F.count("event_id").alias("events"), F.sum("amount").alias("total"))
                  .collect()}
        if actual != {"a": (2, 30.0), "b": (1, 5.0)}:
            raise AssertionError(f"incorrect aggregation: {actual}")
        if frame.select("event_id").distinct().count() != 4:
            raise AssertionError("event IDs lost")
        return {"records": 4, "cutoff_step": 2, "source_accounts": len(actual)}
    finally:
        spark.stop()
