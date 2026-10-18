"""Dataset-free submission integrity audit and deterministic results summary."""

import argparse
import ast
import json
from pathlib import Path
import re
import statistics
import sys
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mmd_fraud.evidence import load, load_benchmarks  # noqa: E402


def results_markdown():
    lines = [
        "# Verified results summary",
        "",
        "Generated from hash-verified versioned aggregate snapshots by",
        "`python scripts/audit_submission.py --write-results`. No training occurs.",
        "",
        "AP is full-ranking average precision; thresholds and models use validation only.",
        "These domains have different populations and targets: do not rank them against each other.",
        "",
        "## Real Elliptic Bitcoin",
        "",
        "203,769 transaction nodes; 234,355 edges; 157,205 unknown labels excluded from supervision.",
        "Train steps 1–34, validation 35–39, test 40–49 (11,184 known test labels).",
        "",
        "| Family | AP | Precision | Recall | F1 | FPR |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    real, bank = load("elliptic"), load("banking")
    keys = ["pr_auc_average_precision", "precision", "recall", "f1", "false_positive_rate"]
    for name, item in real["runs"][0]["families"].items():
        lines.append(
            "| " + name + " | " + " | ".join(f"{item['test'][k]:.6f}" for k in keys) + " |"
        )
    lines += [
        "",
        "Validation-selected family: **" + real["runs"][0]["selected_family"] + "**.",
        "Structural additions have uncertain AP gains; exploratory paired intervals do not",
        "establish an overall improvement. Publisher-local feature availability is not independently",
        "verified. This is retrospective completed-step classification, not live fraud screening.",
        "",
        "## Independent synthetic banking",
        "",
        "Not official IBM AMLSim output or real bank fraud. Positive target: next-day simulated",
        "SAR payment involvement. Three fixed seeds; 500 accounts, 33,600 payments and 24,500",
        "account-days per seed. Test: 5,000 account-days per seed. Features use days strictly before t.",
        "",
        "Arithmetic means across seeds (not pooled predictions):",
        "",
        "| Family | Mean AP | Mean precision | Mean recall | Mean F1 | Mean FPR |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for name in bank["runs"][0]["families"]:
        values = [
            statistics.mean(r["families"][name]["test"][k] for r in bank["runs"]) for k in keys
        ]
        lines.append("| " + name + " | " + " | ".join(f"{v:.6f}" for v in values) + " |")
    lines += [
        "",
        "Combined is validation-selected for all three seeds. Synthetic motifs are intentionally",
        "learnable; these scores do not establish effectiveness on real banks or unseen typologies.",
        "",
        "## Evidence and interpretation",
        "",
        f"- [Real workflow]({real['evidence']['workflow']}); archive SHA-256 `{real['evidence']['artifact_sha256']}`.",
        f"- [Synthetic workflow]({bank['evidence']['workflow']}); archive SHA-256 `{bank['evidence']['artifact_sha256']}`.",
        "- Snapshot byte hashes: `dashboard/data/manifest.json`. Source artifacts expire after seven days;",
        "  curated aggregate snapshots, figures and workflow/PR summaries preserve the submission evidence.",
        "- [Full methodology, ablations, uncertainty and limitations](final-research-report.md).",
        "- [Measured single-machine benchmarks](benchmarks.md); no distributed multi-worker claim.",
        "",
    ]
    return "\n".join(lines)


def broken_links(root=ROOT):
    errors = []
    documents = [
        root / "README.md",
        root / "dashboard/README.md",
        *sorted((root / "docs").rglob("*.md")),
    ]
    for path in documents:
        for target in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", path.read_text()):
            url = urlsplit(target.strip("<>"))
            if url.scheme or not url.path:
                continue
            destination = (path.parent / unquote(url.path)).resolve()
            if not destination.is_relative_to(root.resolve()) or not destination.exists():
                errors.append(f"{path.relative_to(root)}: {target}")
    return errors


def audit():
    real, bank = load("elliptic"), load("banking")
    bench = load_benchmarks()
    errors = broken_links()
    if errors:
        raise ValueError("Broken/escaping documentation links: " + "; ".join(errors))
    if (ROOT / "docs/results-summary.md").read_text() != results_markdown():
        raise ValueError("Results summary differs from verified evidence; regenerate it")
    notebook = json.loads((ROOT / "notebooks/MMDS_Cloud_Pipeline.ipynb").read_text())
    code = "\n".join("".join(c["source"]) for c in notebook["cells"] if c["cell_type"] == "code")
    ast.parse(code)
    if "ref = 'main'" not in code or "fix/issue-" in code:
        raise ValueError("Notebook must fetch main rather than a historical fix branch")
    for cell in notebook["cells"]:
        if cell["cell_type"] == "code" and (cell["outputs"] or cell["execution_count"] is not None):
            raise ValueError("Notebook contains execution output")
    required = [
        "docs/architecture.md",
        "docs/cloud-execution.md",
        "docs/methodology.md",
        "docs/presentation.md",
        "docs/submission-audit.md",
        "docs/final-research-report.md",
    ]
    if any(not (ROOT / p).is_file() for p in required):
        raise ValueError("Submission document missing")
    if real["stats"]["nodes"] != 203769 or real["stats"]["edges"] != 234355:
        raise ValueError("Unexpected original Elliptic release population")
    populations = real["runs"][0]["temporal"]
    if (
        [r["step"] for r in populations] != list(range(1, 50))
        or sum(r["rows"] for r in populations) != real["stats"]["nodes"]
        or any(sum(r[k] for k in ("licit", "illicit", "unknown")) != r["rows"] for r in populations)
    ):
        raise ValueError("Elliptic temporal population mismatch")
    for run in bank["runs"]:
        daily = run["temporal"]
        if (
            [r["time_step"] for r in daily] != list(range(50))
            or sum(r["events"] for r in daily) != bank["stats"]["edges"]
            or sum(v["rows"] for v in run["split_counts"].values()) != bank["stats"]["account_days"]
        ):
            raise ValueError("Synthetic temporal/split population mismatch")
    readme = (ROOT / "README.md").read_text()
    for key in ("pr_auc_average_precision", "f1", "recall", "false_positive_rate"):
        real_value = real["runs"][0]["families"][real["runs"][0]["selected_family"]]["test"][key]
        bank_value = statistics.mean(r["families"]["combined"]["test"][key] for r in bank["runs"])
        if any(f"{v:.6f}" not in readme for v in (real_value, bank_value)):
            raise ValueError("README summary differs from preserved metrics")
    curves = sum(
        "test_curve" in f for d in (real, bank) for r in d["runs"] for f in r["families"].values()
    )
    return {
        "status": "passed",
        "domains": [real["dataset_kind"], bank["dataset_kind"]],
        "measured_curves": curves,
        "measured_spark_sizes": len(bench["measurements"]),
        "local_links": "passed",
        "results_summary": "matches frozen evidence",
        "public_hosting_verified": False,
        "colab_execution_verified": False,
        "scope": "aggregate integrity and documentation; no dataset access/training or public deployment",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--write-results", action="store_true")
    args = parser.parse_args()
    if args.write_results:
        (ROOT / "docs/results-summary.md").write_text(results_markdown())
    print(json.dumps(audit(), indent=2))
