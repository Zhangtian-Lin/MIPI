import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

SourceGrade = Literal["S1", "S2", "S3", "S4", "S5", "S6"]
SourceStatus = Literal["candidate", "trial", "active", "degraded", "inactive", "retired"]
RobotsStatus = Literal["unknown", "allowed", "limited", "disallowed", "not_applicable"]
SourceActorRole = Literal["source_admin", "system_admin"]
SourceDecisionAction = Literal[
    "approve_for_trial", "activate", "degrade", "deactivate", "retire"
]


@dataclass(frozen=True)
class SourceRegistration:
    public_id: str
    name: str
    owner: str
    base_url: str
    source_grade: SourceGrade
    authority_scope: tuple[str, ...]
    languages: tuple[str, ...]


@dataclass(frozen=True)
class SourceRecord:
    internal_id: UUID
    public_id: str
    name: str
    owner: str
    base_url: str
    source_grade: SourceGrade
    authority_scope: tuple[str, ...]
    languages: tuple[str, ...]
    status: SourceStatus
    crawl_status: str
    robots_status: RobotsStatus
    terms_reviewed_at: datetime | None
    identity_verified_at: datetime | None
    last_reviewed_at: datetime | None
    review_due_at: datetime | None
    access_notes: str | None


@dataclass(frozen=True)
class SourceRegistrationResult:
    source: SourceRecord
    duplicate: bool


@dataclass(frozen=True)
class SourceDecision:
    idempotency_key: str
    actor_id: str
    actor_role: SourceActorRole
    action: SourceDecisionAction
    reason: str
    rule_version: str
    identity_verified: bool
    terms_reviewed: bool
    authority_scope_reviewed: bool
    robots_status: RobotsStatus | None
    evidence_urls: tuple[str, ...]
    access_notes: str | None


@dataclass(frozen=True)
class SourceTransition:
    status: SourceStatus
    crawl_status: str
    robots_status: RobotsStatus


@dataclass(frozen=True)
class SourceDecisionResult:
    decision_id: str
    source: SourceRecord
    duplicate: bool


class SourceNotFoundError(Exception):
    pass


class SourceConflictError(Exception):
    pass


class SourceTransitionError(Exception):
    pass


class SourceDecisionConflictError(Exception):
    pass


def source_decision_fingerprint(source_id: str, decision: SourceDecision) -> str:
    payload = {
        "source_id": source_id,
        "actor_id": decision.actor_id,
        "actor_role": decision.actor_role,
        "action": decision.action,
        "reason": decision.reason.strip(),
        "rule_version": decision.rule_version,
        "identity_verified": decision.identity_verified,
        "terms_reviewed": decision.terms_reviewed,
        "authority_scope_reviewed": decision.authority_scope_reviewed,
        "robots_status": decision.robots_status,
        "evidence_urls": list(decision.evidence_urls),
        "access_notes": decision.access_notes,
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()


def resolve_source_transition(
    *,
    current_status: SourceStatus,
    current_robots_status: RobotsStatus,
    identity_is_verified: bool,
    terms_are_reviewed: bool,
    has_authority_scope: bool,
    has_languages: bool,
    decision: SourceDecision,
    current_access_notes: str | None = None,
) -> SourceTransition:
    if len(decision.reason.strip()) < 8:
        raise ValueError("Decision reason must contain at least 8 characters")
    robots_status = decision.robots_status or current_robots_status
    transitions: dict[tuple[SourceStatus, SourceDecisionAction], tuple[SourceStatus, str]] = {
        ("candidate", "approve_for_trial"): ("trial", "approved_trial"),
        ("candidate", "retire"): ("retired", "retired"),
        ("trial", "activate"): ("active", "approved"),
        ("trial", "deactivate"): ("inactive", "disabled"),
        ("active", "degrade"): ("degraded", "restricted"),
        ("active", "deactivate"): ("inactive", "disabled"),
        ("degraded", "activate"): ("active", "approved"),
        ("degraded", "deactivate"): ("inactive", "disabled"),
        ("inactive", "activate"): ("active", "approved"),
        ("inactive", "retire"): ("retired", "retired"),
    }
    target = transitions.get((current_status, decision.action))
    if target is None:
        raise SourceTransitionError(
            f"Action {decision.action} is not allowed while source is {current_status}"
        )

    if decision.action == "approve_for_trial":
        if not has_authority_scope or not has_languages:
            raise ValueError("Trial approval requires authority scope and languages")
        if not (
            decision.identity_verified
            and decision.terms_reviewed
            and decision.authority_scope_reviewed
        ):
            raise ValueError(
                "Trial approval requires identity, terms, and authority scope review"
            )
        _require_allowed_access(robots_status, decision.access_notes)
    if decision.action == "activate":
        if not (identity_is_verified and terms_are_reviewed):
            raise ValueError("Activation requires previously verified identity and terms")
        if not decision.evidence_urls:
            raise ValueError("Activation requires at least one trial evidence URL")
        _require_allowed_access(
            robots_status, decision.access_notes or current_access_notes
        )

    return SourceTransition(status=target[0], crawl_status=target[1], robots_status=robots_status)


def _require_allowed_access(robots_status: RobotsStatus, access_notes: str | None) -> None:
    if robots_status in {"unknown", "disallowed"}:
        raise ValueError(
            f"Automatic access cannot be approved when robots status is {robots_status}"
        )
    if robots_status == "limited" and not (access_notes and access_notes.strip()):
        raise ValueError("Limited access requires explicit access notes")
