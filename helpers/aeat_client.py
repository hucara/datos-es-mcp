"""
Client for AEAT (Agencia Estatal de Administración Tributaria) statistical data.

AEAT publishes statistical data on datos.gob.es. This client uses the
datos.gob.es semantic API (publisher endpoint) to surface AEAT datasets.

Publisher code: EA0028512 (Agencia Estatal de Administración Tributaria)

Key statistical publications:
  - Anuario Estadístico: IRPF, IVA, Patrimonio, Sociedades, labor market
  - Informes de Recaudación Tributaria: annual tax revenue by type
  - Estadísticas por impuesto: detailed per-tax breakdowns
  - Muestras de datos fiscales: anonymized microdata for research

Reference:
  https://sede.agenciatributaria.gob.es/Sede/estadisticas.html
  https://datos.gob.es — publisher code: EA0028512
"""

import logging
from typing import Any

import httpx

from helpers import datos_gob_es_client
from helpers.logging import MAIN_LOGGER_NAME

logger = logging.getLogger(MAIN_LOGGER_NAME)

# AEAT publisher code on datos.gob.es semantic API
_AEAT_PUBLISHER = "EA0028512"

# Dataset types with search keywords and descriptions
_KNOWN_DATASETS: dict[str, dict[str, str]] = {
    "anuario_estadistico": {
        "keyword": "anuario",
        "description": "Anuario Estadístico AEAT — IRPF, IVA, Patrimonio, Sociedades, labor market",
    },
    "recaudacion": {
        "keyword": "recaudacion",
        "description": "Informes anuales de Recaudación Tributaria — annual tax revenue totals",
    },
    "irpf": {
        "keyword": "IRPF",
        "description": "IRPF statistics — income distribution, tax brackets, deductions",
    },
    "iva": {
        "keyword": "IVA",
        "description": "IVA/VAT statistics — declared sales, purchases, refunds",
    },
    "sociedades": {
        "keyword": "sociedades",
        "description": "Corporate tax (Impuesto sobre Sociedades) — profits, effective rates",
    },
}


async def search_aeat_datasets(
    stat_type: str = "anuario_estadistico",
    custom_query: str | None = None,
    page: int = 1,
    page_size: int = 10,
    session: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """
    Search datos.gob.es for AEAT statistical datasets.

    Uses the publisher/EA0028512.json endpoint to list all AEAT datasets,
    optionally filtered by a keyword match on title.

    Args:
        stat_type: One of the known AEAT dataset types:
                   "anuario_estadistico", "recaudacion", "irpf", "iva", "sociedades"
        custom_query: Override the search keyword.
        page: Page number.
        page_size: Results per page.

    Returns:
        dict with "results" (list of normalized datasets), "count", "page", "page_size".
    """
    entry = _KNOWN_DATASETS.get(stat_type, {})
    keyword = custom_query or entry.get("keyword") or stat_type

    own = session is None
    if own:
        import httpx as _httpx

        from helpers.user_agent import USER_AGENT

        session = _httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
    assert session is not None

    try:
        # Fetch from AEAT publisher — get enough to filter by keyword
        raw = await datos_gob_es_client.search_datasets(
            query=keyword,
            publisher=_AEAT_PUBLISHER,
            page=page,
            page_size=page_size,
            session=session,
        )
        results = raw.get("results", [])

        # If publisher returns unfiltered list, filter by keyword in title/description
        if keyword and results:
            kw_lower = keyword.lower()
            filtered = [
                r
                for r in results
                if kw_lower in r.get("title", "").lower()
                or kw_lower in r.get("description", "").lower()
            ]
            # Only use filtered if it found matches; otherwise return all
            if filtered:
                results = filtered

        return {
            "results": results,
            "count": raw.get("count", len(results)),
            "page": page,
            "page_size": len(results),
        }
    finally:
        if own:
            await session.aclose()
