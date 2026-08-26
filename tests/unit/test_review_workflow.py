import pytest
from mipi.modules.verification.domain import (
    ExistingDecision,
    ReviewConflictError,
    ReviewDecision,
    ReviewPermissionError,
    resolve_workflow,
)


def decision(
    role: str = "reviewer", action: str = "approve", actor: str = "reviewer-1"
) -> ReviewDecision:
    return ReviewDecision(
        actor_id=actor,
        actor_role=role,  # type: ignore[arg-type]
        action=action,  # type: ignore[arg-type]
        reason="Evidence and source were checked.",
        rule_version="review-v1.0",
        limitations=("Do not infer completion",) if action == "approve_with_limits" else (),
    )


def test_r1_reviewer_approval_completes_without_publication() -> None:
    result = resolve_workflow(
        current_status="queued", risk_level="R1", decision=decision(), existing=()
    )

    assert result.task_status == "approved"
    assert result.processing_status == "approved"
    assert result.publication_status == "staged"
    assert result.completed is True


def test_senior_reviewer_can_handle_low_risk_task() -> None:
    result = resolve_workflow(
        current_status="queued",
        risk_level="R1",
        decision=decision("senior_reviewer", actor="senior-1"),
        existing=(),
    )
    assert result.task_status == "approved"


def test_r2_requires_reviewer_and_senior_reviewer() -> None:
    first = decision()
    pending = resolve_workflow(
        current_status="queued", risk_level="R2", decision=first, existing=()
    )
    assert pending.task_status == "in_review"
    assert pending.completed is False

    completed = resolve_workflow(
        current_status="in_review",
        risk_level="R2",
        decision=decision("senior_reviewer", actor="senior-1"),
        existing=(ExistingDecision(first.actor_id, first.actor_role, first.action),),
    )
    assert completed.task_status == "approved"
    assert completed.completed is True


def test_r3_requires_publisher_after_two_reviewers() -> None:
    existing = (
        ExistingDecision("reviewer-1", "reviewer", "approve"),
        ExistingDecision("senior-1", "senior_reviewer", "approve_with_limits"),
    )
    result = resolve_workflow(
        current_status="in_review",
        risk_level="R3",
        decision=decision("publisher", actor="publisher-1"),
        existing=existing,
    )

    assert result.task_status == "approved_with_limits"
    assert result.completed is True


def test_same_actor_cannot_decide_twice() -> None:
    with pytest.raises(ReviewConflictError):
        resolve_workflow(
            current_status="in_review",
            risk_level="R2",
            decision=decision(actor="reviewer-1"),
            existing=(ExistingDecision("reviewer-1", "reviewer", "approve"),),
        )


def test_security_role_can_quarantine_but_cannot_approve() -> None:
    quarantined = resolve_workflow(
        current_status="queued",
        risk_level="R3",
        decision=decision("security_compliance", "quarantine", "security-1"),
        existing=(),
    )
    assert quarantined.task_status == "quarantined"

    with pytest.raises(ReviewPermissionError):
        resolve_workflow(
            current_status="queued",
            risk_level="R1",
            decision=decision("security_compliance", actor="security-1"),
            existing=(),
        )
