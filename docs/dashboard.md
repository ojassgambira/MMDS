# Dashboard access and operation

For the primary static browser dashboard and automatic Pages deployment, see
[GitHub Pages](github-pages.md). This document describes the retained Streamlit fallback.

`dashboard/app.py` is a read-only Streamlit application. It serves versioned,
hash-verified aggregate evidence for real Elliptic and independent synthetic banking.
It never acquires datasets, trains models, runs Spark, loads pickles or executes
uploaded code. Root `requirements.txt` and entry-point `dashboard/requirements.txt` both select
only `requirements-dashboard.lock`;
no Java, Spark or training stack is needed to host it.

## Reported live deployment failure

The owner has now reported a deployed URL showing a generic hosting error.
Successful public execution is still unverified. See the
[production startup investigation](streamlit-deployment.md) for reproduced
browser checks, evidence fallback behavior and the exact owner-only information
needed to diagnose the live service. No live root cause is inferred from that page.

## Free browser hosting

No public Streamlit deployment or public URL is claimed by this PR. The app has
been tested inside cloud infrastructure with Streamlit AppTest and an actual HTTP
health/HTML server. A loopback URL in a cloud test is not a URL on your Mac and is
not a public service.

To publish without running a workload on a personal device, the unavoidable
external action is authorizing a **free Streamlit Community Cloud** account:

1. Open https://share.streamlit.io/ in an iPhone or Mac browser and sign in with GitHub.
2. Create a free app for `ojassgambira/MMDS`. Choose the Phase 6 PR branch to preview,
   or `main` after merge. Main file: **`dashboard/app.py`**.
3. In advanced settings choose Python **3.13**. No secrets or dataset credentials
   are required. Deployment installs the root dashboard-only requirements.
4. Open the HTTPS app URL assigned by Streamlit. Switching domains/seeds and pages
   runs on the cloud host. No notebook cells or local command execution is needed.

This connection cannot be authorized through the available GitHub tools. An
externally authenticated deployment and a browser visit to its assigned public
URL have not been verified. Community Cloud is an optional free provider, not a
paid resource authorization. If its free hosting is unavailable, keep the tested
cloud app undeployed rather than silently selecting a paid service.

## Cloud server and tests

These commands are for **Codex Cloud or a free authorized cloud host only**:

```sh
python -m pip install -r requirements-dashboard.lock
python -m streamlit run dashboard/app.py --server.address 0.0.0.0 --server.port 8501
```

The host must provide its own approved HTTPS routing/authentication. Do not expose
private records using an unauthenticated public route. Codex Cloud verification
uses `127.0.0.1` inside that cloud machine; no external tunnel, proxy bypass or Mac
server is created. `scripts/dashboard_smoke.py` visits every page for both domains
through Streamlit's actual testing runtime. `tests/test_dashboard.py` additionally
starts and stops a real server and verifies health and HTML responses.

## Data and provenance

- `dashboard/data/elliptic.json`: full-release aggregate evaluation, never raw
  transactions. Bitcoin nodes represent transactions; unknown labels are excluded
  from supervision. Completed-step timing and publisher-feature caveats remain.
- `dashboard/data/banking.json`: three independent simulation seeds, account-day
  forecasting, simulated SAR labels. This is not official IBM AMLSim output or
  measured real bank fraud. Seed selection never uses test performance.
- `dashboard/data/spark-benchmarks.json`: actual Spark measurements from generated
  fixtures, separately tagged, on one machine with `local[2]`. Not worker scaling.
- `manifest.json`: snapshot SHA-256 fingerprints. Snapshots include source workflow
  URLs and downloaded artifact digests. The importer verifies all source report
  hashes and provenance before accepting aggregate files.

Current training workflows export at most 101 actual sklearn PR points per family.
No prediction arrays, thresholds, entity IDs or source rows are exported in the
curve object. AP is computed from the full score ranking. Sampling a curve does
not recompute AP; historical artifacts without curves are visibly marked unavailable,
never reconstructed from an AP scalar. Metrics and curves in each snapshot belong
to the same run.

Refresh through `scripts/import_dashboard_evidence.py` using an already downloaded
and digest-verified GitHub aggregate artifact. No dataset download occurs. Reimport
both domains as required; the manifest updates all aggregate fingerprints. Pull requests whose entire diff is dashboard/documentation-only skip dataset
reacquisition, while compatibility and dashboard CI still validate them. This
Phase 6 pull request changes training exporters as well, so its full dataset
workflows run on each update. Weekly/manual dataset workflows remain.

## Graph explorer

The default explorer is a bounded **generated illustrative graph** with hover,
zoom/pan, time filtering, directed arrows and node focus. It is not a real Elliptic
sample or the measured banking dataset. Colors represent groups, never predicted
fraud. Bitcoin examples have transaction nodes and disconnected step components;
banking examples have persistent account nodes and repeated payments.

For operator-authorized private cloud storage, set `MMDS_GRAPH_DIRECTORY` to an
outside-checkout directory containing `elliptic/` and/or `banking/`. Each contains:

- `nodes.csv`: `id,step,group` (group optional; at most 150 nodes).
- `edges.csv`: `source,target,step` (at most 500 events; repeated payments retained).
- `graph.json`: domain (`elliptic` or `banking`), dataset_kind
  (`original_elliptic_release` or `independent_synthetic_banking`), and `sha256`
  entries for both CSVs. Each file is capped at 2 MB; endpoints and times are checked.

This is a manifest assertion, not independent source authentication. IDs are
visible to dashboard viewers, so only provision a subgraph whose display is
already authorized for that host. No such private graph is provided or claimed
verified as real in this PR. Raw/derived transaction records stay outside Git.

## Reproduce report figures

In the full managed cloud development environment, run
`python dashboard/render_report_figures.py`. This renders the three report PNGs
from hash-verified aggregate snapshots without downloading datasets or rerunning
training. Matplotlib is a development/report dependency; the lightweight hosted
dashboard only reads the resulting images.

## Real-browser production validation

The dashboard workflow additionally installs a clean UI-only server environment,
without an editable project/Spark/sklearn, and uses real Chromium sessions on
Python 3.12/3.13. It visits both domains/all pages from root and entry-point working
directories and tests missing/corrupt evidence. This supplements AppTest and HTTP
health checks; it does not establish a working public deployment. Missing aggregate
files show labeled illustrations without scores; corrupt evidence still fails closed.
See the [production reproduction command](streamlit-deployment.md).
