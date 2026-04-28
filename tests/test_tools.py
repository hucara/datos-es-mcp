"""
Tool-layer tests: exercise the MCP tool functions (output formatting, business logic,
edge cases) on top of mocked HTTP responses.

Uses _MockMCP to capture the registered async function without spinning up a real
FastMCP server.
"""

import re

import pytest
from pytest_httpx import HTTPXMock

from tools.get_bde_series import register_get_bde_series_tool
from tools.get_boe_summary import register_get_boe_summary_tool
from tools.query_ine_data import register_query_ine_data_tool
from tools.search_datasets import register_search_datasets_tool
from tools.search_legislation import register_search_legislation_tool


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
def search_datasets_fn():
    mcp = _MockMCP()
    register_search_datasets_tool(mcp)
    return mcp.fn


@pytest.fixture
def query_ine_data_fn():
    mcp = _MockMCP()
    register_query_ine_data_tool(mcp)
    return mcp.fn


@pytest.fixture
def get_bde_series_fn():
    mcp = _MockMCP()
    register_get_bde_series_tool(mcp)
    return mcp.fn


@pytest.fixture
def get_boe_summary_fn():
    mcp = _MockMCP()
    register_get_boe_summary_tool(mcp)
    return mcp.fn


@pytest.fixture
def search_legislation_fn():
    mcp = _MockMCP()
    register_search_legislation_tool(mcp)
    return mcp.fn


# ── search_datasets ────────────────────────────────────────────────────────────


def _semantic_resp(items: list) -> dict:
    """Wrap items in the datos.gob.es semantic API envelope."""
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


_DS1 = {
    "_about": "https://datos.gob.es/catalogo/ea0010587-padron-municipal-2023",
    "title": [{"_value": "Padrón Municipal 2023", "_lang": "es"}],
    "description": [{"_value": "Cifras de población por municipio", "_lang": "es"}],
    "publisher": "http://datos.gob.es/recurso/sector-publico/org/Organismo/EA0010587",
    "distribution": [
        {
            "_about": "https://datos.gob.es/catalogo/ea0010587-padron-municipal-2023/resource/r1",
            "accessURL": "https://example.com/d.csv",
            "format": {"type": "http://purl.org/dc/terms/IMT", "value": "text/csv"},
            "title": [{"_value": "Datos CSV", "_lang": "es"}],
        }
    ],
    "modified": "2024-01-15T10:00:00",
}

_DS_EMP = {
    "_about": "https://datos.gob.es/catalogo/sepe-empleo-datos",
    "title": [{"_value": "Estadísticas de Empleo con Datos", "_lang": "es"}],
    "description": [],
    "publisher": "http://datos.gob.es/recurso/sector-publico/org/Organismo/EA0023598",
    "distribution": [],
    "modified": "2024-06-01",
}


@pytest.mark.asyncio
async def test_search_datasets_formats_output(
    httpx_mock: HTTPXMock, search_datasets_fn
):
    httpx_mock.add_response(
        url=re.compile(r"https://datos\.gob\.es/apidata/catalog/dataset/title/"),
        json=_semantic_resp([_DS1]),
    )

    result = await search_datasets_fn(query="padrón municipal")

    assert "Padrón Municipal 2023" in result
    assert "ea0010587-padron-municipal-2023" in result
    assert "EA0010587" in result
    assert "CSV" in result


@pytest.mark.asyncio
async def test_search_datasets_no_results(httpx_mock: HTTPXMock, search_datasets_fn):
    httpx_mock.add_response(
        url=re.compile(r"https://datos\.gob\.es/apidata/catalog/dataset/title/"),
        json=_semantic_resp([]),
        is_reusable=True,
    )

    result = await search_datasets_fn(query="xyznotexistingquery")

    assert "No datasets found" in result


@pytest.mark.asyncio
async def test_search_datasets_stopword_cleaning_falls_back(
    httpx_mock: HTTPXMock, search_datasets_fn
):
    """Stop words are removed from the query; if that returns nothing the original is retried."""
    httpx_mock.add_response(
        url=re.compile(r"https://datos\.gob\.es/apidata/catalog/dataset/title/"),
        json=_semantic_resp([]),
        is_reusable=True,
    )

    # "datos" is a stop word — will be stripped, both calls return empty
    result = await search_datasets_fn(query="datos empleo")

    assert "No datasets found" in result


