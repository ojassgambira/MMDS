# Presentation-ready explanation and demonstration

Suggested duration: 8–10 minutes. Figures are in `docs/figures`; the final report
and generated results table accompany the presentation. Do not introduce a live
Colab run or new training during the demonstration.

## Slide 1 — Research goal (45 seconds)

“MMDS investigates how graph structure and transaction history contribute to
financial suspicious-activity detection. It compares a real Bitcoin release and
an independent banking simulation through reproducible cloud pipelines.”

State immediately: the banking labels are simulated SAR involvement, not confirmed
fraud; the two domains' scores cannot be directly ranked.

## Slide 2 — Data and targets (60 seconds)

Show the domain table in the [README](../README.md). Elliptic has 203,769
transactions and 234,355 directed links; 157,205 unknown labels are excluded from
supervision. Banking has persistent account nodes, repeated payment events and
three fixed simulation seeds. Explain transaction nodes versus account nodes.

## Slide 3 — Architecture (60 seconds)

Show the [architecture diagram](architecture.md): domain adapters, Spark validation,
time-bounded feature construction, chronological fitting, private checkpoints,
aggregate publication and read-only UI. Explain that Spark processing and sparse
single-host graph mining are separate stages. No multi-worker claim is made.

## Slide 4 — Leakage and evaluation (60 seconds)

Show train 1–34 / validation 35–39 / test 40–49. Elliptic uses completed-step
retrospective information; banking forecasts day t using only days < t. Models,
scalers and thresholds never use held-out test labels for selection. Prior
research iterations have inspected the test period, so it is not a fresh lockbox.

## Slide 5 — Elliptic results and ablation (75 seconds)

Use [Elliptic figure](figures/elliptic-evaluation.png) and [results table](results-summary.md).
The validation-selected model has AP 0.657412 and F1 0.692382. The frozen
transaction baseline AP is 0.652145; exploratory paired AP/F1 intervals include
zero. Do not describe that difference as established improvement.

Explain why graphs underperform: no cross-step links, no wallet identity/history,
zero available labeled historical neighbors, redundant degree context and late
population shift. Publisher-local feature causality is not independently verified.

## Slide 6 — Synthetic banking findings (75 seconds)

Use [banking seed 0 figure](figures/banking-evaluation.png); explicitly label it
seed 0 rather than the mean. Combined is validation-selected for all seeds; mean
AP 0.432368 and F1 0.501451. Test AP varies about 0.282–0.550 across seeds.
Recurring simulated account motifs make temporal/combined models useful here.
This is a synthetic design finding, not real-bank performance or transferability.

## Slide 7 — Measured processing (45 seconds)

Show [Spark figure](figures/spark-processing.png). One machine, Spark local[2],
1 GB heap, two shuffle partitions, generated workloads. The smallest Bitcoin
measurement includes cold work and takes longer than larger warm passes. Explain
warm-up and single-repetition limitations rather than inferring reverse scaling.

## Slide 8 — Dashboard demonstration (90 seconds)

If an authorized free hosted URL is available, open it in a browser; otherwise use
the checked-in figures/report. No public URL is currently verified.

1. Choose Elliptic: show dataset statistics, target semantics and evidence provenance.
2. Open graph explorer; say “generated illustration,” then use time/focus controls.
3. Show chronological patterns, a confusion matrix and measured PR curve.
4. Switch to synthetic banking; compare seeds without choosing one by test quality.
5. Show benchmark configuration and research limitations.

The app reads aggregates; it does not download data, train or load pickle files.
Private operator-provided graphs are unverified source assertions and require
separate display authorization. Never expose private account records in a demo.

## Slide 9 — Engineering validation (45 seconds)

Show the successful PR's GitHub checks: supported Python matrix, dataset-free
regressions, real release job, synthetic replicas, lightweight dashboard and
actual Spark benchmarks. Explain checksum checkpoints, bounded resources and
sanitized public artifacts. A test success is not a real-data success; the latter
has separate source manifests and execution evidence.

## Slide 10 — Conclusion and honest limits (45 seconds)

“The deliverable is a reproducible, separate-domain research architecture with
verified evaluation and measured single-machine processing. Real Bitcoin evidence
supports modest, uncertain structural gains; synthetic banking shows benefits
from recurring history under simulation assumptions. Independent banking data,
a new untouched cohort and a real multi-worker cluster are future research.”

## Likely questions

- **Is this production-ready?** No: label delivery, distribution shift, calibration,
  compliance, privacy and operational validation are outside the measured scope.
- **Why no GNN?** The project prioritizes bounded interpretable graph features,
  chronological baselines and reproducibility on free CPU resources.
- **Why not official AMLSim?** Its reviewed legacy dependencies conflict with the
  supported stack. Independent generation is explicitly documented, not relabeled.
- **Are the graph examples real?** Default UI graphs are illustrations. Model
  metrics come from separately verified real/synthetic execution artifacts.
- **Can I reproduce without a Mac workload?** Yes, through free public GitHub
  workflows or an authorized hosted cloud; optional Colab requires account consent.
