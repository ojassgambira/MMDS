# Experiment reproducibility

Every future run must emit a manifest outside Git with git commit, UTC execution
time, source dataset URL/version/license status, per-file SHA-256/byte sizes,
configuration hash, Python/Java/Spark versions, exact dependency lock, random
seeds, partition counts, executor resources, input/output counts, validation
report and elapsed time. Record failures and skipped checks alongside success.
Pin upstream AMLSim commit and JAR hashes rather than tracking mutable master.

Use seed 0 for generated simulations and fixed train/validation/test boundaries.
Fit preprocessing only on training observations. Evaluate each domain separately;
exclude unknown labels from supervised metrics and record their count. Use PR-AUC,
illicit recall/precision, confusion matrices and time-stratified metrics in Phase 2;
no scores exist in Phase 1. Account for class imbalance and temporal leakage.

The requirements lock is manually pinned; installation and pip check passed in
cloud on 2026-10-14. It has no artifact hashes yet. Capture a
hash-based lock for stronger supply-chain reproducibility. CI actions use major
version tags; immutable action SHAs are a later hardening step. OS packages are
not fully locked, so byte-identical environments are not promised.
