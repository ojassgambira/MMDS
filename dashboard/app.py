"""Read-only MMDS research dashboard. No acquisition, training or arbitrary code loading."""

# ruff: noqa: E402 -- Community Cloud loads repository src without installing Spark extras.
from pathlib import Path
import os
import sys
import logging
import platform

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from mmd_fraud.evidence import load, load_benchmarks
from mmd_fraud.dashboard_graph import example, figure, private_graph

st.set_page_config(page_title="MMDS • Financial Graph Research", page_icon="◈", layout="wide")
st.markdown("## MMDS · Financial Graph Research")
st.caption("Reproducible evidence across two distinct financial graph domains")
choice = st.sidebar.selectbox("Research domain", ["Elliptic Bitcoin", "Synthetic banking"])
domain = "elliptic" if choice == "Elliptic Bitcoin" else "banking"
with st.sidebar.expander("Runtime diagnostics"):
    st.caption(f"Python {platform.python_version()} · Streamlit {st.__version__}")
    st.caption("UI-only runtime · no dataset credentials or private models required")
try:
    evidence = load(domain)
except FileNotFoundError:
    logging.getLogger("mmds.dashboard").exception("Bundled dashboard evidence missing")
    from mmd_fraud.dashboard_sample import show_sample

    show_sample(domain)
    st.stop()
except (ValueError, OSError, KeyError, TypeError) as exc:
    logging.getLogger("mmds.dashboard").exception("Bundled dashboard evidence rejected")
    st.error(f"Evidence unavailable or invalid: {type(exc).__name__}. No metrics are substituted.")
    st.stop()
run_index = (
    st.sidebar.selectbox("Simulation seed", list(range(len(evidence["runs"]))))
    if domain == "banking"
    else 0
)
run = evidence["runs"][run_index]
page = st.sidebar.radio(
    "Workspace",
    [
        "Overview",
        "Transaction graph",
        "Temporal patterns",
        "Models & PR curves",
        "Scalability",
        "Research report",
    ],
)
st.sidebar.markdown("**Evidence boundary**")
st.sidebar.caption(
    "Real transaction classification"
    if domain == "elliptic"
    else "Independent synthetic account SAR forecasting · not official AMLSim or real fraud"
)
st.sidebar.link_button("Verified source workflow", evidence["evidence"]["workflow"])
if domain == "elliptic":
    st.info(
        "Real original Elliptic release · completed-step offline transaction classification. Unknown labels are excluded from supervised evaluation."
    )
else:
    st.info(
        "Independently generated synthetic banking data · next-day account SAR involvement. SAR is not confirmed fraud. Registry known at day zero."
    )

families = run["families"]
selected = run["selected_family"]
metrics = families[selected]["test"]
if page == "Overview":
    a, b, c, d = st.columns(4)
    a.metric(
        "Transactions" if domain == "elliptic" else "Accounts", f"{evidence['stats']['nodes']:,}"
    )
    b.metric(
        "Directed links" if domain == "elliptic" else "Payment events",
        f"{evidence['stats']['edges']:,}",
    )
    c.metric("Held-out rows", f"{metrics['rows']:,}")
    d.metric("Unknown excluded", f"{evidence['stats']['unknown_excluded']:,}")
    st.subheader("Validation-selected model")
    st.write(f"**{selected}** · {families[selected]['candidate']}")
    cols = st.columns(4)
    for col, name, key in zip(
        cols,
        ["PR-AUC (AP)", "F1", "Recall", "False-positive rate"],
        ["pr_auc_average_precision", "f1", "recall", "false_positive_rate"],
    ):
        col.metric(name, f"{metrics[key]:.4f}")
    st.caption(
        "Selection and operating thresholds use validation data. Scores from these domains are not directly comparable."
    )
    counts = pd.DataFrame(run["split_counts"]).T.reset_index(names="Period")
    st.dataframe(counts, hide_index=True, width="stretch")
    if domain == "elliptic":
        labels = pd.DataFrame(
            [{"Label": k, "Rows": v} for k, v in evidence["stats"]["labels"].items()]
        )
        st.plotly_chart(
            px.bar(
                labels,
                x="Label",
                y="Rows",
                color="Label",
                title="Source labels: 1 illicit · 2 licit · unknown",
            ),
            use_container_width=True,
        )
    else:
        st.caption(
            f"Seed {run['seed']} of three fixed replicas · {evidence['stats']['account_days']:,} account-day forecasts. All labels are synthetic SAR indicators."
        )
    with st.expander("Evidence provenance"):
        st.json(evidence["evidence"])
