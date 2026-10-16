"""Reproduce report PNGs from aggregate evidence; run in the full cloud environment."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from mmd_fraud.evidence import load, load_benchmarks  # noqa: E402


def render(output=None):
    output = Path(output) if output else ROOT / "docs/figures"
    output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.size": 9})
    for domain in ["elliptic", "banking"]:
        data = load(domain)
        run = data["runs"][0]
        fig, ax = plt.subplots(2, 2, figsize=(12, 8.5), layout="constrained")
        names = list(run["families"])
        ax[0, 0].barh(
            names,
            [run["families"][n]["test"]["pr_auc_average_precision"] for n in names],
            color="#167e86",
        )
        ax[0, 0].set_xlabel("Held-out average precision")
        ax[0, 0].set_xlim(0, 1)
        for name, item in run["families"].items():
            pts = item.get("test_curve", {}).get("points", [])
            if pts:
                ax[0, 1].plot(
                    [p["recall"] for p in pts],
                    [p["precision"] for p in pts],
                    label=name,
                    linewidth=1,
                )
        ax[0, 1].set(xlabel="Recall", ylabel="Precision", xlim=(0, 1), ylim=(0, 1))
        ax[0, 1].legend(fontsize=6, loc="lower left")
        selected = run["selected_family"]
        matrix = run["families"][selected]["test"]["confusion_matrix"]
        ax[1, 0].imshow(matrix, cmap="Blues")
        for i in range(2):
            for j in range(2):
                ax[1, 0].text(
                    j,
                    i,
                    f"{matrix[i][j]:,}",
                    ha="center",
                    va="center",
                    color="white" if matrix[i][j] > max(map(max, matrix)) / 2 else "black",
                    fontsize=12,
                )
        ax[1, 0].set(
            xticks=[0, 1],
            yticks=[0, 1],
            xlabel="Predicted",
            ylabel="Observed",
            title=f"Validation winner: {selected}",
        )
        temporal = run["temporal"]
        if domain == "elliptic":
            ax[1, 1].plot(
                [r["step"] for r in temporal],
                [r["rows"] for r in temporal],
                label="All transactions",
            )
            ax[1, 1].plot(
                [r["step"] for r in temporal],
                [r["illicit"] for r in temporal],
                label="Known illicit",
            )
            ax[1, 1].set_xlabel("Released Elliptic step")
        else:
            ax[1, 1].plot(
                [r["time_step"] for r in temporal],
                [r["events"] for r in temporal],
                label="Synthetic payments",
            )
            ax[1, 1].plot(
                [r["time_step"] for r in temporal],
                [r["sar_payments"] for r in temporal],
                label="Simulated SAR payments",
            )
            ax[1, 1].set_xlabel("UTC simulation day")
        ax[1, 1].set_ylabel("Count")
        ax[1, 1].legend(fontsize=8)
        title = (
            "Real Elliptic • known-label held-out transactions"
            if domain == "elliptic"
            else "Independent synthetic banking • seed 0 • SAR is not confirmed fraud"
        )
        fig.suptitle(title)
        fig.savefig(output / f"{domain}-evaluation.png", dpi=170)
        plt.close(fig)
    bench = load_benchmarks()
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5), layout="constrained")
    for ax, domain in zip(axes, ["bitcoin_generated_fixture", "independent_synthetic_banking"]):
        rows = [r for r in bench["measurements"] if r["domain"] == domain]
        ax.plot([r["events"] for r in rows], [r["seconds"] for r in rows], "o-", color="#167e86")
        ax.set(
            xlabel="Generated events/edges",
            ylabel="Processing seconds",
            title=domain.replace("_", " "),
        )
        ax.grid(alpha=0.2)
    fig.suptitle(
        "One machine • Spark local[2] • 1 GB heap • 2 shuffle partitions • cold/warm single passes"
    )
    fig.savefig(output / "spark-processing.png", dpi=170)
    plt.close(fig)


if __name__ == "__main__":
    render()
