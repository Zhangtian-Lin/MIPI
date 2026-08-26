import hashlib
from datetime import UTC, datetime

import pytest
from mipi.modules.collection.data_gov_my import DataGovMyConnector, ingestion_payload
from mipi.modules.collection.domain import (
    FetchedResource,
    FetchPolicy,
    InvalidCollectionPayloadError,
    SourceNotRunnableError,
    UnsafeTargetError,
    allowed_collection_limit,
    validate_external_url,
)


class FakeFetcher:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.requested_url: str | None = None

    def fetch(self, url: str, policy: FetchPolicy) -> FetchedResource:
        self.requested_url = url
        assert policy.allowed_hosts == ("api.data.gov.my",)
        return FetchedResource(
            requested_url=url,
            final_url=url,
            status_code=200,
            content_type="application/json",
            body=self.body,
            fetched_at=datetime(2026, 8, 26, 10, 0, tzinfo=UTC),
        )


def resolver_for(ip: str) -> list[tuple[object, ...]]:
    return [(2, 1, 6, "", (ip, 443))]


def test_url_policy_accepts_only_allowlisted_public_https_targets() -> None:
    validate_external_url(
        "https://api.data.gov.my/data-catalogue?id=test",
        allowed_hosts=("api.data.gov.my",),
        resolver=lambda _host, _port: resolver_for("8.8.8.8"),
    )

    with pytest.raises(UnsafeTargetError):
        validate_external_url(
            "https://api.data.gov.my/data-catalogue",
            allowed_hosts=("api.data.gov.my",),
            resolver=lambda _host, _port: resolver_for("127.0.0.1"),
        )
    with pytest.raises(UnsafeTargetError):
        validate_external_url(
            "https://example.com/data",
            allowed_hosts=("api.data.gov.my",),
            resolver=lambda _host, _port: resolver_for("8.8.8.8"),
        )


def test_source_lifecycle_gates_collection_before_network_access() -> None:
    assert (
        allowed_collection_limit(
            source_status="trial", crawl_status="approved_trial", requested_limit=10
        )
        == 10
    )
    assert (
        allowed_collection_limit(
            source_status="active", crawl_status="approved", requested_limit=100
        )
        == 100
    )
    with pytest.raises(SourceNotRunnableError):
        allowed_collection_limit(
            source_status="candidate", crawl_status="pending_terms_review", requested_limit=1
        )
    with pytest.raises(SourceNotRunnableError):
        allowed_collection_limit(
            source_status="trial", crawl_status="approved_trial", requested_limit=11
        )


def test_connector_builds_a_versioned_ingestion_envelope() -> None:
    body = b'[{"date":"2026-07-01","section":"7","exports":12.3,"imports":9.1}]'
    fetcher = FakeFetcher(body)

    output = DataGovMyConnector(fetcher).collect(
        "trade_sitc_1d", limit=1, task_id="crawl-test-1"
    )

    expected_hash = "sha256:" + hashlib.sha256(body).hexdigest()
    assert fetcher.requested_url == (
        "https://api.data.gov.my/data-catalogue?"
        "id=trade_sitc_1d&limit=1&sort=-date"
    )
    assert output.record_count == 1
    assert output.submission.content_hash == expected_hash
    assert output.submission.idempotency_key.endswith(expected_hash)
    assert output.submission.source_id == "SRC-MY-DATAGOV"
    assert output.submission.verification_hint == "F4"
    assert output.submission.metadata["license"] == "CC-BY-4.0"
    assert ingestion_payload(output.submission)["crawled_at"] == "2026-08-26T10:00:00+00:00"


def test_connector_rejects_empty_or_non_list_payloads() -> None:
    with pytest.raises(InvalidCollectionPayloadError):
        DataGovMyConnector(FakeFetcher(b"[]")).collect(
            "trade_sitc_1d", limit=1, task_id="crawl-test-empty"
        )
    with pytest.raises(InvalidCollectionPayloadError):
        DataGovMyConnector(FakeFetcher(b'{"message":"unexpected"}')).collect(
            "trade_sitc_1d", limit=1, task_id="crawl-test-object"
        )
