export const FILES = [
  "elliptic.json",
  "banking.json",
  "benchmarks.json",
  "graphs.json",
  "report.json",
  "report.md",
  "elliptic-evaluation.png",
  "banking-evaluation.png",
  "spark-processing.png",
];
export const REPO = "https://github.com/ojassgambira/MMDS";
export const PAGES = [
  ["overview", "Overview"],
  ["graph", "Graph explorer"],
  ["temporal", "Temporal analytics"],
  ["models", "Models & evaluation"],
  ["scalability", "Spark benchmarks"],
  ["research", "Research report"],
];
export function title(name) {
  return name.replaceAll("_", " ").replace(/^./, (c) => c.toUpperCase());
}
export function number(value) {
  return new Intl.NumberFormat("en-US").format(value);
}
export function decimal(value) {
  return value.toFixed(4);
}
export function metricRows(run) {
  return Object.entries(run.families).sort(
    (a, b) =>
      b[1].validation.pr_auc_average_precision -
      a[1].validation.pr_auc_average_precision,
  );
}
export function graphView(graph, count, period, focus) {
  const nodes = graph.nodes.slice(0, count).filter((n) => n.step <= period);
  const ids = new Set(nodes.map((n) => n.id));
  const edges = graph.edges.filter(
    (e) =>
      e.step <= period &&
      ids.has(e.source) &&
      ids.has(e.target) &&
      (focus === "All nodes" || [e.source, e.target].includes(focus)),
  );
  const visible = new Set(edges.flatMap((e) => [e.source, e.target]));
  return {
    nodes: nodes.filter(
      (n) => focus === "All nodes" || visible.has(n.id) || n.id === focus,
    ),
    edges,
  };
}
export function positiveLabels(domain) {
  return domain === "elliptic"
    ? ["Known licit", "Known illicit"]
    : ["No simulated SAR", "Simulated SAR"];
}
export async function loadEvidence(
  base = import.meta.env.BASE_URL,
  fetcher = fetch,
) {
  const response = await fetcher(`${base}data/manifest.json`);
  if (!response.ok)
    throw new Error("The public evidence manifest could not be loaded.");
  const manifest = await response.json();
  if (
    manifest.schema_version !== 1 ||
    JSON.stringify(Object.keys(manifest.files).sort()) !==
      JSON.stringify([...FILES].sort())
  )
    throw new Error("Unexpected public evidence manifest.");
  const entries = await Promise.all(
    FILES.map(async (name) => {
      const response = await fetcher(`${base}data/${name}`);
      if (!response.ok) throw new Error(`Missing verified asset: ${name}`);
      const buffer = await response.arrayBuffer();
      const digest = Array.from(
        new Uint8Array(await crypto.subtle.digest("SHA-256", buffer)),
        (b) => b.toString(16).padStart(2, "0"),
      ).join("");
      if (digest !== manifest.files[name])
        throw new Error(`Evidence integrity check failed: ${name}`);
      return [
        name,
        name.endsWith(".json")
          ? JSON.parse(new TextDecoder().decode(buffer))
          : name.endsWith(".md")
            ? new TextDecoder().decode(buffer)
            : URL.createObjectURL(new Blob([buffer], { type: "image/png" })),
      ];
    }),
  );
  const files = Object.fromEntries(entries);
  if (
    files["elliptic.json"].dataset_kind !== "original_elliptic_release" ||
    files["banking.json"].dataset_kind !== "independent_synthetic_banking"
  )
    throw new Error("Domain provenance mismatch.");
  return { ...files, manifest };
}

export function cohortRows(run) {
  return [
    ["train", "1–34"],
    ["validation", "35–39"],
    ["test", "40–49"],
  ].map(([name, period]) => ({ name, period, ...run.split_counts[name] }));
}
