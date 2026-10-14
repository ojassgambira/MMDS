# Automation verification record

Prepared in Codex Cloud on 2026-10-14. No workload ran on a Mac. No real dataset
was downloaded, no paid resource was provisioned, and no Colab session was executed.

## Repository and compatibility review

Reviewed the repository tree, Phase 1 adapters/contracts/validation and Spark
smoke, Phase 2 acquisition/preprocessing/graph code, tests, configuration files,
notebook, dependency declarations, CI and the architecture/execution/source notes.
GitHub main was at `22dfa1adc7bd19569daa35e4f69bc9804fe286c4` (merged Colab PR #3).
The immediate failure was the notebook's exact Python 3.12 assertion; the package
also excluded 3.13. Existing architecture left training empty and used descriptive
or global-cutoff graph snapshots, which were unsuitable as per-transaction
chronological predictors without an explicit prediction-time definition.

Installed package metadata was inspected: Spark 4.0.1 and PyArrow 20.0.0 require
Python >=3.9; NumPy 2.2.6, SciPy 1.15.3 and scikit-learn 1.7.2 require >=3.10.
All project Python files parse with Python 3.11 syntax. The new compatibility
contract is 3.11–3.13, with the exact dependency set tested by the GitHub matrix.
Metadata alone is not evidence of runtime compatibility: use the PR's matrix
check results for each interpreter. Python 3.14+ remains unsupported.

## Executed in Codex Cloud

- Python 3.12.14, Java 21; isolated dependency installation and `pip check` passed.
  The initial sandbox could not reach its proxy. Using the supported additional
  network permission allowed package installation and Git access. No dataset
  destination was contacted or retried.
- Six new automation tests passed initially in 49.07 seconds, including generated
  preprocessing/training, chronological/unknown-label guards, known metric values,
  train-only scaling, test-feature invariance of model selection, archive corruption
  rejection, single-attempt failed acquisition reporting and checkpoint restoration.
- The public entry point was executed with a `generated_test_fixture` configuration:

  ```bash
  python scripts/run_cloud.py \
    --workspace /workspace/mmds-automation-evidence/runtime \
    --storage /workspace/mmds-automation-evidence/storage \
    --config /workspace/mmds-automation-evidence/fixture-config.json
  ```

  It created a fresh virtual environment, installed the pinned stack, passed
  `pip check`, Ruff, **39 pytest tests in 160.92 seconds**, and Spark smoke.
  It then processed 196 generated nodes and 195 chain edges across all 49 source
  steps, computed temporal graph features and trained/evaluated all three baselines.
  These are synthetic correctness records, **not Elliptic data or model quality
  evidence**. The generated fixture supplies both known classes in every period
  and preserves unknown labels separately.
- Actual stage times for that entry-point run: checks 177.57 seconds; preprocessing
  39.52; temporal features 5.12; models 0.87. These are one cloud fixture run, not
  scalability benchmarks. The code was in a dirty development tree, recorded in
  its manifest; later CI checks validate the committed source.
- The run status was `success`. Models, metrics, Parquet tables, logs, source hashes,
  report and verified checkpoint copies were created outside Git under the paths
  above. The run key was `1ff8759609d99581267f`. Temporary cloud workspaces may be
  reclaimed; these paths are execution evidence, not permanent hosting promises.
- `git diff --check` and final Ruff checks passed. The existing distributed tests
  now also cover end-of-step features remaining unchanged when future edges are added.

The CI workflow installs the full pins and runs `pip check`, Ruff, the full pytest
suite (including generated end-to-end training/resume) and Spark smoke on Python
3.11, 3.12 and 3.13. Its results are attached to the PR; they do not simulate Google
Drive consent or prove that Colab's current service can reach a dataset host.

## Still requires external cloud execution

- Actual Colab hosted runtime startup and Run all execution.
- Google Drive authorization, mount behavior, capacity and persistence across a
  real Colab runtime reset. Generic filesystem checkpoint copying/restoration was
  tested in Codex Cloud; it is not described as a Drive integration test.
- Real Elliptic acquisition from PyG or authorized existing Kaggle CSVs; publisher
  terms/authentication if required; complete real-data validation and baseline
  results. Source failures stop with a report. There is no synthetic fallback in
  the default notebook workflow.
- Real-data precision, recall, F1, PR-AUC and confusion matrices. No such values
  are reported here. They are generated only after successful real-data execution.

Codex Cloud acquisition remains deliberately disabled under the user's instruction
to stop retrying those downloads. That limitation does not block development,
generated correctness tests or GitHub compatibility checks.
