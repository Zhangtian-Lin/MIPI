from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

from mipi.modules.sources.application import SourceService
from mipi.modules.sources.domain import (
    RobotsStatus,
    SourceActorRole,
    SourceConflictError,
    SourceDecision,
    SourceDecisionAction,
    SourceDecisionConflictError,
    SourceGrade,
    SourceNotFoundError,
    SourceRecord,
    SourceRegistration,
    SourceTransitionError,
)


class SourceRegistrationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(pattern=r"^SRC-[A-Za-z0-9][A-Za-z0-9._-]*$")
    name: str = Field(min_length=1, max_length=300)
    owner: str = Field(min_length=1, max_length=300)
    base_url: HttpUrl
    source_grade: SourceGrade
    authority_scope: list[str] = Field(min_length=1)
    languages: list[str] = Field(min_length=1)


class SourceDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: SourceDecisionAction
    reason: str = Field(min_length=8, max_length=2000)
    rule_version: str = Field(default="source-review-v1.0", min_length=1, max_length=100)
    identity_verified: bool = False
    terms_reviewed: bool = False
    authority_scope_reviewed: bool = False
    robots_status: RobotsStatus | None = None
    evidence_urls: list[HttpUrl] = Field(default_factory=list, max_length=20)
    access_notes: str | None = Field(default=None, max_length=2000)


def create_source_router(service: SourceService, *, local_admin_enabled: bool) -> APIRouter:
    router = APIRouter(prefix="/v1/admin/sources", tags=["admin-sources"])

    @router.post("")
    def register_source(
        request: SourceRegistrationRequest,
        x_actor_id: Annotated[str, Header(min_length=1)] = "local-admin",
        x_actor_role: Annotated[SourceActorRole, Header()] = "source_admin",
    ) -> dict[str, object]:
        _require_local_admin(local_admin_enabled)
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

    @router.post("/{source_id}/decisions")
    def decide_source(
        source_id: str,
        request: SourceDecisionRequest,
        x_actor_id: Annotated[str, Header(min_length=1, max_length=200)],
        x_actor_role: Annotated[SourceActorRole, Header()],
        idempotency_key: Annotated[
            str, Header(alias="Idempotency-Key", min_length=8, max_length=500)
        ],
    ) -> dict[str, object]:
        _require_local_admin(local_admin_enabled)
        try:
            result = service.decide(
                source_id,
                SourceDecision(
                    idempotency_key=idempotency_key,
                    actor_id=x_actor_id,
                    actor_role=x_actor_role,
                    action=request.action,
                    reason=request.reason,
                    rule_version=request.rule_version,
                    identity_verified=request.identity_verified,
                    terms_reviewed=request.terms_reviewed,
                    authority_scope_reviewed=request.authority_scope_reviewed,
                    robots_status=request.robots_status,
                    evidence_urls=tuple(str(url) for url in request.evidence_urls),
                    access_notes=request.access_notes,
                ),
            )
        except SourceNotFoundError as error:
            raise _error(404, "SOURCE_NOT_FOUND", str(error)) from error
        except SourceTransitionError as error:
            raise _error(409, "SOURCE_TRANSITION_CONFLICT", str(error)) from error
        except SourceDecisionConflictError as error:
            raise _error(409, "SOURCE_DECISION_IDEMPOTENCY_CONFLICT", str(error)) from error
        except ValueError as error:
            raise _error(422, "INVALID_SOURCE_DECISION", str(error)) from error
        return _response(
            {"decision_id": result.decision_id, "source": _source_payload(result.source)},
            duplicate=result.duplicate,
        )

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


def _require_local_admin(enabled: bool) -> None:
    if not enabled:
        raise HTTPException(
            status_code=503,
            detail={
                "code": "SOURCE_ADMIN_AUTH_NOT_CONFIGURED",
                "message": "Source mutations require a configured identity provider.",
            },
        )


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})
