"""Phase 4 causal snapshots, direction, sparse limits and paired inference regressions."""
import tempfile
from pathlib import Path
import unittest

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq
from scipy import sparse

from mmd_fraud.cloud_config import validate_config
from mmd_fraud.spark.research import (mine_snapshots, pagerank, rolling_features,
                                      RESEARCH_FAMILIES, build_research)
from mmd_fraud.training.research import paired_intervals
from mmd_fraud.training.comparison import train_comparison
import test_experiments


class ResearchTests(unittest.TestCase):
    def test_pagerank_direction_dangling_mass_and_isolates(self):
        graph = sparse.csr_matrix(([1., 1.], ([0, 1], [1, 2])), shape=(4, 4))
        incoming, outgoing = pagerank(graph), pagerank(graph.T.tocsr())
        self.assertGreater(incoming[2], incoming[0])
        self.assertGreater(outgoing[0], outgoing[2])
        self.assertAlmostEqual(incoming.sum(), 4.)
        np.testing.assert_allclose(pagerank(sparse.csr_matrix((3, 3))), np.ones(3))

    def test_future_graph_labels_and_order_cannot_change_completed_snapshot(self):
        ids, steps, labels = ['a', 'b', 'c', 'd'], [1, 1, 2, 3], ['1', 'unknown', '2', '1']
        first, audit = mine_snapshots(ids, steps, labels, ['a', 'b'], ['b', 'c'], train_end=1)
        changed, _ = mine_snapshots(ids, steps, ['2', 'unknown', '1', '2'],
                                     ['a', 'b', 'd'], ['b', 'c', 'a'], train_end=1)
        for name in first:
            np.testing.assert_array_equal(first[name][:2], changed[name][:2])
        self.assertEqual(first['historical_labeled_neighbors'][0], 0)  # no own-step labels
        self.assertEqual(first['historical_labeled_neighbors'][2], 0)  # unknown is never negative
        self.assertEqual(audit['cross_step_edges'], 1)
        # Strictly prior, training-only labels may be used at the later endpoint.
        labeled, _ = mine_snapshots(['a', 'b', 'c'], [1, 2, 3], ['1', '1', '2'],
                                    ['a', 'b'], ['b', 'c'], train_end=1)
        self.assertEqual(labeled['historical_fraud_fraction'][1], 1)
        self.assertEqual(labeled['historical_labeled_neighbors'][2], 0)
        order = [2, 0, 3, 1]
        reordered, _ = mine_snapshots([ids[i] for i in order], [steps[i] for i in order],
                                      [labels[i] for i in order], ['a', 'b'], ['b', 'c'], train_end=1)
        for name in first:
            np.testing.assert_allclose(reordered[name], first[name][order])

    def test_schema_bounds_and_missing_endpoints(self):
        with self.assertRaisesRegex(ValueError, 'missing endpoint'):
            mine_snapshots(['a'], [1], ['1'], ['a'], ['missing'])
        with self.assertRaisesRegex(ValueError, 'identities'):
            mine_snapshots(['a', 'a'], [1, 1], ['1', '2'], [], [])
        with self.assertRaisesRegex(ValueError, 'bounded'):
            mine_snapshots([], [], [], [], [])
        self.assertNotIn('label', set(c for v in RESEARCH_FAMILIES.values() for c in v))
        with self.assertRaisesRegex(ValueError, 'requires experiments'):
            validate_config({'research': True})
        with self.assertRaisesRegex(ValueError, 'fixes splits'):
            validate_config({'experiments': True, 'research': True, 'train_end': 33})

    def test_rolling_window_excludes_current_future_and_expired_steps(self):
        from mmd_fraud.spark.research import ROLL_INPUTS
        rows = [{'time_step': t, **{c: float(t) for c in ROLL_INPUTS}} for t in range(1, 10)]
        a = rolling_features(pa.Table.from_pylist(rows))
        self.assertEqual(a['rolling_mean_total_degree'][0], 0)
        self.assertEqual(a['rolling_mean_total_degree'][6], 4)  # steps 2..6
        for row in rows:
            if row['time_step'] >= 7:
                row.update({c: 10000. for c in ROLL_INPUTS})
        b = rolling_features(pa.Table.from_pylist(rows))
        for name in a:
            np.testing.assert_array_equal(a[name][:6], b[name][:6])
        self.assertEqual(a['rolling_mean_total_degree'][6], b['rolling_mean_total_degree'][6])

    def test_paired_bootstrap_identical_scores_zero_and_deterministic(self):
        y = np.tile([0, 1], 10)
        steps = np.repeat(np.arange(40, 50), 2)
        score = np.tile([.1, .8], 10)
        a = paired_intervals(y, steps, score, score, .5, .5, repeats=25)
        b = paired_intervals(y, steps, score, score, .5, .5, repeats=25)
        self.assertEqual(a, b)
        for item in a.values():
            self.assertEqual(item, {'lower_95': 0., 'upper_95': 0., 'valid_resamples': 25})

    def test_research_roundtrip_and_frozen_baseline(self):
        from unittest.mock import patch
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rows = test_experiments.ExperimentTrainingTests().records()
            for row in rows:
                row['in_degree'] = row['out_degree'] = row['total_degree'] = 1.
            pq.write_table(pa.Table.from_pylist(rows), root / 'features.parquet')
            pq.write_table(pa.table({'source': ['1-1'], 'target': ['1-2']}), root / 'edges.parquet')
            audit = build_research(root / 'features.parquet', root / 'edges.parquet', root / 'research.parquet')
            self.assertEqual(audit['cross_step_edges'], 0)
            self.assertEqual(audit['historical_label_feature_nonzero'], 0)
            with patch('mmd_fraud.training.comparison.CANDIDATES', ('hist_balanced',)):
                result = train_comparison(root / 'research.parquet', root / 'output', root / 'cache',
                    families={'transaction_only': RESEARCH_FAMILIES['transaction_only'],
                              'advanced_graph': RESEARCH_FAMILIES['advanced_graph']},
                    preserve_baseline=True, export_scores=True)
            self.assertEqual(result['families']['transaction_only']['candidate'], 'hist_unweighted')
            self.assertEqual(result['families']['advanced_graph']['candidate'], 'hist_balanced')
            data = np.load(root / 'output/transaction_only-private-scores.npz')
            self.assertEqual(len(data['y']), result['split_counts']['test']['rows'])
            from mmd_fraud.training.research import research_report
            report = research_report(root / 'output', audit)
            self.assertEqual(len(report['paired_step_bootstrap']), 1)
            self.assertTrue((root / 'output/research-results.png').is_file())
            text = (root / 'output/research-report.md').read_text()
            self.assertIn('historically known neighbor labels: 0', text)
            self.assertNotIn('1-1', text)  # no individual transaction IDs in public report
