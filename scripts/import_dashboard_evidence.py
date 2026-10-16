"""Import only hash-verified public aggregates; never datasets, model files or predictions."""

import argparse
from mmd_fraud.evidence import import_snapshot

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--domain", choices=["elliptic", "banking"], required=True)
    parser.add_argument("--workflow", required=True)
    parser.add_argument("--artifact-sha256", required=True)
    args = parser.parse_args()
    print(
        import_snapshot(
            args.source,
            args.domain,
            {"workflow": args.workflow, "artifact_sha256": args.artifact_sha256},
        )
    )
