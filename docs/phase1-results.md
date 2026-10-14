# Phase 1 execution record

Executed on 2026-10-14 in Codex Cloud, /workspace/MMDS. No workload ran on a Mac.
The initial checkout had no tracked files or local commits; its origin was
https://github.com/ojassgambira/MMDS.git. Remote main contained a short README. The first fetch populated FETCH_HEAD only;
an explicit remote-tracking ref fetch and a merge connected the foundation to
main history, preserving the original project title and resolving the README conflict. Python 3.12.14 and Java JRE 21.0.12.1
were present; javac, Maven, PySpark, pytest and ruff were initially absent.

## Commands and actual outcomes

| Commands | Outcome |
| --- | --- |
| pwd; ls -la; rg --files; git status --short; git remote -v; git log -1 --oneline | Empty checkout, connected GitHub remote; initial local log unavailable |
| python --version; java -version; command -v javac; command -v mvn | Python/Java present; compiler and Maven absent |
| cat /etc/codex/network-policy.json; cloud environment status | Restricted proxy policy; no VPN or configured credentials; runtime policy state unknown |
| curl upstream README and requirements | Initial sandbox proxy connections failed; no files fetched by curl |
| python -m venv .venv | Created isolated cloud environment |
| .venv/bin/python -m pip install pyspark==4.0.1 pytest==8.4.2 ruff==0.13.3 setuptools==80.9.0 wheel==0.45.1 | Initial sandbox request failed due to proxy/network permission; not a package-version incompatibility |
| PYTHONPATH=src python -m unittest discover -s tests -v | Before dependencies: 15 passed, 1 Spark test skipped |
| PYTHONPATH=src python scripts/spark_smoke.py | Before dependencies: failed with missing PySpark |
| .venv/bin/python -m pip install --retries 0 -r requirements-dev.lock | With supported additional network permission: succeeded; Spark package download about 434 MB, no dataset downloads |
| .venv/bin/python -m pip install --no-build-isolation --no-deps -e . | Succeeded |
| .venv/bin/python -m pip check | No broken requirements |
| .venv/bin/python -m ruff check . | All checks passed |
| SPARK_LOCAL_IP=127.0.0.1 PYSPARK_PYTHON=/workspace/MMDS/.venv/bin/python .venv/bin/python -m pytest -q | 16 passed in 9.26s, including Spark; cloud network permission enabled for Spark sockets |
| .venv/bin/python scripts/spark_smoke.py | Succeeded: records=4, cutoff_step=2, source_accounts=2 |
| .venv/bin/python -m unittest discover -s tests -v | Final dependency-installed run: 16 passed in 8.783s, no skips |
| PYTHONPATH=src python -m compileall -q src scripts tests; git diff --check | Succeeded |

Research used connected GitHub fetch for IBM/AMLSim README, requirements.txt and
pom.xml and connected web research for the Elliptic publisher, original paper
and Spark installation documentation. GitHub research permissions do not imply
Kaggle credentials or simulator dependencies are available in the cloud shell.

Smoke output verifies generated event identity, inclusive temporal filtering,
Python worker execution and account-level sum/count aggregation with a shuffle.
Spark logged its usual incubator-vector and native-Hadoop fallback warnings.
The unittest Spark run also emitted a PySpark socket ResourceWarning after collect;
it did not fail the test, and Spark stop runs in a finally block.

AMLSim simulation was deferred because the legacy dependency stack, Java compiler
and MASON are unavailable; compatibility is not verified. No Elliptic source files
were acquired; adapter correctness was tested with generated original-width CSVs.
No model training, deployment, paid resource provisioning or multi-machine
benchmark was performed. GitHub CI execution is separate from these cloud results;
its current status must be checked on the pull request.
