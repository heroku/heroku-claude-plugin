"""Unit tests for pure functions in scripts/check_references.py"""

import sys
from datetime import date
from pathlib import Path

import pytest

# check_references.py lives at repo root of scripts/, not in a package —
# add scripts/ to path so we can import it directly.
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "scripts"))

import check_references as cr


# ---------------------------------------------------------------------------
# _parse_source_header
# ---------------------------------------------------------------------------

class TestParseSourceHeader:
    def test_single_header(self):
        content = "<!-- Source: https://example.com/page — verified 2025-01-15 -->"
        result = cr._parse_source_header(content)
        assert result == [("https://example.com/page", date(2025, 1, 15))]

    def test_multiple_headers(self):
        content = (
            "<!-- Source: https://a.com — verified 2025-01-01 -->\n"
            "Some content\n"
            "<!-- Source: https://b.com/path — verified 2024-06-30 -->\n"
        )
        result = cr._parse_source_header(content)
        assert len(result) == 2
        assert result[0] == ("https://a.com", date(2025, 1, 1))
        assert result[1] == ("https://b.com/path", date(2024, 6, 30))

    def test_no_header_returns_empty(self):
        content = "# Just a regular markdown file\n\nNo source header here."
        result = cr._parse_source_header(content)
        assert result == []

    def test_url_with_query_string(self):
        content = "<!-- Source: https://example.com/page?foo=bar — verified 2025-03-10 -->"
        result = cr._parse_source_header(content)
        assert result[0][0] == "https://example.com/page?foo=bar"

    def test_date_parsed_correctly(self):
        content = "<!-- Source: https://example.com — verified 2023-12-31 -->"
        result = cr._parse_source_header(content)
        assert result[0][1] == date(2023, 12, 31)

    def test_extra_whitespace_in_comment(self):
        content = "<!--  Source:  https://example.com  —  verified  2025-01-15  -->"
        result = cr._parse_source_header(content)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# _is_stale
# ---------------------------------------------------------------------------

class TestIsStale:
    def test_stale_beyond_threshold(self):
        old_date = date(2020, 1, 1)
        assert cr._is_stale(old_date, 30) is True

    def test_fresh_within_threshold(self):
        fresh_date = date.today()
        assert cr._is_stale(fresh_date, 30) is False

    def test_exactly_at_threshold_is_not_stale(self):
        from datetime import timedelta
        threshold = 30
        exactly_at = date.today() - timedelta(days=threshold)
        assert cr._is_stale(exactly_at, threshold) is False

    def test_one_day_over_threshold_is_stale(self):
        from datetime import timedelta
        threshold = 30
        one_over = date.today() - timedelta(days=threshold + 1)
        assert cr._is_stale(one_over, threshold) is True

    def test_zero_threshold(self):
        # Any date before today is stale with threshold=0
        from datetime import timedelta
        yesterday = date.today() - timedelta(days=1)
        assert cr._is_stale(yesterday, 0) is True

    def test_custom_threshold(self):
        from datetime import timedelta
        ninety_days_ago = date.today() - timedelta(days=90)
        assert cr._is_stale(ninety_days_ago, 60) is True
        assert cr._is_stale(ninety_days_ago, 120) is False


# ---------------------------------------------------------------------------
# _update_date_stamp
# ---------------------------------------------------------------------------

class TestUpdateDateStamp:
    def test_updates_matching_url(self):
        content = "<!-- Source: https://example.com — verified 2020-01-01 -->"
        result = cr._update_date_stamp(content, "https://example.com", "2025-06-15")
        assert "verified 2025-06-15" in result
        assert "verified 2020-01-01" not in result

    def test_does_not_update_non_matching_url(self):
        content = (
            "<!-- Source: https://a.com — verified 2020-01-01 -->\n"
            "<!-- Source: https://b.com — verified 2021-06-01 -->\n"
        )
        result = cr._update_date_stamp(content, "https://a.com", "2025-01-01")
        assert "https://b.com — verified 2021-06-01" in result

    def test_url_preserved_in_output(self):
        content = "<!-- Source: https://example.com/long/path — verified 2020-01-01 -->"
        result = cr._update_date_stamp(content, "https://example.com/long/path", "2025-01-01")
        assert "https://example.com/long/path" in result

    def test_multiple_headers_only_target_updated(self):
        content = (
            "<!-- Source: https://a.com — verified 2020-01-01 -->\n"
            "<!-- Source: https://b.com — verified 2021-06-01 -->\n"
        )
        result = cr._update_date_stamp(content, "https://a.com", "2025-03-01")
        assert "https://a.com — verified 2025-03-01" in result
        assert "https://b.com — verified 2021-06-01" in result

    def test_no_match_returns_original(self):
        content = "<!-- Source: https://example.com — verified 2020-01-01 -->"
        result = cr._update_date_stamp(content, "https://other.com", "2025-01-01")
        assert result == content
