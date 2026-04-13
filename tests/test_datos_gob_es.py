"""
Tests for datos.gob.es client and search tools.
"""

import pytest
import pytest_asyncio
from pytest_httpx import HTTPXMock

from helpers.datos_gob_es_client import search_datasets, get_dataset_details


@pytest.fixture
def ckan_search_response():
    return {
        "success": True,
        "result": {
            "count": 2,
            "results": [
                {
                    "id": "test-id-1",
                    "name": "test-dataset-1",
                    "title": "Padrón Municipal 2023",
                    "notes": "Cifras de población por municipio",
                    "organization": {"title": "INE", "name": "ine"},
                    "theme": [{"id": "sector-publico", "label": "Sector Público"}],
                    "tags": [{"display_name": "padrón"}, {"display_name": "población"}],
                    "resources": [
                        {"id": "r1", "format": "CSV", "url": "https://example.com/data.csv"},
                    ],
                    "metadata_modified": "2024-01-15T10:00:00",
                },
                {
                    "id": "test-id-2",
                    "name": "test-dataset-2",
                    "title": "Censo 2021",
                    "notes": "Resultados del censo de población",
                    "organization": {"title": "INE", "name": "ine"},
                    "theme": [],
                    "tags": [],
                    "resources": [],
                    "metadata_modified": "2022-06-01T00:00:00",
                },
            ],
        },
    }


@pytest.mark.asyncio
async def test_search_datasets_returns_results(httpx_mock: HTTPXMock, ckan_search_response):
    httpx_mock.add_response(
        url="https://datos.gob.es/catalog/api/action/package_search",
        match_querystring=False,
        json=ckan_search_response,
    )

    result = await search_datasets(query="padron municipal")

    assert result["count"] == 2
    assert len(result["results"]) == 2
    assert result["results"][0]["title"] == "Padrón Municipal 2023"
    assert result["results"][0]["organization"] == "INE"
    assert "CSV" in result["results"][0]["formats"]


@pytest.mark.asyncio
async def test_search_datasets_empty(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://datos.gob.es/catalog/api/action/package_search",
        match_querystring=False,
        json={"success": True, "result": {"count": 0, "results": []}},
    )

    result = await search_datasets(query="xxxxxxxxnotexisting")

    assert result["count"] == 0
    assert result["results"] == []


@pytest.mark.asyncio
async def test_get_dataset_details(httpx_mock: HTTPXMock):
    httpx_mock.add_response(
        url="https://datos.gob.es/catalog/api/action/package_show",
        match_querystring=False,
        json={
            "success": True,
            "result": {
                "id": "test-id-1",
                "name": "test-dataset-1",
                "title": "Padrón Municipal 2023",
                "notes": "Descripción completa",
                "resources": [{"id": "r1", "format": "CSV"}],
                "metadata_modified": "2024-01-15",
                "license_title": "Creative Commons Attribution",
            },
        },
    )

    data = await get_dataset_details("test-id-1")

    assert data["id"] == "test-id-1"
    assert data["title"] == "Padrón Municipal 2023"
    assert len(data["resources"]) == 1
