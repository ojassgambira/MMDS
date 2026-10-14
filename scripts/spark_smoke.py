"""Run only in cloud; Spark local[2] means cloud worker processes."""
import json
from mmd_fraud.spark.smoke import run_smoke

if __name__ == "__main__":
    print(json.dumps(run_smoke(), sort_keys=True))
