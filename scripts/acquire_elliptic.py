"""Cloud-only acquisition CLI. Requires permitted HTTPS to data.pyg.org."""
import argparse
import json
from pathlib import Path
from mmd_fraud.data.acquire import acquire

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--destination", type=Path, required=True)
    parser.add_argument("--max-download-bytes", type=int, default=200_000_000)
    parser.add_argument("--max-expanded-bytes", type=int, default=500_000_000)
    args = parser.parse_args()
    print(json.dumps(acquire(args.destination, args.max_download_bytes,
                             args.max_expanded_bytes), indent=2))
