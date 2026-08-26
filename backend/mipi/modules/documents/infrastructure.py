from io import BytesIO
from typing import cast
from urllib.parse import urlsplit

from minio import Minio
from minio.error import S3Error
from psycopg.types.json import Jsonb

from mipi.modules.documents.domain import (
    DocumentSubmission,
    DocumentVersionRecord,
    merge_l2_publication_status,
)
from mipi.modules.sources.domain import SourceNotFoundError
from mipi.shared.database import open_database
from mipi.shared.ids import new_id


class PostgresDocumentRepository:
    def __init__(self, database_url: str) -> None:
        self._database_url = database_url

    def register_version(
        self, submission: DocumentSubmission, *, stored_object_uri: str
    ) -> DocumentVersionRecord:
        with open_database(self._database_url) as connection, connection.transaction():
            connection.execute(
                "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
                (f"{submission.source_id}:{submission.canonical_url}",),
            )
            source_row = connection.execute(
                "SELECT id FROM sources WHERE public_id = %s", (submission.source_id,)
            ).fetchone()
            if source_row is None:
                raise SourceNotFoundError(submission.source_id)
            source_internal_id = source_row["id"]

            document_row = connection.execute(
                """
                SELECT id, public_id, publication_status
                FROM documents
                WHERE source_id = %s AND canonical_url = %s
                """,
                (source_internal_id, submission.canonical_url),
            ).fetchone()
            if document_row is None:
                document_row = connection.execute(
                    """
                    INSERT INTO documents (
                        public_id, source_id, canonical_url, document_type,
                        primary_language, published_at, publication_status
                    )
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id, public_id, publication_status
                    """,
                    (
                        new_id("DOC"),
                        source_internal_id,
                        submission.canonical_url,
                        submission.document_type,
                        submission.language,
                        submission.published_at,
                        submission.publication_status,
                    ),
                ).fetchone()
                assert document_row is not None
            else:
                merged_status = merge_l2_publication_status(
                    cast(str, document_row["publication_status"]),
                    submission.publication_status,
                )
                connection.execute(
                    """
                    UPDATE documents
                    SET primary_language = COALESCE(primary_language, %s),
                        published_at = COALESCE(published_at, %s),
                        publication_status = %s
                    WHERE id = %s
                    """,
                    (
                        submission.language,
                        submission.published_at,
                        merged_status,
                        document_row["id"],
                    ),
                )

            existing_version = connection.execute(
                """
                SELECT id, version_number, raw_object_uri
                FROM document_versions
                WHERE document_id = %s AND content_hash = %s
                """,
                (document_row["id"], submission.content_hash),
            ).fetchone()
            if existing_version is not None:
                return DocumentVersionRecord(
                    document_internal_id=document_row["id"],
                    document_public_id=cast(str, document_row["public_id"]),
                    version_internal_id=existing_version["id"],
                    version_number=cast(int, existing_version["version_number"]),
                    raw_object_uri=cast(str, existing_version["raw_object_uri"]),
                    created_version=False,
                )

            previous = connection.execute(
                """
                SELECT id, version_number
                FROM document_versions
                WHERE document_id = %s
                ORDER BY version_number DESC
                LIMIT 1
                """,
                (document_row["id"],),
            ).fetchone()
            version_number = 1 if previous is None else cast(int, previous["version_number"]) + 1
            previous_id = None if previous is None else previous["id"]
            version_row = connection.execute(
                """
                INSERT INTO document_versions (
                    document_id, previous_version_id, version_number, title_original,
                    raw_object_uri, content_hash, text_original, crawled_at,
                    processing_status, metadata
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 'fetched', %s)
                RETURNING id
                """,
                (
                    document_row["id"],
                    previous_id,
                    version_number,
                    submission.title_original,
                    stored_object_uri,
                    submission.content_hash,
                    submission.raw_content,
                    submission.crawled_at,
                    Jsonb(submission.metadata),
                ),
            ).fetchone()
            assert version_row is not None
            return DocumentVersionRecord(
                document_internal_id=document_row["id"],
                document_public_id=cast(str, document_row["public_id"]),
                version_internal_id=version_row["id"],
                version_number=version_number,
                raw_object_uri=stored_object_uri,
                created_version=True,
            )


class MinioRawObjectStorage:
    def __init__(
        self,
        *,
        endpoint: str,
        bucket: str,
        access_key: str,
        secret_key: str,
    ) -> None:
        parsed = urlsplit(endpoint)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise ValueError("Invalid object storage endpoint")
        self._bucket = bucket
        self._client = Minio(
            parsed.netloc,
            access_key=access_key,
            secret_key=secret_key,
            secure=parsed.scheme == "https",
        )

    def put_text(
        self,
        *,
        source_id: str,
        content_hash: str,
        content: str,
        content_type: str,
    ) -> str:
        digest = content_hash.removeprefix("sha256:")
        object_name = f"raw/{source_id}/{digest[:2]}/{digest}.txt"
        try:
            self._client.stat_object(self._bucket, object_name)
        except S3Error as error:
            if error.code not in {"NoSuchKey", "NoSuchObject", "NoSuchBucket"}:
                raise
            payload = content.encode("utf-8")
            self._client.put_object(
                self._bucket,
                object_name,
                BytesIO(payload),
                len(payload),
                content_type=content_type,
            )
        return f"s3://{self._bucket}/{object_name}"
