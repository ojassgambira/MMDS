"""Clearly illustrative content when bundled public evidence is missing."""


def show_sample(domain):
    import streamlit as st
    from .dashboard_graph import example, figure

    st.warning(
        "Illustrative mode: verified aggregate files are missing. "
        "No experimental metrics, fraud labels or measured results are substituted."
    )
    st.subheader("Illustrative graph — no experiment results")
    st.caption(
        "Generated example only; this is neither real Elliptic data nor an export "
        "of the measured banking experiment. Groups are not fraud predictions."
    )
    count = st.slider("Illustrative node count", 20, 100, 40, 10)
    nodes, edges = example(domain, count)
    day = st.slider("Illustrative visible period", 1, 49, 49)
    chart, events = figure(nodes, edges, day)
    st.plotly_chart(chart, use_container_width=True)
    st.caption(f"Generated illustration: {count} nodes; {events} visible directed events.")
    st.info(
        "Normal research pages use the versioned dashboard/data snapshots; private "
        "datasets and model files are never required. Restore the public snapshots "
        "from the reviewed repository to display verified results. No downloads or training run here."
    )
