from mcp.server.fastmcp import FastMCP

from helpers.cache import metadata_cache
from helpers.http import source_footer, url_capture
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

        Quick reference — use these codes directly with query_ine_data without
        calling get_ine_operations first:

        Prices / Economy:
          IPC      — Índice de Precios de Consumo (CPI, monthly)
          IPCA     — IPCA armonizado (HICP, monthly EU-comparable)
          CNE / CN — Contabilidad Nacional de España (GDP, quarterly & annual)
          CNTR     — Contabilidad Nacional Trimestral (flash GDP estimates)

        Labour / Employment:
          EPA      — Encuesta de Población Activa (LFS, quarterly unemployment)
          ETCL     — Encuesta Trimestral de Coste Laboral (labour cost, quarterly)
          EACL     — Encuesta Anual de Coste Laboral (annual labour cost)
          EAES     — Encuesta Anual de Estructura Salarial (wage structure, salarios por sector)
          EAES:Q   — Encuesta Cuatrienal de Estructura Salarial (4-yearly detailed wage survey)

        Population / Demographics:
          DPOP     — Cifras Oficiales de Población / Revisión del Padrón Municipal (annual)
          MNPN     — MNP Estadística de Nacimientos (births)
          MNPD     — MNP Estadística de Defunciones (deaths)
          MNPM     — MNP Estadística de Matrimonios (marriages)
          EM       — Estadística de Migraciones (immigration/emigration flows; search "migraciones" not "inmigración")
          EMCR     — Estadística de Migraciones y Cambios de Residencia

        Housing / Prices:
          IPV      — Índice de Precios de la Vivienda (House Price Index, quarterly)
          IPVA     — Índice de Precios de Vivienda en Alquiler (rental price index)
          HPT      — Estadística de Hipotecas (mortgages, monthly)
          ETDP     — Estadística de Transmisión de Derechos de la Propiedad (property sales)

        Health / Social:
          ECV      — Encuesta de Condiciones de Vida (poverty & living standards, annual)
          EPF      — Encuesta de Presupuestos Familiares (household budgets, annual)
          IMCV     — Indicador Multidimensional de Calidad de Vida

        Business:
          ICNE     — Índice de Cifra de Negocios Empresarial
          DIR      — Explotación Estadística del Directorio Central de Empresas (annual)

        NOTE: CIS (Centro de Investigaciones Sociológicas) surveys are NOT INE operations
        and are not available via this tool. Use search_datasets(query="CIS barómetro")
        to find CIS microdata files on datos.gob.es.

        Args:
            search: Optional keyword filter applied to operation names and codes.
                    Use short keywords (e.g. "nacimientos", "IPC") not full sentences.
                    For wages/salaries use "salarial" not "salario" (INE uses "Salarial").
            page: Page number (default: 1, 50 results per page).
        """
        _urls: list[str] = []
        url_capture.set(_urls)
        try:
            ops = await metadata_cache.get_ine_operations()
        except Exception as e:  # noqa: BLE001
            return f"Error fetching INE operations: {e}"

        if search:
            search_lower = search.lower()
            ops = [
                op
                for op in ops
                if search_lower in (op.get("Nombre") or "").lower()
                or search_lower in (op.get("Codigo") or "").lower()
            ]

        if not ops:
            msg = "No INE operations found" + (
                f" matching '{search}'" if search else ""
            )
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
            + (f" matching '{search}'" if search else "")
            + ":\n",
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
        content_parts.append(source_footer(_urls))
        return "\n".join(content_parts)
