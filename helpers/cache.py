"""
In-memory TTL metadata cache for datos-es-mcp.

Stores rarely-changing API metadata (datos.gob.es themes and publishers,
INE operations) with a configurable time-to-live (default 24 hours).
All public methods are async-safe via per-key asyncio.Lock.

Cache misses trigger a lazy fetch from the upstream API. Subsequent concurrent
requests for the same key wait on the same lock rather than issuing duplicate
upstream calls.

Usage:
    from helpers.cache import metadata_cache

    themes     = await metadata_cache.get_themes()
    publishers = await metadata_cache.get_publishers()
    ine_ops    = await metadata_cache.get_ine_operations()
"""

import asyncio
import logging
import time
from typing import Any

import httpx

from helpers.env_config import get_api_url
from helpers.logging import MAIN_LOGGER_NAME
from helpers.user_agent import USER_AGENT

logger = logging.getLogger(MAIN_LOGGER_NAME)

_DEFAULT_TTL: float = 86_400.0  # 24 hours in seconds


class _CacheEntry:
    __slots__ = ("value", "expires_at")

    def __init__(self, value: Any, ttl: float) -> None:
        self.value = value
        self.expires_at = time.monotonic() + ttl


class MetadataCache:
    """
    Lazy-loaded, TTL-expiring in-memory cache for rarely-changing metadata.

    Thread-safety note: designed for asyncio single-threaded use. All public
    methods acquire a per-key asyncio.Lock to avoid duplicate upstream calls
    when multiple coroutines miss the cache simultaneously.
    """

    def __init__(self, ttl: float = _DEFAULT_TTL) -> None:
        self._ttl = ttl
        self._store: dict[str, _CacheEntry] = {}
        self._locks: dict[str, asyncio.Lock] = {}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _lock_for(self, key: str) -> asyncio.Lock:
        if key not in self._locks:
            self._locks[key] = asyncio.Lock()
        return self._locks[key]

    def _get(self, key: str) -> Any | None:
        entry = self._store.get(key)
        if entry is not None and time.monotonic() < entry.expires_at:
            return entry.value
        return None

    def _set(self, key: str, value: Any) -> None:
        self._store[key] = _CacheEntry(value, self._ttl)

    def invalidate(self, key: str | None = None) -> None:
        """Remove one key (or clear the entire cache if key is None)."""
        if key is None:
            self._store.clear()
        else:
            self._store.pop(key, None)

    # ------------------------------------------------------------------
    # datos.gob.es themes (NTI topic categories)
    # ------------------------------------------------------------------

    async def get_themes(self) -> list[dict[str, str]]:
        """
        Return NTI topic categories available on datos.gob.es.

        Each entry has 'id' (CKAN facet value, e.g. 'sector-publico') and
        'label' (display name). Cached for 24 hours.

        Returns an empty list on fetch failure so callers degrade gracefully.
        """
        key = "datos_gob_themes"
        cached = self._get(key)
        if cached is not None:
            return cached

        async with self._lock_for(key):
            # Re-check after lock acquisition (another coroutine may have populated)
            cached = self._get(key)
            if cached is not None:
                return cached

            try:
                themes = await _fetch_datos_gob_themes()
                self._set(key, themes)
                logger.info("Cache populated: %d datos.gob.es themes", len(themes))
                return themes
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not load datos.gob.es themes: %s", exc)
                return []

    # ------------------------------------------------------------------
    # datos.gob.es publishers (organizations)
    # ------------------------------------------------------------------

    async def get_publishers(self) -> list[dict[str, str]]:
        """
        Return publisher organizations available on datos.gob.es.

        Each entry has 'name' (CKAN slug), 'display_name', 'package_count'.
        Cached for 24 hours.

        Returns an empty list on fetch failure so callers degrade gracefully.
        """
        key = "datos_gob_publishers"
        cached = self._get(key)
        if cached is not None:
            return cached

        async with self._lock_for(key):
            cached = self._get(key)
            if cached is not None:
                return cached

            try:
                publishers = await _fetch_datos_gob_publishers()
                self._set(key, publishers)
                logger.info("Cache populated: %d datos.gob.es publishers", len(publishers))
                return publishers
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not load datos.gob.es publishers: %s", exc)
                return []

    # ------------------------------------------------------------------
    # INE statistical operations
    # ------------------------------------------------------------------

    async def get_ine_operations(self) -> list[dict[str, Any]]:
        """
        Return all available INE statistical operations.

        Each entry has Id, Nombre, Codigo, Periodicidad.
        Cached for 24 hours.

        Returns an empty list on fetch failure so callers degrade gracefully.
        """
        key = "ine_operations"
        cached = self._get(key)
        if cached is not None:
            return cached

        async with self._lock_for(key):
            cached = self._get(key)
            if cached is not None:
                return cached

            try:
                ops = await _fetch_ine_operations()
                self._set(key, ops)
                logger.info("Cache populated: %d INE operations", len(ops))
                return ops
            except Exception as exc:  # noqa: BLE001
                logger.warning("Could not load INE operations: %s", exc)
                return []


# ------------------------------------------------------------------
# Internal fetch helpers
# ------------------------------------------------------------------


async def _fetch_datos_gob_themes() -> list[dict[str, str]]:
    base_url = get_api_url("datos_gob_es")
    url = f"{base_url}catalog/api/action/package_search"
    params: dict[str, Any] = {
        "q": "*:*",
        "rows": 0,
        "facet": "on",
        "facet.field": "theme_id",
        "facet.limit": 100,
    }
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}) as client:
        resp = await client.get(url, params=params, timeout=15.0)
        resp.raise_for_status()
        data = resp.json()

    facets = data.get("result", {}).get("search_facets", {})
    items = facets.get("theme_id", {}).get("items", [])
    return [
        {"id": it["name"], "label": it.get("display_name") or it["name"]}
        for it in items
        if it.get("name")
    ]


async def _fetch_datos_gob_publishers() -> list[dict[str, str]]:
    base_url = get_api_url("datos_gob_es")
    url = f"{base_url}catalog/api/action/organization_list"
    params: dict[str, Any] = {
        "all_fields": True,
        "include_dataset_count": True,
        "limit": 500,
    }
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}) as client:
        resp = await client.get(url, params=params, timeout=20.0)
        resp.raise_for_status()
        data = resp.json()

    orgs = data.get("result", [])
    return [
        {
            "name": o.get("name", ""),
            "display_name": o.get("display_name") or o.get("title") or o.get("name", ""),
            "package_count": str(o.get("package_count", 0)),
        }
        for o in orgs
        if isinstance(o, dict) and o.get("name")
    ]


async def _fetch_ine_operations() -> list[dict[str, Any]]:
    base_url = get_api_url("ine")
    url = f"{base_url}ES/OPERACIONES_DISPONIBLES"
    params: dict[str, Any] = {"det": 0}
    async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}) as client:
        resp = await client.get(url, params=params, timeout=20.0)
        resp.raise_for_status()
        data = resp.json()
    return data if isinstance(data, list) else []


# ------------------------------------------------------------------
# Module-level singleton — import and use directly
# ------------------------------------------------------------------

metadata_cache = MetadataCache()
