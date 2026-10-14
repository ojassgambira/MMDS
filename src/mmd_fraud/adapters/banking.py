"""Configurable banking CSV boundary; not a promise of one universal AMLSim schema."""
import csv
from dataclasses import dataclass
from pathlib import Path
from ..contracts import Domain, Edge, GraphDataset, Node
from ..validation import ValidationError, validate


@dataclass(frozen=True)
class BankingColumns:
    account_id: str = "account_id"
    event_id: str = "transaction_id"
    source: str = "source_account"
    target: str = "target_account"
    step: str = "step"
    amount: str = "amount"


def load_banking(accounts: Path, transactions: Path, columns: BankingColumns = BankingColumns(),
                 max_rows: int = 100_000, max_file_bytes: int = 50_000_000) -> GraphDataset:
    def read(path, required):
        if path.stat().st_size > max_file_bytes:
            raise ValidationError("banking file exceeds byte limit")
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if not set(required).issubset(reader.fieldnames or []):
                raise ValidationError("missing banking CSV columns")
            for index, row in enumerate(reader):
                if index >= max_rows:
                    raise ValidationError("banking row limit exceeded")
                yield row
    try:
        nodes = tuple(Node(row[columns.account_id]) for row in read(accounts, [columns.account_id]))
        required = [columns.event_id, columns.source, columns.target, columns.step, columns.amount]
        edges = tuple(Edge(row[columns.source], row[columns.target], row[columns.event_id],
                           int(row[columns.step]), float(row[columns.amount]))
                      for row in read(transactions, required))
        graph = GraphDataset(Domain.BANKING, nodes, edges, "simulation_step")
        validate(graph)
        return graph
    except (ValueError, TypeError, KeyError) as exc:
        raise ValidationError(f"invalid banking CSV: {exc}") from exc