elif page == "Transaction graph":
    st.subheader("Interactive directed graph explorer")
    st.warning(
        "Default view: generated illustrative graph only. It is not a real Elliptic subgraph or an export of the measured banking experiment. Node colors indicate example groups, not predicted fraud."
    )
    graph_root = os.environ.get("MMDS_GRAPH_DIRECTORY")
    if graph_root:
        try:
            nodes, edges = private_graph(Path(graph_root) / domain, domain)
            count = len(nodes)
            st.caption(
                "Operator-provisioned cloud subgraph; provenance is asserted by its manifest, not independently authenticated. Identifiers are visible to this app's viewers."
            )
        except (ValueError, OSError, KeyError):
            st.error("Private graph configuration is invalid; no replacement graph is shown.")
            st.stop()
    else:
        count = st.slider("Example node count", 20, 100, 60, 10)
        nodes, edges = example(domain, count)
    day = st.slider("Visible step" if domain == "elliptic" else "Visible simulation day", 1, 49, 49)
    focus = st.selectbox("Focus node", ["All nodes", *[n["id"] for n in nodes]])
    arrows = st.checkbox("Show flow arrows (first 150 visible events)", True)
    provenance = "Operator-provisioned; source unverified" if graph_root else "Generated example"
    graph, edge_count = figure(nodes, edges, day, focus, arrows, provenance)
    st.plotly_chart(graph, use_container_width=True, config={"scrollZoom": True})
    st.caption(
        f"{count} {'operator-provisioned' if graph_root else 'generated'} nodes before focus · {edge_count} visible directed events. Pan, zoom, hover and focus a node. Banking events can repeat; Bitcoin nodes represent transactions."
    )
elif page == "Temporal patterns":
    st.subheader("Temporal observations")
    st.caption(
        "Descriptive full-period aggregates are not predictor inputs. Elliptic uses released steps; banking uses UTC simulation days."
    )
    temporal = run["temporal"]
    if temporal:
        df = pd.DataFrame(temporal)
        x = "step" if domain == "elliptic" else "time_step"
        y = ["licit", "illicit", "unknown"] if domain == "elliptic" else ["events", "sar_payments"]
        st.plotly_chart(
            px.line(df, x=x, y=y, markers=True, title="Observed period populations"),
            use_container_width=True,
        )
        if domain == "banking":
            st.plotly_chart(
                px.area(df, x=x, y="volume", title="Synthetic payment volume"),
                use_container_width=True,
            )
        st.dataframe(df, hide_index=True, width="stretch")
    else:
        st.warning(
            "This historical artifact does not contain temporal payment aggregates. No pattern is invented."
        )
    if domain == "elliptic":
        family = st.selectbox(
            "Per-step model", list(families), index=list(families).index(selected)
        )
        st.plotly_chart(
            px.line(
                pd.DataFrame(run["per_step"][family]),
                x="step",
                y="average_precision",
                markers=True,
                title="Held-out AP by released step",
            ),
            use_container_width=True,
        )
