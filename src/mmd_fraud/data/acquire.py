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


def extract_one(archive: Path, destination: Path, filename: str, limit: int) -> None:
    with zipfile.ZipFile(archive) as zipped:
        entries = zipped.infolist()
        if len(entries) != 1 or entries[0].filename != filename or entries[0].is_dir():
            raise ValueError("unexpected ZIP members; no arbitrary archive extraction")
        if entries[0].file_size > limit:
            raise ValueError("uncompressed file limit exceeded")
        count = 0
        with zipped.open(entries[0]) as source, destination.open("xb") as output:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                count += len(chunk)
                if count > limit:
                    raise ValueError("uncompressed stream limit exceeded")
                output.write(chunk)


def acquire(destination: Path, max_download_bytes: int = 200_000_000,
            max_expanded_bytes: int = 500_000_000) -> dict:
    destination = outside_repo(destination)
    if max_download_bytes <= 0 or max_expanded_bytes <= 0:
        raise ValueError("limits must be positive")
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
                for chunk in iter(lambda: response.read(1024 * 1024), b""):
                    if time.monotonic() - start > 300:
                        raise TimeoutError("acquisition exceeds 300-second stream budget")
                    downloaded += len(chunk)
                    if downloaded > max_download_bytes:
                        raise ValueError("total download limit exceeded")
                    output.write(chunk)
            target = stage / filename
            extract_one(archive, target, filename, max_expanded_bytes - expanded)
            expanded += target.stat().st_size
            records.append({"file": filename, "url": url, "bytes": target.stat().st_size,
                            "sha256": sha256(target), "archive_sha256": sha256(archive)})
            archive.unlink()
        manifest = {"source": SOURCE, "publisher": "ellipticco/elliptic-data-set",
                    "license": LICENSE, "license_url": "https://www.kaggle.com/ellipticco/elliptic-data-set",
                    "acquired_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "downloaded_bytes": downloaded, "expanded_bytes": expanded,
                    "elapsed_seconds": time.monotonic() - start, "files": records}
        (stage / "acquisition.json").write_text(json.dumps(manifest, indent=2) + "\n")
        stage.rename(destination)
    return manifest
