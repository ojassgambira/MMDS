# Phase 3 recommendations

1. Gate on successful real Elliptic acquisition and a medium-profile run, not only
   generated tests. Preserve input hashes, validation evidence and cloud manifests.
2. Audit the anonymous source feature definitions and availability. Build future
   prediction targets separately from historical snapshots; cutoff snapshots omit
   nodes first appearing at the cutoff. Specify candidate-transaction serving rules
   before modeling. Never use descriptive full-graph degrees as historical inputs.
3. Split by time and fit all preprocessing on training data only. Preserve unknown
   labels separately. Delay the final model until preprocessing verification passes.
4. Add repeated seed-controlled benchmark runs and input skew tests on existing
   approved capacity. Record JVM/executor metrics via Spark monitoring separately
   from environment-wide cgroup memory; do not claim speedup from local[2].
5. Add checkpoint-resume verification with configuration/input-hash matching, then
   shared-storage backends only when an existing cloud store is authorized.
6. Execute AMLSim only after its isolated legacy environment is verified. Pin its
   commit and exact schema and base_date, audit currency/time conventions, and add
   historical banking features with explicit account/event label targets.
7. Add separate domain baselines and PR-AUC/precision/recall reporting. No combined
   Bitcoin/account graph, fabricated model scores, or automatic paid deployment.
