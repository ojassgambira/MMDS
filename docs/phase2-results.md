# Phase 2 actual execution results

Executed in Codex Cloud on 2026-10-14. **Real Elliptic acquisition is blocked by
cloud network policy.** No real Elliptic preprocessing or real banking ingestion
is claimed. The code, generated integration tests and fixture benchmark ran.

## Executed checks

- Inspected Phase 1 AGENTS.md, adapters, contracts, Spark smoke, environment status,
  policy, disk and memory; fetched latest main and created phase2/distributed-preprocessing.
- Queried publisher licensing/source, PyG download code and AMLSim schema/converter
  through connected research tools. Publisher lists CC BY-NC-ND 4.0; no raw data
  or derived dataset has been published.
- `curl -I --max-time 20` against Kaggle's download endpoint and PyG mirror:
  cloud proxy denied CONNECT with HTTP 403. Actual bounded downloader attempts
  also raised URLError with tunnel 403. Runtime status later reported policy
  enforced, with no custom allowed hosts and no configured secrets.
- ` .venv/bin/python scripts/acquire_elliptic.py --destination /workspace/data/elliptic`:
  failed on the first remote request; no completed source directory was published.
  An initial implementation incorrectly treated the workspace's empty .git placeholder
  as a checkout; that guard was fixed and the download then reached the proxy denial.
- `.venv/bin/python -m pytest tests/test_acquisition.py tests/test_distributed.py -q`:
  initial 10 tests passed in 66.20s. These include mocked archive acquisition,
  generated Spark preprocessing, schema failures, temporal invariance and Parquet.
- `SPARK_LOCAL_IP=127.0.0.1 PYSPARK_PYTHON=/workspace/MMDS/.venv/bin/python .venv/bin/python -m pytest -q`:
  27 passed in 69.29s after adding AMLSim ISO timestamp mapping. Later acquisition
  redirect hardening was tested separately; the final full regression suite passed
  **28 tests in 69.92s**, with no skips.
- `.venv/bin/python -m ruff check .`, `.venv/bin/python -m pip check`,
  `.venv/bin/python -m compileall -q src scripts tests`: passed.

## Generated Bitcoin fixture benchmark

These are synthetic correctness records with all labels unknown, **not the
Elliptic dataset and not AMLSim output**. They establish the executed pipeline,
not real-data validity, predictive quality or distributed speedup.

```bash
.venv/bin/python scripts/generate_elliptic_fixture.py \
  --destination /workspace/data/elliptic-fixture --nodes 1000
SPARK_LOCAL_IP=127.0.0.1 PYSPARK_PYTHON=/workspace/MMDS/.venv/bin/python \
  .venv/bin/python scripts/preprocess.py --config configs/elliptic-fixture.json \
  --profile small --output /workspace/artifacts/elliptic-fixture-run-001 \
  --cutoffs 2 10 50
```

Actual result: success; 1,000 transaction nodes, 999 directed chain edges,
165 numeric values per node, all 49 steps, zero missing values or duplicates.
Elapsed 33.639s, validation 15.075s. Historical output rows at exclusive cutoffs
2/10/50: 21/184/1,000. Requested partitions: 2. Node and edge outputs each had
98 physical Parquet files across 49 step directories; read partition counts were
4. Descriptive and each historical output had 2 files/read partitions.
Python driver peak RSS was 32,276,480 bytes; environment-wide cgroup memory was
1,802,903,552 bytes current and 2,579,816,448 bytes peak at manifest capture.
These memory readings do not isolate the JVM or reset the cgroup peak.

Aggregate evidence is in [benchmark log](benchmark-logs/phase2-generated-fixture.json).
The run truthfully recorded the base commit and dirty worktree because it preceded
commit of the Phase 2 implementation; input hashes and configurations are included.
Source records and Parquet outputs remain outside Git in the paths above and may
be lost when the cloud environment is recycled. Spark emitted its usual native
Hadoop fallback/incubator warnings; the run succeeded.

## Remaining access-dependent work

The user indicated intent to enable data.pyg.org; the last actual request still
received 403. Enable that destination through the supported cloud configuration
workflow, then run the exact acquisition and medium-profile commands in
[execution guide](phase2-execution.md). If a redirect is needed, inspect the host
before changing policy; the downloader rejects unexpected redirects.
Only after the full release passes schema/count validation and Parquet round trips
can Phase 2 real-data processing be marked verified. No paid services, permanent
storage, large-scale experiment, final model or AMLSim simulation was started.
