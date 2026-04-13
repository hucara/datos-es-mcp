"""
Client for the AEMET OpenData API (Agencia Estatal de Meteorología).

Provides weather forecasts, observations, alerts, and historical climate data
for Spain. Requires a free API key from https://opendata.aemet.es/

The AEMET API uses a two-step pattern:
  1. First request returns a JSON with a "datos" URL.
  2. Second request to that URL retrieves the actual data.

API docs (Swagger): https://opendata.aemet.es/dist/index.html
Base URL: https://opendata.aemet.es/opendata/api/
"""

import logging
import os
from typing import Any

import httpx

from helpers.env_config import get_api_url
from helpers.http import fetch_json
from helpers.logging import MAIN_LOGGER_NAME
from helpers.user_agent import USER_AGENT

logger = logging.getLogger(MAIN_LOGGER_NAME)


def _get_api_key() -> str | None:
    return os.getenv("AEMET_API_KEY")


async def _fetch_aemet(
    client: httpx.AsyncClient,
    endpoint: str,
) -> list[dict[str, Any]] | dict[str, Any]:
    """
    Execute a two-step AEMET API call.

    Step 1: GET endpoint → returns {"datos": "<url>", "metadatos": "<url>", "estado": 200}
    Step 2: GET datos URL → returns actual data
    """
    api_key = _get_api_key()
    if not api_key:
        raise ValueError(
            "AEMET_API_KEY environment variable is not set. "
            "Get a free key at https://opendata.aemet.es/"
        )

    base_url = get_api_url("aemet")
    url = f"{base_url}{endpoint}"
    headers = {"api_key": api_key, "User-Agent": USER_AGENT}

    meta = await fetch_json(client, url, log_prefix="AEMET step-1", timeout=15.0, headers=headers)

    estado = meta.get("estado")
    if estado == 404:
        raise ValueError(f"AEMET: {meta.get('descripcion', 'Not found')}")
    if estado not in (200, None):
        raise ValueError(f"AEMET API error {estado}: {meta.get('descripcion', 'Unknown')}")

    datos_url = meta.get("datos")
    if not datos_url:
        return meta

    return await fetch_json(client, datos_url, log_prefix="AEMET step-2", timeout=20.0, headers=headers)


async def get_municipio_forecast_daily(
    municipio_code: str,
    session: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """
    Get the daily forecast for a Spanish municipality.

    Args:
        municipio_code: INE 5-digit municipality code (e.g. "28079" for Madrid).
                        Leading zeros must be included.

    Returns:
        List of forecast dicts (usually one per municipality).
    """
    own = session is None
    if own:
        session = httpx.AsyncClient()
    assert session is not None
    try:
        endpoint = f"prediccion/especifica/municipio/diaria/{municipio_code}"
        result = await _fetch_aemet(session, endpoint)
        if isinstance(result, list):
            return result
        return [result] if result else []
    finally:
        if own:
            await session.aclose()


async def get_municipio_forecast_hourly(
    municipio_code: str,
    session: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """
    Get the hourly forecast for a Spanish municipality.

    Args:
        municipio_code: INE 5-digit municipality code.

    Returns:
        List of hourly forecast dicts.
    """
    own = session is None
    if own:
        session = httpx.AsyncClient()
    assert session is not None
    try:
        endpoint = f"prediccion/especifica/municipio/horaria/{municipio_code}"
        result = await _fetch_aemet(session, endpoint)
        if isinstance(result, list):
            return result
        return [result] if result else []
    finally:
        if own:
            await session.aclose()


async def get_all_stations_observations(
    session: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """
    Get current observations from all conventional weather stations in Spain.

    Returns:
        List of station observation dicts with temperature, humidity, wind, etc.
    """
    own = session is None
    if own:
        session = httpx.AsyncClient()
    assert session is not None
    try:
        result = await _fetch_aemet(session, "observacion/convencional/todas")
        if isinstance(result, list):
            return result
        return []
    finally:
        if own:
            await session.aclose()


async def get_station_observations(
    station_id: str,
    session: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """
    Get current observations from a specific weather station.

    Args:
        station_id: AEMET station identifier (e.g. "3195" for Madrid Retiro).

    Returns:
        List of observation dicts.
    """
    own = session is None
    if own:
        session = httpx.AsyncClient()
    assert session is not None
    try:
        endpoint = f"observacion/convencional/datos/estacion/{station_id}"
        result = await _fetch_aemet(session, endpoint)
        if isinstance(result, list):
            return result
        return []
    finally:
        if own:
            await session.aclose()


async def get_national_alerts(
    session: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """
    Get current adverse weather alerts for Spain.

    Returns:
        List of active weather warning/alert dicts.
    """
    own = session is None
    if own:
        session = httpx.AsyncClient()
    assert session is not None
    try:
        result = await _fetch_aemet(session, "avisos_cap/ultimoelaborado/area/ESP")
        if isinstance(result, list):
            return result
        return []
    finally:
        if own:
            await session.aclose()
