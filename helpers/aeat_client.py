"""
Client for AEAT (Agencia Estatal de Administración Tributaria) statistical data.

AEAT does not expose a query API. Its statistical data is published as:
1. Downloadable Excel/CSV files on datos.gob.es
2. An interactive web app (anuario estadístico) for custom tables
3. PDF reports (annual tax collection reports)

We use the datos.gob.es CKAN API to surface AEAT datasets and provide
direct download URLs for statistical files.

Key statistical publications:
  - Anuario Estadístico: IRPF, IVA, Patrimonio, Sociedades, labor market
  - Informes de Recaudación Tributaria: annual tax revenue by type
  - Estadísticas por impuesto: detailed per-tax breakdowns
  - Muestras de datos fiscales: anonymized microdata for research

Reference:
  https://sede.agenciatributaria.gob.es/Sede/estadisticas.html
  https://datos.gob.es — publisher: agencia-tributaria
"""

import logging
from typing import Any

import httpx

from helpers.env_config import get_api_url
from helpers.http import fetch_json
from helpers.logging import MAIN_LOGGER_NAME
from helpers.user_agent import USER_AGENT

logger = logging.getLogger(MAIN_LOGGER_NAME)

# Direct dataset IDs on datos.gob.es for key AEAT statistical publications
_KNOWN_DATASETS = {
    "anuario_estadistico": {
        "id": "ea0028512-https-www-agenciatributaria-es-aeat-internet-datosabiertos-catalogo-hacienda-anuario-estadistico-shtml",
        "description": "Anuario Estadístico AEAT — IRPF, IVA, Patrimonio, Sociedades, labor market",
    },
    "recaudacion": {
        "query": "informes anuales recaudacion tributaria AEAT",
        "description": "Informes anuales de Recaudación Tributaria — annual tax revenue totals",
    },
    "irpf": {
        "query": "estadisticas IRPF impuesto renta personas fisicas AEAT",
        "description": "IRPF statistics — income distribution, tax brackets, deductions",
    },
    "iva": {
        "query": "estadisticas IVA impuesto valor añadido AEAT",
        "description": "IVA/VAT statistics — declared sales, purchases, refunds",
    },
    "sociedades": {
        "query": "estadisticas impuesto sociedades AEAT",
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

    Args:
        stat_type: One of the known AEAT dataset types:
                   "anuario_estadistico", "recaudacion", "irpf", "iva", "sociedades"
        custom_query: Override the search query.
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
        base_url = get_api_url("datos_gob_es")
        url = f"{base_url}catalog/api/action/package_search"

        entry = _KNOWN_DATASETS.get(stat_type, {})

        # Try by known dataset ID first (most precise)
        if "id" in entry and not custom_query:
            id_url = f"{base_url}catalog/api/action/package_show"
            try:
                data = await fetch_json(session, id_url, log_prefix="AEAT API", params={"id": entry["id"]})
                result = data.get("result")
                if result:
                    return {"results": [result], "count": 1}
            except Exception:
                pass  # Fall through to search

        query = custom_query or entry.get("query") or f"AEAT {stat_type} estadistica"
        params: dict[str, Any] = {
            "q": query,
            "fq": 'organization:"agencia-tributaria" OR publisher:"Agencia Tributaria"',
            "rows": min(page_size, 100),
            "start": (page - 1) * page_size,
            "sort": "metadata_modified desc",
        }
        data = await fetch_json(session, url, log_prefix="AEAT API", params=params)
        return data.get("result", {})
    finally:
        if own:
            await session.aclose()
