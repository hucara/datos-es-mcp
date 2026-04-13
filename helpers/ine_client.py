"""
Client for the INE (Instituto Nacional de Estadística) JSON API.

The INE API provides access to all statistical data published by Spain's
National Statistics Institute: demographics, CPI/IPC, labor market (EPA),
GDP, municipal census (Padrón), and more.

API docs: https://www.ine.es/dyngs/DAB/index.htm?cid=1099
Base URL: https://servicios.ine.es/wstempus/js/{lang}/{function}/{input}
"""

import logging
from typing import Any

import httpx

from helpers.env_config import get_api_url
from helpers.http import fetch_json
from helpers.logging import MAIN_LOGGER_NAME
from helpers.user_agent import USER_AGENT

logger = logging.getLogger(MAIN_LOGGER_NAME)

_LANG = "ES"  # ES or EN


def _base(lang: str = _LANG) -> str:
    return f"{get_api_url('ine')}{lang}/"


async def list_operations(
    page: int = 1,
    session: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """
    List all available statistical operations from INEbase.

    Returns:
        List of operations with Id, Nombre (name), Codigo (code), Periodicidad.
    """
    own = session is None
    if own:
        session = httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
    assert session is not None
    try:
        url = f"{_base()}OPERACIONES_DISPONIBLES"
        params = {"det": 0, "page": page}
        data = await fetch_json(session, url, log_prefix="INE API", params=params)
        if isinstance(data, list):
            return data
        return []
    finally:
        if own:
            await session.aclose()


async def get_tables_for_operation(
    operation_code: str,
    session: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """
    List available tables for a given INE statistical operation.

    Args:
        operation_code: INE operation code (e.g. "IPC", "EPA", "CN").

    Returns:
        List of table dicts with Id, Nombre, FK_Operacion, Ultima_Modificacion.
    """
    own = session is None
    if own:
        session = httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
    assert session is not None
    try:
        url = f"{_base()}TABLAS_OPERACION/{operation_code}"
        params = {"det": 0, "tip": "A"}
        data = await fetch_json(session, url, log_prefix="INE API", params=params)
        if isinstance(data, list):
            return data
        return []
    finally:
        if own:
            await session.aclose()


async def get_table_data(
    table_id: str | int,
    last_n: int = 10,
    date_range: str | None = None,
    session: httpx.AsyncClient | None = None,
) -> list[dict[str, Any]]:
    """
    Fetch data for a specific INE table.

    Args:
        table_id: INE table identifier (numeric ID).
        last_n: Return only the last N periods (ignored if date_range is set).
        date_range: Date range in format "YYYYMMDD:YYYYMMDD".

    Returns:
        List of series dicts, each with Nombre, Data (list of {Fecha, Valor}).
    """
    own = session is None
    if own:
        session = httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
    assert session is not None
    try:
        url = f"{_base()}DATOS_TABLA/{table_id}"
        params: dict[str, Any] = {"tip": "AM"}
        if date_range:
            params["date"] = date_range
        else:
            params["nult"] = last_n
        data = await fetch_json(session, url, log_prefix="INE API", params=params)
        if isinstance(data, list):
            return data
        return []
    finally:
        if own:
            await session.aclose()


async def get_series_data(
    series_code: str,
    last_n: int = 10,
    date_range: str | None = None,
    session: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """
    Fetch data for a specific INE statistical series by its code.

    Args:
        series_code: INE series code (e.g. "IPC251856" for CPI national index).
        last_n: Return only the last N periods (ignored if date_range is set).
        date_range: Date range in format "YYYYMMDD:YYYYMMDD".

    Returns:
        Series dict with Nombre, COD, Unidad, Periodicidad, Data list.
    """
    own = session is None
    if own:
        session = httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
    assert session is not None
    try:
        url = f"{_base()}DATOS_SERIE/{series_code}"
        params: dict[str, Any] = {"tip": "AM"}
        if date_range:
            params["date"] = date_range
        else:
            params["nult"] = last_n
        data = await fetch_json(session, url, log_prefix="INE API", params=params)
        if isinstance(data, dict):
            return data
        return {}
    finally:
        if own:
            await session.aclose()
