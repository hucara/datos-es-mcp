"""
Tests for AIReF helper client and get_airef_data tool.
"""

import re

import pytest
from pytest_httpx import HTTPXMock

from helpers.airef_client import TOPIC_REGISTRY, search_airef_related_datasets
from tools.get_airef_data import register_get_airef_data_tool

# ── Helpers ────────────────────────────────────────────────────────────────────


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


_SAMPLE_ITEM = {
    "_about": "https://datos.gob.es/catalogo/e00003901-previsiones-macro-2024",
    "title": [{"_value": "Previsiones Macroeconómicas 2024", "_lang": "es"}],
    "description": [
        {
            "_value": "Actualización de previsiones fiscales y macroeconómicas",
            "_lang": "es",
        }
    ],
    "publisher": "http://datos.gob.es/recurso/sector-publico/org/Organismo/E00003901",
    "distribution": [
        {
            "_about": "https://datos.gob.es/catalogo/e00003901-previsiones-macro-2024/r1",
            "accessURL": "https://example.com/previsiones.xlsx",
            "format": {
                "type": "http://purl.org/dc/terms/IMT",
                "value": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            },
            "title": [{"_value": "Datos Excel", "_lang": "es"}],
        }
    ],
    "issued": "2024-05-01T00:00:00",
    "modified": "2024-05-01T00:00:00",
}


class _MockMCP:
    """Minimal FastMCP stand-in that captures the registered tool function."""

    def __init__(self):
        self.fn = None

    def tool(self):
        def decorator(fn):
            self.fn = fn
            return fn

        return decorator


@pytest.fixture
def get_airef_data_fn():
    mcp = _MockMCP()
    register_get_airef_data_tool(mcp)
    return mcp.fn


# ── airef_client unit tests ────────────────────────────────────────────────────


def test_topic_registry_has_required_topics():
    """All expected topics must exist in the registry."""
    required = {
        "previsiones",
        "sostenibilidad_fiscal",
        "spending_review",
        "inmigracion_pib",
        "fiscal_drag",
        "observatorio_ccaa",
    }
    assert required.issubset(set(TOPIC_REGISTRY.keys()))


def test_topic_registry_entries_have_required_fields():
    """Each topic must have description, airef_url, query, and notes."""
    for key, entry in TOPIC_REGISTRY.items():
        assert "description" in entry, f"Missing 'description' in topic '{key}'"
        assert "airef_url" in entry, f"Missing 'airef_url' in topic '{key}'"
        assert "query" in entry, f"Missing 'query' in topic '{key}'"
        assert "notes" in entry, f"Missing 'notes' in topic '{key}'"


@pytest.mark.asyncio
async def test_search_airef_related_datasets_returns_results(httpx_mock: HTTPXMock):
    """Client should return normalized datasets from datos.gob.es."""
    httpx_mock.add_response(
        url=re.compile(r"https://datos\.gob\.es/apidata/catalog/dataset/title/"),
        json=_semantic_response([_SAMPLE_ITEM]),
    )

    result = await search_airef_related_datasets(topic="previsiones")

    assert result["count"] == 1
    assert len(result["results"]) == 1
    assert result["results"][0]["title"] == "Previsiones Macroeconómicas 2024"
    assert result["topic_info"]["topic"] == "previsiones"
    assert "airef_url" in result["topic_info"]
    assert "notes" in result["topic_info"]


@pytest.mark.asyncio
async def test_search_airef_custom_query(httpx_mock: HTTPXMock):
    """Custom query should override the curated topic query."""
    httpx_mock.add_response(
        url=re.compile(r"https://datos\.gob\.es/apidata/catalog/dataset/title/inmigr"),
        json=_semantic_response([]),
    )

    result = await search_airef_related_datasets(
        topic="previsiones", custom_query="inmigracion economia española"
    )

    assert result["count"] == 0
    assert result["results"] == []


@pytest.mark.asyncio
async def test_search_airef_empty_results(httpx_mock: HTTPXMock):
    """Client should handle empty results gracefully."""
    httpx_mock.add_response(
        url=re.compile(r"https://datos\.gob\.es/apidata/catalog/dataset/title/"),
        json=_semantic_response([]),
    )

    result = await search_airef_related_datasets(topic="spending_review")

    assert result["results"] == []
    assert result["count"] == 0
    assert result["topic_info"]["topic"] == "spending_review"


# ── get_airef_data tool tests ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_airef_data_invalid_topic(get_airef_data_fn):
    """Tool should return an error message for unknown topics."""
    result = await get_airef_data_fn(topic="unknown_topic")

    assert "Invalid topic" in result
    assert "unknown_topic" in result


@pytest.mark.asyncio
async def test_get_airef_data_returns_datasets(
    httpx_mock: HTTPXMock, get_airef_data_fn
):
    """Tool should format datasets with title, publisher, and portal link."""
    httpx_mock.add_response(
        url=re.compile(r"https://datos\.gob\.es/apidata/catalog/dataset/title/"),
        json=_semantic_response([_SAMPLE_ITEM]),
    )

    result = await get_airef_data_fn(topic="previsiones")

    assert "AIReF" in result
    assert "Previsiones Macroeconómicas 2024" in result
    assert "airef.es" in result
    assert "list_dataset_resources" in result


@pytest.mark.asyncio
async def test_get_airef_data_includes_guidance(
    httpx_mock: HTTPXMock, get_airef_data_fn
):
    """Tool output should include claim-verification guidance notes."""
    httpx_mock.add_response(
        url=re.compile(r"https://datos\.gob\.es/apidata/catalog/dataset/title/"),
        json=_semantic_response([]),
    )

    result = await get_airef_data_fn(topic="fiscal_drag")

    assert (
        "fiscal_drag" not in result or "guidance" in result.lower() or "AEAT" in result
    )
    assert "airef.es" in result


@pytest.mark.asyncio
async def test_get_airef_data_immigration_topic(
    httpx_mock: HTTPXMock, get_airef_data_fn
):
    """Immigration topic should include guidance about the 40% GDP claim."""
    httpx_mock.add_response(
        url=re.compile(r"https://datos\.gob\.es/apidata/catalog/dataset/title/"),
        json=_semantic_response([]),
    )

    result = await get_airef_data_fn(topic="inmigracion_pib")

    assert "AIReF" in result
    # The tool should mention the GDP contribution context
    assert "PIB" in result or "GDP" in result or "inmigr" in result.lower()


@pytest.mark.asyncio
async def test_get_airef_data_empty_fallback_message(
    httpx_mock: HTTPXMock, get_airef_data_fn
):
    """When no datasets found, tool should suggest using AIReF portal directly."""
    httpx_mock.add_response(
        url=re.compile(r"https://datos\.gob\.es/apidata/catalog/dataset/title/"),
        json=_semantic_response([]),
    )

    result = await get_airef_data_fn(topic="sostenibilidad_fiscal")

    assert "airef.es" in result
    # Should contain fallback message
    assert "portal" in result.lower() or "No related datasets" in result


@pytest.mark.asyncio
async def test_get_airef_data_custom_query(httpx_mock: HTTPXMock, get_airef_data_fn):
    """Custom query override should be accepted."""
    httpx_mock.add_response(
        url=re.compile(r"https://datos\.gob\.es/apidata/catalog/dataset/title/"),
        json=_semantic_response([_SAMPLE_ITEM]),
    )

    result = await get_airef_data_fn(
        topic="previsiones", query="deuda publica sostenibilidad"
    )

    assert "AIReF" in result
    assert "Previsiones Macroeconómicas 2024" in result
