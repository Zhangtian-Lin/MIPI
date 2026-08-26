"""MIPI worker entry point for explicitly invoked, source-gated collection."""

import argparse
import json
from datetime import UTC, datetime
from http.client import HTTPMessage
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener
from uuid import uuid4

from mipi.modules.collection.data_gov_my import (
    DATASETS,
    SOURCE_ID,
    DataGovMyConnector,
    ingestion_payload,
)
from mipi.modules.collection.domain import (
    CollectionError,
    CollectionHttpError,
    SourceNotRunnableError,
    allowed_collection_limit,
)
from mipi.modules.collection.infrastructure import SafeHttpFetcher


class LocalMipiApi:
    def __init__(self, base_url: str, *, timeout_seconds: float = 10.0) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        parsed = urlsplit(self._base_url)
        if parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1"}:
            raise ValueError("Worker submission is restricted to the local HTTP API")

    def source(self, source_id: str) -> dict[str, object]:
        envelope = self._request("GET", "/admin/sources?limit=500")
        data = envelope.get("data")
        if not isinstance(data, list):
            raise RuntimeError("Local API returned an invalid source registry")
        for item in data:
            if isinstance(item, dict) and item.get("source_id") == source_id:
                return item
        raise SourceNotRunnableError(f"Source is not registered locally: {source_id}")

    def submit(self, payload: dict[str, object]) -> dict[str, object]:
        return self._request("POST", "/ingestion/records", payload)

    def _request(
        self, method: str, path: str, payload: dict[str, object] | None = None
    ) -> dict[str, object]:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            f"{self._base_url}{path}",
            data=body,
            method=method,
            headers={"Accept": "application/json", "Content-Type": "application/json"},
        )
        try:
            with build_opener(_RejectRedirectHandler()).open(
                request, timeout=self._timeout_seconds
            ) as response:
                result: Any = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Local API returned HTTP {error.code}: {detail}") from error
        except (URLError, json.JSONDecodeError) as error:
            raise RuntimeError(f"Local API request failed: {error}") from error
        if not isinstance(result, dict):
            raise RuntimeError("Local API returned a non-object response")
        return result


class _RejectRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> Request | None:
        return None


def main() -> None:
    parser = argparse.ArgumentParser(description="MIPI collection worker")
    subparsers = parser.add_subparsers(dest="command")
    data_gov = subparsers.add_parser(
        "data-gov-my", help="Collect an approved data.gov.my dataset snapshot"
    )
    data_gov.add_argument("--dataset", choices=sorted(DATASETS), required=True)
    data_gov.add_argument("--limit", type=int, default=10)
    data_gov.add_argument("--task-id")
    data_gov.add_argument("--api-base-url", default="http://localhost:8000/v1")
    data_gov.add_argument(
        "--submit",
        action="store_true",
        help="Submit to local L2 ingestion; otherwise emit a dry-run report",
    )
    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        return
    if args.command == "data-gov-my":
        _run_data_gov_my(args)


def _run_data_gov_my(args: argparse.Namespace) -> None:
    started_at = datetime.now(UTC)
    task_id = args.task_id or f"crawl-data-gov-my-{uuid4()}"
    api = LocalMipiApi(args.api_base_url)
    try:
        source = api.source(SOURCE_ID)
        limit = allowed_collection_limit(
            source_status=str(source.get("status")),
            crawl_status=str(source.get("crawl_status")),
            requested_limit=args.limit,
        )
        output = DataGovMyConnector(SafeHttpFetcher()).collect(
            args.dataset,
            limit=limit,
            task_id=task_id,
        )
        report: dict[str, object] = {
            "contract_version": "1.0",
            "status": "succeeded",
            "mode": "submit" if args.submit else "dry_run",
            "started_at": started_at.isoformat(),
            "finished_at": datetime.now(UTC).isoformat(),
            **output.report(),
            "source_status": source.get("status"),
            "source_crawl_status": source.get("crawl_status"),
            "checked_source_count": 1,
            "success_count": 1,
            "failure_count": 0,
            "skipped_count": 0,
            "submitted_count": 1 if args.submit else 0,
        }
        if args.submit:
            response = api.submit(ingestion_payload(output.submission))
            report["ingestion"] = response.get("data")
            report["ingestion_meta"] = response.get("meta")
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
    except (CollectionError, RuntimeError, ValueError) as error:
        report = {
            "contract_version": "1.0",
            "status": "blocked" if isinstance(error, SourceNotRunnableError) else "failed",
            "mode": "submit" if args.submit else "dry_run",
            "started_at": started_at.isoformat(),
            "finished_at": datetime.now(UTC).isoformat(),
            "source_id": SOURCE_ID,
            "dataset_id": args.dataset,
            "task_id": task_id,
            "checked_source_count": 1,
            "success_count": 0,
            "failure_count": 0 if isinstance(error, SourceNotRunnableError) else 1,
            "skipped_count": 1 if isinstance(error, SourceNotRunnableError) else 0,
            "submitted_count": 0,
            "error_type": type(error).__name__,
            "error": str(error),
        }
        if isinstance(error, CollectionHttpError):
            report["http_status"] = error.status_code
            report["retry_after"] = error.retry_after
        print(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True))
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
