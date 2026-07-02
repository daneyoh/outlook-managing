"""
Phase 2.2 characterization tests for rules.py — the single-source classification module.

Per the IRON RULE in the Phase 2.2 task: for each predicate extracted into rules.py we
FIRST pin its CURRENT behavior (representative + edge), against the current
implementation, THEN create the rules.py function (behavior-identical), THEN migrate
call sites. These tests target the rules.py functions and also assert they match the
pre-extraction expressions exactly.

Modules imported: `rules` (new), `app`, `build_dashboard`. All are import-safe
(app documents Api is importable without a window; build_dashboard reads config live).
"""
import app
import build_dashboard
import rules


# ---------------------------------------------------------------------------
# is_urgent — extracted from app._is_urgent (app.py:73-75).
# URGENT_KEYWORDS = ["마감", "긴급", "urgent", "asap"]
# ---------------------------------------------------------------------------

class TestIsUrgent:
    def test_keyword_in_title_detected(self):
        assert rules.is_urgent("긴급 회신 요망", "") is True

    def test_english_keyword_case_insensitive(self):
        assert rules.is_urgent("Please review ASAP", "") is True

    def test_keyword_in_summary_detected(self):
        assert rules.is_urgent("주간 보고", "이번 주 마감입니다") is True

    def test_no_keyword_returns_false(self):
        assert rules.is_urgent("안녕하세요", "잘 지내시죠") is False

    def test_non_string_inputs_coerced(self):
        # app._is_urgent does str(title) + " " + str(summary); None must not crash.
        assert rules.is_urgent(None, None) is False

    def test_urgent_keyword_list_is_the_four_item_urgent_set(self):
        assert rules.URGENT_KEYWORDS == ["마감", "긴급", "urgent", "asap"]

    def test_matches_legacy_app_is_urgent_expression(self):
        # Behavior-identical to the pre-extraction app._is_urgent expression.
        for title, summary in [
            ("긴급 회신 요망", ""),
            ("Please review ASAP", ""),
            ("주간 보고", "이번 주 마감입니다"),
            ("안녕하세요", "잘 지내시죠"),
            ("URGENT", "마감"),
            (123, 456),
        ]:
            expected = any(k in (str(title) + " " + str(summary)).lower()
                           for k in ["마감", "긴급", "urgent", "asap"])
            assert rules.is_urgent(title, summary) is expected


# ---------------------------------------------------------------------------
# has_action — extracted from build_dashboard.has_action (build_dashboard.py:185-187).
# ACTION_KEYWORDS is a 24+ item superset; original took a row dict.
# ---------------------------------------------------------------------------

class TestHasAction:
    def test_action_keyword_in_title_detected(self):
        assert rules.has_action("검토 부탁드립니다", "") is True

    def test_action_keyword_in_summary_detected(self):
        assert rules.has_action("주간 보고", "회신 바랍니다") is True

    def test_english_action_keyword_case_insensitive(self):
        assert rules.has_action("Please REVIEW this", "") is True

    def test_no_action_keyword_returns_false(self):
        assert rules.has_action("안녕하세요", "잘 지내시죠") is False

    def test_action_keyword_list_matches_source(self):
        assert rules.ACTION_KEYWORDS == [
            "요청", "부탁", "검토", "확인", "회신", "답장", "회답", "마감", "기한",
            "까지", "제출", "전달", "공유", "승인", "결재", "피드백", "수정", "보완",
            "필요", "협조", "문의", "답변", "리뷰", "asap", "please", "review",
            "request", "deadline", "urgent", "확인부탁", "회신바랍니다",
        ]

    def test_matches_legacy_build_dashboard_has_action_expression(self):
        # build_dashboard.has_action(row) uses 제목 + " " + 본문요약; the extracted
        # rules.has_action(title, summary) must equal it for every case, and the
        # build_dashboard.has_action delegator must equal both.
        for title, summary in [
            ("검토 부탁드립니다", ""),
            ("주간 보고", "회신 바랍니다"),
            ("Please REVIEW this", ""),
            ("안녕하세요", "잘 지내시죠"),
        ]:
            text = (title + " " + summary).lower()
            expected = any(k.lower() in text for k in rules.ACTION_KEYWORDS)
            assert rules.has_action(title, summary) is expected
            assert build_dashboard.has_action({"제목": title, "본문요약": summary}) is expected


