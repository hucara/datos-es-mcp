"""
Client for SEPE (Servicio Público de Empleo Estatal) employment data.

SEPE publishes open data on registered unemployment, employment contracts,
job seekers, and labor market statistics for Spain.

Data is published as datasets on datos.gob.es and the SEPE open data catalog.
We use the datos.gob.es CKAN API to search and retrieve SEPE datasets.

Reference: https://sede.sepe.gob.es/portalSede/en/datos-abiertos/catalogo-de-datos-del-SEPE
"""

import logging
from typing import Any

import httpx

from helpers.env_config import get_api_url
from helpers.http import fetch_json
from helpers.logging import MAIN_LOGGER_NAME
from helpers.user_agent import USER_AGENT

logger = logging.getLogger(MAIN_LOGGER_NAME)


async def search_employment_datasets(
    stat_type: str = "paro",
    page: int = 1,
    page_size: int = 10,
    session: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """
    Search datos.gob.es for SEPE employment statistics datasets.

    Args:
        stat_type: Type of statistics to search for. Common values:
                   "paro" — registered unemployment
                   "contratos" — employment contracts
                   "demandantes" — job seekers
                   "prestaciones" — unemployment benefits
                   "epe" — working population survey (EPA equivalent)
        page: Page number.
        page_size: Results per page.

    Returns:
        CKAN search result with matching datasets.
    """
    own = session is None
    if own:
        session = httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
    assert session is not None
    try:
        base_url = get_api_url("datos_gob_es")
        url = f"{base_url}catalog/api/action/package_search"
        query = f"SEPE {stat_type} empleo estadistica"
        params: dict[str, Any] = {
            "q": query,
            "fq": 'organization:"sepe" OR tags:"empleo" OR tags:"paro-registrado"',
            "rows": min(page_size, 100),
            "start": (page - 1) * page_size,
            "sort": "metadata_modified desc",
        }
        data = await fetch_json(session, url, log_prefix="SEPE API", params=params)
        return data.get("result", {})
    finally:
        if own:
            await session.aclose()
