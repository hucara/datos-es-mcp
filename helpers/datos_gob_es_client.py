"""
Client for the datos.gob.es open data catalog — linked-data semantic API.

datos.gob.es is Spain's national open data portal with 90,000+ datasets
from all public administrations (national, regional, and local).

API docs: https://datos.gob.es/en/apidata
Base URL: https://datos.gob.es/apidata/

Available endpoints:
  catalog/dataset/title/{keyword}.json   — datasets whose title contains keyword
  catalog/dataset/keyword/{tag}.json     — datasets tagged with keyword
  catalog/dataset/publisher/{code}.json  — all datasets from a publisher
  (query params: _pageSize, _page)

Response format: result.items[]  with fields:
  _about, title[{_value,_lang}], description[{_value,_lang}],
  publisher (URI), distribution[{accessURL, format.value, title}],
  issued, modified, keyword[{_value}]

Note: datos.gob.es does NOT support CKAN's /catalog/api/action/ endpoints.
"""

import logging
import unicodedata
from typing import Any
from urllib.parse import quote

import httpx

from helpers.http import fetch_json
from helpers.logging import MAIN_LOGGER_NAME
from helpers.user_agent import USER_AGENT

logger = logging.getLogger(MAIN_LOGGER_NAME)

_BASE_URL = "https://datos.gob.es/apidata"

# MIME type → friendly format name
# Generic Spanish words that produce poor title-search results when used as the keyword.
# The title/{keyword} endpoint searches for datasets whose title *contains* the keyword,
# so overly common words return unrelated results.
_GENERIC_WORDS = {
    "de",
    "del",
    "la",
    "las",
    "el",
    "los",
    "y",
    "o",
    "en",
    "a",
    "por",
    "para",
    "con",
    "sin",
    "sobre",
    "entre",
    "hacia",
    "desde",
    "hasta",
    "estadistica",
    "estadisticas",
    "datos",
    "dato",
    "informe",
    "informes",
    "indice",
    "indices",
    "precio",
    "precios",
    "tasa",
    "tasas",
    "nivel",
    "niveles",
    "nacional",
    "espana",
    "espanol",
    "española",
    "publico",
    "publica",
    "general",
    "total",
    "media",
    "medios",
    "numero",
    "numeros",
    "porcentaje",
    "porcentajes",
}

_MIME_TO_FORMAT: dict[str, str] = {
    "text/csv": "CSV",
    "application/csv": "CSV",
    "application/vnd.ms-excel": "XLS",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "XLSX",
    "application/json": "JSON",
    "application/xml": "XML",
    "text/xml": "XML",
    "application/xhtml+xml": "HTML",
    "text/html": "HTML",
    "application/pdf": "PDF",
    "application/zip": "ZIP",
    "application/x-zip-compressed": "ZIP",
    "application/rdf+xml": "RDF",
    "text/plain": "TXT",
}


def _strip_accents(s: str) -> str:
    """Remove diacritics so accented words match unaccented stop-word lists."""
    return "".join(
        c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c)
    )


def _mime_to_format(mime: str) -> str:
    """Convert a MIME type string to a short format label."""
    if not mime:
        return ""
    clean = mime.split(";")[0].strip().lower()
    return _MIME_TO_FORMAT.get(clean, clean.split("/")[-1].upper()[:10])


def _extract_text(field: Any, lang_pref: str = "es") -> str:
    """Extract text value from a [{_value, _lang}] list or plain string."""
    if isinstance(field, str):
        return field
    if isinstance(field, list):
        # Prefer Spanish
        for item in field:
            if isinstance(item, dict) and item.get("_lang") == lang_pref:
                return item.get("_value", "")
        # Fall back to first item
        if field and isinstance(field[0], dict):
            return field[0].get("_value", "")
    return ""


def _normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    """Normalize a datos.gob.es semantic API item into a standard dict."""
    about = item.get("_about", "")
    slug = about.rstrip("/").split("/")[-1] if about else ""

    title = _extract_text(item.get("title", ""))
    description = _extract_text(item.get("description", ""))[:300]

    publisher_uri = str(item.get("publisher") or "")
    publisher_code = (
        publisher_uri.split("/")[-1] if "/" in publisher_uri else publisher_uri
    )

    distributions = item.get("distribution") or []
    if not isinstance(distributions, list):
        distributions = [distributions]

    resources = []
    formats: set[str] = set()
    for dist in distributions[:5]:
        if not isinstance(dist, dict):
            continue
        access_url = dist.get("accessURL", "")
        fmt_obj = dist.get("format") or {}
        fmt_mime = fmt_obj.get("value", "") if isinstance(fmt_obj, dict) else ""
        fmt = _mime_to_format(fmt_mime)
        dist_title = _extract_text(dist.get("title", "")) or "File"
        if access_url:
            resources.append({"name": dist_title, "format": fmt, "url": access_url})
            if fmt:
                formats.add(fmt)

    modified = item.get("modified") or item.get("issued") or ""

    return {
        "id": slug,
        "name": slug,
        "title": title,
        "description": description,
        "organization": publisher_code,
        "publisher": publisher_code,
        "formats": sorted(formats),
        "resources_count": len(resources),
        "last_modified": modified,
        "resources": resources,
        "url": about,
        # CKAN-compatible aliases used by some tool formatters
        "notes": description,
        "metadata_modified": modified,
    }


