# Community Cloud startup investigation

## Observed failure and current conclusion

On 2026-10-18 the owner supplied a screenshot of
`https://gb9qxk9gcmcwivczbcyinp.streamlit.app/` showing Streamlit's generic
“Oh no. Error running app.” page. That page does not identify an installer error,
Python traceback, branch/commit, Python version, memory kill or platform outage.
The public URL could not be retrieved through the available browsing tool.
No owner-only Streamlit account session, logs or settings are available through
the GitHub connection. **The exact live root cause is not established.**

Verified PR #15 merged; reproduced from main
`7dc7640716994ba853ec196acac537b69056b6eb`. A fresh Python 3.12.14 virtual environment
installed all dashboard requirements using wheels, with no editable project,
Spark, sklearn, private artifacts or dataset credentials. The unchanged main app
started in real headless Chromium and rendered its overview without JavaScript
errors. Consequently, a missing repository import/dependency has not been
established as the cause of this deployment. No pin was relaxed speculatively. The same UI lock also installed successfully
with uv 0.12.23 in a separate fresh environment.

## Concrete improvements

- `dashboard/requirements.txt` explicitly selects the existing UI-only lock from
  the entry-point directory; root `requirements.txt` still selects that same lock.
  No new runtime dependencies, training changes or model-result changes.
- A runtime diagnostics expander shows Python/Streamlit versions, without secrets.
- Missing bundled aggregate files now show explicitly generated illustrative graph
  content, with **no substituted experimental scores, labels or measured results**.
  Normal pages already use versioned public snapshots; private artifacts are not needed.
- Corrupt/unreadable evidence remains an error with no metrics or fallback results.
  Underlying exceptions are logged with tracebacks. Private graph configuration
  validation and dataset/checkpoint/security limits remain in place.
- A real-browser CI job runs fresh isolated UI environments on Python 3.12/3.13.
  Python 3.12 uses pip and Python 3.13 uses uv 0.12.23; both use the same UI lock.
  It uses the system Chrome/Chromium already present, not a paid browser service.

## Production-style reproduction

`scripts/dashboard_browser_smoke.py` starts an actual Streamlit server on a copied,
uninstalled checkout, drives Chromium over a real WebSocket session, selects both
domains and all six pages, loads report images, and rejects JavaScript, HTTP and
application errors. It repeats from repository-root and entry-point working
directories. Separate missing-evidence and corrupt-evidence cases verify labeled
illustrations and fail-closed behavior. Browser requests are restricted to that
cloud loopback server; no external dataset, token, account session or tunnel is used.

The browser driver lives outside the isolated application environment. Example
for a **managed cloud shell only**, from the repository root:

```sh
python -m pip install -r requirements-browser.lock
python -m venv /workspace/mmds-hosted-ui
/workspace/mmds-hosted-ui/bin/python -m pip install --only-binary=:all: -r dashboard/requirements.txt
/workspace/mmds-hosted-ui/bin/python -m pip check
python scripts/dashboard_browser_smoke.py \
  --python /workspace/mmds-hosted-ui/bin/python \
  --output /workspace/mmds-browser-evidence-new
```

Use a new outside-repository output path. The command requires an existing system
Chromium/Chrome; it does not download a browser or provision resources. Output:
`browser-summary.json`, screenshots of public aggregate/illustrative content and
server logs. These test artifacts do not contain private records. The script
refuses local-device execution. No command is intended for a Mac.

Passing these checks establishes cloud reproduction, **not successful operation of
the public Community Cloud deployment**. No live fix, resource-limit diagnosis,
hosted Python version or authenticated deployment action is claimed without evidence.

## Exact owner-only information/access still needed

The connected tools cannot access Streamlit's **Manage app** console. To determine
the live cause, the owner must authorize access to that console in a supported
session, or provide these non-secret fields from it:

1. Repository, deployed branch/commit and main file path (`dashboard/app.py`).
2. Selected Python version; 3.12 and 3.13 are the production-browser CI targets.
   Python 3.14 is not supported by the current pinned stack and must not be assumed.
3. The first failing dependency-install line and its surrounding error, or the
   complete application traceback / explicit memory-termination message from the
   latest build/runtime log. Include enough context to distinguish installation
   failure from a running-script failure; no passwords or tokens.

This is a request for unavailable deployment evidence, not manual code editing or
Colab debugging. Do not share cookies, passwords, OAuth tokens or raw datasets.
The generic public error page cannot replace this information.

After review/merge, a deployment tracking main should pick up repository changes.
Its actual branch, automatic rebuild behavior and current Python selection have
not been verified. A reboot/redeploy or runtime change, if needed, requires the
owner's authenticated console. Do not repeatedly restart blindly: use the first
actual build/traceback error. A working public URL must be checked separately.

## Supported deployment configuration and references

Repository `ojassgambira/MMDS`, reviewed main branch, entry `dashboard/app.py`,
Python 3.13 (3.12 also tested), default CPU/free Community Cloud, no app secrets.
No dataset acquisition, training, Spark/Java or model deserialization occurs in
the web process. Do not add the full training lock to Community Cloud.

Official Streamlit documentation explains [dependency selection and uv/pip](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/app-dependencies)
and [Python selection / owner-only logs](https://docs.streamlit.io/deploy/streamlit-community-cloud/deploy-your-app/deploy).
It searches the entry-point directory before the repository root; requirements
files are processed with uv where possible and pip as fallback. Repository files
do not independently prove which configuration the live service currently uses.
See [dashboard access](dashboard.md) and [cloud execution](cloud-execution.md).
