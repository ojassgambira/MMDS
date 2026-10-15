# Elliptic feature comparison and bounded tuning

This round adds four predeclared feature families to the existing free hosted
pipeline. The GitHub job enables `experiments: true` automatically; private
`run_cloud.py` configurations can opt in using the same boolean. Baseline checks,
license/version/ZIP-size review, source validation, original chronological
baselines and checkpoint behavior remain in place.

## Source and timing assumptions

The publisher's dataset API description was inspected on 2026-10-15:
https://www.kaggle.com/api/v1/datasets/view/ellipticco/elliptic-data-set
It describes the first **94 attributes as local, including the time step**, and
72 remaining attributes as backward/forward one-hop neighborhood aggregates.
After removing transaction ID and time, the CSV contains 93 local numeric values
followed by 72 aggregates. This experiment uses positions 0–92 of the stored
165-value source array and excludes positions 93–164 entirely. Anonymous feature
names are not assigned invented economic meanings.

Even the publisher-local attributes include opaque summaries associated with
inputs/outputs. Their exact construction/normalization and live availability
cannot be independently established from this release. These are offline
comparisons using publisher-designated local attributes, not proof that all
transaction predictors exist at transaction broadcast. Train-only scaling is
used for logistic/boosting candidates; tree fits use only training observations.
A live fraud system would need an independently timed feature audit. The
structural-only feature families do not consume anonymous source attributes.

The original release has **no edges between source steps**. Graph mining therefore
uses each completed step's component, without pretending it contains persistent
wallet/account identities or cross-step transaction links. All predictors are
for retrospective classification after a transaction's source step completes.
Same-step edges are permitted only under that declared timing assumption.

## Predeclared feature families

| Family | Features | Count |
| --- | --- | ---: |
| transaction_only | Publisher-designated local numeric values; time/ID excluded | 93 |
| graph_only | Existing six causal counts, incoming fraction, degree imbalance, reciprocal neighbors, neighbor degree mean/max and summed excess degree | 12 |
| temporal | Previous-step population mean/std and current transaction's relative deviation for each of the original six graph counts | 18 |
| combined | The union of these three sets | 123 |

Graph neighbors must be visible by focal completion. A neighbor's degree is
frozen at **its own completed step**, which is no later than focal completion.
This conservative rule also supports cross-step generated fixtures. Summed
neighbor excess degree is a length-two walk proxy, not a count of distinct
two-hop identities. No quadratic path expansion or full-graph clustering is used.

Temporal context pools **all transactions from strictly earlier steps**, including
unknown-label nodes but never labels. It uses population-weighted first/second
moments, not averages of step averages. The current step is excluded from its own
baseline. With no history, means/stds are zero; relative deviation divides by
`past_std + 1`. During validation/test, earlier unlabelled step statistics may
advance causally; estimators/scalers remain frozen after training. No absolute
time number, transaction ID, label or publisher neighborhood aggregate enters
any model matrix.

## Fixed search and evaluation protocol

The grid is fixed before real execution: **five candidates per family, 20 fits**.

| Candidate | Parameters / imbalance handling |
| --- | --- |
| Logistic C=0.1 | Train-fitted StandardScaler; balanced class weights, max_iter=1000 |
| Logistic C=1 | Same; different fixed regularization |
| Random forest | 128 trees, depth 12, min leaf 3, balanced_subsample, two fitting workers, sequential inference |
| Histogram gradient boosting | Train-fitted StandardScaler, 150 iterations, 15 leaves, learning rate 0.08, L2=1, unweighted |
| Balanced histogram boosting | Same; training-derived balanced weights |

Boosting's random internal early-stopping split is disabled. No oversampling or
SMOTE uses validation/test observations. Candidate class weights use training
labels only. All three original chronological baseline models are still reported
separately for comparison with PR #10.

Train steps **1–34**, validation **35–39**, test **40–49**. Unknown labels are
excluded from supervised arrays. Stable step/lexicographic-ID ordering, seed 0,
pinned dependencies and two thread limits are preserved. Each family's candidate
is selected by validation **average precision**; ties favor earlier grid order.
The global family is selected by validation AP before any test prediction. Four
family winners are evaluated for the requested comparison, without selecting
between them using test results.

For each winner, choose the validation threshold maximizing F1 with validation
FPR <= **5%**, resolving ties toward the higher threshold. This enumerates all
attainable probability thresholds, including predicting no positives. The cap is
a validation operating-point policy, **not a guarantee about test FPR**. Reports
also retain fixed-0.5 metrics to separate feature/model improvements from threshold
selection. Precision, recall, F1, AP, FPR and confusion matrices are retained for
both periods; AP is independent of the operating threshold.

The test period was already inspected in earlier project PRs. This grid and policy
are fixed before this round's execution, but repeated research use does not create
a fresh external lockbox. No search expansion or threshold adjustment is justified
by this round's test metrics. Label availability remains an offline assumption.

## Resources, resumability and public evidence

Existing two-worker Spark/2 GB heap, 30-minute worker/40-minute job, disk reserve,
8 GB workspace, source row/byte and download limits remain unchanged. The larger
forest is explicitly bounded at 128 trees/depth 12; no GPU/GNN/paid runtime or
unbounded hyperparameter service is used.

Feature extraction and comparison are separately hash-verified stages. Each
candidate has a private atomic model/record checkpoint under the run identity;
restarts reuse only matching source-feature hashes, columns, code, split and seed.
Model hashes and re-evaluated validation metrics are checked before cache reuse.
Uncommitted temporary files do not mark a trial complete. Selection is persisted
before test evaluation. Corrupt checkpoints fail closed. Source hashes are included
in aggregate evidence; no source rows or models are published.

Only three allowlisted aggregate evidence files leave the hosted runner. Public
reports include all feature names, trial validation scores, thresholds, source
fingerprints, family metrics and stage artifact hashes/sizes. Private raw data,
Parquet, candidate/winner models and complete logs are deleted after the hosted
job. Cross-job private persistence still needs separately authorized private
storage; GitHub data/model caches are not used. No Colab execution or Google OAuth
is needed for the GitHub workflow.

## Verification

Results are established only by the PR's completed real-data workflow and verified
aggregate artifact. Synthetic tests exercise feature timing, forbidden aggregate
exclusion, future/label/test interventions, FPR thresholding, cache reuse/integrity,
and the expanded generated end-to-end pipeline. Real model metrics are reported
in the PR after actual execution; no Colab result is inferred from cloud CI.
