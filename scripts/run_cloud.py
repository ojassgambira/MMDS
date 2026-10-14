"""Single cloud entry point; bootstrap an isolated environment, then run the worker."""
import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import venv

REPO = Path(__file__).resolve().parents[1]


def require_cloud():
    if Path("/etc/codex/network-policy.json").is_file():
        return
    if os.environ.get("GITHUB_ACTIONS") == "true":
        return
    if Path("/content").is_dir():
        if os.environ.get("MMDS_COLAB_RUNTIME") == "1":
            return
        try:
            if importlib.util.find_spec("google.colab"):
                os.environ["MMDS_COLAB_RUNTIME"] = "1"
                return
        except ModuleNotFoundError:
            pass
    raise RuntimeError("Use a cloud runtime; this entry point refuses local device execution")


def main():
    require_cloud()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--storage", type=Path)
    parser.add_argument("--config", type=Path, default=REPO / "configs/cloud-pipeline.json")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    if not (3, 11) <= sys.version_info[:2] <= (3, 13):
        raise RuntimeError("Validated Python range is 3.11–3.13. Select a compatible Colab runtime.")
    # Validate output boundaries before creating directories or installing packages.
    sys.path.insert(0, str(REPO / "src"))
    from mmd_fraud.data.acquire import outside_repo
    args.workspace = outside_repo(args.workspace)
    if args.storage:
        args.storage = outside_repo(args.storage)
        if (args.storage == args.workspace or args.workspace in args.storage.parents
                or args.storage in args.workspace.parents):
            raise ValueError("storage must be separate from the temporary workspace")
    args.workspace.mkdir(parents=True, exist_ok=True)
    java = subprocess.run(["java", "-version"], capture_output=True, text=True, check=True)
    if not re.search(r'version "(17|21)\.', java.stderr):
        raise RuntimeError("Select a Colab runtime with Java 17 or 21")
    if not args.worker:
        environment = args.workspace / f"venv-{sys.version_info.major}.{sys.version_info.minor}"
        python = environment / "bin/python"
        if not python.exists():
            venv.create(environment, with_pip=True)
        log_path = args.workspace / "bootstrap.log"
        with log_path.open("a") as log:
            for command in (
                [str(python), "-m", "pip", "install", "--retries", "0", "--timeout", "30",
                 "-r", str(REPO / "requirements-cloud.lock")],
                [str(python), "-m", "pip", "install", "--no-build-isolation", "--no-deps",
                 "-e", str(REPO)],
                [str(python), "-m", "pip", "check"],
            ):
                print("Installing/checking pinned cloud dependencies…", flush=True)
                subprocess.run(command, stdout=log, stderr=log, check=True, timeout=900)
        command = [str(python), str(Path(__file__).resolve()), "--worker",
                   "--workspace", str(args.workspace), "--config", str(args.config.resolve())]
        if args.storage:
            command.extend(["--storage", str(args.storage)])
        env = {**os.environ, "SPARK_LOCAL_IP": "127.0.0.1", "PYSPARK_PYTHON": str(python),
               "OMP_NUM_THREADS": "2", "OPENBLAS_NUM_THREADS": "2"}
        # Bound the whole workload and stop the JVM as well on timeout/interruption.
        process = subprocess.Popen(command, env=env, start_new_session=True)
        try:
            if process.wait(timeout=3600):
                raise RuntimeError(f"Pipeline failed; inspect {args.workspace}/runs/*/report.md")
        except BaseException:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    os.killpg(process.pid, signal.SIGKILL)
            raise
        return
    from mmd_fraud.automation import run_workflow
    os.environ.update({"SPARK_LOCAL_IP": "127.0.0.1", "PYSPARK_PYTHON": sys.executable})
    config = json.loads(args.config.read_text())
    # JVM and Python stderr are recorded together, including failed stages.
    with (args.workspace / "runtime.log").open("a") as log:
        original_stderr = os.dup(2)
        try:
            os.dup2(log.fileno(), 2)
            result = run_workflow(REPO, args.workspace, config, args.storage)
        finally:
            os.dup2(original_stderr, 2)
            os.close(original_stderr)
    (args.workspace / "latest-report.txt").write_text(str(result / "report.md"))


if __name__ == "__main__":
    main()
