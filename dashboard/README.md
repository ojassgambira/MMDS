# Read-only research dashboard

Entry point: `dashboard/app.py`. The lightweight hosting environment installs root
`requirements.txt`; full development/CI installs `requirements-cloud.lock`.

Six pages cover both real Elliptic and independently generated synthetic banking:
statistics, graph exploration, temporal patterns, model comparisons/actual PR
curves, processing benchmarks and the final research report. Default graph views
are labeled generated illustrations; operator-provisioned private graphs have
asserted, unverified provenance. Aggregate snapshots are hash-verified and checked
for metric arithmetic, label semantics and curve populations.

[Cloud access and free deployment instructions](../docs/dashboard.md).
Cloud integration/HTTP checks are verified; a public hosted URL is not. External
GitHub authorization for free Streamlit hosting remains necessary. No workload
needs to run on a personal computer.
