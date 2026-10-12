"""
Keep a long-running web server in step with the code after a deploy.

When new code is pushed, Streamlit Community Cloud pulls it and reruns the
page script, but library modules that were already imported can stay in
memory as the OLD version (seen in practice: new app.py, old report.py).
reload_changed() re-imports any of this package's modules whose file changed
since the server first loaded them, in dependency order, and returns True so
the app can clear cached results computed with the old code.
"""

from __future__ import annotations

import importlib
import os
import sys

# Dependency order: a module comes after everything it imports from this package.
ORDER = ["i18n", "profiles", "portfolios", "allocation", "sample_clients", "data", "risk",
         "duration", "client_scenarios", "projection", "review", "report", "pdf_report"]


def _mtime(module) -> float | None:
    path = getattr(module, "__file__", None)
    try:
        return os.path.getmtime(path) if path else None
    except OSError:
        return None


def reload_changed(stamps: dict, package: str = "portfolio_tool") -> bool:
    """Reload changed modules; `stamps` remembers each file's last-seen mtime."""
    names = [f"{package}.{n}" for n in ORDER] + sorted(
        n for n in sys.modules if n.startswith(package + ".") and n.split(".")[-1] not in ORDER)
    changed = False
    for name in names:
        module = sys.modules.get(name)
        if module is None or name.endswith(".hot_reload"):
            continue
        mtime = _mtime(module)
        seen = stamps.get(name)
        # Once one module changes, reload everything after it too: they may hold
        # references to the old one's functions.
        if changed or (seen is not None and mtime is not None and mtime != seen):
            importlib.reload(module)
            changed = True
            mtime = _mtime(module)
        stamps[name] = mtime
    return changed
