import asyncio
import hashlib
import os
from contextlib import suppress
from uuid import uuid4

import httpx
import pytest
from minio import Minio
from mipi.bootstrap.app import create_app
from mipi.bootstrap.settings import Settings
from mipi.shared.database import open_database

pytestmark = pytest.mark.skipif(
    os.getenv("MIPI_RUN_INTEGRATION") != "1",
    reason="set MIPI_RUN_INTEGRATION=1 when local PostgreSQL and MinIO are running",
)


def test_l0_l2_ingestion_is_idempotent_and_reviewable() -> None:
    asyncio.run(_run_flow())


async def _run_flow() -> None:
    settings = Settings()
    token = uuid4().hex
    source_id = f"SRC-INTEGRATION-{token}"
    content = f"Synthetic MIPI integration evidence {token}"
    digest = hashlib.sha256(content.encode()).hexdigest()
    object_name = f"raw/{source_id}/{digest[:2]}/{digest}.txt"
    ingestion_id: str | None = None
    review_task_id: str | None = None

    transport = httpx.ASGITransport(app=create_app(settings))
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            source_response = await client.post(
                "/v1/admin/sources",
                json={
                    "source_id": source_id,
                    "name": "Synthetic integration source",
                    "owner": "MIPI test suite",
                    "base_url": f"https://{token}.example.test",
                    "source_grade": "S2",
                    "authority_scope": ["integration-test"],
                    "languages": ["en"],
                },
            )
            assert source_response.status_code == 200, source_response.text

            source_headers = {
                "X-Actor-ID": f"source-admin-{token}",
                "X-Actor-Role": "source_admin",
            }
            trial_payload = {
                "action": "approve_for_trial",
                "reason": "Synthetic identity, scope, terms, and robots rules were checked.",
                "identity_verified": True,
                "terms_reviewed": True,
                "authority_scope_reviewed": True,
                "robots_status": "allowed",
                "access_notes": "Synthetic integration source only.",
            }
            trial_headers = {**source_headers, "Idempotency-Key": f"trial-{token}"}
            trial = await client.post(
                f"/v1/admin/sources/{source_id}/decisions",
                headers=trial_headers,
                json=trial_payload,
            )
            assert trial.status_code == 200, trial.text
            assert trial.json()["data"]["source"]["status"] == "trial"

            duplicate_trial = await client.post(
                f"/v1/admin/sources/{source_id}/decisions",
                headers=trial_headers,
                json=trial_payload,
            )
            assert duplicate_trial.status_code == 200, duplicate_trial.text
            assert duplicate_trial.json()["meta"]["duplicate"] is True
            assert duplicate_trial.json()["data"]["decision_id"] == trial.json()["data"][
                "decision_id"
            ]

            conflicting_trial = await client.post(
                f"/v1/admin/sources/{source_id}/decisions",
                headers=trial_headers,
                json={**trial_payload, "reason": "A conflicting retry reason was supplied."},
            )
            assert conflicting_trial.status_code == 409
            assert (
                conflicting_trial.json()["error"]["code"]
                == "SOURCE_DECISION_IDEMPOTENCY_CONFLICT"
            )

            activation = await client.post(
                f"/v1/admin/sources/{source_id}/decisions",
                headers={**source_headers, "Idempotency-Key": f"activate-{token}"},
                json={
                    "action": "activate",
                    "reason": "Synthetic trial retrieval completed successfully.",
                    "robots_status": "allowed",
                    "evidence_urls": [f"https://{token}.example.test/trial-sample"],
                },
            )
            assert activation.status_code == 200, activation.text
            assert activation.json()["data"]["source"]["status"] == "active"
            assert activation.json()["data"]["source"]["crawl_status"] == "approved"

            payload = {
                "contract_version": "1.1",
                "task_id": f"integration-{token}",
                "run_id": f"run-{token}",
                "idempotency_key": f"integration-key-{token}",
                "source_id": source_id,
                "url": f"https://{token}.example.test/article#source-fragment",
                "document_type": "html",
                "language": "en",
                "published_at": None,
                "crawled_at": "2026-08-26T00:00:00Z",
                "content_hash": f"sha256:{digest}",
                "raw_content": content,
                "content_type": "text/plain; charset=utf-8",
                "title_original": "Synthetic integration document",
                "collection_relevance": "high",
                "verification_hint": "F1",
                "publication_status": "staged",
                "metadata": {"synthetic": True},
            }
            first = await client.post("/v1/ingestion/records", json=payload)
            assert first.status_code == 200, first.text
            first_body = first.json()
            ingestion_id = first_body["data"]["ingestion_id"]
            review_task_id = first_body["data"]["review"]["review_task_id"]
            assert first_body["meta"]["duplicate"] is False
            assert first_body["data"]["processing_status"] == "needs_review"
            assert first_body["data"]["review"]["risk_level"] == "R0"
            assert "source_registration_pending" not in first_body["data"]["review_flags"]
            assert first_body["data"]["canonical_url"].endswith("/article")

            duplicate = await client.post("/v1/ingestion/records", json=payload)
            assert duplicate.status_code == 200, duplicate.text
            assert duplicate.json()["meta"]["duplicate"] is True
            assert duplicate.json()["data"]["ingestion_id"] == ingestion_id

            detail = await client.get(f"/v1/admin/ingestion-records/{ingestion_id}")
            assert detail.status_code == 200, detail.text
            assert detail.json()["data"]["review"]["status"] == "queued"

            review = await client.post(
                f"/v1/admin/review-tasks/{review_task_id}/decisions",
                headers={"X-Actor-ID": f"reviewer-{token}", "X-Actor-Role": "reviewer"},
                json={
                    "action": "approve",
                    "reason": "Synthetic evidence and source were checked.",
                    "rule_version": "integration-v1",
                },
            )
            assert review.status_code == 200, review.text
            assert review.json()["data"]["task_status"] == "approved"
            assert review.json()["data"]["publication_status"] == "staged"
            assert review.json()["data"]["completed"] is True

            repeated_review = await client.post(
                f"/v1/admin/review-tasks/{review_task_id}/decisions",
                headers={"X-Actor-ID": f"reviewer-{token}", "X-Actor-Role": "reviewer"},
                json={
                    "action": "approve",
                    "reason": "Synthetic evidence and source were checked again.",
                },
            )
            assert repeated_review.status_code == 409
            assert repeated_review.json()["error"]["code"] == "REVIEW_CONFLICT"

            reviewed_detail = await client.get(
                f"/v1/admin/ingestion-records/{ingestion_id}"
            )
            assert reviewed_detail.status_code == 200, reviewed_detail.text
            reviewed_data = reviewed_detail.json()["data"]
            assert reviewed_data["processing_status"] == "approved"
            assert reviewed_data["publication_status"] == "staged"
            assert len(reviewed_data["review"]["decisions"]) == 1

        minio = Minio(
            settings.object_storage_endpoint.removeprefix("http://").removeprefix("https://"),
            access_key=settings.object_storage_access_key,
            secret_key=settings.object_storage_secret_key,
            secure=settings.object_storage_endpoint.startswith("https://"),
        )
        assert minio.stat_object(settings.object_storage_bucket, object_name).size == len(
            content.encode()
        )

        with open_database(settings.database_url) as connection:
            version_count = connection.execute(
                """
                SELECT count(*) AS count
                FROM document_versions dv
                JOIN documents d ON d.id = dv.document_id
                JOIN sources s ON s.id = d.source_id
                WHERE s.public_id = %s
                """,
                (source_id,),
            ).fetchone()
            assert version_count is not None
            assert version_count["count"] == 1
    finally:
        _cleanup(settings, source_id, ingestion_id, review_task_id, object_name)


