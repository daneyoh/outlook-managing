"""
Phase 1.2 characterization tests — pin CURRENT behavior of build_dashboard.py's pure
functions as golden tests, so Phase 1.5 / Phase 2 refactors can be verified
behavior-preserving.

Exceptions (assert CORRECTED, not current, behavior) per the plan:
  1. project_of dict-input: xfail'd until Phase 2.1 (see TestProjectOf).
  2. INTERNAL_DOMAIN-unset + MY_EMAIL-set fallback guard: asserts the *documented*
     or-fallback behavior. Phase 1.5.2 converted the frozen module-level
     INTERNAL_DOMAIN/MY_EMAIL constants into LIVE accessors
     (get_internal_domain / get_my_email); these tests were co-evolved to call the
     accessors while asserting the SAME expected values (fallback → MY_EMAIL domain),
     so the accessor conversion cannot silently drop the fallback.

No source files are modified by this test file.
"""
import datetime as _datetime_mod
from datetime import datetime, timedelta

import pytest

import build_dashboard


# ---------------------------------------------------------------------------
# norm_subject (build_dashboard.py:117)
# ---------------------------------------------------------------------------

class TestNormSubject:
    def test_strips_single_re_prefix(self):
        assert build_dashboard.norm_subject("Re: 회의 안건") == "회의 안건"

    def test_strips_repeated_mixed_prefixes(self):
        # Re:, Fwd:, 회신:, 답장: chained — current behavior strips them all, repeatedly.
        assert build_dashboard.norm_subject("Re: Fwd: 회신: 답장: 진행상황") == "진행상황"

    def test_strips_prefix_case_insensitively(self):
        assert build_dashboard.norm_subject("RE: hello") == "hello"
        assert build_dashboard.norm_subject("fw: hello") == "hello"

    def test_none_input_returns_empty_string(self):
        assert build_dashboard.norm_subject(None) == ""

    def test_no_prefix_returns_stripped_original(self):
        assert build_dashboard.norm_subject("  plain subject  ") == "plain subject"

    def test_empty_string_returns_empty_string(self):
        assert build_dashboard.norm_subject("") == ""


# ---------------------------------------------------------------------------
# fmt_date (build_dashboard.py:127)
# ---------------------------------------------------------------------------

class TestFmtDate:
    def test_formats_iso_datetime_with_z_suffix(self):
        assert build_dashboard.fmt_date("2026-07-02T09:30:00Z") == "2026-07-02 09:30"

    def test_formats_iso_datetime_without_z(self):
        assert build_dashboard.fmt_date("2026-07-02T09:30:00") == "2026-07-02 09:30"

    def test_empty_string_returns_empty_string(self):
        assert build_dashboard.fmt_date("") == ""

    def test_none_returns_empty_string(self):
        assert build_dashboard.fmt_date(None) == ""

    def test_unparseable_string_falls_back_to_slice(self):
        # Current (quirky) behavior: on ValueError, take first 16 chars and replace
        # the "T" with a space — even if the string isn't really ISO-ish.
        assert build_dashboard.fmt_date("not-a-date-at-all-long") == "not-a-date-at-al"


# ---------------------------------------------------------------------------
# _mk_deadline (build_dashboard.py:154)
# ---------------------------------------------------------------------------

class TestMkDeadline:
    def test_future_date_returned_as_is(self):
        future = datetime.now().date() + timedelta(days=10)
        result = build_dashboard._mk_deadline(future.year, future.month, future.day)
        assert result == future.isoformat()

    def test_invalid_date_returns_none(self):
        assert build_dashboard._mk_deadline(2026, 2, 30) is None

    def test_rolls_to_next_year_if_more_than_183_days_past(self):
        # A date more than 183 days in the past rolls forward one year.
        old = datetime.now().date() - timedelta(days=200)
        result = build_dashboard._mk_deadline(old.year, old.month, old.day)
        expected = None
        try:
            expected = old.replace(year=old.year + 1).isoformat()
        except ValueError:
            # Feb 29 edge case in a non-leap target year — _mk_deadline returns None.
            expected = None
        assert result == expected


