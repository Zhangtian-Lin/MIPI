from fastapi import FastAPI

from mipi.bootstrap.settings import get_settings


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="MIPI API",
        version="0.1.0",
        docs_url="/docs" if settings.env != "production" else None,
    )

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "environment": settings.env}

    @app.get("/v1/changes", tags=["intelligence"])
    async def list_changes() -> dict[str, object]:
        return {
            "data": [],
            "meta": {"contract_version": "1.0", "status": "scaffold"},
            "error": None,
        }

    return app

