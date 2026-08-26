import asyncio

import httpx
from mipi.bootstrap.app import create_app


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
    assert "/v1/admin/ingestion-records" in paths
