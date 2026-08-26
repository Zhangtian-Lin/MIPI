from typing import Any, cast

from mipi.modules.search.domain import EventSearchHit, SearchMatchReason, SearchResults, escape_like
from mipi.shared.database import open_database


class PostgresSearchRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def search(self, query: str, *, limit: int) -> SearchResults:
        pattern = escape_like(query)
        with open_database(self._database_url) as connection:
            rows = connection.execute(
                """
                WITH candidates AS (
                    SELECT ep.projection,
                           ep.projection->>'title_zh' ILIKE %s ESCAPE '\\' AS title_match,
                           ep.projection->>'summary_zh' ILIKE %s ESCAPE '\\' AS summary_match,
                           EXISTS (
                               SELECT 1 FROM jsonb_array_elements(ep.projection->'evidence') ev
                               WHERE ev->'source_span'->>'quote_original' ILIKE %s ESCAPE '\\'
                           ) AS evidence_match,
                           EXISTS (
                               SELECT 1 FROM jsonb_array_elements(ep.projection->'evidence') ev
                               WHERE ev->>'source_name' ILIKE %s ESCAPE '\\'
                           ) AS source_match
                    FROM event_publications ep
                    WHERE ep.is_current
                )
                SELECT * FROM candidates
                WHERE title_match OR summary_match OR evidence_match OR source_match
                ORDER BY CASE WHEN title_match THEN 1 WHEN summary_match THEN 2
                              WHEN evidence_match THEN 3 ELSE 4 END,
                         projection->>'event_date' DESC NULLS LAST
                LIMIT %s
                """,
                (pattern, pattern, pattern, pattern, limit),
            ).fetchall()
        return SearchResults(
            query=query,
            events=tuple(self._to_hit(row, query=query) for row in rows),
        )

    @staticmethod
    def _to_hit(row: dict[str, Any], *, query: str) -> EventSearchHit:
        event = cast(dict[str, object], row["projection"])
        evidence = cast(list[dict[str, Any]], event.get("evidence", []))
        first_evidence = evidence[0] if evidence else {}
        query_folded = query.casefold()
        if row["title_match"]:
            reason: SearchMatchReason = "title_zh"
            excerpt = cast(str, event.get("title_zh", ""))
        elif row["summary_match"]:
            reason = "summary_zh"
            excerpt = cast(str, event.get("summary_zh", ""))
        elif row["evidence_match"]:
            reason = "evidence_original"
            match = next(
                (
                    item
                    for item in evidence
                    if query_folded
                    in cast(
                        str,
                        cast(dict[str, object], item.get("source_span", {})).get(
                            "quote_original", ""
                        ),
                    ).casefold()
                ),
                first_evidence,
            )
            excerpt = cast(
                str,
                cast(dict[str, object], match.get("source_span", {})).get("quote_original", ""),
            )
        else:
            reason = "source_name"
            match = next(
                (
                    item
                    for item in evidence
                    if query_folded in cast(str, item.get("source_name", "")).casefold()
                ),
                first_evidence,
            )
            excerpt = cast(str, match.get("source_name", ""))
        return EventSearchHit(event=event, match_reason=reason, match_excerpt=excerpt[:240])
