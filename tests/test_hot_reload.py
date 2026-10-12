"""The deploy safety net: changed library files get reloaded, unchanged ones don't."""

import os
import sys
import textwrap

from portfolio_tool.hot_reload import reload_changed


def test_changed_module_is_reloaded_and_later_ones_follow(tmp_path, monkeypatch):
    pkg = tmp_path / "demo_pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "i18n.py").write_text("WORD = 'old'\n")
    (pkg / "report.py").write_text(textwrap.dedent("""
        from demo_pkg.i18n import WORD
        def say():
            return WORD
    """))
    monkeypatch.syspath_prepend(str(tmp_path))
    import demo_pkg.report as report
    stamps = {}
    assert reload_changed(stamps, "demo_pkg") is False         # first look: just remember
    assert report.say() == "old"

    (pkg / "i18n.py").write_text("WORD = 'new'\n")
    later = os.path.getmtime(pkg / "i18n.py") + 5
    os.utime(pkg / "i18n.py", (later, later))
    assert reload_changed(stamps, "demo_pkg") is True
    assert sys.modules["demo_pkg.report"].say() == "new"       # report re-imported the new word
    assert reload_changed(stamps, "demo_pkg") is False         # nothing changed since
    for name in [n for n in sys.modules if n.startswith("demo_pkg")]:
        del sys.modules[name]
