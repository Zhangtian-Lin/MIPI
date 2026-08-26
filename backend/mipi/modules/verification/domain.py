from dataclasses import dataclass
from typing import Literal

ActorRole = Literal["reviewer", "senior_reviewer", "publisher", "security_compliance"]
DecisionAction = Literal[
    "approve", "approve_with_limits", "return_for_fix", "reject", "quarantine"
]
ReviewTaskStatus = Literal[
    "queued",
    "in_review",
    "approved",
    "approved_with_limits",
    "returned",
    "rejected",
    "quarantined",
]


@dataclass(frozen=True)
class ReviewDecision:
    actor_id: str
    actor_role: ActorRole
    action: DecisionAction
    reason: str
    rule_version: str
    limitations: tuple[str, ...]


@dataclass(frozen=True)
class ExistingDecision:
    actor_id: str
    actor_role: ActorRole
    action: DecisionAction


@dataclass(frozen=True)
class WorkflowResult:
    task_status: ReviewTaskStatus
    processing_status: str
    publication_status: str
    completed: bool


@dataclass(frozen=True)
class ReviewDecisionResult:
    review_task_id: str
    ingestion_id: str
    task_status: ReviewTaskStatus
    processing_status: str
    publication_status: str
    risk_level: str
    decision_count: int
    completed: bool


class ReviewTaskNotFoundError(Exception):
    pass


class ReviewConflictError(Exception):
    pass


class ReviewPermissionError(Exception):
    pass


def fact_level_for_official_trade_dataset(
    *,
    source_id: str,
    source_grade: str,
    dataset_id: str,
    ingestion_status: str,
    verification_hint: str | None,
) -> str:
    """Resolve the narrow deterministic F rule for reviewed DOSM trade records."""
    if ingestion_status != "approved":
        raise ValueError("Only an approved L2 ingestion can enter L3 verification")
    if source_id != "SRC-MY-DATAGOV" or source_grade != "S2":
        raise ValueError("Official trade verification requires the registered data.gov.my source")
    if dataset_id != "trade_sitc_1d" or verification_hint != "F4":
        raise ValueError("The ingestion is not eligible for the official trade F4 rule")
    return "F4"


def resolve_workflow(
    *,
    current_status: str,
    risk_level: str,
    decision: ReviewDecision,
    existing: tuple[ExistingDecision, ...],
) -> WorkflowResult:
    if current_status not in {"queued", "in_review"}:
        raise ReviewConflictError(f"Review task is already {current_status}")
    if any(item.actor_id == decision.actor_id for item in existing):
        raise ReviewConflictError("This actor has already decided this review task")
    if len(decision.reason.strip()) < 8:
        raise ValueError("Decision reason must contain at least 8 characters")
    if decision.action == "approve_with_limits" and not any(
        item.strip() for item in decision.limitations
    ):
        raise ValueError("approve_with_limits requires at least one limitation")

    if decision.action == "quarantine":
        return WorkflowResult("quarantined", "quarantined", "quarantined", True)
    if decision.actor_role == "security_compliance":
        raise ReviewPermissionError("Security/compliance may quarantine but not editorially decide")
    if decision.action == "return_for_fix":
        return WorkflowResult("returned", "returned", "staged", True)
    if decision.action == "reject":
        return WorkflowResult("rejected", "rejected", "rejected", True)

    required_roles = _required_approval_roles(risk_level)
    if decision.actor_role not in _allowed_approval_roles(risk_level):
        raise ReviewPermissionError(
            f"Role {decision.actor_role} is not an approval role for {risk_level}"
        )
    approvals = (
        *existing,
        ExistingDecision(decision.actor_id, decision.actor_role, decision.action),
    )
    approval_roles = {
        item.actor_role
        for item in approvals
        if item.action in {"approve", "approve_with_limits"}
    }
    if risk_level in {"R0", "R1"} and "senior_reviewer" in approval_roles:
        approval_roles.add("reviewer")
    completed = required_roles.issubset(approval_roles)
    if not completed:
        return WorkflowResult("in_review", "in_review", "under_review", False)
    has_limits = any(item.action == "approve_with_limits" for item in approvals)
    task_status: ReviewTaskStatus = "approved_with_limits" if has_limits else "approved"
    return WorkflowResult(task_status, "approved", "staged", True)


def _required_approval_roles(risk_level: str) -> set[ActorRole]:
    if risk_level in {"R0", "R1"}:
        return {"reviewer"}
    if risk_level == "R2":
        return {"reviewer", "senior_reviewer"}
    if risk_level == "R3":
        return {"reviewer", "senior_reviewer", "publisher"}
    raise ValueError(f"Unsupported risk level: {risk_level}")


def _allowed_approval_roles(risk_level: str) -> set[ActorRole]:
    if risk_level in {"R0", "R1"}:
        return {"reviewer", "senior_reviewer"}
    return _required_approval_roles(risk_level)
