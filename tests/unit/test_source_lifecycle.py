import pytest
from mipi.modules.sources.domain import (
    SourceDecision,
    SourceTransitionError,
    resolve_source_transition,
)


def decision(
    action: str,
    *,
    robots_status: str | None = "allowed",
    evidence_urls: tuple[str, ...] = (),
) -> SourceDecision:
    return SourceDecision(
        idempotency_key="source-decision-test-key",
        actor_id="source-admin-1",
        actor_role="source_admin",
        action=action,  # type: ignore[arg-type]
        reason="Source identity and access conditions were reviewed.",
        rule_version="source-review-v1.0",
        identity_verified=True,
        terms_reviewed=True,
        authority_scope_reviewed=True,
        robots_status=robots_status,  # type: ignore[arg-type]
        evidence_urls=evidence_urls,
        access_notes=None,
    )


def test_candidate_can_enter_trial_only_after_all_checks() -> None:
    result = resolve_source_transition(
        current_status="candidate",
        current_robots_status="unknown",
        identity_is_verified=False,
        terms_are_reviewed=False,
        has_authority_scope=True,
        has_languages=True,
        decision=decision("approve_for_trial"),
    )

    assert result.status == "trial"
    assert result.crawl_status == "approved_trial"


def test_unknown_or_disallowed_access_cannot_enter_trial() -> None:
    with pytest.raises(ValueError):
        resolve_source_transition(
            current_status="candidate",
            current_robots_status="unknown",
            identity_is_verified=False,
            terms_are_reviewed=False,
            has_authority_scope=True,
            has_languages=True,
            decision=decision("approve_for_trial", robots_status="unknown"),
        )


def test_trial_activation_requires_observed_evidence() -> None:
    with pytest.raises(ValueError):
        resolve_source_transition(
            current_status="trial",
            current_robots_status="allowed",
            identity_is_verified=True,
            terms_are_reviewed=True,
            has_authority_scope=True,
            has_languages=True,
            decision=decision("activate", evidence_urls=()),
        )

    result = resolve_source_transition(
        current_status="trial",
        current_robots_status="allowed",
        identity_is_verified=True,
        terms_are_reviewed=True,
        has_authority_scope=True,
        has_languages=True,
        decision=decision("activate", evidence_urls=("https://example.test/sample",)),
    )
    assert result.status == "active"
    assert result.crawl_status == "approved"


def test_limited_source_reuses_reviewed_access_notes_during_activation() -> None:
    result = resolve_source_transition(
        current_status="trial",
        current_robots_status="limited",
        identity_is_verified=True,
        terms_are_reviewed=True,
        has_authority_scope=True,
        has_languages=True,
        decision=decision(
            "activate",
            robots_status="limited",
            evidence_urls=("https://example.test/sample",),
        ),
        current_access_notes="Only the public notices path may be collected weekly.",
    )

    assert result.status == "active"


def test_active_source_must_be_deactivated_before_retirement() -> None:
    with pytest.raises(SourceTransitionError):
        resolve_source_transition(
            current_status="active",
            current_robots_status="allowed",
            identity_is_verified=True,
            terms_are_reviewed=True,
            has_authority_scope=True,
            has_languages=True,
            decision=decision("retire"),
        )
