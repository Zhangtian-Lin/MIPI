import hashlib
import json
from dataclasses import dataclass
from datetime import date
from typing import Literal

EventType = Literal[
    "investment",
    "project_update",
    "policy_update",
    "company_update",
    "tender",
    "governance_update",
]
DatePrecision = Literal["day", "month", "year", "unknown"]


@dataclass(frozen=True)
class EventProjectionInput:
    ingestion_id: str
    event_type: EventType
    title_zh: str
    summary_zh: str
    event_date: date | None
    event_date_precision: DatePrecision
    industries: tuple[str, ...]
    states: tuple[str, ...]
    span_start: int
    span_end: int
    quote_original: str
    quote_zh: str
    model_id: str
    prompt_version: str
    conflict: bool


@dataclass(frozen=True)
class EventRecord:
    event_id: str
    ingestion_id: str
    publication_status: str
    fact_level: str
    title_zh: str
    summary_zh: str
    event_type: str
    event_date: str | None
    industries: tuple[str, ...]
    states: tuple[str, ...]
    conflict: bool
    blockers: tuple[str, ...]
    publication_id: str | None = None
    revision: int | None = None
    duplicate: bool = False


@dataclass(frozen=True)
class EventIngestionCandidate:
    ingestion_id: str
    document_id: str
    source_name: str
    source_grade: str
    canonical_url: str
    title_original: str | None
    language: str | None
    created_at: str
    projected_event_count: int


@dataclass(frozen=True)
class EventWorkbench:
    eligible_ingestions: tuple[EventIngestionCandidate, ...]
    events: tuple[EventRecord, ...]


@dataclass(frozen=True)
class EventSourceText:
    ingestion_id: str
    document_id: str
    title_original: str | None
    language: str | None
    text_original: str


@dataclass(frozen=True)
class EventPublication:
    event_id: str
    projection: dict[str, object]
    duplicate: bool


class EventNotFoundError(Exception):
    pass


class EventProjectionConflictError(Exception):
    pass


class EventPublicationConflictError(Exception):
    pass


def validate_event_input(value: EventProjectionInput, original_text: str) -> None:
    if len(value.title_zh.strip()) < 5 or len(value.title_zh.strip()) > 160:
        raise ValueError("Chinese title must contain 5 to 160 characters")
    if len(value.summary_zh.strip()) < 20 or len(value.summary_zh.strip()) > 800:
        raise ValueError("Chinese summary must contain 20 to 800 characters")
    if not value.industries or not value.states:
        raise ValueError("At least one industry and state scope are required")
    if value.span_start < 0 or value.span_end <= value.span_start:
        raise ValueError("Evidence span offsets are invalid")
    if value.span_end > len(original_text):
        raise ValueError("Evidence span exceeds the preserved original text")
    if original_text[value.span_start : value.span_end] != value.quote_original:
        raise ValueError("Evidence quote does not match the preserved original text")
    if not value.quote_original.strip() or len(value.quote_original) > 500:
        raise ValueError("Original evidence quote must contain at most 500 characters")
    if not value.quote_zh.strip() or len(value.quote_zh) > 500:
        raise ValueError("Chinese evidence quote must contain at most 500 characters")


def event_publication_blockers(record: EventRecord, evidence_count: int) -> tuple[str, ...]:
    blockers: list[str] = []
    if record.fact_level == "F0":
        blockers.append("Publication requires at least F1 verification")
    if evidence_count < 1:
        blockers.append("Publication requires an exact source span")
    if not record.industries or not record.states:
        blockers.append("Publication requires industry and state scope")
    if record.publication_status == "published":
        blockers.append("Event is already published")
    return tuple(blockers)


def request_fingerprint(payload: dict[str, object]) -> str:
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode()).hexdigest()
