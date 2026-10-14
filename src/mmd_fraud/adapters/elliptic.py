"""Bounded standard-library ingestion for original Elliptic CSVs, without downloads."""
import csv
from dataclasses import dataclass
from pathlib import Path
from ..contracts import Domain, Edge, GraphDataset, Node
from ..validation import ValidationError, validate


@dataclass(frozen=True)
class EllipticConfig:
    directory: Path
    features_file: str = "elliptic_txs_features.csv"
    classes_file: str = "elliptic_txs_classes.csv"
    edges_file: str = "elliptic_txs_edgelist.csv"
    numeric_feature_count: int = 165
    max_rows: int = 300_000
    max_file_bytes: int = 300_000_000


def rows(path: Path, *, header: bool, max_rows: int, max_file_bytes: int):
    if path.stat().st_size > max_file_bytes:
        raise ValidationError(f"file exceeds configured byte limit: {path.name}")
    with path.open(newline="", encoding="utf-8-sig") as handle:
        reader = csv.reader(handle)
        if header:
            yield next(reader, [])
        for index, row in enumerate(reader):
            if index >= max_rows:
                raise ValidationError(f"row limit exceeded: {path.name}")
            yield row


def load_elliptic(config: EllipticConfig) -> GraphDataset:
    def read(name, header=False):
        return rows(config.directory / name, header=header,
                    max_rows=config.max_rows, max_file_bytes=config.max_file_bytes)

    try:
        labels = {}
        classes = read(config.classes_file, True)
        if next(classes) != ["txId", "class"]:
            raise ValidationError("expected class header txId,class")
        mapping = {"1": "illicit", "2": "licit", "unknown": "unknown"}
        for row in classes:
            if len(row) != 2 or row[0] in labels or row[1] not in mapping:
                raise ValidationError("invalid or duplicate class record")
            labels[row[0]] = mapping[row[1]]
        nodes = []
        for row in read(config.features_file):
            if len(row) != config.numeric_feature_count + 2:
                raise ValidationError("incorrect feature column count")
            if row[0] not in labels:
                raise ValidationError("missing class record")
            nodes.append(Node(row[0], int(row[1]), tuple(map(float, row[2:])), labels[row[0]]))
        if set(labels) != {n.entity_id for n in nodes}:
            raise ValidationError("class and feature IDs differ")
        edge_rows = read(config.edges_file, True)
        if next(edge_rows) != ["txId1", "txId2"]:
            raise ValidationError("expected edge header txId1,txId2")
        edges = []
        for row in edge_rows:
            if len(row) != 2:
                raise ValidationError("incorrect edge column count")
            edges.append(Edge(*row))
        graph = GraphDataset(Domain.BITCOIN, tuple(nodes), tuple(edges), "elliptic_step")
        validate(graph)
        return graph
    except (ValueError, StopIteration) as exc:
        raise ValidationError(f"invalid Elliptic CSV: {exc}") from exc
