"""Independent seeded banking simulation. NOT IBM AMLSim output or real fraud data."""

import csv
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path

import numpy as np

from .acquire import outside_repo, sha256

UPSTREAM = "7338a4bcb1af9bcfea2201ad7daccfe2a4d569ca"


def generate(output: Path, accounts=500, daily_events=600, seed=0):
    if (
        type(accounts) is not int
        or not 50 <= accounts <= 1000
        or type(daily_events) is not int
        or not 50 <= daily_events <= 1200
        or type(seed) is not int
        or not 0 <= seed < 2**32
    ):
        raise ValueError("bounded generator: 50..1000 accounts, 50..1200 daily events, uint32 seed")
    output = outside_repo(output)
    output.mkdir()  # immutable input
    # Interrupted generation is never silently reused.
    rng = np.random.default_rng(seed)
    names = np.array([f"A{i:05}" for i in range(accounts)])
    propensity = rng.lognormal(0, 0.7, accounts)
    propensity /= propensity.sum()
    risky_pool = rng.choice(accounts, max(12, accounts // 6), replace=False)
    records = []

    def event(day, source, target, amount, sar=False, alert="-1"):
        if source == target:
            target = (target + 1) % accounts
        records.append(
            [
                f"T{len(records):07}",
                names[source],
                names[target],
                "TRANSFER",
                f"{amount:.2f}",
                (datetime(2017, 1, 1, tzinfo=timezone.utc) + timedelta(days=day)).strftime(
                    "%Y-%m-%dT%H:%M:%SZ"
                ),
                str(bool(sar)).lower(),
                alert,
            ]
        )

    campaigns = {}
    for day in range(50):
        sources = rng.choice(accounts, daily_events, p=propensity)
        for source in sources:
            if rng.random() < 0.75:
                peers = np.arange((source // 25) * 25, min((source // 25 + 1) * 25, accounts))
                target = int(rng.choice(peers))
            else:
                target = int(rng.integers(accounts))
            event(day, int(source), target, rng.lognormal(5, 1.2))
        block = day // 7
        if block not in campaigns:
            campaigns[block] = rng.choice(risky_pool, 12, replace=False)
        # Persistent motifs plus benign lookalikes; no perfect amount/type/id label rule.
        for suspicious, group in [
            (True, campaigns[block]),
            (False, rng.choice(accounts, 12, replace=False)),
        ]:
            for i, source in enumerate(group):
                targets = [group[(i + 1) % 12], group[0], group[(i + 4) % 12]]
                for target in targets:
                    event(
                        day,
                        int(source),
                        int(target),
                        rng.lognormal(5 + 0.15 * (day >= 40), 1.2),
                        suspicious and rng.random() < 0.85,
                        f"{block}" if suspicious else "-1",
                    )
    rng.shuffle(records)  # CSV order must not encode causal order or label
    with (output / "accounts.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["acct_id"])
        writer.writerows([[v] for v in names])
    with (output / "transactions.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                "tran_id",
                "orig_acct",
                "bene_acct",
                "tx_type",
                "base_amt",
                "tran_timestamp",
                "is_sar",
                "alert_id",
            ]
        )
        writer.writerows(records)
    provenance = {
        "dataset_kind": "independent_synthetic_banking",
        "official_amlsim_output": False,
        "generator": "mmd_fraud.data.banking_synthetic.v1",
        "seed": seed,
        "accounts": accounts,
        "events": len(records),
        "days": 50,
        "daily_normal_events": daily_events,
        "time_unit": "days_from_2017-01-01_utc",
        "labels": "simulated SAR involvement, not confirmed fraud",
        "compatibility": "subset of IBM AMLSim converted schema; not simulator equivalence",
        "upstream_review_commit": UPSTREAM,
        "files": {n: sha256(output / n) for n in ("accounts.csv", "transactions.csv")},
    }
    (output / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    return provenance
