# Development rules
All development, Python, Java, Spark, tests, data processing, training and deployment
must run in Codex Cloud or GitHub-hosted CI. Never require workloads on the user's Mac.
Use Python 3.12 and Spark 4.0.1 with Java 17 or 21. Keep pinned requirements compatible.
Keep Bitcoin transaction nodes distinct from banking account nodes. Preserve edge
multiplicity and domain-specific time units. Unknown labels are not negatives.
Keep Spark transformations under src/mmd_fraud/spark and training under training.
Use generated fixtures; no large datasets or model artifacts in Git. Put real data
outside the checkout, e.g. /workspace/data. Do not print or commit credentials.
Do not provision paid infrastructure, bypass network controls, or download multi-GB data.
Do not execute upstream install scripts without inspection. Do not train at scale until
Phase 1 smoke verification passes. Report skipped and failed checks truthfully.
Cloud checks:
- PYTHONPATH=src python -m unittest discover -s tests -v
- python -m pytest -q
- python -m ruff check .
- PYTHONPATH=src python scripts/spark_smoke.py
