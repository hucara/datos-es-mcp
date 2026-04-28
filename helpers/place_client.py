"""
Client for Spain's Public Procurement Platform (PLACE).

PLACE (Plataforma de Contratación del Sector Público) is the central platform
where all public sector entities publish their procurement notices and contract
award notices. It covers contracts from the state, autonomous communities,
local entities, and public enterprises.

The platform provides open data files in ATOM/XML format and bulk CSV downloads.
We use the datos.gob.es semantic API to surface relevant datasets and their
download URLs, since PLACE does not expose a general-purpose REST query API.

Reference: https://contrataciondelestado.es/wps/portal/plataforma/datos_abiertos
"""

import logging
from typing import Any

import httpx

from helpers import datos_gob_es_client
from helpers.logging import MAIN_LOGGER_NAME
from helpers.user_agent import USER_AGENT

logger = logging.getLogger(MAIN_LOGGER_NAME)

# PLACE ATOM feed for recently published tender notices (last 7 days rolling)
_ATOM_FEED_URL = "https://contrataciondelestado.es/sindicacion/sindicacion_643/licitacionesPerfilesContratanteCompleto3.atom"


async def search_datasets(
    query: str,
    page: int = 1,
    page_size: int = 20,
    session: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """
    Search for public procurement datasets on datos.gob.es.

    Uses the datos.gob.es semantic API (title keyword search) to surface
    PLACE datasets. Useful for finding bulk data on contracts, tenders, and awards.

    Args:
        query: Search terms (e.g. "licitaciones", "adjudicaciones", "contratos").
        page: Page number (1-based).
        page_size: Results per page.

    Returns:
        dict with 'results' (list of normalized datasets) and 'count'.
    """
    return await datos_gob_es_client.search_datasets(
        query=query,
        page=page,
        page_size=page_size,
        session=session,
    )


async def get_atom_feed(
    session: httpx.AsyncClient | None = None,
) -> str:
    """
    Fetch the latest PLACE ATOM feed (XML) with recently published tender notices.

    Returns the raw XML string of the ATOM feed. Parse with an XML library for
    individual entries.
    """
    own = session is None
    if own:
        session = httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
    assert session is not None
    try:
        resp = await session.get(_ATOM_FEED_URL, timeout=30.0)
        resp.raise_for_status()
        return resp.text
    except httpx.HTTPError as exc:
        logger.error("PLACE ATOM feed request failed: %s", exc)
        raise
    finally:
        if own:
            await session.aclose()
