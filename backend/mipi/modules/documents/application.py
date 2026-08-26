from typing import Protocol

from mipi.modules.documents.domain import DocumentSubmission, DocumentVersionRecord


class DocumentRepository(Protocol):
    def register_version(
        self, submission: DocumentSubmission, *, stored_object_uri: str
    ) -> DocumentVersionRecord: ...


class RawObjectStorage(Protocol):
    def put_text(
        self,
        *,
        source_id: str,
        content_hash: str,
        content: str,
        content_type: str,
    ) -> str: ...


class DocumentService:
    def __init__(self, repository: DocumentRepository, object_storage: RawObjectStorage) -> None:
        self._repository = repository
        self._object_storage = object_storage

    def register(self, submission: DocumentSubmission) -> DocumentVersionRecord:
        stored_object_uri = submission.raw_object_uri
        if submission.raw_content is not None:
            stored_object_uri = self._object_storage.put_text(
                source_id=submission.source_id,
                content_hash=submission.content_hash,
                content=submission.raw_content,
                content_type=submission.content_type,
            )
        if stored_object_uri is None:
            raise ValueError("A raw object URI or raw content is required")
        return self._repository.register_version(
            submission, stored_object_uri=stored_object_uri
        )
