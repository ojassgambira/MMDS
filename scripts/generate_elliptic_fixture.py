"""Generate bounded Bitcoin correctness fixtures, never substitute for real Elliptic."""
import argparse
import csv
import json
from pathlib import Path
from mmd_fraud.data.acquire import outside_repo


def generate(destination: Path, nodes: int) -> None:
    if not 2 <= nodes <= 10000:
        raise ValueError("fixture size must be 2..10000")
    destination = outside_repo(destination)
    destination.mkdir(parents=True, exist_ok=False)
    with (destination / "elliptic_txs_features.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        for index in range(nodes):
            writer.writerow([str(index + 1), 1 + index * 49 // nodes] + [float(index % 7)] * 165)
    with (destination / "elliptic_txs_classes.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["txId", "class"])
        writer.writerows((str(index + 1), "unknown") for index in range(nodes))
    with (destination / "elliptic_txs_edgelist.csv").open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["txId1", "txId2"])
        writer.writerows((str(index), str(index + 1)) for index in range(1, nodes))
    (destination / "fixture.json").write_text(json.dumps({"generated_test_fixture": True,
                                                         "nodes": nodes, "edges": nodes - 1}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--nodes", type=int, default=1000)
    args = parser.parse_args()
    generate(args.destination, args.nodes)
