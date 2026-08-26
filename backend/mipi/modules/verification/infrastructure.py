from typing import Any, cast

from psycopg.types.json import Jsonb

from mipi.modules.verification.domain import (
    ActorRole,
    DecisionAction,
    ExistingDecision,
    ReviewDecision,
    ReviewDecisionResult,
    ReviewTaskNotFoundError,
    resolve_workflow,
)
from mipi.shared.database import open_database
from mipi.shared.ids import new_id


class PostgresReviewRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def decide(
        self, review_task_id: str, decision: ReviewDecision
    ) -> ReviewDecisionResult:
        with open_database(self._database_url) as connection, connection.transaction():
            task = connection.execute(
                """
                SELECT rt.*, ir.public_id AS ingestion_public_id,
                       ir.task_id AS ingestion_task_id, ir.document_id,
                       ir.document_version_id, ir.processing_status,
                       ir.publication_status
                FROM review_tasks rt
                JOIN ingestion_records ir
                  ON rt.object_type = 'ingestion_record' AND rt.object_id = ir.id
                WHERE rt.public_id = %s
                FOR UPDATE OF rt, ir
                """,
                (review_task_id,),
            ).fetchone()
            if task is None:
                raise ReviewTaskNotFoundError(review_task_id)

            rows = connection.execute(
                """
                SELECT actor_id, actor_role, decision
                FROM review_decisions
                WHERE review_task_id = %s
                ORDER BY created_at
                """,
                (task["id"],),
            ).fetchall()
            existing = tuple(self._existing_decision(row) for row in rows)
            workflow = resolve_workflow(
                current_status=cast(str, task["status"]),
                risk_level=cast(str, task["risk_level"]),
                decision=decision,
                existing=existing,
            )

            decision_public_id = new_id("DEC")
            connection.execute(
                """
                INSERT INTO review_decisions (
                    public_id, review_task_id, actor_id, actor_role, decision,
                    reason, rule_version, limitations
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    decision_public_id,
                    task["id"],
                    decision.actor_id,
                    decision.actor_role,
                    decision.action,
                    decision.reason.strip(),
                    decision.rule_version,
                    Jsonb(list(decision.limitations)),
                ),
            )
            connection.execute(
                """
                UPDATE review_tasks
                SET status = %s,
                    decision_reason = %s,
                    decided_at = CASE WHEN %s THEN now() ELSE NULL END
                WHERE id = %s
                """,
                (
                    workflow.task_status,
                    decision.reason.strip(),
                    workflow.completed,
                    task["id"],
                ),
            )
            connection.execute(
                """
                UPDATE ingestion_records
                SET processing_status = %s, publication_status = %s
                WHERE id = %s
                """,
                (workflow.processing_status, workflow.publication_status, task["object_id"]),
            )
            connection.execute(
                "UPDATE documents SET publication_status = %s WHERE id = %s",
                (workflow.publication_status, task["document_id"]),
            )
            version_status = self._version_status(workflow.processing_status)
            connection.execute(
                "UPDATE document_versions SET processing_status = %s WHERE id = %s",
                (version_status, task["document_version_id"]),
            )
            connection.execute(
                """
                INSERT INTO audit_log (
                    actor_type, actor_id, action, object_type, object_id,
                    before_json, after_json, reason, task_id
                )
                VALUES ('human', %s, 'review.decision.recorded', 'review_task', %s,
                        %s, %s, %s, %s)
                """,
                (
                    decision.actor_id,
                    review_task_id,
                    Jsonb(
                        {
                            "task_status": task["status"],
                            "processing_status": task["processing_status"],
                            "publication_status": task["publication_status"],
                        }
                    ),
                    Jsonb(
                        {
                            "decision_id": decision_public_id,
                            "decision": decision.action,
                            "actor_role": decision.actor_role,
                            "task_status": workflow.task_status,
                            "processing_status": workflow.processing_status,
                            "publication_status": workflow.publication_status,
                            "limitations": list(decision.limitations),
                        }
                    ),
                    decision.reason.strip(),
                    task["ingestion_task_id"],
                ),
            )
            connection.execute(
                """
                INSERT INTO outbox (event_type, aggregate_type, aggregate_id, payload)
                VALUES ('review.decision.recorded', 'review_task', %s, %s)
                """,
                (
                    task["id"],
                    Jsonb(
                        {
                            "review_task_id": review_task_id,
                            "ingestion_id": task["ingestion_public_id"],
                            "decision_id": decision_public_id,
                            "task_status": workflow.task_status,
                            "completed": workflow.completed,
                        }
                    ),
                ),
            )
            return ReviewDecisionResult(
                review_task_id=review_task_id,
                ingestion_id=cast(str, task["ingestion_public_id"]),
                task_status=workflow.task_status,
                processing_status=workflow.processing_status,
                publication_status=workflow.publication_status,
                risk_level=cast(str, task["risk_level"]),
                decision_count=len(existing) + 1,
                completed=workflow.completed,
            )

    @staticmethod
    def _existing_decision(row: dict[str, Any]) -> ExistingDecision:
        return ExistingDecision(
            actor_id=cast(str, row["actor_id"]),
            actor_role=cast(ActorRole, row["actor_role"]),
            action=cast(DecisionAction, row["decision"]),
        )

    @staticmethod
    def _version_status(processing_status: str) -> str:
        return {
            "in_review": "under_review",
            "approved": "ingestion_approved",
            "returned": "returned",
            "rejected": "rejected",
            "quarantined": "quarantined",
        }[processing_status]
