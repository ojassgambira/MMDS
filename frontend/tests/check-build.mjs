import { readFileSync, existsSync, readdirSync } from "node:fs";
import { createHash } from "node:crypto";
import assert from "node:assert/strict";
import { join } from "node:path";
const folder = new URL("../dist/", import.meta.url).pathname;
const html = readFileSync(join(folder, "index.html"), "utf8");
for (const match of html.matchAll(/(?:src|href)="([^"]+)"/g)) {
  const url = match[1];
  assert(url.startsWith("/MMDS/"), `Wrong repository base path: ${url}`);
  assert(
    existsSync(join(folder, url.slice("/MMDS/".length))),
    `Broken built link: ${url}`,
  );
}
assert(
  html.includes("Content-Security-Policy") && !html.includes("unsafe-eval"),
);
const manifest = JSON.parse(
  readFileSync(join(folder, "data/manifest.json"), "utf8"),
);
assert.equal(Object.keys(manifest.files).length, 9);
assert.deepEqual(
  readdirSync(join(folder, "data")).sort(),
  [...Object.keys(manifest.files), "manifest.json"].sort(),
);
for (const [name, sha] of Object.entries(manifest.files)) {
  assert(!name.includes("/") && !name.startsWith("."));
  const raw = readFileSync(join(folder, "data", name));
  assert.equal(
    createHash("sha256").update(raw).digest("hex"),
    sha,
    `Asset fingerprint mismatch: ${name}`,
  );
}
const report = readFileSync(join(folder, "data/report.md"), "utf8");
for (const match of report.matchAll(/\[[^\]]*\]\(([^)]+)\)/g))
  assert(
    /^https:\/\//.test(match[1]),
    `Broken portable report link: ${match[1]}`,
  );
console.log(
  "Built base paths, local links, CSP and nine allowlisted asset fingerprints verified.",
);
