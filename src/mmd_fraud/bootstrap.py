"""Idempotent dependency preparation without ensurepip in the hosted Colab runtime."""
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import venv

from .runtime import is_colab

PROBE = r'''
import importlib.metadata as m
import json
from pathlib import Path
import sys
from urllib.parse import unquote, urlparse
request = json.loads(sys.argv[1])
missing = {}
for name, expected in request['pins'].items():
    try:
        actual = m.version(name)
    except m.PackageNotFoundError:
        actual = None
    if actual != expected:
        missing[name] = {'expected': expected, 'actual': actual}
editable = False
try:
    for distribution in m.distributions(name='mmd-fraud'):
        direct = json.loads(distribution.read_text('direct_url.json') or '{}')
        if (direct.get('dir_info', {}).get('editable') is True
                and Path(unquote(urlparse(direct.get('url', '')).path)).resolve()
                == Path(request['repo']).resolve()):
            editable = True
except (m.PackageNotFoundError, ValueError, TypeError):
    pass
print(json.dumps({'missing': missing, 'editable': editable}))
'''

VERIFY = r'''
import importlib
import importlib.metadata as m
import json
import sys
from packaging.requirements import Requirement
pins = json.loads(sys.argv[1])
for name, expected in pins.items():
    assert m.version(name) == expected, f'{name}: expected {expected}, got {m.version(name)}'
    for text in m.requires(name) or []:
        requirement = Requirement(text)
        if requirement.marker and not requirement.marker.evaluate({'extra': ''}):
            continue
        actual = m.version(requirement.name)
        assert actual in requirement.specifier, f'{name} requires {requirement}; installed {actual}'
for module in ('pyspark', 'numpy', 'scipy', 'sklearn', 'pyarrow', 'mmd_fraud'):
    loaded = importlib.import_module(module)
    print(module, getattr(loaded, '__version__', 'import OK'))
print('MMDS pinned dependency closure and fresh-process imports verified')
'''


def locked_versions(path: Path) -> dict:
    pins = {}
    for raw in path.read_text().splitlines():
        line = raw.split('#', 1)[0].strip()
        if not line:
            continue
        if line.startswith('-r '):
            pins.update(locked_versions(path.parent / line[3:].strip()))
        elif line.count('==') == 1:
            name, version = line.split('==')
            if name in pins and pins[name] != version:
                raise ValueError(f'conflicting dependency pin: {name}')
            pins[name] = version
        else:
            raise ValueError(f'unsupported unpinned requirement: {line}')
    return pins


def logged(command, log, **kwargs):
    log.write(json.dumps(command) + '\n')
    log.flush()
    return subprocess.run(command, stderr=log, check=True, timeout=900, **kwargs)


def select_python(workspace: Path, log) -> Path:
    colab = is_colab()
    prefix = 'colab-venv' if colab else 'venv'
    environment = workspace / f'{prefix}-{sys.version_info.major}.{sys.version_info.minor}'
    if colab:
        log.write('Colab isolated mode: runtime pip targets a venv created WITHOUT pip/ensurepip.\n')
        log.write('Global Colab packages and prior workspace venvs are retained.\n')
    python = environment / 'bin/python'
    if environment.is_symlink():
        raise ValueError(f'refusing to rebuild a symlinked virtual environment: {environment}')
    if environment.exists():
        try:
            logged([str(python), '-c',
                    ('import sys; ' if colab else 'import sys, pip; ') +
                    'assert sys.prefix != sys.base_prefix; '
                    f'assert sys.version_info[:2] == {sys.version_info[:2]!r}'], log, stdout=log)
            log.write('Existing isolated environment is healthy.\n')
            return python
        except (OSError, subprocess.SubprocessError) as exc:
            log.write(f'Rebuilding incomplete isolated environment: {type(exc).__name__}: {exc}\n')
            shutil.rmtree(environment)
    if not colab and importlib.util.find_spec('ensurepip') is None:
        raise RuntimeError('This non-Colab cloud Python lacks ensurepip; use a Python installation '
                           'with venv/ensurepip support. Colab uses runtime pip targeting a pip-free venv.')
    venv.create(environment, with_pip=not colab)
    return python


def prepare_dependencies(repo: Path, workspace: Path, log) -> Path:
    python = select_python(workspace, log)
    log.flush()
    # pip --python can manage an empty venv: no target pip or ensurepip is required.
    pip = ([sys.executable, '-m', 'pip', '--python', str(python)] if is_colab()
           else [str(python), '-m', 'pip'])
    if is_colab():
        log.write('Pre-existing global pip check (not MMDS consistency):\n')
        global_check = subprocess.run([sys.executable, '-m', 'pip', 'check'],
                                      stdout=log, stderr=log, timeout=60)
        if global_check.returncode:
            print('Colab global pip check reports existing conflicts (bootstrap.log). '
                  'MMDS uses a separate environment; global packages are preserved.', flush=True)
        log.write(f'Global pip check exit status: {global_check.returncode}; '
                  'global packages are never modified.\n')
    logged(pip + ['--version'], log, stdout=log)
    pins = locked_versions(repo / 'requirements-cloud.lock')
    request = json.dumps({'pins': pins, 'repo': str(repo)})
    result = logged([str(python), '-c', PROBE, request], log, stdout=subprocess.PIPE, text=True)
    installed = json.loads(result.stdout)
    if installed['missing']:
        log.write('Installing only missing/mismatched pins: ' + json.dumps(installed['missing']) + '\n')
        logged(pip + ['install', '--retries', '0', '--timeout', '30',
                '-r', str(repo / 'requirements-cloud.lock')], log, stdout=log)
    else:
        log.write('All dependency pins already match; skipping pip install.\n')
    stamp_path = workspace / 'dependencies.json'
    project_hash = hashlib.sha256((repo / 'pyproject.toml').read_bytes()).hexdigest()
    expected = {'python': str(python), 'repo': str(repo.resolve()), 'pyproject_sha256': project_hash}
    try:
        stamp = json.loads(stamp_path.read_text())
    except (OSError, ValueError):
        stamp = None
    if not installed['editable'] or stamp != expected:
        logged(pip + ['install', '--no-build-isolation', '--no-deps',
                '-e', str(repo)], log, stdout=log)
    else:
        log.write('Editable project metadata is current; skipping project reinstall.\n')
    # A new child interpreter avoids stale imports cached by the notebook kernel.
    logged([str(python), '-c', VERIFY, json.dumps(pins)], log, stdout=log)
    logged(pip + ['check'], log, stdout=log)
    log.write('Isolated environment: full pip check and fresh-process MMDS imports passed.\n')
    temporary = stamp_path.with_suffix('.tmp')
    temporary.write_text(json.dumps(expected, indent=2) + '\n')
    temporary.replace(stamp_path)
    return python
