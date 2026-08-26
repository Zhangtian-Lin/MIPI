from datetime import datetime
from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, field_validator, model_validator

from mipi.modules.documents.domain import DocumentType, L2PublicationStatus
from mipi.modules.ingestion.application import IngestionService
from mipi.modules.ingestion.domain import (
    CollectionRelevance,
    ContentHashMismatchError,
    FactLevel,
    IdempotencyConflictError,
    IngestionNotFoundError,
    IngestionRecord,
    IngestionSubmission,
)
from mipi.modules.sources.domain import SourceNotFoundError


class IngestionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    contract_version: str = Field(pattern=r"^1\.[01]$")
    task_id: str = Field(min_length=1, max_length=200)
    run_id: str | None = Field(default=None, max_length=200)
    idempotency_key: str = Field(min_length=8, max_length=500)
    source_id: str = Field(pattern=r"^SRC-[A-Za-z0-9][A-Za-z0-9._-]*$")
    url: HttpUrl
    document_type: DocumentType = "html"
    language: str | None = Field(default=None, max_length=35)
    published_at: datetime | None = None
    crawled_at: datetime
    content_hash: str = Field(pattern=r"^sha256:[0-9a-fA-F]{64}$")
    raw_object_uri: str | None = Field(
        default=None, min_length=1, pattern=r"^(s3|https?)://"
    )
    raw_content: str | None = Field(default=None, max_length=5_000_000)
    content_type: str = Field(default="text/plain; charset=utf-8", min_length=1, max_length=200)
    title_original: str | None = Field(default=None, max_length=1000)
    collection_relevance: CollectionRelevance = "unknown"
    verification_hint: FactLevel | None = None
    publication_status: L2PublicationStatus = "staged"
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("published_at", "crawled_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("timestamp must include a timezone")
        return value

    @model_validator(mode="after")
    def require_raw_input(self) -> "IngestionRequest":
        if self.raw_object_uri is None and self.raw_content is None:
            raise ValueError("raw_object_uri or raw_content is required")
        if self.contract_version == "1.0" and self.raw_object_uri is None:
            raise ValueError("contract 1.0 requires raw_object_uri")
        return self


def create_ingestion_router(service: IngestionService) -> APIRouter:
    router = APIRouter(tags=["ingestion"])

    @router.post("/v1/ingestion/records")
    def submit_ingestion(request: IngestionRequest) -> dict[str, object]:
        try:
            result = service.submit(_to_submission(request))
        except ContentHashMismatchError as error:
            raise _domain_error(422, "CONTENT_HASH_MISMATCH", str(error)) from error
        except IdempotencyConflictError as error:
            raise _domain_error(409, "IDEMPOTENCY_CONFLICT", str(error)) from error
        except SourceNotFoundError as error:
            raise _domain_error(404, "SOURCE_NOT_FOUND", str(error)) from error
        except ValueError as error:
            raise _domain_error(422, "INVALID_INGESTION", str(error)) from error
        return _response(_record_payload(result.record), duplicate=result.duplicate)

    @router.get("/v1/admin/ingestion-records")
    def list_candidates(
        limit: Annotated[int, Query(ge=1, le=500)] = 50,
        status: Annotated[str | None, Query(pattern=r"^(needs_review|quarantined)$")] = None,
    ) -> dict[str, object]:
        records = [_record_payload(record) for record in service.list(limit=limit, status=status)]
        return _response(records, count=len(records))

    @router.get("/v1/admin/ingestion-records/{ingestion_id}")
    def get_candidate(ingestion_id: str) -> dict[str, object]:
        try:
            record = service.get(ingestion_id)
        except IngestionNotFoundError as error:
            raise _domain_error(404, "INGESTION_NOT_FOUND", str(error)) from error
        return _response(_record_payload(record))

    return router


def _to_submission(request: IngestionRequest) -> IngestionSubmission:
    return IngestionSubmission(
        contract_version=request.contract_version,
        task_id=request.task_id,
        run_id=request.run_id,
        idempotency_key=request.idempotency_key,
        source_id=request.source_id,
        url=str(request.url),
        document_type=request.document_type,
        language=request.language,
        published_at=request.published_at,
        crawled_at=request.crawled_at,
        content_hash=request.content_hash.lower(),
        raw_object_uri=request.raw_object_uri,
        raw_content=request.raw_content,
        content_type=request.content_type,
        title_original=request.title_original,
        collection_relevance=request.collection_relevance,
        verification_hint=request.verification_hint,
        publication_status=request.publication_status,
        metadata=request.metadata,
    )


def _record_payload(record: IngestionRecord) -> dict[str, object]:
    return {
        "ingestion_id": record.public_id,
        "task_id": record.task_id,
        "source": {
            "source_id": record.source_id,
            "name": record.source_name,
            "source_grade": record.source_grade,
        },
        "document_id": record.document_id,
        "version_number": record.version_number,
        "canonical_url": record.canonical_url,
        "content_hash": record.content_hash,
        "raw_object_uri": record.raw_object_uri,
        "collection_relevance": record.collection_relevance,
        "verification_hint": record.verification_hint,
        "publication_status": record.publication_status,
        "processing_status": record.processing_status,
        "review_flags": list(record.review_flags),
        "review": {
            "review_task_id": record.review_task_id,
            "status": record.review_status,
            "risk_level": record.risk_level,
        },
        "created_at": record.created_at.isoformat(),
    }


def _response(
    data: object, *, duplicate: bool = False, count: int | None = None
) -> dict[str, object]:
    meta: dict[str, object] = {
        "contract_version": "1.1",
        "request_id": str(uuid4()),
        "duplicate": duplicate,
    }
    if count is not None:
        meta["count"] = count
    return {"data": data, "meta": meta, "error": None}


def _domain_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})
