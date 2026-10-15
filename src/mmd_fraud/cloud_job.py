"""Bounded GitHub-hosted real training; public evidence contains aggregates only."""
import argparse
import json
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
import time

from .automation import cloud_runtime, verified, write_json
from .data.acquire import outside_repo, sha256
from .data.release_review import review_release
from .diagnostics import tail

MAX_SECONDS = 1800
MAX_WORKSPACE_BYTES = 8_000_000_000
MIN_FREE_BYTES = 2_000_000_000


def require_free_hosted_ci():
    if (cloud_runtime() != 'github_ci' or os.environ.get('RUNNER_ENVIRONMENT') != 'github-hosted'
            or os.environ.get('MMDS_PUBLIC_REPOSITORY') != 'true'):
        raise RuntimeError('Real training job requires a public repository and standard GitHub-hosted Linux')
    if sys.platform != 'linux':
        raise RuntimeError('Only free standard Linux runners are supported')


def stop(process):
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()


def resource_check(workspace: Path, started: float):
    if time.monotonic() - started > MAX_SECONDS:
        raise TimeoutError(f'worker exceeded {MAX_SECONDS}-second wall-clock limit')
    size = 0
    for path in workspace.rglob('*'):
        try:
            if path.is_file():
                size += path.stat().st_size
        except FileNotFoundError:
            pass  # Atomic staging/cleanup may remove a file between enumeration and stat.
    if size > MAX_WORKSPACE_BYTES:
        raise ValueError('workspace exceeds 8 GB ceiling')
    if shutil.disk_usage(workspace).free < MIN_FREE_BYTES:
        raise ValueError('less than 2 GB disk reserve remains')


def run_worker(repo: Path, workspace: Path, config: Path):
    env = {**os.environ, 'PYTHONUNBUFFERED': '1', 'PYTHONPATH': str(repo / 'src'),
           'PYSPARK_PYTHON': sys.executable, 'SPARK_LOCAL_IP': '127.0.0.1',
           'OMP_NUM_THREADS': '2', 'OPENBLAS_NUM_THREADS': '2',
           'MMDS_TEST_REPORT_DIRECTORY': ''}
    command = [sys.executable, str(repo / 'scripts/run_cloud.py'), '--worker',
               '--workspace', str(workspace), '--config', str(config)]
    # Complete logs stay private. Public diagnostics below export classified causes/frames,
    # never arbitrary Spark CSV payloads, source records or model serialization.
    with (workspace / 'job.log').open('a') as log:
        process = subprocess.Popen(command, cwd=repo, env=env, stdout=log, stderr=log,
                                   start_new_session=True)
        began = time.monotonic()
        try:
            while process.poll() is None:
                resource_check(workspace, began)
                time.sleep(2)
            if process.returncode:
                raise subprocess.CalledProcessError(process.returncode, command)
        finally:
            stop(process)


def diagnostics(workspace: Path, error: Exception | None) -> dict:
    record = {}
    try:
        record = json.loads((workspace / 'failure.json').read_text())
    except (OSError, ValueError):
        pass
    stage = record.get('stage', 'cloud job preflight/worker')
    text = str(error or '') + '\n' + str(record.get('error', ''))
    logs = [workspace / n for n in ('job.log', 'bootstrap.log', 'runtime.log', 'worker.log')]
    try:
        current = Path((workspace / 'active-run.txt').read_text()).resolve()
        if current.is_relative_to(workspace.resolve() / 'runs'):
            logs.append(current / 'execution.log')
            if not record:
                stage = json.loads((current / 'execution.json').read_text()).get('active_stage', stage)
    except (OSError, ValueError):
        pass
    text += '\n' + '\n'.join(tail(p) for p in logs)
    classifications = {
        'OutOfMemoryError': 'Java heap exhausted; no successful stage is claimed',
        'No space left on device': 'disk exhausted',
        'disk reserve': 'disk reserve exhausted',
        'workspace exceeds': 'workspace byte ceiling exceeded',
        'wall-clock limit': 'worker wall-clock budget exceeded',
        'HTTP Error 401': 'source access authorization denied; no retry',
        'HTTP Error 403': 'source access authorization denied; no retry',
        'Connection refused': 'network transport refused; no retry',
        'no metrics fabricated': 'a chronological split lacks both known classes',
        'publisher license/version/size changed': 'publisher terms/version/size changed; review required',
        'mirror release differs': 'mirror differs from reviewed release; review required',
        'corrupt': 'checkpoint integrity validation failed',
    }
    causes = [safe for marker, safe in classifications.items() if marker in text]
    root = str(record.get('error', type(error).__name__ if error else 'none')).split(':', 1)[0]
    if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9.]*', root):
        root = 'unclassified exception'
    frames = re.findall(r'File "[^"\n]*[/\\]([A-Za-z_0-9]+\.py)", line (\d+), in ([A-Za-z_0-9<>]+)', text)
    return {'stage': stage, 'root_error_type': root, 'causes': causes,
            'trace_frames': [f'{f}:{n} in {fn}' for f, n, fn in frames[-12:]],
            'log_policy': 'Full logs private to runner; only classified causes/frames are public'}


