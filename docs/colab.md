# MMDS: one-command cloud execution

The notebook now has one execution cell. Open it in a **free hosted Colab CPU**
runtime and select **Runtime → Run all**. It automatically loads the automation
branch before merge (main if that branch has been deleted), installs dependencies
in an isolated environment, runs tests, acquires the original Elliptic release,
validates/preprocesses it in Spark, builds temporal graph predictors, trains three
bounded baselines, computes metrics and writes a report. No workload runs on your
Mac or iPhone, and no paid compute or storage is provisioned.

[Open the notebook](https://colab.research.google.com/github/ojassgambira/MMDS/blob/automation/run-all/notebooks/MMDS_Cloud_Pipeline.ipynb).
After branch deletion, open the same notebook from main through Colab's GitHub tab.

## Browser instructions and unavoidable actions

1. Sign in to Google, open the notebook, select a hosted Python CPU runtime, and
   connect. On iPhone, Safari → Request Desktop Website and landscape orientation
   can make menus easier to use. Keep the tab active during execution.
2. Review the publisher's terms for this private noncommercial university analysis.
   The repository records CC BY-NC-ND 4.0. Do not redistribute raw/derived artifacts.
3. Select **Runtime → Run all**. No code editing or manual cell ordering is needed.
4. Authorize Google Drive when Colab prompts. The default private destination is
   `My Drive/MMDS/automated`. The optional form selector offers temporary Colab
   storage instead; it disappears on reset. Check your existing Drive capacity;
   do not purchase storage for this workflow. Allow roughly 3 GB free in both
   runtime and persistent storage for raw data, processed tables and copies.
5. Read the report displayed at completion. Persistent reports and artifacts are
   under `MMDS/automated/runs/<run-key>`. The report/manifest must say `success`;
   a directory or a partial checkpoint alone is not a successful execution.

Google account sign-in, connecting a hosted runtime, Drive consent and accepting
any publisher terms cannot be automated by repository code. A free runtime can
be disconnected or reclaimed. Run all again to restore verified checkpoints;
there is no guarantee of uninterrupted free compute or sufficient runtime quota.

## Python and dependency compatibility

The old notebook required exactly 3.12 while `pyproject.toml` excluded 3.13. The
new supported range is **Python 3.11–3.13**, with Java 17 or 21 and Spark 4.0.1.
The code uses no 3.12-only syntax. The dependency set supports these interpreter
versions and a GitHub matrix installs it and executes the complete test suite,
including Spark and generated-data baseline training, on all three versions.
See [verification evidence](automation-verification.md) for actual results.

`requirements-cloud.lock` includes the existing development pins and NumPy 2.2.6,
SciPy 1.15.3, scikit-learn 1.7.2, joblib 1.5.2, threadpoolctl 3.6.0 and PyArrow 20.0.0.
The entry point creates a virtual environment with the current interpreter and
runs `pip check`. Colab's globally preinstalled packages are untouched, and no
kernel restart is needed. Java is checked before work. A future Python 3.14+
runtime is deliberately unsupported until tested; select a compatible Colab
runtime rather than deleting the version check. No downgrade is performed.

## Single entry point and optional configuration

In an approved cloud shell (never a local device):

```bash
python scripts/run_cloud.py --workspace /workspace/mmds-run \
  --storage /workspace/mounted-private-storage
```

`--storage` is optional and must be an existing authorized filesystem/mount path.
It does not provision cloud services. Google Drive is mounted by the notebook.
Temporary processing happens in `--workspace`; data/models remain outside Git.
Dependencies install automatically. The worker runs Ruff, pytest and Spark smoke
before acquisition. Worker execution is bounded to one hour, two Spark CPU
workers, medium-profile source limits and 64 depth-limited forest trees.

Defaults are in `configs/cloud-pipeline.json`: full original release, PyG mirror,
train through step 34, validation through 39, fixed seed 0. Optional JSON can be
passed with `--config`, or selected using the notebook form's `config_path` field.
No edits are required for the defaults. An existing authorized source example:

```json
{
  "source": "existing",
  "input_directory": "/content/drive/MyDrive/MMDS/elliptic",
  "data_mode": "full",
  "train_end": 34,
  "validation_end": 39,
  "seed": 0,
  "master": "local[2]"
}
```

`data_mode: sample` with `sample_per_step: 200` selects up to 9,800 transactions
and at most 10,000 induced edge records. Source counts are audited, and the sample
must have both classes in each fixed split. If not, execution fails explicitly;
it never silently adjusts test boundaries or substitutes synthetic data.
Default full processing avoids sampling bias for the initial baseline.

## Acquisition and authentication

Source: [publisher's original Elliptic release](https://www.kaggle.com/datasets/ellipticco/elliptic-data-set).
Automatic acquisition uses its documented [PyG mirror](https://data.pyg.org/datasets/elliptic),
with no Kaggle credential. The existing downloader caps total compressed bytes at
200 MB and expanded bytes at 500 MB, validates archive structure, rejects
unexpected redirects, records SHA-256 provenance and publishes only complete
acquisitions. No denied destination is retried or bypassed. Mirror availability
is established only by an actual successful run; it is not guaranteed by code.

Codex Cloud dataset downloads remain disabled per the user's earlier instruction.
Development uses generated fixtures. If Colab cannot access the mirror, the report
records failure. Supply authorized publisher CSVs in private Drive via `existing`.
The expected filenames are `elliptic_txs_features.csv`, `elliptic_txs_classes.csv`
and `elliptic_txs_edgelist.csv` directly inside `input_directory`.

If using Kaggle's official client separately, accept its terms and store required
`KAGGLE_USERNAME`/`KAGGLE_KEY` in **Colab Secrets**; retrieve via `userdata.get`
into runtime memory and pass to that client's environment only. Remove bindings
after use. Never hardcode credentials, print them, save them in Drive, or commit
`kaggle.json`. Kaggle sign-in/authorization is manual when that alternative is
needed. The workflow does not invoke an unbounded Kaggle download or claim that
client authentication has been tested.

## Validation, prediction timing and evaluation

Spark validates all source feature widths/numeric values, transaction identities,
class alignment, finite values, label vocabulary, source steps and edge endpoints.
The full release must have 203,769 nodes, 234,355 directed edges, 4,545 illicit,
42,019 licit and 157,205 unknown labels, covering steps 1–49. Parquet outputs are
read back and their counts verified. Normalized duplicate semantics remain those
of Phase 2: simple Bitcoin edges, conflicting transaction records rejected.

The new task is **retrospective classification after a transaction's source step
completes**, with one example per transaction. Each predictor uses edges with
`available_step < time_step + 1`; a future edge cannot change an older example.
Same-step edges are allowed only under this explicit end-of-step assumption.
Predictors are in/out/total degree, distinct neighbor count, past-neighbor count
and same-step-neighbor count. The full-graph descriptive features remain separate.
All 165 anonymous source features, IDs, absolute time and labels are excluded
from the model's feature matrix. Unknown nodes can participate in graph structure
but never become negative supervised examples. Steps are discrete Elliptic units,
not inferred calendar dates or known within-step transaction timestamps.

Train: 1–34. Validation: 35–39. Test: 40–49. All scalers and models fit only training
rows. Baselines are a prior dummy classifier, balanced logistic regression and a
64-tree, depth-8 balanced random forest. The better learned model is selected by
validation average precision before test evaluation. Threshold is fixed at 0.5;
there is no test-based threshold tuning, shuffling or large hyperparameter search.
Each split must have both known classes; otherwise metrics are not fabricated.

Metrics include precision, recall, F1, **PR-AUC defined as average precision**, and
2×2 confusion matrices (rows=true, columns=predicted; licit=0, illicit=1). Reports
include split counts, unknown exclusions and measured stage timings. Test metrics
for all baselines are descriptive comparisons; model selection uses validation
only. Offline labels are assumed available for training before later periods;
the dataset does not establish real-time label delivery. These are research
baselines, not deployment or production accuracy claims.

## Checkpoints, outputs and failures

A run key includes code/configuration fingerprints, Python/dependency versions,
and hashes for provided CSVs. Source provenance and hashes are rechecked on every
resume. Completed stages have full artifact hash inventories; corruption fails
closed. Matching Drive checkpoints restore into temporary runtime storage.
Interrupted stages restart from their stage boundary; verified stages are reused.
Changed code/configuration creates a new run. A changed mirror release cannot
silently reuse an old run. Preserve the old workspace and start a fresh one.

Artifacts include `execution.json`, `report.md`, test/runtime/bootstrap logs,
`preprocess/` node/edge/descriptive Parquet and its validation manifest,
`causal/transactions/` model-ready features, and `models/` joblib models plus
`metrics.json`. Private raw acquisitions are cached separately for session resets.
Only load trusted joblib files. Data and model artifacts are never committed.

Each stage is copied to storage with checksum verification before the checkpoint
manifest is published. Interrupted copies do not count as completed stages.
Failure reports remain available in temporary storage even if Drive copying
fails. Do not equate a passed synthetic integration test with real Elliptic access,
Colab execution or measured real-data model quality.
