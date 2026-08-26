from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from mipi.modules.sources.application import SourceService
from mipi.modules.sources.domain import (
    SourceConflictError,
    SourceGrade,
    SourceRecord,
    SourceRegistration,
)


class SourceRegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(pattern=r"^SRC-[A-Za-z0-9][A-Za-z0-9._-]*$")
    name: str = Field(min_length=1, max_length=300)
    owner: str = Field(min_length=1, max_length=300)
    base_url: HttpUrl
    source_grade: SourceGrade
    authority_scope: list[str] = Field(default_factory=list)
    languages: list[str] = Field(default_factory=list)


def create_source_router(service: SourceService) -> APIRouter:
    router = APIRouter(prefix="/v1/admin/sources", tags=["admin-sources"])

    @router.post("")
    def register_source(
        request: SourceRegistrationRequest,
        x_actor_id: Annotated[str, Header(min_length=1)] = "local-admin",
    ) -> dict[str, object]:
        try:
            result = service.register(
                SourceRegistration(
                    public_id=request.source_id,
                    name=request.name,
                    owner=request.owner,
                    base_url=str(request.base_url),
                    source_grade=request.source_grade,
                    authority_scope=tuple(request.authority_scope),
                    languages=tuple(request.languages),
                ),
                actor_id=x_actor_id,
            )
        except SourceConflictError as error:
            raise HTTPException(
                status_code=409,
                detail={"code": "SOURCE_CONFLICT", "message": str(error)},
            ) from error
        return _response(_source_payload(result.source), duplicate=result.duplicate)

    @router.get("")
    def list_sources(limit: Annotated[int, Query(ge=1, le=500)] = 100) -> dict[str, object]:
        sources = [_source_payload(source) for source in service.list(limit)]
        return _response(sources, count=len(sources))

    return router


def _source_payload(source: SourceRecord) -> dict[str, object]:
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
