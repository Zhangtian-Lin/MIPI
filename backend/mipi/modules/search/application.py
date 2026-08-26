from typing import Protocol

from mipi.modules.search.domain import SearchResults, normalize_query


class SearchRepository(Protocol):
    def search(self, query: str, *, limit: int) -> SearchResults: ...


class SearchService:
    def __init__(self, repository: SearchRepository) -> None:
        self._repository = repository

    def search(self, query: str, *, limit: int = 20) -> SearchResults:
        return self._repository.search(normalize_query(query), limit=limit)
