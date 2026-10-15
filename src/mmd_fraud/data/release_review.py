"""Fail closed if public publisher terms/version or measured release metadata change."""
import json
import time
import urllib.request

from .acquire import LICENSE, MAX_DOWNLOAD_BYTES, MAX_EXPANDED_BYTES
from .mirror import inspect_release

PUBLISHER_API = 'https://www.kaggle.com/api/v1/datasets/view/ellipticco/elliptic-data-set'
PUBLISHER_LICENSE = 'Attribution-NonCommercial-NoDerivatives 4.0 International (CC BY-NC-ND 4.0)'
RELEASE_BYTES = 697459499
# Measured original ZIP central directories on 2026-10-15, rechecked in PR #8 CI.
REVIEWED = {'elliptic_txs_features.csv': (150601883, 689683771, 'f62b0d9d'),
            'elliptic_txs_classes.csv': (925698, 3305144, 'a0d598c5'),
            'elliptic_txs_edgelist.csv': (1690631, 4470584, '68acfa24')}


class PublisherRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('publisher metadata redirect requires review; no new host contacted')


def publisher_metadata():
    request = urllib.request.Request(PUBLISHER_API, headers={'Accept': 'application/json'})
    with urllib.request.build_opener(PublisherRedirects()).open(request, timeout=30) as response:
        data = response.read(262145)
        if len(data) > 262144:
            raise ValueError('publisher metadata exceeds 256 KiB budget')
        return json.loads(data)


def review_release() -> dict:
    publisher = publisher_metadata()
    if (publisher.get('ref') != 'ellipticco/elliptic-data-set'
            or publisher.get('currentVersionNumber') != 1
            or publisher.get('totalBytes') != RELEASE_BYTES
            or publisher.get('licenseName') != PUBLISHER_LICENSE):
        raise ValueError('publisher license/version/size changed; review required before acquisition')
    mirror = inspect_release()
    actual = {r['file']: (r['archive_bytes'], r['expanded_bytes'], r['crc32'])
              for r in mirror['files']}
    if (actual != REVIEWED or len(mirror['files']) != len(REVIEWED)
            or mirror['archive_bytes'] > MAX_DOWNLOAD_BYTES
            or mirror['expanded_bytes'] != RELEASE_BYTES
            or mirror['expanded_bytes'] > MAX_EXPANDED_BYTES):
        raise ValueError('mirror release differs from reviewed original release; acquisition stopped')
    return {'status': 'passed', 'checked_utc': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'publisher_api': PUBLISHER_API, 'publisher_version': 1, 'license': LICENSE,
            'use': 'authorized noncommercial university research; do not redistribute datasets/models',
            'mirror': mirror, 'publisher_last_updated': publisher.get('lastUpdated')}
