from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from mipi.modules.verification.application import ReviewService
from mipi.modules.verification.domain import (
    ActorRole,
    DecisionAction,
    ReviewConflictError,
    ReviewDecision,
    ReviewPermissionError,
    ReviewTaskNotFoundError,
)

Limitation = Annotated[str, Field(min_length=1, max_length=500)]


class ReviewDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    action: DecisionAction
    reason: str = Field(min_length=8, max_length=2000)
    rule_version: str = Field(default="review-v1.0", min_length=1, max_length=100)
    limitations: list[Limitation] = Field(default_factory=list, max_length=20)


def create_review_router(service: ReviewService, *, local_review_enabled: bool) -> APIRouter:
    router = APIRouter(prefix="/v1/admin/review-tasks", tags=["admin-review"])

    @router.post("/{review_task_id}/decisions")
    def decide_review(
        review_task_id: str,
        request: ReviewDecisionRequest,
        x_actor_id: Annotated[str, Header(min_length=1, max_length=200)],
        x_actor_role: Annotated[ActorRole, Header()],
    ) -> dict[str, object]:
        if not local_review_enabled:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "REVIEW_AUTH_NOT_CONFIGURED",
                    "message": "Production review decisions require an identity provider.",
                },
            )
        try:
            result = service.decide(
                review_task_id,
                ReviewDecision(
                    actor_id=x_actor_id,
                    actor_role=x_actor_role,
                    action=request.action,
                    reason=request.reason,
                    rule_version=request.rule_version,
                    limitations=tuple(item.strip() for item in request.limitations),
                ),
            )
        except ReviewTaskNotFoundError as error:
            raise _error(404, "REVIEW_TASK_NOT_FOUND", str(error)) from error
        except ReviewConflictError as error:
            raise _error(409, "REVIEW_CONFLICT", str(error)) from error
        except ReviewPermissionError as error:
            raise _error(403, "REVIEW_PERMISSION_DENIED", str(error)) from error
        except ValueError as error:
            raise _error(422, "INVALID_REVIEW_DECISION", str(error)) from error
        return {
            "data": {
                "review_task_id": result.review_task_id,
                "ingestion_id": result.ingestion_id,
                "task_status": result.task_status,
                "processing_status": result.processing_status,
                "publication_status": result.publication_status,
                "risk_level": result.risk_level,
                "decision_count": result.decision_count,
                "completed": result.completed,
            },
            "meta": {"contract_version": "1.1", "request_id": str(uuid4())},
            "error": None,
        }

    return router


def _error(status: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code=status, detail={"code": code, "message": message})
