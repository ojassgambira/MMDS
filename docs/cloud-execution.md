# Installation and cloud execution guide

The primary browser implementation is a [static GitHub Pages build](github-pages.md);
publication is verified separately after merge and Pages authorization.
Its workflow exports verified aggregates and tests browser views; the Python/ML
pipelines below remain cloud-only. Streamlit is retained as a fallback.

All shell commands here run **only in Codex Cloud or free authorized cloud
infrastructure**. A Mac or iPhone is only a browser client. No paid/GPU resources
are used. Supported full stack: Python 3.11–3.13, Java 17 or 21, Spark 4.0.1.
Python 3.14 is deliberately unsupported pending compatibility verification.

## Automated free GitHub execution

The public repository already has four workflows under `.github/workflows`:

| Workflow | What it verifies | Output |
| --- | --- | --- |
| Cloud compatibility checks | Full generated-data tests, pip consistency, Ruff, Spark smoke on Python 3.11/12/13 | Sanitized aggregate test evidence |
| Unattended real-data training | Publisher/size/license review, real Elliptic validation, bounded baselines, comparisons and research | Aggregate training/research reports and plots |
| Synthetic banking research | Three fixed independently generated replicas; account forecasting, models and uncertainty | Aggregate banking report and plots |
| Dashboard and Spark benchmark validation | UI-only dependency boundary, all pages, six measured Spark processing sizes | Single-machine benchmark JSON |

PRs/main pushes run relevant workflows. Dataset jobs skip pull requests whose
entire diff is dashboard/documentation-only; weekly/manual real-data execution
remains available. Optional manual runs use GitHub's Actions **Run workflow**
button, not a terminal on a personal device. Standard public-repository hosted
runners only; private/self-hosted real-data jobs are refused by the current guards.

Download **aggregate** artifacts from the successful run, or inspect versioned
`dashboard/data` after artifact retention expires. A passed unit test does not
establish dataset access. Use workflow status, provenance and report success.

## Managed-cloud development installation

Clone `https://github.com/ojassgambira/MMDS.git` and check out the intended reviewed
commit in the cloud workspace. In Codex Cloud, from the repository root:

```sh
python -m venv /workspace/mmds-dev
/workspace/mmds-dev/bin/python -m pip install -r requirements-cloud.lock
/workspace/mmds-dev/bin/python -m pip install --no-build-isolation --no-deps -e .
/workspace/mmds-dev/bin/python -m pip check
/workspace/mmds-dev/bin/python scripts/audit_submission.py
/workspace/mmds-dev/bin/python -m pytest -q
PYTHONPATH=src /workspace/mmds-dev/bin/python -m unittest discover -s tests -v
/workspace/mmds-dev/bin/python -m ruff check .
PYTHONPATH=src /workspace/mmds-dev/bin/python scripts/spark_smoke.py
```

These checks use generated fixtures and bundled aggregates, not external datasets.
The cloud must permit Spark loopback sockets. Preserve its configured proxy and CA
trust; do not bypass network controls. Codex Cloud dataset acquisition is disabled
by project policy. A non-Colab Python missing ensurepip needs an environment with
venv support; no unreviewed bootstrap download is used.

## Domain execution entry points

- **Elliptic:** `scripts/run_training_job.py` is restricted to free public GitHub
  hosted runners. It performs the full fixed protocol, enforces source byte/time
  limits and publishes aggregate evidence. [Exact command and budgets](unattended-training.md).
- **Banking:** in managed cloud, run
  `python scripts/run_banking_job.py --workspace /workspace/banking-private-new`.
  Use the full environment interpreter above; the workspace must be new and outside
  the repository. Configuration: `configs/banking-research.json`, seeds 0/1/2.
  [Contract, checkpoints and bounded synthetic protocol](phase5-banking.md).
- **Benchmarks:** `python scripts/benchmark_spark.py --workspace /workspace/bench-private-new`.
  This creates generated fixtures for three sizes per domain, records actual local[2]
  configuration and validates persisted counts. It never measures worker scaling.
- **Colab:** optional [Run all notebook and Drive guide](colab.md). The notebook
  fetches main, uses runtime pip to populate a pip-free isolated environment,
  and invokes `scripts/run_cloud.py`. Default configuration runs initial graph
  baselines, not the full Phase 4 research protocol. No actual Colab execution is
  claimed. Hosted connection, account/Drive consent and publisher terms are manual.

Commands using a bare `python` above assume the full cloud environment is active;
otherwise use its absolute interpreter path. Never execute them on a personal device.

## Dashboard and persistence

Free browser deployment uses `dashboard/app.py`, Python 3.13 and root
`requirements.txt`. [Detailed instructions](dashboard.md) identify the unavoidable
external Streamlit/GitHub authorization. No dataset credentials are needed for the
aggregate dashboard. No public URL or successful external deployment is claimed.

Raw files, Parquets, scores and models remain in private outside-checkout workspaces.
GitHub cleans them after each job. Colab can copy verified stages into
`/content/drive/MyDrive/MMDS/automated`; temporary storage disappears on reset.
Checkpoint reuse requires matching code/configuration/input/dependency fingerprints
and artifact hashes. A corrupt checkpoint fails closed; interrupted stages restart.
Never load an untrusted joblib model or publish dataset files in Git/CI artifacts.

## Failure recovery and authentication

Pipeline reports identify the active phase and actual exception, with bounded
redacted bootstrap/runtime/worker log tails. Dependency failures occur before data
acquisition. Access denial stops once; it is never silently retried or replaced
with synthetic success. Default PyG acquisition needs no Kaggle secret; if an
explicit alternative needs Kaggle authorization, use Colab Secrets and private
CSV storage as documented. Do not commit `kaggle.json`, tokens or model files.

Free runtime quotas, dataset terms/access, account consent and external hosting
availability cannot be guaranteed by this repository. These are genuine external
boundaries, not reasons to ask a user to debug cells or run local workloads.