def _cleanup(
    settings: Settings,
    source_id: str,
    ingestion_id: str | None,
    review_task_id: str | None,
    object_name: str,
) -> None:
    minio = Minio(
        settings.object_storage_endpoint.removeprefix("http://").removeprefix("https://"),
        access_key=settings.object_storage_access_key,
        secret_key=settings.object_storage_secret_key,
        secure=settings.object_storage_endpoint.startswith("https://"),
    )
    with suppress(Exception):
        minio.remove_object(settings.object_storage_bucket, object_name)

    with open_database(settings.database_url) as connection, connection.transaction():
        source = connection.execute(
            "SELECT id FROM sources WHERE public_id = %s", (source_id,)
        ).fetchone()
        if source is None:
            return
        connection.execute("DELETE FROM outbox WHERE aggregate_id = %s", (source["id"],))
        connection.execute("DELETE FROM source_decisions WHERE source_id = %s", (source["id"],))
        documents = connection.execute(
            "SELECT id FROM documents WHERE source_id = %s", (source["id"],)
        ).fetchall()
        document_ids = [row["id"] for row in documents]
        ingestion = None
        if ingestion_id is not None:
            ingestion = connection.execute(
                "SELECT id FROM ingestion_records WHERE public_id = %s", (ingestion_id,)
            ).fetchone()
        if ingestion is not None:
            connection.execute("DELETE FROM outbox WHERE aggregate_id = %s", (ingestion["id"],))
            review_task = connection.execute(
                """
                SELECT id FROM review_tasks
                WHERE object_type = 'ingestion_record' AND object_id = %s
                """,
                (ingestion["id"],),
            ).fetchone()
            if review_task is not None:
                connection.execute(
                    "DELETE FROM outbox WHERE aggregate_id = %s", (review_task["id"],)
                )
                connection.execute(
                    "DELETE FROM review_decisions WHERE review_task_id = %s",
                    (review_task["id"],),
                )
            connection.execute(
                """
                DELETE FROM review_tasks
                WHERE object_type = 'ingestion_record' AND object_id = %s
                """,
                (ingestion["id"],),
            )
            connection.execute("DELETE FROM ingestion_records WHERE id = %s", (ingestion["id"],))
        if ingestion_id is not None:
            connection.execute("DELETE FROM audit_log WHERE object_id = %s", (ingestion_id,))
        if review_task_id is not None:
            connection.execute("DELETE FROM audit_log WHERE object_id = %s", (review_task_id,))
        for document_id in document_ids:
            connection.execute(
                "DELETE FROM document_versions WHERE document_id = %s", (document_id,)
            )
        connection.execute("DELETE FROM documents WHERE source_id = %s", (source["id"],))
        connection.execute("DELETE FROM audit_log WHERE object_id = %s", (source_id,))
        connection.execute("DELETE FROM sources WHERE id = %s", (source["id"],))
