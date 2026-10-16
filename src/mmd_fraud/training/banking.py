"""Banking anomaly baseline and aggregate-only research reporting."""

import json
from pathlib import Path
import time

import joblib
import numpy as np
import pyarrow.parquet as pq
from scipy.special import expit
from sklearn.ensemble import IsolationForest
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

from .baselines import evaluate
from .comparison import validation_threshold
from mmd_fraud.spark.banking_research import FAMILIES


def anomaly(feature_path: Path, output: Path):
    table = pq.read_table(feature_path).sort_by(
        [("time_step", "ascending"), ("entity_id", "ascending")]
    )
    days = table["time_step"].to_numpy()
    names = FAMILIES["combined"]
    x = np.column_stack([table[c].to_numpy() for c in names])
    y = np.array([int(v == "1") for v in table["label"].to_pylist()])
    train, val, test = days <= 34, (days >= 35) & (days <= 39), days >= 40
    model = make_pipeline(
        StandardScaler(),
        IsolationForest(
            n_estimators=128, max_samples=256, contamination="auto", n_jobs=2, random_state=0
        ),
    )
    began = time.monotonic()
    with threadpool_limits(2):
        model.fit(x[train])  # all training rows
        # No label-dependent fitting or test calibration.
        score = expit(-model.decision_function(x[val]))
        threshold = validation_threshold(y[val], score)
        test_score = expit(-model.decision_function(x[test]))
    joblib.dump(model, output / "isolation_forest.joblib")
    restored = joblib.load(output / "isolation_forest.joblib")
    np.testing.assert_allclose(expit(-restored.decision_function(x[test])), test_score)
    result = {
        "fit_seconds": time.monotonic() - began,
        "threshold": threshold,
        "validation": evaluate(y[val], score, threshold),
        "test": evaluate(y[test], test_score, threshold),
        "test_fixed": evaluate(y[test], test_score),
        "policy": "unsupervised fit on training rows; sigmoid(-decision_function) is a ranking score, not calibrated risk",
    }
    (output / "anomaly.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def sar_vocabulary(value):
    """Translate shared backend class names without relabeling the real Elliptic reference."""
    if isinstance(value, dict):
        return {
            ("sar_positive" if k == "illicit" else k): sar_vocabulary(v) for k, v in value.items()
        }
    if isinstance(value, list):
        return [sar_vocabulary(v) for v in value]
    if value == "licit=0":
        return "no_simulated_sar_involvement=0"
    if value == "illicit=1":
        return "simulated_sar_involvement=1"
    return value


def report(runs, reference, public: Path):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    runs = sar_vocabulary(runs)
    public.mkdir()
    kind = runs[0]["provenance"]["dataset_kind"]
    title = (
        "independently generated synthetic"
        if kind == "independent_synthetic_banking"
        else "external AMLSim-compatible (origin unverified)"
    )
    summary = {
        "dataset_kind": kind,
        "official_amlsim_output": runs[0]["provenance"]["official_amlsim_output"],
        "real_banking_fraud_verified": False,
        "runs": runs,
        "elliptic_reference": reference,
        "task": "next-day account SAR involvement from strictly earlier transactions",
        "split_days": {"train": [1, 34], "validation": [35, 39], "test": [40, 49]},
    }
    lines = [
        f"# Phase 5: {title} banking evaluation",
        "",
        "**Official AMLSim provenance and real banking fraud detection are not verified.**",
        "",
        "AMLSim-compatible converted columns; target is next-day account involvement in a simulated",
        "SAR transaction. All predictors use days < target day. Account registry is known at day zero.",
        "Repeated directed events preserve multiplicity. Labels, alert IDs, account IDs and type IDs are excluded.",
        "Train days 1–34; validation 35–39; test 40–49. Same account population across periods:",
        "this evaluates future behavior of known accounts, not generalization to unseen accounts.",
        "SAR is an artificial suspicious-activity label, not proof of money laundering or fraud.",
        "",
        "| Seed | Family | Validation AP | Test AP | Precision | Recall | F1 | FPR |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for run in runs:
        comparison = run["comparison"]
        for name, item in comparison["families"].items():
            lines.append(
                f"| {run['seed']} | {name} | {item['validation']['pr_auc_average_precision']:.6f} | "
                + " | ".join(
                    f"{item['test'][c]:.6f}"
                    for c in (
                        "pr_auc_average_precision",
                        "precision",
                        "recall",
                        "f1",
                        "false_positive_rate",
                    )
                )
                + " |"
            )
        item = run["anomaly"]
        lines.append(
            f"| {run['seed']} | isolation_forest | {item['validation']['pr_auc_average_precision']:.6f} | "
            + " | ".join(
                f"{item['test'][c]:.6f}"
                for c in (
                    "pr_auc_average_precision",
                    "precision",
                    "recall",
                    "f1",
                    "false_positive_rate",
                )
            )
            + " |"
        )
    lines += [
        "",
        "Each family uses the existing five fixed candidates, seed zero, validation AP selection and",
        "validation-F1 threshold under 5% validation FPR. Test FPR can exceed the cap. Dataset seeds are",
        "predeclared replicates, never selected by test score. Isolation Forest is fitted without labels;",
        "validation labels select its operating threshold. Its sigmoid score is not a calibrated probability.",
        "",
        "## Paired uncertainty and scalability",
        "",
        "Each comparison includes 500 paired target-day bootstrap draws on the same held-out account-days.",
        "Ten day blocks and overlapping history windows limit independence; intervals are exploratory,",
        "uncorrected for multiple comparisons and cannot establish real-world improvement.",
        "",
        "| Seed | Selected family | AP delta 95% CI vs transaction-only | Mining seconds |",
        "| --- | --- | --- | ---: |",
    ]
    for run in runs:
        family = run["comparison"]["selected_family"]
        interval = run["paired_intervals"].get(family, {}).get("pr_auc_average_precision")
        text = (
            f"[{interval['lower_95']:.6f}, {interval['upper_95']:.6f}]"
            if interval
            else "baseline selected"
        )
        lines.append(
            f"| {run['seed']} | {family} | {text} | {sum(b['seconds'] for b in run['graph_benchmarks']):.3f} |"
        )
    lines += [
        "",
        "Full 49-prefix graph timings (events versus unique pairs), account/day/label populations,",
        "Spark stage timings, model fit times, candidate warnings and source hashes are in banking-summary.json.",
        "These are within-run observational scalability measurements, not production throughput estimates.",
        "",
        "## Comparison with real Bitcoin Elliptic",
        "",
        "| Property | Banking study | Elliptic Phase 4 reference |",
        "| --- | --- | --- |",
        f"| Provenance | {title} | Real original Elliptic release |",
        "| Nodes | Persistent bank accounts | Individual Bitcoin transactions |",
        "| Edges | Repeated, amount-bearing payments | Simple directed transaction links |",
        "| Target | Next-day simulated account SAR involvement | Known illicit transaction class |",
        "| Time | UTC simulation days; strict start-of-day history | Released steps; completed-step offline graph |",
        "| Unknown labels | None in independent generator | 157,205 excluded from supervision |",
        "| Cross-time history | Repeated accounts/payments | No cross-step edges |",
        "",
        f"Preserved real Elliptic transaction baseline AP **{reference['baseline']['pr_auc_average_precision']:.6f}**, "
        f"F1 **{reference['baseline']['f1']:.6f}**, recall **{reference['baseline']['recall']:.6f}**, "
        f"FPR **{reference['baseline']['false_positive_rate']:.6f}** ([source PR #12]({reference['url']})).",
        "",
        "These domains have different units, targets, label mechanisms and splits. Their scores are",
        "descriptive comparisons, not a cross-domain ranking, transfer experiment or claim that synthetic",
        "banking performance predicts real bank performance. Existing Elliptic code/results are preserved.",
        "",
        "![Synthetic banking held-out results](banking-results.png)",
        "",
        "Private data, model files and per-row scores are not published. Retained private workspaces can",
        "resume hash-verified stages/trials; standard hosted jobs delete the private workspace afterward.",
    ]
    (public / "banking-report.md").write_text("\n".join(lines) + "\n")
    (public / "banking-summary.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False) + "\n"
    )
    fig, axes = plt.subplots(2, 2, figsize=(11, 8), layout="constrained")
    names = [*FAMILIES, "isolation_forest"]
    for ax, metric in zip(
        axes.flat, ("pr_auc_average_precision", "f1", "recall", "false_positive_rate")
    ):
        values = np.array(
            [
                [
                    r["anomaly"]["test"][metric]
                    if name == "isolation_forest"
                    else r["comparison"]["families"][name]["test"][metric]
                    for name in names
                ]
                for r in runs
            ]
        )
        means = values.mean(axis=0)
        ax.barh(
            names,
            means,
            xerr=np.maximum(np.array([means - values.min(axis=0), values.max(axis=0) - means]), 0),
            color="#367d72",
        )
        ax.set_title(metric.replace("_", " "))
        ax.set_xlim(left=0)
        ax.grid(axis="x", alpha=0.2)
    fig.suptitle(f"{title.capitalize()} banking • held-out days 40–49 • seed mean/range")
    fig.savefig(public / "banking-results.png", dpi=170)
    plt.close(fig)
