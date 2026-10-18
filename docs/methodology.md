# Research methodology

## Questions and experimental unit

1. Does graph/temporal context help retrospective Bitcoin illicit-transaction
   classification beyond released local transaction attributes?
2. Does account graph/temporal history help forecast next-day simulated SAR
   involvement in an independently generated banking ledger?
3. What processing costs are actually observed on bounded free-cloud workloads?

The questions share engineering, not labels. Elliptic observations are individual
transactions; banking observations are persistent-account/forecast-day pairs.
No shared fraud score, cross-domain ranking or transfer-learning claim is made.

## Data and provenance

Real Elliptic has 203,769 transactions, 234,355 directed links, 49 released steps,
4,545 illicit, 42,019 licit and 157,205 unknown labels. IDs are joined explicitly;
unknowns participate only in graph structure, never as negative supervised labels.
All numeric features, file schemas, counts and endpoints are validated.

Banking is independently generated, AMLSim-compatible **synthetic** data, not official
IBM output or real bank fraud. Three fixed seeds yield 500 accounts, 33,600 payments
and 24,500 account-days each. Labels indicate same-day simulated SAR involvement;
missing labels are rejected. Payment multiplicity is retained. The official
simulator's legacy dependencies were reviewed and not executed.

## Feature timing and graph quality

Elliptic is retrospective: source-step transactions and edges are visible after
that step completes. No within-step/live ordering is known. Research uses 93 local
source attributes and excludes 72 anonymous publisher neighborhood aggregates;
local construction/normalization availability is not independently established.
Directional PageRank, weak components, bounded communities, degree statistics and
rolling population anomalies use explicit prefixes. All released edges are within
a step; no persistent wallet history can be inferred. Historical neighbor label
features have no available labeled neighbors and remain zero. These facts help
explain weak graph-only/temporal performance without assigning unsupported causality.

Banking features for forecast day t use only payments on days **< t**: previous-day
activity/amounts, historical directed weighted PageRank, weak components,
community structure, rolling windows and anomaly summaries. IDs, account metadata,
SAR flags and alert identifiers are excluded from predictors. All accounts exist
by day zero; evaluation forecasts known accounts rather than unseen customers.

## Identical chronological evaluation

Both domains use train periods 1–34, validation 35–39 and held-out test 40–49.
Banking day zero supplies history. Neither splits randomly nor fits transforms on
the test cohort. Elliptic known-label split sizes are 29,894 / 5,486 / 11,184;
banking account-day splits are 17,000 / 2,500 / 5,000 per seed.

Transaction-only, graph-only, temporal-only and combined families use identical
within-domain rows and splits. Fixed bounded grids include class-imbalance
handling; the frozen best transaction baseline is retained. Validation AP selects
candidates; validation F1 under 5% validation FPR sets operating thresholds. This
cap is not a guarantee of test FPR. Test scores are descriptive after selection.
Phase 4 adds directional/component/community/rolling ablations; Phase 5 also
compares unsupervised Isolation Forest. Its transformed anomaly score is not a
calibrated fraud probability. Earlier initial graph baselines use fixed 0.5 thresholds;
they must not be conflated with research comparisons.

## Metrics and uncertainty

Report precision, recall, F1, FPR=FP/(FP+TN), and PR-AUC defined as sklearn
**average precision**, not trapezoidal integration. Confusion matrices use rows
observed, columns predicted and explicit domain-specific binary labels. Dashboard
PR curves are at most 101 sampled actual ranking points; AP uses the full ranking.
Confusion matrices cannot reconstruct AP or complete score rankings.

Five hundred seeded paired period-bootstrap draws compare models on identical test
rows. Ten test periods, persistent accounts, overlapping windows and synthetic
campaign structure limit independence. Intervals are exploratory, uncorrected for
multiple comparisons; prior iterations have already inspected the test period.
It is not an untouched external lockbox. Three predeclared seeds are repetitions,
not candidates selected for their test performance. Banking means are arithmetic
seed means, not pooled customer metrics.

## Scalability protocol and limits

Measured Spark processing covers CSV validation, graph summaries and Parquet
write/read/count at three generated sizes per domain on **one local[2] machine**.
Generation and Spark startup are excluded; the first measured work is cold and
later runs share a warm JVM. One pass per size does not estimate variance or
asymptotic scaling. Sparse CPU graph-prefix timings are reported separately.
No worker-count comparison, distributed multi-worker speedup, peak-memory or
production throughput measurement is claimed. [Exact timings](benchmarks.md).

## Evidence, reproducibility and limitations

Code/configuration/input hashes, dependency versions, seeds and stage inventories
control checkpoints. Rows are sorted before fitting; numerical/platform changes
may still perturb tied scores or thresholds. Curated aggregate hashes verify bytes,
not independent publisher authenticity. Raw data/models remain private.
[Results](results-summary.md), [full report](final-research-report.md),
[reproducibility boundaries](reproducibility.md), [Phase 4 protocol](phase4-research.md)
and [Phase 5 protocol](phase5-banking.md) provide measured evidence and caveats.
