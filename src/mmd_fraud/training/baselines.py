"""Bounded offline Bitcoin baselines; labels/anonymous aggregates are not inputs."""
import json
import time
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


def chronological_split(records: list[dict], train_end: int, validation_end: int, cutoff_offset: int = 1) -> dict:
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
        if row["feature_cutoff_exclusive"] != step + cutoff_offset:
            raise ValueError("invalid feature observation boundary")
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


def evaluate(y: np.ndarray, probabilities: np.ndarray, threshold: float = 0.5) -> dict:
    y, probabilities = np.asarray(y), np.asarray(probabilities)
    if (y.ndim != 1 or probabilities.shape != y.shape or set(y.tolist()) != {0, 1}
            or not np.isfinite(probabilities).all()
            or ((probabilities < 0) | (probabilities > 1)).any()):
        raise ValueError("metrics require both binary classes and finite probabilities in [0, 1]")
    if not np.isfinite(threshold) or not 0 <= threshold <= np.nextafter(1., 2.):
        raise ValueError("invalid decision threshold")
    prediction = (probabilities >= threshold).astype(int)
    matrix = confusion_matrix(y, prediction, labels=[0, 1])
    tn, fp, fn, tp = matrix.ravel()
    return {
        "precision": float(precision_score(y, prediction, zero_division=0)),
        "recall": float(recall_score(y, prediction, zero_division=0)),
        "f1": float(f1_score(y, prediction, zero_division=0)),
        "pr_auc_average_precision": float(average_precision_score(y, probabilities)),
        "false_positive_rate": float(fp / (fp + tn)),
        "confusion_matrix": matrix.tolist(),
        "confusion_matrix_order": ["licit=0", "illicit=1"],
        "rows": len(y), "illicit": int(y.sum()), "threshold": float(threshold),
    }


def train(feature_path: Path, output: Path, train_end: int = 34,
          validation_end: int = 39, seed: int = 0) -> dict:
    dataset = pq.ParquetDataset(feature_path)
    if sum(pq.read_metadata(p).num_rows for p in dataset.files) > 300000:
        raise ValueError("training table exceeds bounded original-release size")
    records = dataset.read(columns=["entity_id", "time_step", "label",
                                    "feature_cutoff_exclusive", *FEATURES]).to_pylist()
    # Spark/Parquet partition enumeration is not a reproducible training row order.
    records.sort(key=lambda r: (r["time_step"], r["entity_id"]))
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
        "row_order": "time_step then entity_id (lexicographic)",
        "training_seconds": {},
        "model_configuration": {"prior": {"strategy": "prior"},
                                "logistic_regression": {"class_weight": "balanced", "max_iter": 1000},
                                "random_forest": {"n_estimators": 64, "max_depth": 8,
                                                  "min_samples_leaf": 3, "class_weight": "balanced",
                                                  "fit_jobs": 2, "inference_jobs": 1}},
        "split_counts": {k: {"rows": len(y), "illicit": int(y.sum())}
                         for k, (_, y) in arrays.items()}, "models": {},
    }
    for name, model in models.items():
        began = time.monotonic()
        model.fit(*arrays["train"])
        result["training_seconds"][name] = time.monotonic() - began
        if isinstance(model, RandomForestClassifier):
            # Sequential tree accumulation avoids scheduling-dependent score tie ordering.
            model.n_jobs = 1
        x, y = arrays["validation"]
        score = model.predict_proba(x)[:, list(model.classes_).index(1)]
        result["models"][name] = {"validation": evaluate(y, score)}
        path = output / f"{name}.joblib"
        joblib.dump(model, path)
        restored = joblib.load(path)  # Only the model just written by this process is trusted.
        if not np.allclose(restored.predict_proba(x), model.predict_proba(x), rtol=1e-12, atol=1e-15):
            raise ValueError("model serialization probability round-trip failed")
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
