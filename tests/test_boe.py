"""
Tests for the BOE (Boletín Oficial del Estado) client.
"""

import re

import pytest
from pytest_httpx import HTTPXMock

from helpers.boe_client import get_boe_summary, search_legislation


@pytest.fixture
def sample_boe_summary():
    return {
        "sumario": {
            "metadatos": {
                "fecha_publicacion": "20241201",
                "numero_oficial": "290",
            },
            "diario": {
                "seccion": [
                    {
                        "nombre": "I. Disposiciones generales",
                        "@nombre": "I. Disposiciones generales",
                        "departamento": [
                            {
                                "nombre": "Ministerio de Hacienda",
                                "item": [
                                    {
                                        "titulo": "Real Decreto 1234/2024 sobre presupuestos",
                                        "identificador": "BOE-A-2024-12345",
                                    }
                                ],
                            }
                        ],
                    }
                ]
            },
        }
    }


@pytest.fixture
def sample_legislation_search():
    return {
        "response": {
            "numFound": 1,
            "docs": [
                {
                    "identificador": "BOE-A-2018-16673",
                    "titulo": "Ley Orgánica 3/2018, de Protección de Datos",
                    "rango": "Ley Orgánica",
                    "departamento": "Jefatura del Estado",
                    "fecha_publicacion": "2018-12-06",
                    "estado_consolidacion": "Vigente con modificaciones",
                }
            ],
        }
    }


@pytest.mark.asyncio
async def test_get_boe_summary(httpx_mock: HTTPXMock, sample_boe_summary):
    httpx_mock.add_response(
        url=re.compile(r"https://www\.boe\.es/datosabiertos/api/boe/sumario/20241201"),
        json=sample_boe_summary,
    )

    result = await get_boe_summary("20241201")

    assert "sumario" in result
    assert result["sumario"]["metadatos"]["numero_oficial"] == "290"


@pytest.mark.asyncio
async def test_search_legislation(httpx_mock: HTTPXMock, sample_legislation_search):
    # /legislacion-consolidada is permanently broken (HTTP 500); search_legislation
    # raises RuntimeError immediately without making an HTTP call.
    with pytest.raises(RuntimeError, match="legislacion-consolidada"):
        await search_legislation("proteccion datos")
