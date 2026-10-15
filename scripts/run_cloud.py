"""Single cloud entry point with actionable diagnostics for every failure phase."""
import argparse
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import traceback

REPO = Path(__file__).resolve().parents[1]


def require_cloud():
    from mmd_fraud.runtime import is_colab
    if is_colab():
        os.environ['MMDS_COLAB_RUNTIME'] = '1'
        return
    if Path('/etc/codex/network-policy.json').is_file() or os.environ.get('GITHUB_ACTIONS') == 'true':
        return
    raise RuntimeError('Use a hosted cloud runtime; local device execution is refused')


def bootstrap(args):
    from mmd_fraud.bootstrap import prepare_dependencies
    args.phase = 'dependencies'
    with (args.workspace / 'bootstrap.log').open('a') as log:
        try:
            print('Checking/preparing compatible cloud dependencies…', flush=True)
            python = prepare_dependencies(REPO, args.workspace, log)
        except Exception:
            traceback.print_exc(file=log)
            raise
    args.phase = 'worker startup'
    command = [str(python), str(Path(__file__).resolve()), '--worker',
               '--workspace', str(args.workspace), '--config', str(args.config.resolve())]
    if args.storage:
        command.extend(['--storage', str(args.storage)])
    env = {**os.environ, 'SPARK_LOCAL_IP': '127.0.0.1', 'PYSPARK_PYTHON': str(python),
           'PYTHONPATH': str(REPO / 'src'),
           'OMP_NUM_THREADS': '2', 'OPENBLAS_NUM_THREADS': '2', 'PYTHONUNBUFFERED': '1'}
    with (args.workspace / 'worker.log').open('a') as log:
        process = subprocess.Popen(command, env=env, stderr=log, start_new_session=True)
        try:
            code = process.wait(timeout=3600)
            if code:
                raise RuntimeError(f'Worker exited with status {code}; see the recorded cause below')
        except BaseException:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
            raise


def worker(args, config):
    args.phase = 'worker'
    os.environ.update({'SPARK_LOCAL_IP': '127.0.0.1', 'PYSPARK_PYTHON': sys.executable})
    with (args.workspace / 'runtime.log').open('a') as log:
        original_stderr = os.dup(2)
        try:
            os.dup2(log.fileno(), 2)
            try:
                from mmd_fraud.automation import run_workflow
                result = run_workflow(REPO, args.workspace, config, args.storage)
            except Exception:
                # Print while fd 2 still points at runtime.log; never lose the root traceback.
                traceback.print_exc(file=log)
                log.flush()
                raise
        finally:
            os.dup2(original_stderr, 2)
            os.close(original_stderr)
    (args.workspace / 'latest-report.txt').write_text(str(result / 'report.md'))


def main(argv=None):
    sys.path.insert(0, str(REPO / 'src'))
    require_cloud()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--workspace', type=Path, required=True)
    parser.add_argument('--storage', type=Path)
    parser.add_argument('--config', type=Path, default=REPO / 'configs/cloud-pipeline.json')
    parser.add_argument('--worker', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    from mmd_fraud.data.acquire import outside_repo
    from mmd_fraud.cloud_config import validate_config, validate_paths
    from mmd_fraud.diagnostics import failure_details, record_failure
    args.workspace = outside_repo(args.workspace)
    args.workspace.mkdir(parents=True, exist_ok=True)
    if not args.worker:
        for name in ('bootstrap.log', 'runtime.log', 'worker.log'):
            (args.workspace / name).write_text('')
        for name in ('failure.json', 'active-run.txt', 'latest-report.txt'):
            (args.workspace / name).unlink(missing_ok=True)
    args.phase = 'preflight'
    try:
        if not (3, 11) <= sys.version_info[:2] <= (3, 13):
            raise RuntimeError('Supported Python range is 3.11–3.13; select a compatible hosted runtime')
        args.phase = 'configuration'
        config = validate_config(json.loads(args.config.read_text()))
        args.phase = 'storage'
        args.workspace, args.storage = validate_paths(args.workspace, args.storage)
        args.phase = 'java'
        java = subprocess.run(['java', '-version'], capture_output=True, text=True, check=True)
        if not re.search(r'version "(17|21)\.', java.stderr):
            raise RuntimeError('Spark requires Java 17 or 21 in this supported configuration')
        if args.worker:
            worker(args, config)
        else:
            bootstrap(args)
    except Exception as exc:
        # Preserve the worker's more specific stage/cause instead of overwriting with exit status.
        if not (args.workspace / 'failure.json').exists():
            record_failure(args.workspace, exc, args.phase)
        if not args.worker:
            print(failure_details(args.workspace, exc), file=sys.stderr, flush=True)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
