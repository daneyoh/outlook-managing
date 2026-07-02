"""
conftest.py — puts `00. BACKEND/` on sys.path so tests can do
`import build_dashboard`, `import fetch_mail`, `import weekly_review`.

Phase 1 harness scaffold (see .omc/plans/outlook-widget-fix-plan.md, Phase 1.1).
No source changes here — only test infrastructure.

Import-time side effects observed in the backend modules (documented, not fixed —
this is exactly what motivates Phase 1.5's config/paths decoupling):

- build_dashboard.py:30-35 reads config at IMPORT time:
    MY_EMAIL = getattr(_cfg, "MY_EMAIL", "")
    MY_NAME = getattr(_cfg, "MY_NAME", "")
    INTERNAL_DOMAIN = getattr(_cfg, "INTERNAL_DOMAIN", "").lower() or (MY_EMAIL's domain)
  These become frozen module-level snapshots of `00. BACKEND/config.py` at the moment
  `build_dashboard` is first imported in the test session. Because config.py in this
  repo already contains real values (MY_EMAIL set, INTERNAL_DOMAIN NOT set), the import
  exercises the `or`-fallback path by default. Tests that need a *different* MY_EMAIL/
  INTERNAL_DOMAIN combination (e.g. the mandatory fallback-guard case) monkeypatch the
  already-imported `build_dashboard` module's globals directly in the test — they do
  NOT reload the module or edit config.py, per the "no source-behavior change" and
  "monkeypatch in the test, not in source" constraints for this phase.

- fetch_mail.py has no win32com/pythoncom/Outlook-COM dependency in this codebase (it
  talks to Microsoft Graph via `msal` + `requests`, not the desktop Outlook COM object
  model) — so there is nothing to guard/skip here. Confirmed by grepping the module for
  win32com/pythoncom/comtypes (no matches). fetch_mail.py DOES read
  `02. DB/state/user_config.json` at import time (via `_load_user_cfg_early()`, line
  ~30-44) and creates directories (`os.makedirs(DB_DIR, ...)`, `os.makedirs(STATE_DIR,
  ...)`, `os.makedirs(.../logs, ...)`) as a side effect of computing its module-level
  path constants. This is a real filesystem side effect on import, but it is idempotent
  (safe to import repeatedly) and writes into this repo's own `02. DB/` tree, not
  outside it — so the smoke import test is left to run against it as-is rather than
  mocked, per "isolate/guard only if importing fails without Outlook" (it does not fail
  here).

- app.py, build_dashboard.py, fetch_mail.py, weekly_review.py, fetch_loop.py all guard
  their side-effectful entry points behind `if __name__ == "__main__":` — confirmed by
  grep. app.py additionally documents (line 9-10) that `Api` must be importable without
  creating a window; `import webview` is a local import inside the `__main__` block
  (app.py:1442), not a module-level import — so importing app.py does not touch
  pywebview. (app.py is not required by the Phase 1.1 smoke test but was checked because
  `_is_ad_key`'s smallest callable seam, `_AD_RE`/`_strip_ad`, lives there.)
"""
import os
import sys

BACKEND_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                            "00. BACKEND")

if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)