# ---------------------------------------------------------------------------
# parse_deadline (build_dashboard.py:169)
# ---------------------------------------------------------------------------

class TestParseDeadline:
    def test_explicit_ymd_recognized_without_cue(self):
        assert build_dashboard.parse_deadline("공유 드립니다 2026-08-15 참고") == "2026-08-15"

    def test_md_with_cue_recognized(self):
        now = datetime.now()
        result = build_dashboard.parse_deadline("8/20까지 회신 부탁드립니다")
        assert result == build_dashboard._mk_deadline(now.year, 8, 20)

    def test_md_without_cue_not_recognized(self):
        assert build_dashboard.parse_deadline("회의는 8/20 에 있습니다") is None

    def test_ndays_relative_to_now(self):
        result = build_dashboard.parse_deadline("3일까지 제출해주세요")
        expected = (datetime.now() + timedelta(days=3)).date().isoformat()
        assert result == expected

    def test_empty_text_returns_none(self):
        assert build_dashboard.parse_deadline("") is None

    def test_none_text_returns_none(self):
        assert build_dashboard.parse_deadline(None) is None

    def test_korean_month_day_with_cue(self):
        # Quirk: "20일까지" itself matches _RE_NDAYS (N일까지/이내/내) BEFORE _RE_KMD
        # (M월 D일) is even tried — _RE_NDAYS is checked first in parse_deadline's
        # branch order. So "8월 20일까지" resolves via the N-days-from-now branch
        # (day=20 → now+20 days), NOT via the "8월" Korean-month-day branch. This is
        # current behavior worth pinning exactly because it's non-obvious.
        result = build_dashboard.parse_deadline("8월 20일까지 마감입니다")
        expected = (datetime.now() + timedelta(days=20)).date().isoformat()
        assert result == expected

    def test_korean_month_day_with_cue_but_no_trailing_nday_pattern(self):
        # To actually exercise the _RE_KMD (M월 D일) branch, the cue must be present
        # but NOT form an N일까지/이내/내 pattern immediately after the day digits.
        now = datetime.now()
        result = build_dashboard.parse_deadline("8월 20일 마감 예정입니다")
        assert result == build_dashboard._mk_deadline(now.year, 8, 20)


# ---------------------------------------------------------------------------
# _deadline_days (build_dashboard.py:203) — D-day calculation
# ---------------------------------------------------------------------------

class TestDeadlineDays:
    def test_future_date_returns_positive_days(self):
        future = (datetime.now().date() + timedelta(days=5)).isoformat()
        assert build_dashboard._deadline_days(future) == 5

    def test_past_date_returns_negative_days(self):
        past = (datetime.now().date() - timedelta(days=5)).isoformat()
        assert build_dashboard._deadline_days(past) == -5

    def test_today_returns_zero(self):
        today = datetime.now().date().isoformat()
        assert build_dashboard._deadline_days(today) == 0

    def test_none_returns_none(self):
        assert build_dashboard._deadline_days(None) is None

    def test_empty_string_returns_none(self):
        assert build_dashboard._deadline_days("") is None

    def test_malformed_iso_returns_none(self):
        assert build_dashboard._deadline_days("not-a-date") is None


# ---------------------------------------------------------------------------
# _parse_dt (build_dashboard.py:214)
# ---------------------------------------------------------------------------

class TestParseDt:
    def test_parses_z_suffixed_iso_and_strips_tzinfo(self):
        dt = build_dashboard._parse_dt("2026-07-02T09:30:00Z")
        assert dt == datetime(2026, 7, 2, 9, 30, 0)
        assert dt.tzinfo is None

    def test_parses_naive_iso(self):
        dt = build_dashboard._parse_dt("2026-07-02T09:30:00")
        assert dt == datetime(2026, 7, 2, 9, 30, 0)

    def test_empty_string_returns_none(self):
        assert build_dashboard._parse_dt("") is None

    def test_none_returns_none(self):
        assert build_dashboard._parse_dt(None) is None

    def test_malformed_string_returns_none(self):
        assert build_dashboard._parse_dt("not-a-datetime") is None


