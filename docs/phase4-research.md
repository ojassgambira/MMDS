# Phase 4 research protocol

This is a bounded offline study on the original Elliptic release, following merged
PR #11 (`16c4156`). It runs automatically in the existing public repository's free
standard GitHub-hosted Linux workflow. No Colab session, GPU, credentials, paid
services or local computer is required. Use **Actions → Unattended real-data
training → Run workflow** for an optional repeat; pushes, pull requests and the
weekly schedule already run it automatically.

## Fixed evaluation and baseline

The protocol is fixed before this round's real-data execution: train steps 1–34,
validation 35–39, test 40–49, seed 0. Unknown labels never become negatives.
All ablations use identical sorted transaction IDs, labels and chronological rows.
The preserved transaction-only model is exactly PR #11's unweighted histogram
booster: train-fitted StandardScaler, 150 iterations, 15 leaves, learning rate .08,
L2 1, no early stopping. Its threshold is recomputed using the unchanged validation
F1/5% FPR rule. Prior test AP was .652145; this is a reproducibility reference,
not a target used to tune this round. No deployment-baseline replacement occurs.

The other seven fixed families each use the existing five-candidate grid: balanced
logistic C=.1/1, balanced-subsample 128-tree depth-12 forest, and unweighted/balanced
histogram boosting. Total **36 fits**, plus the unchanged Phase 3 comparison.
Winner selection uses validation average precision only; test scores never alter
candidate selection or thresholds. Fixed-.5 metrics and confusion matrices remain
available. A validation FPR cap does not promise that cap under test distribution
shift. All candidate warnings and timings are recorded.

## Underperformance hypotheses and audit

- **Direction:** source→target Bitcoin flow is distinct from its reversal. Compute
  both PageRanks and remove both in the `without_direction` ablation. Directional
  degree features remain, so this isolates PageRank, not all direction information.
- **Disconnected times and availability:** audit same-/cross-step edges, backwards
  edges and self loops. Transactions have no persistent wallet identity. Historical
  transaction/account activity cannot be reconstructed from this release.
- **Labels:** record historically known neighbor coverage. Only known training
  labels from strictly earlier steps may enter that statistic. Unknown neighbors
  do not count as negative. Validation/test labels never enter features. Prior-step
  label availability is assumed, not established by the publisher; if cross-step
  edges are absent, these predictors are exactly zero and provide no benefit.
- **Leakage:** each focal node uses the graph prefix ending at its own source
  step, never later edges/nodes. Same-step structure is explicitly available only
  after that entire sampled step completes, not at broadcast-time detection.
  A neighbor's new relationships cannot retroactively change an earlier prediction.
- **Feature quality:** publish train/test moments and zero fractions for every
  feature, plus per-step AP. This exposes constant history features and population
  shifts. Compare graph/rolling-only with transaction-plus-graph/rolling and union.
  These are diagnostics, not proof that any one factor caused poor performance.
- **Publisher attributes:** retain only the 93 publisher-designated local numeric
  attributes. Exclude all 72 anonymous forward/backward aggregates. Exact local
  attribute construction, normalization and live availability remain unverified.

## Feature definitions

Spark performs distributed ingestion, source/relationship validation and the
existing completed-step feature computation. A separate bounded sparse SciPy pass
consumes those verified Parquets (maximum 300k nodes / 500k edges, unchanged upstream
byte/time limits). For each step it computes the whole visible prefix, then emits
values only for the focal step's nodes. Earlier focal features are frozen.

- Forward/reverse PageRank: damping .85, 30 fixed iterations, dangling-mass
  redistribution, multiplied by visible node count. This is a fixed approximation,
  not a convergence claim.
- Weak components: size, directed edge density, mean total degree and source/sink
  fractions. No component IDs are predictors.
- Communities: eight synchronous majority-label sweeps with self votes,
  lexicographic transaction-ID tie order, no random seed dependency. Size, mean
  degree and internal-edge fraction are emitted; community IDs are excluded.
  This bounded heuristic can oscillate or partition poorly; no optimality claim.
- Historical label context: count and illicit fraction of distinct adjacent known
  training nodes from strictly earlier steps. No own-step label propagation.
- Rolling population mean/std and absolute standardized anomaly `(abs(x-mean)/(std+1))`
  for in/out/total degree and the first eight local numeric attributes. Window is
  `[step-5, step)`, weighted by transactions; empty history is zero. These are source
  step units, not daily windows or individual wallet histories. The anomaly score
  is unsupervised context, not an independently calibrated fraud probability.

Families: preserved transaction-only, advanced graph, rolling temporal,
transaction+graph, transaction+rolling, union, union minus PageRanks, union minus
component/community statistics. This is an ablation study, not an exhaustive search.

## Evidence, uncertainty, scalability and persistence

`research-report.md` contains tables and a standalone Matplotlib figure
`research-results.png`. `training-summary.json` includes all Phase 4 metrics,
feature quality, all 49 prefix timings, candidate logs, per-step AP and paired
uncertainty intervals. The evidence manifest hashes every public file.

For each comparison, resample the ten held-out source steps with replacement using
500 seeded **paired** bootstrap draws. Report percentile 95% intervals for model
minus baseline AP/F1/recall/FPR, skipping single-class resamples and reporting the
valid count. A source step is the cluster unit; this better reflects dependence
than independent transaction bootstrap but only ten units remain. Intervals are
exploratory, not corrected for multiple comparisons. The test period was inspected
in prior PRs; this is not an untouched external lockbox. A favorable point estimate
alone is not a statistically established improvement.

Prefix node/edge/time measurements provide a modest observational scalability
benchmark, with warmed/cold allocation and graph composition confounded. They are
not extrapolated into production throughput. Worker remains limited to 30 minutes,
8 GB workspace, 2 GB free disk reserve, two CPU threads, Spark 2 GB heap; hosted
job timeout remains 40 minutes. No dataset security limits are loosened.

Hash-verified stage and per-trial checkpoints resume within retained private
workspaces. Prediction arrays, source rows, Parquets, models and full logs remain
private to the ephemeral runner and are deleted on job completion. Only aggregate
reports/plots are uploaded, with seven-day retention; no public dataset/model cache.
Cross-job private persistence requires separately authorized storage. No new external
authentication is currently needed for the authorized public PyG source. Publisher
license/version/size review still runs before acquisition and fails closed on changes.
