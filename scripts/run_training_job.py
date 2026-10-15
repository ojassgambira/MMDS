"""Run bounded unattended real-data training only on free public GitHub-hosted CI."""
from mmd_fraud.cloud_job import main

if __name__ == '__main__':
    raise SystemExit(main())
