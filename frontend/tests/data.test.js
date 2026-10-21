import { describe, it, expect } from "vitest";
import { readFileSync } from "node:fs";
import {
  FILES,
  loadEvidence,
  graphView,
  cohortRows,
  metricRows,
  positiveLabels,
} from "../src/data.js";
const asset = (name) =>
  readFileSync(new URL(`../public/data/${name}`, import.meta.url));
const original = JSON.parse(asset("manifest.json"));
const fetcher = async (path) => new Response(asset(path.split("/").at(-1)));

describe("verified static evidence", () => {
  it("loads only fingerprinted public files and separate provenance", async () => {
    const data = await loadEvidence("/MMDS/", fetcher);
    expect(data["elliptic.json"].stats.nodes).toBe(203769);
    expect(data["banking.json"].runs).toHaveLength(3);
    expect(data["banking.json"].dataset_kind).toBe(
      "independent_synthetic_banking",
    );
    expect(Object.keys(data.manifest.files).sort()).toEqual([...FILES].sort());
  });
  it("rejects corruption and missing assets rather than inventing metrics", async () => {
    await expect(
      loadEvidence("/MMDS/", async (path) =>
        path.endsWith("elliptic.json") ? new Response("{}") : fetcher(path),
      ),
    ).rejects.toThrow("integrity");
    await expect(
      loadEvidence("/MMDS/", async (path) =>
        path.endsWith("graphs.json")
          ? new Response("", { status: 404 })
          : fetcher(path),
      ),
    ).rejects.toThrow("Missing");
  });
  it("rejects unapproved manifest paths", async () => {
    const manifest = {
      ...original,
      files: { ...original.files, "../secret.json": "0".repeat(64) },
    };
    await expect(
      loadEvidence("/MMDS/", async (path) =>
        path.endsWith("manifest.json")
          ? Response.json(manifest)
          : fetcher(path),
      ),
    ).rejects.toThrow("Unexpected");
  });
  it("filters only generated graph assets without introducing future nodes or endpoints", () => {
    const graph = JSON.parse(asset("graphs.json")).elliptic;
    const view = graphView(graph, 40, 20, "All nodes");
    expect(graph.dataset_kind).toBe("generated_illustration");
    const ids = new Set(view.nodes.map((n) => n.id));
    expect(
      view.nodes.every((n) => n.step <= 20 && n.id.startsWith("TX-")),
    ).toBe(true);
    expect(
      view.edges.every(
        (e) => e.step <= 20 && ids.has(e.source) && ids.has(e.target),
      ),
    ).toBe(true);
    const focus = graphView(graph, 80, 49, graph.nodes[0].id);
    expect(
      focus.edges.every((e) =>
        [e.source, e.target].includes(graph.nodes[0].id),
      ),
    ).toBe(true);
  });
  it("preserves positive targets, actual curves and validation-based ordering", () => {
    for (const domain of ["elliptic", "banking"]) {
      const data = JSON.parse(asset(`${domain}.json`));
      for (const run of data.runs) {
        const rows = metricRows(run);
        expect(rows[0][0]).toBe(run.selected_family);
        for (const [, family] of rows) {
          expect(
            family.test.confusion_matrix.flat().reduce((a, b) => a + b, 0),
          ).toBe(family.test.rows);
          expect(family.test_curve.rows).toBe(family.test.rows);
          expect(family.test_curve.points.length).toBeLessThanOrEqual(101);
        }
      }
    }
    expect(positiveLabels("banking")[1]).toBe("Simulated SAR");
    expect(positiveLabels("elliptic")[1]).toBe("Known illicit");
  });
});

it("chronological periods never depend on alphabetical JSON key ordering", () => {
  const data = JSON.parse(asset("elliptic.json"));
  const rows = cohortRows(data.runs[0]);
  expect(rows.map((r) => [r.name, r.period, r.rows])).toEqual([
    ["train", "1–34", 29894],
    ["validation", "35–39", 5486],
    ["test", "40–49", 11184],
  ]);
});
