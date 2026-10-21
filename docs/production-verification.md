# Production verification — 21 October 2026

Production URL: https://ojassgambira.github.io/MMDS/

## Published baseline and verified evidence

The published main commit is `d4f3155c7f56f592fa7a0e7c14d58c9aabea8842`.
[Pages deployment run](https://github.com/ojassgambira/MMDS/actions/runs/39596880900)
succeeded, including its **actual public URL** Chromium verification at
2026-10-21 12:07:26 UTC: all six sections in both research domains, rendered charts,
no application alerts/page errors, and the expected commit in the public manifest
and footer. This is actual public-site evidence, not a localhost health check.

The deployment artifact (ID `12344397581`, 15 files, 2,664,995 uncompressed bytes)
was downloaded through the GitHub connector and inspected in Codex Cloud. All nine
public research assets matched the verified exporter byte for byte, and their
SHA-256 values matched the published artifact manifest. The source aggregate
manifest and clean build commit were checked. The artifact contains only HTML,
three bundled JS/CSS files, an icon and ten allowlisted data/manifest files.
No raw transaction/account dataset, prediction arrays, model binaries, credential
files or Python sources are in the deployment artifact. A common credential-marker
scan found none. This bounded inspection is not a guarantee about every historical
repository revision or every possible secret format.

Real original Elliptic, independent synthetic banking, generated illustration
subgraphs and generated Spark benchmark workloads remain separate. All model
scores and measured curves retain their frozen values. Synthetic SAR targets are
not verified bank fraud; illustrative graph nodes are not actual transactions.

## Confirmed submission blockers and fixes

A Chromium/axe-core 4.14.0 audit of the **exact downloaded production artifact**,
served in isolated Codex Cloud, tested all 24 combinations of six sections, two
domains and desktop/mobile widths (1440/390 px). The baseline failed these rules:

- `color-contrast`: labels, table headings, selected navigation indices and footer
  links did not meet the 4.5:1 text requirement.
- `nested-interactive`: charts used `role="img"` while containing focusable Plotly
  controls, incorrectly giving interactive figures static-image semantics.
- `scrollable-region-focusable`: overflowing mobile tables, including Markdown
  report tables, had no keyboard-focusable scroll container.

The fix darkens text, uses labeled `figure` roles for interactive plots, and gives
all table scroll regions accessible names, keyboard focus and visible focus rings.
Markdown tables use the same scroll container. Scientific computations and public
research asset bytes are unchanged.

The new automated regression covers all 24 combinations with WCAG 2 A/AA and
2.1 A/AA axe rules, viewport overflow, chart rendering and actual keyboard scrolling.
Additional browser assertions compare every model's visible AP/precision/recall/F1/
FPR, validation ordering, PR points, confusion counts, three banking seed means,
temporal series and six Spark measurements against the exported frozen evidence.
These tests support both a production build in cloud CI and the fixed public
`MMDS_LIVE_URL` without starting a local server. Post-deployment CI runs the same
suite against the actual public site and retains browser evidence.

## Readiness boundary

**The published baseline is not fully submission-ready:** the accessibility defects
above are reproducible. A passing test of the proposed fix in Codex Cloud or PR CI
is not evidence that the public site has received the fix. The fix must merge,
deploy, and pass the real-URL workflow before this blocker is closed.

At audit start Codex Cloud's enforced outbound policy excluded
`ojassgambira.github.io`. The owner chose to allow it; direct expanded testing waits
for an observed, enforced policy update. The existing GitHub-hosted live checks
remain valid, but live mobile interactions, complete link traversal and the expanded
accessibility suite are not claimed on the basis of local artifact tests. No
network bypass, paid resources or Mac workloads are used. No temporary audit branch
or unrelated workflow is published solely to circumvent that restriction.

Automated WCAG checks are not a manual screen-reader or assistive-technology
certification. A final PASS requires public-site execution evidence; retain any
manual-review items and infrastructure limitations in the final assessment.

## Fix validation in managed Codex Cloud

- Production Vite build and repository-base-path, local-link and asset-hash checks passed.
- 45 Chromium tests passed, including all 24 automated accessibility cases and
  five model/temporal/benchmark evidence regressions. Automated rule violations
  were zero for these tested fix views. These were cloud-hosted production-build
  tests, not a claim that the fix is already live.
- Six frontend unit tests and 18 targeted Python export/dashboard/submission tests passed.
- Ruff, actionlint and source evidence/document-link audits passed.
- The original production artifact's accessibility findings remain relevant until
  the fix is actually deployed. See the PR and workflow logs for final CI results.

To run the same tests against the actual deployed origin in authorized cloud CI,
set `MMDS_LIVE_URL=https://ojassgambira.github.io/MMDS/` for `npm run test:browser
--prefix frontend`. This mode starts no local server and rejects other public
origins. The post-deploy workflow sets this automatically; no Mac or notebook
execution is required. Automated test cases that intentionally replace a response
operate only within their isolated browser context and never change public files.
