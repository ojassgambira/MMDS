# Final submission-readiness audit

Audit date: 2026-10-18. Verified PR #14 merged; inspected main commit
`c06dc5d5250fbf02a7a458012747f1f388879979`. Audit implementation and final check
results are recorded in the accompanying pull request and its GitHub checks.

## Scope and findings resolved

| Area | Finding and resolution |
| --- | --- |
| Entry documentation | README, architecture and dashboard README still described early phases; rewritten for both completed domains and actual cloud boundaries |
| Colab reproducibility | Notebook preferred an old fix branch if it still existed; now fetches main only, with a regression guard and current browser links |
| Evidence integrity | Hashes/population totals alone did not detect internally inconsistent published metrics; added binary matrix, target order, positive counts, finite score arithmetic and curve population/order checks |
| Graph provenance | Private graph hover/count text said generated; now shows operator-provisioned unverified provenance; rejects edges before endpoint availability |
| Secret diagnostics | Quoted JSON credential fields escaped earlier redaction; added structured-value redaction and regression cases |
| Results consistency | Added deterministic evidence-derived results summary and a stale-table regression guard; existing metric snapshots unchanged |
| Submission package | Added cloud installation/execution guide, methodology, current architecture diagram, presentation script and this audit |
| CI | Submission audit runs in the supported-Python matrix; tests check document links, notebook routing, aggregate semantics and security failure cases |

## Verification protocol

Run the following in the full managed cloud environment from the repository root:

```sh
python scripts/audit_submission.py
python -m pytest -q
PYTHONPATH=src python -m unittest discover -s tests -v
python -m ruff check .
PYTHONPATH=src python scripts/spark_smoke.py
python scripts/dashboard_smoke.py
python -m pip check
```

The audit needs no external dataset: it checks versioned aggregate fingerprints,
metric arithmetic, PR point populations, documentation link destinations, results
synchronization, notebook syntax/unexecuted state and main-branch selection.
It does **not** recompute AP from raw scores or independently authenticate sources.
The accompanying PR records cloud test results and final-head GitHub workflow URLs.
Existing source evidence is preserved in `dashboard/data`; source workflow/archive
hashes remain in each snapshot. No new model gain is claimed by this audit.

## Verified managed-cloud checks

Codex Cloud Python 3.12.14 completed **110 pytest tests** (231.46 seconds) and
**110 unittest tests** (220.458 seconds). The UI-only environment passed all six
pages for both domains without Spark/sklearn installed. Dependency consistency,
Ruff, actionlint, snapshot integrity, local links and results synchronization passed.
The standalone Spark smoke passed with cutoff step 2, four records and two source
accounts. Fresh PR CI results are recorded in the accompanying pull request. These are actual cloud checks, not hosted Colab or public hosting
verification. Training source, Spark feature code, frozen snapshot bytes and the
existing research figures are unchanged by the audit.

## Submission checklist

- [Project overview and target definitions](../README.md)
- [Architecture diagram and processing boundaries](architecture.md)
- [Installation, automation, storage and failure recovery](cloud-execution.md)
- [Methodology and evaluation assumptions](methodology.md)
- [Evidence-derived results summary](results-summary.md)
- [Final research report, tables, plots and limitations](final-research-report.md)
- [Presentation narrative and demo fallback](presentation.md)
- [Benchmark measurements/configurations](benchmarks.md)
- [Data terms/source review](data-sources.md) and [AMLSim assessment](amlsim-feasibility.md)
- [Dashboard access and privacy](dashboard.md)

These materials form a repository-based research submission. The institution's
specific rubric, cover sheet, student details, slide/PDF format and upload portal
were not supplied; compliance with an unseen rubric cannot be verified. No
student/institution details or final upload are fabricated.

## Remaining external boundaries

**Public dashboard hosting:** cloud integration and HTTP tests do not establish a
public deployment. Free Streamlit Community Cloud requires external account/GitHub
OAuth, unavailable to the current tools. Entry point, Python version and exact
browser steps are ready in the dashboard guide. If a live URL is mandatory for the
rubric, this remains a blocker; the checked-in report/figures are a demo fallback.

**Colab:** no actual hosted Colab/Drive execution has been verified. Account sign-in,
runtime connection and Drive consent are unavoidable if that optional route is
used. No manual Colab debugging is required for the GitHub route.

**Scientific scope:** independent synthetic banking is not real fraud; official
AMLSim was not executed; Bitcoin feature availability is retrospective; previous
test inspection/limited periods constrain generalization. Single-machine Spark
benchmarks do not establish distributed scaling. These are disclosed limitations,
not missing experiments disguised as successful results.

**Access, retention and licensing:** external sources/free runner capacity can
change; artifacts expire after seven days, while aggregate snapshots remain in Git.
Dataset redistribution is restricted by reviewed terms. The repository has no
separate code reuse license; no blanket open-source permission is asserted.
