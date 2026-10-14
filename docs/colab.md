# Execute MMDS in Google Colab

Codex Cloud develops and tests code; GitHub versions it; a free Google Colab CPU
runtime acquires authorized Elliptic data and executes the small Phase 2 pipeline.
Nothing runs on your Mac or iPhone. Do not retry Codex Cloud dataset downloads:
the required domains are listed but its HTTPS proxy was unreachable.

## Browser steps (Mac or iPhone)

1. Sign in to Google in Safari or Chrome. Open
   [Colab](https://colab.research.google.com/) → File → Open notebook → GitHub.
   Paste `https://github.com/ojassgambira/MMDS`, select the PR branch before merge
   (or `main` afterward), then `notebooks/MMDS_Cloud_Pipeline.ipynb`.
2. On iPhone, Safari's page menu → Request Desktop Website can make the Colab
   menus easier to use. Landscape orientation helps. Colab's mobile UI can be
   awkward; the same notebook can be continued from a Mac browser.
3. Save a private copy in Drive if desired. This copies the notebook, not datasets.
   In Runtime → Change runtime type choose a free CPU Python 3 runtime, with
   Python 3.12 and Java 17/21. If the default differs, use a compatible past
   runtime through Runtime settings. Stop if the guards fail. Do not buy compute.
4. Connect. In the first cell set `REPO_REF` to the PR branch before merge, or
   `main` afterward. For reproducibility, use the exact tested commit SHA.
   Run that cell with its play button. The notebook clones or verifies an
   existing `/content/MMDS` checkout, loads the requested ref, and prints its SHA.
5. Run the dependency cell. All installations happen in Google's VM. No terminal
   or Python installation on your device is needed.
6. Set `PERSIST_TO_DRIVE=True` to preserve results in your existing private Drive,
   run the storage cell and complete Google's mount authorization. Otherwise
   `/content/mmds` is temporary and disappears on disconnect/reset. Check capacity.
7. Review dataset terms. Use default `SOURCE_MODE='pyg'` for the documented PyG
   mirror. Run acquisition once. It is bounded to 200 MB compressed/500 MB expanded
   and records hashes. A failed cell stops; inspect it before any deliberate rerun.
   Do not switch mirrors automatically or bypass access controls.
8. Alternatively, obtain the publisher release through the official Kaggle page,
   accept its terms, extract the three named CSVs to private Drive, mount Drive,
   and select `existing` with that folder. Do not upload `kaggle.json` or credentials.
   If a Kaggle API client requires authentication, use Colab Secrets named
   `KAGGLE_USERNAME` and `KAGGLE_KEY`, retrieving them with `userdata.get` into
   runtime memory only. Do not print them; remove runtime environment bindings
   after the client exits. The default mirror requires no authentication.
9. Run source audit/sample creation, Spark processing, then output validation.
   Keep the default small profile: up to 1,960 selected nodes, 10,000 edge records,
   two workers and two temporal snapshots. Do not run large training jobs.
10. Run benchmarks and visualization, then the persistence cell. Confirm the
    private Drive folder contains `ARCHIVE_COMPLETE.json`, `run/run.json` with
    success, Parquet outputs, sample/source hashes, benchmark CSV and plot.
    The archive marker follows hash verification of run files. If copying fails,
    preserve the temporary results and inspect the partial folder; do not label
    it complete or overwrite it. A new run ID gives a fresh destination.
11. Before ending the session, verify files in Drive using its browser UI. On
    iPhone keep the Colab tab active during processing; backgrounding Safari can
    disconnect the UI and free runtimes can be reclaimed. A reset loses VM files;
    start from setup again, reusing private source CSVs if available. Outputs in
    Drive remain; code changes should be developed/reviewed through GitHub PRs.

## Meaning of results

The sampler streams the bounded source files, audits source row/edge counts,
labels and step coverage, and hashes all inputs. It selects the first 40 nodes
per step in source file order, retaining only edges between selected nodes.
It rejects malformed IDs, duplicate source IDs/classes, orphan edges, empty
graphs and budget overruns. This source audit is not full numeric validation
of unsampled feature rows or an official publisher checksum verification.

The existing Spark pipeline validates all sample values, node/class alignment,
edge endpoints, label semantics and source time units. It checks persisted row
counts and computes descriptive and exclusive-cutoff historical graph features.
Unknown labels remain unknown; anonymous source features are not causal graph
inputs. Sample graph degrees and timings cannot represent the complete graph,
fraud prevalence, multi-machine scalability or model accuracy.

CSV/Parquet data stays outside Git. Raw and derived data must stay private under
the publisher's terms (repository documentation records CC BY-NC-ND 4.0).
GitHub contains code, the unexecuted notebook and documentation only. The notebook
does not fall back to fixtures and call them real data. If real data is unavailable,
stop processing; dataset-free development tests remain usable.

## Development verification

Run in Codex Cloud with no network or external dataset required:

```bash
PYTHONPATH=src python -m unittest discover -s tests -p 'test_colab.py' -v
PYTHONPATH=src python -m unittest discover -s tests -p 'test_acquisition.py' -v
PYTHONPATH=src python -m unittest discover -s tests -p 'test_foundation.py' -v
```

With pinned dependencies installed, run the repository's full checks:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
python -m pytest -q
python -m ruff check .
PYTHONPATH=src python scripts/spark_smoke.py
```

These use generated fixtures and mocked network responses. Notebook structure and
cell syntax checks do not establish Colab execution or successful real acquisition.
No Colab run or real-data run has been performed while preparing this handoff.

Preparation checks in Codex Cloud on 2026-10-14: 24 standard-library tests passed,
including the four new handoff/sample tests. Full unittest discovery reported an
import error for the distributed suite and skipped the foundation Spark test
because PySpark is not installed. The pytest, Ruff and Spark smoke commands were
also attempted and could not run because their modules are absent. `git diff
--check` passed. No external dataset download was attempted. GitHub's existing
workflow installs the pinned dependencies and runs lint, pytest and Spark smoke;
its result must be checked separately before treating the full gate as passed.
