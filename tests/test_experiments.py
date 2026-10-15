"""Generated fixtures prove feature timing and validation-only search decisions."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from mmd_fraud.spark.experiments import (FAMILIES, GRAPH_FEATURES, TEMPORAL_FEATURES,
                                        TRANSACTION_FEATURES, experiment_features)
from mmd_fraud.spark.pipeline import session
from mmd_fraud.training.comparison import train_comparison, validation_threshold
from mmd_fraud.training.baselines import evaluate


class ExperimentTrainingTests(unittest.TestCase):
    def records(self):
        names = set(c for v in FAMILIES.values() for c in v)
        return [{'entity_id': f'{step}-{label}', 'time_step': step, 'label': label,
                 'feature_cutoff_exclusive': step + 1,
                 **{c: float((step % 4) + int(label == '1')) for c in names}}
                for step in range(1, 50) for label in ('1', '2', 'unknown')]

    def test_threshold_uses_validation_f1_with_fpr_constraint(self):
        y = np.array([0, 0, 0, 1, 1])
        score = np.array([.1, .2, .7, .6, .9])
        threshold = validation_threshold(y, score)
        checked = evaluate(y, score, threshold)
        self.assertEqual(checked['false_positive_rate'], 0)
        self.assertEqual(checked['recall'], .5)
        self.assertGreater(threshold, .7)
        with self.assertRaises(ValueError):
            validation_threshold(y, score, -1)

    def test_test_intervention_cannot_change_selection_scalers_or_thresholds_and_cache_reuses(self):
        with tempfile.TemporaryDirectory() as temp, patch(
                'mmd_fraud.training.comparison.CANDIDATES', ('logistic_c01', 'hist_balanced')):
            root = Path(temp)
            rows = self.records()
            source = root / 'features.parquet'
            pq.write_table(pa.Table.from_pylist(rows), source)
            original_bytes = source.read_bytes()
            a = train_comparison(source, root / 'one', root / 'cache')
            with patch('mmd_fraud.training.comparison.candidate', side_effect=AssertionError('refit cached trial')):
                restored = train_comparison(source, root / 'restored', root / 'cache')
            self.assertEqual(a, restored)
            for row in rows:
                if row['time_step'] >= 40:
                    for name in TRANSACTION_FEATURES:
                        row[name] += 10000
                    if row['label'] in {'1', '2'}:
                        row['label'] = '1' if row['label'] == '2' else '2'
            pq.write_table(pa.Table.from_pylist(rows), source)
            b = train_comparison(source, root / 'two', root / 'cache')
            self.assertEqual(a['selected_family'], b['selected_family'])
            for family in FAMILIES:
                for key in ('candidate', 'threshold', 'validation', 'validation_fixed'):
                    self.assertEqual(a['families'][family][key], b['families'][family][key])
            frozen = json.loads((root / 'one/selection.json').read_text())
            self.assertNotIn('test', frozen['families']['combined'])
            checkpoint = root / 'cache' / a['search_identity'] / 'transaction_only-logistic_c01.joblib'
            checkpoint.write_text('corruption')
            # Reuse a cache whose input identity still matches.
            source.write_bytes(original_bytes)
            with self.assertRaisesRegex(ValueError, 'corrupt comparison'):
                train_comparison(source, root / 'broken', root / 'cache')

    def test_feature_contract_excludes_time_ids_labels_and_neighbor_source_aggregates(self):
        self.assertEqual(len(TRANSACTION_FEATURES), 93)
        self.assertEqual(len(FAMILIES['combined']), len(set(FAMILIES['combined'])))
        for names in FAMILIES.values():
            self.assertFalse({'time_step', 'label', 'entity_id', 'source_features'} & set(names))
            self.assertNotIn('local_093', names)


class ExperimentSparkTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.spark = session({'driver_memory': '1g', 'partitions': 2}, Path(cls.temp.name) / 'checkpoint')

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()
        cls.temp.cleanup()

    def test_future_edges_source_aggregates_and_labels_cannot_change_prior_predictors(self):
        s = self.spark
        nodes = s.createDataFrame([
            ('1', 1, '1', [1.] * 93 + [900.] * 72),
            ('2', 1, '2', [2.] * 93 + [800.] * 72),
            ('3', 2, 'unknown', [3.] * 93 + [700.] * 72)],
            'entity_id string,time_step int,label string,source_features array<double>')
        edges = s.createDataFrame([('1', '2', 1, 1, 1), ('2', '3', 1, 2, 2)],
            'source string,target string,source_step int,target_step int,available_step int')
        a = {r.entity_id: r.asDict() for r in experiment_features(nodes, edges).collect()}
        self.assertEqual(a['1']['neighbor_degree_mean'], 1)
        self.assertEqual(a['1']['past_mean_total_degree'], 0)
        self.assertEqual(a['3']['past_mean_total_degree'], 1)
        self.assertEqual(a['3']['past_std_total_degree'], 0)
        self.assertEqual(a['3']['relative_total_degree'], 0)
        future = edges.unionByName(s.createDataFrame([('3', '1', 2, 1, 2)], edges.schema))
        changed = s.createDataFrame([('1', 1, 'unknown', [1.] * 93 + [-9.] * 72),
                                     ('2', 1, '1', [2.] * 93 + [-8.] * 72),
                                     ('3', 2, '2', [30.] * 93 + [-7.] * 72)], nodes.schema)
        b = {r.entity_id: r.asDict() for r in experiment_features(changed, future).collect()}
        names = (*TRANSACTION_FEATURES, *GRAPH_FEATURES, *TEMPORAL_FEATURES)
        for txid in ('1', '2'):
            self.assertEqual({c: a[txid][c] for c in names}, {c: b[txid][c] for c in names})
        # Step 2 context excludes all current-step changes, including its new edge.
        for name in TEMPORAL_FEATURES:
            if name.startswith('past_'):
                self.assertEqual(a['3'][name], b['3'][name])
