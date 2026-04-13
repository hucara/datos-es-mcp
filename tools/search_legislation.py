from mcp.server.fastmcp import FastMCP

from helpers import boe_client
from helpers.logging import log_tool


def register_search_legislation_tool(mcp: FastMCP) -> None:
    @mcp.tool()
    @log_tool
    async def search_legislation(
        query: str,
        from_date: str | None = None,
        to_date: str | None = None,
        page: int = 1,
        page_size: int = 20,
    ) -> str:
        """
        Search Spain's consolidated legislation (Legislación Consolidada) via the BOE API.

        Returns laws, decrees, and regulations currently in force, with their
        consolidation status, issuing department, and document identifiers.

        Args:
            query: Search text (e.g. "proteccion datos", "contratos publicos", "IVA").
            from_date: Start date filter in YYYY-MM-DD format (e.g. "2020-01-01").
            to_date: End date filter in YYYY-MM-DD format (e.g. "2024-12-31").
            page: Page number (default: 1).
            page_size: Results per page (default: 20, max: 100).
        """
        offset = (page - 1) * page_size
        try:
            data = await boe_client.search_legislation(
                query=query,
                from_date=from_date,
                to_date=to_date,
                offset=offset,
                limit=page_size,
            )
        except Exception as e:  # noqa: BLE001
            return f"Error searching legislation for '{query}': {e}"

        response = data.get("response") or data
        docs = response.get("docs") or []
        total = response.get("numFound") or len(docs)

        if not docs:
            return f"No legislation found matching '{query}'."

        content_parts = [
            f"Consolidated Legislation — {total} result(s) for '{query}'",
            f"Page {page} (showing {len(docs)} results):\n",
        ]

        for i, doc in enumerate(docs, offset + 1):
            title = doc.get("titulo") or doc.get("title") or "Unknown"
            doc_id = doc.get("identificador") or doc.get("id") or "?"
            dept = doc.get("departamento") or doc.get("organismo") or ""
            rango = doc.get("rango") or ""
            fecha = doc.get("fecha_publicacion") or doc.get("fecha") or ""
            estado = doc.get("estado_consolidacion") or ""

            content_parts.append(f"{i}. {title}")
            content_parts.append(f"   ID: {doc_id}")
            if rango:
                content_parts.append(f"   Type: {rango}")
            if dept:
                content_parts.append(f"   Department: {dept}")
            if fecha:
                content_parts.append(f"   Published: {str(fecha)[:10]}")
            if estado:
                content_parts.append(f"   Status: {estado}")
            content_parts.append(
                f"   URL: https://www.boe.es/buscar/act.php?id={doc_id}"
            )
            content_parts.append("")

        return "\n".join(content_parts)
