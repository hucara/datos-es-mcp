"""
Client for SEPE (Servicio Público de Empleo Estatal) employment data.

SEPE publishes open data on registered unemployment, employment contracts,
job seekers, and labor market statistics for Spain.

Data is published as datasets on datos.gob.es. We use the datos.gob.es
semantic API (title keyword search) to retrieve SEPE datasets.

Reference: https://sede.sepe.gob.es/portalSede/en/datos-abiertos/catalogo-de-datos-del-SEPE
"""

import logging
from typing import Any

import httpx

from helpers import datos_gob_es_client
from helpers.logging import MAIN_LOGGER_NAME

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
        dict with 'results' (list of normalized datasets) and 'count'.
    """
    # Use stat_type as the title keyword — specific enough to target SEPE datasets
    query = f"{stat_type} SEPE empleo"
    return await datos_gob_es_client.search_datasets(
        query=query,
        page=page,
        page_size=page_size,
        session=session,
    )
