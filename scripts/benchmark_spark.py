"""Run bounded generated-fixture benchmarks in cloud infrastructure; never on a Mac."""

import argparse
from pathlib import Path
from mmd_fraud.spark.benchmark import run_benchmarks

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--workspace", type=Path, required=True)
    args = parser.parse_args()
    result = run_benchmarks(args.workspace)
    print(result["configuration"])
    print(result["measurements"])
