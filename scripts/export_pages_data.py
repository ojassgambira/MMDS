"""Export an explicit public aggregate DTO, never transaction rows or private models."""

import argparse
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mmd_fraud.evidence import load, load_benchmarks  # noqa: E402
from mmd_fraud.dashboard_graph import example  # noqa: E402
from mmd_fraud.report_links import hosted_report  # noqa: E402

METRICS = (
    "precision",
    "recall",
    "f1",
    "pr_auc_average_precision",
    "false_positive_rate",
    "confusion_matrix",
    "confusion_matrix_order",
    "rows",
    "threshold",
)
FILES = {
    "elliptic.json",
    "banking.json",
    "benchmarks.json",
    "graphs.json",
    "report.json",
    "report.md",
    "elliptic-evaluation.png",
    "banking-evaluation.png",
    "spark-processing.png",
}


def pick(value, names):
    return {key: value[key] for key in names}


def project(source):
    """Allowlist every published level; unknown source fields cannot become web assets."""
    domain = source["domain"]
    positive = "illicit" if domain == "elliptic" else "sar_positive"
    evidence = pick(source["evidence"], ("workflow", "artifact_sha256"))
    if not re.fullmatch(
        r"https://github.com/ojassgambira/MMDS/actions/runs/\d+", evidence["workflow"]
    ) or not re.fullmatch(r"[a-f0-9]{64}", evidence["artifact_sha256"]):
        raise ValueError("invalid public evidence provenance")
    result = pick(source, ("schema_version", "domain", "dataset_kind"))
    result["evidence"] = evidence
    stats = (
        ("nodes", "edges", "unknown_excluded", "labels")
        if domain == "elliptic"
        else ("nodes", "edges", "unknown_excluded", "account_days")
    )
    result["stats"] = pick(source["stats"], stats)
    if domain == "elliptic":
        result["stats"]["labels"] = pick(source["stats"]["labels"], ("unknown", "1", "2"))
    result["runs"] = []
    for run in source["runs"]:
        item = pick(run, ("seed", "selected_family"))
        item["split_counts"] = {
            name: pick(run["split_counts"][name], ("rows", positive))
            for name in ("train", "validation", "test")
        }
        item["families"] = {}
        for name, family in run["families"].items():
            if not re.fullmatch(r"[a-z_]+", name):
                raise ValueError("invalid public family name")
            projected = {
                "candidate": family["candidate"],
                "feature_count": len(family["features"]) if "features" in family else None,
            }
            for key in ("validation", "test", "test_fixed"):
                if key in family:
                    projected[key] = pick(family[key], (*METRICS, positive))
            if "test_curve" in family:
                curve = family["test_curve"]
                projected["test_curve"] = {
                    **pick(curve, ("method", "rows", "positive")),
                    "points": [pick(p, ("precision", "recall")) for p in curve["points"]],
                }
            item["families"][name] = projected
        keys = (
            ("step", "rows", "unknown", "illicit", "licit")
            if domain == "elliptic"
            else ("time_step", "events", "volume", "sar_payments")
        )
        item["temporal"] = [pick(row, keys) for row in run["temporal"]]
        keys = (
            ("step", "visible_nodes", "visible_edges", "seconds")
            if domain == "elliptic"
            else ("cutoff_day", "accounts", "events", "unique_directed_pairs", "seconds")
        )
        item["benchmarks"] = [pick(row, keys) for row in run["benchmarks"]]
        item["per_step"] = {
            family: [pick(p, ("step", "rows", "average_precision")) for p in points]
            for family, points in run.get("per_step", {}).items()
            if family in item["families"]
        }
        item["intervals"] = {
            family: {
                metric: pick(interval, ("lower_95", "upper_95", "valid_resamples"))
                for metric, interval in values.items()
                if metric in ("pr_auc_average_precision", "f1", "recall", "false_positive_rate")
            }
            for family, values in run["intervals"].items()
            if family in item["families"]
        }
        result["runs"].append(item)
    if domain == "banking":
        result["family_means"] = {
            name: {
                metric: statistics.mean(r["families"][name]["test"][metric] for r in result["runs"])
                for metric in METRICS[:5]
            }
            for name in result["runs"][0]["families"]
        }
    return result


