"""Bounded offline Bitcoin baselines; labels/anonymous aggregates are not inputs."""
import json
from pathlib import Path

import joblib
import numpy as np
import pyarrow.parquet as pq
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (average_precision_score, confusion_matrix, f1_score,
                             precision_score, recall_score)
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from mmd_fraud.spark.causal import FEATURES


def chronological_split(records: list[dict], train_end: int, validation_end: int) -> dict:
    if not 1 <= train_end < validation_end < 49:
        raise ValueError("chronological boundaries must satisfy 1 <= train < validation < 49")
    if len({r["entity_id"] for r in records}) != len(records):
        raise ValueError("duplicate transaction feature IDs")
    groups = {"train": [], "validation": [], "test": []}
    unknown = 0
    for row in records:
        step = row["time_step"]
        if not isinstance(step, int) or not 1 <= step <= 49:
            raise ValueError("invalid source time")
        if row["feature_cutoff_exclusive"] != step + 1:
            raise ValueError("features must be bounded to their transaction's completed step")
        if row["label"] == "unknown":
            unknown += 1
            continue
        if row["label"] not in {"1", "2"}:
            raise ValueError("invalid supervised label")
        group = "train" if step <= train_end else "validation" if step <= validation_end else "test"
        groups[group].append(row)
    for name, rows in groups.items():
        if {r["label"] for r in rows} != {"1", "2"}:
            raise ValueError(f"{name} must contain both illicit and licit labels; no metrics fabricated")
    return {"groups": groups, "unknown_excluded": unknown}


def evaluate(y: np.ndarray, probabilities: np.ndarray) -> dict:
    prediction = (probabilities >= 0.5).astype(int)
    return {
        "precision": float(precision_score(y, prediction, zero_division=0)),
        "recall": float(recall_score(y, prediction, zero_division=0)),
        "f1": float(f1_score(y, prediction, zero_division=0)),
        "pr_auc_average_precision": float(average_precision_score(y, probabilities)),
        "confusion_matrix": confusion_matrix(y, prediction, labels=[0, 1]).tolist(),
        "confusion_matrix_order": ["licit=0", "illicit=1"],
        "rows": len(y), "illicit": int(y.sum()), "threshold": 0.5,
    }


def train(feature_path: Path, output: Path, train_end: int = 34,
          validation_end: int = 39, seed: int = 0) -> dict:
    dataset = pq.ParquetDataset(feature_path)
    if sum(pq.read_metadata(p).num_rows for p in dataset.files) > 300000:
        raise ValueError("training table exceeds bounded original-release size")
    records = dataset.read(columns=["entity_id", "time_step", "label",
                                    "feature_cutoff_exclusive", *FEATURES]).to_pylist()
    splits = chronological_split(records, train_end, validation_end)
    arrays = {}
    for name, rows in splits["groups"].items():
        x = np.asarray([[r[c] for c in FEATURES] for r in rows], dtype=float)
        if not np.isfinite(x).all() or (x < 0).any():
            raise ValueError("invalid graph feature values")
        arrays[name] = (x, np.asarray([int(r["label"] == "1") for r in rows]))
    output.mkdir()
    models = {
        "prior": DummyClassifier(strategy="prior", random_state=seed),
        "logistic_regression": make_pipeline(
            StandardScaler(), LogisticRegression(class_weight="balanced", max_iter=1000,
                                                  random_state=seed)),
        "random_forest": RandomForestClassifier(
            n_estimators=64, max_depth=8, min_samples_leaf=3, class_weight="balanced",
            n_jobs=2, random_state=seed),
    }
    result = {
        "features": list(FEATURES), "seed": seed, "train_end": train_end,
        "validation_end": validation_end, "unknown_excluded": splits["unknown_excluded"],
        "task": "retrospective transaction classification after source step completes",
        "label_availability_assumption": "offline train labels known before validation; not verified live",
        "split_counts": {k: {"rows": len(y), "illicit": int(y.sum())}
                         for k, (_, y) in arrays.items()}, "models": {},
    }
    for name, model in models.items():
        model.fit(*arrays["train"])
        x, y = arrays["validation"]
        score = model.predict_proba(x)[:, list(model.classes_).index(1)]
        result["models"][name] = {"validation": evaluate(y, score)}
        joblib.dump(model, output / f"{name}.joblib")
    # Choose before any test evaluation; no threshold/hyperparameter search on test.
    result["selected_model"] = max(
        ("logistic_regression", "random_forest"),
        key=lambda n: result["models"][n]["validation"]["pr_auc_average_precision"])
    for name, model in models.items():
        x, y = arrays["test"]
        score = model.predict_proba(x)[:, list(model.classes_).index(1)]
        result["models"][name]["test"] = evaluate(y, score)
    (output / "metrics.json").write_text(json.dumps(result, indent=2) + "\n")
    return result