elif page == "Models & PR curves":
    st.subheader("Chronological model evaluation")
    rows = []
    for name, item in families.items():
        rows.append(
            {
                "Family": name,
                "Candidate": item["candidate"],
                "Validation AP": item["validation"]["pr_auc_average_precision"],
                "Test AP": item["test"]["pr_auc_average_precision"],
                "Precision": item["test"]["precision"],
                "Recall": item["test"]["recall"],
                "F1": item["test"]["f1"],
                "FPR": item["test"]["false_positive_rate"],
            }
        )
    frame = pd.DataFrame(rows)
    st.dataframe(frame, hide_index=True, width="stretch")
    st.plotly_chart(
        px.bar(frame, x="Family", y=["Test AP", "F1", "Recall"], barmode="group"),
        use_container_width=True,
    )
    family = st.selectbox(
        "Confusion matrix model", list(families), index=list(families).index(selected)
    )
    item = families[family]
    labels = (
        ["Licit", "Illicit"]
        if domain == "elliptic"
        else ["No simulated SAR", "Simulated SAR involvement"]
    )
    st.plotly_chart(
        px.imshow(
            item["test"]["confusion_matrix"],
            x=labels,
            y=labels,
            text_auto=True,
            color_continuous_scale="Teal",
            labels={"x": "Predicted", "y": "Observed"},
            title="Held-out confusion matrix",
        ),
        use_container_width=True,
    )
    st.caption(
        f"Operating threshold {item['test']['threshold']:.8f}, chosen on validation. The 5% validation FPR cap is not a test guarantee."
    )
    curve = go.Figure()
    for name, value in families.items():
        points = value.get("test_curve", {}).get("points", [])
        if points:
            curve.add_trace(
                go.Scatter(
                    x=[p["recall"] for p in points],
                    y=[p["precision"] for p in points],
                    mode="lines",
                    name=name,
                )
            )
    if curve.data:
        curve.update_layout(
            xaxis_title="Recall",
            yaxis_title="Precision",
            xaxis_range=[0, 1],
            yaxis_range=[0, 1],
            title="Held-out PR curves · sampled aggregate points",
        )
        st.plotly_chart(curve, use_container_width=True)
        st.caption(
            "Curves sample actual sklearn PR points; reported AP uses the full ranking. Curves are never reconstructed from AP."
        )
    else:
        st.warning(
            "This historical evidence has no measured PR curve points. They will appear after the current evidence workflow is imported."
        )
    with st.expander("Fixed-0.5 scores and exploratory paired intervals"):
        st.json(
            {
                "fixed_threshold": item.get("test_fixed"),
                "paired_intervals": run.get("intervals", {}).get(family),
            }
        )
elif page == "Scalability":
    st.subheader("Measured execution and scalability")
    st.warning(
        "PySpark benchmarks below use generated fixtures on one cloud machine, local[2]. No distributed multi-worker scaling or real-data throughput extrapolation is claimed."
    )
    path = ROOT / "dashboard/data/spark-benchmarks.json"
    if path.exists():
        bench = load_benchmarks()
        st.json(bench["configuration"], expanded=False)
        df = pd.DataFrame(bench["measurements"])
        st.plotly_chart(
            px.line(
                df,
                x="events",
                y="seconds",
                color="domain",
                markers=True,
                hover_data=["nodes", "input_bytes"],
                title="Spark ingestion + validation + account/transaction graph summaries",
            ),
            use_container_width=True,
        )
        st.dataframe(df, hide_index=True, width="stretch")
    else:
        st.info("No Spark benchmark measurements bundled yet.")
    st.caption(
        "Prefix graph mining below is sparse CPU work, not Spark execution or a worker-count scaling test."
    )
    b = pd.DataFrame(run["benchmarks"])
    x = "visible_edges" if domain == "elliptic" else "events"
    st.plotly_chart(
        px.line(b, x=x, y="seconds", markers=True, title="Sparse graph prefix timings"),
        use_container_width=True,
    )
else:
    st.subheader("Research methodology and conclusions")
    report = ROOT / "docs/final-research-report.md"
    text = report.read_text() if report.exists() else "Research report is being prepared."
    from mmd_fraud.report_links import hosted_report

    st.markdown(hosted_report(text, report, ROOT))
    for name in [f"{domain}-evaluation.png", "spark-processing.png"]:
        figure = ROOT / "docs/figures" / name
        if figure.exists():
            st.image(str(figure))
    st.download_button(
        "Download final research report",
        report.read_text() if report.exists() else "",
        file_name="MMDS-final-research-report.md",
        mime="text/markdown",
    )
    st.caption(
        "Source metrics remain versioned and hash-verified. No raw datasets, models, or prediction arrays are included in this dashboard."
    )
