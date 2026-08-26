from typing import Protocol

from mipi.modules.trade.domain import TradeBatch, TradePublication


class TradeRepository(Protocol):
    def project(self, ingestion_id: str, *, actor_id: str, rule_version: str) -> TradeBatch: ...

    def publish(
        self,
        batch_id: str,
        *,
        publisher_id: str,
        reason: str,
        rule_version: str,
        idempotency_key: str,
    ) -> TradePublication: ...

    def current_overview(self) -> TradePublication | None: ...


class TradeService:
    def __init__(self, repository: TradeRepository) -> None:
        self._repository = repository

    def project(self, ingestion_id: str, *, actor_id: str, rule_version: str) -> TradeBatch:
        return self._repository.project(ingestion_id, actor_id=actor_id, rule_version=rule_version)

    def publish(
        self,
        batch_id: str,
        *,
        publisher_id: str,
        reason: str,
        rule_version: str,
        idempotency_key: str,
    ) -> TradePublication:
        if len(reason.strip()) < 8:
            raise ValueError("Publication reason must contain at least 8 characters")
        return self._repository.publish(
            batch_id,
            publisher_id=publisher_id,
            reason=reason,
            rule_version=rule_version,
            idempotency_key=idempotency_key,
        )

    def current_overview(self) -> TradePublication | None:
        return self._repository.current_overview()
