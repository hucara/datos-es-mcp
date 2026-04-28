"""
Client for regional government procurement portals in Spain.

Each of the three major autonomous communities maintains its own open data portal
alongside the national PLACE platform. These regional portals publish procurement
data (licitaciones, adjudicaciones, contratos menores) with greater granularity
and shorter lag times than the national aggregate.

Sources:
  Madrid    — datos.comunidad.madrid (CKAN)
              https://datos.comunidad.madrid/catalogo/api/action/
  Cataluña  — analisi.transparenciacatalunya.cat (Socrata/CKAN-compatible)
              https://analisi.transparenciacatalunya.cat/api/action/
  Valencia  — dadesobertes.gva.es (CKAN)
              https://dadesobertes.gva.es/api/action/

All three also publish datasets on the national datos.gob.es portal, which we query
as a secondary source to surface bulk CSV/XML files for historical analysis.

Key procurement dataset IDs (pre-validated):
  Madrid    — "contratos-menores", "licitaciones-adjudicadas" (searched by tag)
  Cataluña  — Contractació pública datasets on the analytics portal
  Valencia  — "contratacion" tag group on dadesobertes.gva.es
"""

import logging
from typing import Any

import httpx

from helpers.http import fetch_json
from helpers.logging import MAIN_LOGGER_NAME
from helpers.user_agent import USER_AGENT

logger = logging.getLogger(MAIN_LOGGER_NAME)

# Regional CKAN API base URLs
_REGIONAL_PORTALS: dict[str, dict] = {
    "madrid": {
        "name": "Comunidad de Madrid",
        "ckan_url": "https://datos.comunidad.madrid/catalogo/api/action/",
        "datos_gob_publisher": "comunidad-de-madrid",
        "procurement_tags": "contratacion-publica contratacion licitaciones",
        "portal_url": "https://datos.comunidad.madrid",
        "contracts_portal_url": "https://www.contratacionpublicamadrid.es",
    },
    "cataluña": {
        "name": "Generalitat de Catalunya",
        "ckan_url": "https://analisi.transparenciacatalunya.cat/api/action/",
        "datos_gob_publisher": "generalitat-de-catalunya",
        "procurement_tags": "contractació contractes licitació",
        "portal_url": "https://analisi.transparenciacatalunya.cat",
        "contracts_portal_url": "https://contractaciopublica.gencat.cat",
    },
    "valencia": {
        "name": "Generalitat Valenciana",
        "ckan_url": "https://dadesobertes.gva.es/api/action/",
        "datos_gob_publisher": "generalitat-valenciana",
        "procurement_tags": "contratació contractes licitació",
        "portal_url": "https://dadesobertes.gva.es",
        "contracts_portal_url": "https://contratacion.gva.es",
    },
}


async def search_regional_ckan(
    region: str,
    query: str,
    page: int = 1,
    page_size: int = 10,
    session: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """
    Search a regional CKAN portal directly for procurement datasets.

    Args:
        region: One of "madrid", "cataluña", "valencia".
        query: Search terms (e.g. "obras", "servicios informaticos", "contratos menores").
        page: Page number (1-based).
        page_size: Results per page.

    Returns:
        CKAN search result dict with {"results": [...], "count": N}.
    """
    if region not in _REGIONAL_PORTALS:
        raise ValueError(f"Unknown region '{region}'. Valid: {list(_REGIONAL_PORTALS)}")

    portal = _REGIONAL_PORTALS[region]
    ckan_url = portal["ckan_url"]
    tags = portal["procurement_tags"]

    own = session is None
    if own:
        session = httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
    assert session is not None

    try:
        url = f"{ckan_url}package_search"
        # Build procurement-focused query
        full_query = f"{query} {tags}" if query else tags
        params: dict[str, Any] = {
            "q": full_query,
            "rows": min(page_size, 100),
            "start": (page - 1) * page_size,
            "sort": "metadata_modified desc",
        }
        data = await fetch_json(
            session, url, log_prefix="Regional contracts", params=params
        )
        result = data.get("result") or {}
        return {
            "results": result.get("results", []),
            "count": result.get("count", 0),
            "source": "regional_ckan",
            "portal": portal,
        }
    finally:
        if own:
            await session.aclose()


async def search_datos_gob_by_region(
    region: str,
    query: str,
    page: int = 1,
    page_size: int = 10,
    session: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """
    Search datos.gob.es for procurement datasets from a specific regional publisher.

    Uses the datos.gob.es linked-data semantic API (publisher endpoint), NOT the
    CKAN-style API which does not exist on this portal.

    Args:
        region: One of "madrid", "cataluña", "valencia".
        query: Search terms (used as additional title keyword filter).
        page: Page number (1-based).
        page_size: Results per page.

    Returns:
        Dict with {"results": [...], "count": N, "source": "datos_gob_es", "portal": {...}}.
    """
    if region not in _REGIONAL_PORTALS:
        raise ValueError(f"Unknown region '{region}'. Valid: {list(_REGIONAL_PORTALS)}")

    portal = _REGIONAL_PORTALS[region]
    publisher = portal["datos_gob_publisher"]

    own = session is None
    if own:
        session = httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
    assert session is not None

    try:
        # datos.gob.es semantic API: list all datasets from a publisher
        # Endpoint: GET /apidata/catalog/dataset/publisher/{code}.json
        url = f"https://datos.gob.es/apidata/catalog/dataset/publisher/{publisher}.json"
        params: dict[str, Any] = {
            "_pageSize": min(page_size, 50),
            "_page": page - 1,
        }
        data = await fetch_json(
            session, url, log_prefix="Regional contracts", params=params
        )
        items = (data.get("result") or {}).get("items") or []
        total = (data.get("result") or {}).get("totalItems") or len(items)

        # Filter by query keywords against title if provided
        if query:
            kw = query.lower().split()

            def _matches(item: dict) -> bool:
                titles = item.get("title") or []
                title_text = " ".join(
                    (t.get("_value") or "") for t in titles if isinstance(t, dict)
                ).lower()
                return any(k in title_text for k in kw)

            items = [i for i in items if _matches(i)]

        # Normalise items to a CKAN-like shape for the tool formatter
        results = []
        for item in items:
            titles = item.get("title") or []
            title = next(
                (
                    t.get("_value")
                    for t in titles
                    if isinstance(t, dict) and t.get("_lang") == "es"
                ),
                next((t.get("_value") for t in titles if isinstance(t, dict)), ""),
            )
            about = item.get("_about") or ""
            dist = item.get("distribution") or []
            resources = [
                {
                    "format": (d.get("format") or {}).get("value", "?").upper(),
                    "url": d.get("accessURL") or "",
                    "name": "Download",
                }
                for d in dist
                if isinstance(d, dict)
            ]
            results.append(
                {
                    "title": title,
                    "name": about.split("/")[-1] if about else "",
                    "notes": (item.get("description") or [""])[0]
                    if isinstance(item.get("description"), list)
                    else item.get("description") or "",
                    "metadata_modified": item.get("modified") or "",
                    "resources": resources,
                }
            )

        return {
            "results": results,
            "count": total,
            "source": "datos_gob_es",
            "portal": portal,
        }
    finally:
        if own:
            await session.aclose()


def get_portal_info(region: str) -> dict:
    """Return metadata dict for the given region."""
    return _REGIONAL_PORTALS.get(region, {})


def list_regions() -> list[str]:
    """Return list of supported region keys."""
    return list(_REGIONAL_PORTALS)
