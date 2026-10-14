# Phase 2 implementation plan

1. Gate: pass the actual Spark smoke, unit suite and lint in cloud; confirm GitHub
   CI result and record the commit. Resolve any Phase 1 access blockers first.
2. Obtain authorized original Elliptic CSVs in cloud; freeze provenance/hashes,
   validate full schema/counts, and audit the temporal meaning of all aggregates.
3. Add Spark CSV-to-Parquet ingestion with explicit schemas, distributed validation,
   domain-separated storage, quarantine reports and bounded driver collection.
4. Implement distributed degree, neighborhood and temporal activity features;
   distinguish account event counts from transaction graph adjacency. Add known
   graph/temporal correctness fixtures and leakage tests.
5. Reproduce a bounded AMLSim simulation only after isolated compatibility checks;
   map the pinned output schema and declare label target and currency/time units.
6. Build separate domain baselines with temporal splits, seeded preprocessing and
   imbalanced metrics. Persist features before training and compare only meaningful
   domain-level metrics, with no combined graph or invented labels.
7. Run approved scalability benchmarks, then add cloud dashboard views for data
   quality, provenance, measured metrics and timing. Approve costs before deployment.

Large-scale training remains prohibited until Phase 1 verification is complete.
