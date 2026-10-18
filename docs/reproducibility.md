# Reproducibility and evidence boundaries

The project preserves fixed chronological splits, explicit domain targets, bounded
candidate grids and independent seeds. Code/configuration/dependency/input hashes,
source/license review, versions, artifact inventories and phase status accompany
private runs. Corrected or changed code creates a new run key rather than silently
reusing stale checkpoints. Interrupted stages restart; corrupt inventories fail
closed. Cloud guides document storage and cleanup.

## What is reproducible

- Generated-fixture tests and submission integrity audit need no external dataset.
- Free public GitHub jobs acquire the reviewed original Elliptic release and run
  the fixed real-data protocol, subject to source access/terms/free runner capacity.
- The independent banking generator records source fingerprints, sizes and fixed
  seeds 0/1/2. It does not claim to execute official AMLSim.
- Bundled domain snapshots and Spark benchmark JSON are protected by SHA manifests;
  each research snapshot records its successful source workflow and archive digest.
- `python scripts/audit_submission.py --write-results` regenerates the submission
  results table without training; CI rejects drift from preserved snapshots.
- `python dashboard/render_report_figures.py` renders the report figures from
  aggregates in the full managed cloud environment. The UI-only host reads PNGs.

## Chronological and numerical guarantees

Training fits preprocessing/models on train rows only. Validation AP selects
candidates, validation labels select thresholds, and identical within-domain test
cohorts support ablations. Unknown Elliptic labels are excluded; bank SAR labels
are simulation involvement. Feature observation cutoffs are explicit and tested.
Prior test inspection means these are not untouched external confirmation cohorts.

Row order, seeds and forest inference accumulation are controlled. Different CPU,
Spark summation order or library versions can still alter tied scores or thresholds.
For example, a verified Phase 6 banking rerun changed one threshold by about
2.8e-15 with identical predictions and reported scores. Bitwise model or complete
floating-point identity across machines is not promised. Paired intervals over ten
periods are exploratory; three synthetic seeds do not establish population efficacy.

## Environment and publication limits

Python 3.11–3.13 / Spark 4.0.1 / Java 17 or 21 are the supported configuration;
GitHub CI uses Java 21. Requirements are version-pinned but lack artifact hashes.
CI actions use major tags and OS packages are not fully locked. A stronger
hash-based lock and immutable action SHAs are future supply-chain hardening;
no hermetic or security-certification claim is made.

Private raw data, features, models and prediction arrays remain outside Git/public
artifacts. Only allowlisted aggregate reports/figures are published. GitHub artifacts
expire after seven days; the curated metric snapshots, tables and figures remain
versioned. Aggregate integrity checks establish internal consistency, not independent
publisher authentication or recomputation of AP from absent raw scores.

The public dashboard is not deployed/verified; external free-hosting authorization
is still needed. Actual hosted Colab/Drive execution is not verified. No multi-worker
cluster, production validation or official AMLSim execution is claimed. See
[methodology](methodology.md), [audit](submission-audit.md), [data terms](data-sources.md)
and [cloud execution](cloud-execution.md).
