"""Cloud-only acquisition CLI. Requires permitted HTTPS to data.pyg.org."""
import argparse
import json
from pathlib import Path
from mmd_fraud.data.acquire import acquire, MAX_DOWNLOAD_BYTES, MAX_EXPANDED_BYTES, STREAM_SECONDS

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--max-download-bytes", type=int, default=MAX_DOWNLOAD_BYTES)
    parser.add_argument("--max-expanded-bytes", type=int, default=MAX_EXPANDED_BYTES)
    parser.add_argument("--seconds", type=int, default=STREAM_SECONDS)
    args = parser.parse_args()
    print(json.dumps(acquire(args.destination, args.max_download_bytes,
                             args.max_expanded_bytes, args.seconds), indent=2))