def export(output):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    if any(p.is_symlink() or p.name not in FILES | {"manifest.json"} for p in output.iterdir()):
        raise ValueError("export directory contains unexpected files; refusing publication")

    def write(name, value):
        (output / name).write_text(
            json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False) + "\n"
        )

    for domain in ("elliptic", "banking"):
        write(f"{domain}.json", project(load(domain)))
    bench = load_benchmarks()
    configuration = pick(
        bench["configuration"],
        (
            "runtime",
            "master",
            "driver_memory",
            "shuffle_partitions",
            "default_parallelism",
            "spark",
            "python",
            "java",
            "cpu_count_visible",
            "machines",
            "distributed_multi_worker_verified",
            "order",
            "repetitions",
            "scope",
        ),
    )
    write(
        "benchmarks.json",
        {
            "configuration": configuration,
            "measurements": [
                pick(row, ("domain", "nodes", "events", "input_bytes", "seconds", "output_rows"))
                for row in bench["measurements"]
            ],
        },
    )
    graphs = {}
    for domain in ("elliptic", "banking"):
        nodes, edges = example(
            domain, 80
        )  # Generated in cloud Python, never from private source rows.
        nodes = [
            {
                **node,
                "x": math.cos(i * 2 * math.pi / len(nodes)),
                "y": math.sin(i * 2 * math.pi / len(nodes)),
            }
            for i, node in enumerate(nodes)
        ]
        graphs[domain] = {
            "domain": domain,
            "dataset_kind": "generated_illustration",
            "nodes": nodes,
            "edges": edges,
        }
    write("graphs.json", graphs)
    report = ROOT / "docs/final-research-report.md"
    text = hosted_report(report.read_text(), report, ROOT)
    write("report.json", {"title": "MMDS final research report", "markdown": text})
    portable = (
        text
        + "\n"
        + "\n".join(
            f"![Aggregate research figure](https://raw.githubusercontent.com/ojassgambira/MMDS/main/docs/figures/{name})"
            for name in (
                "elliptic-evaluation.png",
                "banking-evaluation.png",
                "spark-processing.png",
            )
        )
    )
    (output / "report.md").write_text(portable)
    for name in ("elliptic-evaluation.png", "banking-evaluation.png", "spark-processing.png"):
        raw = (ROOT / "docs/figures" / name).read_bytes()
        if not raw.startswith(b"\x89PNG\r\n\x1a\n") or len(raw) > 2_000_000:
            raise ValueError("invalid aggregate figure")
        (output / name).write_bytes(raw)
    source = json.loads((ROOT / "dashboard/data/manifest.json").read_text())["sha256"]
    manifest = {
        "schema_version": 1,
        "source_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "source_dirty": bool(
            subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT, text=True).strip()
        ),
        "aggregate_source_sha256": source,
        "files": {
            name: hashlib.sha256((output / name).read_bytes()).hexdigest() for name in sorted(FILES)
        },
    }
    write("manifest.json", manifest)
    verify(output)
    return manifest


def verify(output):
    output = Path(output)
    manifest = json.loads((output / "manifest.json").read_text())
    if set(manifest["files"]) != FILES:
        raise ValueError("unexpected static publication manifest")
    for name, expected in manifest["files"].items():
        path = output / name
        if (
            path.is_symlink()
            or path.stat().st_size > 2_000_000
            or hashlib.sha256(path.read_bytes()).hexdigest() != expected
        ):
            raise ValueError("invalid static public asset")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "frontend/public/data")
    args = parser.parse_args()
    result = export(args.output)
    print(
        json.dumps(
            {
                "status": "passed",
                "files": len(result["files"]),
                "source_commit": result["source_commit"],
                "scope": "verified public aggregates and explicitly generated illustrations only",
            }
        )
    )
