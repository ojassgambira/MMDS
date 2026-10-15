"""Acquire original Elliptic files from the documented PyG mirror, never implicitly."""
import hashlib
import json
import shutil
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

FILES = ("elliptic_txs_features.csv", "elliptic_txs_classes.csv", "elliptic_txs_edgelist.csv")
SOURCE = "https://data.pyg.org/datasets/elliptic"
LICENSE = "CC-BY-NC-ND-4.0"
# Measured 2026-10-15 via three bounded ZIP central-directory Range requests.
# ZIPs total 153,218,212 bytes; CSVs total 697,459,499 bytes. See docs/issue-7.md.
MAX_DOWNLOAD_BYTES = 200_000_000
MAX_EXPANDED_BYTES = 750_000_000
STREAM_SECONDS = 600


def validate_limits(download, expanded, seconds=STREAM_SECONDS):
    for name, value, ceiling in (("max_download_bytes", download, 300_000_000),
                                 ("max_expanded_bytes", expanded, 1_000_000_000),
                                 ("acquisition_seconds", seconds, 1800)):
        if type(value) is not int or not 0 < value <= ceiling:
            raise ValueError(f"{name} must be an integer in 1..{ceiling}")


def deadline(start, seconds):
    if time.monotonic() - start > seconds:
        raise TimeoutError(f"acquisition exceeds {seconds}-second stream budget")


class MirrorRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not newurl.startswith(SOURCE + "/"):
            raise ValueError("unexpected redirect; inspect new host before acquisition")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def open_remote(request):
    return urllib.request.build_opener(MirrorRedirects()).open(request, timeout=60)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def outside_repo(path: Path) -> Path:
    resolved = path.resolve()
    if any((parent / ".git").is_file() or (parent / ".git" / "HEAD").exists()
           for parent in (resolved, *resolved.parents)):
        raise ValueError("datasets and outputs must be outside a Git checkout")
    return resolved


def extract_one(archive: Path, destination: Path, filename: str, limit: int,
                *, total_limit: int | None = None, start=None, seconds=STREAM_SECONDS) -> None:
    with zipfile.ZipFile(archive) as zipped:
        entries = zipped.infolist()
        if len(entries) != 1 or entries[0].filename != filename or entries[0].is_dir():
            raise ValueError(f"{filename}: unexpected ZIP members; no arbitrary archive extraction")
        if entries[0].file_size > limit:
            raise ValueError(f"{filename}: uncompressed file limit exceeded; declared_size="
                             f"{entries[0].file_size}, remaining_allowance={limit}, "
                             f"expanded_limit={total_limit if total_limit is not None else limit}")
        count = 0
        with zipped.open(entries[0]) as source, destination.open("xb") as output:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                if start is not None:
                    deadline(start, seconds)
                count += len(chunk)
                if count > limit:
                    raise ValueError(f"{filename}: uncompressed stream limit exceeded; streamed={count}, remaining_allowance={limit}, expanded_limit={total_limit}")
                output.write(chunk)