# ---------------------------------------------------------------------------
# load_project_rules (build_dashboard.py:225)
# ---------------------------------------------------------------------------

class TestLoadProjectRules:
    def test_reads_existing_dict_file(self, tmp_path, monkeypatch):
        rules_file = tmp_path / "widget_projects.json"
        rules_file.write_text('{"프로젝트A": ["키워드1"]}', encoding="utf-8")
        monkeypatch.setattr(build_dashboard, "PROJECTS_FILE", str(rules_file))
        assert build_dashboard.load_project_rules() == {"프로젝트A": ["키워드1"]}

    def test_missing_file_creates_empty_file_and_returns_empty_dict(self, tmp_path, monkeypatch):
        rules_file = tmp_path / "sub" / "widget_projects.json"
        monkeypatch.setattr(build_dashboard, "PROJECTS_FILE", str(rules_file))
        result = build_dashboard.load_project_rules()
        assert result == {}
        assert rules_file.exists()

    def test_non_dict_json_returns_empty_dict(self, tmp_path, monkeypatch):
        rules_file = tmp_path / "widget_projects.json"
        rules_file.write_text('["not", "a", "dict"]', encoding="utf-8")
        monkeypatch.setattr(build_dashboard, "PROJECTS_FILE", str(rules_file))
        assert build_dashboard.load_project_rules() == {}

    def test_malformed_json_returns_empty_dict(self, tmp_path, monkeypatch):
        rules_file = tmp_path / "widget_projects.json"
        rules_file.write_text("{not valid json", encoding="utf-8")
        monkeypatch.setattr(build_dashboard, "PROJECTS_FILE", str(rules_file))
        assert build_dashboard.load_project_rules() == {}


# ---------------------------------------------------------------------------
# project_of (build_dashboard.py:248) — list input is a normal golden test;
# dict input is xfail'd per the plan's mandatory exemption (Phase 2.1 bug fix).
# ---------------------------------------------------------------------------

class TestProjectOf:
    def test_bracket_tag_takes_priority_over_rules(self):
        row = {"제목": "[프로젝트X] 진행 상황 공유", "보낸사람": "", "받는사람": ""}
        rules = {"다른프로젝트": ["진행"]}
        assert build_dashboard.project_of(row, rules) == "프로젝트X"

    def test_list_input_matches_keyword_in_subject(self):
        """Current + intended behavior for legacy list-shaped rules: keyword found in
        normalized subject/sender/recipient text → matching project name."""
        row = {"제목": "월간 정산 요청", "보낸사람": "a@x.com", "받는사람": "me@x.com"}
        rules = {"정산팀": ["정산"]}
        assert build_dashboard.project_of(row, rules) == "정산팀"

    def test_list_input_no_match_returns_other(self):
        row = {"제목": "안녕하세요", "보낸사람": "a@x.com", "받는사람": "me@x.com"}
        rules = {"정산팀": ["정산"]}
        assert build_dashboard.project_of(row, rules) == "기타"

    def test_no_rules_returns_other(self):
        row = {"제목": "아무 제목", "보낸사람": "", "받는사람": ""}
        assert build_dashboard.project_of(row, {}) == "기타"

    def test_dict_input_matches_via_senders_field(self):
        """Phase 2.1 semantics: a dict-shaped project entry's `senders` list matches
        against the mail's 보낸사람/받는사람 (same match shape as
        build_dashboard.py's get_card_mails `any(s in sender for s in senders)`),
        even when keywords/subjects are empty (senders-only match by sender alone)."""
        row = {"제목": "안건 없음", "보낸사람": "vip@partner.com", "받는사람": "me@x.com"}
        rules = {"파트너프로젝트": {"senders": ["vip@partner.com"], "keywords": [], "subjects": []}}
        assert build_dashboard.project_of(row, rules) == "파트너프로젝트"

    def test_dict_input_matches_via_keywords_field(self):
        row = {"제목": "정산 마감 안내", "보낸사람": "a@x.com", "받는사람": "me@x.com"}
        rules = {"정산팀": {"senders": [], "keywords": ["정산"], "subjects": []}}
        assert build_dashboard.project_of(row, rules) == "정산팀"

    def test_dict_input_matches_via_recipient(self):
        """senders should also match against 받는사람 (recipient), per plan Step 1."""
        row = {"제목": "회신", "보낸사람": "other@x.com", "받는사람": "team@partner.com"}
        rules = {"파트너프로젝트": {"senders": ["team@partner.com"], "keywords": [], "subjects": []}}
        assert build_dashboard.project_of(row, rules) == "파트너프로젝트"

    def test_dict_input_matches_via_subjects_field(self):
        row = {"제목": "월간 리포트 공유", "보낸사람": "a@x.com", "받는사람": "me@x.com"}
        rules = {"리포트팀": {"senders": [], "keywords": [], "subjects": ["리포트"]}}
        assert build_dashboard.project_of(row, rules) == "리포트팀"

    def test_dict_input_no_match_returns_other(self):
        row = {"제목": "무관한 제목", "보낸사람": "a@x.com", "받는사람": "me@x.com"}
        rules = {"정산팀": {"senders": ["vip@partner.com"], "keywords": ["정산"], "subjects": []}}
        assert build_dashboard.project_of(row, rules) == "기타"


