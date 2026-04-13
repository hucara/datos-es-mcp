"""
Client for the datos.gob.es open data catalog API (CKAN-based).

datos.gob.es is Spain's national open data portal with 90,000+ datasets
from all public administrations (national, regional, and local).

API docs: https://datos.gob.es/en/apidata
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
    query: str,
    theme: str | None = None,
    publisher: str | None = None,
    format: str | None = None,
    page: int = 1,
    page_size: int = 20,
    session: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """
    Search for datasets in the datos.gob.es catalog using the CKAN API.

    Args:
        query: Search keywords (searches title, description, tags).
        theme: NTI topic category (e.g. "sector-publico", "economia", "medio-ambiente").
        publisher: Publisher/organization name filter.
        format: File format filter (e.g. "CSV", "JSON", "XML").
        page: Page number (1-based).
        page_size: Results per page (max 100).

    Returns:
        dict with 'results' (list of datasets), 'count' (total), 'page', 'page_size'.
    """
    own = session is None
    if own:
        session = httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
    assert session is not None
    try:
        base_url = get_api_url("datos_gob_es")
        url = f"{base_url}catalog/api/action/package_search"

        fq_parts = []
        if theme:
            fq_parts.append(f'theme_id:"{theme}"')
        if publisher:
            fq_parts.append(f'organization:"{publisher}"')
        if format:
            fq_parts.append(f'res_format:"{format.upper()}"')

        params: dict[str, Any] = {
            "q": query,
            "rows": min(page_size, 100),
            "start": (page - 1) * page_size,
            "sort": "score desc, metadata_modified desc",
        }
        if fq_parts:
            params["fq"] = " AND ".join(fq_parts)

        data = await fetch_json(session, url, log_prefix="datos.gob.es", params=params)
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
                    "organization": (ds.get("organization") or {}).get("title"),
                    "publisher": ds.get("publisher", {}).get("name") if ds.get("publisher") else None,
                    "themes": [t.get("label", t.get("id", "")) for t in ds.get("theme", [])],
                    "tags": [t.get("display_name", t.get("name", "")) for t in ds.get("tags", [])],
                    "formats": formats,
                    "resources_count": len(resources),
                    "last_modified": ds.get("metadata_modified"),
                    "url": f"https://datos.gob.es/es/catalogo/{ds.get('name', ds.get('id', ''))}",
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


async def get_dataset_details(
    dataset_id: str,
    session: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """
    Get full metadata for a specific dataset by its ID or slug.

    Args:
        dataset_id: Dataset ID (UUID) or slug (name).

    Returns:
        Full CKAN dataset dict.
    """
    own = session is None
    if own:
        session = httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
    assert session is not None
    try:
        base_url = get_api_url("datos_gob_es")
        url = f"{base_url}catalog/api/action/package_show"
        params = {"id": dataset_id}
        data = await fetch_json(session, url, log_prefix="datos.gob.es", params=params)
        result = data.get("result", {})
        return result
    finally:
        if own:
            await session.aclose()
