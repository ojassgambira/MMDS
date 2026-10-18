# Measured processing benchmarks

The Phase 6 suite executed CSV validation, graph summaries, Parquet write/read and
output count validation at three generated sizes for each domain. These are
**single-machine measurements**, not a distributed multi-worker scalability study.

Bundled evidence: `dashboard/data/spark-benchmarks.json`, protected by its SHA-256
manifest. Codex Cloud: Python 3.12.14, Spark 4.0.1, Java 21, local[2], 1 GB driver
heap, two shuffle partitions, three visible CPUs and two concurrent task slots.

| Generated workload | Nodes/accounts | Events/edges | Seconds |
| --- | ---: | ---: | ---: |
| Bitcoin correctness fixture | 100 | 99 | 15.466 |
| Bitcoin correctness fixture | 500 | 499 | 8.944 |
| Bitcoin correctness fixture | 1,000 | 999 | 8.197 |
| Independent synthetic banking | 100 | 8,600 | 2.182 |
| Independent synthetic banking | 500 | 28,600 | 2.382 |
| Independent synthetic banking | 1,000 | 53,600 | 2.721 |

Source generation and Spark startup are excluded. The first measured processing
includes cold work; subsequent runs share a warm JVM. One repetition per size,
small data, topology and compression limit interpretation. The decreasing Bitcoin
times are not evidence of inverse scaling. Peak memory, shuffle bytes, spill,
variance and worker-count speedup were **not measured**. No production throughput
or real-data extrapolation is made. Graph-prefix sparse CPU timings in the research
snapshots are distinct from these Spark processing measurements.

[Phase 6 GitHub verification](https://github.com/ojassgambira/MMDS/actions/runs/38906512069)
independently repeated all six sizes on Python 3.13.16 / Java 21, four visible CPUs,
still local[2] on one machine. Its timings were 13.085/6.748/6.424 seconds for
Bitcoin and 1.695/1.869/2.152 seconds for banking. Those hardware/runtime measurements
are not merged into the bundled Codex series. Archive SHA-256:
`6b9e1dfa22c01a043d85dd0863dd8695704cddb7cac8e059a1c9aa608d6fb3ce`.
Artifacts have seven-day retention; the archived measurement record remains here.

Reproduce in an approved managed cloud using the full lock:

```sh
python scripts/benchmark_spark.py --workspace /workspace/benchmark-private-new
```

Use a new outside-checkout workspace; private generated CSV/Parquet outputs are
not committed. The GitHub dashboard workflow reruns this bounded benchmark and
publishes only measured JSON. See [cloud guide](cloud-execution.md) and
[full report/figure](final-research-report.md).

Earlier [Phase 2 fixture measurements](phase2-results.md) remain historical evidence.
The initial 10K/100K/1M and multi-executor plan was not executed and is not a result.
Future scaling studies should control cold/warm phases, repeat each size, capture
memory/shuffle/spill and use actual multiple workers only with approved free capacity.
