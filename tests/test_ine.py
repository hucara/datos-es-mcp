"""
Tests for the INE (Instituto Nacional de Estadística) client.
"""

import pytest
from pytest_httpx import HTTPXMock

from helpers.ine_client import list_operations, get_table_data, get_series_data


@pytest.fixture
def sample_operations():
    return [
        {"Id": 25, "Nombre": "Índice de Precios de Consumo (IPC)", "Codigo": "IPC",
         "Periodicidad": {"Nombre": "Mensual"}},
        {"Id": 33, "Nombre": "Encuesta de Población Activa (EPA)", "Codigo": "EPA",
         "Periodicidad": {"Nombre": "Trimestral"}},
    ]


@pytest.fixture
def sample_table_data():
    return [
        {
            "Nombre": "IPC General Nacional",
            "COD": "IPC251856",
            "Unidad": {"Nombre": "Índice"},
            "Periodicidad": {"Nombre": "Mensual"},
            "Data": [
                {"Fecha": 1704067200000, "Valor": 112.4},
                {"Fecha": 1706745600000, "Valor": 112.9},
                {"Fecha": 1709164800000, "Valor": 113.2},
            ],
        }
    ]


@pytest.mark.asyncio
async def test_list_operations(httpx_mock: HTTPXMock, sample_operations):
    httpx_mock.add_response(
        url="https://servicios.ine.es/wstempus/js/ES/OPERACIONES_DISPONIBLES",
        match_querystring=False,
        json=sample_operations,
    )

    ops = await list_operations()

    assert len(ops) == 2
    assert ops[0]["Codigo"] == "IPC"
    assert ops[1]["Codigo"] == "EPA"


@pytest.mark.asyncio
async def test_get_table_data(httpx_mock: HTTPXMock, sample_table_data):
    httpx_mock.add_response(
        url="https://servicios.ine.es/wstempus/js/ES/DATOS_TABLA/50902",
        match_querystring=False,
        json=sample_table_data,
    )

    data = await get_table_data(table_id="50902", last_n=3)

    assert len(data) == 1
    assert data[0]["Nombre"] == "IPC General Nacional"
    assert len(data[0]["Data"]) == 3


@pytest.mark.asyncio
async def test_get_series_data(httpx_mock: HTTPXMock):
    series_response = {
        "Nombre": "IPC General Nacional",
        "COD": "IPC251856",
        "Unidad": {"Nombre": "Índice"},
        "Periodicidad": {"Nombre": "Mensual"},
        "Data": [{"Fecha": 1704067200000, "Valor": 112.4}],
    }
    httpx_mock.add_response(
        url="https://servicios.ine.es/wstempus/js/ES/DATOS_SERIE/IPC251856",
        match_querystring=False,
        json=series_response,
    )

    data = await get_series_data("IPC251856", last_n=1)

    assert data["COD"] == "IPC251856"
    assert len(data["Data"]) == 1
    assert data["Data"][0]["Valor"] == 112.4
