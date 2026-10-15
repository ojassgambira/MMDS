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

## Follow-up: diagnostic improvements after a reported Colab failure

The user reported Python 3.13, a mounted Drive and subprocess exit status 1.
No Colab runtime logs were supplied or accessed, so the exact cause of that
execution cannot be established. The following defects were reproduced in cloud
regressions and corrected:

- The worker raised exceptions after restoring stderr, omitting the root traceback
  from `runtime.log`. Tracebacks now stay in the log; a parent fallback captures
  worker startup errors. Failed commands include relevant check-log output.
- The notebook caught only the last subprocess call and read entire log files.
  Repository/setup errors are now caught too, and diagnostic reads are bounded.
  Missing logs and the pipeline's failed status are explicit. A simulated notebook
  setup error displays the captured Git error without a generic rethrown exception.
- An old `failure.json` could mask a new setup error. Pre-worker failures now show
  the current cause and label available earlier logs as historical context.
- An interrupted remote folder without `execution.json` failed before recovery.
  Uncommitted copies now restart, while committed stages still require valid hashes.
  Generated integration tests simulate storage quota and training failures, then
  verify reuse of completed preprocessing and successful checkpoint restoration.

Default configuration types/limits, missing source files, separate workspace and
storage paths, a mounted Drive and write/read access are checked before installation.
Tests simulate the exact default Drive path; this is not actual Drive integration
verification. Acquisition HTTP 401/403 produces an explicit authorization/access
instruction without retrying. No external dataset was contacted in these tests.

A public entry-point invocation with an invalid JSON setting was also executed in
Codex Cloud. It exited with status 1 and displayed `Stage: configuration` and
`ValueError: train_end must be an integer`, saving the same cause in `failure.json`
before any dependency installation. This establishes error visibility, not real
Colab execution or model results. The PR's full Python 3.11–3.13 CI matrix provides
committed-source regression evidence; the actual reported Colab root cause remains
unknown until a run's underlying diagnostics are available.

## Confirmed Colab ensurepip failure (2026-10-15)

The user subsequently supplied the confirmed dependency-stage cause: their Colab
Python 3.13 runtime lacked `ensurepip`, and `venv.create(..., with_pip=True)` failed
before acquisition/training. This establishes the reported failure mechanism;
no access to that private Colab runtime or its live logs was available here.

The bootstrap now selects runtime Python/pip in hosted Colab using runtime-specific
environment information, without creating or repairing a Colab venv. Earlier
failed Colab venv directories are ignored. Other supported cloud environments
retain checked/recoverable isolated venvs. Package metadata is probed before any
install; current pins and current editable project metadata skip reinstalls.
Verification imports and the worker run under the selected interpreter in fresh
processes, with the checkout explicitly available through PYTHONPATH.

The existing pins remain unchanged: missing ensurepip is not a package-version
incompatibility. Tests simulate its absence, partial/broken environments and
Colab environment markers, verify the worker/Spark interpreter choice, and run
actual fresh-process dependency checks and a second idempotent preparation in
Codex Cloud/GitHub CI. No real dataset acquisition or hosted Colab execution is
claimed. Drive paths, raw caches and pipeline checkpoints retain their existing
behavior; only workspace venv directories in non-Colab mode can be rebuilt.

Initial current-fix verification in Codex Cloud: 60 pytest tests passed in 149.23
seconds, including actual child-process imports and idempotent second preparation
under simulated Colab mode. Ruff and the installed environment's pip check passed.
The PR's Python 3.11/3.12/3.13 checks are the committed-source compatibility record.
These checks do not establish successful execution in the user's hosted Colab.

## Issue #7: extraction ceiling and dependency conflicts

The user's supplied acquisition trace confirms the old expanded-byte ceiling is
too small. Three actual HTTP 206 ZIP metadata checks measured 697,459,499 expanded
bytes and 153,218,212 ZIP bytes, without downloading CSV bodies in Codex Cloud.
Kaggle's public API independently confirmed original release version 1, the same
expanded total and CC BY-NC-ND 4.0. See [Issue #7 measurements and results](issue-7.md).

The current Colab bootstrap supersedes the earlier global-runtime installation:
runtime pip now targets an isolated pip-free environment created with
`with_pip=False`. Global packages are preserved and their real pip check status is
reported. Full isolated pip check/imports are mandatory. This retains the
no-ensurepip guarantee; it does not silently declare existing global conflicts
resolved. Dependency pins remain tested on Python 3.11–3.13.

Real release validation is now a separate GitHub-hosted bounded job; only its
actual report can establish acquisition/sample success. Generated fixture metrics
are never presented as real Bitcoin fraud model results. Colab/Drive execution
remains external and unverified by these cloud shell/CI simulations.
