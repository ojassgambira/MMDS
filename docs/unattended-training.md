# Unattended real-data training (Issue #9)

The free GitHub-hosted workflow `Unattended real-data training` executes the real
original Elliptic pipeline automatically on pull requests and pushes to main.
After merge, it also runs Mondays at 04:17 UTC and offers **Actions → Unattended
real-data training → Run workflow**. Full release is the default; the optional
`data_mode` selector chooses an explicitly labelled correctness sample. There is
no code editing, cell ordering, Mac execution, Drive credential or Kaggle secret.
Schedules run the default branch and may be delayed or disabled by GitHub after
repository inactivity; this is a batch workflow, not a persistent service.

The job runs only for this **public repository**, on a standard GitHub-hosted
Ubuntu Linux runner. The script independently checks the hosted-runner/public
repository markers. It refuses Codex Cloud dataset downloads, Colab/self-hosted
execution and private-repository training in this entry point. No larger runner,
GPU, paid storage or cloud account is provisioned. Existing Colab/private-storage
execution remains available separately through `scripts/run_cloud.py`.

## Before processing

The job installs the pinned Python 3.13 dependencies, Java 21, and editable project,
then checks pip consistency. Its cloud entry point is:

```bash
python scripts/run_training_job.py --workspace "$RUNNER_TEMP/mmds-private" \
  --evidence "$RUNNER_TEMP/mmds-public" --data-mode full
```

This command is intended only for GitHub-hosted CI, never a local device. It checks
at least 6 GB free disk, publisher metadata (at most 256 KiB, 30-second timeout),
license CC BY-NC-ND 4.0, original release version 1 and 697,459,499-byte total.
Three bounded ZIP-tail requests must match the previously reviewed original ZIP
sizes/member sizes/CRCs. A change in terms, version or measured release metadata
stops acquisition for review. Integrity metadata is not a publisher signature.
The authorized use is noncommercial university research; dataset/model files are
not redistributed as public GitHub artifacts.

The worker runs Ruff, the entire generated-data regression suite and Spark smoke
before downloading data. Acquisition retains the independent 200 MB compressed,
750 MB expanded and 600-second limits from Issue #7. No failed source request is
silently retried, and the job never substitutes a sample or fixture after failure.
Every full run validates all numeric source features, IDs, widths, label alignment,
edge endpoints, original counts and steps. Samples audit the complete source
schema/IDs/counts/relationships and validate sample numeric values in Spark.

## Prediction timing and reproducibility

The task is retrospective classification after each transaction's discrete source
step completes. Six graph predictors use only edges with availability before
`transaction_step + 1`; later edges cannot change an earlier transaction's
features. Same-step information is allowed under this end-of-step assumption.
Anonymous publisher aggregates, transaction IDs, absolute time and labels never
enter predictors. Unknown labels participate only in graph structure and are
excluded from supervised fitting and metrics. Offline training-label availability
is assumed; live label delivery is not established by this dataset.

Train steps 1–34; validation 35–39; held-out test 40–49. Scaling and fitting use
training only. Prior dummy, balanced logistic regression (1,000 iteration cap)
and a 64-tree, depth-8 balanced forest are the only baselines. Validation average
precision selects the learned model before any test evaluation. The fixed 0.5
threshold is never tuned on the test period. Both labels must exist in every split.

Metrics: precision, recall, F1, PR-AUC defined as **average precision**, false
positive rate **FP/(FP+TN)**, confusion matrices and split/class counts. Matrices
use rows=true, columns=predicted, order [licit=0, illicit=1]. Per-model fitting
seconds and parameters are recorded. Serialized models must reproduce validation
probabilities within numerical tolerance before the model stage is committed.
Rows are sorted by step then lexicographic transaction ID before seeded fitting;
forest inference uses sequential accumulation to avoid scheduling-dependent score
ties. Package/Python versions, code fingerprints, configuration, source hashes,
stage hashes and artifact sizes are recorded. Exact floating-point/serialization
identity across hardware or library releases is not promised.

Full-release and induced-sample results have distinct dataset-kind labels. A
sample is biased by source order and graph induction and must not be described
as a full-population estimate. Synthetic regression metrics are never reported
as real fraud metrics. Observed performance is a research baseline, not evidence
of deployment readiness or a live label-availability guarantee.

## Resource bounds, checkpoints and diagnosis

Two Spark CPU workers, 2 GB medium-profile driver heap, bounded row/byte profiles,
and two model fitting threads; forest inference uses one. The job supervisor
checks elapsed time, workspace size and remaining disk every two seconds. It
terminates the worker process group after 1,800 seconds, above 8 GB workspace,
or below 2 GB free disk. Acquisition/processing have additional earlier guards.
The hosted job has a 40-minute overall limit, including dependency setup. These
are process/resource budgets, not reserved or guaranteed free-tier capacity.

Stages record their active name before work starts, so abrupt termination still
identifies the last stage. Completed checkpoints are hash-verified; incomplete
stages restart and changed code/configuration/dependencies create a new run key.
Failures retain their stage, cause and timing inside the runtime workspace.
There is no automatic failed-run retry or model-size escalation.

A retained workspace can resume on another invocation. Fresh GitHub-hosted jobs
start without previous private data/models; public Actions caches/artifacts are
not used to persist licensed datasets or models. Existing authorized private
filesystem/Drive storage through `run_cloud.py --storage` supports cross-session
checkpoint restoration. Such storage is optional and is not provisioned by CI.

Public reports include aggregate validation/metrics, package versions, stage
seconds, and artifact path/size/SHA-256 inventories. Public diagnostics classify
known failures (source authorization, changed terms/release, heap, disk, timeout,
split-class shortage or corrupt checkpoints) and retain safe code-frame locations.
Arbitrary exception payloads and Spark CSV rows stay in private runner logs. No
raw CSV, Parquet, model, credential or full runtime log is uploaded publicly.
The evidence manifest hashes both public report files. Unexpected files or
symlinks in the public evidence directory stop publication. On job completion or
failure, private data/models/checkpoints/logs are removed; hosted runner teardown
also discards them if the job is forcibly stopped. Reports expire after seven days.

## Authorization boundary

This GitHub workflow needs no Colab session, Google OAuth or private Drive access.
The existing authorized GitHub connection and public mirror suffice. Weekly
execution becomes active only when the workflow is on main; PR tests verify the
same workflow before merge. This task does not merge the PR.

If private Colab/Drive persistence is chosen separately, Google sign-in, connecting
a free hosted runtime and authorizing Drive are external interactive actions.
Consent may need renewal after runtime/account changes. Repository automation
cannot start/control the user's private Colab session or grant OAuth. No manual
code edits, log copying or Colab debugging are required by the GitHub workflow.

## Execution evidence

Real model metrics are claimed only in a completed workflow's aggregate report.
The PR records measured results and CI links after actual execution. Code and
synthetic test success alone do not establish real training or Colab execution.

## Feature-family experiments

The hosted job now also runs [the predeclared feature comparison](feature-comparison.md):
transaction-only, graph mining, temporal context and combined predictors, with
training-only imbalance handling, validation-only model/threshold tuning and
separate test metrics. The original three baselines remain in the report.
