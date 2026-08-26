from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

DocumentType = Literal["html", "pdf", "social", "api", "other"]
L2PublicationStatus = Literal["raw_only", "staged", "under_review", "quarantined"]


@dataclass(frozen=True)
class DocumentSubmission:
    source_id: str
    canonical_url: str
    document_type: DocumentType
    language: str | None
    published_at: datetime | None
    crawled_at: datetime
    content_hash: str
    raw_object_uri: str | None
    raw_content: str | None
    content_type: str
    title_original: str | None
    publication_status: L2PublicationStatus
    metadata: dict[str, object]


@dataclass(frozen=True)
class DocumentVersionRecord:
    document_internal_id: UUID
    document_public_id: str
    version_internal_id: UUID
    version_number: int
    raw_object_uri: str
    created_version: bool


def merge_l2_publication_status(current: str, incoming: L2PublicationStatus) -> str:
    if current == "quarantined" or incoming == "quarantined":
        return "quarantined"
    l2_order = {"discovered": 0, "raw_only": 1, "staged": 2, "under_review": 3}
    if current not in l2_order:
        return current
    return max(current, incoming, key=lambda value: l2_order[value])
