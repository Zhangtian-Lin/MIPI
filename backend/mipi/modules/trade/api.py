from typing import Annotated, Literal
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from mipi.modules.trade.application import TradeService
from mipi.modules.trade.domain import (
    TradeBatchNotFoundError,
    TradeIngestionNotApprovedError,
    TradeIngestionNotFoundError,
    TradeProjectionConflictError,
    TradePublicationConflictError,
)

TradeProcessingRole = Literal["processing_agent", "system_admin"]


class TradeProjectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    ingestion_id: str = Field(pattern=r"^ING-")
    rule_version: str = Field(default="trade-sitc-v1.0", min_length=1, max_length=100)


class TradePublicationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=8, max_length=2000)
    rule_version: str = Field(default="trade-publication-v1.0", min_length=1, max_length=100)


def create_trade_router(
    service: TradeService,
    *,
    local_processing_enabled: bool,
    local_publication_enabled: bool,
) -> APIRouter:
    router = APIRouter(tags=["trade-indicators"])

    @router.post("/v1/admin/trade-indicators/project")
    def project_trade_batch(
        request: TradeProjectionRequest,
        x_actor_id: Annotated[str, Header(min_length=1, max_length=200)],
        x_actor_role: Annotated[TradeProcessingRole, Header()],
    ) -> dict[str, object]:
        if not local_processing_enabled:
            raise _error(
                503,
                "PROCESSING_AUTH_NOT_CONFIGURED",
                "Production processing requires a service identity provider.",
            )
        try:
            result = service.project(
                request.ingestion_id,
                actor_id=x_actor_id,
                rule_version=request.rule_version,
            )
        except TradeIngestionNotFoundError as error:
            raise _error(404, "TRADE_INGESTION_NOT_FOUND", str(error)) from error
        except TradeIngestionNotApprovedError as error:
            raise _error(
                409,
                "TRADE_INGESTION_NOT_APPROVED",
                "The ingestion must complete L2 review before projection.",
            ) from error
        except (TradeProjectionConflictError, ValueError) as error:
            raise _error(422, "INVALID_TRADE_PROJECTION", str(error)) from error
        return _response(
            {
                "batch_id": result.public_id,
                "ingestion_id": result.ingestion_id,
                "dataset_id": result.dataset_id,
                "status": result.status,
                "observation_count": result.observation_count,
            },
            duplicate=result.duplicate,
        )

    @router.post("/v1/admin/trade-indicators/{batch_id}/publish")
    def publish_trade_batch(
        batch_id: str,
        request: TradePublicationRequest,
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
                batch_id,
                publisher_id=x_actor_id,
                reason=request.reason,
                rule_version=request.rule_version,
                idempotency_key=idempotency_key,
            )
        except TradeBatchNotFoundError as error:
            raise _error(404, "TRADE_BATCH_NOT_FOUND", str(error)) from error
        except TradePublicationConflictError as error:
            raise _error(409, "TRADE_PUBLICATION_CONFLICT", str(error)) from error
        except ValueError as error:
            raise _error(422, "TRADE_PUBLICATION_NOT_READY", str(error)) from error
        return _response(result.projection, duplicate=result.duplicate)

    @router.get("/v1/trade/overview")
    def get_trade_overview() -> dict[str, object]:
        result = service.current_overview()
        return _response(None if result is None else result.projection)

    return router


def _response(data: object, *, duplicate: bool = False) -> dict[str, object]:
    return {
        "data": data,
        "meta": {
            "contract_version": "1.0",
            "request_id": str(uuid4()),
            "duplicate": duplicate,
        },
        "error": None,
    }


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})
