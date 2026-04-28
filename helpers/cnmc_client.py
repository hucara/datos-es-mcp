"""
Client for the CNMC Data portal (Comisión Nacional de los Mercados y la Competencia).

CNMC is Spain's national competition and markets regulatory authority, overseeing
energy (electricity, gas), telecommunications, postal services, transport, and media.

The CNMC Data portal is a CKAN instance with statistics on regulated markets:
energy prices, consumption, capacity, coverage, competition indicators, etc.

Reference: https://data.cnmc.es/
"""

import logging
from typing import Any

import httpx

from helpers.env_config import get_api_url
from helpers.http import fetch_json
from helpers.logging import MAIN_LOGGER_NAME
from helpers.user_agent import USER_AGENT

logger = logging.getLogger(MAIN_LOGGER_NAME)

_SECTOR_QUERIES = {
    "electricity": "electricidad energia electrica",
    "gas": "gas natural",
    "telecom": "telecomunicaciones banda ancha internet movil",
    "postal": "servicios postales correo",
    "transport": "transporte ferroviario aeropuertos",
    "audiovisual": "audiovisual television radio",
    "competition": "competencia mercado",
}


async def search_datasets(
    query: str,
    sector: str | None = None,
    page: int = 1,
    page_size: int = 20,
    session: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """
    Search datasets in the CNMC Data portal.

    Args:
        query: Search keywords.
        sector: Sector filter — one of: "electricity", "gas", "telecom",
                "postal", "transport", "audiovisual", "competition".
        page: Page number.
        page_size: Results per page.

    Returns:
        CKAN search result dict.
    """
    own = session is None
    if own:
        session = httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
    assert session is not None
    try:
        base_url = get_api_url("cnmc")
        url = f"{base_url}api/action/package_search"

        full_query = query
        if sector and sector in _SECTOR_QUERIES:
            full_query = f"{query} {_SECTOR_QUERIES[sector]}".strip()

        params: dict[str, Any] = {
            "q": full_query,
            "rows": min(page_size, 100),
            "start": (page - 1) * page_size,
            "sort": "metadata_modified desc",
        }

        data = await fetch_json(session, url, log_prefix="CNMC API", params=params)
        result = data.get("result", {})

        datasets = result.get("results", [])
        normalized = []
        for ds in datasets:
            resources = ds.get("resources", [])
            formats = list(
                {r.get("format", "").upper() for r in resources if r.get("format")}
            )
            normalized.append(
                {
                    "id": ds.get("id"),
                    "name": ds.get("name"),
                    "title": ds.get("title") or ds.get("name", ""),
                    "description": (ds.get("notes") or "")[:300],
                    "formats": formats,
                    "resources_count": len(resources),
                    "last_modified": ds.get("metadata_modified"),
                    "url": f"https://data.cnmc.es/dataset/{ds.get('name', ds.get('id', ''))}",
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
