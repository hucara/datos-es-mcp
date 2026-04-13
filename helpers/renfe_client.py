"""
Client for Renfe open data portal (data.renfe.com).

Renfe's open data portal is a CKAN instance exposing train schedules,
station data, real-time GPS positions, and operational statistics.

Available data:
- GTFS schedules for AVE (high-speed), long-distance, medium-distance
- GTFS schedules for Cercanías (commuter) and Rodalies
- Station locations and metadata
- Real-time vehicle positions (AVE/long-distance)

Reference: https://data.renfe.com/
"""

import logging
from typing import Any

import httpx

from helpers.env_config import get_api_url
from helpers.http import fetch_json
from helpers.logging import MAIN_LOGGER_NAME
from helpers.user_agent import USER_AGENT

logger = logging.getLogger(MAIN_LOGGER_NAME)


async def search_datasets(
    query: str = "",
    format: str | None = None,
    page: int = 1,
    page_size: int = 20,
    session: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """
    Search datasets in the Renfe open data portal.

    Args:
        query: Search keywords (e.g. "GTFS", "horarios", "estaciones", "cercanias").
        format: File format filter (e.g. "GTFS", "CSV", "JSON").
        page: Page number (1-based).
        page_size: Results per page.

    Returns:
        CKAN search result dict with 'results' list and 'count'.
    """
    own = session is None
    if own:
        session = httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
    assert session is not None
    try:
        base_url = get_api_url("renfe")
        url = f"{base_url}api/action/package_search"

        params: dict[str, Any] = {
            "q": query,
            "rows": min(page_size, 100),
            "start": (page - 1) * page_size,
            "sort": "metadata_modified desc",
        }
        if format:
            params["fq"] = f'res_format:"{format.upper()}"'

        data = await fetch_json(session, url, log_prefix="Renfe API", params=params)
        result = data.get("result", {})

        datasets = result.get("results", [])
        normalized = []
        for ds in datasets:
            resources = ds.get("resources", [])
            formats = list({r.get("format", "").upper() for r in resources if r.get("format")})
            normalized.append(
                {
                    "id": ds.get("id"),
                    "name": ds.get("name"),
                    "title": ds.get("title") or ds.get("name", ""),
                    "description": (ds.get("notes") or "")[:300],
                    "formats": formats,
                    "resources_count": len(resources),
                    "last_modified": ds.get("metadata_modified"),
                    "resources": [
                        {
                            "id": r.get("id"),
                            "name": r.get("name") or r.get("description"),
                            "format": r.get("format", "").upper(),
                            "url": r.get("url"),
                            "last_modified": r.get("last_modified"),
                        }
                        for r in resources
                    ],
                    "url": f"https://data.renfe.com/dataset/{ds.get('name', ds.get('id', ''))}",
                }
            )

        return {
            "results": normalized,
            "count": result.get("count", len(normalized)),
            "page": page,
            "page_size": len(normalized),
        }
    finally:
        if own:
            await session.aclose()
