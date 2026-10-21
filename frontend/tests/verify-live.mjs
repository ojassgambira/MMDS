import { chromium } from "@playwright/test";
import { existsSync } from "node:fs";
import assert from "node:assert/strict";
const url = process.env.PAGES_URL;
assert.equal(
  url,
  "https://ojassgambira.github.io/MMDS/",
  "Unexpected deployment target; refusing verification of another origin.",
);
let last;
for (let attempt = 0; attempt < 4; attempt++) {
  let browser;
  try {
    const response = await fetch(
      `${url}data/manifest.json?verify=${Date.now()}`,
      { cache: "no-store", signal: AbortSignal.timeout(20000) },
    );
    assert(response.ok, `Public manifest HTTP ${response.status}`);
    const manifest = await response.json();
    assert.equal(
      manifest.source_commit,
      process.env.EXPECTED_COMMIT,
      "Public deployment is stale or from another commit",
    );
    browser = await chromium.launch({
      executablePath:
        process.env.CHROME_BIN ||
        (existsSync("/usr/bin/chromium")
          ? "/usr/bin/chromium"
          : "/usr/bin/google-chrome"),
      headless: true,
      args: ["--no-sandbox", "--disable-dev-shm-usage"],
    });
    const page = await browser.newPage();
    const errors = [];
    page.on("pageerror", (e) => errors.push(e.message));
    await page.route("**/*", (route) =>
      new URL(route.request().url()).origin === new URL(url).origin
        ? route.continue()
        : route.abort(),
    );
    for (const domain of ["elliptic", "banking"]) {
      for (const [id, label] of [
        ["overview", "Validation-selected model"],
        ["graph", "Directed graph explorer"],
        ["temporal", "Observed temporal populations"],
        ["models", "Model families & ablations"],
        ["scalability", "Measured configurations & counts"],
        ["research", "Research evaluation"],
      ]) {
        await page.goto(`${url}?domain=${domain}#${id}`);
        await page
          .getByRole("heading", { name: label, exact: true })
          .waitFor({ timeout: 30000 });
        if (["graph", "temporal", "models", "scalability"].includes(id))
          await page
            .locator(".js-plotly-plot .main-svg")
            .first()
            .waitFor({ timeout: 30000 });
        await page
          .locator("footer")
          .getByRole("link", {
            name: process.env.EXPECTED_COMMIT.slice(0, 7),
            exact: true,
          })
          .waitFor({ timeout: 15000 });
        assert.equal(
          await page.getByRole("alert").count(),
          0,
          "Public dashboard displayed an error",
        );
      }
    }
    assert.deepEqual(errors, []);
    console.log(
      JSON.stringify({
        status: "verified",
        url,
        commit: manifest.source_commit,
        domain_page_visits: 12,
      }),
    );
    process.exitCode = 0;
    last = null;
    break;
  } catch (error) {
    last = error;
  } finally {
    await browser?.close();
  }
  if (attempt < 3) await new Promise((resolve) => setTimeout(resolve, 10000));
}
if (last) throw last;
