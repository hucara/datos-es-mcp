from mcp.server.fastmcp import FastMCP

from helpers import aeat_client
from helpers.logging import log_tool

_STAT_TYPES = aeat_client._KNOWN_DATASETS

_TYPE_HELP = "\n".join(
    f'  "{k}" — {v["description"]}'
    for k, v in _STAT_TYPES.items()
)

# Contextual guidance mapped to common claim categories
_CLAIM_GUIDANCE = {
    "irpf": (
        "For IRPF threshold claims (e.g. 'minimum taxable income was X in year Y'), "
        "look for files named 'Estadística IRPF' and filter by year. "
        "The 'mínimo exento' (tax-free minimum) and tramos (brackets) are in the "
        "methodology notes and annual statistics tables. "
        "Also useful: INE's 'Encuesta de Condiciones de Vida' for after-tax income data."
    ),
    "iva": (
        "For VAT/IVA claims (e.g. franchise del IVA, rebaja de IVA), look for "
        "'Estadística del IVA' files. The franchise threshold and reduced rates "
        "are in the BOE (Real Decreto-Ley). Cross-reference with CNMC data on "
        "price transmission to consumers."
    ),
    "recaudacion": (
        "For tax revenue claims (e.g. 'recaudación total', '% del PIB'), "
        "the annual Informe de Recaudación Tributaria is the authoritative source. "
        "Cross-reference with Eurostat 'gov_10a_main' for EU comparison."
    ),
    "sociedades": (
        "For corporate tax claims (e.g. 'tipo efectivo impuesto sociedades', "
        "record company profits), look for 'Estadística del IS'. "
        "CaixaBank and IBEX35 profits are also in CNMV annual reports."
    ),
}


def register_get_aeat_stats_tool(mcp: FastMCP) -> None:
    @mcp.tool()
    @log_tool
    async def get_aeat_stats(
        stat_type: str = "anuario_estadistico",
        query: str | None = None,
        page: int = 1,
    ) -> str:
        """
        Search AEAT (Agencia Tributaria) fiscal statistics datasets.

        AEAT publishes annual statistics on income tax (IRPF), VAT (IVA),
        corporate tax (Sociedades), and total tax revenue. These are critical
        for verifying fiscal and tax-threshold claims.

        Note: AEAT does not have a query API. This tool surfaces downloadable
        datasets (CSV/Excel) from datos.gob.es, plus contextual guidance on
        which source to use for specific claim types.

        Args:
            stat_type: Type of fiscal statistics:
                       - "anuario_estadistico" — full statistical yearbook
                         (IRPF, IVA, Patrimonio, Sociedades, labor market by year)
                       - "recaudacion"  — annual tax revenue totals by tax type
                       - "irpf"         — income tax statistics and bracket data
                       - "iva"          — VAT statistics (sales, exemptions, refunds)
                       - "sociedades"   — corporate tax statistics and effective rates
            query: Optional custom search override.
            page: Page number for results.

        For verifying specific claims:
          - IRPF minimum taxable threshold → stat_type="irpf"
          - IVA franchise exemption → stat_type="iva" + search BOE
          - CaixaBank record profit → stat_type="sociedades" + CNMV annual reports
          - Tax revenue as % of GDP → stat_type="recaudacion" + Eurostat gov_10a_main
        """
        if stat_type not in _STAT_TYPES:
            valid = ", ".join(f'"{k}"' for k in _STAT_TYPES)
            return f"Invalid stat_type '{stat_type}'. Valid values: {valid}."

        try:
            result = await aeat_client.search_aeat_datasets(
                stat_type=stat_type,
                custom_query=query,
                page=page,
            )
        except Exception as e:  # noqa: BLE001
            return f"Error searching AEAT datasets: {e}"

        datasets = result.get("results", [])
        # Handle single dataset result (from package_show)
        if isinstance(datasets, dict):
            datasets = [datasets]
        count = result.get("count", len(datasets))

        stat_desc = _STAT_TYPES[stat_type]["description"]
        content_parts = [
            f"AEAT Fiscal Statistics — {stat_desc}",
            f"Found {count} dataset(s) (page {page}):\n",
        ]

        for i, ds in enumerate(datasets if isinstance(datasets, list) else [datasets], 1):
            if not isinstance(ds, dict):
                continue
            title = ds.get("title") or "Unknown"
            ds_id = ds.get("id") or "?"
            ds_name = ds.get("name") or ds_id
            notes = (ds.get("notes") or "")[:300]
            resources = ds.get("resources") or []
            modified = ds.get("metadata_modified") or ""

            content_parts.append(f"{i}. {title}")
            content_parts.append(f"   ID: {ds_id}")
            if notes:
                content_parts.append(f"   Description: {notes}...")
            content_parts.append(f"   Resources: {len(resources)} file(s)")
            if modified:
                content_parts.append(f"   Last updated: {str(modified)[:10]}")

            # Show downloadable files
            for r in resources[:5]:
                fmt = (r.get("format") or "?").upper()
                name = r.get("name") or r.get("description") or "File"
                url = r.get("url") or ""
                if url:
                    content_parts.append(f"   [{fmt}] {name}: {url}")

            content_parts.append(
                f"   Portal: https://datos.gob.es/es/catalogo/{ds_name}"
            )
            content_parts.append("")

        # Add contextual guidance
        guidance = _CLAIM_GUIDANCE.get(stat_type)
        if guidance:
            content_parts.append(f"Claim verification guidance:\n{guidance}")
            content_parts.append("")

        content_parts.append(
            "Direct access: https://sede.agenciatributaria.gob.es/Sede/estadisticas.html\n"
            "Interactive yearbook: https://sede.agenciatributaria.gob.es/Sede/estadisticas/anuario-estadistico.html"
        )
        return "\n".join(content_parts)
