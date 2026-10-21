import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { title, decimal, number } from "../../src/data.js";
const root = new URL("../../public/data/", import.meta.url);
const source = (name) => JSON.parse(readFileSync(new URL(name, root)));
const panel = (page, heading) =>
  page
    .locator("section.panel")
    .filter({ has: page.getByRole("heading", { name: heading, exact: true }) });
const traces = async (page, label) => {
  const chart = page.getByRole("figure", { name: label, exact: true });
  await expect(chart.locator(".main-svg").first()).toBeVisible();
  return chart.evaluate((e) => e.data.map((t) => ({ x: t.x, y: t.y, z: t.z })));
};
const keys = [
  "pr_auc_average_precision",
  "precision",
  "recall",
  "f1",
  "false_positive_rate",
];
for (const domain of ["elliptic", "banking"]) {
  const data = source(`${domain}.json`);
  for (const run of data.runs) {
    test(`${domain} seed ${run.seed}: every displayed model score, PR point and confusion count equals frozen evidence`, async ({
      page,
    }) => {
      await page.goto(`?domain=${domain}&seed=${run.seed}#models`);
      await expect(
        page.getByRole("heading", {
          name: "Model families & ablations",
          exact: true,
        }),
      ).toBeVisible();
      const rows = await panel(page, "Model families & ablations")
        .locator("tbody tr")
        .evaluateAll((rs) =>
          rs.map((r) => [...r.cells].map((c) => c.innerText)),
        );
      const ordered = Object.entries(run.families).sort(
        (a, b) =>
          b[1].validation.pr_auc_average_precision -
          a[1].validation.pr_auc_average_precision,
      );
      expect(rows).toHaveLength(ordered.length);
      for (const [i, [name, family]] of ordered.entries()) {
        expect(rows[i][0]).toContain(title(name));
        expect(rows[i][1]).toBe(String(family.feature_count ?? "Not recorded"));
        expect(rows[i].slice(2)).toEqual([
          decimal(family.validation.pr_auc_average_precision),
          ...keys.map((k) => decimal(family.test[k])),
        ]);
      }
      const curves = await traces(
        page,
        "Measured held-out precision recall curves",
      );
      for (const [i, [, family]] of Object.entries(run.families).entries()) {
        expect(curves[i].x).toEqual(
          family.test_curve.points.map((p) => p.recall),
        );
        expect(curves[i].y).toEqual(
          family.test_curve.points.map((p) => p.precision),
        );
      }
      for (const [name, family] of Object.entries(run.families)) {
        await page.getByLabel("Evaluation model").selectOption(name);
        await expect
          .poll(
            async () => (await traces(page, "Held-out confusion matrix"))[0].z,
          )
          .toEqual(family.test.confusion_matrix);
        expect(
          await panel(page, "Operating point & uncertainty")
            .locator(".metric strong")
            .allTextContents(),
        ).toEqual(keys.map((k) => decimal(family.test[k])));
        const counts = await panel(page, "Confusion matrix")
          .locator("tbody tr")
          .evaluateAll((rs) =>
            rs.map((r) => [...r.cells].slice(1).map((c) => c.innerText)),
          );
        expect(counts).toEqual(
          family.test.confusion_matrix.map((row) => row.map(number)),
        );
      }
      if (domain === "banking") {
        const means = await panel(page, "Across three fixed synthetic replicas")
          .locator("tbody tr")
          .evaluateAll((rs) =>
            rs.map((r) => [...r.cells].map((c) => c.innerText)),
          );
        expect(means).toEqual(
          Object.entries(data.family_means).map(([name, m]) => [
            title(name),
            ...keys.map((k) => decimal(m[k])),
          ]),
        );
      }
      await page.goto(`?domain=${domain}&seed=${run.seed}#temporal`);
      const temporal = await traces(page, "Temporal transaction populations");
      for (const [i, key] of (domain === "elliptic"
        ? ["licit", "illicit", "unknown"]
        : ["events", "sar_payments"]
      ).entries()) {
        expect(temporal[i].x).toEqual(
          run.temporal.map((r) => r.step ?? r.time_step),
        );
        expect(temporal[i].y).toEqual(run.temporal.map((r) => r[key]));
      }
    });
  }
}
test("all six measured Spark configurations and chart values equal verified evidence", async ({
  page,
}) => {
  const bench = source("benchmarks.json");
  await page.goto("#scalability");
  const counts = panel(page, "Measured configurations & counts");
  await expect(counts).toBeVisible();
  const rows = await counts
    .locator("tbody tr")
    .evaluateAll((rs) => rs.map((r) => [...r.cells].map((c) => c.innerText)));
  expect(rows).toEqual(
    bench.measurements.map((m) => [
      m.domain === "bitcoin_generated_fixture"
        ? "Bitcoin fixture"
        : "Synthetic banking",
      number(m.nodes),
      number(m.events),
      number(m.input_bytes),
      m.seconds.toFixed(6),
      number(m.output_rows),
    ]),
  );
  for (const [kind, label] of [
    ["bitcoin_generated_fixture", "Generated Bitcoin fixture"],
    ["independent_synthetic_banking", "Independent synthetic banking"],
  ]) {
    const actual = (await traces(page, `${label} processing benchmark`))[0];
    const expected = bench.measurements.filter((m) => m.domain === kind);
    expect(actual.x).toEqual(expected.map((m) => m.events));
    expect(actual.y).toEqual(expected.map((m) => m.seconds));
  }
  await counts
    .getByText("Actual execution configuration", { exact: true })
    .click();
  expect(JSON.parse(await counts.locator("pre").innerText())).toEqual(
    bench.configuration,
  );
});
