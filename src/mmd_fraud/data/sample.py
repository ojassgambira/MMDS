"""Bounded, deterministic induced samples for cloud notebook smoke processing."""
import csv
import json
import tempfile
from collections import Counter
from pathlib import Path

from .acquire import FILES, outside_repo, sha256, MAX_EXPANDED_BYTES


def sample_elliptic(source: Path, destination: Path, per_step: int = 40,
                   max_rows: int = 300000, max_bytes: int = MAX_EXPANDED_BYTES,
                   max_sample_edges: int = 10000) -> dict:
    """Keep the first per_step transactions at each source step, then induced edges.

    This is a reproducible correctness sample, not a representative benchmark or
    training split. Source record counts are audited; Spark validates sampled values.
    """
    source, destination = outside_repo(source), outside_repo(destination)
    if not 1 <= per_step <= 200 or min(max_rows, max_bytes, max_sample_edges) <= 0:
        raise ValueError("invalid sample limits")
    if destination.exists():
        raise FileExistsError("sample destination already exists")
    paths = [source / name for name in FILES]
    if sum(path.stat().st_size for path in paths) > max_bytes:
        raise ValueError("source exceeds byte budget")
    selected, ids, steps = set(), set(), Counter()
    labels, class_ids = Counter(), set()
    source_edges = sample_edges = 0
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        stage = Path(temporary)
        with paths[0].open(newline="") as handle, (stage / FILES[0]).open("w", newline="") as out:
            writer = csv.writer(out)
            for count, row in enumerate(csv.reader(handle), 1):
                if count > max_rows or len(row) != 167:
                    raise ValueError("source features exceed row limit or have invalid width")
                txid, step = row[:2]
                if not txid.isdecimal() or txid in ids or not step.isdecimal():
                    raise ValueError("invalid or duplicate source feature ID/step")
                step = int(step)
                if not 1 <= step <= 49:
                    raise ValueError("invalid source step")
                ids.add(txid)
                steps[step] += 1
                if steps[step] <= per_step:
                    selected.add(txid)
                    writer.writerow(row)
        with paths[1].open(newline="") as handle, (stage / FILES[1]).open("w", newline="") as out:
            reader, writer = csv.reader(handle), csv.writer(out)
            if next(reader, []) != ["txId", "class"]:
                raise ValueError("invalid classes header")
            writer.writerow(["txId", "class"])
            for count, row in enumerate(reader, 1):
                if count > max_rows or len(row) != 2:
                    raise ValueError("invalid classes rows")
                txid, label = row
                if txid in class_ids or txid not in ids or label not in {"1", "2", "unknown"}:
                    raise ValueError("invalid class ID or label")
                class_ids.add(txid)
                labels[label] += 1
                if txid in selected:
                    writer.writerow(row)
        if not ids or class_ids != ids:
            raise ValueError("empty source or mismatched class IDs")
        with paths[2].open(newline="") as handle, (stage / FILES[2]).open("w", newline="") as out:
            reader, writer = csv.reader(handle), csv.writer(out)
            if next(reader, []) != ["txId1", "txId2"]:
                raise ValueError("invalid edges header")
            writer.writerow(["txId1", "txId2"])
            for row in reader:
                source_edges += 1
                if source_edges > max_rows or len(row) != 2 or not set(row).issubset(ids):
                    raise ValueError("invalid source edge or row limit exceeded")
                if set(row).issubset(selected):
                    sample_edges += 1
                    if sample_edges > max_sample_edges:
                        raise ValueError("sample edges exceed small profile; lower per_step")
                    writer.writerow(row)
        if not sample_edges:
            raise ValueError("sample has no edges; choose a larger bounded per_step")
        manifest = {
            "selection": "first transactions per step in source order; induced edges",
            "per_step": per_step, "sample_nodes": len(selected),
            "sample_edges_raw": sample_edges, "source_nodes": len(ids),
            "source_edges_raw": source_edges, "source_labels": dict(labels),
            "source_steps": sorted(steps), "source_step_counts": dict(steps),
            "inputs": [{"file": p.name, "sha256": sha256(p)} for p in paths],
            "outputs": [{"file": n, "sha256": sha256(stage / n)} for n in FILES],
        }
        (stage / "sample.json").write_text(json.dumps(manifest, indent=2) + "\n")
        stage.rename(destination)
    return manifest
