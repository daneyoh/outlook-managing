"""
Phase 1.1 smoke test — confirms the three target backend modules import cleanly
with `00. BACKEND/` on sys.path (see conftest.py for import-time side effects
documented and deliberately left as-is this phase).
"""
import importlib


def test_import_build_dashboard():
    """build_dashboard imports without raising, despite its import-time config read."""
    module = importlib.import_module("build_dashboard")
    assert hasattr(module, "build_data")


def test_import_fetch_mail():
    """fetch_mail imports without raising (no Outlook-COM dependency; Graph API only)."""
    module = importlib.import_module("fetch_mail")
    assert hasattr(module, "GRAPH")


def test_import_weekly_review():
    """weekly_review imports without raising (pulls MY_EMAIL etc. from build_dashboard)."""
    module = importlib.import_module("weekly_review")
    assert hasattr(module, "REVIEW_OUT_FILE")


def test_no_module_launches_on_import():
    """All three modules guard side-effectful entry points behind __main__ — importing
    them must not open a webview window, start a fetch loop, or write dashboard/report
    HTML files. This is a coarse guard: if any module's __main__ body ran on import,
    it would raise (e.g. missing sys.argv handling) or hang (e.g. webview.start()),
    and this test (plus the whole suite completing at all) would fail/hang."""
    importlib.import_module("build_dashboard")
    importlib.import_module("fetch_mail")
    importlib.import_module("weekly_review")
