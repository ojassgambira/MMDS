import { test, expect } from "@playwright/test";
const pages = {
  overview: "Validation-selected model",
  graph: "Directed graph explorer",
  temporal: "Observed temporal populations",
  models: "Model families & ablations",
  scalability: "Measured configurations & counts",
  research: "Research evaluation",
};
for (const domain of ["elliptic", "banking"]) {
  for (const [page, heading] of Object.entries(pages)) {
    test(`${domain}: ${page} renders actual built application under repository base`, async ({
      page: browser,
    }) => {
      const errors = [],
        failed = [],
        external = [];
      browser.on("pageerror", (e) => errors.push(e.message));
      browser.on("response", (r) => {
        if (r.status() >= 400) failed.push(r.url());
      });
      browser.on("request", (r) => {
        if (
          !r.url().startsWith("http://127.0.0.1:4173/") &&
          !r.url().startsWith("blob:")
        )
          external.push(r.url());
      });
      await browser.goto(`?domain=${domain}#${page}`);
      await expect(
        browser.getByRole("heading", { name: heading, exact: true }),
      ).toBeVisible();
      if (["graph", "temporal", "models", "scalability"].includes(page))
        await expect(
          browser.locator(".js-plotly-plot .main-svg").first(),
        ).toBeVisible();
      if (page === "research") {
        await expect(browser.locator(".report-image")).toHaveCount(2);
        await expect
          .poll(() =>
            browser
              .locator(".report-image")
              .evaluateAll((images) =>
                images.every((i) => i.complete && i.naturalWidth > 0),
              ),
          )
          .toBe(true);
      }
      await expect(browser.getByRole("alert")).toHaveCount(0);
      expect(errors).toEqual([]);
      expect(failed).toEqual([]);
      expect(external).toEqual([]);
    });
  }
}
test("navigation, independent seeds, models, graph controls and reload are functional", async ({
  page,
}) => {
  await page.goto("");
  await page.getByLabel("Research domain").selectOption("banking");
  await page.getByLabel("Simulation seed").selectOption("2");
  await page.getByRole("link", { name: "Models & evaluation" }).click();
  await expect(
    page.getByRole("heading", { name: "Confusion matrix", exact: true }),
  ).toBeVisible();
  await page.getByLabel("Evaluation model").selectOption("temporal_only");
  await expect(page.getByLabel("Evaluation model")).toHaveValue(
    "temporal_only",
  );
  await page.reload();
  await expect(page.getByLabel("Simulation seed")).toHaveValue("2");
  await expect(
    page.getByRole("heading", { name: "Model families & ablations" }),
  ).toBeVisible();
  await page.getByRole("link", { name: "Graph explorer" }).click();
  await expect(page.locator(".js-plotly-plot .main-svg").first()).toBeVisible();
  await page.getByLabel("Example nodes").focus();
  await page.getByLabel("Example nodes").press("Home");
  await expect(page.getByLabel("Example nodes")).toHaveValue("20");
  await page.getByLabel("Focus node").selectOption("ACCOUNT-000");
  await expect(page.getByLabel("Focus node")).toHaveValue("ACCOUNT-000");
  await expect(
    page.getByText("Illustrative content only.", { exact: true }),
  ).toBeVisible();
});
test("mobile navigation and tables stay within viewport", async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto("?domain=banking#models");
  await expect(
    page.getByRole("heading", { name: "Model families & ablations" }),
  ).toBeVisible();
  await expect(page.locator(".js-plotly-plot .main-svg").first()).toBeVisible();
  expect(
    await page.evaluate(
      () => document.documentElement.scrollWidth <= innerWidth + 1,
    ),
  ).toBe(true);
  await page.getByRole("link", { name: "Temporal analytics" }).click();
  await expect(
    page.getByRole("heading", { name: "Observed temporal populations" }),
  ).toBeVisible();
});
test("corrupt evidence fails closed without substituted metrics", async ({
  page,
}) => {
  await page.route("**/data/elliptic.json", (route) =>
    route.fulfill({ status: 200, body: "{}" }),
  );
  await page.goto("");
  await expect(page.getByRole("alert")).toContainText("integrity");
  await expect(page.locator(".metric")).toHaveCount(0);
});
test("missing assets fail with useful report link and no invented results", async ({
  page,
}) => {
  await page.route("**/data/graphs.json", (route) =>
    route.fulfill({ status: 404, body: "" }),
  );
  await page.goto("");
  await expect(page.getByRole("alert")).toContainText("Missing verified asset");
  await expect(
    page.getByRole("link", { name: "Open verified research report" }),
  ).toBeVisible();
  await expect(page.locator(".metric")).toHaveCount(0);
});
