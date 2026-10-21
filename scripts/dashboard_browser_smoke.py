"""Real Chromium + Streamlit WebSocket sessions on an uninstalled cloud checkout."""

import argparse
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from mmd_fraud.automation import cloud_runtime  # noqa: E402
from mmd_fraud.diagnostics import tail  # noqa: E402

PAGES = {
    "Overview": "Validation-selected model",
    "Transaction graph": "Interactive directed graph explorer",
    "Temporal patterns": "Temporal observations",
    "Models & PR curves": "Chronological model evaluation",
    "Scalability": "Measured execution and scalability",
    "Research report": "Research methodology and conclusions",
}


def copy_checkout(destination):
    for name in ("src", "dashboard", "docs", "configs", "notebooks", ".streamlit"):
        shutil.copytree(
            ROOT / name,
            destination / name,
            ignore=shutil.ignore_patterns("__pycache__", "*.egg-info"),
        )
    for source in ROOT.iterdir():
        if source.is_file() and not source.name.startswith("."):
            shutil.copyfile(source, destination / source.name)


def run_case(python, browser_path, checkout, output, scenario, cwd):
    from playwright.sync_api import sync_playwright

    output.mkdir(parents=True)
    log_path = output / "server.log"
    env = {k: v for k, v in os.environ.items() if k not in ("PYTHONPATH", "MMDS_GRAPH_DIRECTORY")}
    with socket.socket() as available:
        available.bind(("127.0.0.1", 0))
        port = available.getsockname()[1]
    command = [
        python,
        "-m",
        "streamlit",
        "run",
        str(checkout / "dashboard/app.py"),
        "--server.address=127.0.0.1",
        f"--server.port={port}",
        "--server.headless=true",
        "--browser.gatherUsageStats=false",
    ]
    with log_path.open("w") as log:
        process = subprocess.Popen(command, cwd=cwd, env=env, stdout=log, stderr=log)
        try:
            for _ in range(100):
                if process.poll() is not None:
                    raise RuntimeError("Streamlit exited before startup: " + tail(log_path))
                try:
                    with urllib.request.urlopen(
                        f"http://127.0.0.1:{port}/_stcore/health", timeout=1
                    ):
                        break
                except OSError:
                    time.sleep(0.2)
            else:
                raise RuntimeError("Streamlit readiness timeout: " + tail(log_path))
            with sync_playwright() as pw:
                browser = pw.chromium.launch(
                    executable_path=browser_path,
                    headless=True,
                    args=["--no-sandbox", "--disable-dev-shm-usage"],
                )
                page = browser.new_page(viewport={"width": 1440, "height": 1000})
                errors, sockets, visited, http_errors = [], [], [], []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.on("websocket", lambda ws: sockets.append(ws.url))
                page.on(
                    "response",
                    lambda response: http_errors.append(str(response.status))
                    if response.status >= 400
                    else None,
                )
                # No external URLs, account sessions, datasets or telemetry in the test browser.
                page.route(
                    "**/*",
                    lambda route: route.continue_()
                    if route.request.url.startswith(f"http://127.0.0.1:{port}/")
                    else route.abort(),
                )
                page.goto(f"http://127.0.0.1:{port}/")
                page.get_by_text("MMDS · Financial Graph Research", exact=True).wait_for(
                    timeout=30000
                )
                sidebar = page.get_by_test_id("stSidebar")
                for domain in ("Elliptic Bitcoin", "Synthetic banking"):
                    current = sidebar.get_by_role("combobox").first.inner_text()
                    if domain not in current:
                        sidebar.get_by_role("combobox").first.click()
                        page.get_by_role("option", name=domain, exact=True).click()
                    if scenario == "verified":
                        marker = (
                            "Real original Elliptic release"
                            if domain == "Elliptic Bitcoin"
                            else "Independently generated synthetic banking data"
                        )
                        page.get_by_text(marker, exact=False).first.wait_for(timeout=20000)
                        for name, heading in PAGES.items():
                            sidebar.get_by_text(name, exact=True).click()
                            try:
                                page.get_by_text(heading, exact=True).wait_for(timeout=20000)
                            except Exception as error:
                                page.screenshot(path=str(output / "failure.png"))
                                (output / "failure-page.txt").write_text(
                                    page.locator("body").inner_text()[-8000:]
                                )
                                raise RuntimeError(
                                    f"Page did not render: {domain}/{name}: " + tail(log_path)
                                ) from error
                            if name in (
                                "Transaction graph",
                                "Temporal patterns",
                                "Models & PR curves",
                                "Scalability",
                            ):
                                page.get_by_test_id("stPlotlyChart").first.wait_for(timeout=20000)
                            if name == "Research report":
                                page.wait_for_function(
                                    """() => { const images = Array.from(document.querySelectorAll('[data-testid="stImage"] img'));
                                    return images.length >= 2 && images.every(img => img.complete && img.naturalWidth > 0); }""",
                                    timeout=20000,
                                )
                            if page.get_by_test_id("stException").count():
                                raise RuntimeError(
                                    f"App exception: {domain}/{name}: " + tail(log_path)
                                )
                            visited.append(f"{domain}/{name}")
                    elif scenario == "missing":
                        page.get_by_text(
                            "Illustrative graph — no experiment results", exact=True
                        ).wait_for(timeout=20000)
                        page.get_by_test_id("stPlotlyChart").first.wait_for(timeout=20000)
                        if page.get_by_test_id("stMetric").count():
                            raise RuntimeError(
                                "Missing evidence must not display experimental metrics"
                            )
                        visited.append(f"{domain}/illustrative-only")
                    else:
                        page.get_by_text("Evidence unavailable or invalid:", exact=False).wait_for(
                            timeout=20000
                        )
                        if (
                            page.get_by_test_id("stMetric").count()
                            or page.get_by_test_id("stPlotlyChart").count()
                        ):
                            raise RuntimeError("Corrupt evidence must fail closed")
                        visited.append(f"{domain}/integrity-error")
                    page.screenshot(path=str(output / f"{domain.split()[0]}.png"))
                if errors or http_errors or not any("/_stcore/stream" in url for url in sockets):
                    raise RuntimeError(
                        f"Browser/HTTP errors or missing real Streamlit session: {errors}, {http_errors}"
                    )
                browser.close()
                return {
                    "scenario": scenario,
                    "cwd": cwd.relative_to(checkout).as_posix(),
                    "pages": visited,
                    "javascript_errors": errors,
                    "http_errors": http_errors,
                    "websocket_verified": True,
                }
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=10)


