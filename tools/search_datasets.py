import logging

from mcp.server.fastmcp import FastMCP

from helpers import datos_gob_es_client
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
        Search for datasets in the datos.gob.es catalog (90,000+ Spanish open datasets).

        This is the starting point for discovering Spanish public data.
        Use specific keywords; the API uses AND logic so generic words like "datos"
        may return zero results.

        Args:
            query: Search keywords (e.g. "paro registrado", "contaminacion aire Madrid").
            theme: NTI sector filter. Common values:
                   "sector-publico", "economia", "medio-ambiente", "transporte",
                   "educacion", "salud", "ciencia-tecnologia", "vivienda",
                   "hacienda", "justicia", "turismo", "empleo", "agricultura".
            publisher: Publisher name or slug. Accepts common names like "INE",
                       "AEMET", "Ministerio de Sanidad", "Comunidad de Madrid", etc.
                       Also accepts raw CKAN slugs like "instituto-nacional-de-estadistica".
            format: File format filter (e.g. "CSV", "JSON", "XML", "XLSX").
            page: Page number (default: 1).
            page_size: Results per page (default: 20, max: 100).

        Typical workflow: search_datasets → get_dataset_info → list_dataset_resources.
        """
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

        return "\n".join(content_parts)
