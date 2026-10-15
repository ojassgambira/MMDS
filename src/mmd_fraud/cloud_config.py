"""Validate cloud settings and mount/write access before expensive setup."""
import os
from pathlib import Path
import tempfile

from .data.acquire import (FILES, outside_repo, MAX_DOWNLOAD_BYTES, MAX_EXPANDED_BYTES,
                           STREAM_SECONDS, validate_limits)


def validate_config(config: dict) -> dict:
    if not isinstance(config, dict):
        raise ValueError("configuration must be a JSON object")
    allowed = {"source", "data_mode", "sample_per_step", "train_end", "validation_end",
               "seed", "master", "input_directory", "max_download_bytes",
               "max_expanded_bytes", "acquisition_seconds", "experiments", "research"}
    if set(config) - allowed:
        raise ValueError(f"unknown configuration keys: {sorted(set(config) - allowed)}")
    config = {"source": "pyg", "data_mode": "full", "sample_per_step": 200,
              "train_end": 34, "validation_end": 39, "seed": 0,
              "master": "local[2]", "experiments": False, "research": False, "max_download_bytes": MAX_DOWNLOAD_BYTES,
              "max_expanded_bytes": MAX_EXPANDED_BYTES, "acquisition_seconds": STREAM_SECONDS, **config}
    if type(config["experiments"]) is not bool:
        raise ValueError("experiments must be boolean")
    if type(config["research"]) is not bool or (config["research"] and not config["experiments"]):
        raise ValueError("research requires experiments and boolean settings")
    validate_limits(config["max_download_bytes"], config["max_expanded_bytes"],
                    config["acquisition_seconds"])
    if config["source"] not in {"pyg", "existing", "generated_test_fixture"}:
        raise ValueError("source must be pyg, existing, or generated_test_fixture")
    if config["data_mode"] not in {"full", "sample"} or config["master"] != "local[2]":
        raise ValueError("data_mode must be full/sample; master must be local[2]")
    for key in ("sample_per_step", "train_end", "validation_end", "seed"):
        if type(config[key]) is not int:
            raise ValueError(f"{key} must be an integer")
    if not 1 <= config["train_end"] < config["validation_end"] < 49:
        raise ValueError("split boundaries must satisfy 1 <= train_end < validation_end < 49")
    if not 1 <= config["sample_per_step"] <= 200 or not 0 <= config["seed"] < 2**32:
        raise ValueError("sample_per_step must be 1–200; seed must be 0..2**32-1")
    if config["research"] and (config["train_end"], config["validation_end"], config["seed"]) != (34, 39, 0):
        raise ValueError("research protocol fixes splits 34/39 and seed 0")
    if config["source"] != "pyg":
        if not isinstance(config.get("input_directory"), str) or not config["input_directory"]:
            raise ValueError("existing source requires input_directory containing all three publisher CSVs")
        source = outside_repo(Path(config["input_directory"]))
        missing = [name for name in FILES if not (source / name).is_file()]
        if missing:
            raise ValueError(f"source CSVs missing: {', '.join(missing)}")
    return config


def validate_paths(workspace: Path, storage: Path | None) -> tuple[Path, Path | None]:
    workspace = outside_repo(workspace)
    storage = outside_repo(storage) if storage else None
    if storage and (storage == workspace or workspace in storage.parents
                    or storage in workspace.parents):
        raise ValueError("storage must be separate from the temporary workspace")
    if storage and storage.is_relative_to(Path("/content/drive")):
        # Do not create a fake MyDrive directory when the mount is absent.
        if not os.path.ismount("/content/drive") or not Path("/content/drive/MyDrive").is_dir():
            raise ValueError("Google Drive is not mounted. Authorize the notebook's Drive prompt first.")
    for directory in (workspace, storage):
        if directory:
            directory.mkdir(parents=True, exist_ok=True)
            try:
                with tempfile.TemporaryFile(dir=directory) as handle:
                    handle.write(b"MMDS write probe")
                    handle.flush()
                    handle.seek(0)
                    if handle.read() != b"MMDS write probe":
                        raise OSError("write/read probe mismatch")
            except OSError as exc:
                raise OSError(f"Storage path is not writable: {directory}: {exc}") from exc
    return workspace, storage