def acquire(destination: Path, max_download_bytes: int = MAX_DOWNLOAD_BYTES,
            max_expanded_bytes: int = MAX_EXPANDED_BYTES,
            seconds: int = STREAM_SECONDS) -> dict:
    destination = outside_repo(destination)
    validate_limits(max_download_bytes, max_expanded_bytes, seconds)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise FileExistsError("refusing to replace existing acquisition")
    if shutil.disk_usage(destination.parent).free < max_download_bytes + max_expanded_bytes:
        raise ValueError("insufficient free disk for bounded acquisition")
    start = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="elliptic-acquire-", dir=destination.parent) as temporary:
        stage = Path(temporary)
        records, downloaded, expanded = [], 0, 0
        for filename in FILES:
            url = f"{SOURCE}/{filename}.zip"
            archive = stage / f"{filename}.zip"
            request = urllib.request.Request(url, headers={"User-Agent": "MMDS-academic-research/0.2"})
            with open_remote(request) as response, archive.open("xb") as output:
                if not response.url.startswith(SOURCE + "/"):
                    raise ValueError("unexpected redirect; inspect new host before acquisition")
                declared = response.headers.get("Content-Length")
                if declared is not None and int(declared) > max_download_bytes - downloaded:
                    raise ValueError(f"{filename}.zip: compressed limit exceeded; declared_size="
                                     f"{declared}, remaining_allowance={max_download_bytes - downloaded}, "
                                     f"download_limit={max_download_bytes}")
                archive_bytes = 0
                for chunk in iter(lambda: response.read(1024 * 1024), b""):
                    deadline(start, seconds)
                    archive_bytes += len(chunk)
                    downloaded += len(chunk)
                    if downloaded > max_download_bytes:
                        raise ValueError(f"{filename}.zip: total download limit exceeded; streamed={downloaded}, download_limit={max_download_bytes}")
                    output.write(chunk)
            if declared is not None and archive_bytes != int(declared):
                raise ValueError(f"{filename}.zip: truncated download; declared_size={declared}, received={archive_bytes}")
            target = stage / filename
            extract_one(archive, target, filename, max_expanded_bytes - expanded,
                        total_limit=max_expanded_bytes, start=start, seconds=seconds)
            expanded += target.stat().st_size
            records.append({"file": filename, "url": url, "bytes": target.stat().st_size,
                            "sha256": sha256(target), "archive_sha256": sha256(archive),
                            "archive_bytes": archive_bytes})
            archive.unlink()
        deadline(start, seconds)
        manifest = {"source": SOURCE, "publisher": "ellipticco/elliptic-data-set",
                    "license": LICENSE, "license_url": "https://www.kaggle.com/ellipticco/elliptic-data-set",
                    "acquired_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "downloaded_bytes": downloaded, "expanded_bytes": expanded,
                    "limits": {"max_download_bytes": max_download_bytes,
                               "max_expanded_bytes": max_expanded_bytes, "seconds": seconds},
                    "elapsed_seconds": time.monotonic() - start, "files": records}
        (stage / "acquisition.json").write_text(json.dumps(manifest, indent=2) + "\n")
        stage.rename(destination)
    return manifest


def verify_acquisition(directory: Path, max_download_bytes=MAX_DOWNLOAD_BYTES,
                       max_expanded_bytes=MAX_EXPANDED_BYTES) -> dict:
    """Recheck private caches before reuse; hashes establish integrity, not publisher signatures."""
    validate_limits(max_download_bytes, max_expanded_bytes)
    directory = outside_repo(directory)
    manifest = json.loads((directory / "acquisition.json").read_text())
    if (manifest.get("source") != SOURCE or manifest.get("license") != LICENSE
            or manifest.get("publisher") != "ellipticco/elliptic-data-set"):
        raise ValueError("unexpected source provenance")
    records = manifest["files"]
    if len(records) != len(FILES) or {r["file"] for r in records} != set(FILES):
        raise ValueError("raw provenance must contain exactly the three publisher CSVs")
    total = 0
    for r in records:
        path = directory / r["file"]
        if (path.is_symlink() or r.get("url") != f"{SOURCE}/{path.name}.zip"
                or path.stat().st_size != r["bytes"]):
            raise ValueError(f"raw input hashes/size/provenance mismatch: {path.name}")
        total += r["bytes"]
    if (manifest["expanded_bytes"] != total or total > max_expanded_bytes
            or not 0 < manifest["downloaded_bytes"] <= max_download_bytes
            or (all("archive_bytes" in r for r in records)
                and sum(r["archive_bytes"] for r in records) != manifest["downloaded_bytes"])):
        raise ValueError("cached acquisition exceeds limits or has inconsistent byte totals")
    # Enforce the cumulative cache byte ceiling before reading payloads for hashing.
    for r in records:
        if sha256(directory / r["file"]) != r["sha256"]:
            raise ValueError(f"raw input hashes/size/provenance mismatch: {r['file']}")
    return manifest
