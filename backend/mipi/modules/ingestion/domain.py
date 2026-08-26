from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from urllib.parse import urlsplit, urlunsplit
from uuid import UUID

from mipi.modules.documents.domain import DocumentType, L2PublicationStatus

CollectionRelevance = Literal["high", "medium", "low", "unknown"]
FactLevel = Literal["F0", "F1", "F2", "F3", "F4"]
ProcessingStatus = Literal["needs_review", "quarantined"]
RiskLevel = Literal["R0", "R1", "R2", "R3"]


@dataclass(frozen=True)
class IngestionSubmission:
    contract_version: str
    task_id: str
    run_id: str | None
    idempotency_key: str
    source_id: str
    url: str
    document_type: DocumentType
    language: str | None
    published_at: datetime | None
    crawled_at: datetime
    content_hash: str
    raw_object_uri: str | None
    raw_content: str | None
    content_type: str
    title_original: str | None
    collection_relevance: CollectionRelevance
    verification_hint: FactLevel | None
    publication_status: L2PublicationStatus
    metadata: dict[str, object]


@dataclass(frozen=True)
class IngestionRecord:
    internal_id: UUID
    public_id: str
    task_id: str
    source_id: str
    source_name: str
    source_grade: str
    document_id: str
    version_number: int
    canonical_url: str
    content_hash: str
    raw_object_uri: str
    collection_relevance: CollectionRelevance
    verification_hint: FactLevel | None
    publication_status: L2PublicationStatus
    processing_status: ProcessingStatus
    review_flags: tuple[str, ...]
    review_task_id: str
    review_status: str
    risk_level: RiskLevel
    created_at: datetime


@dataclass(frozen=True)
class IngestionResult:
    record: IngestionRecord
    duplicate: bool


class ContentHashMismatchError(Exception):
    pass


class IdempotencyConflictError(Exception):
    pass


class IngestionNotFoundError(Exception):
    pass


def canonicalize_url(value: str) -> str:
    parsed = urlsplit(value.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("URL must use http or https and include a host")
    scheme = parsed.scheme.lower()
    host = parsed.hostname.lower()
    port = parsed.port
    if port is not None and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    ):
        host = f"{host}:{port}"
    path = parsed.path or "/"
    return urlunsplit((scheme, host, path, parsed.query, ""))


def review_flags_for(submission: IngestionSubmission) -> tuple[str, ...]:
    flags: list[str] = []
    if submission.raw_content is None:
        flags.append("external_object_not_verified")
    if submission.collection_relevance == "unknown":
        flags.append("relevance_unknown")
    if submission.language is None:
        flags.append("language_unknown")
    if submission.verification_hint is None:
        flags.append("fact_level_unassessed")
    if _contains_instruction_like_content(submission.raw_content):
        flags.append("untrusted_instruction_pattern")
    return tuple(flags)


def processing_status_for(flags: tuple[str, ...]) -> ProcessingStatus:
    if "untrusted_instruction_pattern" in flags:
        return "quarantined"
    return "needs_review"


def risk_level_for(flags: tuple[str, ...], source_grade: str) -> RiskLevel:
    if "untrusted_instruction_pattern" in flags:
        return "R3"
    if source_grade in {"S5", "S6"} or "external_object_not_verified" in flags:
        return "R2"
    if flags:
        return "R1"
    return "R0"


def _contains_instruction_like_content(content: str | None) -> bool:
    if content is None:
        return False
    lowered = content.lower()
    markers = (
        "ignore previous instructions",
        "ignore all previous instructions",
        "system prompt",
        "developer message",
        "忽略之前的指令",
        "忽略以上指令",
        "系统提示词",
    )
    return any(marker in lowered for marker in markers)
