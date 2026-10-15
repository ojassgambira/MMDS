"""Completed-step graph mining and strictly previous-step population baselines."""
from pyspark.sql import DataFrame, Window, functions as F

from .causal import FEATURES, end_of_step_features

LOCAL_FEATURE_COUNT = 93  # Publisher: first 94 local attributes include time; CSV ID is not a feature.
GRAPH_FEATURES = (*FEATURES, 'incoming_fraction', 'degree_imbalance', 'reciprocal_neighbors',
                  'neighbor_degree_mean', 'neighbor_degree_max', 'neighbor_excess_degree_sum')
TEMPORAL_FEATURES = tuple(f'{prefix}_{name}' for name in FEATURES
                          for prefix in ('past_mean', 'past_std', 'relative'))
TRANSACTION_FEATURES = tuple(f'local_{i:03}' for i in range(LOCAL_FEATURE_COUNT))
FAMILIES = {'transaction_only': TRANSACTION_FEATURES, 'graph_only': GRAPH_FEATURES,
            'temporal': TEMPORAL_FEATURES,
            'combined': (*TRANSACTION_FEATURES, *GRAPH_FEATURES, *TEMPORAL_FEATURES)}


def graph_mining(nodes: DataFrame, edges: DataFrame) -> DataFrame:
    base = end_of_step_features(nodes, edges)
    incoming = edges.filter('available_step <= target_step').select(
        F.col('target').alias('entity_id'), F.col('source').alias('neighbor'),
        F.lit(1).alias('incoming'), F.lit(0).alias('outgoing'))
    outgoing = edges.filter('available_step <= source_step').select(
        F.col('source').alias('entity_id'), F.col('target').alias('neighbor'),
        F.lit(0).alias('incoming'), F.lit(1).alias('outgoing'))
    links = (incoming.unionByName(outgoing).filter('entity_id != neighbor')
             .groupBy('entity_id', 'neighbor').agg(F.max('incoming').alias('incoming'),
                                                F.max('outgoing').alias('outgoing')))
    # A neighbor's own completed-step degree is frozen. For any visible link its
    # completion is <= focal completion, even for non-original cross-step fixtures.
    links = links.join(base.select(F.col('entity_id').alias('neighbor'),
                                   F.col('total_degree').alias('neighbor_degree')), 'neighbor')
    mined = links.groupBy('entity_id').agg(
        F.sum(F.col('incoming') * F.col('outgoing')).alias('reciprocal_neighbors'),
        F.avg('neighbor_degree').alias('neighbor_degree_mean'),
        F.max('neighbor_degree').alias('neighbor_degree_max'),
        F.sum(F.greatest(F.col('neighbor_degree') - 1, F.lit(0))).alias('neighbor_excess_degree_sum'))
    return (base.join(mined, 'entity_id', 'left')
            .fillna(0, list(GRAPH_FEATURES[8:]))
            .withColumn('incoming_fraction', F.col('in_degree') / (F.col('total_degree') + 1))
            .withColumn('degree_imbalance', F.abs(F.col('in_degree') - F.col('out_degree')) /
                        (F.col('total_degree') + 1)))


def temporal_features(graph: DataFrame) -> DataFrame:
    # All transactions (including unknowns) from strictly earlier steps, no labels.
    aggregates = graph.groupBy('time_step').agg(F.count('*').alias('step_n'), *[
        expr for name in FEATURES for expr in
        (F.sum(name).alias(f'sum_{name}'),
         F.sum(F.col(name).cast('double') ** 2).alias(f'sq_{name}'))])
    history = Window.orderBy('time_step').rowsBetween(Window.unboundedPreceding, -1)
    aggregates = aggregates.withColumn('past_n', F.coalesce(F.sum('step_n').over(history), F.lit(0)))
    for name in FEATURES:
        mean = F.coalesce(F.sum(f'sum_{name}').over(history) / F.nullif(F.col('past_n'), F.lit(0)), F.lit(0))
        second = F.coalesce(F.sum(f'sq_{name}').over(history) / F.nullif(F.col('past_n'), F.lit(0)), F.lit(0))
        aggregates = (aggregates.withColumn(f'past_mean_{name}', mean)
                      .withColumn(f'past_std_{name}', F.sqrt(F.greatest(second - mean ** 2, F.lit(0)))))
    context = ['time_step', *[f'{p}_{n}' for n in FEATURES for p in ('past_mean', 'past_std')]]
    result = graph.join(aggregates.select(*context), 'time_step')
    for name in FEATURES:
        result = result.withColumn(f'relative_{name}',
                                   (F.col(name) - F.col(f'past_mean_{name}')) /
                                   (F.col(f'past_std_{name}') + 1))
    return result


def experiment_features(nodes: DataFrame, edges: DataFrame) -> DataFrame:
    mined = temporal_features(graph_mining(nodes, edges))
    local = nodes.select('entity_id', *[F.col('source_features')[i].alias(name)
                                       for i, name in enumerate(TRANSACTION_FEATURES)])
    # The remaining 72 anonymous forward/backward neighborhood aggregates are excluded.
    return (mined.join(local, 'entity_id').withColumn('schema_version', F.lit('comparison_v1')))
