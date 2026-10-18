# Verified results summary

Generated from hash-verified versioned aggregate snapshots by
`python scripts/audit_submission.py --write-results`. No training occurs.

AP is full-ranking average precision; thresholds and models use validation only.
These domains have different populations and targets: do not rank them against each other.

## Real Elliptic Bitcoin

203,769 transaction nodes; 234,355 edges; 157,205 unknown labels excluded from supervision.
Train steps 1–34, validation 35–39, test 40–49 (11,184 known test labels).

| Family | AP | Precision | Recall | F1 | FPR |
| --- | ---: | ---: | ---: | ---: | ---: |
| transaction_only | 0.652145 | 0.837264 | 0.558176 | 0.669811 | 0.006542 |
| advanced_graph | 0.090647 | 0.140845 | 0.141509 | 0.141176 | 0.052048 |
| rolling_temporal | 0.362273 | 0.268326 | 0.610063 | 0.372719 | 0.100303 |
| transaction_graph | 0.654507 | 0.857831 | 0.559748 | 0.677450 | 0.005593 |
| transaction_rolling | 0.658517 | 0.838710 | 0.572327 | 0.680374 | 0.006636 |
| combined | 0.659236 | 0.853147 | 0.575472 | 0.687324 | 0.005973 |
| without_direction | 0.655510 | 0.829932 | 0.575472 | 0.679666 | 0.007110 |
| without_components | 0.657412 | 0.895262 | 0.564465 | 0.692382 | 0.003982 |

Validation-selected family: **without_components**.
Structural additions have uncertain AP gains; exploratory paired intervals do not
establish an overall improvement. Publisher-local feature availability is not independently
verified. This is retrospective completed-step classification, not live fraud screening.

## Independent synthetic banking

Not official IBM AMLSim output or real bank fraud. Positive target: next-day simulated
SAR payment involvement. Three fixed seeds; 500 accounts, 33,600 payments and 24,500
account-days per seed. Test: 5,000 account-days per seed. Features use days strictly before t.

Arithmetic means across seeds (not pooled predictions):

| Family | Mean AP | Mean precision | Mean recall | Mean F1 | Mean FPR |
| --- | ---: | ---: | ---: | ---: | ---: |
| transaction_only | 0.226261 | 0.262554 | 0.415959 | 0.315831 | 0.029754 |
| graph_only | 0.100943 | 0.131310 | 0.104759 | 0.115577 | 0.018879 |
| temporal_only | 0.274448 | 0.289119 | 0.419710 | 0.328378 | 0.027356 |
| combined | 0.432368 | 0.446153 | 0.575433 | 0.501451 | 0.018676 |
| isolation_forest | 0.145012 | 0.169434 | 0.284524 | 0.207695 | 0.037758 |

Combined is validation-selected for all three seeds. Synthetic motifs are intentionally
learnable; these scores do not establish effectiveness on real banks or unseen typologies.

## Evidence and interpretation

- [Real workflow](https://github.com/ojassgambira/MMDS/actions/runs/38904556561); archive SHA-256 `5c4e108c504a69ccaa534dbfe81c66bfde5490be4db9765d12ed50d47bd780b8`.
- [Synthetic workflow](https://github.com/ojassgambira/MMDS/actions/runs/38904556473); archive SHA-256 `d916d492acbd4da67af7db491fef4d834aa4c7207ff03421c66e54db2245745a`.
- Snapshot byte hashes: `dashboard/data/manifest.json`. Source artifacts expire after seven days;
  curated aggregate snapshots, figures and workflow/PR summaries preserve the submission evidence.
- [Full methodology, ablations, uncertainty and limitations](final-research-report.md).
- [Measured single-machine benchmarks](benchmarks.md); no distributed multi-worker claim.
