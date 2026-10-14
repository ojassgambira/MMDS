"""Generated correctness fixtures only; these are not banking/AMLSim source data."""
import csv
import json
import tempfile
import unittest
from pathlib import Path
from pyspark.sql import functions as F
from mmd_fraud.adapters.elliptic import EllipticConfig
from mmd_fraud.adapters.banking import BankingColumns
from mmd_fraud.spark.preprocess import elliptic, banking
from mmd_fraud.spark.graph import statistics, historical
from mmd_fraud.spark.pipeline import session, run
from mmd_fraud.validation import ValidationError


class DistributedTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.root = Path(cls.temp.name)
        cls.profile = {'partitions': 2, 'driver_memory': '1g', 'max_rows': 100,
                       'max_input_bytes': 1000000, 'max_cutoffs': 3}
        cls.spark = session(cls.profile, cls.root / 'checkpoints')

    @classmethod
    def tearDownClass(cls):
        cls.spark.stop()
        cls.temp.cleanup()

    def setUp(self):
        self.input = self.root / self._testMethodName
        self.input.mkdir()
        self.write('elliptic_txs_features.csv', [['1', 1] + [1.0] * 165,
                                                 ['2', 1] + [2.0] * 165,
                                                 ['3', 2] + [3.0] * 165,
                                                 ['4', 3] + [4.0] * 165])
        self.write('elliptic_txs_classes.csv', [['txId', 'class'], ['4', 'unknown'],
                                               ['2', '2'], ['1', '1'], ['3', 'unknown']])
        self.write('elliptic_txs_edgelist.csv', [['txId1', 'txId2'], ['1', '2'],
                                                ['2', '3'], ['3', '4']])
        self.cfg = EllipticConfig(self.input, max_rows=100)

    def write(self, name, rows):
        with (self.input / name).open('w', newline='') as handle:
            csv.writer(handle).writerows(rows)

    def load(self, missing='reject'):
        return elliptic(self.spark, self.cfg, missing)

    def test_graph_and_temporal_future_invariance(self):
        nodes, edges, counts = self.load()
        self.assertEqual((counts['nodes'], counts['edges']), (4, 3))
        self.assertEqual(counts['labels'], {'1': 1, '2': 1, 'unknown': 2})
        static = {r.entity_id: r.asDict() for r in statistics(nodes, edges).collect()}
        self.assertEqual(static['2']['total_degree'], 2)
        self.assertEqual(static['1']['neighbor_mean_degree'], 2)
        past = {r.entity_id: r.asDict() for r in historical(nodes, edges, 2).collect()}
        self.assertEqual(set(past), {'1', '2'})
        self.assertEqual(past['2']['out_degree'], 0)
        self.assertEqual(past['1']['neighbor_mean_degree'], 1)
        self.assertEqual(past['1']['previous_step_out_degree'], 1)
        self.assertNotIn('source_features', past['1'])
        altered = edges.unionByName(self.spark.createDataFrame(
            [('4', '1', 3, 1, 3)], 'source string,target string,source_step int,'
                                  'target_step int,available_step int'))
        again = {r.entity_id: r.asDict() for r in historical(nodes, altered, 2).collect()}
        self.assertEqual(past, again)
        with self.assertRaises(ValueError):
            historical(nodes, edges, 0)
        self.assertEqual(historical(nodes, edges, 1).count(), 0)

    def test_duplicates_missing_and_schema(self):
        with (self.input / 'elliptic_txs_features.csv').open('a') as handle:
            csv.writer(handle).writerow(['1', 1] + [1.0] * 165)
        with (self.input / 'elliptic_txs_edgelist.csv').open('a') as handle:
            handle.write('1,2\n')
        nodes, edges, counts = self.load()
        self.assertEqual(counts['feature_duplicates_removed'], 1)
        self.assertEqual(counts['edge_duplicates_removed'], 1)
        self.assertEqual(nodes.count(), 4)
        self.assertEqual(edges.count(), 3)
        self.write('elliptic_txs_features.csv', [['1', 1] + [''] + [1.0] * 164,
                                                ['2', 1] + [2.0] * 165,
                                                ['3', 2] + [3.0] * 165,
                                                ['4', 3] + [4.0] * 165])
        with self.assertRaises(ValidationError):
            self.load()
        nodes, _, counts = self.load('zero')
        self.assertEqual(counts['missing_numeric_values'], 1)
        self.assertEqual(nodes.filter("entity_id='1'").first().source_features[0], 0)
        self.write('elliptic_txs_features.csv', [['1', 1] + ['oops'] * 165])
        with self.assertRaises(ValidationError):
            self.load('zero')

    def test_conflict_and_dangling(self):
        with (self.input / 'elliptic_txs_classes.csv').open('a') as handle:
            handle.write('1,2\n')
        with self.assertRaises(ValidationError):
            self.load()
        self.write('elliptic_txs_classes.csv', [['txId', 'class'], ['1', '1'], ['2', '2'],
                                               ['3', 'unknown'], ['4', 'unknown']])
        self.write('elliptic_txs_edgelist.csv', [['txId1', 'txId2'], ['1', 'missing']])
        with self.assertRaises(ValidationError):
            self.load()

    def test_width_time_and_labels(self):
        self.write('elliptic_txs_features.csv', [['1', 1, 0.1]])
        with self.assertRaises(Exception):  # Spark FAILFAST raises its JVM-backed parse error.
            self.load()
        self.write('elliptic_txs_features.csv', [['1', '1.5'] + [1.0] * 165])
        with self.assertRaises(ValidationError):
            self.load()
        self.write('elliptic_txs_features.csv', [['1', 1] + [1.0] * 165])
        self.write('elliptic_txs_classes.csv', [['txId', 'class'], ['1', 'bad']])
        with self.assertRaises(ValidationError):
            self.load()

    def test_banking_schema_mapping_preserves_events(self):
        accounts, events = self.input / 'accounts.csv', self.input / 'transactions.csv'
        accounts.write_text('ACCOUNT_ID,extra\na,x\nb,y\n')
        events.write_text('id,orig,dest,step,amount\nt1,a,b,0,10\nt2,a,b,1,20\nt1,a,b,0,10\n')
        columns = BankingColumns('ACCOUNT_ID', 'id', 'orig', 'dest', 'step', 'amount')
        nodes, transfers, counts = banking(self.spark, accounts, events, columns, 100, 1000000)
        self.assertEqual(counts['events'], 2)
        self.assertEqual(counts['event_duplicates_removed'], 1)
        self.assertEqual(transfers.filter(F.col('time_step') < 1).count(), 1)
        self.assertEqual(nodes.select('domain').first().domain, 'banking_account')
        with events.open('a') as handle:
            handle.write('t1,a,b,0,99\n')
        with self.assertRaises(ValidationError):
            banking(self.spark, accounts, events, columns, 100, 1000000)

    def test_amlsim_iso_timestamp_mapping(self):
        accounts, events = self.input / 'accounts.csv', self.input / 'events.csv'
        accounts.write_text('acct_id\na\nb\n')
        events.write_text('tran_id,orig_acct,bene_acct,base_amt,tran_timestamp\n'
                          't1,a,b,1,2017-01-02T00:00:00Z\n')
        columns = BankingColumns('acct_id', 'tran_id', 'orig_acct', 'bene_acct',
                                 'tran_timestamp', 'base_amt')
        _, transfers, _ = banking(self.spark, accounts, events, columns, 100, 1000000,
                                   'days_from_base_utc', "yyyy-MM-dd'T'HH:mm:ss'Z'",
                                   '2017-01-01T00:00:00+00:00')
        self.assertEqual(transfers.first().time_step, 1)
        with self.assertRaises(ValueError):
            banking(self.spark, accounts, events, columns, 100, 1000000,
                    timestamp_format="yyyy-MM-dd", base_date='2017-01-01')

    def test_pipeline_parquet_and_manifest(self):
        # Runner owns session shutdown. Recreate class session afterward.
        output = self.root / 'run'
        manifest = run({'directory': str(self.input)}, self.profile, output, cutoffs=(2,))
        self.__class__.spark = session(self.profile, self.root / 'checkpoints')
        self.assertEqual(manifest['status'], 'success')
        self.assertEqual(manifest['stages']['nodes']['rows'], 4)
        self.assertEqual(manifest['stages']['historical_features_2']['rows'], 2)
        persisted = self.spark.read.parquet(str(output / 'nodes'))
        self.assertEqual(persisted.count(), 4)
        self.assertTrue(list((output / 'nodes').glob('time_step=*')))
        self.assertEqual(json.loads((output / 'run.json').read_text())['status'], 'success')
        with self.assertRaises(FileExistsError):
            run({'directory': str(self.input)}, self.profile, output, cutoffs=(2,))
