"""Bounded release metadata inspection: ZIP tails only, no CSV bodies or credentials."""
import io
import re
import time
import urllib.request
import zipfile

from .acquire import FILES, SOURCE, LICENSE, open_remote

TAIL_BYTES = 65557  # EOCD plus maximum ZIP comment; original single-member ZIPs fit.


def inspect_release() -> dict:
    records = []
    started = time.monotonic()
    for name in FILES:
        url = f"{SOURCE}/{name}.zip"
        request = urllib.request.Request(url, headers={"Range": f"bytes=-{TAIL_BYTES}",
                                                      "Accept-Encoding": "identity"})
        with open_remote(request) as response:
            if response.status != 206 or response.url != url:
                raise ValueError(f"{name}: bounded ZIP metadata requires HTTP 206 at the authorized URL")
            match = re.fullmatch(r"bytes (\d+)-(\d+)/(\d+)",
                                 response.headers.get("Content-Range", ""))
            if not match:
                raise ValueError(f"{name}: missing/invalid Content-Range")
            first, last, total = map(int, match.groups())
            if last != total - 1 or first != max(0, total - TAIL_BYTES):
                raise ValueError(f"{name}: unexpected ZIP tail range")
            payload = response.read(TAIL_BYTES + 1)
            if len(payload) != last - first + 1 or len(payload) > TAIL_BYTES:
                raise ValueError(f"{name}: truncated or oversized metadata response")
        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            entries = archive.infolist()
            if len(entries) != 1 or entries[0].filename != name or entries[0].is_dir():
                raise ValueError(f"{name}: unexpected ZIP members")
            entry = entries[0]
            if entry.flag_bits & 1 or entry.compress_type != zipfile.ZIP_DEFLATED:
                raise ValueError(f"{name}: encrypted/unsupported archive")
            records.append({"file": name, "url": url, "archive_bytes": total,
                            "member_compressed_bytes": entry.compress_size,
                            "expanded_bytes": entry.file_size, "crc32": f"{entry.CRC:08x}",
                            "metadata_bytes_read": len(payload)})
    return {"source": SOURCE, "publisher": "ellipticco/elliptic-data-set", "license": LICENSE,
            "inspection": "HTTP 206 ZIP central directories; CSV contents not downloaded or validated",
            "inspected_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "seconds": time.monotonic() - started, "files": records,
            "archive_bytes": sum(r["archive_bytes"] for r in records),
            "expanded_bytes": sum(r["expanded_bytes"] for r in records),
            "metadata_bytes_read": sum(r["metadata_bytes_read"] for r in records)}
