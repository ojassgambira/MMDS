"""Only aggregate evidence may leave free CI runners."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


class EvidenceTests(unittest.TestCase):
    def test_artifacts_are_allowlisted_and_redacted(self):
        repo = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            inputs = root / 'inputs'
            inputs.mkdir()
            for name in ('private.csv', 'data.parquet', 'model.joblib', 'kaggle.json'):
                (inputs / name).write_text('private-never-publish')
            (inputs / 'real-release.json').write_text('{"status": "failed"}')
            (inputs / 'pytest.log').write_text('KAGGLE_KEY=secret-value\nhttps://user:password@example.test')
            (inputs / 'generated-report.md').write_text('Generated fixture report')
            summary = root / 'summary.md'
            subprocess.run([sys.executable, str(repo / 'scripts/prepare_ci_evidence.py'),
                            '--directory', str(inputs), '--output', str(root / 'public')],
                           check=True, env={**os.environ, 'PYTHONPATH': str(repo / 'src'),
                                            'GITHUB_STEP_SUMMARY': str(summary)})
            self.assertEqual(sorted(p.name for p in (root / 'public').iterdir()),
                             ['generated-report.md', 'pytest.log', 'real-release.json'])
            published = '\n'.join(p.read_text() for p in (root / 'public').iterdir())
            for secret in ('secret-value', 'user:password', 'private-never-publish'):
                self.assertNotIn(secret, published)
            self.assertIn('[REDACTED]', published)
            self.assertIn('"failed"', summary.read_text())
