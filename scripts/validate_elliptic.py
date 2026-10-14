"""Cloud CLI: validate already-acquired data; never fetch data implicitly."""
import argparse
import json
from pathlib import Path
from mmd_fraud.adapters.elliptic import EllipticConfig, load_elliptic

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=Path, default=Path("configs/elliptic.json"))
    args = parser.parse_args()
    config = json.loads(args.config.read_text())
    config["directory"] = Path(config["directory"])
    graph = load_elliptic(EllipticConfig(**config))
    print(json.dumps({"domain": graph.domain.value, "nodes": len(graph.nodes),
                      "edges": len(graph.edges)}))
