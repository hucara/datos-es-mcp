import logging

from mcp.server.fastmcp import FastMCP

from helpers import datos_gob_es_client
from helpers.http import source_footer, url_capture
from helpers.logging import MAIN_LOGGER_NAME, log_tool
from helpers.publishers import find_publisher

logger = logging.getLogger(MAIN_LOGGER_NAME)

# Generic Spanish stop words that break AND-based searches on datos.gob.es
_STOP_WORDS = {
    "datos",
    "dato",
    "fichero",
    "ficheros",
    "archivo",
    "archivos",
    "tabla",
    "tablas",
    "csv",
    "excel",
    "xlsx",
    "json",
    "xml",
    "dataset",
    "conjuntos",
    "conjunto",
}


def _clean_query(query: str) -> str:
    words = query.split()
    cleaned = [w for w in words if w.lower().strip() not in _STOP_WORDS]
    result = " ".join(cleaned).strip()
    if result != query:
        logger.debug("Cleaned search query: '%s' -> '%s'", query, result)
    return result or query


def register_search_datasets_tool(mcp: FastMCP) -> None:
    @mcp.tool()
    @log_tool
    async def search_datasets(
        query: str,
        theme: str | None = None,
        publisher: str | None = None,
        format: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> str:
        """
        LAST RESORT: Search the datos.gob.es catalog by dataset title.

        WARNING: datos.gob.es datasets are poorly tagged and the title-keyword search
        returns noisy, often irrelevant results. This tool finds dataset references
        (titles + download links), NOT actual data values.

        Use dedicated tools instead whenever possible — they hit real APIs and return numbers:
          - INE statistics   → query_ine_data(operation_code=...) [IPC, EPA, CNE, MNP, IPVFN, ...]
          - BdE rates        → get_bde_series
          - Eurostat         → get_eurostat_data
          - AEAT fiscal      → get_aeat_stats
          - Health stats     → get_health_stats
          - Education stats  → get_education_stats
          - Housing stats    → get_housing_stats
          - SS/pensions      → get_social_security_stats
          - Traffic (DGT)    → get_traffic_stats
          - Justice (CGPJ)   → get_justice_stats
          - Energy (REData)  → get_energy_data
          - BOE/legislation  → get_boe_summary / search_legislation

        Use this tool ONLY when:
          - The institution has no dedicated tool (e.g. CNMV, Tribunal de Cuentas, Hacienda transfers)
          - Searching by publisher= code to list all datasets from a specific organisation
          - Explicitly looking for a downloadable bulk file (CSV/XLSX) to inspect

        Args:
            query: Single distinctive keyword — the API matches against dataset titles only.
                   Multi-word phrases are reduced to the first non-generic word.
            publisher: Publisher code on datos.gob.es. When provided, returns all datasets
                       from that publisher (ignores query). More reliable than keyword search.
                       Known codes: EA0028512=AEAT, EA0010587=INE
            theme: Ignored by current API.
            format: Ignored by current API.
            page: Page number (default: 1).
            page_size: Results per page (default: 20, max: 100).
        """
        _urls: list[str] = []
        url_capture.set(_urls)

        # Resolve publisher alias to CKAN slug if needed
        resolved_publisher = publisher
        if publisher:
            slug = find_publisher(publisher)
            if slug and slug != publisher:
                logger.debug("Publisher '%s' resolved to slug '%s'", publisher, slug)
                resolved_publisher = slug

        cleaned_query = _clean_query(query)
        result = await datos_gob_es_client.search_datasets(
            query=cleaned_query,
            theme=theme,
            publisher=resolved_publisher,
            format=format,
            page=page,
            page_size=page_size,
        )

        datasets = result.get("results", [])

        # Fallback to original query if cleaned returns nothing
        if not datasets and cleaned_query != query:
            result = await datos_gob_es_client.search_datasets(
                query=query,
                theme=theme,
                publisher=resolved_publisher,
                format=format,
                page=page,
                page_size=page_size,
            )
            datasets = result.get("results", [])

        if not datasets:
            return f"No datasets found for query: '{query}'"

        content_parts = [
            f"Found {result.get('count', len(datasets))} dataset(s) for query: '{query}'",
            f"Page {page} of results:\n",
        ]
        for i, ds in enumerate(datasets, 1):
            content_parts.append(f"{i}. {ds.get('title', 'Untitled')}")
            content_parts.append(f"   ID: {ds.get('id')}")
            if ds.get("description"):
                content_parts.append(f"   Description: {ds['description'][:200]}...")
            if ds.get("organization"):
                content_parts.append(f"   Organization: {ds['organization']}")
            if ds.get("themes"):
                content_parts.append(f"   Themes: {', '.join(ds['themes'][:3])}")
            if ds.get("formats"):
                content_parts.append(f"   Formats: {', '.join(ds['formats'][:5])}")
            content_parts.append(f"   Resources: {ds.get('resources_count', 0)}")
            if ds.get("last_modified"):
                content_parts.append(f"   Last updated: {ds['last_modified'][:10]}")
            content_parts.append(f"   URL: {ds.get('url')}")
            content_parts.append("")

        content_parts.append(source_footer(_urls))
        return "\n".join(content_parts)
