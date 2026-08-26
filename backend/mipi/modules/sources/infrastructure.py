from typing import Any, cast

from psycopg.types.json import Jsonb

from mipi.modules.sources.domain import (
    SourceConflictError,
    SourceGrade,
    SourceNotFoundError,
    SourceRecord,
    SourceRegistration,
    SourceRegistrationResult,
    SourceStatus,
)
from mipi.shared.database import open_database


class PostgresSourceRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def register(
        self, registration: SourceRegistration, *, actor_id: str
    ) -> SourceRegistrationResult:
        with open_database(self._database_url) as connection, connection.transaction():
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (registration.public_id,),
            )
            existing_row = connection.execute(
                "SELECT * FROM sources WHERE public_id = %s", (registration.public_id,)
            ).fetchone()
            if existing_row is not None:
                existing = self._to_record(existing_row)
                if not self._matches(existing, registration):
                    raise SourceConflictError(registration.public_id)
                return SourceRegistrationResult(source=existing, duplicate=True)

            row = connection.execute(
                """
                INSERT INTO sources (
                    public_id, name, owner, base_url, source_grade,
                    authority_scope, languages, status, crawl_status
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'candidate', 'pending_terms_review')
                RETURNING *
                """,
                (
                    registration.public_id,
                    registration.name,
                    registration.owner,
                    registration.base_url,
                    registration.source_grade,
                    Jsonb(list(registration.authority_scope)),
                    Jsonb(list(registration.languages)),
                ),
            ).fetchone()
            assert row is not None
            source = self._to_record(row)
            connection.execute(
                """
                INSERT INTO audit_log (
                    actor_type, actor_id, action, object_type, object_id, after_json, reason
                )
                VALUES ('human', %s, 'source.registered', 'source', %s, %s, %s)
                """,
                (
                    actor_id,
                    source.public_id,
                    Jsonb(self._public_payload(source)),
                    "Candidate source registration; terms and authority scope require review.",
                ),
            )
            return SourceRegistrationResult(source=source, duplicate=False)

    def get(self, public_id: str) -> SourceRecord:
        with open_database(self._database_url) as connection:
            row = connection.execute(
                "SELECT * FROM sources WHERE public_id = %s", (public_id,)
            ).fetchone()
        if row is None:
            raise SourceNotFoundError(public_id)
        return self._to_record(row)

    def list(self, limit: int) -> list[SourceRecord]:
        with open_database(self._database_url) as connection:
            rows = connection.execute(
                "SELECT * FROM sources ORDER BY created_at DESC LIMIT %s", (limit,)
            ).fetchall()
        return [self._to_record(row) for row in rows]

    @staticmethod
    def _to_record(row: dict[str, Any]) -> SourceRecord:
        return SourceRecord(
            internal_id=row["id"],
            public_id=cast(str, row["public_id"]),
            name=cast(str, row["name"]),
            owner=cast(str, row["owner"]),
            base_url=cast(str, row["base_url"]),
            source_grade=cast(SourceGrade, row["source_grade"]),
            authority_scope=tuple(cast(list[str], row["authority_scope"])),
            languages=tuple(cast(list[str], row["languages"])),
            status=cast(SourceStatus, row["status"]),
            crawl_status=cast(str, row["crawl_status"]),
        )

    @staticmethod
    def _matches(existing: SourceRecord, registration: SourceRegistration) -> bool:
        return (
            existing.name == registration.name
            and existing.owner == registration.owner
            and existing.base_url == registration.base_url
            and existing.source_grade == registration.source_grade
            and existing.authority_scope == registration.authority_scope
            and existing.languages == registration.languages
        )

    @staticmethod
    def _public_payload(source: SourceRecord) -> dict[str, object]:
        return {
            "source_id": source.public_id,
            "name": source.name,
            "owner": source.owner,
            "base_url": source.base_url,
            "source_grade": source.source_grade,
            "authority_scope": list(source.authority_scope),
            "languages": list(source.languages),
            "status": source.status,
            "crawl_status": source.crawl_status,
        }
