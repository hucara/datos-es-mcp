"""
Client for the Banco de España (BdE) Statistics API.

Provides access to economic and financial time series published by the
Bank of Spain: interest rates, exchange rates, credit, banking data,
money supply, balance of payments, etc.

API docs: https://www.bde.es/webbe/en/estadisticas/recursos/api-estadisticas-bde.html
Base URL: https://app.bde.es/bierest/resources/srdatosapp/
"""

import logging
from typing import Any

import httpx

from helpers.env_config import get_api_url
from helpers.http import fetch_json
from helpers.logging import MAIN_LOGGER_NAME
from helpers.user_agent import USER_AGENT

logger = logging.getLogger(MAIN_LOGGER_NAME)

# Frequency code to human-readable name
_FREQ_NAMES = {
    "D": "Daily",
    "M": "Monthly",
    "Q": "Quarterly",
    "A": "Annual",
}


async def get_latest_data(
    series_codes: list[str],
    lang: str = "en",
    session: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch the most recent published value for one or more BdE series.

    Args:
        series_codes: List of BdE series codes (e.g. ["TI_1_2_1", "TC_1_1_1"]).
        lang: Language for descriptions ("es" or "en").

    Returns:
        List of series dicts with current value, description, frequency, trend.
    """
    own = session is None
    if own:
        session = httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
    assert session is not None
    try:
        base_url = get_api_url("bde")
        url = f"{base_url}favoritas"
        # Series codes with "#" must be URL-encoded as "%23"
        encoded_codes = [c.replace("#", "%23") for c in series_codes]
        params = {
            "idioma": lang,
            "series": ",".join(encoded_codes),
        }
        data = await fetch_json(session, url, log_prefix="BdE API", params=params)
        if isinstance(data, list):
            return data
        return []
    finally:
        if own:
            await session.aclose()


async def get_series_history(
    series_codes: list[str],
    time_range: str = "60M",
    lang: str = "en",
    session: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch historical data for one or more BdE series.

    Args:
        series_codes: List of BdE series codes.
        time_range: Time range for data retrieval:
                    - Monthly: "30M", "60M", "MAX"
                    - Quarterly: "30M", "60M", "MAX"
                    - Annual: "60M", "MAX"
                    - Daily: "3M", "12M", "36M"
                    - Specific year: "2024", "2023", etc.
        lang: Language for descriptions ("es" or "en").

    Returns:
        List of series dicts with dates array, values array, and metadata.
    """
    own = session is None
    if own:
        session = httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
    assert session is not None
    try:
        base_url = get_api_url("bde")
        url = f"{base_url}listaSeries"
        encoded_codes = [c.replace("#", "%23") for c in series_codes]
        params = {
            "idioma": lang,
            "series": ",".join(encoded_codes),
            "rango": time_range,
        }
        data = await fetch_json(session, url, log_prefix="BdE API", params=params)
        if isinstance(data, list):
            return data
        return []
    finally:
        if own:
            await session.aclose()
