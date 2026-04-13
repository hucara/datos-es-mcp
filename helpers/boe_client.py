"""
Client for the BOE (Boletín Oficial del Estado) Open Data API.

Provides access to Spain's Official State Gazette, the BORME (Official Mercantile
Registry Gazette), and the consolidated legislation collection.

API docs: https://www.boe.es/datosabiertos/api/api.php
"""

import logging
from typing import Any

import httpx

from helpers.env_config import get_api_url
from helpers.http import fetch_json
from helpers.logging import MAIN_LOGGER_NAME
from helpers.user_agent import USER_AGENT

logger = logging.getLogger(MAIN_LOGGER_NAME)

_BOE_HEADERS = {"Accept": "application/json"}


async def get_boe_summary(
    date: str,
    session: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """
    Get the BOE daily summary for a given date.

    Args:
        date: Date in YYYYMMDD format (e.g. "20241201").

    Returns:
        BOE summary dict with sections, departments, documents.
    """
    own = session is None
    if own:
        session = httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
    assert session is not None
    try:
        base_url = get_api_url("boe")
        url = f"{base_url}boe/sumario/{date}"
        return await fetch_json(session, url, log_prefix="BOE API", headers=_BOE_HEADERS)
    finally:
        if own:
            await session.aclose()


async def get_borme_summary(
    date: str,
    session: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """
    Get the BORME (Mercantile Registry) daily summary for a given date.

    Args:
        date: Date in YYYYMMDD format.

    Returns:
        BORME summary dict.
    """
    own = session is None
    if own:
        session = httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
    assert session is not None
    try:
        base_url = get_api_url("boe")
        url = f"{base_url}borme/sumario/{date}"
        return await fetch_json(session, url, log_prefix="BOE API", headers=_BOE_HEADERS)
    finally:
        if own:
            await session.aclose()


async def search_legislation(
    query: str,
    from_date: str | None = None,
    to_date: str | None = None,
    offset: int = 0,
    limit: int = 20,
    session: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """
    Search consolidated legislation (Legislación Consolidada) in the BOE.

    Args:
        query: Search text (searches title and text of regulations).
        from_date: Start date filter in YYYY-MM-DD format.
        to_date: End date filter in YYYY-MM-DD format.
        offset: Pagination offset.
        limit: Number of results per page (max 100).

    Returns:
        Dict with 'response' containing 'docs' list and 'numFound'.
    """
    own = session is None
    if own:
        session = httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
    assert session is not None
    try:
        base_url = get_api_url("boe")
        url = f"{base_url}legislacion-consolidada"
        params: dict[str, Any] = {
            "query": query,
            "offset": offset,
            "limit": min(limit, 100),
        }
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        return await fetch_json(session, url, log_prefix="BOE API", headers=_BOE_HEADERS, params=params)
    finally:
        if own:
            await session.aclose()


async def get_legislation_metadata(
    law_id: str,
    session: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """
    Get full metadata for a specific consolidated regulation.

    Args:
        law_id: BOE regulation identifier (e.g. "BOE-A-1978-31229").

    Returns:
        Metadata dict.
    """
    own = session is None
    if own:
        session = httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
    assert session is not None
    try:
        base_url = get_api_url("boe")
        url = f"{base_url}legislacion-consolidada/id/{law_id}/metadatos"
        return await fetch_json(session, url, log_prefix="BOE API", headers=_BOE_HEADERS)
    finally:
        if own:
            await session.aclose()
