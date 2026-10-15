"""Free cloud-only bounded release validation; never publishes dataset artifacts."""
import argparse
import json
from pathlib import Path
import time

from mmd_fraud.automation import cloud_runtime, write_json
from mmd_fraud.data.acquire import (acquire, verify_acquisition, outside_repo,
                                   MAX_DOWNLOAD_BYTES, MAX_EXPANDED_BYTES)
from mmd_fraud.data.mirror import inspect_release
from mmd_fraud.data.sample import sample_elliptic
from mmd_fraud.diagnostics import redact


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--report', type=Path, required=True)
    parser.add_argument('--destination', type=Path)
    args = parser.parse_args()
    runtime = cloud_runtime()
    args.report = outside_repo(args.report)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    report = {'status': 'running', 'runtime': runtime, 'stages': {}}
    started = time.monotonic()
    try:
        report['active_stage'] = 'metadata'
        metadata = inspect_release()
        report['metadata'] = metadata
        report['stages']['metadata'] = {'seconds': metadata['seconds'], 'status': 'passed'}
        if (metadata['archive_bytes'] > MAX_DOWNLOAD_BYTES
                or metadata['expanded_bytes'] > MAX_EXPANDED_BYTES):
            raise ValueError('release metadata exceeds reviewed acquisition budgets; inspect release changes')
        if args.destination:
            if runtime != 'github_ci':
                raise RuntimeError('Real validation acquisition is restricted to GitHub-hosted CI')
            report['active_stage'] = 'acquisition'
            began = time.monotonic()
            acquire(args.destination)
            provenance = verify_acquisition(args.destination)
            report['stages']['acquisition'] = {'seconds': time.monotonic() - began,
                                               'status': 'passed',
                                               'bytes': provenance['expanded_bytes']}
            began = time.monotonic()
            report['active_stage'] = 'source_schema_relationships'
            audit = sample_elliptic(args.destination, args.destination.parent / 'validation-sample',
                                    per_step=200)
            if (audit['source_nodes'] != 203769 or audit['source_edges_raw'] != 234355
                    or audit['source_labels'] != {'1': 4545, '2': 42019, 'unknown': 157205}
                    or audit['source_steps'] != list(range(1, 50))):
                raise ValueError('original release counts/labels/time coverage mismatch')
            report['source_audit'] = {k: v for k, v in audit.items()
                                      if k.startswith('source_') or k.startswith('sample_')}
            report['stages']['source_schema_relationships'] = {
                'seconds': time.monotonic() - began, 'status': 'passed'}
            # Full CSV width, IDs, class alignment and edge endpoints audited above.
            # Real numeric values and sample Parquet round-trip are validated by Spark.
            from mmd_fraud.spark.pipeline import run
            profile = json.loads(Path('configs/profiles.json').read_text())['small']
            began = time.monotonic()
            report['active_stage'] = 'sample_spark'
            result = run({'directory': str(args.destination.parent / 'validation-sample'),
                          'dataset_kind': 'real_elliptic_induced_sample'}, profile,
                         args.destination.parent / 'validation-spark', cutoffs=())
            report['stages']['sample_spark'] = {'seconds': time.monotonic() - began,
                                              'status': result['status'],
                                              'validation': result['validation']}
        report['status'] = 'success'
        report['active_stage'] = 'complete'
    except Exception as exc:
        report['status'] = 'failed'
        report['error'] = redact(f'{type(exc).__name__}: {exc}')
        raise
    finally:
        report['seconds'] = time.monotonic() - started
        report['training'] = 'not run; acquisition/schema/Spark validation only'
        write_json(args.report, report)
        print(json.dumps(report, indent=2), flush=True)


if __name__ == '__main__':
    main()