def main():
    cloud_runtime()  # Never run workloads on a personal computer.
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", required=True, help="Isolated UI-only server interpreter")
    parser.add_argument(
        "--browser", default=shutil.which("chromium") or shutil.which("google-chrome")
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if not args.browser:
        raise RuntimeError("System Chromium/Chrome required; no browser download is attempted")
    output = args.output.resolve()
    if output.is_relative_to(ROOT) or output.exists():
        raise ValueError("Use a new browser evidence directory outside the repository")
    output.mkdir(parents=True)
    subprocess.run(
        [
            args.python,
            "-I",
            "-c",
            "import importlib.util; assert all(importlib.util.find_spec(n) is None "
            "for n in ('mmd_fraud','pyspark','sklearn'))",
        ],
        check=True,
    )
    results = []
    try:
        with tempfile.TemporaryDirectory(prefix="mmds-production-") as temp:
            checkout = Path(temp) / "checkout"
            checkout.mkdir()
            copy_checkout(checkout)
            for label, cwd in [("root", checkout), ("entrypoint", checkout / "dashboard")]:
                results.append(
                    run_case(args.python, args.browser, checkout, output / label, "verified", cwd)
                )
            shutil.rmtree(checkout / "dashboard/data")
            results.append(
                run_case(
                    args.python, args.browser, checkout, output / "missing", "missing", checkout
                )
            )
            shutil.copytree(ROOT / "dashboard/data", checkout / "dashboard/data")
            for name in ("elliptic.json", "banking.json"):
                with (checkout / "dashboard/data" / name).open("a") as handle:
                    handle.write(" ")
            results.append(
                run_case(
                    args.python, args.browser, checkout, output / "corrupt", "corrupt", checkout
                )
            )
        (output / "browser-summary.json").write_text(
            json.dumps({"status": "passed", "cases": results}, indent=2)
        )
        print(
            json.dumps(
                {
                    "status": "passed",
                    "verified_page_visits": sum(len(r["pages"]) for r in results),
                    "browser": args.browser,
                    "scope": "cloud reproduction; not public deployment verification",
                }
            )
        )
    except Exception as error:
        (output / "browser-summary.json").write_text(
            json.dumps({"status": "failed", "error": str(error)}, indent=2)
        )
        raise


if __name__ == "__main__":
    main()
