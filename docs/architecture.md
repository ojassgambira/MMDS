# Architecture

| Domain | Nodes | Edges | Time | Label target |
| --- | --- | --- | --- | --- |
| Bitcoin | transactions | directed payment flows between transactions | Elliptic discrete steps 1–49 | transaction |
| Banking | accounts | individual transfers, retaining repeated edges/event IDs | simulation step from declared configuration | future account/event tasks, explicitly chosen |

Adapters return GraphDataset with an explicit Domain and time_unit. CSV parsing
and validation are dependency-free. The original Elliptic reader joins class rows
by ID, not CSV position; requires matching node/class sets; bounds bytes and rows;
and rejects bad widths, labels, time steps, duplicates and dangling endpoints.
BankingColumns maps a declared source schema to account and event fields. It is
not an unverified mapping of every AMLSim output version. Amounts must be finite
and nonnegative; duplicate event IDs fail, but repeated account pairs remain.
A banking input must represent one currency or pre-normalized amounts; multi-
currency analytics require explicit currency fields and policy in Phase 2.

FeatureExtractor shares only a method and FeatureRecord schema: domain, entity
ID, cutoff, time unit, feature version and named numeric values. IDs are only
unique within their domain. Do not concatenate graphs or mix label targets.
DegreeFeatures is a small reference implementation with inclusive temporal
cutoffs; banking degree counts transfer events. Bitcoin edges are visible only
when both endpoint transactions are visible. Full-graph reference extraction is
for small data; distributed implementations will keep this contract separately.

Spark code resides under spark/ and never imports training/. Training consumes
persisted, versioned feature tables in Phase 2 and never starts Spark implicitly.
No data-derived normalizers or supervised models are fitted in Phase 1.
Original Elliptic anonymized aggregates need a leakage audit before use in a
strict historical prediction task; filtering nodes alone cannot establish that
the provided aggregate features are causal.
