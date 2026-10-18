"""Bounded aggregate PR points. No transaction IDs, prediction scores or thresholds."""

import numpy as np
from sklearn.metrics import precision_recall_curve
from .baselines import evaluate


def pr_curve(y, score, limit=101):
    evaluate(y, score)
    precision, recall, _ = precision_recall_curve(y, score)
    idx = np.unique(np.linspace(0, len(precision) - 1, min(limit, len(precision))).astype(int))
    return {
        "method": "sampled sklearn precision_recall_curve; AP uses full ranking",
        "rows": len(y),
        "positive": int(np.asarray(y).sum()),
        "points": [{"recall": float(recall[i]), "precision": float(precision[i])} for i in idx],
    }
