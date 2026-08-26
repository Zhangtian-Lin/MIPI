from typing import Annotated
from uuid import uuid4

from fastapi import APIRouter, Query

from mipi.modules.search.application import SearchService


def create_search_router(service: SearchService) -> APIRouter:
    router = APIRouter(tags=["search"])

    @router.get("/v1/search")
    def search(
        q: Annotated[str, Query(min_length=2, max_length=100)],
        limit: Annotated[int, Query(ge=1, le=20)] = 20,
    ) -> dict[str, object]:
        result = service.search(q, limit=limit)
        return {
            "data": {
                "query": result.query,
                "groups": {
                    "events": [
                        {
                            "event": item.event,
                            "match_reason": item.match_reason,
                            "match_excerpt": item.match_excerpt,
                        }
                        for item in result.events
                    ],
                    "companies": [],
                    "projects": [],
                    "policies": [],
                    "locations": [],
                },
            },
            "meta": {
                "contract_version": "1.0",
                "request_id": str(uuid4()),
                "count": len(result.events),
            },
            "error": None,
        }

    return router
