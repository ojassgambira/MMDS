# Planned scalability benchmarks

No scalability measurements were performed in Phase 1. A cloud local[2] smoke
test checks correctness only. Do not claim distributed speedup from it.

In Phase 2, benchmark generated graphs at 10K, 100K and 1M events, starting at the
smallest scale and within approved existing cloud capacity. Compare 1, 2 and 4
partitions on identical resources, then multiple executors only if available
and explicitly cost-approved. Separate parsing/validation, degree aggregation,
temporal windows and feature persistence from training. Include skewed hubs,
repeated banking edges and disconnected transaction components.

Record wall time, rows/s, shuffle read/write, spill, peak memory, partitions,
executor count, input/output sizes and failure rate. Perform warmup then three
measured repeats; retain median and spread. Check semantic correctness at every
scale against small reference outputs. Strong scaling uses fixed input; weak
scaling keeps records per worker fixed. Report storage and resource costs when
known; do not provision resources without approval. Define success thresholds
after the first baseline rather than inventing measurements.
