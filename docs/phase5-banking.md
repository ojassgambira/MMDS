# Phase 5: synthetic banking research

The default workflow generates **independent synthetic banking data**, not real
bank records and **not official IBM AMLSim output**. It implements a bounded subset
of AMLSim's converted CSV contract and evaluates account-level next-day simulated
SAR involvement. SAR involvement is neither confirmed fraud nor evidence that an
account owner committed money laundering.

## Official AMLSim assessment

Reviewed IBM/AMLSim master commit `7338a4bcb1af9bcfea2201ad7daccfe2a4d569ca`:

- [Repository/license](https://github.com/IBM/AMLSim/tree/7338a4bcb1af9bcfea2201ad7daccfe2a4d569ca): Apache-2.0 for the core project.
- [README](https://github.com/IBM/AMLSim/blob/7338a4bcb1af9bcfea2201ad7daccfe2a4d569ca/README.md): documented Python 3.7 / Java 8 stack, legacy graph dependencies, separately supplied MASON 20 and other Java jars.
- [requirements.txt](https://github.com/IBM/AMLSim/blob/7338a4bcb1af9bcfea2201ad7daccfe2a4d569ca/requirements.txt): NetworkX **1.11**, matplotlib **>=3.1.2**. The README instead lists matplotlib 2.2.3; the disagreement is recorded rather than treating either as a modern tested lock.
- NetworkX 1.11's `networkx/algorithms/dag.py` imports `fractions.gcd`, removed
  from current Python. Reproduced the ImportError on cloud Python 3.12.14 and
  inspected the pinned upstream source. This project supports Python 3.11–3.13;
  blindly installing that legacy stack into its verified runtime is incompatible.
- No official generator, upstream install script or Java jar was executed. Core
  Apache licensing is not the blocker; legacy dependency compatibility is. No
  claim is made that all external jar licensing or an isolated legacy stack was
  evaluated. Updating the official simulator is a separate migration effort.

The explicitly permitted independent fallback avoids those dependencies, adds
none to the project's existing lock, and records generator/source hashes and seed.
For publications, acknowledge Suzumura and Kanezashi, *Anti-Money Laundering
Datasets / AMLSim*, 2021; schema compatibility does not imply their implementation
produced these simulations.

## One cloud entry point and automation

The public repository's **Synthetic banking research** GitHub workflow runs on
PRs, main pushes and optional Actions dispatch, using free standard Linux,
Python 3.13 and Java 21. It installs the existing lock, runs regression tests and
executes:

```sh
python scripts/run_banking_job.py --workspace "$RUNNER_TEMP/banking-private"
```

Do not execute it on a personal computer. Codex Cloud can execute the same entry
point with a workspace outside the checkout. No Colab session, Google Drive,
Kaggle authentication, GPU or paid service is needed.

`configs/banking-research.json` predeclares accounts=500, 600 normal events/day,
50 days, dataset seeds **0,1,2**. Each seed adds 72 motif payments/day, producing
33,600 transactions and 24,500 forecast account-days. Seeds are repetitions,
not candidates selected by test performance. Bounds: 50–1000 accounts,
50–1200 normal daily events, 100,000 transaction rows, 50 MB per source file,
30-minute elapsed check, 8 GB workspace and 2 GB free-disk reserve. GitHub's job
hard timeout is 30 minutes. Spark heap 1 GB, local[2]; model threads two.

The simulator uses repeated local-community payments, heterogeneous activity,
persistent seven-day suspicious cycles/fan-in/fan-out motifs and benign
lookalikes. Amount distributions overlap, late amounts shift modestly, and not
every suspicious-pattern payment is flagged. IDs, CSV ordering, transaction type,
alert IDs, account metadata and SAR flags cannot enter model feature matrices.
These mechanisms deliberately create learnable synthetic structure; there is no
claim that they match empirical bank distributions or unseen laundering methods.

## Input contract and validation

Default generated files are outside Git:

- `accounts.csv`: `acct_id` (a minimal subset of the converted schema).
- `transactions.csv`: `tran_id,orig_acct,bene_acct,tx_type,base_amt,tran_timestamp,is_sar,alert_id`.
- `provenance.json`: independent generator version, seed, sizes, SHA-256 fingerprints,
  upstream schema-review commit and explicit `official_amlsim_output=false`.

`--input /cloud/path/to/converted-csvs` accepts an already authorized compatible
external directory with a one-seed config. It labels provenance
`external_amlsim_compatible_unverified`; it does not authenticate that IBM's
simulator produced it. Compatible external CSVs are not silently relabeled as the
independent generator or real banking data. No automatic external download occurs.

The supported experiment contract requires a complete ledger on UTC days 0–49,
a known account registry by the 2017-01-01 base date and explicit `is_sar`
true/false values. Missing labels are rejected. If `open_dt` is present, malformed
or future dates are rejected. Other schemas/time ranges require an explicit
adapter rather than guessing. Generated data satisfies this contract.

Existing Spark banking validation checks headers, identifiers, conflicting
transaction IDs, finite nonnegative amounts, UTC timestamps, account endpoints,
row/byte limits and day range. Conflicting duplicate SAR labels are separately
rejected. Exact duplicate IDs are deduplicated, while **different IDs connecting
the same accounts retain their event multiplicity**. Account/day row counts,
finite features, Parquet round trips and stage hashes are validated.

## Causal features and evaluation

For forecast day t, every feature uses only transactions with day **< t**;
`feature_cutoff_exclusive=t`. The target is involvement (source or destination) in
at least one flagged SAR payment during day t. Account activity counts self
transfers once, while directed flow counts one incoming and one outgoing event.

- Transaction-only: preceding-day payment count, total amount, mean and std,
  aggregated over the account's incoming and outgoing events.
- Graph-only: cumulative incoming/outgoing event counts, distinct counterparties,
  forward/reverse weighted PageRank (30 fixed iterations, damping .85), weak
  component size, reciprocal-neighbor fraction. Counts/weights retain multiplicity;
  topology summaries use unique neighbors. IDs are not predictors.
- Temporal-only: trailing-seven-day count and volume, prior-day volume divided by
  older seven-day average, an older-window standardized amount anomaly and active
  days. Anomaly reference is `[t-8,t-1)`, excluding the preceding-day observation;
  trailing aggregates use `[t-7,t)`. Empty history becomes zero. These are simulation
  days, not Elliptic released steps.
- Combined: union of the three disjoint named feature sets.

Days 1–34 train, 35–39 validation, 40–49 test. All four families use the same
sorted account-day IDs, labels and splits. Repeated accounts across periods are
intentional: future behavior of known accounts, **not** unseen-account evaluation.
No actual current/future SAR labels are predictors. Static account labels such as
`prior_sar_count` are ignored. Source files must be complete: no observed SAR event
means target-negative under this contract, not unknown real-world innocence.

Each family uses the existing five fixed candidates: balanced logistic C=.1/1,
128-tree depth-12 balanced-subsample forest and unweighted/balanced histogram
boosting (150 iterations, 15 leaves, learning rate .08, L2 1, no early stopping).
Train-fitted scaling; model seed zero. Per-family/global selection uses validation
average precision only. Threshold maximizes validation F1 under 5% validation FPR;
no test guarantee. Fixed-.5 metrics, precision/recall/F1/AP/FPR/confusion matrices,
fit times and warnings remain available. Twenty supervised fits plus one anomaly
fit per simulation seed, no adaptive test-driven search.

Isolation Forest (128 trees, max_samples256) fits all training rows without labels.
Sigmoid of negative decision_function preserves its ranking and bounds scores;
it is not calibrated fraud probability. Validation labels choose its threshold;
test data never calibrates the scaler, detector or threshold. Self-owned model
round trips are verified; external pickle/joblib inputs are never loaded.

## Research evidence, uncertainty and comparison

Four allowlisted aggregate files are uploaded for seven days: `banking-summary.json`,
`banking-report.md`, `banking-results.png`, `banking-evidence-manifest.json`.
They include seed-level metrics, source/feature/model hashes, stages, all 49 prefix
benchmarks, 500 paired target-day bootstrap intervals and preserved real Elliptic
reference metadata. Plot bars show seed means; whiskers show seed ranges, not
confidence intervals. Account/transaction records, per-row predictions, models
and full logs stay private and are deleted after the hosted job.

Prefix time/event/unique-pair benchmarks are observational scalability evidence
on the tested runner, not a controlled throughput extrapolation. Ten test-day
clusters and overlapping windows limit bootstrap independence; intervals are
exploratory with no multiple-comparison correction. Multiple synthetic seeds do
not establish real-world efficacy.

`configs/elliptic-reference.json` records the **previously verified real** PR #12
baseline, workflow and evidence hash. Its predictive unit, target and time semantics
differ from banking. Reports compare domain structure and display the verified
reference metrics without treating scores as directly comparable, asserting
cross-domain transfer or overwriting any Elliptic result.

Within retained private storage, source/preprocess/features/models/statistics
stages and individual supervised trials resume with hashes. Input/code/config/
dependency changes create a new run identity; modified completed stages fail closed.
Interrupted uncommitted stages restart. Per-seed status records name the failing
stage and preserve the exact original traceback in the private cloud job log.
Fresh hosted jobs do not reuse public data/model caches.
