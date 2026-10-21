# MMDS — Financial Graph Mining and Fraud Detection

A reproducible university research project combining PySpark data processing,
graph mining, temporal analytics and chronological machine-learning evaluation.
All workloads run in managed cloud infrastructure or free GitHub-hosted Linux.
No Mac execution, paid service or GPU is required.

Two domains share engineering infrastructure while retaining **different targets**:

| Domain | Evidence | Graph and prediction task |
| --- | --- | --- |
| Elliptic Bitcoin | Real original release: 203,769 transactions, 234,355 links, 49 steps | Transaction nodes; retrospective illicit-transaction classification after a source step completes |
| Banking | Independently generated synthetic data: 500 accounts and 33,600 payments per seed; three fixed seeds | Account nodes, repeated payment events; next-day simulated SAR involvement |

Banking is **not official IBM AMLSim output**, real bank fraud or proof of money
laundering. Unknown Bitcoin labels are excluded from supervision. Scores from the
two domains are not directly comparable. Existing verified results are preserved.

## Start here

- [Final research report and figures](docs/final-research-report.md)
- [Verified results summary](docs/results-summary.md), generated directly from hash-verified evidence
- [Project architecture and diagram](docs/architecture.md)
- [Installation and cloud execution](docs/cloud-execution.md)
- [Research methodology](docs/methodology.md), [limitations and reproducibility](docs/reproducibility.md)
- [Presentation and demonstration script](docs/presentation.md)
- [Submission audit and remaining boundaries](docs/submission-audit.md)

## Results at a glance

Elliptic's validation-selected `without_components` model achieves held-out
AP **0.657412**, F1 **0.692382**, recall **0.564465**, FPR **0.003982**.
The frozen transaction baseline AP is **0.652145**. Exploratory paired intervals
include zero for AP/F1 differences: an overall improvement is **not established**.

Independent synthetic banking's combined model is validation-selected for all
three seeds: mean AP **0.432368**, F1 **0.501451**, recall **0.575433**, FPR **0.018676**.
These are arithmetic seed means, not pooled real-bank predictions. Performance
varies substantially across seeds and does not establish real-world efficacy.

## GitHub Pages dashboard

The primary browser dashboard is migrating to a static React/Vite/Plotly build on
GitHub Pages. Target URL: **https://ojassgambira.github.io/MMDS/**; public deployment
success is established only by the post-deploy workflow/browser verification.
[Architecture, export privacy, automated deployment and one-time Pages authorization](docs/github-pages.md).
The browser only renders public aggregates and clearly labeled illustrative graphs;
all Python, Spark and ML remain in cloud CI. The existing Streamlit dashboard and
its research functionality remain available as an optional fallback.

## Streamlit fallback dashboard

The Streamlit app provides six pages per domain: statistics, interactive directed
graph exploration, temporal patterns, model comparisons/confusion matrices and
23 measured PR curves, processing benchmarks, and the research report. Default
graphs are explicitly generated illustrations; optional operator-authorized
subgraphs remain outside Git. No raw data, prediction arrays or models are served.

[Dashboard access and free hosting instructions](docs/dashboard.md).
[Reported deployment failure and production-browser investigation](docs/streamlit-deployment.md).
The app has cloud HTTP and Streamlit integration tests; **no public dashboard URL
is currently verified**. Free Streamlit Community Cloud deployment requires
external GitHub authorization. Use `dashboard/app.py`, Python 3.13 and root
`requirements.txt` (UI only). This is browser authorization, not local execution.

## Cloud execution and verification

The existing public-repository GitHub Actions automatically validate Python
3.11–3.13 / Java 21, run generated-data regressions and Spark smoke, and execute
bounded real Elliptic and synthetic banking experiments. Standard hosted runners
are used; no larger runner or paid infrastructure is provisioned. Dataset terms,
public-repository guards, download/time/disk budgets and cleanup remain enforced.
[Workflow details](docs/unattended-training.md) and [banking protocol](docs/phase5-banking.md).

For a **managed cloud shell only**, install the full development environment:

```sh
python -m venv /workspace/mmds-dev
/workspace/mmds-dev/bin/python -m pip install -r requirements-cloud.lock
/workspace/mmds-dev/bin/python -m pip install --no-build-isolation --no-deps -e .
/workspace/mmds-dev/bin/python scripts/audit_submission.py
/workspace/mmds-dev/bin/python -m pytest -q
/workspace/mmds-dev/bin/python -m ruff check .
/workspace/mmds-dev/bin/python scripts/spark_smoke.py
```

Use the [cloud guide](docs/cloud-execution.md) for complete commands, storage,
checkpoints and output contracts. Optional [Colab Run all](docs/colab.md) always
fetches main and supports Python 3.11–3.13; Drive consent and a hosted runtime
connection cannot be automated. **Actual hosted Colab execution is unverified.**
Codex Cloud uses generated fixtures and does not retry dataset downloads.

## Repository map

| Path | Purpose |
| --- | --- |
| `src/mmd_fraud/adapters`, `data` | Domain contracts, bounded acquisition and independent banking generator |
| `src/mmd_fraud/spark` | Validation, preprocessing and persisted graph/temporal tables |
| `src/mmd_fraud/training` | Bounded CPU models, chronological comparison and uncertainty |
| `scripts` / `configs` | Cloud entry points, resource budgets and fixed protocols |
| `dashboard` | Read-only UI, aggregate evidence and manifest |
| `docs` | Research, results, diagrams, cloud instructions and presentation |
| `tests` / `.github/workflows` | Generated-data regression, security boundaries and cloud CI |

Spark processing benchmarks are actual **single-machine `local[2]`** executions,
not multi-worker scaling. Sparse PageRank/community mining and sklearn fitting
also run on a single CPU host. [Measured configurations and limitations](docs/benchmarks.md).

## Research and data responsibility

The Elliptic paper is Weber et al., *Anti-Money Laundering in Bitcoin:
Experimenting with Graph Convolutional Networks for Financial Forensics* (2019),
[arXiv:1908.02591](https://arxiv.org/abs/1908.02591). Source files are the original
[publisher release](https://www.kaggle.com/datasets/ellipticco/elliptic-data-set),
with reviewed CC BY-NC-ND 4.0 metadata; they are not redistributed here.
[Data source and license review](docs/data-sources.md).
Banking schema compatibility draws on [IBM AMLSim](https://github.com/IBM/AMLSim);
[legacy dependency assessment and independent fallback](docs/amlsim-feasibility.md)
explain why the official generator was not executed. Repository code has no
separate declared reuse license; do not infer a code license from dataset or
upstream licenses.

This is research software, not a production fraud service. Prior test inspection,
retrospective feature availability, missing real labels, synthetic design,
limited periods and free-runtime variability constrain interpretation.
