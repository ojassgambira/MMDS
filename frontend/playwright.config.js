import { defineConfig } from "@playwright/test";
import { existsSync } from "node:fs";
export default defineConfig({
  testDir: "./tests/browser",
  timeout: 60000,
  expect: { timeout: 15000 },
  workers: 2,
  retries: 0,
  use: {
    baseURL: "http://127.0.0.1:4173/MMDS/",
    headless: true,
    launchOptions: {
      executablePath:
        process.env.CHROME_BIN ||
        (existsSync("/usr/bin/chromium")
          ? "/usr/bin/chromium"
          : "/usr/bin/google-chrome"),
      args: ["--no-sandbox", "--disable-dev-shm-usage"],
    },
    screenshot: "only-on-failure",
    trace: "retain-on-failure",
  },
  webServer: {
    command: "npm run preview",
    url: "http://127.0.0.1:4173/MMDS/",
    reuseExistingServer: false,
  },
  reporter: [["list"], ["html", { open: "never" }]],
});