# ---------------------------------------------------------------------------
# has_action (build_dashboard.py:137) — bonus coverage, small pure function
# used directly by the TODO-classification path.
# ---------------------------------------------------------------------------

class TestHasAction:
    def test_action_keyword_in_subject_detected(self):
        row = {"제목": "검토 부탁드립니다", "본문요약": ""}
        assert build_dashboard.has_action(row) is True

    def test_no_action_keyword_returns_false(self):
        row = {"제목": "안녕하세요", "본문요약": "잘 지내시죠"}
        assert build_dashboard.has_action(row) is False


# ---------------------------------------------------------------------------
# _is_to_me (build_dashboard.py:117-124) — already a callable seam. Pinned here
# per Phase 2.2 target #4 before any consolidation touches its call sites.
# Depends on get_my_email() (LIVE accessor) and _my_group_addrs(); we monkeypatch
# both to make the test deterministic and independent of config.py.
# ---------------------------------------------------------------------------

class TestIsToMe:
    def test_my_email_in_to_field_true(self, monkeypatch):
        monkeypatch.setattr(build_dashboard, "get_my_email", lambda: "me@corp.com")
        monkeypatch.setattr(build_dashboard, "_my_group_addrs", lambda: [])
        assert build_dashboard._is_to_me("Me@Corp.com; other@x.com") is True

    def test_group_addr_in_to_field_true(self, monkeypatch):
        monkeypatch.setattr(build_dashboard, "get_my_email", lambda: "me@corp.com")
        monkeypatch.setattr(build_dashboard, "_my_group_addrs", lambda: ["team@corp.com"])
        assert build_dashboard._is_to_me("team@corp.com") is True

    def test_neither_present_false(self, monkeypatch):
        monkeypatch.setattr(build_dashboard, "get_my_email", lambda: "me@corp.com")
        monkeypatch.setattr(build_dashboard, "_my_group_addrs", lambda: ["team@corp.com"])
        assert build_dashboard._is_to_me("stranger@x.com") is False

    def test_empty_to_field_false(self, monkeypatch):
        monkeypatch.setattr(build_dashboard, "get_my_email", lambda: "me@corp.com")
        monkeypatch.setattr(build_dashboard, "_my_group_addrs", lambda: [])
        assert build_dashboard._is_to_me("") is False

    def test_none_to_field_false(self, monkeypatch):
        monkeypatch.setattr(build_dashboard, "get_my_email", lambda: "me@corp.com")
        monkeypatch.setattr(build_dashboard, "_my_group_addrs", lambda: [])
        assert build_dashboard._is_to_me(None) is False

    def test_empty_my_email_falls_through_to_groups(self, monkeypatch):
        # bool guard: empty my_email must not match; groups still checked.
        monkeypatch.setattr(build_dashboard, "get_my_email", lambda: "")
        monkeypatch.setattr(build_dashboard, "_my_group_addrs", lambda: ["team@corp.com"])
        assert build_dashboard._is_to_me("team@corp.com") is True
        assert build_dashboard._is_to_me("me@corp.com") is False


