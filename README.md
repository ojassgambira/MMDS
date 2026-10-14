# MMDS Financial Fraud Detection

Scalable Multi-Domain Financial Fraud Detection Using Distributed Graph Mining,
Temporal Analytics, and Machine Learning.

University Mining of Massive Datasets project: distributed graph mining, temporal
analytics, and machine learning across Bitcoin and banking domains.

Phase 1 provides bounded CSV adapters, validation, a domain-aware feature contract,
generated Spark smoke data and cloud CI. No models have been trained.

Development commands run in **Codex Cloud or GitHub-hosted CI**, never on a local Mac.
For free browser-based data execution, see the [Google Colab guide](docs/colab.md)
and [MMDS Cloud Pipeline notebook](notebooks/MMDS_Cloud_Pipeline.ipynb).
Use **Runtime → Run all**: dependencies, tests, bounded acquisition, PySpark,
chronological initial baselines, metrics, private Drive checkpoints and a report
run through one entry point. See [verification evidence](docs/automation-verification.md)
for what actually executed. No real-data or Colab results are implied by code.
See [cloud setup](docs/cloud-setup.md), [architecture](docs/architecture.md),
[data sources](docs/data-sources.md), [AMLSim feasibility](docs/amlsim-feasibility.md),
[reproducibility](docs/reproducibility.md), [benchmarks](docs/benchmarks.md),
[Phase 2 plan](docs/phase2.md), and [execution results](docs/phase1-results.md).

```bash
python -m venv .venv
.venv/bin/python -m pip install -r requirements-cloud.lock
.venv/bin/python -m pip install --no-build-isolation --no-deps -e .
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
.venv/bin/python scripts/spark_smoke.py
```

`src/mmd_fraud/adapters` holds source boundaries, `spark` holds distributed
operations, and `training` holds bounded chronological Bitcoin baselines. `tests` uses only generated
fixtures. Configurations, cloud entry points, dashboard plans and research notes
live in `configs`, `scripts`, `dashboard` and `docs` respectively.

Phase 2 adds bounded cloud acquisition, distributed CSV validation, partitioned
Parquet graph tables, causal cutoff snapshots, AMLSim timestamp mapping and
processing profiles. See [Phase 2 execution](docs/phase2-execution.md),
[actual results](docs/phase2-results.md) and [Phase 3 recommendations](docs/phase3.md).
Real-data success must be established separately from generated fixture tests.
