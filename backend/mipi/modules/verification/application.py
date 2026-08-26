from typing import Protocol

from mipi.modules.verification.domain import ReviewDecision, ReviewDecisionResult


class ReviewRepository(Protocol):
    def decide(self, review_task_id: str, decision: ReviewDecision) -> ReviewDecisionResult: ...


class ReviewService:
    def __init__(self, repository: ReviewRepository) -> None:
        self._repository = repository

    def decide(
        self, review_task_id: str, decision: ReviewDecision
    ) -> ReviewDecisionResult:
        return self._repository.decide(review_task_id, decision)
