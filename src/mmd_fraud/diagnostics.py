"""Dependency-free failure summaries usable before environment installation."""

import json
import re
from pathlib import Path
from urllib.error import HTTPError


def redact(text: str) -> str:
    text = re.sub(r"(https?://)[^\s/@]+:[^\s/@]+@", r"\1[REDACTED]@", text)
    # Structured error bodies often quote keys and values, including spaces.
    text = re.sub(
        r"""(?i)(["'](?:kaggle_key|password|token|api_key|authorization|access_token|refresh_token)["']\s*:\s*)(["'])(?:\\.|(?!\2).)*?\2""",
        r'\1"[REDACTED]"',
        text,
    )
    text = re.sub(r"(?im)(authorization\s*[:=]\s*)[^\n]+", r"\1[REDACTED]", text)
    return re.sub(
        r"(?i)((?:kaggle_key|password|token|api_key|authorization)\s*[=:]\s*)[^\s&]+",
        r"\1[REDACTED]",
        text,
    )


def tail(path: Path, max_bytes: int = 8000, max_lines: int = 60) -> str:
    try:
        with path.open("rb") as handle:
            handle.seek(0, 2)
            size = handle.tell()
            handle.seek(max(0, size - max_bytes))
            text = handle.read(max_bytes).decode("utf-8", errors="replace")
        return redact("\n".join(text.splitlines()[-max_lines:])) or "(empty log)"
    except OSError as exc:
        return f"(log unavailable: {type(exc).__name__})"


def guidance(error: Exception, stage: str) -> str:
    if isinstance(error, HTTPError) and error.code in {401, 403} and stage == "acquisition":
        return (
            "Dataset access was denied. Open the official Elliptic Kaggle release, authorize "
            "access/accept its terms, place the three authorized CSVs in private Drive, and "
            "select an 'existing' source configuration in the notebook form. The default "
            "PyG mirror uses no Kaggle credentials. Do not retry a denied download."
        )
    if stage == "acquisition":
        return "Acquisition stopped without retry; see the source error below. No dataset success is claimed."
    if stage == "storage":
        return (
            "Check the mounted Drive's capacity and write access, then Run all again. "
            "Completed local checkpoints are preserved; copying can resume."
        )
    if stage == "dependencies":
        return "Dependency installation/check failed. The pip error below identifies the package or access issue."
    return "Completed verified stages can resume on Run all; the failed stage is not marked successful."


def failure_details(
    workspace: Path, error: Exception | None = None, prefer_recorded: bool = True
) -> str:
    parts = ["MMDS execution failed; no successful execution is claimed."]
    try:
        status = json.loads((workspace / "failure.json").read_text()) if prefer_recorded else None
        if not isinstance(status, dict) or any(
            not isinstance(status.get(name), str) for name in ("stage", "error", "instruction")
        ):
            raise ValueError("no usable current failure record")
        parts += [f"Stage: {status['stage']}", status["error"], status["instruction"]]
    except (OSError, ValueError, KeyError):
        status = None
    if not prefer_recorded:
        parts.append(
            "Setup failed before worker launch; available log tails may be from an earlier attempt."
        )
    if error and status is None:
        parts.append(redact(f"{type(error).__name__}: {error}"))
        for name in ("stdout", "stderr", "output"):
            output = getattr(error, name, None)
            if output:
                if isinstance(output, bytes):
                    output = output.decode(errors="replace")
                parts.append(redact(str(output)[-8000:]))
    logs = [workspace / name for name in ("bootstrap.log", "runtime.log", "worker.log")]
    try:
        active = Path((workspace / "active-run.txt").read_text())
        if active.resolve().is_relative_to((workspace / "runs").resolve()):
            logs.append(active / "execution.log")
    except (OSError, ValueError):
        pass
    for path in logs:
        parts += [f"\n--- Final relevant lines: {path.name} ---", tail(path)]
    return "\n".join(parts)


def record_failure(workspace: Path, error: Exception, stage: str) -> None:
    detail = f"{type(error).__name__}: {error}"
    for name in ("stderr", "output"):
        output = getattr(error, name, None)
        if output:
            if isinstance(output, bytes):
                output = output.decode(errors="replace")
            detail += "\n" + str(output)[-8000:]
    value = {
        "status": "failed",
        "stage": stage,
        "error": redact(detail),
        "instruction": guidance(error, stage),
    }
    temporary = workspace / "failure.tmp"
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(workspace / "failure.json")
