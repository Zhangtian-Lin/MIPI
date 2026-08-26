import asyncio

import httpx
from mipi.bootstrap.app import create_app
from mipi.bootstrap.settings import Settings


async def request(path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


async def post(path: str, payload: dict[str, object]) -> httpx.Response:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.post(path, json=payload)


def test_health() -> None:
    response = asyncio.run(request("/health"))
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_changes_is_empty_scaffold() -> None:
    response = asyncio.run(request("/v1/changes"))
    assert response.status_code == 200
    assert response.json()["data"] == []


def test_ingestion_contract_rejects_invalid_hash_before_database_access() -> None:
    response = asyncio.run(
        post(
            "/v1/ingestion/records",
            {
                "contract_version": "1.1",
                "task_id": "contract-test",
                "idempotency_key": "contract-test-key",
                "source_id": "SRC-TEST",
                "url": "https://example.test/document",
                "crawled_at": "2026-08-26T00:00:00Z",
                "content_hash": "sha256:short",
                "raw_content": "content",
            },
        )
    )

    assert response.status_code == 422
    assert response.json()["data"] is None
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_generated_openapi_includes_ingestion_and_admin_routes() -> None:
    app = create_app()
    paths = app.openapi()["paths"]

    assert "/v1/ingestion/records" in paths
    assert "/v1/admin/sources" in paths
    assert "/v1/admin/sources/{source_id}/decisions" in paths
    assert "/v1/admin/ingestion-records" in paths
    assert "/v1/admin/review-tasks/{review_task_id}/decisions" in paths
    assert "/v1/admin/trade-indicators/project" in paths
    assert "/v1/admin/trade-indicators/{batch_id}/publish" in paths
    assert "/v1/trade/overview" in paths


def test_production_rejects_header_only_review_identity() -> None:
    async def run() -> httpx.Response:
        transport = httpx.ASGITransport(app=create_app(Settings(env="production")))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/v1/admin/review-tasks/REV-test/decisions",
                headers={"X-Actor-ID": "reviewer-test", "X-Actor-Role": "reviewer"},
                json={"action": "approve", "reason": "Checked test evidence."},
            )

    response = asyncio.run(run())
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "REVIEW_AUTH_NOT_CONFIGURED"


def test_production_rejects_header_only_source_admin_identity() -> None:
    async def run() -> httpx.Response:
        transport = httpx.ASGITransport(app=create_app(Settings(env="production")))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/v1/admin/sources/SRC-test/decisions",
                headers={
                    "X-Actor-ID": "source-admin-test",
                    "X-Actor-Role": "source_admin",
                    "Idempotency-Key": "source-admin-production-test",
                },
                json={
                    "action": "approve_for_trial",
                    "reason": "Identity and access conditions were checked.",
                    "identity_verified": True,
                    "terms_reviewed": True,
                    "authority_scope_reviewed": True,
                    "robots_status": "allowed",
                },
            )

    response = asyncio.run(run())
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "SOURCE_ADMIN_AUTH_NOT_CONFIGURED"


def test_production_rejects_header_only_trade_processing_identity() -> None:
    async def run() -> httpx.Response:
        transport = httpx.ASGITransport(app=create_app(Settings(env="production")))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/v1/admin/trade-indicators/project",
                headers={
                    "X-Actor-ID": "processing-agent-test",
                    "X-Actor-Role": "processing_agent",
                },
                json={"ingestion_id": "ING-test"},
            )

    response = asyncio.run(run())
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "PROCESSING_AUTH_NOT_CONFIGURED"


def test_production_rejects_header_only_trade_publisher_identity() -> None:
    async def run() -> httpx.Response:
        transport = httpx.ASGITransport(app=create_app(Settings(env="production")))
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.post(
                "/v1/admin/trade-indicators/TIB-test/publish",
                headers={
                    "X-Actor-ID": "publisher-test",
                    "X-Actor-Role": "publisher",
                    "Idempotency-Key": "trade-publication-test",
                },
                json={"reason": "Reviewed the complete official trade projection."},
            )

    response = asyncio.run(run())
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "PUBLICATION_AUTH_NOT_CONFIGURED"
