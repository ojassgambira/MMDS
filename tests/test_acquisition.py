import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch
from mmd_fraud.data.acquire import FILES, SOURCE, acquire, extract_one, outside_repo, sha256, MirrorRedirects


class Response(io.BytesIO):
    def __init__(self, payload, url):
        super().__init__(payload)
        self.url = url
        self.headers = {}


class AcquisitionTests(unittest.TestCase):
    def test_atomic_acquisition_and_hashes(self):
        def response(request):
            filename = request.full_url.rsplit('/', 1)[1][:-4]
            buffer = io.BytesIO()
            with zipfile.ZipFile(buffer, 'w') as archive:
                archive.writestr(filename, 'fixture-only\n')
            return Response(buffer.getvalue(), request.full_url)
        with tempfile.TemporaryDirectory() as temp, patch(
                'mmd_fraud.data.acquire.open_remote', side_effect=response):
            destination = Path(temp) / 'raw'
            manifest = acquire(destination, 10000, 10000)
            self.assertEqual(len(manifest['files']), 3)
            for filename in FILES:
                record = next(r for r in manifest['files'] if r['file'] == filename)
                self.assertEqual(record['sha256'], sha256(destination / filename))
            self.assertEqual(json.loads((destination / 'acquisition.json').read_text())['source'], SOURCE)
            with self.assertRaises(FileExistsError):
                acquire(destination)

    def test_failed_download_never_publishes_dataset(self):
        with tempfile.TemporaryDirectory() as temp, patch(
                'mmd_fraud.data.acquire.open_remote', side_effect=OSError('network unavailable')):
            destination = Path(temp) / 'raw'
            with self.assertRaises(OSError):
                acquire(destination)
            self.assertFalse(destination.exists())
            self.assertEqual(list(Path(temp).iterdir()), [])

    def test_zip_traversal_and_expansion_limits(self):
        with tempfile.TemporaryDirectory() as temp:
            archive, target = Path(temp) / 'archive.zip', Path(temp) / 'out'
            for filename, limit in (('../evil.csv', 100), ('x.csv', 1)):
                with zipfile.ZipFile(archive, 'w') as zipped:
                    zipped.writestr(filename, '123456')
                with self.assertRaises(ValueError):
                    extract_one(archive, target, 'x.csv', limit)
                self.assertFalse(target.exists())

    def test_checkout_guard(self):
        with self.assertRaises(ValueError):
            outside_repo(Path(__file__).resolve().parent / 'data')

    def test_redirect_rejected_before_contact(self):
        with self.assertRaises(ValueError):
            MirrorRedirects().redirect_request(None, None, 302, 'redirect', {},
                                               'https://unapproved.example/data.zip')
