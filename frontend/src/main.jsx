import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import Chart from "./Chart.jsx";
import {
  loadEvidence,
  PAGES,
  REPO,
  title,
  number,
  decimal,
  metricRows,
  cohortRows,
  graphView,
  positiveLabels,
} from "./data.js";
import "./style.css";

const KEYS = [
  "pr_auc_average_precision",
  "precision",
  "recall",
  "f1",
  "false_positive_rate",
];
const LABELS = ["AP", "Precision", "Recall", "F1", "FPR"];
const names = { elliptic: "Elliptic Bitcoin", banking: "Synthetic banking" };
function Panel({ title: heading, note, children, wide = false }) {
  return (
    <section className={`panel ${wide ? "wide" : ""}`}>
      <div className="panel-heading">
        <h2>{heading}</h2>
        {note && <span className="small muted">{note}</span>}
      </div>
      {children}
    </section>
  );
}
function Metric({ label, value, note }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
      {note && <small>{note}</small>}
    </div>
  );
}
function Table({ headers, rows, caption }) {
  return (
    <div
      className="table-scroll"
      tabIndex={0}
      role="region"
      aria-label={caption ?? `${headers[0]} table`}
    >
      <table>
        {caption && <caption>{caption}</caption>}
        <thead>
          <tr>
            {headers.map((h) => (
              <th key={h} scope="col">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i}>
              {row.map((cell, j) => (
                <td key={j}>{cell}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
function ModelTable({ run }) {
  return (
    <Table
      headers={["Model", "Features", "Validation AP", ...LABELS]}
      rows={metricRows(run).map(([name, f]) => [
        <span>
          {title(name)}{" "}
          {name === run.selected_family && (
            <span className="tag">Selected</span>
          )}
        </span>,
        f.feature_count ?? "Not recorded",
        decimal(f.validation.pr_auc_average_precision),
        ...KEYS.map((k) => decimal(f.test[k])),
      ])}
      caption="Identical within-domain chronological test cohort. Selection uses validation AP."
    />
  );
}
function Overview({ data, run, domain }) {
  const selected = run.families[run.selected_family];
  return (
    <>
      <div className="metrics">
        <Metric
          label={domain === "elliptic" ? "Transactions" : "Accounts"}
          value={number(data.stats.nodes)}
          note={
            domain === "elliptic"
              ? "Real original release"
              : "Independent simulation"
          }
        />
        <Metric
          label={
            domain === "elliptic" ? "Directed links" : "Payment events / seed"
          }
          value={number(data.stats.edges)}
          note="Domain-specific edge semantics"
        />
        <Metric
          label="Known held-out rows"
          value={number(selected.test.rows)}
          note={
            domain === "elliptic"
              ? "Transaction observations"
              : "Account-day forecasts"
          }
        />
        <Metric
          label={
            domain === "elliptic"
              ? "Unknown labels excluded"
              : "Simulation replicas"
          }
          value={
            domain === "elliptic"
              ? number(data.stats.unknown_excluded)
              : "3 fixed seeds"
          }
          note={
            domain === "elliptic"
              ? "Never treated as negatives"
              : "Seeds 0, 1, 2; no test-based selection"
          }
        />
      </div>
      <div className="grid">
        <Panel
          title="Validation-selected model"
          note={title(run.selected_family)}
        >
          <div className="model-name">
            {title(run.selected_family)}
            <span>{selected.candidate}</span>
          </div>
          <div className="score-grid">
            {[0, 3, 2, 4].map((i) => (
              <Metric
                key={i}
                label={LABELS[i]}
                value={decimal(selected.test[KEYS[i]])}
              />
            ))}
          </div>
          <p className="small muted">
            Threshold {selected.test.threshold.toFixed(6)} selected on
            validation data. A 5% validation FPR constraint is not a test
            guarantee.
          </p>
        </Panel>
        <Panel title="Evaluation protocol" note="No random split">
          <div className="timeline">
            {cohortRows(run).map((c) => (
              <div key={c.name}>
                <small>{c.name}</small>
                <b>{c.period}</b>
                <span>{number(c.rows)} rows</span>
              </div>
            ))}
          </div>
          <p className="small">
            {domain === "elliptic"
              ? "Retrospective classification after each source step completes. Publisher-local feature availability is not independently established."
              : "Forecast day t from payments strictly before t. SAR involvement is a simulated target, not confirmed fraud."}
          </p>
        </Panel>
        <Panel
          title="Chronological class balance"
          note="Known supervised labels only"
        >
          <Chart
            label="Chronological positive class prevalence"
            data={[
              {
                type: "bar",
                x: cohortRows(run).map((c) => c.name),
                y: cohortRows(run).map(
                  (s) => (100 * (s.illicit ?? s.sar_positive)) / s.rows,
                ),
                marker: { color: ["#123c47", "#399a9a", "#d5a346"] },
              },
            ]}
            layout={{
              yaxis: { title: { text: "Positive prevalence (%)" } },
              height: 280,
            }}
          />
        </Panel>
        <Panel title="Evidence provenance" note="Versioned and hash-verified">
          <div className="evidence-mark">
            ✓ <span>Curated public research aggregates</span>
          </div>
          <p className="small">
            The dashboard does not acquire datasets, train models, execute
            Python or serve private records.
          </p>
          <a
            className="text-link"
            href={data.evidence.workflow}
            target="_blank"
            rel="noreferrer"
          >
            Original verified experiment ↗
          </a>
          <details>
            <summary>Archive SHA-256</summary>
            <code className="hash">{data.evidence.artifact_sha256}</code>
          </details>
          <p className="small muted">
            AP is average precision, not trapezoidal PR area. Values across
            these domains are not directly comparable.
          </p>
        </Panel>
      </div>
    </>
  );
}
function Graph({ graph, domain }) {
  const [count, setCount] = useState(60),
    [period, setPeriod] = useState(49),
    [focus, setFocus] = useState("All nodes");
  const view = useMemo(
    () => graphView(graph, count, period, focus),
    [graph, count, period, focus],
  );
  const positions = Object.fromEntries(graph.nodes.map((n) => [n.id, n]));
  const x = [],
    y = [];
  view.edges.forEach((e) => {
    x.push(positions[e.source].x, positions[e.target].x, null);
    y.push(positions[e.source].y, positions[e.target].y, null);
  });
  const annotations = view.edges.slice(0, 150).map((e) => ({
    x: positions[e.target].x,
    y: positions[e.target].y,
    ax: 0.6 * positions[e.target].x + 0.4 * positions[e.source].x,
    ay: 0.6 * positions[e.target].y + 0.4 * positions[e.source].y,
    xref: "x",
    yref: "y",
    axref: "x",
    ayref: "y",
    showarrow: true,
    arrowhead: 2,
    arrowsize: 0.8,
    arrowwidth: 1,
    arrowcolor: "#9babab",
    text: "",
  }));
  return (
    <>
      <div className="notice illustrative">
        <b>Illustrative content only.</b> Generated graph, not real Elliptic
        records or an export of the measured banking experiment. Colors show
        groups, never predicted fraud.
      </div>
      <Panel
        title="Directed graph explorer"
        note={`${view.nodes.length} visible nodes · ${view.edges.length} visible events`}
      >
        <div className="controls">
          <label>
            Example nodes: {count}
            <input
              aria-label="Example nodes"
              type="range"
              min="20"
              max="80"
              step="10"
              value={count}
              onChange={(e) => {
                setCount(+e.target.value);
                setFocus("All nodes");
              }}
            />
          </label>
          <label>
            Visible {domain === "elliptic" ? "step" : "simulation day"}:{" "}
            {period}
            <input
              aria-label="Visible period"
              type="range"
              min="1"
              max="49"
              value={period}
              onChange={(e) => setPeriod(+e.target.value)}
            />
          </label>
          <label>
            Focus node
            <select
              aria-label="Focus node"
              value={focus}
              onChange={(e) => setFocus(e.target.value)}
            >
              <option>All nodes</option>
              {graph.nodes.slice(0, count).map((n) => (
                <option key={n.id}>{n.id}</option>
              ))}
            </select>
          </label>
        </div>
        <Chart
          label="Generated directed transaction or account graph"
          data={[
            {
              type: "scatter",
              mode: "lines",
              x,
              y,
              line: { width: 1, color: "#c7d7d5" },
              hoverinfo: "skip",
            },
            {
              type: "scatter",
              mode: "markers",
              x: view.nodes.map((n) => n.x),
              y: view.nodes.map((n) => n.y),
              text: view.nodes.map((n) => n.id),
              customdata: view.nodes.map((n) => n.id),
              hovertemplate: "%{text}<extra>Generated illustration</extra>",
              marker: {
                size: 13,
                color: view.nodes.map((n) => n.group),
                colorscale: "Tealgrn",
                line: { color: "white", width: 1 },
              },
            },
          ]}
          layout={{
            height: 510,
            showlegend: false,
            xaxis: { visible: false },
            yaxis: { visible: false, scaleanchor: "x" },
            annotations,
            dragmode: "pan",
            margin: { l: 20, r: 20, t: 20, b: 20 },
          }}
          onClick={(e) => {
            const id = e.points?.[0]?.customdata;
            if (id) setFocus(id);
          }}
        />
        <p className="small muted">
          Pan, zoom, hover, or click a node to focus. First 150 visible events
          have arrows.{" "}
          {domain === "elliptic"
            ? "Transaction nodes have disconnected step groups; wallet histories cannot be inferred."
            : "Persistent account nodes can have repeated payment events."}{" "}
          No graph mining or model inference runs in the browser.
        </p>
      </Panel>
    </>
  );
}
function Temporal({ run, domain, family, setFamily }) {
  const t = run.temporal,
    x = t.map((p) => p.step ?? p.time_step);
  const series =
    domain === "elliptic"
      ? [
          ["licit", "Known licit"],
          ["illicit", "Known illicit"],
          ["unknown", "Unknown"],
        ]
      : [
          ["events", "All synthetic payments"],
          ["sar_payments", "SAR-flagged payments"],
        ];
  return (
    <>
      <div className="notice">
        Descriptive full-period observations. These plots are not additional
        predictor inputs.
      </div>
      <div className="grid">
        <Panel
          title="Observed temporal populations"
          wide
          note={
            domain === "elliptic"
              ? "49 released steps"
              : "50 UTC simulation days"
          }
        >
          <Chart
            label="Temporal transaction populations"
            data={series.map(([key, label]) => ({
              type: "scatter",
              mode: "lines",
              name: label,
              x,
              y: t.map((p) => p[key]),
            }))}
            layout={{
              xaxis: {
                title: {
                  text:
                    domain === "elliptic" ? "Released step" : "Simulation day",
                },
              },
              yaxis: { title: { text: "Payment / transaction count" } },
            }}
          />
        </Panel>
        {domain === "banking" ? (
          <Panel title="Synthetic payment volume" wide>
            <Chart
              label="Synthetic payment volume over time"
              data={[
                {
                  type: "scatter",
                  mode: "lines",
                  x,
                  y: t.map((p) => p.volume),
                  fill: "tozeroy",
                  line: { color: "#178b8c" },
                  name: "Synthetic volume",
                },
              ]}
              layout={{
                xaxis: { title: { text: "UTC simulation day" } },
                yaxis: { title: { text: "Simulation amount units" } },
              }}
            />
            <p className="small muted">
              SAR payment counts describe events; the model target is
              account-day involvement. They are different populations.
            </p>
          </Panel>
        ) : (
          <Panel title="Held-out performance by step" wide>
            <label className="inline-label">
              Model
              <select
                aria-label="Temporal model"
                value={family}
                onChange={(e) => setFamily(e.target.value)}
              >
                {Object.keys(run.families).map((n) => (
                  <option key={n} value={n}>
                    {title(n)}
                  </option>
                ))}
              </select>
            </label>
            <Chart
              label="Held-out average precision by released step"
              data={[
                {
                  type: "scatter",
                  mode: "lines+markers",
                  x: run.per_step[family].map((p) => p.step),
                  y: run.per_step[family].map((p) => p.average_precision),
                  connectgaps: false,
                  name: "Held-out AP",
                },
              ]}
              layout={{
                xaxis: { title: { text: "Test step" } },
                yaxis: { title: { text: "Average precision" }, range: [0, 1] },
              }}
            />
            <p className="small muted">
              Late-period variation and changing label prevalence are
              associations, not proof of a causal external event.
            </p>
          </Panel>
        )}
        <Panel title="Source-period counts" wide>
          <Table
            headers={["Period", ...series.map((s) => s[1])]}
            rows={t.map((p) => [
              p.step ?? p.time_step,
              ...series.map(([key]) => number(p[key])),
            ])}
          />
        </Panel>
      </div>
    </>
  );
}
function Models({ data, run, domain, family, setFamily }) {
  const item = run.families[family],
    matrix = item.test.confusion_matrix,
    labels = positiveLabels(domain),
    max = Math.max(...matrix.flat());
  const annotations = matrix.flatMap((row, i) =>
    row.map((v, j) => ({
      x: labels[j],
      y: labels[i],
      text: number(v),
      showarrow: false,
      font: { size: 20, color: v > max / 2 ? "white" : "#213b44" },
    })),
  );
  return (
    <>
      <div className="notice">
        Models and operating thresholds use validation data only. Prior research
        has inspected this test cohort; it is not an untouched external lockbox.
      </div>
      <div className="grid">
        <Panel
          title="Model families & ablations"
          wide
          note="Rows ordered by validation AP"
        >
          <ModelTable run={run} />
        </Panel>
        <Panel
          title="Measured precision–recall curves"
          wide
          note="Actual ranking points, sampled to ≤101 per family"
        >
          <Chart
            label="Measured held-out precision recall curves"
            data={Object.entries(run.families)
              .filter(([, f]) => f.test_curve)
              .map(([name, f]) => ({
                type: "scatter",
                mode: "lines",
                name: title(name),
                x: f.test_curve.points.map((p) => p.recall),
                y: f.test_curve.points.map((p) => p.precision),
                line: { width: name === run.selected_family ? 3 : 1.5 },
              }))}
            layout={{
              height: 450,
              xaxis: { title: { text: "Recall" }, range: [0, 1] },
              yaxis: { title: { text: "Precision" }, range: [0, 1] },
              legend: { orientation: "h", y: -0.2 },
            }}
          />
          <p className="small muted">
            Legend clicks hide/isolate curves. Reported AP uses the complete
            score ranking; a curve is never reconstructed from a scalar AP.
          </p>
        </Panel>
        <Panel
          title="Confusion matrix"
          note="Rows observed · columns predicted"
        >
          <label className="inline-label">
            Model
            <select
              aria-label="Evaluation model"
              value={family}
              onChange={(e) => setFamily(e.target.value)}
            >
              {Object.keys(run.families).map((n) => (
                <option key={n} value={n}>
                  {title(n)}
                </option>
              ))}
            </select>
          </label>
          <Chart
            label="Held-out confusion matrix"
            data={[
              {
                type: "heatmap",
                z: matrix,
                x: labels,
                y: labels,
                colorscale: [
                  [0, "#eef6f4"],
                  [1, "#123c47"],
                ],
                showscale: false,
                hovertemplate:
                  "Observed %{y}<br>Predicted %{x}<br>%{z} rows<extra></extra>",
              },
            ]}
            layout={{
              xaxis: { title: { text: "Predicted" }, side: "bottom" },
              yaxis: { title: { text: "Observed" }, autorange: "reversed" },
              annotations,
              margin: { l: 135, r: 15, t: 10, b: 90 },
            }}
          />
          <Table
            headers={["Observed / predicted", ...labels]}
            rows={matrix.map((row, i) => [labels[i], ...row.map(number)])}
          />
        </Panel>
        <Panel title="Operating point & uncertainty" note={title(family)}>
          <div className="score-grid">
            {KEYS.map((k, i) => (
              <Metric key={k} label={LABELS[i]} value={decimal(item.test[k])} />
            ))}
          </div>
          <p className="small">
            Threshold: {item.test.threshold.toFixed(6)} ·{" "}
            {number(item.test.rows)} held-out rows.
          </p>
          <details>
            <summary>Fixed 0.5 scores and paired intervals</summary>
            <pre>
              {JSON.stringify(
                {
                  fixed_0_5: item.test_fixed,
                  exploratory_intervals:
                    run.intervals[family] ?? "Frozen reference",
                },
                null,
                2,
              )}
            </pre>
          </details>
          <p className="small muted">
            500 period-bootstrap draws; only ten test periods and no
            multiple-comparison correction. Intervals are exploratory.{" "}
            {domain === "elliptic"
              ? "No established overall Elliptic AP/F1 improvement is claimed."
              : "Synthetic repetitions and persistent accounts do not establish real-bank efficacy."}
          </p>
        </Panel>
        {domain === "banking" && (
          <Panel
            title="Across three fixed synthetic replicas"
            wide
            note="Arithmetic seed means, not pooled predictions"
          >
            <Table
              headers={["Family", ...LABELS.map((x) => `Mean ${x}`)]}
              rows={Object.entries(data.family_means).map(([n, m]) => [
                title(n),
                ...KEYS.map((k) => decimal(m[k])),
              ])}
            />
            <p className="small muted">
              Combined is validation-selected for all three seeds. Seed
              variation and deliberately learnable simulated motifs prevent
              real-world efficacy claims.
            </p>
          </Panel>
        )}
      </div>
    </>
  );
}
function Scalability({ bench, run, domain }) {
  const c = bench.configuration;
  return (
    <>
      <div className="notice">
        <b>One cloud machine · {c.master}.</b> Generated workloads, single
        cold/warm passes. No distributed multi-worker speedup or real-data
        throughput extrapolation is claimed.
      </div>
      <div className="metrics">
        <Metric label="Measured workloads" value={bench.measurements.length} />
        <Metric label="Spark task slots" value={c.default_parallelism} />
        <Metric label="Driver heap" value={c.driver_memory} />
        <Metric label="Shuffle partitions" value={c.shuffle_partitions} />
      </div>
      <div className="grid">
        {[
          ["bitcoin_generated_fixture", "Generated Bitcoin fixture"],
          ["independent_synthetic_banking", "Independent synthetic banking"],
        ].map(([kind, label]) => {
          const rows = bench.measurements.filter((m) => m.domain === kind);
          return (
            <Panel
              key={kind}
              title={label}
              note="Actual Spark ingestion + validation + graph summaries + Parquet round trip"
            >
              <Chart
                label={`${label} processing benchmark`}
                data={[
                  {
                    type: "scatter",
                    mode: "lines+markers",
                    x: rows.map((r) => r.events),
                    y: rows.map((r) => r.seconds),
                    line: { color: "#178b8c" },
                    name: "Measured seconds",
                  },
                ]}
                layout={{
                  xaxis: {
                    title: { text: "Generated edges / payment events" },
                  },
                  yaxis: { title: { text: "Processing seconds" } },
                }}
              />
            </Panel>
          );
        })}
        <Panel title="Measured configurations & counts" wide>
          <Table
            headers={[
              "Workload",
              "Nodes / accounts",
              "Events / edges",
              "Input bytes",
              "Seconds",
              "Verified output rows",
            ]}
            rows={bench.measurements.map((m) => [
              m.domain === "bitcoin_generated_fixture"
                ? "Bitcoin fixture"
                : "Synthetic banking",
              number(m.nodes),
              number(m.events),
              number(m.input_bytes),
              m.seconds.toFixed(6),
              number(m.output_rows),
            ])}
          />
          <details>
            <summary>Actual execution configuration</summary>
            <pre>{JSON.stringify(c, null, 2)}</pre>
          </details>
          <p className="small muted">
            Source generation and Spark startup excluded. The first Bitcoin pass
            includes cold work and is slower than larger warm passes. One
            repetition per size does not estimate variance, asymptotic scaling,
            memory, shuffle or spill.
          </p>
        </Panel>
        <Panel
          title="Sparse graph prefix timings"
          wide
          note="Single-host CPU mining; separate from the Spark benchmark"
        >
          <Chart
            label="Sparse CPU graph prefix timing"
            data={[
              {
                type: "scatter",
                mode: "lines+markers",
                x: run.benchmarks.map((r) => r.visible_edges ?? r.events),
                y: run.benchmarks.map((r) => r.seconds),
                name: names[domain],
              },
            ]}
            layout={{
              xaxis: { title: { text: "Visible prefix edges / events" } },
              yaxis: { title: { text: "Sparse CPU seconds" } },
            }}
          />
        </Panel>
      </div>
    </>
  );
}
function Research({ assets, domain }) {
  return (
    <>
      <div className="report-actions">
        <a
          className="button"
          href={`${import.meta.env.BASE_URL}data/report.md`}
          download
        >
          Download research report ↓
        </a>
        <a
          className="text-link"
          href={`${REPO}/blob/main/docs/presentation.md`}
          target="_blank"
          rel="noreferrer"
        >
          Presentation script ↗
        </a>
        <a
          className="text-link"
          href={`${REPO}/blob/main/docs/architecture.md`}
          target="_blank"
          rel="noreferrer"
        >
          Architecture diagram ↗
        </a>
      </div>
      <Panel title="Research evaluation" wide>
        <article className="markdown">
          <Markdown
            remarkPlugins={[remarkGfm]}
            skipHtml
            components={{
              table: ({ children }) => (
                <div
                  className="table-scroll"
                  tabIndex={0}
                  role="region"
                  aria-label="Research results table"
                >
                  <table>{children}</table>
                </div>
              ),
            }}
          >
            {assets["report.json"].markdown}
          </Markdown>
        </article>
      </Panel>
      <div className="grid">
        <Panel
          title={
            domain === "elliptic"
              ? "Real Elliptic evaluation"
              : "Independent synthetic banking · seed 0"
          }
          wide
        >
          <img
            className="report-image"
            alt={
              domain === "elliptic"
                ? "Verified Elliptic evaluation plots"
                : "Synthetic banking evaluation plots for seed zero, not a seed mean"
            }
            src={assets[`${domain}-evaluation.png`]}
          />
        </Panel>
        <Panel title="Measured single-machine processing" wide>
          <img
            className="report-image"
            alt="Actual single-machine Spark timings with cold and warm limitations"
            src={assets["spark-processing.png"]}
          />
        </Panel>
      </div>
    </>
  );
}
class Boundary extends React.Component {
  state = { error: null };
  static getDerivedStateFromError(error) {
    return { error };
  }
  render() {
    return this.state.error ? (
      <main className="fatal">
        <h1>Dashboard could not render.</h1>
        <p role="alert">
          No results are substituted. Reload the page or use the verified
          repository report.
        </p>
        <a href={`${REPO}/blob/main/docs/final-research-report.md`}>
          Open research report
        </a>
      </main>
    ) : (
      this.props.children
    );
  }
}
function App() {
  const [assets, setAssets] = useState(null),
    [error, setError] = useState(null);
  const [domain, setDomain] = useState(
    new URLSearchParams(location.search).get("domain") === "banking"
      ? "banking"
      : "elliptic",
  );
  const [seed, setSeed] = useState(
      Number(new URLSearchParams(location.search).get("seed")) || 0,
    ),
    [page, setPage] = useState(location.hash.slice(1) || "overview"),
    [family, setFamily] = useState("");
  useEffect(() => {
    loadEvidence().then(setAssets).catch(setError);
    const hash = () => {
      const value = location.hash.slice(1) || "overview";
      if (PAGES.some(([id]) => id === value)) setPage(value);
    };
    addEventListener("hashchange", hash);
    return () => removeEventListener("hashchange", hash);
  }, []);
  useEffect(() => {
    const query = new URLSearchParams({ domain, seed: String(seed) });
    history.replaceState(null, "", `${location.pathname}?${query}#${page}`);
  }, [domain, seed, page]);
  if (error)
    return (
      <main className="fatal">
        <span className="eyebrow">MMDS · Evidence integrity</span>
        <h1>Verified evidence could not be loaded.</h1>
        <p role="alert">
          {error.message} No metrics or replacement results are displayed.
        </p>
        <a href={`${REPO}/blob/main/docs/final-research-report.md`}>
          Open verified research report ↗
        </a>
      </main>
    );
  if (!assets)
    return (
      <main className="fatal" aria-live="polite">
        <span className="eyebrow">MMDS · Research Observatory</span>
        <h1>Loading verified research evidence…</h1>
        <p>
          Checking public asset fingerprints. No private data or models are
          requested.
        </p>
      </main>
    );
  const data = assets[`${domain}.json`],
    run = data.runs.find((r) => r.seed === seed) ?? data.runs[0],
    current = Object.hasOwn(run.families, family)
      ? family
      : run.selected_family,
    active = PAGES.find((p) => p[0] === page)?.[0] ?? "overview";
  return (
    <div className="shell">
      <a className="skip" href="#main">
        Skip to research content
      </a>
      <aside className="sidebar">
        <a className="brand" href="#overview">
          <img src={`${import.meta.env.BASE_URL}favicon.svg`} alt="" />
          <span>
            MMDS<small>Research Observatory</small>
          </span>
        </a>
        <div className="sidebar-label">RESEARCH WORKSPACE</div>
        <nav aria-label="Dashboard sections">
          {PAGES.map(([id, label], i) => (
            <a
              key={id}
              href={`#${id}`}
              className={active === id ? "active" : ""}
              aria-current={active === id ? "page" : undefined}
            >
              <span className="nav-index">0{i + 1}</span>
              {label}
            </a>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <span className="status-dot" /> Static · no server runtime
          <p>
            Verified aggregates.
            <br />
            Separate scientific targets.
          </p>
          <a href={REPO} target="_blank" rel="noreferrer">
            Source & reproducibility ↗
          </a>
        </div>
      </aside>
      <main id="main">
        <header>
          <div>
            <div className="eyebrow">
              FINANCIAL GRAPH RESEARCH /{" "}
              {PAGES.find((p) => p[0] === active)[1].toUpperCase()}
            </div>
            <h1>{names[domain]}</h1>
            <p className="subtitle">
              {domain === "elliptic"
                ? "Real Bitcoin transaction classification · Original Elliptic release"
                : "Independent banking simulation · Next-day account SAR forecasting"}
            </p>
          </div>
          <div className="selectors">
            <label>
              Research domain
              <select
                aria-label="Research domain"
                value={domain}
                onChange={(e) => {
                  setDomain(e.target.value);
                  setFamily("");
                  setSeed(0);
                }}
              >
                <option value="elliptic">Elliptic Bitcoin</option>
                <option value="banking">Synthetic banking</option>
              </select>
            </label>
            {domain === "banking" && (
              <label>
                Simulation seed
                <select
                  aria-label="Simulation seed"
                  value={run.seed}
                  onChange={(e) => setSeed(+e.target.value)}
                >
                  {data.runs.map((r) => (
                    <option key={r.seed} value={r.seed}>
                      Seed {r.seed}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>
        </header>
        <div className="domain-band">
          <span className={`badge ${domain}`}>
            {domain === "elliptic" ? "REAL DATA" : "INDEPENDENT SYNTHETIC DATA"}
          </span>
          <span>
            {domain === "elliptic"
              ? "Unknown labels are excluded from supervision. Completed-step retrospective evaluation."
              : "Not official IBM AMLSim output. Simulated SAR involvement is not confirmed fraud."}
          </span>
        </div>
        {active === "overview" && (
          <Overview data={data} run={run} domain={domain} />
        )}
        {active === "graph" && (
          <Graph
            key={domain}
            graph={assets["graphs.json"][domain]}
            domain={domain}
          />
        )}
        {active === "temporal" && (
          <Temporal
            run={run}
            domain={domain}
            family={current}
            setFamily={setFamily}
          />
        )}
        {active === "models" && (
          <Models
            data={data}
            run={run}
            domain={domain}
            family={current}
            setFamily={setFamily}
          />
        )}
        {active === "scalability" && (
          <Scalability
            bench={assets["benchmarks.json"]}
            run={run}
            domain={domain}
          />
        )}
        {active === "research" && <Research assets={assets} domain={domain} />}
        <footer>
          <span>MMDS · Reproducible financial research</span>
          <span>
            Build{" "}
            <a href={`${REPO}/commit/${assets.manifest.source_commit}`}>
              {assets.manifest.source_commit.slice(0, 7)}
            </a>
            {assets.manifest.source_dirty ? " · development tree" : ""} ·{" "}
            <a href={`${import.meta.env.BASE_URL}data/manifest.json`}>
              Evidence manifest
            </a>
          </span>
          <small>
            Targets remain separate; cross-domain scores are not directly
            comparable. No Python, Spark or model inference runs in your
            browser.
          </small>
        </footer>
      </main>
    </div>
  );
}
createRoot(document.getElementById("root")).render(
  <Boundary>
    <App />
  </Boundary>,
);
