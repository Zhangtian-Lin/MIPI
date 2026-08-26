from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from mipi.bootstrap.settings import Settings, get_settings
from mipi.modules.documents.application import DocumentService
from mipi.modules.documents.infrastructure import MinioRawObjectStorage, PostgresDocumentRepository
from mipi.modules.events.api import create_event_router
from mipi.modules.events.application import EventService
from mipi.modules.events.infrastructure import PostgresEventRepository
from mipi.modules.ingestion.api import create_ingestion_router
from mipi.modules.ingestion.application import IngestionService
from mipi.modules.ingestion.infrastructure import PostgresIngestionRepository
from mipi.modules.sources.api import create_source_router
from mipi.modules.sources.application import SourceService
from mipi.modules.sources.infrastructure import PostgresSourceRepository
from mipi.modules.trade.api import create_trade_router
from mipi.modules.trade.application import TradeService
from mipi.modules.trade.infrastructure import PostgresTradeRepository
from mipi.modules.verification.api import create_review_router
from mipi.modules.verification.application import ReviewService
from mipi.modules.verification.infrastructure import PostgresReviewRepository


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    app = FastAPI(
        title="MIPI API",
        version="0.1.0",
        docs_url="/docs" if settings.env != "production" else None,
    )
    if settings.env != "production":
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["http://localhost:3000", "http://localhost:3001"],
            allow_methods=["*"],
            allow_headers=["*"],
        )

    sources = SourceService(PostgresSourceRepository(settings.database_url))
    documents = DocumentService(
        PostgresDocumentRepository(settings.database_url),
        MinioRawObjectStorage(
            endpoint=settings.object_storage_endpoint,
            bucket=settings.object_storage_bucket,
            access_key=settings.object_storage_access_key,
            secret_key=settings.object_storage_secret_key,
        ),
    )
    ingestion = IngestionService(
        sources=sources,
        documents=documents,
        repository=PostgresIngestionRepository(settings.database_url),
    )
    app.include_router(create_source_router(sources, local_admin_enabled=settings.env == "local"))
    app.include_router(create_ingestion_router(ingestion))
    app.include_router(
        create_review_router(
            ReviewService(PostgresReviewRepository(settings.database_url)),
            local_review_enabled=settings.env == "local",
        )
    )
    app.include_router(
        create_trade_router(
            TradeService(PostgresTradeRepository(settings.database_url)),
            local_processing_enabled=settings.env == "local",
            local_publication_enabled=settings.env == "local",
        )
    )
    app.include_router(
        create_event_router(
            EventService(PostgresEventRepository(settings.database_url)),
            local_processing_enabled=settings.env == "local",
            local_publication_enabled=settings.env == "local",
        )
    )

    @app.exception_handler(RequestValidationError)
    async def validation_error(_request: Request, error: RequestValidationError) -> JSONResponse:
        details = [
            {"path": list(item["loc"]), "message": item["msg"], "type": item["type"]}
            for item in error.errors()
        ]
        return _error_response(422, "VALIDATION_ERROR", "Request validation failed", details)

    @app.exception_handler(HTTPException)
    async def http_error(_request: Request, error: HTTPException) -> JSONResponse:
        if isinstance(error.detail, dict):
            code = str(error.detail.get("code", "HTTP_ERROR"))
            message = str(error.detail.get("message", "Request failed"))
        else:
            code = "HTTP_ERROR"
            message = str(error.detail)
        return _error_response(error.status_code, code, message)

    @app.get("/health", tags=["system"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "environment": settings.env}

    return app


def _error_response(
    status_code: int,
    code: str,
    message: str,
    details: list[dict[str, object]] | None = None,
) -> JSONResponse:
    request_id = str(uuid4())
    return JSONResponse(
        status_code=status_code,
        content={
            "data": None,
            "meta": {"contract_version": "1.1", "request_id": request_id},
            "error": {
                "code": code,
                "message": message,
                "details": details or [],
                "request_id": request_id,
                "retryable": status_code >= 500,
            },
        },
    )
