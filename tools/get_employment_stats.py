from mcp.server.fastmcp import FastMCP

from helpers import sepe_client
from helpers.http import source_footer, url_capture
from helpers.logging import log_tool

_STAT_TYPES = {
    "paro": "Registered unemployment (paro registrado)",
    "contratos": "Employment contracts (contratos de trabajo)",
    "demandantes": "Job seekers (demandantes de empleo)",
    "prestaciones": "Unemployment benefits (prestaciones por desempleo)",
    "movilidad": "Labor mobility statistics",
}


def register_get_employment_stats_tool(mcp: FastMCP) -> None:
    @mcp.tool()
    @log_tool
    async def get_employment_stats(
        stat_type: str = "paro",
        page: int = 1,
    ) -> str:
        """
        Find employment statistics datasets from SEPE (Spain's Public Employment Service).

        Returns datasets with registered unemployment, contracts, job seekers,
        and unemployment benefits — broken down by province, sector, age, and sex.

        Args:
            stat_type: Type of labor statistics to search for:
                       - "paro"         — registered unemployment by province/municipality
                       - "contratos"    — employment contracts by type, sector, province
                       - "demandantes"  — job seekers profiles and flows
                       - "prestaciones" — unemployment benefits recipients
                       - "movilidad"    — labor mobility and geographic flows
            page: Page number for results (default: 1).

        Workflow: get_employment_stats → list_dataset_resources → download CSV/XLSX file.
        For up-to-date national figures, use query_ine_data with operation_code="EPA"
        for the official Labour Force Survey.
        """
        if stat_type not in _STAT_TYPES:
            valid = ", ".join(f'"{k}"' for k in _STAT_TYPES)
            return f"Invalid stat_type '{stat_type}'. Valid values: {valid}."

        _urls: list[str] = []
        url_capture.set(_urls)
        try:
            result = await sepe_client.search_employment_datasets(
                stat_type=stat_type, page=page
            )
        except Exception as e:  # noqa: BLE001
            return f"Error searching SEPE employment datasets: {e}"

        datasets = result.get("results", [])
        count = result.get("count", len(datasets))

        if not datasets:
            return (
                f"No SEPE datasets found for '{stat_type}'.\n"
                "Try searching directly: search_datasets(query='SEPE paro registrado')"
            )

        stat_desc = _STAT_TYPES[stat_type]
        content_parts = [
            f"SEPE Employment Statistics — {stat_desc}",
            f"Found {count} dataset(s) (page {page}):\n",
        ]

        for i, ds in enumerate(datasets, 1):
            title = ds.get("title") or "Unknown"
            ds_id = ds.get("id") or "?"
            org = ds.get("organization") or ""
            modified = ds.get("metadata_modified") or ""
            notes = (ds.get("notes") or "")[:200]
            resources = ds.get("resources", [])
            fmt_list = list(
                {r.get("format", "").upper() for r in resources if r.get("format")}
            )

            content_parts.append(f"{i}. {title}")
            content_parts.append(f"   ID: {ds_id}")
            if org:
                content_parts.append(f"   Publisher: {org}")
            if notes:
                content_parts.append(f"   Description: {notes}...")
            if fmt_list:
                content_parts.append(f"   Formats: {', '.join(fmt_list[:5])}")
            content_parts.append(f"   Resources: {len(resources)}")
            if modified:
                content_parts.append(f"   Last updated: {str(modified)[:10]}")
            content_parts.append(
                f"   URL: https://datos.gob.es/es/catalogo/{ds.get('name', ds_id)}"
            )
            content_parts.append("")

        content_parts.append(
            "Tip: Use list_dataset_resources(dataset_id) to see downloadable files.\n"
            "For Labour Force Survey (EPA) figures, use: query_ine_data(operation_code='EPA')"
        )
        content_parts.append(source_footer(_urls))
        return "\n".join(content_parts)
