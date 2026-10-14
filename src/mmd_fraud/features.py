"""Tiny reference extractor; distributed implementations belong in spark/."""
from .contracts import Domain, FeatureRecord, GraphDataset
from .validation import validate


class DegreeFeatures:
    def extract(self, graph: GraphDataset, cutoff_step: int) -> tuple[FeatureRecord, ...]:
        validate(graph)
        if cutoff_step < 0:
            raise ValueError("cutoff must be nonnegative")
        visible = {n.entity_id for n in graph.nodes
                   if n.time_step is None or n.time_step <= cutoff_step}
        counts = {key: {"in_degree": 0.0, "out_degree": 0.0} for key in visible}
        for edge in graph.edges:
            if edge.source not in visible or edge.target not in visible:
                continue
            if graph.domain == Domain.BANKING and edge.time_step > cutoff_step:
                continue
            counts[edge.source]["out_degree"] += 1
            counts[edge.target]["in_degree"] += 1
        return tuple(FeatureRecord(graph.domain, key, cutoff_step, graph.time_unit, counts[key])
                     for key in sorted(visible))
