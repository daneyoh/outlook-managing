"""
Phase 1.2 — targets named in the plan/audit that have NO clean callable seam today.

Per the plan: "If a target has no clean callable seam, do NOT refactor to create one —
write a `# TODO Phase 2` note in the test file naming the target and skip it with a
reason." These are recorded here (skipped, not deleted/ignored silently) so Phase 2's
extraction work has an explicit paper trail and a place to land real tests once a seam
exists.
"""
import pytest


# TODO Phase 2: "replied / 내가 답한 detection" — currently computed as
# `replied_threads` inline inside build_dashboard.build_data() (build_dashboard.py:
# ~347-355): a dict comprehension over `rows_union` that tracks, per normalized-subject
# thread key, whether the LATEST message in that thread was sent by me (구분 ==
# "보낸메일"). This logic is not exposed as a standalone function — it is a local
# variable built inline in the middle of a 270-line function, using two other locals
# (_latest_date, _latest_dir) that are themselves built in the same loop. There is no
# seam to call in isolation without either (a) refactoring build_data() to extract it
# (out of scope this phase) or (b) running the entire build_data() pipeline against a
# real/fixture mailbox.json + archive file (a much heavier integration test than a
# Phase-1 pure-function characterization test, and arguably belongs in Phase 2 once
# the extraction creates a real seam to characterize against).
@pytest.mark.skip(reason="No standalone callable seam for 'replied/내가 답한' detection "
                          "today — it is inline in build_dashboard.build_data() "
                          "(build_dashboard.py:~347-355). Extracting a seam is Phase 2 "
                          "work (see rules.py consolidation); do not refactor here.")
def test_replied_thread_detection_placeholder():
    ...


# TODO Phase 2: "경과일 (elapsed days)" — currently computed inline inside
# build_dashboard.build_data()'s thread-status loop (build_dashboard.py:~426-431):
# `elapsed = (now - dt).days` where `dt = _parse_dt(last.get("날짜", ""))`, gated by
# `if status in ("회신 대기", "확인 필요")`. The underlying primitive (_parse_dt) IS
# tested directly in test_build_dashboard_characterization.py::TestParseDt — what's
# NOT independently testable is the "elapsed days FOR A THREAD, gated by its computed
# status" composition, because `status` itself is derived inline in the same loop from
# other locals (last_dir, to_me, unread) with no standalone predicate function to call.
@pytest.mark.skip(reason="No standalone callable seam for the elapsed-days-per-thread "
                          "composition today — status + elapsed are both inline in "
                          "build_dashboard.build_data()'s thread loop "
                          "(build_dashboard.py:~408-431). The underlying _parse_dt "
                          "primitive IS covered (see TestParseDt); the composition "
                          "with thread status awaits a Phase 2 extraction seam.")
def test_elapsed_days_per_thread_placeholder():
    ...
