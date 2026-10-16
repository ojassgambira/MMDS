"""Generated illustrative graphs only. Never presented as real Elliptic transactions."""

import math
import numpy as np
import plotly.graph_objects as go


def example(domain, count=60):
    if domain not in ("elliptic", "banking") or not 20 <= count <= 150:
        raise ValueError("bounded example graph required")
    rng = np.random.default_rng(42)
    prefix = "TX" if domain == "elliptic" else "ACCOUNT"
    nodes = [
        {
            "id": f"{prefix}-{i:03}",
            "group": i // 10,
            "step": (1 + (i // 10) * 48 // max(1, (count - 1) // 10))
            if domain == "elliptic"
            else 0,
        }
        for i in range(count)
    ]
    edges = []
    for i in range(count):
        if domain == "elliptic":
            if i % 10 != 9 and i + 1 < count:
                edges.append(
                    {
                        "source": nodes[i]["id"],
                        "target": nodes[i + 1]["id"],
                        "step": nodes[i]["step"],
                    }
                )
        else:
            for _ in range(3):
                target = int(rng.integers(count))
                if target != i:
                    edges.append(
                        {
                            "source": nodes[i]["id"],
                            "target": nodes[target]["id"],
                            "step": int(rng.integers(1, 50)),
                        }
                    )
    return nodes, edges


def figure(nodes, edges, day=49, focus="All nodes", arrows=True):
    nodes = [n for n in nodes if n["step"] <= day]
    ids = {n["id"] for n in nodes}
    visible = [e for e in edges if e["step"] <= day and e["source"] in ids and e["target"] in ids]
    if focus != "All nodes":
        visible = [e for e in visible if focus in (e["source"], e["target"])]
        ids = {focus} | {e[k] for e in visible for k in ("source", "target")}
        nodes = [n for n in nodes if n["id"] in ids]
    positions = {
        n["id"]: (math.cos(i * 2 * math.pi / len(nodes)), math.sin(i * 2 * math.pi / len(nodes)))
        for i, n in enumerate(nodes)
    }
    x, y, annotations = [], [], []
    for e in visible:
        a, b = positions[e["source"]], positions[e["target"]]
        x.extend([a[0], b[0], None])
        y.extend([a[1], b[1], None])
        if arrows and len(annotations) < 150:
            annotations.append(
                dict(
                    x=b[0],
                    y=b[1],
                    ax=0.65 * b[0] + 0.35 * a[0],
                    ay=0.65 * b[1] + 0.35 * a[1],
                    xref="x",
                    yref="y",
                    axref="x",
                    ayref="y",
                    showarrow=True,
                    arrowhead=2,
                    arrowsize=1,
                    arrowwidth=1,
                    arrowcolor="#64748b",
                    text="",
                )
            )
    fig = go.Figure(
        go.Scatter(x=x, y=y, mode="lines", line=dict(color="#b6c3ce", width=1), hoverinfo="skip")
    )
    fig.add_trace(
        go.Scatter(
            x=[positions[n["id"]][0] for n in nodes],
            y=[positions[n["id"]][1] for n in nodes],
            mode="markers",
            marker=dict(
                size=12,
                color=[n["group"] for n in nodes],
                colorscale="Tealgrn",
                line=dict(width=1, color="white"),
            ),
            text=[n["id"] for n in nodes],
            hovertemplate="%{text}<extra>Generated example</extra>",
        )
    )
    fig.update_layout(
        height=530,
        showlegend=False,
        annotations=annotations,
        dragmode="pan",
        margin=dict(l=10, r=10, t=10, b=10),
        paper_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(visible=False),
        yaxis=dict(visible=False, scaleanchor="x"),
    )
    return fig, len(visible)


def private_graph(directory, domain):
    """Optional operator-provisioned cloud subgraph. No network or file upload endpoint."""
    import csv
    import hashlib
    import json
    from pathlib import Path
    from .evidence import ROOT

    directory = Path(directory).resolve()
    if directory.is_relative_to(ROOT) or domain not in ("elliptic", "banking"):
        raise ValueError("private graph must be outside the checkout and domain-tagged")
    manifest = json.loads((directory / "graph.json").read_text())
    expected = (
        "original_elliptic_release" if domain == "elliptic" else "independent_synthetic_banking"
    )
    if manifest["domain"] != domain or manifest["dataset_kind"] != expected:
        raise ValueError("private graph provenance/domain mismatch")
    for name in ("nodes.csv", "edges.csv"):
        path = directory / name
        if path.is_symlink() or path.stat().st_size > 2_000_000:
            raise ValueError("private graph byte limit exceeded")
        if hashlib.sha256(path.read_bytes()).hexdigest() != manifest["sha256"][name]:
            raise ValueError("private graph hash mismatch")
    with (directory / "nodes.csv").open(newline="") as f:
        nodes = [
            dict(id=r["id"], group=int(r.get("group", 0)), step=int(r["step"]))
            for r in csv.DictReader(f)
        ]
    with (directory / "edges.csv").open(newline="") as f:
        edges = [
            dict(source=r["source"], target=r["target"], step=int(r["step"]))
            for r in csv.DictReader(f)
        ]
    ids = {n["id"] for n in nodes}
    if not 0 < len(nodes) <= 150 or len(ids) != len(nodes) or len(edges) > 500:
        raise ValueError("private graph node/edge limit exceeded")
    if any(not n["id"] or not 0 <= n["step"] <= 49 for n in nodes):
        raise ValueError("invalid private graph node/time")
    if any(
        e["source"] not in ids or e["target"] not in ids or not 0 <= e["step"] <= 49 for e in edges
    ):
        raise ValueError("invalid private graph endpoint/time")
    return nodes, edges