# ---------------------------------------------------------------------------
# is_from_internal — extracted from the inline `_internal_domain in from_field`
# comparison at build_dashboard.py:428-429 and app.py:681.
# Semantics pinned: case sensitivity, empty-domain → False, substring match.
# ---------------------------------------------------------------------------

class TestIsFromInternal:
    def test_domain_substring_match_true(self):
        assert rules.is_from_internal("alice@corp.com", "corp.com") is True

    def test_domain_not_present_false(self):
        assert rules.is_from_internal("alice@other.com", "corp.com") is False

    def test_empty_domain_returns_false(self):
        # Empty internal_domain must never match anything (guards the bool(dom) gate).
        assert rules.is_from_internal("alice@corp.com", "") is False

    def test_none_domain_returns_false(self):
        assert rules.is_from_internal("alice@corp.com", None) is False

    def test_from_field_lowercased_before_compare(self):
        # from_field is lowercased; internal_domain is passed already-lowercased by
        # callers (get_internal_domain returns .lower()). A mixed-case from_field with
        # a lowercase domain still matches.
        assert rules.is_from_internal("Alice@CORP.com", "corp.com") is True

    def test_none_from_field_returns_false(self):
        assert rules.is_from_internal(None, "corp.com") is False

    def test_substring_semantics_partial_domain(self):
        # Pure substring match (no token boundary) — pins current behavior exactly.
        assert rules.is_from_internal("x@sub.corp.com", "corp.com") is True

    def test_matches_legacy_inline_expression(self):
        for from_field, dom in [
            ("alice@corp.com", "corp.com"),
            ("alice@other.com", "corp.com"),
            ("alice@corp.com", ""),
            ("Alice@CORP.com", "corp.com"),
        ]:
            expected = bool(dom) and dom in (from_field or "").lower()
            assert rules.is_from_internal(from_field, dom) is expected


# ---------------------------------------------------------------------------
# is_external_request — extracted from build_dashboard.build_data()'s
# `"참조요청": (not to_me) and name_match` (build_dashboard.py:456-457).
# ---------------------------------------------------------------------------

class TestIsExternalRequest:
    def test_not_to_me_and_name_match_true(self):
        assert rules.is_external_request(is_internal=False, to_me=False, name_match=True) is True

    def test_to_me_makes_it_false(self):
        assert rules.is_external_request(is_internal=False, to_me=True, name_match=True) is False

    def test_no_name_match_false(self):
        assert rules.is_external_request(is_internal=False, to_me=False, name_match=False) is False

    def test_is_internal_flag_does_not_affect_result(self):
        # The 참조요청 expression itself is (not to_me) and name_match — is_internal is
        # not part of it (the counts['외부요청'] combination lives in app.py get_view).
        assert (rules.is_external_request(is_internal=True, to_me=False, name_match=True)
                == rules.is_external_request(is_internal=False, to_me=False, name_match=True))

    def test_matches_legacy_expression(self):
        for to_me in (True, False):
            for name_match in (True, False):
                expected = (not to_me) and name_match
                assert rules.is_external_request(False, to_me, name_match) is expected


# ---------------------------------------------------------------------------
# replied_thread_keys — extracted from build_dashboard.build_data()'s inline
# replied_threads (build_dashboard.py:412-420): per normalized-subject thread, the
# LATEST message's 구분 == "보낸메일" → replied.
#
# NOTE: this is DISTINCT from weekly_review.py:155-169's "회신한 대화" algorithm
# (which is time-windowed and requires a prior received message). They are NOT the
# same algorithm — see test_replied_algorithms_are_distinct below and the Phase 2.2
# report. weekly_review is intentionally NOT migrated to this function.
# ---------------------------------------------------------------------------

