"""Fail closed on invalid identifiers, numeric values, labels and endpoints."""
import math
from .contracts import Domain, GraphDataset


class ValidationError(ValueError):
    pass


def validate(graph: GraphDataset) -> None:
    if not isinstance(graph.domain, Domain) or not graph.time_unit:
        raise ValidationError("domain and time unit required")
    ids = [n.entity_id for n in graph.nodes]
    if not ids or any(not i.strip() for i in ids) or len(ids) != len(set(ids)):
        raise ValidationError("node IDs must be nonempty and unique")
    known = set(ids)
    for node in graph.nodes:
        if node.label not in {"licit", "illicit", "unknown"}:
            raise ValidationError("unsupported label")
        if any(not math.isfinite(v) for v in node.features):
            raise ValidationError("nonfinite node feature")
        if graph.domain == Domain.BITCOIN:
            if node.time_step is None or not 1 <= node.time_step <= 49:
                raise ValidationError("Elliptic time step must be 1..49")
    event_ids = set()
    for edge in graph.edges:
        if edge.source not in known or edge.target not in known:
            raise ValidationError("dangling edge endpoint")
        if graph.domain == Domain.BANKING:
            if not edge.event_id or edge.event_id in event_ids:
                raise ValidationError("banking event IDs must be nonempty and unique")
            event_ids.add(edge.event_id)
            if edge.time_step is None or edge.time_step < 0:
                raise ValidationError("banking event time must be nonnegative")
            if edge.amount is None or not math.isfinite(edge.amount) or edge.amount < 0:
                raise ValidationError("banking amount must be finite and nonnegative")