@pytest.mark.asyncio
async def test_search_datasets_stopword_cleaning_succeeds_after_fallback(
    httpx_mock: HTTPXMock, search_datasets_fn
):
    """Cleaned query returns nothing, but original query returns results.

    "conjunto" is in the tool's _STOP_WORDS list (gets stripped) but is NOT
    in the client's _GENERIC_WORDS, so it produces a different keyword.
    - cleaned query "empleo" → client uses "empleo" → title/empleo.json → empty
    - original "conjunto empleo" → client uses "conjunto" (first non-generic) → title/conjunto.json → found
    """
    # First call (cleaned query "empleo") → title/empleo.json → empty
    httpx_mock.add_response(
        url=re.compile(r"https://datos\.gob\.es/apidata/catalog/dataset/title/empleo"),
        json=_semantic_resp([]),
    )
    # Second call (original "conjunto empleo") → title/conjunto.json → found
    httpx_mock.add_response(
        url=re.compile(
            r"https://datos\.gob\.es/apidata/catalog/dataset/title/conjunto"
        ),
        json=_semantic_resp([_DS_EMP]),
    )

    result = await search_datasets_fn(query="conjunto empleo")

    assert "Estadísticas de Empleo con Datos" in result


# ── query_ine_data ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_query_ine_data_requires_param(query_ine_data_fn):
    result = await query_ine_data_fn()
    assert "Error" in result
    assert "operation_code" in result


@pytest.mark.asyncio
async def test_query_ine_data_operation_code_mode(
    httpx_mock: HTTPXMock, query_ine_data_fn
):
    httpx_mock.add_response(
        url=re.compile(
            r"https://servicios\.ine\.es/wstempus/js/ES/TABLAS_OPERACION/IPC"
        ),
        json=[
            {
                "Id": 50902,
                "Nombre": "IPC General Nacional",
                "Ultima_Modificacion": "2024-03-01",
            },
            {
                "Id": 50903,
                "Nombre": "IPC por CCAA",
                "Ultima_Modificacion": "2024-03-01",
            },
        ],
    )

    result = await query_ine_data_fn(operation_code="IPC")

    assert "IPC General Nacional" in result
    assert "50902" in result
    assert "IPC por CCAA" in result


@pytest.mark.asyncio
async def test_query_ine_data_table_mode(httpx_mock: HTTPXMock, query_ine_data_fn):
    httpx_mock.add_response(
        url=re.compile(r"https://servicios\.ine\.es/wstempus/js/ES/DATOS_TABLA/50902"),
        json=[
            {
                "Nombre": "IPC General Nacional",
                "Unidad": {"Nombre": "Índice"},
                "Periodicidad": {"Nombre": "Mensual"},
                "Data": [
                    {"Fecha": 1704067200000, "Valor": 112.4},
                    {"Fecha": 1706745600000, "Valor": 112.9},
                ],
            }
        ],
    )

    result = await query_ine_data_fn(table_id="50902", last_n_periods=2)

    assert "IPC General Nacional" in result
    assert "112.4" in result
    assert "Índice" in result


@pytest.mark.asyncio
async def test_query_ine_data_series_mode(httpx_mock: HTTPXMock, query_ine_data_fn):
    httpx_mock.add_response(
        url=re.compile(
            r"https://servicios\.ine\.es/wstempus/js/ES/DATOS_SERIE/IPC251856"
        ),
        json={
            "Nombre": "IPC General Nacional",
            "COD": "IPC251856",
            "Unidad": {"Nombre": "Índice"},
            "Periodicidad": {"Nombre": "Mensual"},
            "Data": [{"Fecha": 1704067200000, "Valor": 112.4}],
        },
    )

    result = await query_ine_data_fn(series_code="IPC251856", last_n_periods=1)

    assert "IPC General Nacional" in result
    assert "IPC251856" in result
    assert "112.4" in result


@pytest.mark.asyncio
async def test_query_ine_data_operation_not_found(
    httpx_mock: HTTPXMock, query_ine_data_fn
):
    httpx_mock.add_response(
        url=re.compile(
            r"https://servicios\.ine\.es/wstempus/js/ES/TABLAS_OPERACION/UNKNOWN"
        ),
        json=[],
    )

    result = await query_ine_data_fn(operation_code="UNKNOWN")

    assert "No tables found" in result


# ── get_bde_series ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_bde_series_no_codes(get_bde_series_fn):
    result = await get_bde_series_fn(series_codes="")
    assert "Error" in result