# ---------------------------------------------------------------------------
# Mandatory fallback-guard case (guards Phase 1.5.2):
# INTERNAL_DOMAIN unset + MY_EMAIL set → internal/external classification derives
# the internal domain from MY_EMAIL's domain (the or-fallback formerly at
# build_dashboard.py:34-35, now inside get_internal_domain()).
#
# Phase 1.5.2 CO-EVOLUTION: the frozen module-level constants INTERNAL_DOMAIN /
# MY_EMAIL are now LIVE accessors — get_internal_domain() / get_my_email(). These
# tests were updated to call the accessors instead of reading the (now-removed)
# module-level string attribute and reloading the module. The EXPECTED VALUES are
# unchanged (fallback → MY_EMAIL domain; internal predicate matches on domain).
# Because the accessor resolves live, monkeypatching config's MY_EMAIL is enough —
# no importlib.reload is needed; this also demonstrates the restart-free liveness.
# The inline predicate shape used in build_data() (build_dashboard.py) is exercised
# via the same accessor call, mirroring the production `is_internal = bool(dom) and
# dom in from_field` computation.
# ---------------------------------------------------------------------------

class TestInternalDomainFallbackGuard:
    def test_internal_domain_falls_back_to_my_email_domain_when_unset(self, monkeypatch):
        """Pins the or-fallback for real: when INTERNAL_DOMAIN is empty/unset and
        MY_EMAIL is set, get_internal_domain() derives the domain from MY_EMAIL.
        Phase 1.5.2 co-evolution: reads the LIVE accessor build_dashboard
        .get_internal_domain() instead of the removed module-level string attribute.
        The accessor resolves config live, so patching config's MY_EMAIL (with
        INTERNAL_DOMAIN blank) suffices — no module reload. If the accessor's
        or-fallback (or its nested live get_my_email call) were dropped, this fails.
        """
        import config

        # user_config.json must not shadow config for this test; the accessor's
        # precedence is user_config.json > config.py. Force the loader to return {}
        # so we exercise the config.py branch deterministically.
        monkeypatch.setattr(build_dashboard, "_load_user_config", lambda: {})
        monkeypatch.setattr(config, "MY_EMAIL", "user@internal-example.com")
        monkeypatch.setattr(config, "INTERNAL_DOMAIN", "", raising=False)

        assert build_dashboard.get_internal_domain() == "internal-example.com"

    def test_classification_predicate_uses_fallback_derived_domain(self, monkeypatch):
        """Exercises the inline is_internal predicate shape used in build_data()
        against a mail whose sender domain matches the MY_EMAIL-derived fallback
        domain. Phase 1.5.2 co-evolution: computes the domain via the LIVE accessor
        get_internal_domain() (fallback branch) rather than reading a monkeypatched
        module-level constant."""
        monkeypatch.setattr(build_dashboard, "_load_user_config", lambda: {})
        import config
        monkeypatch.setattr(config, "MY_EMAIL", "user@internal-example.com")
        monkeypatch.setattr(config, "INTERNAL_DOMAIN", "", raising=False)

        _dom = build_dashboard.get_internal_domain()
        from_field = "colleague@internal-example.com".lower()
        is_internal = bool(_dom) and _dom in from_field
        assert is_internal is True

    def test_classification_predicate_false_when_domain_does_not_match_fallback(self, monkeypatch):
        monkeypatch.setattr(build_dashboard, "_load_user_config", lambda: {})
        import config
        monkeypatch.setattr(config, "MY_EMAIL", "user@internal-example.com")
        monkeypatch.setattr(config, "INTERNAL_DOMAIN", "", raising=False)

        _dom = build_dashboard.get_internal_domain()
        from_field = "vendor@external-example.com".lower()
        is_internal = bool(_dom) and _dom in from_field
        assert is_internal is False
