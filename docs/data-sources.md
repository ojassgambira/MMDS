# Data sources

Original Elliptic release (not Elliptic++, Elliptic2, or an address graph):
https://www.kaggle.com/datasets/ellipticco/elliptic-data-set
Research source: https://arxiv.org/abs/1908.02591
Source documentation was consulted via connected research tools on 2026-10-14;
no source CSVs were downloaded. The paper describes approximately 200K transaction
nodes and 234K payment-flow edges. Expected original release counts are 203,769
nodes and 234,355 edges; confirm them against the acquired release manifest.

| File | Layout |
| --- | --- |
| elliptic_txs_features.csv | no header; transaction ID, integer time step, 165 numeric features (167 columns total) |
| elliptic_txs_classes.csv | header txId,class; 1 illicit, 2 licit, unknown unlabeled |
| elliptic_txs_edgelist.csv | header txId1,txId2; directed transaction-to-transaction flow |

The advertised 166 attributes include the time step. Steps are 1–49; do not
interpret them as UNIX timestamps or infer wallet ownership. Feature names are
anonymous, so the adapter uses positions rather than invented meanings. Unknown
labels must be excluded from supervised target fitting, not mapped to licit.

Acquisition is a separate, explicitly authorized cloud activity: visit the
publisher's Kaggle release, review its current terms/license and version, then
use a credentialed cloud Kaggle download or upload an authorized cloud copy to
/workspace/data/elliptic. Record hashes, byte sizes, source URL and release date
before ingestion. Kaggle access and exact current terms were not validated in
this runtime. Do not download multi-GB datasets in Phase 1.

Edit configs/elliptic.json and run, in cloud:
`PYTHONPATH=src python scripts/validate_elliptic.py --config configs/elliptic.json`.
Configured limits fail rather than silently truncate: samples need internally
consistent feature/class/edge files (an induced subgraph). The adapter retains
all bounded rows in memory; this is not the distributed full-data ingestion path.

AMLSim: https://github.com/IBM/AMLSim
Use pinned upstream commits and their schema configuration. Accounts are nodes,
transactions are events; alerts and SAR memberships are synthetic scenario labels,
not proven real-world illicit behavior. Raw tx logs and converted transactions
have different schemas. No simulator outputs were obtained in Phase 1.

## Original release metadata verified 2026-10-15

The publisher's public dataset API (`https://www.kaggle.com/api/v1/datasets/view/ellipticco/elliptic-data-set`)
returned version 1, last updated 2019-07-31, totalBytes 697,459,499 and license
“Attribution-NonCommercial-NoDerivatives 4.0 International (CC BY-NC-ND 4.0)”.
PyG's upstream `torch_geometric/datasets/elliptic.py` identifies
`https://data.pyg.org/datasets/elliptic` as its download source. Three bounded
HTTP Range inspections of that mirror confirmed the original filenames and ZIP
member sizes; see [measurements and execution boundaries](issue-7.md). Metadata
inspection establishes neither publisher signatures nor successful model training.
Use the release for the authorized private noncommercial project; do not publish
raw/derived dataset files in GitHub artifacts. The CI validation publishes only
aggregate audits, timings and statuses.
