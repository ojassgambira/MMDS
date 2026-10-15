"""Cloud job boundaries, mocked release preflight and aggregate-only evidence."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

from mmd_fraud import cloud_job
from mmd_fraud.automation import inventory
from mmd_fraud.data import release_review as review
from mmd_fraud.training.baselines import evaluate, train
from test_automation import generated_features


def publisher():
    return {'ref': 'ellipticco/elliptic-data-set', 'currentVersionNumber': 1,
            'totalBytes': review.RELEASE_BYTES, 'licenseName': review.PUBLISHER_LICENSE}


def mirror():
    return {'files': [{'file': n, 'archive_bytes': c, 'expanded_bytes': e, 'crc32': crc}
                       for n, (c, e, crc) in review.REVIEWED.items()],
            'archive_bytes': 153218212, 'expanded_bytes': review.RELEASE_BYTES}


class CloudJobTests(unittest.TestCase):
    def test_publisher_terms_version_and_size_fail_before_mirror_or_download(self):
        for key, value in (('licenseName', 'changed'), ('currentVersionNumber', 2),
                           ('totalBytes', 2_000_000_000), ('ref', 'other')):
            with patch.object(review, 'publisher_metadata', return_value={**publisher(), key: value}), \
                    patch.object(review, 'inspect_release') as fetch:
                with self.assertRaisesRegex(ValueError, 'review required'):
                    review.review_release()
                fetch.assert_not_called()
        with patch.object(review, 'publisher_metadata', return_value=publisher()), \
                patch.object(review, 'inspect_release', return_value=mirror()):
            self.assertEqual(review.review_release()['status'], 'passed')
        changed = mirror()
        changed['files'][0]['crc32'] = '00000000'
        with patch.object(review, 'publisher_metadata', return_value=publisher()), \
                patch.object(review, 'inspect_release', return_value=changed):
            with self.assertRaisesRegex(ValueError, 'differs from reviewed'):
                review.review_release()

    def test_publisher_metadata_cannot_redirect_or_grow_unbounded(self):
        with self.assertRaises(ValueError):
            review.PublisherRedirects().redirect_request(None, None, 302, '', {}, 'https://elsewhere.test')
        with patch.object(review.urllib.request, 'build_opener') as opener:
            opener.return_value.open.return_value.__enter__.return_value.read.return_value = b'x' * 262145
            with self.assertRaisesRegex(ValueError, '256 KiB'):
                review.publisher_metadata()

    def test_requires_free_hosted_public_repository_no_colab_or_mac(self):
        for runtime, runner, public in (('codex_cloud', 'github-hosted', 'true'),
                                        ('colab', 'github-hosted', 'true'),
                                        ('github_ci', 'self-hosted', 'true'),
                                        ('github_ci', 'github-hosted', 'false')):
            with patch.object(cloud_job, 'cloud_runtime', return_value=runtime), patch.dict(
                    os.environ, {'RUNNER_ENVIRONMENT': runner, 'MMDS_PUBLIC_REPOSITORY': public}):
                with self.assertRaises(RuntimeError):
                    cloud_job.require_free_hosted_ci()
        with patch.object(cloud_job, 'cloud_runtime', return_value='github_ci'), patch.dict(
                os.environ, {'RUNNER_ENVIRONMENT': 'github-hosted', 'MMDS_PUBLIC_REPOSITORY': 'true'}):
            cloud_job.require_free_hosted_ci()

    def test_metrics_fpr_and_invalid_probabilities(self):
        y = np.array([0, 0, 1, 1])
        self.assertEqual(evaluate(y, np.array([.1, .6, .4, .9]))['false_positive_rate'], .5)
        self.assertEqual(evaluate(y, np.zeros(4))['false_positive_rate'], 0)
        self.assertEqual(evaluate(y, np.ones(4))['false_positive_rate'], 1)
        for score in (np.array([np.nan, .1, .2, .3]), np.array([0, 1, 2, 1]), np.ones(3)):
            with self.assertRaises(ValueError):
                evaluate(y, score)
        with self.assertRaises(ValueError):
            evaluate(np.zeros(4), np.zeros(4))

    def test_training_is_invariant_to_parquet_row_order(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            rows = generated_features()
            pq.write_table(pa.Table.from_pylist(rows), root / 'one.parquet')
            pq.write_table(pa.Table.from_pylist(list(reversed(rows))), root / 'two.parquet')
            one = train(root / 'one.parquet', root / 'one')
            two = train(root / 'two.parquet', root / 'two')
            self.assertEqual(one['models'], two['models'])
            self.assertEqual(one['selected_model'], two['selected_model'])
            self.assertEqual(one['model_configuration'], two['model_configuration'])

    def test_resource_limits_and_termination_are_bounded(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(cloud_job.time, 'monotonic', return_value=1801):
                with self.assertRaises(TimeoutError):
                    cloud_job.resource_check(root, 0)
            with patch.object(cloud_job.shutil, 'disk_usage') as disk:
                disk.return_value.free = 1
                with self.assertRaisesRegex(ValueError, 'disk reserve'):
                    cloud_job.resource_check(root, cloud_job.time.monotonic())
            (root / 'large').touch()
            with patch.object(Path, 'rglob', return_value=[root / 'large']), \
                    patch.object(Path, 'stat') as stat:
                stat.return_value.st_size = cloud_job.MAX_WORKSPACE_BYTES + 1
                with patch.object(Path, 'is_file', return_value=True):
                    with self.assertRaisesRegex(ValueError, '8 GB'):
                        cloud_job.resource_check(root, cloud_job.time.monotonic())
        with patch.object(cloud_job.subprocess, 'Popen') as launch, \
                patch.object(cloud_job, 'resource_check', side_effect=TimeoutError('limit')), \
                patch.object(cloud_job, 'stop') as stop, tempfile.TemporaryDirectory() as temp:
            launch.return_value.poll.return_value = None
            with self.assertRaises(TimeoutError):
                cloud_job.run_worker(Path(temp), Path(temp), Path(temp) / 'config.json')
            stop.assert_called_once_with(launch.return_value)

    def test_failed_preflight_is_reported_without_starting_worker_or_leaking_logs(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            with patch.object(cloud_job, 'require_free_hosted_ci'), patch.object(
                    cloud_job, 'review_release', side_effect=ValueError('publisher license/version/size changed token=SECRET')), \
                    patch.object(cloud_job, 'run_worker') as worker, patch.object(cloud_job.shutil, 'disk_usage') as disk:
                disk.return_value.free = 10_000_000_000
                code = cloud_job.main(['--workspace', str(root / 'private'), '--evidence', str(root / 'public')])
            self.assertEqual(code, 1)
            worker.assert_not_called()
            text = '\n'.join(p.read_text() for p in (root / 'public').iterdir())
            self.assertNotIn('SECRET', text)
            self.assertIn('publisher terms/version/size changed', text)
            self.assertFalse(json.loads((root / 'public/training-summary.json').read_text())['real_training_verified'])

    def test_export_only_verified_aggregates_and_manifest_no_models_records_or_full_logs(self):
        # Synthetic metadata boundary test, NOT a real-data execution.
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run = root / 'private/runs/key'
            run.mkdir(parents=True)
            (root / 'private/active-run.txt').write_text(str(run))
            state = {'status': 'success', 'dataset_kind': 'real_elliptic_induced_sample',
                     'config': {'source': 'pyg', 'data_mode': 'sample'}, 'stages': {}}
            for stage in ('checks', 'preprocess', 'causal', 'models'):
                path = run / stage
                path.mkdir()
                (path / 'PRIVATE.parquet').write_text('PRIVATE RECORDS')
                if stage == 'preprocess':
                    (path / 'run.json').write_text(json.dumps({'validation': {'nodes': 3}}))
                if stage == 'models':
                    (path / 'secret.joblib').write_text('PRIVATE MODEL')
                    scores = evaluate(np.array([0, 1]), np.array([.1, .8]))
                    (path / 'metrics.json').write_text(json.dumps({
                        'models': {'test_model': {'test': scores}}, 'selected_model': 'test_model',
                        'unknown_excluded': 1, 'split_counts': {'test': {'rows': 2, 'illicit': 1}}}))
                state['stages'][stage] = {'hashes': inventory(path), 'seconds': .1}
            (run / 'execution.json').write_text(json.dumps(state))
            (root / 'private/runtime.log').write_text('RAW,SOURCE,RECORD token=SECRET')
            out = root / 'public'
            summary = cloud_job.publish_evidence(root / 'private', out)
            self.assertTrue(summary['real_training_verified'])
            text = '\n'.join(p.read_text() for p in out.iterdir())
            self.assertNotIn('PRIVATE RECORDS', text)
            self.assertNotIn('PRIVATE MODEL', text)
            self.assertNotIn('RAW,SOURCE', text)
            self.assertNotIn('SECRET', text)
            manifest = json.loads((out / 'training-evidence-manifest.json').read_text())['sha256']
            self.assertEqual(set(manifest), {'training-summary.json', 'training-report.md'})
            cloud_job.publish_evidence(root / 'private', out)
            self.assertEqual(json.loads((out / 'training-evidence-manifest.json').read_text())['sha256'], manifest)
            (run / 'models/secret.joblib').write_text('tampered')
            self.assertFalse(cloud_job.publish_evidence(root / 'private', out)['real_training_verified'])
            (out / 'data.csv').write_text('private')
            with self.assertRaisesRegex(ValueError, 'unexpected files'):
                cloud_job.publish_evidence(root / 'private', out)

    def test_killed_worker_reports_last_persisted_stage_and_safe_cause(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            run = root / 'runs/key'
            run.mkdir(parents=True)
            (root / 'active-run.txt').write_text(str(run))
            (run / 'execution.json').write_text('{"active_stage":"causal"}')
            (root / 'runtime.log').write_text('java.lang.OutOfMemoryError RAW PRIVATE ROW\n')
            result = cloud_job.diagnostics(root, subprocess.CalledProcessError(-9, ['worker']))
            self.assertEqual(result['stage'], 'causal')
            self.assertIn('Java heap exhausted', str(result['causes']))
            self.assertNotIn('RAW PRIVATE ROW', str(result))
