"""Cloud entry point; no local device execution is supported."""
from mmd_fraud.banking_job import main

if __name__ == '__main__':
    raise SystemExit(main())
