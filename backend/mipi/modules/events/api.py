from datetime import date
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from mipi.modules.events.application import EventService
from mipi.modules.events.domain import (
    EventNotFoundError,
    EventProjectionConflictError,
    EventProjectionInput,
    EventPublicationConflictError,
)


class EventProjectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ingestion_id: str = Field(pattern=r"^ING-")
    event_type: Literal[
        "investment",
        "project_update",
        "policy_update",
        "company_update",
        "tender",
        "governance_update",
    ]
    title_zh: str = Field(min_length=5, max_length=160)
    summary_zh: str = Field(min_length=20, max_length=800)
    event_date: date | None = None
    event_date_precision: Literal["day", "month", "year", "unknown"] = "unknown"
    industries: list[str] = Field(min_length=1, max_length=10)
    states: list[str] = Field(min_length=1, max_length=20)
    span_start: int = Field(ge=0)
    span_end: int = Field(gt=0)
    quote_original: str = Field(min_length=1, max_length=500)
    quote_zh: str = Field(min_length=1, max_length=500)
    model_id: str = Field(min_length=1, max_length=200)
    prompt_version: str = Field(min_length=1, max_length=100)
    conflict: bool = False
    rule_version: str = Field(default="event-projection-v1.0", min_length=1, max_length=100)


class EventPublicationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=8, max_length=2000)
    rule_version: str = Field(default="event-publication-v1.0", min_length=1, max_length=100)


def create_event_router(
    service: EventService, *, local_processing_enabled: bool, local_publication_enabled: bool
) -> APIRouter:
    router = APIRouter(tags=["events"])

    @router.get("/v1/changes")
    def list_changes(
        limit: Annotated[int, Query(ge=1, le=10)] = 10,
        industry: str | None = None,
        state: str | None = None,
        event_type: str | None = None,
    ) -> dict[str, object]:
        return _response(
            list(
                service.list_published(
                    limit=limit, industry=industry, state=state, event_type=event_type
                )
            )
        )

    @router.get("/v1/events/{event_id}")
    def get_event(event_id: str) -> dict[str, object]:
        result = service.get_published(event_id)
        if result is None:
            raise _error(404, "EVENT_NOT_FOUND", "Published event was not found")
        return _response(result)

    @router.get("/v1/admin/events/workbench")
    def get_event_workbench(
        x_actor_id: Annotated[str, Header(min_length=1, max_length=200)],
        x_actor_role: Annotated[Literal["processing_agent", "publisher", "system_admin"], Header()],
        limit: Annotated[int, Query(ge=1, le=200)] = 100,
    ) -> dict[str, object]:
        if not local_processing_enabled:
            raise _error(
                503,
                "EVENT_WORKBENCH_AUTH_NOT_CONFIGURED",
                "Production event workbench access requires an identity provider.",
            )
        result = service.workbench(limit=limit)
        return _response(
            {
                "eligible_ingestions": [item.__dict__ for item in result.eligible_ingestions],
                "events": [
                    {
                        **item.__dict__,
                        "industries": list(item.industries),
                        "states": list(item.states),
                        "blockers": list(item.blockers),
                    }
                    for item in result.events
                ],
            }
        )

    @router.get("/v1/admin/events/ingestions/{ingestion_id}/source")
    def get_event_source(
        ingestion_id: str,
        x_actor_id: Annotated[str, Header(min_length=1, max_length=200)],
        x_actor_role: Annotated[Literal["processing_agent", "system_admin"], Header()],
    ) -> dict[str, object]:
        if not local_processing_enabled:
            raise _error(
                503,
                "EVENT_WORKBENCH_AUTH_NOT_CONFIGURED",
                "Production event workbench access requires an identity provider.",
            )
        try:
            return _response(service.get_source(ingestion_id).__dict__)
        except EventNotFoundError as error:
            raise _error(404, "EVENT_INGESTION_NOT_FOUND", str(error)) from error
        except EventProjectionConflictError as error:
            raise _error(409, "EVENT_PROJECTION_CONFLICT", str(error)) from error

    @router.post("/v1/admin/events/project")
    def project_event(
        request: EventProjectionRequest,
        x_actor_id: Annotated[str, Header(min_length=1, max_length=200)],
        x_actor_role: Annotated[Literal["processing_agent", "system_admin"], Header()],
        idempotency_key: Annotated[
            str, Header(alias="Idempotency-Key", min_length=8, max_length=500)
        ],
    ) -> dict[str, object]:
        if not local_processing_enabled:
            raise _error(
                503,
                "PROCESSING_AUTH_NOT_CONFIGURED",
                "Production processing requires a service identity provider.",
            )
        try:
            value = EventProjectionInput(**request.model_dump(exclude={"rule_version"}))
            result = service.project(
                value,
                actor_id=x_actor_id,
                rule_version=request.rule_version,
                idempotency_key=idempotency_key,
            )
        except EventNotFoundError as error:
            raise _error(404, "EVENT_INGESTION_NOT_FOUND", str(error)) from error
        except EventProjectionConflictError as error:
            raise _error(409, "EVENT_PROJECTION_CONFLICT", str(error)) from error
        except ValueError as error:
            raise _error(422, "INVALID_EVENT_PROJECTION", str(error)) from error
        return _response(
            {
                **result.__dict__,
                "industries": list(result.industries),
                "states": list(result.states),
                "blockers": list(result.blockers),
            },
            duplicate=result.duplicate,
        )

    @router.post("/v1/admin/events/{event_id}/publish")
    def publish_event(
        event_id: str,
        request: EventPublicationRequest,
        x_actor_id: Annotated[str, Header(min_length=1, max_length=200)],
        x_actor_role: Annotated[Literal["publisher"], Header()],
        idempotency_key: Annotated[
            str, Header(alias="Idempotency-Key", min_length=8, max_length=500)
        ],
    ) -> dict[str, object]:
        if not local_publication_enabled:
            raise _error(
                503,
                "PUBLICATION_AUTH_NOT_CONFIGURED",
                "Production publication requires an identity provider.",
            )
        try:
            result = service.publish(
                event_id,
                publisher_id=x_actor_id,
                reason=request.reason,
                rule_version=request.rule_version,
                idempotency_key=idempotency_key,
            )
        except EventNotFoundError as error:
            raise _error(404, "EVENT_NOT_FOUND", str(error)) from error
        except EventPublicationConflictError as error:
            raise _error(409, "EVENT_PUBLICATION_CONFLICT", str(error)) from error
        except ValueError as error:
            raise _error(422, "EVENT_PUBLICATION_NOT_READY", str(error)) from error
        return _response(result.projection, duplicate=result.duplicate)

    return router


def _response(data: object, *, duplicate: bool = False) -> dict[str, object]:
    return {
        "data": data,
        "meta": {"contract_version": "1.0", "request_id": str(uuid4()), "duplicate": duplicate},
        "error": None,
    }


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})
