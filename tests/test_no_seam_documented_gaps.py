"""
Phase 1.2 — targets named in the plan/audit that have NO clean callable seam today.

Per the plan: "If a target has no clean callable seam, do NOT refactor to create one —
write a `# TODO Phase 2` note in the test file naming the target and skip it with a
reason." These are recorded here (skipped, not deleted/ignored silently) so Phase 2's
extraction work has an explicit paper trail and a place to land real tests once a seam
exists.
"""
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "00. BACKEND"))
import rules  # noqa: E402
import build_dashboard as bd  # noqa: E402


# RESOLVED in Phase 2.2: "replied / 내가 답한 detection" previously had no callable seam
# (it was inline in build_dashboard.build_data() as the `replied_threads` local). Phase
# 2.2 extracted it to rules.replied_thread_keys(rows, norm_subject), so this documented
# gap now lands as a real test. The extraction was proven byte-identical to the old
# inline algorithm on the live mailbox (151 threads, new==old). rules.replied_thread_keys
# is also characterized in test_rules_characterization.py; this test guards the seam at
# the documented-gap location so the paper trail resolves.
def test_replied_thread_detection_seam():
    rows = [
        {"제목": "RE: 프로젝트 A", "날짜": "2026-06-01", "구분": "받은메일"},
        {"제목": "프로젝트 A", "날짜": "2026-06-02", "구분": "보낸메일"},   # latest = sent → replied
        {"제목": "프로젝트 B", "날짜": "2026-06-03", "구분": "받은메일"},   # latest = received → not
        {"제목": "프로젝트 B", "날짜": "2026-06-01", "구분": "보낸메일"},
    ]
    replied = rules.replied_thread_keys(rows, bd.norm_subject)
    a_key = bd.norm_subject("프로젝트 A") or "프로젝트 A"
    b_key = bd.norm_subject("프로젝트 B") or "프로젝트 B"
    assert a_key in replied      # thread whose latest message I sent
    assert b_key not in replied  # thread whose latest message I received


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
