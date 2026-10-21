import { test, expect } from "@playwright/test";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
const require = createRequire(import.meta.url);
const axe = readFileSync(require.resolve("axe-core/axe.min.js"), "utf8");
for (const width of [1440, 390]) {
  for (const domain of ["elliptic", "banking"]) {
    for (const section of [
      "overview",
      "graph",
      "temporal",
      "models",
      "scalability",
      "research",
    ]) {
      test(`${width}px ${domain}/${section}: automated WCAG rules and keyboard-accessible overflow`, async ({
        page,
      }) => {
        await page.setViewportSize({ width, height: 900 });
        await page.goto(`?domain=${domain}#${section}`);
        await expect(page.locator(".badge")).toBeVisible();
        for (const chart of await page.locator(".chart").all()) {
          await expect(chart).toHaveAttribute("role", "figure");
          await expect(chart.locator(".main-svg").first()).toBeVisible();
        }
        await page.evaluate(axe);
        const violations = await page.evaluate(async () => {
          const results = await window.axe.run(document, {
            runOnly: {
              type: "tag",
              values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"],
            },
          });
          return results.violations.map((v) => ({
            id: v.id,
            impact: v.impact,
            nodes: v.nodes.map((n) => ({
              target: n.target,
              summary: n.failureSummary,
            })),
          }));
        });
        expect(violations).toEqual([]);
        for (const region of await page.locator(".table-scroll").all()) {
          await expect(region).toHaveAttribute("tabindex", "0");
          await expect(region).toHaveAccessibleName(/./);
          await region.focus();
          await expect(region).toBeFocused();
          if (await region.evaluate((e) => e.scrollWidth > e.clientWidth)) {
            await region.press("ArrowRight");
            await expect
              .poll(() => region.evaluate((e) => e.scrollLeft))
              .toBeGreaterThan(0);
          }
        }
        expect(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth + 1,
          ),
        ).toBe(true);
      });
    }
  }
}
