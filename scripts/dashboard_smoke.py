"""UI-only runtime integration: all pages, no Spark or sklearn installation required."""

from pathlib import Path
from streamlit.testing.v1 import AppTest

root = Path(__file__).resolve().parents[1]
app = AppTest.from_file(str(root / "dashboard/app.py"), default_timeout=30).run()
for name in ("Elliptic Bitcoin", "Synthetic banking"):
    app.sidebar.selectbox[0].select(name).run()
    for page in (
        "Overview",
        "Transaction graph",
        "Temporal patterns",
        "Models & PR curves",
        "Scalability",
        "Research report",
    ):
        app.sidebar.radio[0].set_value(page).run()
        if app.exception:
            raise RuntimeError(f"Dashboard failed in {name}/{page}: {app.exception}")
print("Verified all six pages for both domains in UI-only runtime.")
