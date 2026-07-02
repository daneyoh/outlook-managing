"""
Phase 1.2 characterization tests for the ad/spam ("광고") classification decision.

`_is_ad_key` (app.py:822) is a METHOD on the `Api` class, not a free function, and it
is side-effectful (reads JSON_FILE from disk). Per the plan, we do NOT refactor it into
a free function (that extraction is Phase 2) and we do NOT instantiate `Api` here.
Instead we pin the decision at the smallest callable seam that already exists today:
the module-level `_AD_RE` regex (app.py:88) and `_strip_ad` (app.py:91), which together
ARE the actual decision logic `_is_ad_key` delegates to (it uses `_AD_RE.match(...)` to
decide whether a title carries the ad marker, and `_strip_ad` to normalize it before
comparing keys). These two are free functions/module constants and safe to import.

`app.py` is safe to import: it documents (app.py:9-10) that `Api` must be importable
without creating a window, and `import webview` is a local import inside the
`if __name__ == "__main__":` block (app.py:1442), not a module-level import.
"""
import app


class TestAdRegexMatch:
    """_AD_RE (app.py:88) — decides whether a title's head carries an ad marker."""

    def test_matches_parenthesized_ad_marker(self):
        assert app._AD_RE.match("(광고) 특가 이벤트 안내") is not None

    def test_matches_bracketed_ad_marker(self):
        assert app._AD_RE.match("[광고] 특가 이벤트 안내") is not None

    def test_matches_bare_ad_marker_followed_by_colon(self):
        assert app._AD_RE.match("광고: 특가 이벤트 안내") is not None

    def test_does_not_match_word_containing_ad_as_substring(self):
        # "광고팀" (ad TEAM) must NOT be treated as an ad marker — the bare-form match
        # requires a separator (space/:/-) right after "광고".
        assert app._AD_RE.match("광고팀 회의 안내") is None

    def test_does_not_match_when_ad_marker_not_at_start(self):
        assert app._AD_RE.match("특가 이벤트 (광고) 안내") is None

    def test_does_not_match_plain_subject(self):
        assert app._AD_RE.match("정기 회의 안건 공유") is None


class TestStripAd:
    """_strip_ad (app.py:91) — repeatedly removes the ad-marker head, used by
    _is_ad_key to normalize titles before comparing them."""

    def test_strips_single_bracketed_marker(self):
        assert app._strip_ad("[광고] 특가 이벤트 안내") == "특가 이벤트 안내"

    def test_strips_repeated_markers(self):
        assert app._strip_ad("(광고)(광고) 특가 이벤트") == "특가 이벤트"

    def test_no_marker_returns_original_stripped(self):
        assert app._strip_ad("  일반 제목  ") == "일반 제목"

    def test_title_that_is_only_the_marker_keeps_original(self):
        # Quirk: if stripping would leave nothing, _strip_ad falls back to the
        # original (unstripped-of-whitespace) title rather than returning "".
        result = app._strip_ad("[광고]")
        assert result == "[광고]"

    def test_none_input_returns_empty_string(self):
        assert app._strip_ad(None) == ""

    def test_word_with_ad_substring_is_not_stripped(self):
        assert app._strip_ad("광고팀 회의 안내") == "광고팀 회의 안내"


class TestAdKeyDecisionSeam:
    """Exercises the same match-then-normalize sequence _is_ad_key performs
    (app.py:822-840), at the module-level seam, without touching JSON_FILE or
    instantiating Api. This pins the DECISION _is_ad_key makes for a given raw
    title vs. a candidate display key, so a Phase-2 extraction into a free
    function can be verified against this exact behavior."""

    def test_raw_title_with_ad_marker_normalizes_to_same_key_as_stripped_display_title(self):
        # Two genuinely different inputs, from two different call sites:
        # 1) the raw mailbox title, still carrying the ad marker _AD_RE matches.
        raw_title = "[광고] Re: 특가 이벤트 안내"
        # 2) an already-stripped display title (e.g. produced by an earlier
        # _strip_ad call at render time) — no marker, different string entirely.
        stripped_display_title = "특가 이벤트 안내"

        # This is the same normalization _is_ad_key applies to the raw mailbox
        # title before comparing: norm_subject(_strip_ad(raw)).
        norm_raw = app.build_dashboard.norm_subject(app._strip_ad(raw_title))
        # And the same normalization applied to the candidate display key.
        norm_display = app.build_dashboard.norm_subject(stripped_display_title)

        assert app._AD_RE.match(app.build_dashboard.norm_subject(raw_title)) is not None
        # A concrete literal expected key pins the result so a no-op regression
        # in _strip_ad/norm_subject (e.g. returning the input unchanged) fails.
        assert norm_raw == "특가 이벤트 안내"
        assert norm_raw == norm_display

    def test_raw_title_without_ad_marker_is_not_flagged(self):
        raw_title = "정기 회의 안건 공유"
        assert app._AD_RE.match(app.build_dashboard.norm_subject(raw_title)) is None
