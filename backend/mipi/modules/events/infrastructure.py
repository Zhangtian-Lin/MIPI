from typing import Any, cast
from uuid import UUID

from psycopg.types.json import Jsonb

from mipi.modules.events.domain import (
    EventIngestionCandidate,
    EventNotFoundError,
    EventProjectionConflictError,
    EventProjectionInput,
    EventPublication,
    EventPublicationConflictError,
    EventRecord,
    EventSourceText,
    EventWorkbench,
    event_publication_blockers,
    request_fingerprint,
    validate_event_input,
)
from mipi.shared.database import open_database
from mipi.shared.ids import new_id


class PostgresEventRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def project(
        self,
        value: EventProjectionInput,
        *,
        actor_id: str,
        rule_version: str,
        idempotency_key: str,
    ) -> EventRecord:
        fingerprint = request_fingerprint({**value.__dict__, "event_date": str(value.event_date)})
        with open_database(self._database_url) as connection, connection.transaction():
            existing = connection.execute(
                "SELECT * FROM events WHERE projection_idempotency_key = %s",
                (idempotency_key,),
            ).fetchone()
            if existing is not None:
                if existing["projection_fingerprint"] != fingerprint:
                    raise EventProjectionConflictError("Idempotency key was reused with new input")
                return self._event_record(existing, evidence_count=1, duplicate=True)
            ingestion = connection.execute(
                """
                SELECT ir.id, ir.public_id, ir.processing_status, ir.document_version_id,
                       dv.text_original, dv.title_original, d.primary_language,
                       d.public_id AS document_public_id, d.canonical_url,
                       s.public_id AS source_public_id, s.name AS source_name,
                       s.source_grade, d.published_at, dv.version_number, dv.crawled_at
                FROM ingestion_records ir
                JOIN document_versions dv ON dv.id = ir.document_version_id
                JOIN documents d ON d.id = ir.document_id
                JOIN sources s ON s.id = ir.source_id
                WHERE ir.public_id = %s
                FOR UPDATE OF ir
                """,
                (value.ingestion_id,),
            ).fetchone()
            if ingestion is None:
                raise EventNotFoundError(value.ingestion_id)
            if ingestion["processing_status"] != "approved":
                raise EventProjectionConflictError("Ingestion must complete L2 review")
            original_text = cast(str | None, ingestion["text_original"])
            if original_text is None:
                raise EventProjectionConflictError("Preserved original text is unavailable")
            validate_event_input(value, original_text)
            event_uuid = UUID(new_id("EVT").removeprefix("EVT-"))
            event_id = f"EVT-{event_uuid}"
            claim_uuid = UUID(new_id("CLM").removeprefix("CLM-"))
            claim_id = f"CLM-{claim_uuid}"
            attributes = {
                "ingestion_id": value.ingestion_id,
                "industries": list(value.industries),
                "states": list(value.states),
                "model_id": value.model_id,
                "prompt_version": value.prompt_version,
            }
            connection.execute(
                """
                INSERT INTO events (
                    id, public_id, event_type, title_zh, summary_zh, event_date,
                    event_date_precision, fact_level, conflict, publication_status,
                    attributes, rule_version, created_by, projection_idempotency_key,
                    projection_fingerprint
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,'F1',%s,'canonical_private',%s,%s,%s,%s,%s)
                """,
                (
                    event_uuid,
                    event_id,
                    value.event_type,
                    value.title_zh.strip(),
                    value.summary_zh.strip(),
                    value.event_date,
                    value.event_date_precision,
                    value.conflict,
                    Jsonb(attributes),
                    rule_version,
                    actor_id,
                    idempotency_key,
                    fingerprint,
                ),
            )
            connection.execute(
                """
                INSERT INTO claims (
                    id, public_id, predicate, value_json, value_type, fact_level,
                    claim_status, valid_from, rule_version
                ) VALUES (%s,%s,'event.occurred',%s,'event','F1',%s,%s,%s)
                """,
                (
                    claim_uuid,
                    claim_id,
                    Jsonb(
                        {"title_zh": value.title_zh.strip(), "summary_zh": value.summary_zh.strip()}
                    ),
                    "conflict" if value.conflict else "active",
                    value.event_date,
                    rule_version,
                ),
            )
            span = {
                "start": value.span_start,
                "end": value.span_end,
                "quote_original": value.quote_original,
                "quote_zh": value.quote_zh,
                "model_id": value.model_id,
                "prompt_version": value.prompt_version,
            }
            connection.execute(
                """
                INSERT INTO claim_evidence (
                    claim_id, document_version_id, evidence_role, source_span,
                    independence_group, directness, extraction_confidence
                ) VALUES (%s,%s,'supports',%s,%s,1,1)
                """,
                (
                    claim_uuid,
                    ingestion["document_version_id"],
                    Jsonb(span),
                    f"source:{ingestion['source_public_id']}",
                ),
            )
            connection.execute(
                "INSERT INTO event_claims (event_id, claim_id) VALUES (%s,%s)",
                (event_uuid, claim_uuid),
            )
            connection.execute(
                """
                INSERT INTO audit_log (
                    actor_type, actor_id, action, object_type, object_id,
                    after_json, reason, task_id
                ) VALUES ('agent',%s,'event.projected','event',%s,%s,%s,%s)
                """,
                (
                    actor_id,
                    event_id,
                    Jsonb({"fact_level": "F1", **attributes}),
                    "Created a private L3 event with an exact source span.",
                    rule_version,
                ),
            )
            connection.execute(
                """INSERT INTO outbox (event_type, aggregate_type, aggregate_id, payload)
                   VALUES ('event.projected','event',%s,%s)""",
                (
                    event_uuid,
                    Jsonb({"event_id": event_id, "publication_status": "canonical_private"}),
                ),
            )
            row = connection.execute("SELECT * FROM events WHERE id = %s", (event_uuid,)).fetchone()
            assert row is not None
            return self._event_record(row, evidence_count=1)

    def publish(
        self,
        event_id: str,
        *,
        publisher_id: str,
        reason: str,
        rule_version: str,
        idempotency_key: str,
    ) -> EventPublication:
        fingerprint = request_fingerprint(
            {
                "event_id": event_id,
                "publisher_id": publisher_id,
                "reason": reason.strip(),
                "rule_version": rule_version,
            }
        )
        with open_database(self._database_url) as connection, connection.transaction():
            existing = connection.execute(
                "SELECT * FROM event_publications WHERE idempotency_key = %s", (idempotency_key,)
            ).fetchone()
            if existing is not None:
                if existing["request_fingerprint"] != fingerprint:
                    raise EventPublicationConflictError("Idempotency key was reused with new input")
                return EventPublication(
                    event_id=event_id, projection=existing["projection"], duplicate=True
                )
            row = connection.execute(
                self._event_evidence_sql() + " WHERE e.public_id = %s FOR UPDATE OF e",
                (event_id,),
            ).fetchone()
            if row is None:
                raise EventNotFoundError(event_id)
            record = self._event_record(row, evidence_count=1)
            blockers = event_publication_blockers(record, 1)
            if blockers:
                raise ValueError(blockers[0])
            publication_uuid = UUID(new_id("EVP").removeprefix("EVP-"))
            publication_id = f"EVP-{publication_uuid}"
            revision_row = connection.execute(
                """SELECT COALESCE(MAX(revision), 0) + 1 AS revision
                   FROM event_publications WHERE event_id = %s""",
                (row["id"],),
            ).fetchone()
            assert revision_row is not None
            revision = cast(int, revision_row["revision"])
            time_row = connection.execute("SELECT clock_timestamp() AS published_at").fetchone()
            assert time_row is not None
            published_at = time_row["published_at"]
            projection = self._projection(
                row,
                publication_id=publication_id,
                revision=revision,
                published_at=published_at.isoformat(),
            )
            connection.execute(
                """UPDATE event_publications SET is_current = false
                   WHERE event_id = %s AND is_current""",
                (row["id"],),
            )
            connection.execute(
                """
                INSERT INTO event_publications (
                    id, public_id, event_id, revision, projection, publisher_id,
                    publication_reason, rule_version, idempotency_key, request_fingerprint,
                    published_at
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    publication_uuid,
                    publication_id,
                    row["id"],
                    revision,
                    Jsonb(projection),
                    publisher_id,
                    reason.strip(),
                    rule_version,
                    idempotency_key,
                    fingerprint,
                    published_at,
                ),
            )
            connection.execute(
                """UPDATE events SET publication_status = 'published', updated_at = now()
                   WHERE id = %s""",
                (row["id"],),
            )
            connection.execute(
                """INSERT INTO audit_log (
                    actor_type, actor_id, action, object_type, object_id,
                    after_json, reason, task_id
                ) VALUES ('human',%s,'event.published','event',%s,%s,%s,%s)""",
                (
                    publisher_id,
                    event_id,
                    Jsonb({"publication_id": publication_id, "revision": revision}),
                    reason.strip(),
                    rule_version,
                ),
            )
            connection.execute(
                """INSERT INTO outbox (event_type, aggregate_type, aggregate_id, payload)
                   VALUES ('event.published','event',%s,%s)""",
                (
                    row["id"],
                    Jsonb(
                        {
                            "event_id": event_id,
                            "publication_id": publication_id,
                            "revision": revision,
                        }
                    ),
                ),
            )
            return EventPublication(event_id=event_id, projection=projection, duplicate=False)

    def workbench(self, *, limit: int) -> EventWorkbench:
        with open_database(self._database_url) as connection:
            ingestions = connection.execute(
                """
                SELECT ir.public_id, d.public_id AS document_public_id, s.name AS source_name,
                       s.source_grade, ir.canonical_url, dv.title_original, d.primary_language,
                       ir.created_at,
                       (SELECT count(*) FROM events e
                        WHERE e.attributes->>'ingestion_id' = ir.public_id) AS projected_event_count
                FROM ingestion_records ir
                JOIN documents d ON d.id = ir.document_id
                JOIN document_versions dv ON dv.id = ir.document_version_id
                JOIN sources s ON s.id = ir.source_id
                WHERE ir.processing_status = 'approved'
                ORDER BY ir.created_at DESC LIMIT %s
                """,
                (limit,),
            ).fetchall()
            rows = connection.execute(
                """
                SELECT e.*, ep.public_id AS publication_public_id, ep.revision,
                       (SELECT count(*) FROM event_claims ec
                        JOIN claim_evidence ce ON ce.claim_id=ec.claim_id
                        WHERE ec.event_id=e.id) AS evidence_count
                FROM events e LEFT JOIN event_publications ep ON ep.event_id=e.id AND ep.is_current
                ORDER BY e.created_at DESC LIMIT %s
                """,
                (limit,),
            ).fetchall()
        return EventWorkbench(
            eligible_ingestions=tuple(
                EventIngestionCandidate(
                    ingestion_id=cast(str, r["public_id"]),
                    document_id=cast(str, r["document_public_id"]),
                    source_name=cast(str, r["source_name"]),
                    source_grade=cast(str, r["source_grade"]),
                    canonical_url=cast(str, r["canonical_url"]),
                    title_original=cast(str | None, r["title_original"]),
                    language=cast(str | None, r["primary_language"]),
                    created_at=r["created_at"].isoformat(),
                    projected_event_count=cast(int, r["projected_event_count"]),
                )
                for r in ingestions
            ),
            events=tuple(
                self._event_record(r, evidence_count=cast(int, r["evidence_count"])) for r in rows
            ),
        )

    def get_source(self, ingestion_id: str) -> EventSourceText:
        with open_database(self._database_url) as connection:
            row = connection.execute(
                """
                SELECT ir.public_id, ir.processing_status, d.public_id AS document_public_id,
                       d.primary_language, dv.title_original, dv.text_original
                FROM ingestion_records ir
                JOIN documents d ON d.id=ir.document_id
                JOIN document_versions dv ON dv.id=ir.document_version_id
                WHERE ir.public_id=%s
                """,
                (ingestion_id,),
            ).fetchone()
        if row is None:
            raise EventNotFoundError(ingestion_id)
        if row["processing_status"] != "approved":
            raise EventProjectionConflictError("Ingestion must complete L2 review")
        if row["text_original"] is None:
            raise EventProjectionConflictError("Preserved original text is unavailable")
        return EventSourceText(
            ingestion_id=cast(str, row["public_id"]),
            document_id=cast(str, row["document_public_id"]),
            title_original=cast(str | None, row["title_original"]),
            language=cast(str | None, row["primary_language"]),
            text_original=cast(str, row["text_original"]),
        )

    def list_published(
        self, *, limit: int, industry: str | None, state: str | None, event_type: str | None
    ) -> tuple[dict[str, object], ...]:
        clauses = ["ep.is_current"]
        params: list[object] = []
        if industry:
            clauses.append("ep.projection->'industries' ? %s")
            params.append(industry)
        if state:
            clauses.append("ep.projection->'states' ? %s")
            params.append(state)
        if event_type:
            clauses.append("ep.projection->>'event_type' = %s")
            params.append(event_type)
        params.append(limit)
        with open_database(self._database_url) as connection:
            rows = connection.execute(
                f"SELECT projection FROM event_publications ep WHERE {' AND '.join(clauses)} "
                "ORDER BY projection->>'event_date' DESC NULLS LAST, published_at DESC LIMIT %s",
                tuple(params),
            ).fetchall()
        return tuple(cast(dict[str, object], row["projection"]) for row in rows)

    def get_published(self, event_id: str) -> dict[str, object] | None:
        with open_database(self._database_url) as connection:
            row = connection.execute(
                """SELECT ep.projection FROM event_publications ep JOIN events e ON e.id=ep.event_id
                   WHERE e.public_id=%s AND ep.is_current""",
                (event_id,),
            ).fetchone()
        return None if row is None else cast(dict[str, object], row["projection"])

    @staticmethod
    def _event_record(
        row: dict[str, Any], *, evidence_count: int, duplicate: bool = False
    ) -> EventRecord:
        attributes = cast(dict[str, object], row.get("attributes") or {})
        record = EventRecord(
            event_id=cast(str, row["public_id"]),
            ingestion_id=cast(str, attributes.get("ingestion_id", "")),
            publication_status=cast(str, row["publication_status"]),
            fact_level=cast(str, row["fact_level"]),
            title_zh=cast(str, row["title_zh"]),
            summary_zh=cast(str, row["summary_zh"] or ""),
            event_type=cast(str, row["event_type"]),
            event_date=None if row["event_date"] is None else row["event_date"].isoformat(),
            industries=tuple(cast(list[str], attributes.get("industries", []))),
            states=tuple(cast(list[str], attributes.get("states", []))),
            conflict=cast(bool, row["conflict"]),
            blockers=(),
            publication_id=cast(str | None, row.get("publication_public_id")),
            revision=cast(int | None, row.get("revision")),
            duplicate=duplicate,
        )
        return EventRecord(
            **{**record.__dict__, "blockers": event_publication_blockers(record, evidence_count)}
        )

    @staticmethod
    def _event_evidence_sql() -> str:
        return """
            SELECT e.*, c.public_id AS claim_public_id, ce.source_span, ce.independence_group,
                   d.public_id AS document_public_id, d.primary_language, d.published_at,
                   d.canonical_url, dv.version_number, dv.crawled_at,
                   s.public_id AS source_public_id, s.name AS source_name, s.source_grade
            FROM events e
            JOIN event_claims ec ON ec.event_id=e.id
            JOIN claims c ON c.id=ec.claim_id
            JOIN claim_evidence ce ON ce.claim_id=c.id AND ce.evidence_role='supports'
            JOIN document_versions dv ON dv.id=ce.document_version_id
            JOIN documents d ON d.id=dv.document_id
            JOIN sources s ON s.id=d.source_id
        """

    @staticmethod
    def _projection(
        row: dict[str, Any], *, publication_id: str, revision: int, published_at: str
    ) -> dict[str, object]:
        attributes = cast(dict[str, object], row["attributes"])
        return {
            "event_id": row["public_id"],
            "publication_id": publication_id,
            "revision": revision,
            "published_at": published_at,
            "event_type": row["event_type"],
            "title_zh": row["title_zh"],
            "summary_zh": row["summary_zh"],
            "event_date": None if row["event_date"] is None else row["event_date"].isoformat(),
            "event_date_precision": row["event_date_precision"],
            "fact_level": row["fact_level"],
            "conflict": row["conflict"],
            "industries": attributes["industries"],
            "states": attributes["states"],
            "independent_source_count": 1,
            "caveats": ["该事件目前仅由一个可识别来源支持。"] if row["fact_level"] == "F1" else [],
            "evidence": [
                {
                    "claim_id": row["claim_public_id"],
                    "source_id": row["source_public_id"],
                    "source_name": row["source_name"],
                    "source_grade": row["source_grade"],
                    "document_id": row["document_public_id"],
                    "document_version": row["version_number"],
                    "canonical_url": row["canonical_url"],
                    "language": row["primary_language"],
                    "published_at": None
                    if row["published_at"] is None
                    else row["published_at"].isoformat(),
                    "crawled_at": row["crawled_at"].isoformat(),
                    "source_span": row["source_span"],
                    "independence_group": row["independence_group"],
                }
            ],
        }
