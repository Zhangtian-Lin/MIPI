import hashlib
import json
from typing import Any, cast

from psycopg.types.json import Jsonb

from mipi.modules.trade.domain import (
    DATASET_ID,
    TradeBatch,
    TradeBatchNotFoundError,
    TradeIngestionNotApprovedError,
    TradeIngestionNotFoundError,
    TradeProjectionConflictError,
    TradePublication,
    TradePublicationConflictError,
    build_trade_overview,
    normalize_trade_payload,
)
from mipi.modules.verification.domain import fact_level_for_official_trade_dataset
from mipi.shared.database import open_database
from mipi.shared.ids import new_id


class PostgresTradeRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def project(self, ingestion_id: str, *, actor_id: str, rule_version: str) -> TradeBatch:
        with open_database(self._database_url) as connection, connection.transaction():
            row = connection.execute(
                """
                SELECT ir.*, s.id AS source_internal_id, s.public_id AS source_public_id,
                       s.source_grade, dv.text_original
                FROM ingestion_records ir
                JOIN sources s ON s.id = ir.source_id
                JOIN document_versions dv ON dv.id = ir.document_version_id
                WHERE ir.public_id = %s
                FOR UPDATE OF ir
                """,
                (ingestion_id,),
            ).fetchone()
            if row is None:
                raise TradeIngestionNotFoundError(ingestion_id)
            if row["processing_status"] != "approved":
                raise TradeIngestionNotApprovedError(ingestion_id)
            metadata = self._metadata(row)
            dataset_id = metadata.get("dataset_id")
            if dataset_id != DATASET_ID:
                raise TradeProjectionConflictError(
                    f"Ingestion dataset must be {DATASET_ID}, got {dataset_id!r}"
                )
            raw_content = row["text_original"]
            if not isinstance(raw_content, str) or not raw_content:
                raise TradeProjectionConflictError(
                    "Approved ingestion has no database-preserved source text"
                )
            fact_level = fact_level_for_official_trade_dataset(
                source_id=cast(str, row["source_public_id"]),
                source_grade=cast(str, row["source_grade"]),
                dataset_id=dataset_id,
                ingestion_status=cast(str, row["processing_status"]),
                verification_hint=cast(str | None, row["verification_hint"]),
            )
            observations = normalize_trade_payload(raw_content)

            existing = connection.execute(
                """
                SELECT public_id, status, observation_count
                FROM trade_indicator_batches
                WHERE ingestion_record_id = %s AND rule_version = %s
                """,
                (row["id"], rule_version),
            ).fetchone()
            if existing is not None:
                return TradeBatch(
                    public_id=cast(str, existing["public_id"]),
                    ingestion_id=ingestion_id,
                    dataset_id=DATASET_ID,
                    status=cast(str, existing["status"]),
                    observation_count=cast(int, existing["observation_count"]),
                    duplicate=True,
                )

            batch_id = new_id("TIB")
            batch = connection.execute(
                """
                INSERT INTO trade_indicator_batches (
                    public_id, ingestion_record_id, source_id, document_version_id,
                    dataset_id, fact_level, observation_count, processed_by, rule_version
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    batch_id,
                    row["id"],
                    row["source_internal_id"],
                    row["document_version_id"],
                    DATASET_ID,
                    fact_level,
                    len(observations),
                    actor_id,
                    rule_version,
                ),
            ).fetchone()
            assert batch is not None
            with connection.cursor() as cursor:
                cursor.executemany(
                    """
                    INSERT INTO trade_indicator_observations (
                        batch_id, period, sitc_section, exports_rm_million, imports_rm_million
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    [
                        (
                            batch["id"],
                            item.period,
                            item.section,
                            item.exports_rm_million,
                            item.imports_rm_million,
                        )
                        for item in observations
                    ],
                )
            connection.execute(
                """
                INSERT INTO audit_log (
                    actor_type, actor_id, action, object_type, object_id,
                    after_json, reason, task_id
                )
                VALUES ('agent', %s, 'trade.batch.projected', 'trade_indicator_batch',
                        %s, %s, 'Approved L2 official dataset normalized into L3', %s)
                """,
                (
                    actor_id,
                    batch_id,
                    Jsonb(
                        {
                            "ingestion_id": ingestion_id,
                            "dataset_id": DATASET_ID,
                            "fact_level": fact_level,
                            "observation_count": len(observations),
                            "rule_version": rule_version,
                        }
                    ),
                    row["task_id"],
                ),
            )
            return TradeBatch(
                public_id=batch_id,
                ingestion_id=ingestion_id,
                dataset_id=DATASET_ID,
                status="canonical_private",
                observation_count=len(observations),
                duplicate=False,
            )

    def publish(
        self,
        batch_id: str,
        *,
        publisher_id: str,
        reason: str,
        rule_version: str,
        idempotency_key: str,
    ) -> TradePublication:
        fingerprint = self._publication_fingerprint(
            batch_id=batch_id,
            publisher_id=publisher_id,
            reason=reason,
            rule_version=rule_version,
        )
        with open_database(self._database_url) as connection, connection.transaction():
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended('trade-publication', 0))"
            )
            existing = connection.execute(
                """
                SELECT tip.*, tib.public_id AS batch_public_id
                FROM trade_indicator_publications tip
                JOIN trade_indicator_batches tib ON tib.id = tip.batch_id
                WHERE tip.idempotency_key = %s
                """,
                (idempotency_key,),
            ).fetchone()
            if existing is not None:
                if existing["request_fingerprint"] != fingerprint:
                    raise TradePublicationConflictError(idempotency_key)
                return self._to_publication(existing, duplicate=True)

            batch = connection.execute(self._batch_evidence_sql(), (batch_id,)).fetchone()
            if batch is None:
                raise TradeBatchNotFoundError(batch_id)
            if batch["fact_level"] != "F4":
                raise TradePublicationConflictError("Trade publication requires F4 verification")
            already_published = connection.execute(
                "SELECT public_id FROM trade_indicator_publications WHERE batch_id = %s",
                (batch["id"],),
            ).fetchone()
            if already_published is not None:
                raise TradePublicationConflictError(
                    f"Batch is already published as {already_published['public_id']}"
                )
            observations = normalize_trade_payload(
                json.dumps(
                    [
                        {
                            "date": item["period"].isoformat(),
                            "section": item["sitc_section"],
                            "exports": str(item["exports_rm_million"]),
                            "imports": str(item["imports_rm_million"]),
                        }
                        for item in connection.execute(
                            """
                            SELECT period, sitc_section, exports_rm_million, imports_rm_million
                            FROM trade_indicator_observations
                            WHERE batch_id = %s
                            ORDER BY period, sitc_section
                            """,
                            (batch["id"],),
                        ).fetchall()
                    ]
                )
            )
            projection = build_trade_overview(
                observations,
                evidence=self._evidence_payload(batch),
            )
            publication_id = new_id("TIP")
            connection.execute(
                "UPDATE trade_indicator_publications SET is_current = false WHERE is_current"
            )
            published = connection.execute(
                """
                INSERT INTO trade_indicator_publications (
                    public_id, batch_id, idempotency_key, request_fingerprint,
                    projection, publisher_id, reason, rule_version
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING *
                """,
                (
                    publication_id,
                    batch["id"],
                    idempotency_key,
                    fingerprint,
                    Jsonb(projection),
                    publisher_id,
                    reason.strip(),
                    rule_version,
                ),
            ).fetchone()
            assert published is not None
            published["batch_public_id"] = batch_id
            connection.execute(
                """
                UPDATE trade_indicator_batches
                SET status = 'published', updated_at = now()
                WHERE id = %s
                """,
                (batch["id"],),
            )
            connection.execute(
                """
                INSERT INTO audit_log (
                    actor_type, actor_id, action, object_type, object_id,
                    after_json, reason, task_id
                )
                VALUES ('human', %s, 'trade.publication.published', 'trade_indicator_publication',
                        %s, %s, %s, %s)
                """,
                (
                    publisher_id,
                    publication_id,
                    Jsonb(
                        {
                            "batch_id": batch_id,
                            "revision": published["revision"],
                            "rule_version": rule_version,
                        }
                    ),
                    reason.strip(),
                    batch["task_id"],
                ),
            )
            connection.execute(
                """
                INSERT INTO outbox (event_type, aggregate_type, aggregate_id, payload)
                VALUES ('trade.publication.published', 'trade_indicator_publication', %s, %s)
                """,
                (
                    published["id"],
                    Jsonb(
                        {
                            "publication_id": publication_id,
                            "batch_id": batch_id,
                            "revision": published["revision"],
                        }
                    ),
                ),
            )
            return self._to_publication(published, duplicate=False)

    def current_overview(self) -> TradePublication | None:
        with open_database(self._database_url) as connection:
            row = connection.execute(
                """
                SELECT tip.*, tib.public_id AS batch_public_id
                FROM trade_indicator_publications tip
                JOIN trade_indicator_batches tib ON tib.id = tip.batch_id
                WHERE tip.is_current
                """
            ).fetchone()
        return None if row is None else self._to_publication(row, duplicate=False)

    @staticmethod
    def _metadata(row: dict[str, Any]) -> dict[str, object]:
        payload = row["submitted_payload"]
        if not isinstance(payload, dict) or not isinstance(payload.get("metadata"), dict):
            raise TradeProjectionConflictError("Ingestion metadata is missing")
        return cast(dict[str, object], payload["metadata"])

    @staticmethod
    def _publication_fingerprint(
        *, batch_id: str, publisher_id: str, reason: str, rule_version: str
    ) -> str:
        canonical = json.dumps(
            {
                "batch_id": batch_id,
                "publisher_id": publisher_id,
                "reason": reason.strip(),
                "rule_version": rule_version,
            },
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        )
        return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()

    @staticmethod
    def _batch_evidence_sql() -> str:
        return """
            SELECT tib.*, ir.public_id AS ingestion_public_id, ir.task_id,
                   ir.canonical_url, ir.content_hash,
                   s.public_id AS source_public_id, s.name AS source_name,
                   s.source_grade, d.public_id AS document_public_id,
                   dv.version_number, dv.crawled_at, dv.metadata
            FROM trade_indicator_batches tib
            JOIN ingestion_records ir ON ir.id = tib.ingestion_record_id
            JOIN sources s ON s.id = tib.source_id
            JOIN document_versions dv ON dv.id = tib.document_version_id
            JOIN documents d ON d.id = dv.document_id
            WHERE tib.public_id = %s
            FOR UPDATE OF tib
        """

    @staticmethod
    def _evidence_payload(row: dict[str, Any]) -> dict[str, object]:
        metadata = row["metadata"] if isinstance(row["metadata"], dict) else {}
        return {
            "source_id": row["source_public_id"],
            "source_name": row["source_name"],
            "source_grade": row["source_grade"],
            "ingestion_id": row["ingestion_public_id"],
            "document_id": row["document_public_id"],
            "document_version": row["version_number"],
            "canonical_url": row["canonical_url"],
            "content_hash": row["content_hash"],
            "crawled_at": row["crawled_at"].isoformat(),
            "license": metadata.get("license"),
            "license_url": metadata.get("license_url"),
            "attribution": metadata.get("attribution"),
        }

    @staticmethod
    def _to_publication(row: dict[str, Any], *, duplicate: bool) -> TradePublication:
        projection = cast(dict[str, object], row["projection"]).copy()
        projection.update(
            {
                "publication_id": row["public_id"],
                "revision": row["revision"],
                "published_at": row["published_at"].isoformat(),
            }
        )
        return TradePublication(
            public_id=cast(str, row["public_id"]),
            batch_id=cast(str, row.get("batch_public_id", "")),
            revision=cast(int, row["revision"]),
            projection=projection,
            duplicate=duplicate,
        )