class TestRepliedThreadKeys:
    def test_latest_sent_thread_is_replied(self):
        rows = [
            {"제목": "안건 A", "구분": "받은메일", "날짜": "2026-06-01T10:00:00"},
            {"제목": "Re: 안건 A", "구분": "보낸메일", "날짜": "2026-06-02T10:00:00"},
        ]
        # norm_subject strips "Re:" so both collapse to "안건 A"; latest is 보낸메일.
        assert rules.replied_thread_keys(rows, build_dashboard.norm_subject) == {"안건 A"}

    def test_latest_received_thread_is_not_replied(self):
        rows = [
            {"제목": "안건 B", "구분": "보낸메일", "날짜": "2026-06-01T10:00:00"},
            {"제목": "Re: 안건 B", "구분": "받은메일", "날짜": "2026-06-02T10:00:00"},
        ]
        assert rules.replied_thread_keys(rows, build_dashboard.norm_subject) == set()

    def test_tie_date_last_writer_wins_dict_order(self):
        # Equal dates: `dt > latest_date[k]` is strict, so the FIRST-seen at that date
        # is kept (later equal ones do not overwrite). Pin this exact quirk.
        rows = [
            {"제목": "안건 C", "구분": "보낸메일", "날짜": "2026-06-01T10:00:00"},
            {"제목": "안건 C", "구분": "받은메일", "날짜": "2026-06-01T10:00:00"},
        ]
        # First seen at that date is 보낸메일 → stays 보낸메일 → replied.
        assert rules.replied_thread_keys(rows, build_dashboard.norm_subject) == {"안건 C"}

    def test_empty_rows_returns_empty_set(self):
        assert rules.replied_thread_keys([], build_dashboard.norm_subject) == set()

    def test_empty_norm_subject_falls_back_to_raw_title(self):
        # key = norm_subject(제목) or 제목; a title that norm_subject empties uses raw.
        rows = [{"제목": "Re:", "구분": "보낸메일", "날짜": "2026-06-01T10:00:00"}]
        # norm_subject("Re:") -> "" so key falls back to raw "Re:".
        assert rules.replied_thread_keys(rows, build_dashboard.norm_subject) == {"Re:"}

    def test_matches_legacy_build_dashboard_inline_algorithm(self):
        # Replica of build_dashboard.py:412-420, asserted identical on mixed data.
        rows = [
            {"제목": "T1", "구분": "받은메일", "날짜": "2026-06-01T10:00:00"},
            {"제목": "T1", "구분": "보낸메일", "날짜": "2026-06-03T10:00:00"},
            {"제목": "T2", "구분": "보낸메일", "날짜": "2026-06-01T10:00:00"},
            {"제목": "T2", "구분": "받은메일", "날짜": "2026-06-05T10:00:00"},
            {"제목": "T3", "구분": "보낸메일", "날짜": "2026-06-02T10:00:00"},
        ]
        latest_date, latest_dir = {}, {}
        for r in rows:
            k = build_dashboard.norm_subject(r.get("제목", "")) or r.get("제목", "")
            dt = r.get("날짜", "") or ""
            if k not in latest_date or dt > latest_date[k]:
                latest_date[k] = dt
                latest_dir[k] = r.get("구분", "")
        expected = {k for k, d in latest_dir.items() if d == "보낸메일"}
        assert rules.replied_thread_keys(rows, build_dashboard.norm_subject) == expected


class TestRepliedAlgorithmsAreDistinct:
    """Guards the Phase 2.2 decision NOT to consolidate weekly_review into
    rules.replied_thread_keys: the two 'replied' notions differ. A thread whose only
    message is an old sent mail (no prior received) is 'replied' under
    build_dashboard's latest-direction rule but NOT under weekly_review's
    'sent-in-last-7d with an earlier received' rule."""

    def test_lone_old_sent_mail_is_replied_only_under_build_dashboard_rule(self):
        rows = [{"제목": "V", "구분": "보낸메일", "날짜": "2000-01-01T00:00:00"}]
        # build_dashboard latest-direction rule → replied.
        assert rules.replied_thread_keys(rows, build_dashboard.norm_subject) == {"V"}
        # weekly_review rule (inline replica): not in last 7d AND no earlier received.
        from datetime import datetime, timedelta
        from collections import defaultdict
        now = datetime.now()
        week_ago = now - timedelta(days=7)
        sent_recent = [r for r in rows
                       if r.get("구분") == "보낸메일"
                       and (build_dashboard._parse_dt(r.get("날짜", "")) or datetime.min) >= week_ago]
        recv_dts = defaultdict(list)
        wr_keys = set()
        for s in sent_recent:
            sdt = build_dashboard._parse_dt(s.get("날짜", ""))
            key = build_dashboard.norm_subject(s.get("제목", ""))
            if sdt and any(rd < sdt for rd in recv_dts.get(key, [])):
                wr_keys.add(key)
        assert wr_keys == set()
