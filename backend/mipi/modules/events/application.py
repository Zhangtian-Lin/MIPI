from typing import Protocol

from mipi.modules.events.domain import (
    EventProjectionInput,
    EventPublication,
    EventRecord,
    EventSourceText,
    EventWorkbench,
)


class EventRepository(Protocol):
    def project(
        self,
        value: EventProjectionInput,
        *,
        actor_id: str,
        rule_version: str,
        idempotency_key: str,
    ) -> EventRecord: ...

    def publish(
        self,
        event_id: str,
        *,
        publisher_id: str,
        reason: str,
        rule_version: str,
        idempotency_key: str,
    ) -> EventPublication: ...

    def workbench(self, *, limit: int) -> EventWorkbench: ...
    def get_source(self, ingestion_id: str) -> EventSourceText: ...
    def list_published(
        self, *, limit: int, industry: str | None, state: str | None, event_type: str | None
    ) -> tuple[dict[str, object], ...]: ...
    def get_published(self, event_id: str) -> dict[str, object] | None: ...


class EventService:
    def __init__(self, repository: EventRepository) -> None:
        self._repository = repository

    def project(self, value: EventProjectionInput, **kwargs: str) -> EventRecord:
        return self._repository.project(value, **kwargs)

    def publish(self, event_id: str, **kwargs: str) -> EventPublication:
        return self._repository.publish(event_id, **kwargs)

    def workbench(self, *, limit: int = 100) -> EventWorkbench:
        return self._repository.workbench(limit=limit)

    def get_source(self, ingestion_id: str) -> EventSourceText:
        return self._repository.get_source(ingestion_id)

    def list_published(
        self,
        *,
        limit: int = 10,
        industry: str | None = None,
        state: str | None = None,
        event_type: str | None = None,
    ) -> tuple[dict[str, object], ...]:
        return self._repository.list_published(
            limit=limit, industry=industry, state=state, event_type=event_type
        )

    def get_published(self, event_id: str) -> dict[str, object] | None:
        return self._repository.get_published(event_id)
