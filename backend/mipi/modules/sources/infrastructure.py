from typing import Any, cast

from psycopg.types.json import Jsonb

from mipi.modules.sources.domain import (
    RobotsStatus,
    SourceConflictError,
    SourceDecision,
    SourceDecisionConflictError,
    SourceDecisionResult,
    SourceGrade,
    SourceNotFoundError,
    SourceRecord,
    SourceRegistration,
    SourceRegistrationResult,
    SourceStatus,
    resolve_source_transition,
    source_decision_fingerprint,
)
from mipi.shared.database import open_database
from mipi.shared.ids import new_id


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

    def decide(self, source_id: str, decision: SourceDecision) -> SourceDecisionResult:
        with open_database(self._database_url) as connection, connection.transaction():
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (decision.idempotency_key,),
            )
            fingerprint = source_decision_fingerprint(source_id, decision)
            existing_decision = connection.execute(
                """
                SELECT sd.public_id AS decision_public_id, sd.request_fingerprint, s.*
                FROM source_decisions sd
                JOIN sources s ON s.id = sd.source_id
                WHERE sd.idempotency_key = %s
                """,
                (decision.idempotency_key,),
            ).fetchone()
            if existing_decision is not None:
                if existing_decision["request_fingerprint"] != fingerprint:
                    raise SourceDecisionConflictError(decision.idempotency_key)
                return SourceDecisionResult(
                    decision_id=cast(str, existing_decision["decision_public_id"]),
                    source=self._to_record(existing_decision),
                    duplicate=True,
                )
            row = connection.execute(
                "SELECT * FROM sources WHERE public_id = %s FOR UPDATE", (source_id,)
            ).fetchone()
            if row is None:
                raise SourceNotFoundError(source_id)
            current = self._to_record(row)
            transition = resolve_source_transition(
                current_status=current.status,
                current_robots_status=current.robots_status,
                identity_is_verified=current.identity_verified_at is not None,
                terms_are_reviewed=current.terms_reviewed_at is not None,
                has_authority_scope=bool(current.authority_scope),
                has_languages=bool(current.languages),
                decision=decision,
                current_access_notes=current.access_notes,
            )
            decision_id = new_id("SRV")
            effective_access_notes = decision.access_notes or current.access_notes
            connection.execute(
                """
                INSERT INTO source_decisions (
                    public_id, source_id, idempotency_key, request_fingerprint,
                    actor_id, actor_role, action,
                    previous_status, resulting_status, previous_crawl_status,
                    resulting_crawl_status, reason, rule_version, identity_verified,
                    terms_reviewed, authority_scope_reviewed, robots_status,
                    evidence_urls, access_notes
                )
                VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                )
                """,
                (
                    decision_id,
                    current.internal_id,
                    decision.idempotency_key,
                    fingerprint,
                    decision.actor_id,
                    decision.actor_role,
                    decision.action,
                    current.status,
                    transition.status,
                    current.crawl_status,
                    transition.crawl_status,
                    decision.reason.strip(),
                    decision.rule_version,
                    decision.identity_verified,
                    decision.terms_reviewed,
                    decision.authority_scope_reviewed,
                    transition.robots_status,
                    Jsonb(list(decision.evidence_urls)),
                    effective_access_notes,
                ),
            )
            updated_row = connection.execute(
                """
                UPDATE sources
                SET status = %s,
                    crawl_status = %s,
                    robots_status = %s,
                    identity_verified_at = CASE
                        WHEN %s THEN COALESCE(identity_verified_at, now())
                        ELSE identity_verified_at
                    END,
                    terms_reviewed_at = CASE
                        WHEN %s THEN COALESCE(terms_reviewed_at, now())
                        ELSE terms_reviewed_at
                    END,
                    last_reviewed_at = now(),
                    review_due_at = CASE
                        WHEN %s IN ('trial', 'active', 'degraded')
                        THEN now() + interval '180 days'
                        ELSE NULL
                    END,
                    access_notes = %s,
                    updated_at = now()
                WHERE id = %s
                RETURNING *
                """,
                (
                    transition.status,
                    transition.crawl_status,
                    transition.robots_status,
                    decision.identity_verified,
                    decision.terms_reviewed,
                    transition.status,
                    effective_access_notes,
                    current.internal_id,
                ),
            ).fetchone()
            assert updated_row is not None
            updated = self._to_record(updated_row)
            connection.execute(
                """
                INSERT INTO audit_log (
                    actor_type, actor_id, action, object_type, object_id,
                    before_json, after_json, reason
                )
                VALUES ('human', %s, 'source.lifecycle.decided', 'source', %s, %s, %s, %s)
                """,
                (
                    decision.actor_id,
                    source_id,
                    Jsonb(self._public_payload(current)),
                    Jsonb(
                        {
                            **self._public_payload(updated),
                            "decision_id": decision_id,
                            "decision": decision.action,
                            "rule_version": decision.rule_version,
                            "evidence_urls": list(decision.evidence_urls),
                        }
                    ),
                    decision.reason.strip(),
                ),
            )
            connection.execute(
                """
                INSERT INTO outbox (event_type, aggregate_type, aggregate_id, payload)
                VALUES ('source.lifecycle.changed', 'source', %s, %s)
                """,
                (
                    current.internal_id,
                    Jsonb(
                        {
                            "source_id": source_id,
                            "decision_id": decision_id,
                            "previous_status": current.status,
                            "status": updated.status,
                            "crawl_status": updated.crawl_status,
                        }
                    ),
                ),
            )
            return SourceDecisionResult(
                decision_id=decision_id, source=updated, duplicate=False
            )

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
            robots_status=cast(RobotsStatus, row["robots_status"]),
            terms_reviewed_at=row["terms_reviewed_at"],
            identity_verified_at=row["identity_verified_at"],
            last_reviewed_at=row["last_reviewed_at"],
            review_due_at=row["review_due_at"],
            access_notes=cast(str | None, row["access_notes"]),
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
            "robots_status": source.robots_status,
            "terms_reviewed_at": None
            if source.terms_reviewed_at is None
            else source.terms_reviewed_at.isoformat(),
            "identity_verified_at": None
            if source.identity_verified_at is None
            else source.identity_verified_at.isoformat(),
            "last_reviewed_at": None
            if source.last_reviewed_at is None
            else source.last_reviewed_at.isoformat(),
            "review_due_at": None
            if source.review_due_at is None
            else source.review_due_at.isoformat(),
            "access_notes": source.access_notes,
        }