def publish_evidence(workspace: Path, evidence: Path, *, review=None, error=None):
    evidence.mkdir(parents=True, exist_ok=True)
    allowed = {'training-summary.json', 'training-report.md', 'training-evidence-manifest.json'}
    if any(p.is_symlink() or p.name not in allowed for p in evidence.iterdir()):
        raise ValueError('evidence directory contains unexpected files; refusing publication')
    summary = {'status': 'failed', 'runtime': 'github_ci', 'real_training_verified': False,
               'limits': {'worker_seconds': MAX_SECONDS, 'workspace_bytes': MAX_WORKSPACE_BYTES,
                          'disk_reserve_bytes': MIN_FREE_BYTES, 'cpu_workers': 2},
               'release_review': review, 'diagnostics': diagnostics(workspace, error)}
    try:
        directory = Path((workspace / 'active-run.txt').read_text()).resolve()
        if not directory.is_relative_to(workspace.resolve() / 'runs'):
            raise ValueError('run pointer escapes workspace')
        state = json.loads((directory / 'execution.json').read_text())
        if (state['config']['source'] != 'pyg' or state['dataset_kind'] not in
                {'original_elliptic_release', 'real_elliptic_induced_sample'}):
            raise ValueError('public real-training evidence requires the authorized public source')
        summary.update({k: state[k] for k in ('dataset_kind', 'git_commit', 'git_dirty', 'python',
                                             'dependencies', 'config', 'acquisition') if k in state})
        manifest = {}
        for stage, info in state['stages'].items():
            if not verified(directory / stage, info['hashes']):
                raise ValueError(f'corrupt {stage} checkpoint')
            manifest[stage] = {'seconds': info['seconds'], 'artifacts': [
                {'path': name, 'sha256': digest, 'bytes': (directory / stage / name).stat().st_size}
                for name, digest in info['hashes'].items()]}
        summary['stage_manifests'] = manifest
        summary['source_files'] = [{k: r[k] for k in ('file', 'bytes', 'sha256', 'archive_sha256')}
                                   for r in state.get('provenance', {}).get('files', [])]
        if (directory / 'preprocess/run.json').exists():
            summary['validation'] = json.loads((directory / 'preprocess/run.json').read_text())['validation']
        if state['status'] == 'success' and error is None:
            if not {'checks', 'preprocess', 'causal', 'models'} <= set(manifest):
                raise ValueError('success lacks required verified stages')
            summary['metrics'] = json.loads((directory / 'models/metrics.json').read_text())
            m = summary['metrics']
            if (m['unknown_excluded'] + sum(c['rows'] for c in m['split_counts'].values())
                    != summary['validation']['nodes']):
                raise ValueError('training row counts differ from validated graph')
            if state['config'].get('experiments'):
                if not {'experiment_features', 'comparison'} <= set(manifest):
                    raise ValueError('comparison lacks verified stages')
                comparison = json.loads((directory / 'comparison/comparison.json').read_text())
                if (comparison['split_counts'] != m['split_counts']
                        or comparison['unknown_excluded'] != m['unknown_excluded']):
                    raise ValueError('comparison population differs from baseline')
                summary['comparison'] = comparison
            summary['status'] = 'success'
            summary['real_training_verified'] = True
            summary['diagnostics'] = None
    except (OSError, ValueError, KeyError) as exc:
        summary['status'] = 'failed'
        summary['real_training_verified'] = False
        summary.pop('metrics', None)
        summary.pop('comparison', None)
        summary['evidence_error_type'] = type(exc).__name__
    write_json(evidence / 'training-summary.json', summary)
    lines = ['# MMDS unattended cloud training', '', f"Status: **{summary['status']}**",
             f"Dataset: `{summary.get('dataset_kind', 'not acquired/validated')}`", '',
             'This is GitHub-hosted execution, not Colab or Drive verification.',
             'Predictors: six graph features at the completed source step; anonymous source',
             'features and labels excluded. Unknown labels excluded from supervised rows.',
             'Train 1–34; validation 35–39; test 40–49; threshold 0.5.',
             'Selection uses validation AP only; same-step information is explicitly retrospective.', '']
    if summary.get('metrics'):
        m = summary['metrics']
        lines += [f"Selected on validation AP: **{m['selected_model']}**", '',
                  '| Model | Period | Precision | Recall | F1 | PR-AUC (AP) | FPR | Confusion matrix |',
                  '| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |']
        for name, periods in m['models'].items():
            for period, scores in periods.items():
                lines.append(f"| {name} | {period} | " + ' | '.join(
                    f"{scores[k]:.6f}" for k in ('precision', 'recall', 'f1',
                    'pr_auc_average_precision', 'false_positive_rate')) +
                    f" | {scores['confusion_matrix']} |")
        lines += ['', 'Confusion matrix: rows=true, columns=predicted; [licit=0, illicit=1].',
                  'PR-AUC is average precision, not trapezoidal integration.', '',
                  'Split counts:', '```json', json.dumps(m['split_counts'], indent=2), '```']
    else:
        lines += ['No successful training/metrics claimed.', '```json',
                  json.dumps(summary['diagnostics'], indent=2), '```']
    if summary.get('comparison'):
        comparison = summary['comparison']
        lines += ['', '## Predeclared feature comparison', '',
                  '93 publisher-local attributes only; 72 anonymous neighborhood aggregates excluded.',
                  'Local attribute live availability is a publisher assumption, not independently verified.',
                  'Temporal baselines use strictly previous-step population statistics, without labels.',
                  'Twenty fixed candidates; selection uses validation AP only. Each family threshold',
                  'maximizes validation F1 under a 5% validation FPR cap; test FPR may exceed it.',
                  f"Selected family: **{comparison['selected_family']}**", '',
                  '| Family | Candidate | Val AP | Test AP | F1 | Recall | FPR | Threshold |',
                  '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
        for family, item in comparison['families'].items():
            m = item['test']
            lines.append(f"| {family} | {item['candidate']} | "
                         f"{item['validation']['pr_auc_average_precision']:.6f} | " +
                         ' | '.join(f"{m[k]:.6f}" for k in
                         ('pr_auc_average_precision', 'f1', 'recall', 'false_positive_rate')) +
                         f" | {item['threshold']:.6f} |")
        lines += ['', 'Fixed-0.5 comparison metrics, validation trials, source hashes and all feature',
                  'names are retained in training-summary.json. Test metrics never select a family.']
    lines += ['', '## Stage seconds', '']
    for name, item in summary.get('stage_manifests', {}).items():
        lines.append(f"- {name}: {item['seconds']:.3f}")
    lines += ['', 'Private data/models/logs are deleted when the job ends. Public evidence contains',
              'aggregate metrics and artifact hashes/sizes, not raw or derived transaction records.',
              'Ephemeral checkpoints resume within a retained workspace, not across fresh hosted jobs.']
    (evidence / 'training-report.md').write_text('\n'.join(lines) + '\n')
    public_files = {p.name: sha256(p)
                    for p in evidence.iterdir() if p.name != 'training-evidence-manifest.json'}
    write_json(evidence / 'training-evidence-manifest.json', {'sha256': public_files})
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--data-mode', choices=['full', 'sample'], default='full')
    args = parser.parse_args(argv)
    require_free_hosted_ci()
    workspace, evidence = outside_repo(args.workspace), outside_repo(args.evidence)
    if workspace == evidence or workspace in evidence.parents or evidence in workspace.parents:
        raise ValueError('public evidence must be separate from private workspace')
    workspace.mkdir(parents=True, exist_ok=True)
    # Stale failure pointers never label a new preflight as an earlier run's failure.
    for name in ('failure.json', 'active-run.txt', 'latest-report.txt'):
        (workspace / name).unlink(missing_ok=True)
    review, error = None, None
    try:
        if shutil.disk_usage(workspace).free < 6_000_000_000:
            raise ValueError('at least 6 GB free runtime disk required before training')
        review = review_release()
        config = {'source': 'pyg', 'data_mode': args.data_mode, 'experiments': True}
        write_json(workspace / 'job-config.json', config)
        run_worker(Path(__file__).resolve().parents[2], workspace, workspace / 'job-config.json')
    except Exception as exc:
        error = exc
    summary = publish_evidence(workspace, evidence, review=review, error=error)
    print((evidence / 'training-report.md').read_text(), flush=True)
    return 0 if summary['real_training_verified'] else 1
