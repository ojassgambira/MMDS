# Static MMDS dashboard on GitHub Pages

Target URL: **https://ojassgambira.github.io/MMDS/**. This is the configured target,
not a claim that the site has deployed or been verified publicly.

The primary dashboard is a static React/Vite application in `frontend/`, with
self-hosted Plotly charts and no backend service. All Python, Spark, graph mining,
model fitting, evaluation and data export remain in cloud pipelines. The browser
only verifies asset hashes, filters illustrative views and renders public aggregates.
Streamlit remains intact in `dashboard/app.py` as an optional cloud fallback.

## Preserved research views

- Real original Elliptic Bitcoin statistics, cohorts, labels, model families,
  ablations, measured PR curves, confusion matrices and per-step evaluation.
- Independently generated synthetic banking results for seeds 0/1/2, account-day
  forecasting, daily transaction patterns, model comparisons and arithmetic seed means.
- Generated illustrative directed graphs with period, size and node-focus controls,
  hover, pan and zoom. These are not actual Elliptic or measured banking subgraphs;
  colors are groups, not fraud predictions. No private subgraph is published.
- Actual single-machine Spark processing benchmarks, complete configuration,
  counts/timings, and separately labeled sparse CPU prefix measurements.
- Full research narrative/tables, existing aggregate figures, provenance links,
  architecture and presentation links, and a portable Markdown report download.

Targets remain separate. Unknown Bitcoin labels never become negatives. Simulated
SAR involvement is neither official IBM AMLSim output nor verified bank fraud.
Average precision is computed in Python from full rankings; the client draws
exported real PR points. No metric is inferred from curves or invented after failure.

## Automated build and publication

`.github/workflows/pages.yml` validates PRs and builds/deploys reviewed main pushes.
It uses standard free public-repository Ubuntu runners, Python 3.13 and Node 24:

1. Verify existing aggregate hashes/metric contracts, then export explicit public DTOs.
2. `npm ci --ignore-scripts` from the committed lock (no dependency lifecycle scripts).
3. Formatting, frontend unit tests, production build, base-path/local-link checks,
   allowlisted asset fingerprints and production-dependency audit.
4. Real system Chromium tests of both domains/all pages under **`/MMDS/`**, mobile
   layout, seed/model selection, graph controls, reloads and failure states.
5. Upload only `frontend/dist` as the Pages artifact. PRs do not publish.
6. On main, configure/deploy Pages with scoped `pages:write` / `id-token:write`.
7. Verify the actual public manifest's commit and all twelve domain/page combinations
   in Chromium. A failed/stale public verification fails the workflow; an uploaded
   artifact alone is never reported as a successful public deployment.

Navigation uses URL fragments, so shared/reloaded sections do not need a backend
router or a broad 404 rewrite. `vite.config.js` pins the case-sensitive `/MMDS/`
base, including chart chunks, icons, JSON, image assets and downloads. No external
font/CDN, analytics, Python runtime, credential, Spark service or model is loaded.
A content security policy rejects external connections, plugins and dynamic eval.

## One genuine initial administration boundary

On 2026-10-21 GitHub's repository metadata reported `has_pages=false`. The available
connected tools expose repository code/PR operations but no Pages administration
operation. GitHub's official configure-pages action states that enabling a new
site requires a token other than ordinary `GITHUB_TOKEN`; a GitHub App would need
`administration:write` plus `pages:write`. We do not request or store a PAT.

If Pages is still disabled when this PR merges, the repository owner must make
**one browser setting**: repository **Settings → Pages → Build and deployment →
Source → GitHub Actions**. That is a service administration action, not code editing,
local execution or notebook debugging. A custom environment approval rule, if the
owner has configured one, also requires the corresponding authorized approval.

After merge, main's workflow deploys automatically if that setting is enabled.
If a run encountered the disabled-site boundary, its error identifies the setting;
once authorized, the workflow can be run from Actions. No paid hosting, custom
domain, browser-side ML or Streamlit account is needed. Publication cannot be
verified before the PR is merged and the actual Pages site is available.

Official references: [GitHub custom Pages workflows](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages),
[configure-pages enablement permissions](https://github.com/actions/configure-pages/blob/v5/action.yml).

## Public export contract and privacy

`scripts/export_pages_data.py` reads only the fixed versioned `dashboard/data`
manifest/snapshots and three named aggregate research figures. It verifies the
source contracts and projects allowlisted fields instead of copying arbitrary
experiment folders. Unknown records, prediction arrays, model paths, extra fields
and operator-provisioned graphs cannot enter the static DTO. Example graphs are
explicitly generated in cloud Python using the existing helper.

Generated `frontend/public/data/` is ignored in Git. The exporter permits exactly
nine files plus its manifest: two domain JSONs, benchmark JSON, illustration JSON,
report JSON/Markdown and three named PNGs. Unexpected files/symlinks fail publication.
No raw/derived transaction rows, account records, credentials, joblib models or
per-row predictions are published. The manifest records original aggregate SHA-256
fingerprints and the application build commit; client hashes verify downloaded bytes.
Hashes establish integrity relative to the publication, not publisher authentication.
Missing or corrupt assets fail closed with a repository report link and no scores.

Generated illustrations intentionally include fake node IDs, always labeled as
illustrations; they are not an exception for actual record-level publication.
Private operator-subgraph capabilities remain only in the preserved Streamlit
fallback and require the previously documented display authorization.

## Managed-cloud reproduction only

From the repository root in Codex Cloud or free authorized cloud infrastructure:

```sh
python -m pip install -r requirements-dashboard.lock
python scripts/export_pages_data.py
npm ci --ignore-scripts --prefix frontend
npm run lint --prefix frontend
npm test --prefix frontend
npm run build --prefix frontend
npm run test:browser --prefix frontend
```

Node 24 and an existing system Chromium/Chrome are required. The tests do not
download a browser. Set `CHROME_BIN` only if the approved cloud image uses a different
system browser path. If the cloud home directory is read-only, set npm's cache to
a writable cloud workspace (for example `npm --cache /workspace/npm-cache ci ...`).
Do not run these workloads on a Mac. Python export never acquires a dataset or trains.

The original [research report](final-research-report.md), [results](results-summary.md),
[methodology](methodology.md), [benchmarks](benchmarks.md) and [cloud execution](cloud-execution.md)
remain authoritative. The former [Streamlit deployment investigation](streamlit-deployment.md)
records that incident; it is not a prerequisite for the static site.
