"""
Tests for the Banco de España (BdE) statistics client.
"""

import re

import pytest
from pytest_httpx import HTTPXMock

from helpers.bde_client import get_latest_data, get_series_history


@pytest.fixture
def sample_latest():
    return [
        {
            "serie": "TI_1_2_1",
            "descripcionCorta": "ECB deposit facility rate",
            "codFrecuencia": "M",
            "decimales": 2,
            "simbolo": "%",
            "tendencia": "=",
            "fechaValor": "2024-12-01",
            "valor": 3.0,
        }
    ]


@pytest.fixture
def sample_history():
    return [
        {
            "serie": "TI_1_2_1",
            "descripcion": "ECB deposit facility rate",
            "descripcionCorta": "ECB deposit facility rate",
            "codFrecuencia": "M",
            "simbolo": "%",
            "decimales": 2,
            "fechaInicio": "1999-01-01",
            "fechaFin": "2024-12-01",
            "fechas": ["2024-10-01", "2024-11-01", "2024-12-01"],
            "valores": [3.25, 3.25, 3.0],
        }
    ]


@pytest.mark.asyncio
async def test_get_latest_data(httpx_mock: HTTPXMock, sample_latest):
    httpx_mock.add_response(
        url=re.compile(r"https://app\.bde\.es/bierest/resources/srdatosapp/favoritas"),
        json=sample_latest,
    )

    result = await get_latest_data(series_codes=["TI_1_2_1"])

    assert len(result) == 1
    assert result[0]["serie"] == "TI_1_2_1"
    assert result[0]["valor"] == 3.0


@pytest.mark.asyncio
async def test_get_series_history(httpx_mock: HTTPXMock, sample_history):
    httpx_mock.add_response(
        url=re.compile(
            r"https://app\.bde\.es/bierest/resources/srdatosapp/listaSeries"
        ),
        json=sample_history,
    )

    result = await get_series_history(series_codes=["TI_1_2_1"], time_range="30M")

    assert len(result) == 1
    assert result[0]["serie"] == "TI_1_2_1"
    assert len(result[0]["fechas"]) == 3
    assert result[0]["valores"][-1] == 3.0
