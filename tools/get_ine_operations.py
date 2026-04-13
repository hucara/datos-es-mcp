from mcp.server.fastmcp import FastMCP

from helpers.cache import metadata_cache
from helpers.logging import log_tool


def register_get_ine_operations_tool(mcp: FastMCP) -> None:
    @mcp.tool()
    @log_tool
    async def get_ine_operations(search: str | None = None, page: int = 1) -> str:
        """
        List available statistical operations from INE (Instituto Nacional de Estadística).

        Returns a paginated list of all statistical surveys and operations in INEbase.
        Results are served from a 24-hour cache after the first call.
        Use this to discover operation codes before calling query_ine_data.

        Common operations:
        - IPC: Índice de Precios de Consumo (Consumer Price Index)
        - EPA: Encuesta de Población Activa (Labour Force Survey)
        - CN: Contabilidad Nacional (National Accounts / GDP)
        - PADRON: Padrón Municipal (Municipal Register — population by municipality)
        - EPNFL: Estadística de Nacimientos (Birth Statistics)
        - DEFUN: Estadística de Defunciones (Death Statistics)

        Args:
            search: Optional keyword filter applied to operation names and codes.
            page: Page number (default: 1, 50 results per page).
        """
        try:
            ops = await metadata_cache.get_ine_operations()
        except Exception as e:  # noqa: BLE001
            return f"Error fetching INE operations: {e}"

        if search:
            search_lower = search.lower()
            ops = [
                op for op in ops
                if search_lower in (op.get("Nombre") or "").lower()
                or search_lower in (op.get("Codigo") or "").lower()
            ]

        if not ops:
            msg = "No INE operations found" + (f" matching '{search}'" if search else "")
            return msg

        # Paginate in-memory (50 per page)
        page_size = 50
        total = len(ops)
        start = (page - 1) * page_size
        page_ops = ops[start : start + page_size]

        if not page_ops:
            return f"Page {page} is out of range. Total operations: {total}."

        content_parts = [
            f"INE Statistical Operations (page {page}, {page_size}/page):",
            f"Showing {len(page_ops)} of {total} operation(s)"
            + (f" matching '{search}'" if search else "") + ":\n",
        ]

        for op in page_ops:
            name = op.get("Nombre") or "Unknown"
            code = op.get("Codigo") or op.get("Id") or "?"
            periodicity = op.get("Periodicidad", {})
            if isinstance(periodicity, dict):
                period_name = periodicity.get("Nombre", "")
            else:
                period_name = str(periodicity)

            line = f"  [{code}] {name}"
            if period_name:
                line += f" ({period_name})"
            content_parts.append(line)

        if total > start + page_size:
            remaining = total - start - page_size
            content_parts.append(
                f"\n... {remaining} more operation(s). Use page={page + 1} to continue."
            )

        content_parts.append(
            "\nUse query_ine_data with the operation code to retrieve statistical data."
        )
        return "\n".join(content_parts)
