"""Semantic contracts; sharing interfaces does not merge graph domains."""
from dataclasses import dataclass
from enum import Enum
from typing import Protocol


class Domain(str, Enum):
    BITCOIN = "bitcoin_transaction"
    BANKING = "banking_account"


@dataclass(frozen=True)
class Node:
    entity_id: str
    time_step: int | None = None
    features: tuple[float, ...] = ()
    label: str = "unknown"


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    event_id: str | None = None
    time_step: int | None = None
    amount: float | None = None


@dataclass(frozen=True)
class GraphDataset:
    domain: Domain
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]
    time_unit: str


@dataclass(frozen=True)
class FeatureRecord:
    domain: Domain
    entity_id: str
    cutoff_step: int
    time_unit: str
    values: dict[str, float]
    schema_version: str = "1"


class FeatureExtractor(Protocol):
    def extract(self, graph: GraphDataset, cutoff_step: int) -> tuple[FeatureRecord, ...]: ...
