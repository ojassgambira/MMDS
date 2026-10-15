"""Colab bootstrap regressions; no hosted Colab or external dataset is used."""
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from mmd_fraud import bootstrap
from mmd_fraud.runtime import is_colab

REPO = Path(__file__).resolve().parents[1]


class BootstrapTests(unittest.TestCase):
    def test_worker_and_spark_use_the_selected_interpreter(self):
        from test_diagnostics import entry
        with tempfile.TemporaryDirectory() as temp:
            args = SimpleNamespace(workspace=Path(temp), storage=None,
                                   config=REPO / 'configs/cloud-pipeline.json')
            with patch('mmd_fraud.bootstrap.prepare_dependencies', return_value=Path(sys.executable)), \
                    patch.object(entry.subprocess, 'Popen') as launch:
                launch.return_value.wait.return_value = 0
                entry.bootstrap(args)
            command = launch.call_args.args[0]
            self.assertEqual(command[0], sys.executable)
            self.assertIn('--worker', command)
            self.assertEqual(launch.call_args.kwargs['env']['PYSPARK_PYTHON'], sys.executable)
            self.assertEqual(launch.call_args.kwargs['env']['PYTHONPATH'], str(REPO / 'src'))

    def test_colab_detection_uses_runtime_information_and_host_directory(self):
        for variable in ('COLAB_RELEASE_TAG', 'COLAB_BACKEND_VERSION', 'MMDS_COLAB_RUNTIME'):
            with patch.dict(os.environ, {variable: '1'}, clear=True), \
                    patch.object(Path, 'is_dir', return_value=True):
                self.assertTrue(is_colab())
        with patch.dict(os.environ, {}, clear=True), patch.object(Path, 'is_dir', return_value=True):
            self.assertFalse(is_colab())
        with patch.dict(os.environ, {'COLAB_RELEASE_TAG': 'release'}, clear=True), \
                patch.object(Path, 'is_dir', return_value=False):
            self.assertFalse(is_colab())

    def test_colab_ignores_partial_venv_without_ensurepip(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            partial = root / 'venv-3.13'
            partial.mkdir()
            (partial / 'pyvenv.cfg').write_text('incomplete earlier attempt')
            with patch('mmd_fraud.bootstrap.is_colab', return_value=True), \
                    patch.object(bootstrap.venv, 'create') as create, \
                    patch.object(bootstrap.importlib.util, 'find_spec', return_value=None):
                python = bootstrap.select_python(root, io.StringIO())
            self.assertEqual(python, root / f'colab-venv-{sys.version_info.major}.{sys.version_info.minor}/bin/python')
            create.assert_called_once_with(python.parent.parent, with_pip=False)
            self.assertTrue(partial.exists())

    def test_broken_cloud_venv_is_rebuilt_without_touching_checkpoints(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env = root / f'venv-{sys.version_info.major}.{sys.version_info.minor}'
            (env / 'bin').mkdir(parents=True)
            (env / 'bin/python').touch()
            checkpoint = root / 'runs/keep.json'
            checkpoint.parent.mkdir()
            checkpoint.write_text('preserve')
            def create(path, with_pip):
                self.assertFalse(path.exists())
                self.assertTrue(with_pip)
                (path / 'bin').mkdir(parents=True)
                (path / 'bin/python').touch()
            with patch('mmd_fraud.bootstrap.is_colab', return_value=False), \
                    patch.object(bootstrap.subprocess, 'run', side_effect=subprocess.CalledProcessError(1, 'python')), \
                    patch.object(bootstrap.importlib.util, 'find_spec', return_value=object()), \
                    patch.object(bootstrap.venv, 'create', side_effect=create) as factory:
                selected = bootstrap.select_python(root, io.StringIO())
            factory.assert_called_once_with(env, with_pip=True)
            self.assertEqual(selected, env / 'bin/python')
            self.assertEqual(checkpoint.read_text(), 'preserve')

    def test_healthy_cloud_venv_is_reused(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            env = root / f'venv-{sys.version_info.major}.{sys.version_info.minor}'
            env.mkdir()
            with patch('mmd_fraud.bootstrap.is_colab', return_value=False), \
                    patch.object(bootstrap.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)), \
                    patch.object(bootstrap.venv, 'create') as create:
                self.assertEqual(bootstrap.select_python(root, io.StringIO()), env / 'bin/python')
            create.assert_not_called()

    def test_non_colab_missing_ensurepip_has_precise_error(self):
        with tempfile.TemporaryDirectory() as temp, \
                patch('mmd_fraud.bootstrap.is_colab', return_value=False), \
                patch.object(bootstrap.importlib.util, 'find_spec', return_value=None), \
                patch.object(bootstrap.venv, 'create') as create:
            with self.assertRaisesRegex(RuntimeError, 'non-Colab cloud Python lacks ensurepip'):
                bootstrap.select_python(Path(temp), io.StringIO())
            create.assert_not_called()

    def test_matching_pins_and_project_skip_reinstalls_and_use_runtime_python(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            stamp = {'python': sys.executable, 'repo': str(REPO.resolve()),
                     'pyproject_sha256': hashlib.sha256((REPO / 'pyproject.toml').read_bytes()).hexdigest()}
            (root / 'dependencies.json').write_text(json.dumps(stamp))
            def command(args, **kwargs):
                self.assertEqual(args[0], sys.executable)
                if bootstrap.PROBE in args:
                    return subprocess.CompletedProcess(args, 0, json.dumps({'missing': {}, 'editable': True}))
                return subprocess.CompletedProcess(args, 0)
            with patch('mmd_fraud.bootstrap.is_colab', return_value=True), \
                    patch.object(bootstrap, 'select_python', return_value=Path(sys.executable)), \
                    patch.object(bootstrap.subprocess, 'run', side_effect=command) as calls:
                self.assertEqual(bootstrap.prepare_dependencies(REPO, root, io.StringIO()), Path(sys.executable))
            self.assertFalse(any('install' in c.args[0] for c in calls.call_args_list))
            self.assertTrue(any(bootstrap.VERIFY in c.args[0] for c in calls.call_args_list))

    def test_mismatched_dependencies_install_and_verify_before_caching(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            def command(args, **kwargs):
                if bootstrap.PROBE in args:
                    return subprocess.CompletedProcess(args, 0, json.dumps({
                        'missing': {'numpy': {'expected': '2.2.6', 'actual': '2.0.0'}}, 'editable': False}))
                if bootstrap.VERIFY in args:
                    raise subprocess.CalledProcessError(1, args)
                return subprocess.CompletedProcess(args, 0)
            with patch('mmd_fraud.bootstrap.is_colab', return_value=True), \
                    patch.object(bootstrap, 'select_python', return_value=Path(sys.executable)), \
                    patch.object(bootstrap.subprocess, 'run', side_effect=command) as calls:
                with self.assertRaises(subprocess.CalledProcessError):
                    bootstrap.prepare_dependencies(REPO, root, io.StringIO())
            self.assertTrue(any('-r' in c.args[0] for c in calls.call_args_list))
            self.assertFalse((root / 'dependencies.json').exists())

    def test_real_fresh_interpreter_imports_without_using_ensurepip(self):
        # Exercise a REAL empty isolated environment using runtime pip, with ensurepip absent.
        # Downloads are pinned packages only; never an external dataset.
        pins = bootstrap.locked_versions(REPO / 'requirements-cloud.lock')
        probe = subprocess.run([sys.executable, '-c', bootstrap.PROBE,
                                json.dumps({'pins': pins, 'repo': str(REPO)})],
                               check=True, capture_output=True, text=True)
        self.assertEqual(json.loads(probe.stdout)['missing'], {})
        with tempfile.TemporaryDirectory() as temp, patch('mmd_fraud.bootstrap.is_colab', return_value=True), \
                patch.object(bootstrap.importlib.util, 'find_spec', return_value=None), \
                patch.object(bootstrap.venv, 'create', wraps=bootstrap.venv.create) as create:
            root = Path(temp)
            with (root / 'bootstrap.log').open('w') as log:
                selected = bootstrap.prepare_dependencies(REPO, root, log)
                # Second run checks actual installed metadata and must skip all installs.
                with patch.object(bootstrap.subprocess, 'run', wraps=subprocess.run) as commands:
                    bootstrap.prepare_dependencies(REPO, root, log)
            create.assert_called_once_with(selected.parent.parent, with_pip=False)
            self.assertEqual(selected.parent.parent.parent, root)
            self.assertNotEqual(str(selected), sys.executable)
            self.assertFalse(any('install' in c.args[0] for c in commands.call_args_list))

    def test_global_conflicts_are_reported_and_target_pip_check_is_mandatory(self):
        with tempfile.TemporaryDirectory() as temp:
            log = io.StringIO()
            target = Path(temp) / 'colab-venv-3.13/bin/python'
            def command(args, **kwargs):
                if args == [sys.executable, '-m', 'pip', 'check']:
                    return subprocess.CompletedProcess(args, 1)  # existing missing jedi/bigframes conflict
                if bootstrap.PROBE in args:
                    return subprocess.CompletedProcess(args, 0, json.dumps({'missing': {}, 'editable': True}))
                if args[-1] == 'check':
                    raise subprocess.CalledProcessError(1, args)
                return subprocess.CompletedProcess(args, 0)
            with patch('mmd_fraud.bootstrap.is_colab', return_value=True), \
                    patch.object(bootstrap, 'select_python', return_value=target), \
                    patch.object(bootstrap.subprocess, 'run', side_effect=command) as calls:
                with self.assertRaises(subprocess.CalledProcessError):
                    bootstrap.prepare_dependencies(REPO, Path(temp), log)
            self.assertIn('Global pip check exit status: 1', log.getvalue())
            self.assertTrue(any(c.args[0][:5] == [sys.executable, '-m', 'pip', '--python', str(target)]
                                for c in calls.call_args_list))
            self.assertFalse((Path(temp) / 'dependencies.json').exists())
            for call in calls.call_args_list:
                args = call.args[0]
                if 'install' in args:
                    self.assertIn('--python', args)

    def test_partial_colab_isolated_environment_is_rebuilt_without_pip(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            environment = root / f'colab-venv-{sys.version_info.major}.{sys.version_info.minor}'
            environment.mkdir()
            (environment / 'partial').touch()
            with patch('mmd_fraud.bootstrap.is_colab', return_value=True), \
                    patch.object(bootstrap.subprocess, 'run', side_effect=FileNotFoundError('partial python')), \
                    patch.object(bootstrap.importlib.util, 'find_spec', return_value=None), \
                    patch.object(bootstrap.venv, 'create') as create:
                selected = bootstrap.select_python(root, io.StringIO())
            create.assert_called_once_with(environment, with_pip=False)
            self.assertEqual(selected, environment / 'bin/python')
            self.assertFalse((environment / 'partial').exists())
