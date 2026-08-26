from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, cast
from uuid import UUID

from psycopg.types.json import Jsonb

from mipi.modules.documents.domain import DocumentVersionRecord, L2PublicationStatus
from mipi.modules.ingestion.domain import (
    CollectionRelevance,
    FactLevel,
    IdempotencyConflictError,
    IngestionNotFoundError,
    IngestionRecord,
    IngestionResult,
    IngestionSubmission,
    ProcessingStatus,
    RiskLevel,
)
from mipi.shared.database import open_database
from mipi.shared.ids import new_id


class PostgresIngestionRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    @contextmanager
    def idempotency_lock(self, key: str) -> Iterator[None]:
        with open_database(self._database_url) as connection:
            connection.execute("SELECT pg_advisory_lock(hashtextextended(%s, 0))", (key,))
            try:
                yield
            finally:
                connection.execute("SELECT pg_advisory_unlock(hashtextextended(%s, 0))", (key,))

    def find_by_idempotency_key(self, key: str) -> IngestionRecord | None:
        with open_database(self._database_url) as connection:
            row = connection.execute(self._select_sql("ir.idempotency_key = %s"), (key,)).fetchone()
        return None if row is None else self._to_record(row)

    def save(
        self,
        submission: IngestionSubmission,
        *,
        document: DocumentVersionRecord,
        source_internal_id: UUID,
        canonical_url: str,
        source_grade: str,
        review_flags: tuple[str, ...],
        processing_status: str,
        risk_level: str,
    ) -> IngestionResult:
        with open_database(self._database_url) as connection, connection.transaction():
            existing_row = connection.execute(
                self._select_sql("ir.idempotency_key = %s"),
                (submission.idempotency_key,),
            ).fetchone()
            if existing_row is not None:
                existing = self._to_record(existing_row)
                if (
                    existing.source_id == submission.source_id
                    and existing.canonical_url == canonical_url
                    and existing.content_hash == submission.content_hash
                ):
                    return IngestionResult(record=existing, duplicate=True)
                raise IdempotencyConflictError(submission.idempotency_key)

            ingestion_internal_id = UUID(str(new_id("ING").removeprefix("ING-")))
            ingestion_public_id = f"ING-{ingestion_internal_id}"
            review_internal_id = UUID(str(new_id("REV").removeprefix("REV-")))
            review_public_id = f"REV-{review_internal_id}"
            raw_object_uri = document.raw_object_uri
            connection.execute(
                """
                INSERT INTO ingestion_records (
                    id, public_id, contract_version, task_id, run_id, idempotency_key,
                    source_id, document_id, document_version_id, submitted_url,
                    canonical_url, content_hash, raw_object_uri, collection_relevance,
                    verification_hint, publication_status, processing_status,
                    review_flags, submitted_payload
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    ingestion_internal_id,
                    ingestion_public_id,
                    submission.contract_version,
                    submission.task_id,
                    submission.run_id,
                    submission.idempotency_key,
                    source_internal_id,
                    document.document_internal_id,
                    document.version_internal_id,
                    submission.url,
                    canonical_url,
                    submission.content_hash,
                    raw_object_uri,
                    submission.collection_relevance,
                    submission.verification_hint,
                    submission.publication_status,
                    processing_status,
                    Jsonb(list(review_flags)),
                    Jsonb(self._submitted_payload(submission)),
                ),
            )
            review_status = "quarantined" if processing_status == "quarantined" else "queued"
            connection.execute(
                """
                INSERT INTO review_tasks (
                    id, public_id, review_type, risk_level, object_type, object_id, status
                )
                VALUES (%s, %s, 'ingestion_candidate', %s, 'ingestion_record', %s, %s)
                """,
                (
                    review_internal_id,
                    review_public_id,
                    risk_level,
                    ingestion_internal_id,
                    review_status,
                ),
            )
            connection.execute(
                """
                INSERT INTO audit_log (
                    actor_type, actor_id, action, object_type, object_id,
                    after_json, reason, task_id
                )
                VALUES ('agent', %s, 'ingestion.accepted', 'ingestion_record', %s, %s, %s, %s)
                """,
                (
                    submission.run_id or submission.task_id,
                    ingestion_public_id,
                    Jsonb(
                        {
                            "source_id": submission.source_id,
                            "document_id": document.document_public_id,
                            "content_hash": submission.content_hash,
                            "processing_status": processing_status,
                            "review_flags": list(review_flags),
                        }
                    ),
                    "Stored at L2 and routed to review; not publication-authorized.",
                    submission.task_id,
                ),
            )
            connection.execute(
                """
                INSERT INTO outbox (event_type, aggregate_type, aggregate_id, payload)
                VALUES ('ingestion.candidate.created', 'ingestion_record', %s, %s)
                """,
                (
                    ingestion_internal_id,
                    Jsonb(
                        {
                            "ingestion_id": ingestion_public_id,
                            "review_task_id": review_public_id,
                        }
                    ),
                ),
            )
            row = connection.execute(
                self._select_sql("ir.id = %s"), (ingestion_internal_id,)
            ).fetchone()
            assert row is not None
            return IngestionResult(record=self._to_record(row), duplicate=False)

    def get(self, public_id: str) -> IngestionRecord:
        with open_database(self._database_url) as connection:
            row = connection.execute(self._select_sql("ir.public_id = %s"), (public_id,)).fetchone()
        if row is None:
            raise IngestionNotFoundError(public_id)
        return self._to_record(row)

    def list(self, *, limit: int, status: str | None) -> list[IngestionRecord]:
        where = "TRUE" if status is None else "ir.processing_status = %s"
        parameters: tuple[object, ...] = (limit,) if status is None else (status, limit)
        with open_database(self._database_url) as connection:
            rows = connection.execute(
                self._select_sql(where) + " ORDER BY ir.created_at DESC LIMIT %s",
                parameters,
            ).fetchall()
        return [self._to_record(row) for row in rows]

    @staticmethod
    def _select_sql(where: str) -> str:
        return f"""
            SELECT ir.*, s.public_id AS source_public_id, s.name AS source_name,
                   s.source_grade, d.public_id AS document_public_id,
                   dv.version_number, rt.public_id AS review_task_public_id,
                   rt.status AS review_status, rt.risk_level
            FROM ingestion_records ir
            JOIN sources s ON s.id = ir.source_id
            JOIN documents d ON d.id = ir.document_id
            JOIN document_versions dv ON dv.id = ir.document_version_id
            JOIN review_tasks rt
              ON rt.object_type = 'ingestion_record' AND rt.object_id = ir.id
            WHERE {where}
        """

    @staticmethod
    def _to_record(row: dict[str, Any]) -> IngestionRecord:
        return IngestionRecord(
            internal_id=row["id"],
            public_id=cast(str, row["public_id"]),
            task_id=cast(str, row["task_id"]),
            source_id=cast(str, row["source_public_id"]),
            source_name=cast(str, row["source_name"]),
            source_grade=cast(str, row["source_grade"]),
            document_id=cast(str, row["document_public_id"]),
            version_number=cast(int, row["version_number"]),
            canonical_url=cast(str, row["canonical_url"]),
            content_hash=cast(str, row["content_hash"]),
            raw_object_uri=cast(str, row["raw_object_uri"]),
            collection_relevance=cast(CollectionRelevance, row["collection_relevance"]),
            verification_hint=cast(FactLevel | None, row["verification_hint"]),
            publication_status=cast(L2PublicationStatus, row["publication_status"]),
            processing_status=cast(ProcessingStatus, row["processing_status"]),
            review_flags=tuple(cast(list[str], row["review_flags"])),
            review_task_id=cast(str, row["review_task_public_id"]),
            review_status=cast(str, row["review_status"]),
            risk_level=cast(RiskLevel, row["risk_level"]),
            created_at=row["created_at"],
        )

    @staticmethod
    def _submitted_payload(submission: IngestionSubmission) -> dict[str, object]:
        return {
            "contract_version": submission.contract_version,
            "task_id": submission.task_id,
            "run_id": submission.run_id,
            "idempotency_key": submission.idempotency_key,
            "source_id": submission.source_id,
            "url": submission.url,
            "document_type": submission.document_type,
            "language": submission.language,
            "published_at": None
            if submission.published_at is None
            else submission.published_at.isoformat(),
            "crawled_at": submission.crawled_at.isoformat(),
            "content_hash": submission.content_hash,
            "raw_object_uri": submission.raw_object_uri,
            "content_type": submission.content_type,
            "title_original": submission.title_original,
            "collection_relevance": submission.collection_relevance,
            "verification_hint": submission.verification_hint,
            "publication_status": submission.publication_status,
            "metadata": submission.metadata,
        }
