"""Read-only, versioned aggregate contracts shared by reports and the dashboard."""

import hashlib
import json
from pathlib import Path

DOMAINS = ("elliptic", "banking")
ROOT = Path(__file__).resolve().parents[2]


def load(domain, directory=None):
    if domain not in DOMAINS:
        raise ValueError("unknown research domain")
    directory = Path(directory) if directory else ROOT / "dashboard/data"
    path = directory / f"{domain}.json"
    if path.stat().st_size > 2_000_000:
        raise ValueError("aggregate evidence exceeds 2 MB")
    manifest = json.loads((directory / "manifest.json").read_text())
    if hashlib.sha256(path.read_bytes()).hexdigest() != manifest["sha256"][path.name]:
        raise ValueError("dashboard evidence hash mismatch")
    data = json.loads(path.read_text())
    if data["schema_version"] != 1 or data["domain"] != domain:
        raise ValueError("dashboard evidence domain/schema mismatch")
    expected = (
        "original_elliptic_release" if domain == "elliptic" else "independent_synthetic_banking"
    )
    if data["dataset_kind"] != expected:
        raise ValueError("dashboard provenance mismatch")
    for run in data["runs"]:
        if run["selected_family"] not in run["families"]:
            raise ValueError("invalid validation selection")
        for family in run["families"].values():
            m = family["test"]
            if sum(sum(row) for row in m["confusion_matrix"]) != m["rows"]:
                raise ValueError("confusion matrix population mismatch")
    return data


def verify_artifact(directory, manifest_name):
    """Only named aggregate source reports may enter the snapshot importer."""
    directory = Path(directory)
    manifest = json.loads((directory / manifest_name).read_text())["sha256"]
    allowed = {
        "training-summary.json",
        "training-report.md",
        "research-report.md",
        "research-results.png",
        "banking-summary.json",
        "banking-report.md",
        "banking-results.png",
    }
    if not manifest or not set(manifest) <= allowed:
        raise ValueError("unexpected evidence file in manifest")
    summary = (
        "training-summary.json" if manifest_name.startswith("training") else "banking-summary.json"
    )
    if summary not in manifest:
        raise ValueError("summary hash is required")
    for name, expected in manifest.items():
        path = directory / name
        if path.is_symlink() or path.stat().st_size > 5_000_000:
            raise ValueError("invalid aggregate evidence file")
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError("source evidence hash mismatch")


def compact(source, domain, provenance):
    if domain == "elliptic":
        if (
            not source.get("real_training_verified")
            or source["dataset_kind"] != "original_elliptic_release"
        ):
            raise ValueError("real full Elliptic evidence required")
        r = source["research"]
        runs = [
            {
                "seed": r["seed"],
                "families": r["families"],
                "selected_family": r["selected_family"],
                "split_counts": r["split_counts"],
                "temporal": r["audit"]["step_populations"],
                "per_step": r["per_step"],
                "benchmarks": r["audit"]["snapshot_benchmarks"],
                "intervals": r["paired_step_bootstrap"],
            }
        ]
        stats = {
            "nodes": source["validation"]["nodes"],
            "edges": source["validation"]["edges"],
            "labels": source["validation"]["labels"],
            "unknown_excluded": r["unknown_excluded"],
        }
    else:
        if (
            source["dataset_kind"] != "independent_synthetic_banking"
            or source["official_amlsim_output"]
        ):
            raise ValueError("independent synthetic banking evidence required")
        runs = []
        for r in source["runs"]:
            runs.append(
                {
                    "seed": r["seed"],
                    "families": {
                        **r["comparison"]["families"],
                        "isolation_forest": {"candidate": "isolation_forest", **r["anomaly"]},
                    },
                    "selected_family": r["comparison"]["selected_family"],
                    "split_counts": r["comparison"]["split_counts"],
                    "temporal": r["validation"].get("daily", []),
                    "benchmarks": r["graph_benchmarks"],
                    "intervals": r["paired_intervals"],
                }
            )
        stats = {
            "nodes": source["runs"][0]["validation"]["nodes"],
            "edges": source["runs"][0]["validation"]["events"],
            "account_days": source["runs"][0]["validation"]["account_days"],
            "unknown_excluded": 0,
        }
    for run in runs:
        for item in run["families"].values():
            for name in ("trials", "model_sha256", "fit_seconds"):
                item.pop(name, None)
    return {
        "schema_version": 1,
        "domain": domain,
        "dataset_kind": source["dataset_kind"],
        "evidence": provenance,
        "stats": stats,
        "runs": runs,
    }


def import_snapshot(source_directory, domain, provenance, destination=None):
    if domain not in DOMAINS:
        raise ValueError("unknown research domain")
    directory = Path(source_directory)
    name = "training" if domain == "elliptic" else "banking"
    verify_artifact(directory, f"{name}-evidence-manifest.json")
    source = json.loads((directory / f"{name}-summary.json").read_text())
    result = compact(source, domain, provenance)
    destination = Path(destination) if destination else ROOT / "dashboard/data"
    destination.mkdir(parents=True, exist_ok=True)
    path = destination / f"{domain}.json"
    path.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n")
    manifest = {
        "sha256": {
            p.name: hashlib.sha256(p.read_bytes()).hexdigest()
            for p in destination.glob("*.json")
            if p.name in ("elliptic.json", "banking.json", "spark-benchmarks.json")
        }
    }
    (destination / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    load(domain, destination)
    return path


def load_benchmarks(directory=None):
    directory = Path(directory) if directory else ROOT / "dashboard/data"
    path = directory / "spark-benchmarks.json"
    manifest = json.loads((directory / "manifest.json").read_text())["sha256"]
    if hashlib.sha256(path.read_bytes()).hexdigest() != manifest[path.name]:
        raise ValueError("Spark benchmark hash mismatch")
    data = json.loads(path.read_text())
    config = data["configuration"]
    if (
        config["master"] != "local[2]"
        or config["machines"] != 1
        or config["distributed_multi_worker_verified"]
    ):
        raise ValueError("unsupported benchmark scaling claim")
    for row in data["measurements"]:
        if row["seconds"] <= 0 or row["output_rows"] != row["nodes"]:
            raise ValueError("invalid Spark benchmark measurement")
    return data
