"""Bounded sparse mining of completed-step snapshots, downstream of Spark validation.

No label is used unless its step is strictly earlier AND in the training period.
Sparse CPU mining is deliberately bounded to the original release scale.
"""
import time

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from scipy import sparse
from scipy.sparse.csgraph import connected_components

from .experiments import GRAPH_FEATURES, TRANSACTION_FEATURES

DIRECTIONAL = ('pagerank_in', 'pagerank_out')
STRUCTURAL = ('component_size', 'component_density', 'component_degree_mean',
              'component_source_fraction', 'component_sink_fraction', 'community_size',
              'community_internal_fraction', 'community_degree_mean')
LABEL_HISTORY = ('historical_labeled_neighbors', 'historical_fraud_fraction')
ROLL_INPUTS = ('in_degree', 'out_degree', 'total_degree', *TRANSACTION_FEATURES[:8])
ROLLING = tuple(f'{prefix}_{name}' for name in ROLL_INPUTS
                for prefix in ('rolling_mean', 'rolling_std', 'anomaly'))
ADVANCED = (*GRAPH_FEATURES, *DIRECTIONAL, *STRUCTURAL, *LABEL_HISTORY)
RESEARCH_FAMILIES = {
    'transaction_only': TRANSACTION_FEATURES,
    'advanced_graph': ADVANCED,
    'rolling_temporal': ROLLING,
    'transaction_graph': (*TRANSACTION_FEATURES, *ADVANCED),
    'transaction_rolling': (*TRANSACTION_FEATURES, *ROLLING),
    'combined': (*TRANSACTION_FEATURES, *ADVANCED, *ROLLING),
    'without_direction': (*TRANSACTION_FEATURES, *GRAPH_FEATURES, *STRUCTURAL, *LABEL_HISTORY, *ROLLING),
    'without_components': (*TRANSACTION_FEATURES, *GRAPH_FEATURES, *DIRECTIONAL, *LABEL_HISTORY, *ROLLING),
}


def pagerank(adjacency, iterations=30):
    """Fixed-iteration damped PageRank, including dangling mass; no convergence claim."""
    n = adjacency.shape[0]
    degree = np.asarray(adjacency.sum(axis=1)).ravel()
    transition = sparse.diags(1 / np.maximum(degree, 1)) @ adjacency
    score = np.full(n, 1 / n)
    for _ in range(iterations):
        score = .15 / n + .85 * (transition.T @ score + score[degree == 0].sum() / n)
    return score * n  # size-normalized; component size is a separate feature



def communities(graph, initial):
    """Eight synchronous majority-vote sweeps, deterministic ties; heuristic partition."""
    graph = (graph + graph.T).astype(bool)
    graph.setdiag(True)  # self vote stabilizes isolated nodes
    u, v = graph.nonzero()
    labels = initial.copy()
    for _ in range(8):
        pairs, counts = np.unique(np.column_stack((u, labels[v])), axis=0, return_counts=True)
        order = np.lexsort((pairs[:, 1], -counts, pairs[:, 0]))
        ordered = pairs[order]
        first = np.r_[True, ordered[1:, 0] != ordered[:-1, 0]]
        updated = labels.copy()
        updated[ordered[first, 0]] = ordered[first, 1]
        if np.array_equal(updated, labels):
            break
        labels = updated
    return np.unique(labels, return_inverse=True)[1]


