from typing import Protocol

from mipi.modules.sources.domain import (
    SourceDecision,
    SourceDecisionResult,
    SourceRecord,
    SourceRegistration,
    SourceRegistrationResult,
)


class SourceRepository(Protocol):
    def register(
        self, registration: SourceRegistration, *, actor_id: str
    ) -> SourceRegistrationResult: ...

    def get(self, public_id: str) -> SourceRecord: ...

    def list(self, limit: int) -> list[SourceRecord]: ...

    def decide(self, source_id: str, decision: SourceDecision) -> SourceDecisionResult: ...


class SourceService:
    def __init__(self, repository: SourceRepository) -> None:
        self._repository = repository

    def register(
        self, registration: SourceRegistration, *, actor_id: str
    ) -> SourceRegistrationResult:
        if not registration.authority_scope or not registration.languages:
            raise ValueError("Source registration requires authority scope and languages")
        return self._repository.register(registration, actor_id=actor_id)

    def get(self, public_id: str) -> SourceRecord:
        return self._repository.get(public_id)

    def list(self, limit: int = 100) -> list[SourceRecord]:
        return self._repository.list(limit)

    def decide(self, source_id: str, decision: SourceDecision) -> SourceDecisionResult:
        return self._repository.decide(source_id, decision)
