import hashlib
from contextlib import AbstractContextManager
from dataclasses import replace
from typing import Protocol
from uuid import UUID

from mipi.modules.documents.application import DocumentService
from mipi.modules.documents.domain import DocumentSubmission, DocumentVersionRecord
from mipi.modules.ingestion.domain import (
    ContentHashMismatchError,
    IdempotencyConflictError,
    IngestionRecord,
    IngestionResult,
    IngestionSubmission,
    canonicalize_url,
    processing_status_for,
    review_flags_for,
    risk_level_for,
)
from mipi.modules.sources.application import SourceService


class IngestionRepository(Protocol):
    def idempotency_lock(self, key: str) -> AbstractContextManager[None]: ...

    def find_by_idempotency_key(self, key: str) -> IngestionRecord | None: ...

    def save(
        self,
        submission: IngestionSubmission,
        *,
        document: DocumentVersionRecord,
        source_internal_id: UUID,
        canonical_url: str,
        source_grade: str,
        review_flags: tuple[str, ...],
        processing_status: str,
        risk_level: str,
    ) -> IngestionResult: ...

    def get(self, public_id: str) -> IngestionRecord: ...

    def list(self, *, limit: int, status: str | None) -> list[IngestionRecord]: ...


class IngestionService:
    def __init__(
        self,
        *,
        sources: SourceService,
        documents: DocumentService,
        repository: IngestionRepository,
    ) -> None:
        self._sources = sources
        self._documents = documents
        self._repository = repository

    def submit(self, submission: IngestionSubmission) -> IngestionResult:
        canonical_url = canonicalize_url(submission.url)
        self._verify_hash(submission)

        with self._repository.idempotency_lock(submission.idempotency_key):
            return self._submit_locked(submission, canonical_url)

    def _submit_locked(
        self, submission: IngestionSubmission, canonical_url: str
    ) -> IngestionResult:

        existing = self._repository.find_by_idempotency_key(submission.idempotency_key)
        if existing is not None:
            if (
                existing.source_id == submission.source_id
                and existing.canonical_url == canonical_url
                and existing.content_hash == submission.content_hash
            ):
                return IngestionResult(record=existing, duplicate=True)
            raise IdempotencyConflictError(submission.idempotency_key)

        source = self._sources.get(submission.source_id)
        flags = review_flags_for(submission)
        processing_status = processing_status_for(flags)
        publication_status = (
            "quarantined"
            if processing_status == "quarantined"
            else submission.publication_status
        )
        normalized = replace(submission, publication_status=publication_status)
        document = self._documents.register(
            DocumentSubmission(
                source_id=normalized.source_id,
                canonical_url=canonical_url,
                document_type=normalized.document_type,
                language=normalized.language,
                published_at=normalized.published_at,
                crawled_at=normalized.crawled_at,
                content_hash=normalized.content_hash,
                raw_object_uri=normalized.raw_object_uri,
                raw_content=normalized.raw_content,
                content_type=normalized.content_type,
                title_original=normalized.title_original,
                publication_status=normalized.publication_status,
                metadata=normalized.metadata,
            )
        )
        return self._repository.save(
            normalized,
            document=document,
            source_internal_id=source.internal_id,
            canonical_url=canonical_url,
            source_grade=source.source_grade,
            review_flags=flags,
            processing_status=processing_status,
            risk_level=risk_level_for(flags, source.source_grade),
        )

    def get(self, public_id: str) -> IngestionRecord:
        return self._repository.get(public_id)

    def list(self, *, limit: int = 50, status: str | None = None) -> list[IngestionRecord]:
        return self._repository.list(limit=limit, status=status)

    @staticmethod
    def _verify_hash(submission: IngestionSubmission) -> None:
        if submission.raw_content is None:
            return
        actual = "sha256:" + hashlib.sha256(submission.raw_content.encode("utf-8")).hexdigest()
        if actual != submission.content_hash.lower():
            raise ContentHashMismatchError(
                f"Expected {submission.content_hash.lower()}, calculated {actual}"
            )