@pytest.mark.asyncio
async def test_get_bde_series_history(httpx_mock: HTTPXMock, get_bde_series_fn):
    httpx_mock.add_response(
        url=re.compile(
            r"https://app\.bde\.es/bierest/resources/srdatosapp/listaSeries"
        ),
        json=[
            {
                "serie": "TI_1_2_1",
                "descripcion": "ECB deposit facility rate",
                "codFrecuencia": "M",
                "simbolo": "%",
                "decimales": 2,
                "fechaInicio": "1999-01-01",
                "fechaFin": "2024-12-01",
                "fechas": ["2024-10-01", "2024-11-01", "2024-12-01"],
                "valores": [3.25, 3.25, 3.0],
            }
        ],
    )

    result = await get_bde_series_fn(series_codes="TI_1_2_1", time_range="30M")

    assert "ECB deposit facility rate" in result
    assert "TI_1_2_1" in result
    assert "3.0" in result


@pytest.mark.asyncio
async def test_get_bde_series_latest_only(httpx_mock: HTTPXMock, get_bde_series_fn):
    httpx_mock.add_response(
        url=re.compile(r"https://app\.bde\.es/bierest/resources/srdatosapp/favoritas"),
        json=[
            {
                "serie": "TI_1_2_1",
                "descripcionCorta": "ECB deposit rate",
                "codFrecuencia": "M",
                "simbolo": "%",
                "tendencia": "=",
                "fechaValor": "2024-12-01",
                "valor": 3.0,
            }
        ],
    )

    result = await get_bde_series_fn(series_codes="TI_1_2_1", latest_only=True)

    assert "ECB deposit rate" in result
    assert "3.0" in result
    assert "2024-12-01" in result


@pytest.mark.asyncio
async def test_get_bde_series_not_found(httpx_mock: HTTPXMock, get_bde_series_fn):
    httpx_mock.add_response(
        url=re.compile(
            r"https://app\.bde\.es/bierest/resources/srdatosapp/listaSeries"
        ),
        json=[],
    )

    result = await get_bde_series_fn(series_codes="INVALID_CODE")

    assert "No data found" in result


# ── get_boe_summary ────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_get_boe_summary_invalid_gazette(get_boe_summary_fn):
    result = await get_boe_summary_fn(date="20241201", gazette="INVALID")
    assert "Error" in result
    assert "gazette" in result.lower() or "BOE" in result


@pytest.mark.asyncio
async def test_get_boe_summary_formats_sections(
    httpx_mock: HTTPXMock, get_boe_summary_fn
):
    httpx_mock.add_response(
        url=re.compile(r"https://www\.boe\.es/datosabiertos/api/boe/sumario/20241201"),
        json={
            "sumario": {
                "metadatos": {"fecha_publicacion": "20241201", "numero_oficial": "290"},
                "diario": {
                    "seccion": [
                        {
                            "nombre": "I. Disposiciones generales",
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
        },
    )

    result = await get_boe_summary_fn(date="20241201")

    assert "BOE Summary" in result
    assert "No. 290" in result
    assert "I. Disposiciones generales" in result
    assert "Real Decreto 1234/2024" in result
    assert "Ministerio de Hacienda" in result


@pytest.mark.asyncio
async def test_get_boe_summary_no_sections(httpx_mock: HTTPXMock, get_boe_summary_fn):
    httpx_mock.add_response(
        url=re.compile(r"https://www\.boe\.es/datosabiertos/api/boe/sumario/20250101"),
        json={
            "sumario": {
                "metadatos": {"fecha_publicacion": "20250101"},
                "diario": {"seccion": []},
            }
        },
    )

    result = await get_boe_summary_fn(date="20250101")

    assert "20250101" in result


# ── search_legislation ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_legislation_not_found(
    httpx_mock: HTTPXMock, search_legislation_fn
):
    httpx_mock.add_response(
        url=re.compile(
            r"https://www\.boe\.es/datosabiertos/api/legislacion-consolidada"
        ),
        json={"response": {"numFound": 0, "docs": []}},
    )

    result = await search_legislation_fn(query="xyznotexisting")

    assert "No legislation found" in result


@pytest.mark.asyncio
async def test_search_legislation_formats_results(
    httpx_mock: HTTPXMock, search_legislation_fn
):
    httpx_mock.add_response(
        url=re.compile(
            r"https://www\.boe\.es/datosabiertos/api/legislacion-consolidada"
        ),
        json={
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
        },
    )

    result = await search_legislation_fn(query="proteccion datos")

    assert "Ley Orgánica 3/2018" in result
    assert "BOE-A-2018-16673" in result
    assert "Jefatura del Estado" in result
    assert "Vigente con modificaciones" in result
    assert "boe.es/buscar/act.php" in result