async def search_datasets(
    query: str,
    theme: str | None = None,
    publisher: str | None = None,
    format: str | None = None,
    keyword: str | None = None,
    page: int = 1,
    page_size: int = 20,
    session: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """
    Search for datasets in the datos.gob.es catalog using the semantic API.

    Uses the title/{keyword} endpoint for keyword searches, or
    publisher/{code} endpoint when a publisher code is provided.

    Args:
        query: Search keyword (used as title keyword search).
        theme: Ignored — not supported by the semantic API.
        publisher: Publisher code (e.g. "EA0028512" for AEAT).
                   If provided, searches by publisher instead of keyword.
        format: Ignored — filtering by format not supported at query time.
        page: Page number (1-based → converted to 0-based for the API).
        page_size: Results per page.

    Returns:
        dict with 'results' (list of datasets), 'count', 'page', 'page_size'.
    """
    own = session is None
    if own:
        session = httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
    assert session is not None
    try:
        page_zero = max(0, page - 1)
        params: dict[str, Any] = {"_pageSize": min(page_size, 100), "_page": page_zero}

        if publisher:
            url = f"{_BASE_URL}/catalog/dataset/publisher/{quote(publisher, safe='')}.json"
        else:
            if not keyword:
                # Pick the first non-generic word from the query for the title keyword search
                words = query.split() if query else []
                keyword = next(
                    (
                        w
                        for w in words
                        if _strip_accents(w.lower()).rstrip("s") not in _GENERIC_WORDS
                        and len(w) > 3
                    ),
                    words[0] if words else query,
                )
            url = f"{_BASE_URL}/catalog/dataset/title/{quote(keyword, safe='')}.json"

        data = await fetch_json(session, url, log_prefix="datos.gob.es", params=params)
        result = data.get("result", {})
        items = result.get("items", [])
        total = result.get("totalResults") or len(items)

        normalized = [_normalize_item(item) for item in items]

        return {
            "results": normalized,
            "count": total,
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
    Get metadata for a specific dataset by its slug or publisher code.

    For a publisher code (e.g. "EA0028512"), returns the first dataset
    from that publisher. For a slug, returns the matching dataset if found
    via title search.

    Args:
        dataset_id: Dataset slug or publisher code.

    Returns:
        Normalized dataset dict, or empty dict if not found.
    """
    own = session is None
    if own:
        session = httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
    assert session is not None
    try:
        params: dict[str, Any] = {"_pageSize": 1, "_page": 0}

        # Try as direct dataset slug (e.g. "e00003901-anuario-trafico-2023")
        # Use a plain GET without retry since this endpoint may not exist.
        try:
            url = f"{_BASE_URL}/catalog/dataset/{quote(dataset_id, safe='')}.json"
            resp = await session.get(
                url, timeout=10.0, follow_redirects=True, params=params
            )
            if resp.status_code == 200:
                data = resp.json()
                items = data.get("result", {}).get("items", [])
                if items:
                    return _normalize_item(items[0])
                result_obj = data.get("result")
                if isinstance(result_obj, dict) and result_obj.get("_about"):
                    return _normalize_item(result_obj)
        except Exception:
            pass

        # Try as publisher code
        try:
            url = f"{_BASE_URL}/catalog/dataset/publisher/{quote(dataset_id, safe='')}.json"
            data = await fetch_json(
                session, url, log_prefix="datos.gob.es", params=params
            )
            items = data.get("result", {}).get("items", [])
            if items:
                return _normalize_item(items[0])
        except Exception:
            pass

        # Try as title search (last resort — may return wrong dataset for slugs)
        url = f"{_BASE_URL}/catalog/dataset/title/{quote(dataset_id, safe='')}.json"
        data = await fetch_json(session, url, log_prefix="datos.gob.es", params=params)
        items = data.get("result", {}).get("items", [])
        return _normalize_item(items[0]) if items else {}
    finally:
        if own:
            await session.aclose()
