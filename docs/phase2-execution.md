# Phase 2: cloud acquisition and distributed preprocessing

All commands below execute in Codex Cloud, in /workspace/MMDS. The user's Mac is
only a review UI. No final model training or paid infrastructure is involved.
The inspected cloud has an 8 GiB cgroup memory limit and about 30 GiB free disk.
Neither /workspace nor Codex Cloud is permanent storage: export authorized files
to an existing approved cloud store before environment teardown, or re-acquire
using the manifest. No permanent store or cloud credentials are configured here.

## Source, license and download methods

Publisher: [Elliptic Kaggle release](https://www.kaggle.com/ellipticco/elliptic-data-set).
The publisher's indexed description lists **CC BY-NC-ND 4.0**. This university
workflow performs private noncommercial analysis; it publishes code and aggregate
execution evidence, not raw or derived data. Do not assume that a third-party
repository's MIT/Apache software license relicenses the dataset. Review the
publisher terms again before redistribution or commercial use.

The [publisher announcement](https://www.elliptic.co/insights/elliptic-dataset-cryptocurrency-financial-crime/)
links to the original release. The
[PyG adapter source](https://github.com/pyg-team/pytorch_geometric/blob/master/torch_geometric/datasets/elliptic.py)
documents a public mirror at https://data.pyg.org/datasets/elliptic, with one ZIP
per CSV; no PyTorch dependency or Kaggle credential is needed for this mirror.
The alternative Kaggle CLI (`kaggle datasets download -d ellipticco/elliptic-data-set`)
may require credentials and access to redirected storage hosts; it was not used.
Do not bypass denied destinations or retrieve data through an unrelated mirror.

Expected original files: headerless features (ID, step, 165 numeric values),
classes (txId,class), edges (txId1,txId2). Original release has 203,769 transactions,
234,355 directed edges, 4,545 illicit, 42,019 licit and 157,205 unknown labels,
and steps 1–49. Unknown labels remain unknown, not negative training examples.
The mirror is mutable: acquisition records per-file SHA-256 and archive hashes,
URLs, UTC time, byte sizes and elapsed time, not a fictitious immutable release ID.
No official publisher checksum is currently available for comparison.

```bash
.venv/bin/python scripts/acquire_elliptic.py --destination /workspace/data/elliptic
SPARK_LOCAL_IP=127.0.0.1 PYSPARK_PYTHON=/workspace/MMDS/.venv/bin/python \
  .venv/bin/python scripts/preprocess.py \
  --config configs/elliptic-processing.json --profile medium \
  --output /workspace/artifacts/elliptic-run-001 --cutoffs 2 35 50
```

Acquisition rejects existing destinations, uses a temporary staging directory,
limits total compressed bytes to 200 MB and expanded bytes to 500 MB, checks disk
space, verifies archive structure/CRC while reading, and atomically publishes only
all three complete files. It rejects unexpected archive paths and redirects.
Failed downloads leave no directory pretending to be a complete acquisition.
Cloud network access to data.pyg.org must be enabled through environment settings.

## Processing behavior and outputs

Spark uses explicit string CSV schemas and FAILFAST parsing, including exact
record widths. CSV column pruning is disabled to avoid silently truncating malformed
records. IDs must be nonempty; Bitcoin IDs must contain only decimal digits, and
steps must be integers 1–49. It validates matching class/node sets, finite numeric
features, supported labels and referential integrity. Exact normalized duplicates
are removed with counts; conflicting records for an ID fail instead of choosing
an arbitrary row. Bitcoin duplicate relationships collapse to a simple directed
graph; banking repeated transfers retain distinct event IDs.

Missing feature policy defaults to reject. Explicit `missing_policy: zero` fills
only absent numeric values with a constant and records how many values were filled;
nonnumeric tokens and infinities still fail. No mean, scaling or other fitted
preprocessing is performed, so no future-informed imputation is introduced.
Source-provided anonymous features are preserved under `source_features` in nodes
for auditing, but are never consumed by historical graph feature computations.
Their upstream neighborhood aggregates have not been established as causal.

The run writes immutable, partitioned Parquet checkpoints and verifies row counts
by reading them back: nodes by time_step, edges by available_step, and historical
features by cutoff_step. Descriptive features have a separate output directory.
Graphs are Spark node and edge tables keyed by transaction IDs; no address graph,
GraphFrames dependency or driver-side graph object is constructed.

`available_step = max(source_step, target_step)` conservatively treats a relationship
as observed only after both transactions exist. At the **start** of cutoff t,
features use nodes with step < t and edges with available_step < t. Features include
in/out/total degree, distinct undirected neighbor count, mean/max neighbor total
degree, previous-step degree and age. Neighbors exclude self-links; degree counts
both directions of a self-link. No labels or supplied feature values enter these
computations. Strict cutoff differs intentionally from Phase 1's inclusive
reference interface and is explicit in output schema version 2.

Snapshot features are retrospective research artifacts, not claims of real-time
availability or performance. The dataset's discrete steps do not establish
ordering within a step; same-step information is withheld at that step's start.
Future-node/edge additions cannot change a previous snapshot. Historical banking
feature computation and supervised label mapping are deferred; this phase ingests
and validates account/event tables only.

Each run writes run.json before processing, after each completed output and on
failure. It records input hashes, profile/configuration, Git commit/dirty state,
versions, validation row counts, duplicate/missing counts, step/label distributions,
stage durations, requested/read partition counts and physical Parquet file counts.
Python peak RSS is only the Python driver; cgroup current/peak memory includes the
whole environment and its history, not isolated JVM peak usage. Unavailable
memory measurements are omitted, never invented. A small number of partition
files can differ from requested Spark partitions and is recorded separately.

Completed nodes/edges Parquet outputs are durable *within the current workspace*
and truncate later query lineage; they remain usable after a subsequent stage
fails. Runs do not auto-resume or overwrite partial checkpoints. Inspect run.json,
use a new output directory to rerun, and preserve hashes when reusing checkpoints.
A failed run is never marked successful. Record counts/bytes are enforced before
expensive features, and no unbounded `.collect()` is used for node or edge tables.
Labels/time-step summaries have fixed small cardinality. Each Parquet file caps
records at 100,000. Processing time limits should additionally be set by the
cloud job runner (GitHub CI currently has a 12-minute timeout).

## Profiles

| Profile | Rows per table | Total input bytes | Shuffle/output partitions | Driver memory | Max snapshots |
| --- | ---: | ---: | ---: | --- | ---: |
| small | 10,000 | 50 MB | 2 | 1 GiB | 3 |
| medium | 300,000 | 500 MB | 4 | 2 GiB | 5 |
| large | 2,000,000 | 1 GB | 16 | 4 GiB | 10 |

Profiles are in configs/profiles.json. Limits fail instead of silently sampling.
The complete original Elliptic release fits medium; small needs an explicitly
prepared, internally consistent induced subgraph. Large is a configuration,
not a benchmark result or permission to provision larger infrastructure.
`--master local[2]` runs Spark workers in the cloud; multi-machine execution
requires an already approved cluster/master and shared storage. Local output
paths are unsuitable for a remote cluster without shared filesystem access.

## Banking and AMLSim boundary

Use configs/banking.json for integer-step normalized events, or
configs/amlsim-converted.json for converted AMLSim fields acct_id, tran_id,
orig_acct, bene_acct, base_amt, tran_timestamp. Mapping was inspected against
[AMLSim schema](https://github.com/IBM/AMLSim/blob/master/paramFiles/1K/schema.json)
and [converter](https://github.com/IBM/AMLSim/blob/master/scripts/convert_logs.py).
Set base_date to the actual simulation's UTC start. Default conversion maps ISO
UTC timestamps to elapsed days; edit the Spark timestamp format for your pinned
output version. Integer-step pipelines do not reinterpret strings as timestamps.

```bash
SPARK_LOCAL_IP=127.0.0.1 PYSPARK_PYTHON=/workspace/MMDS/.venv/bin/python \
  .venv/bin/python scripts/preprocess.py --domain banking \
  --config configs/amlsim-converted.json --profile small \
  --output /workspace/artifacts/banking-run-001
```

Only account IDs and transfer fields are retained; personal/party metadata is
not copied. Require one declared currency or pre-normalized amounts. SAR flags
are not automatically turned into real-world fraud labels. No AMLSim simulator
was executed and no banking dataset was acquired. Test fixtures are clearly
marked generated correctness cases, not claimed banking observations.
