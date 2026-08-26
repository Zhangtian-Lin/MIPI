import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Protocol
from urllib.parse import urlencode

from mipi.modules.collection.domain import (
    FetchedResource,
    FetchPolicy,
    InvalidCollectionPayloadError,
)
from mipi.modules.ingestion.domain import (
    CollectionRelevance,
    FactLevel,
    IngestionSubmission,
)

SOURCE_ID = "SRC-MY-DATAGOV"
API_HOST = "api.data.gov.my"
API_ENDPOINT = f"https://{API_HOST}/data-catalogue"
LICENSE = "CC-BY-4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by/4.0/"


@dataclass(frozen=True)
class DatasetSpec:
    dataset_id: str
    title: str
    relevance: CollectionRelevance
    verification_hint: FactLevel
    sort: str | None = None


DATASETS: dict[str, DatasetSpec] = {
    "trade_sitc_1d": DatasetSpec(
        dataset_id="trade_sitc_1d",
        title="Monthly Trade by SITC Section (1 digit)",
        relevance="high",
        verification_hint="F4",
        sort="-date",
    ),
    "iowrt_2d": DatasetSpec(
        dataset_id="iowrt_2d",
        title="Wholesale & Retail Trade by Division (2 digit)",
        relevance="medium",
        verification_hint="F4",
        sort="-date",
    ),
    "datasets": DatasetSpec(
        dataset_id="datasets",
        title="List of Datasets on data.gov.my",
        relevance="medium",
        verification_hint="F2",
    ),
}


class Fetcher(Protocol):
    def fetch(self, url: str, policy: FetchPolicy) -> FetchedResource: ...


@dataclass(frozen=True)
class ConnectorOutput:
    submission: IngestionSubmission
    record_count: int
    byte_count: int
    dataset_id: str

    def report(self) -> dict[str, object]:
        return {
            "task_id": self.submission.task_id,
            "run_id": self.submission.run_id,
            "idempotency_key": self.submission.idempotency_key,
            "source_id": self.submission.source_id,
            "dataset_id": self.dataset_id,
            "url": self.submission.url,
            "crawled_at": self.submission.crawled_at.isoformat(),
            "content_hash": self.submission.content_hash,
            "record_count": self.record_count,
            "byte_count": self.byte_count,
            "collection_relevance": self.submission.collection_relevance,
            "verification_hint": self.submission.verification_hint,
            "publication_status": self.submission.publication_status,
        }


class DataGovMyConnector:
    policy = FetchPolicy(allowed_hosts=(API_HOST,), max_bytes=2_000_000)

    def __init__(self, fetcher: Fetcher) -> None:
        self._fetcher = fetcher

    def collect(self, dataset_id: str, *, limit: int, task_id: str) -> ConnectorOutput:
        spec = DATASETS.get(dataset_id)
        if spec is None:
            raise ValueError(f"Unsupported data.gov.my dataset: {dataset_id}")
        if not 1 <= limit <= 1000:
            raise ValueError("Dataset limit must be between 1 and 1000")
        query: dict[str, str | int] = {"id": spec.dataset_id, "limit": limit}
        if spec.sort:
            query["sort"] = spec.sort
        url = f"{API_ENDPOINT}?{urlencode(query)}"
        fetched = self._fetcher.fetch(url, self.policy)
        try:
            text = fetched.body.decode("utf-8")
            payload = json.loads(text)
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise InvalidCollectionPayloadError("API did not return valid UTF-8 JSON") from error
        if not isinstance(payload, list) or not payload:
            raise InvalidCollectionPayloadError("API response must be a non-empty JSON list")
        content_hash = "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()
        run_id = f"data-gov-my:{spec.dataset_id}:{fetched.fetched_at:%Y%m%dT%H%M%SZ}"
        submission = IngestionSubmission(
            contract_version="1.1",
            task_id=task_id,
            run_id=run_id,
            idempotency_key=f"{SOURCE_ID}:{spec.dataset_id}:{content_hash}",
            source_id=SOURCE_ID,
            url=fetched.final_url,
            document_type="api",
            language="en",
            published_at=None,
            crawled_at=fetched.fetched_at,
            content_hash=content_hash,
            raw_object_uri=None,
            raw_content=text,
            content_type="application/json; charset=utf-8",
            title_original=spec.title,
            collection_relevance=spec.relevance,
            verification_hint=spec.verification_hint,
            publication_status="staged",
            metadata={
                "connector": "data_gov_my.v1",
                "dataset_id": spec.dataset_id,
                "record_count": len(payload),
                "discovery_method": "official_open_api",
                "license": LICENSE,
                "license_url": LICENSE_URL,
                "attribution": "Government of Malaysia / data.gov.my",
                "rate_limit": "4 requests per minute",
            },
        )
        return ConnectorOutput(
            submission=submission,
            record_count=len(payload),
            byte_count=len(fetched.body),
            dataset_id=spec.dataset_id,
        )


def ingestion_payload(submission: IngestionSubmission) -> dict[str, object]:
    payload = asdict(submission)
    payload["crawled_at"] = submission.crawled_at.isoformat()
    payload["published_at"] = (
        None if submission.published_at is None else submission.published_at.isoformat()
    )
    return payload
