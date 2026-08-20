import asyncio

import httpx
from mipi.bootstrap.app import create_app


async def request(path: str) -> httpx.Response:
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get(path)


def test_health() -> None:
    response = asyncio.run(request("/health"))
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_changes_is_empty_scaffold() -> None:
    response = asyncio.run(request("/v1/changes"))
    assert response.status_code == 200
    assert response.json()["data"] == []
