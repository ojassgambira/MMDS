"""Run distributed preprocessing in Codex Cloud; source data must already exist."""
import argparse
import json
from pathlib import Path
from mmd_fraud.spark.pipeline import run

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--profiles", type=Path, default=Path("configs/profiles.json"))
    parser.add_argument("--profile", choices=["small", "medium", "large"], default="medium")
    parser.add_argument("--domain", choices=["bitcoin", "banking"], default="bitcoin")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--master", default="local[2]")
    parser.add_argument("--cutoffs", type=int, nargs="+", default=[2, 35, 50])
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    profile = json.loads(args.profiles.read_text())[args.profile]
    print(json.dumps(run(config, profile, args.output, args.domain, args.master,
                         tuple(args.cutoffs)), indent=2))
