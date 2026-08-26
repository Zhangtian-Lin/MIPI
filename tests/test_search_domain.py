import pytest
from mipi.modules.search.domain import escape_like, normalize_query
from mipi.modules.search.infrastructure import PostgresSearchRepository


def test_search_query_normalizes_whitespace_without_changing_language() -> None:
    assert normalize_query("  data   pusat  ") == "data pusat"
    assert normalize_query("半导体 项目") == "半导体 项目"


def test_search_query_requires_two_visible_characters() -> None:
    with pytest.raises(ValueError, match="at least 2"):
        normalize_query(" a ")


def test_search_escapes_sql_like_wildcards() -> None:
    assert escape_like(r"50%_test\path") == r"%50\%\_test\\path%"


def test_search_explanation_uses_the_evidence_that_actually_matched() -> None:
    row = {
        "projection": {
            "title_zh": "测试事件标题",
            "summary_zh": "测试事件摘要",
            "evidence": [
                {"source_name": "First", "source_span": {"quote_original": "unrelated"}},
                {"source_name": "Second", "source_span": {"quote_original": "Johor project"}},
            ],
        },
        "title_match": False,
        "summary_match": False,
        "evidence_match": True,
        "source_match": False,
    }

    hit = PostgresSearchRepository._to_hit(row, query="johor")

    assert hit.match_reason == "evidence_original"
    assert hit.match_excerpt == "Johor project"
