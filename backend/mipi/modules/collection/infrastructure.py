from datetime import UTC, datetime
from http.client import HTTPMessage
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

from mipi.modules.collection.domain import (
    CollectionHttpError,
    CollectionNetworkError,
    FetchedResource,
    FetchPolicy,
    ResponseTooLargeError,
    UnexpectedContentTypeError,
    validate_external_url,
)


class SafeHttpFetcher:
    def fetch(self, url: str, policy: FetchPolicy) -> FetchedResource:
        validate_external_url(url, allowed_hosts=policy.allowed_hosts)
        opener = build_opener(_SafeRedirectHandler(policy))
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": policy.user_agent,
            },
            method="GET",
        )
        try:
            with opener.open(request, timeout=policy.timeout_seconds) as response:
                final_url = response.geturl()
                validate_external_url(final_url, allowed_hosts=policy.allowed_hosts)
                content_type = response.headers.get_content_type().lower()
                if content_type not in {"application/json", "application/geo+json"}:
                    raise UnexpectedContentTypeError(
                        f"Expected JSON, received {content_type}"
                    )
                content_length = response.headers.get("Content-Length")
                if content_length is not None and int(content_length) > policy.max_bytes:
                    raise ResponseTooLargeError(
                        f"Response exceeds {policy.max_bytes} bytes"
                    )
                body = response.read(policy.max_bytes + 1)
                if len(body) > policy.max_bytes:
                    raise ResponseTooLargeError(
                        f"Response exceeds {policy.max_bytes} bytes"
                    )
                return FetchedResource(
                    requested_url=url,
                    final_url=final_url,
                    status_code=response.status,
                    content_type=content_type,
                    body=body,
                    fetched_at=datetime.now(UTC),
                )
        except HTTPError as error:
            raise CollectionHttpError(
                error.code, retry_after=error.headers.get("Retry-After")
            ) from error
        except URLError as error:
            raise CollectionNetworkError(str(error.reason)) from error


class _SafeRedirectHandler(HTTPRedirectHandler):
    def __init__(self, policy: FetchPolicy) -> None:
        super().__init__()
        self._policy = policy

    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> Request | None:
        validate_external_url(newurl, allowed_hosts=self._policy.allowed_hosts)
        return super().redirect_request(req, fp, code, msg, headers, newurl)
