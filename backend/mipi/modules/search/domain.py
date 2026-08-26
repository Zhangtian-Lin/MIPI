from dataclasses import dataclass
from typing import Literal

SearchMatchReason = Literal["title_zh", "summary_zh", "evidence_original", "source_name"]


@dataclass(frozen=True)
class EventSearchHit:
    event: dict[str, object]
    match_reason: SearchMatchReason
    match_excerpt: str


@dataclass(frozen=True)
class SearchResults:
    query: str
    events: tuple[EventSearchHit, ...]


def normalize_query(value: str) -> str:
    normalized = " ".join(value.split())
    if len(normalized) < 2:
        raise ValueError("Search query must contain at least 2 characters")
    if len(normalized) > 100:
        raise ValueError("Search query must contain at most 100 characters")
    return normalized


def escape_like(value: str) -> str:
    return "%" + value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_") + "%"
