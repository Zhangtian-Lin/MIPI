import ipaddress
import socket
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import cast
from urllib.parse import urlsplit

ResolvedAddress = tuple[object, object, object, object, tuple[object, ...]]
Resolver = Callable[[str, int], Sequence[ResolvedAddress]]


@dataclass(frozen=True)
class FetchPolicy:
    allowed_hosts: tuple[str, ...]
    max_bytes: int = 2_000_000
    timeout_seconds: float = 15.0
    user_agent: str = "MIPI-Collector/0.1 (+https://github.com/Zhangtian-Lin/MIPI)"


@dataclass(frozen=True)
class FetchedResource:
    requested_url: str
    final_url: str
    status_code: int
    content_type: str
    body: bytes
    fetched_at: datetime


class CollectionError(Exception):
    pass


class UnsafeTargetError(CollectionError):
    pass


class ResponseTooLargeError(CollectionError):
    pass


class UnexpectedContentTypeError(CollectionError):
    pass


class InvalidCollectionPayloadError(CollectionError):
    pass


class SourceNotRunnableError(CollectionError):
    pass


class CollectionHttpError(CollectionError):
    def __init__(self, status_code: int, retry_after: str | None = None) -> None:
        self.status_code = status_code
        self.retry_after = retry_after
        super().__init__(f"Collection endpoint returned HTTP {status_code}")


class CollectionNetworkError(CollectionError):
    pass


def validate_external_url(
    url: str,
    *,
    allowed_hosts: tuple[str, ...],
    resolver: Resolver | None = None,
) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise UnsafeTargetError("Collection targets must use HTTPS and include a host")
    hostname = parsed.hostname.lower().rstrip(".")
    if hostname not in {host.lower().rstrip(".") for host in allowed_hosts}:
        raise UnsafeTargetError(f"Host is not in the connector allowlist: {hostname}")
    if parsed.username or parsed.password:
        raise UnsafeTargetError("Collection URLs must not contain user information")
    if parsed.port not in {None, 443}:
        raise UnsafeTargetError("Collection targets must use the standard HTTPS port")

    resolve = resolver or _resolve_host
    try:
        addresses = resolve(hostname, 443)
    except OSError as error:
        raise CollectionNetworkError(f"DNS resolution failed for {hostname}") from error
    if not addresses:
        raise UnsafeTargetError(f"Host did not resolve: {hostname}")
    for address in addresses:
        raw_ip = str(address[4][0])
        try:
            ip = ipaddress.ip_address(raw_ip)
        except ValueError as error:
            raise UnsafeTargetError(f"Resolver returned an invalid IP: {raw_ip}") from error
        if not ip.is_global:
            raise UnsafeTargetError(f"Host resolved to a non-public address: {raw_ip}")


def allowed_collection_limit(
    *, source_status: str, crawl_status: str, requested_limit: int
) -> int:
    if requested_limit < 1:
        raise ValueError("Collection limit must be positive")
    if source_status == "trial" and crawl_status == "approved_trial":
        if requested_limit > 10:
            raise SourceNotRunnableError("Trial collection is limited to 10 records per run")
        return requested_limit
    if source_status == "active" and crawl_status == "approved":
        return requested_limit
    raise SourceNotRunnableError(
        f"Source cannot collect while status={source_status} and crawl_status={crawl_status}"
    )


def _resolve_host(hostname: str, port: int) -> Sequence[ResolvedAddress]:
    return cast(
        Sequence[ResolvedAddress],
        socket.getaddrinfo(hostname, port, type=socket.SOCK_STREAM),
    )
