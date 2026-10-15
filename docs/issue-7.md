# Issue #7: measured acquisition budgets and cloud automation

The supplied Colab error establishes an acquisition expansion failure after tests
and Spark smoke passed. It does not establish successful preprocessing or training.
The previous global runtime install also downgraded PyArrow and conflicted with
bigframes/datasets; a scoped MMDS import check did not establish global consistency.

## Release inspection and provenance

Measured in Codex Cloud on 2026-10-15 using HTTP 206 ZIP-tail requests of at most
65,557 bytes each. Total metadata read: **196,671 bytes**, 1.644 seconds in the
recorded script run. CSV bodies were not downloaded in Codex Cloud. The inspection
script rejects ignored Range requests before reading a full response, invalid
Content-Range, oversized/truncated responses, and unexpected archive members.

| Original CSV | ZIP bytes | Expanded bytes | CRC32 from directory |
| --- | ---: | ---: | --- |
| elliptic_txs_features.csv | 150,601,883 | 689,683,771 | f62b0d9d |
| elliptic_txs_classes.csv | 925,698 | 3,305,144 | a0d598c5 |
| elliptic_txs_edgelist.csv | 1,690,631 | 4,470,584 | 68acfa24 |
| Total | 153,218,212 | 697,459,499 | |

The publisher Kaggle API independently returned version 1, totalBytes 697,459,499,
lastUpdated 2019-07-31 and CC BY-NC-ND 4.0. PyG upstream identifies this same mirror.
Public mirror access needs no credentials. Hashes/CRCs verify transfer integrity;
they are not authenticated publisher signatures. License/publisher/source URLs,
individual sizes and SHA-256 values stay in the private acquisition manifest.

Defaults: **200,000,000 compressed bytes**, **750,000,000 expanded bytes**,
**600 seconds** cumulative stream/extraction budget, 60-second request timeout.
The expanded default has about 7.5% headroom over the measured release. Each limit
is independent. Configuration permits positive integers up to 300,000,000 compressed,
1,000,000,000 expanded and 1,800 seconds, keeping this original-release workflow
bounded. Larger releases require a reviewed change. No safety check was disabled.
The medium Spark, sample-source and supplied-CSV limits now accommodate this
measured release. Row/edge limits and sampling limits remain unchanged.

Before download: disk reserve for compressed + expanded ceilings. During download:
declared and streamed cumulative compressed checks, exact declared Content-Length,
time budget and approved redirects. Extraction: one exact expected member, declared
remaining allowance, streamed cumulative expansion, ZIP CRC and timeout. Publication
is atomic; failures remove staging without retry. Errors name the file, declared
size, remaining allowance and relevant limit. Interrupted acquisitions restart;
complete private caches resume only after source, license, sizes and hashes verify.

## Colab dependency isolation without ensurepip

The existing runtime pip manages a workspace `colab-venv-X.Y` using `--python`.
The environment is created with `with_pip=False`; ensurepip is never invoked.
Pinned packages, editable project metadata, worker and Spark imports live there.
Global Colab PyArrow/IPython/bigframes/datasets are preserved. The bootstrap records
the real global pip check result, including existing conflicts, and requires a
full isolated pip check plus fresh imports. It cannot undo global changes from an
earlier notebook run; those unrelated conflicts remain reported. No successful
Colab/Drive execution is inferred from the simulated missing-ensurepip tests.

## Unattended free cloud verification

`.github/workflows/ci.yml` runs on push/PR and supports workflow_dispatch:

- Python 3.11/3.12/3.13, Java 21: pinned installation, pip check, Ruff, complete
  generated-data tests (including initial models), checkpoint/restore, Spark smoke.
  The suite exercises an actual pip-free isolated install, missing ensurepip,
  pre-existing global conflicts, >500 MB generated ZIP extraction, malicious/oversized
  archives, cumulative limits, truncation/CRC, interruption, timeout and cache tampering.
- GitHub-hosted Ubuntu/Python 3.13: bounded mirror metadata, complete original-release
  acquisition (at most 200 MB transferred/750 MB expanded), SHA-256 verification,
  all source widths/IDs/labels/edge endpoints/counts/steps, deterministic induced
  sample, numeric validation and Parquet round-trip using Spark. This job does
  **not train real models** or establish full-source numeric validation.
- Allowlisted redacted aggregate reports, generated-fixture logs and stage timings
  are published as seven-day artifacts and job summaries, including failure status.
  No source CSV, Parquet, model, Drive content or credentials are public artifacts.
  Real-data directories are deleted after the job. Failed acquisition is not retried.

All jobs use standard GitHub-hosted Linux runners in this public repository;
no paid service or self-hosted runner is provisioned. Codex Cloud acquisition
remains disabled; only bounded metadata inspection was performed there.

## External approvals

GitHub CI requires no Drive OAuth or Colab session and handles the above validation
unattended. The private persistent full pipeline remains a Colab Run all workflow.
Google sign-in, a free hosted runtime connection, publisher terms where required,
and Drive OAuth are external user actions; repository code cannot grant them or
start/control a private Colab session. No code edits, log copying or manual cell
debugging are part of the workflow. Notebook defaults load this fix branch before
merge and main after branch deletion. Merge remains a maintainer decision after
required checks; this work does not merge the PR.

## Execution evidence

Verification results and CI URLs are recorded here after execution. Metadata
inspection above is verified; real Colab execution and real model metrics remain
unverified and are not claimed.
