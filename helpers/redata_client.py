"""
Client for the REData API (Red Eléctrica de España / Redeia).

REData is the public open data API of Spain's electricity system operator.
No authentication required. Returns JSON:API format.

Base URL: https://apidatos.ree.es/{lang}/datos/{category}/{widget}
Docs: https://www.ree.es/en/datos/apidata

Categories and key widgets:
  generacion:
    estructura-generacion     — generation mix by technology (renewable %)
    potencia-instalada        — installed capacity by technology (GW)
    maxima-renovable          — maximum renewable coverage of demand
    evolucion-renovable       — renewable energy evolution over time
  demanda:
    demanda-tiempo-real       — real-time demand
    demanda-maxima-diaria     — daily maximum demand
    variacion-demanda         — demand variation
  mercados:
    precios-spot-mercado      — spot market prices
    precios-restricciones     — restriction prices
    coste-servicios-ajuste    — adjustment services cost
  balance:
    balance-electrico         — electrical balance (generation, imports, exports)
  intercambios:
    todas-fronteras-5min      — all border exchanges
"""

import logging
from datetime import date
from typing import Any

import httpx

from helpers.http import fetch_json
from helpers.logging import MAIN_LOGGER_NAME
from helpers.user_agent import USER_AGENT

logger = logging.getLogger(MAIN_LOGGER_NAME)

_BASE_URL = "https://apidatos.ree.es"


async def _fetch(
    client: httpx.AsyncClient,
    category: str,
    widget: str,
    start_date: str,
    end_date: str,
    time_trunc: str = "month",
    lang: str = "en",
    geo_limit: str | None = None,
) -> dict[str, Any]:
    url = f"{_BASE_URL}/{lang}/datos/{category}/{widget}"
    params: dict[str, Any] = {
        "start_date": start_date,
        "end_date": end_date,
        "time_trunc": time_trunc,
    }
    if geo_limit:
        params["geo_limit"] = geo_limit

    return await fetch_json(
        client,
        url,
        log_prefix="REData",
        params=params,
        headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
    )


async def get_generation_mix(
    start_date: str,
    end_date: str,
    time_trunc: str = "month",
    session: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """
    Get Spain's electricity generation mix by technology.

    Args:
        start_date: ISO datetime string "YYYY-MM-DDTHH:MM".
        end_date: ISO datetime string "YYYY-MM-DDTHH:MM".
        time_trunc: Aggregation level: "hour", "day", "month", "year".

    Returns:
        JSON:API response with generation by technology (renewable + non-renewable).
    """
    own = session is None
    if own:
        session = httpx.AsyncClient()
    assert session is not None
    try:
        return await _fetch(
            session,
            "generacion",
            "estructura-generacion",
            start_date,
            end_date,
            time_trunc,
        )
    finally:
        if own:
            await session.aclose()


async def get_installed_capacity(
    start_date: str,
    end_date: str,
    time_trunc: str = "year",
    session: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """
    Get Spain's installed electricity generation capacity by technology (GW).

    Args:
        start_date: ISO datetime string.
        end_date: ISO datetime string.
        time_trunc: Aggregation level (typically "year").
    """
    own = session is None
    if own:
        session = httpx.AsyncClient()
    assert session is not None
    try:
        return await _fetch(
            session,
            "generacion",
            "potencia-instalada",
            start_date,
            end_date,
            time_trunc,
        )
    finally:
        if own:
            await session.aclose()


async def get_electricity_balance(
    start_date: str,
    end_date: str,
    time_trunc: str = "month",
    session: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """
    Get Spain's electrical balance: generation, imports, exports, demand.

    Args:
        start_date: ISO datetime string.
        end_date: ISO datetime string.
        time_trunc: Aggregation level.
    """
    own = session is None
    if own:
        session = httpx.AsyncClient()
    assert session is not None
    try:
        return await _fetch(
            session,
            "balance",
            "balance-electrico",
            start_date,
            end_date,
            time_trunc,
        )
    finally:
        if own:
            await session.aclose()


async def get_market_prices(
    start_date: str,
    end_date: str,
    time_trunc: str = "month",
    session: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """
    Get Spanish electricity market prices (adjustment services cost).

    Args:
        start_date: ISO datetime string.
        end_date: ISO datetime string.
        time_trunc: Aggregation level.
    """
    own = session is None
    if own:
        session = httpx.AsyncClient()
    assert session is not None
    try:
        return await _fetch(
            session,
            "mercados",
            "coste-servicios-ajuste",
            start_date,
            end_date,
            time_trunc,
        )
    finally:
        if own:
            await session.aclose()


async def get_demand(
    start_date: str,
    end_date: str,
    time_trunc: str = "month",
    session: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """
    Get Spain's electricity demand evolution.

    Args:
        start_date: ISO datetime string.
        end_date: ISO datetime string.
        time_trunc: Aggregation level.
    """
    own = session is None
    if own:
        session = httpx.AsyncClient()
    assert session is not None
    try:
        return await _fetch(
            session,
            "demanda",
            "variacion-demanda",
            start_date,
            end_date,
            time_trunc,
        )
    finally:
        if own:
            await session.aclose()


def _default_date_range(years_back: int = 2) -> tuple[str, str]:
    """Return a default (start_date, end_date) ISO string pair."""
    today = date.today()
    start = date(today.year - years_back, 1, 1)
    return f"{start}T00:00", f"{today}T23:59"