def mine_snapshots(ids, steps, labels, source, target, train_end=34):
    n = len(ids)
    if not 0 < n <= 300000 or len(source) > 500000:
        raise ValueError('research graph exceeds validated bounded release limits')
    index = {name: i for i, name in enumerate(ids)}
    if len(index) != n or len(steps) != n or len(labels) != n:
        raise ValueError('invalid research node identities')
    if len(source) != len(target) or any(v not in index for v in (*source, *target)):
        raise ValueError('research edge has missing endpoint')
    steps = np.asarray(steps)
    labels = np.asarray(labels)
    a = np.array([index[v] for v in source], dtype=int)
    b = np.array([index[v] for v in target], dtype=int)
    features = {name: np.zeros(n) for name in (*DIRECTIONAL, *STRUCTURAL, *LABEL_HISTORY)}
    timings = []
    for step in sorted(set(steps)):
        began = time.monotonic()
        visible = np.flatnonzero(steps <= step)
        focal = np.flatnonzero(steps == step)
        mapping = np.full(n, -1, dtype=int)
        mapping[visible] = np.arange(len(visible))
        mask = (steps[a] <= step) & (steps[b] <= step)
        u, v = mapping[a[mask]], mapping[b[mask]]
        graph = sparse.csr_matrix((np.ones(len(u)), (u, v)), shape=(len(visible), len(visible)))
        graph.sum_duplicates()
        if graph.nnz:
            graph.data[:] = 1
        forward, backward = pagerank(graph), pagerank(graph.T.tocsr())
        _, components = connected_components(graph, directed=True, connection='weak')
        sizes = np.bincount(components)
        outdegree = np.asarray(graph.sum(axis=1)).ravel()
        indegree = np.asarray(graph.sum(axis=0)).ravel()
        edge_counts = np.bincount(components, weights=outdegree)
        ranks = np.argsort(np.argsort(np.asarray(ids)[visible]))
        community = communities(graph, ranks)
        community_size = np.bincount(community)
        internal = community[u] == community[v]
        internal_degree = np.bincount(np.r_[u[internal], v[internal]], minlength=len(visible))
        values = {
            'community_size': community_size[community],
            'community_internal_fraction': internal_degree / np.maximum(outdegree + indegree, 1),
            'community_degree_mean': np.bincount(community, weights=outdegree + indegree)[community] / community_size[community],
            'pagerank_in': forward, 'pagerank_out': backward,
            'component_size': sizes[components],
            'component_density': edge_counts[components] / np.maximum(sizes[components] * (sizes[components] - 1), 1),
            'component_degree_mean': 2 * edge_counts[components] / sizes[components],
            'component_source_fraction': np.bincount(components, weights=(indegree == 0))[components] / sizes[components],
            'component_sink_fraction': np.bincount(components, weights=(outdegree == 0))[components] / sizes[components],
        }
        undirected = (graph + graph.T).astype(bool).astype(float)
        undirected.setdiag(0)
        known = (steps[visible] < step) & (steps[visible] <= train_end) & (labels[visible] != 'unknown')
        count = undirected @ known.astype(float)
        fraud = undirected @ (known & (labels[visible] == '1')).astype(float)
        values['historical_labeled_neighbors'] = count
        values['historical_fraud_fraction'] = np.divide(fraud, count, out=np.zeros_like(fraud), where=count > 0)
        for name, values_here in values.items():
            features[name][focal] = values_here[mapping[focal]]
        timings.append({'step': int(step), 'visible_nodes': len(visible), 'visible_edges': int(graph.nnz),
                        'seconds': time.monotonic() - began})
    audit = {'nodes': n, 'edges': len(a), 'cross_step_edges': int((steps[a] != steps[b]).sum()),
             'forward_time_edges': int((steps[a] < steps[b]).sum()),
             'backward_time_edges': int((steps[a] > steps[b]).sum()),
             'self_loops': int((a == b).sum()),
             'historical_label_feature_nonzero': int((features['historical_labeled_neighbors'] > 0).sum()),
             'snapshot_benchmarks': timings}
    return features, audit


def rolling_features(table):
    steps = table['time_step'].to_numpy()
    result = {}
    for name in ROLL_INPUTS:
        values = table[name].to_numpy().astype(float)
        mean, std = np.zeros(len(values)), np.zeros(len(values))
        for step in sorted(set(steps)):
            # Five prior source time steps, not five prior rows; population weighted.
            history = values[(steps >= step - 5) & (steps < step)]
            current = steps == step
            if len(history):
                mean[current], std[current] = history.mean(), history.std()
        result[f'rolling_mean_{name}'] = mean
        result[f'rolling_std_{name}'] = std
        result[f'anomaly_{name}'] = np.abs(values - mean) / (std + 1)
    return result


def build_research(features_path, edges_path, output, train_end=34):
    datasets = [pq.ParquetDataset(features_path), pq.ParquetDataset(edges_path)]
    for dataset, limit in zip(datasets, (300000, 500000)):
        if sum(pq.read_metadata(p).num_rows for p in dataset.files) > limit:
            raise ValueError('research input exceeds bounded release limits before materialization')
    table = datasets[0].read()
    edges = datasets[1].read(columns=['source', 'target'])
    mined, audit = mine_snapshots(table['entity_id'].to_pylist(), table['time_step'].to_numpy(),
                                 table['label'].to_pylist(), edges['source'].to_pylist(),
                                 edges['target'].to_pylist(), train_end)
    for name, values in {**mined, **rolling_features(table)}.items():
        table = table.append_column(name, pa.array(values))
    names = list(dict.fromkeys(c for v in RESEARCH_FAMILIES.values() for c in v))
    quality = {}
    for period, mask in {'train': table['time_step'].to_numpy() <= train_end,
                         'test': table['time_step'].to_numpy() >= 40}.items():
        quality[period] = {}
        for name in names:
            values = table[name].to_numpy()[mask]
            if not np.isfinite(values).all():
                raise ValueError('nonfinite research features')
            quality[period][name] = {'mean': float(values.mean()), 'std': float(values.std()),
                                     'zero_fraction': float((values == 0).mean())}
    audit['feature_quality'] = quality
    steps, labels = table['time_step'].to_numpy(), np.array(table['label'].to_pylist())
    audit['step_populations'] = [{'step': int(t), 'rows': int((steps == t).sum()),
        'unknown': int(((steps == t) & (labels == 'unknown')).sum()),
        'illicit': int(((steps == t) & (labels == '1')).sum()),
        'licit': int(((steps == t) & (labels == '2')).sum())} for t in sorted(set(steps))]
    pq.write_table(table, output)
    restored = pq.read_table(output)
    if not restored.equals(table):
        raise ValueError('research Parquet round-trip mismatch')
    return audit
