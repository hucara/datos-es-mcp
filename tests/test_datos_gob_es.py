"""
Tests for datos.gob.es client and search tools.
"""

import re

import pytest
from pytest_httpx import HTTPXMock

from helpers.datos_gob_es_client import get_dataset_details, search_datasets


def _semantic_response(items: list) -> dict:
    """Wrap items in the datos.gob.es semantic API response envelope."""
    return {
        "format": "linked-data-api",
        "version": "0.2",
        "result": {
            "items": items,
            "itemsPerPage": len(items),
            "page": 0,
            "totalResults": len(items),
        },
    }


_SAMPLE_ITEMS = [
    {
        "_about": "https://datos.gob.es/catalogo/ea0010587-padron-municipal-2023",
        "title": [{"_value": "Padrón Municipal 2023", "_lang": "es"}],
        "description": [{"_value": "Cifras de población por municipio", "_lang": "es"}],
        "publisher": "http://datos.gob.es/recurso/sector-publico/org/Organismo/EA0010587",
        "distribution": [
            {
                "_about": "https://datos.gob.es/catalogo/ea0010587-padron-municipal-2023/resource/r1",
                "accessURL": "https://example.com/data.csv",
                "format": {"type": "http://purl.org/dc/terms/IMT", "value": "text/csv"},
                "title": [{"_value": "Datos CSV", "_lang": "es"}],
            }
        ],
        "issued": "2024-01-15T10:00:00",
        "modified": "2024-01-15T10:00:00",
        "keyword": [{"_value": "padrón"}, {"_value": "población"}],
    },
    {
        "_about": "https://datos.gob.es/catalogo/ea0010587-censo-2021",
        "title": [{"_value": "Censo 2021", "_lang": "es"}],
        "description": [{"_value": "Resultados del censo de población", "_lang": "es"}],
        "publisher": "http://datos.gob.es/recurso/sector-publico/org/Organismo/EA0010587",
        "distribution": [],
        "issued": "2022-06-01T00:00:00",
        "modified": "2022-06-01T00:00:00",
        "keyword": [],
    },
]


@pytest.mark.asyncio
async def test_search_datasets_returns_results(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=re.compile(r"https://datos\.gob\.es/apidata/catalog/dataset/title/padron"),
        json=_semantic_response(_SAMPLE_ITEMS),
    )

    result = await search_datasets(query="padron municipal")

    assert result["count"] == 2
    assert len(result["results"]) == 2
    assert result["results"][0]["title"] == "Padrón Municipal 2023"
    assert result["results"][0]["organization"] == "EA0010587"
    assert "CSV" in result["results"][0]["formats"]


@pytest.mark.asyncio
async def test_search_datasets_empty(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url=re.compile(r"https://datos\.gob\.es/apidata/catalog/dataset/title/"),
        json=_semantic_response([]),
    )

    result = await search_datasets(query="xxxxxxxxnotexisting")

    assert result["count"] == 0
    assert result["results"] == []


@pytest.mark.asyncio
async def test_get_dataset_details(httpx_mock: HTTPXMock):
    # First attempt: direct slug lookup returns 404 (endpoint may not exist)
    httpx_mock.add_response(
        url=re.compile(r"https://datos\.gob\.es/apidata/catalog/dataset/padron\.json"),
        status_code=404,
    )
    # Second attempt: publisher lookup fails (returns empty)
    httpx_mock.add_response(
        url=re.compile(
            r"https://datos\.gob\.es/apidata/catalog/dataset/publisher/padron"
        ),
        json=_semantic_response([]),
    )
    # Third attempt: title lookup succeeds
    httpx_mock.add_response(
        url=re.compile(r"https://datos\.gob\.es/apidata/catalog/dataset/title/padron"),
        json=_semantic_response([_SAMPLE_ITEMS[0]]),
    )

    data = await get_dataset_details("padron")

    assert "padron" in data["id"]
    assert data["title"] == "Padrón Municipal 2023"
    assert len(data["resources"]) == 1
