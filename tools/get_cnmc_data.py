from mcp.server.fastmcp import FastMCP

from helpers import cnmc_client
from helpers.logging import log_tool

_SECTORS = {
    "electricity": "Electricity market (generation, consumption, prices, capacity)",
    "gas": "Natural gas market (supply, distribution, prices)",
    "telecom": "Telecommunications (broadband, mobile, internet penetration)",
    "postal": "Postal services (volumes, operators, quality)",
    "transport": "Transport infrastructure (rail, airports)",
    "audiovisual": "Audiovisual media (TV, radio audiences and operators)",
    "competition": "Competition enforcement (mergers, antitrust, sanctions)",
}


def register_get_cnmc_data_tool(mcp: FastMCP) -> None:
    @mcp.tool()
    @log_tool
    async def get_cnmc_data(
        query: str = "",
        sector: str | None = None,
        page: int = 1,
    ) -> str:
        """
        Search datasets from CNMC (Spain's National Competition and Markets Authority).

        CNMC Data covers regulated markets: electricity, natural gas,
        telecommunications, postal services, transport, and audiovisual.

        Args:
            query: Optional keywords to narrow the search
                   (e.g. "precio electricidad", "cobertura banda ancha", "tarifas gas").
            sector: Market sector to filter by:
                    - "electricity"  — electricity market statistics
                    - "gas"          — natural gas market data
                    - "telecom"      — broadband, mobile, internet coverage stats
                    - "postal"       — postal services data
                    - "transport"    — regulated transport infrastructure
                    - "audiovisual"  — TV/radio market statistics
                    - "competition"  — competition enforcement decisions
                    Leave empty to search across all sectors.
            page: Page number for results.
        """
        if sector and sector not in _SECTORS:
            valid = ", ".join(f'"{k}"' for k in _SECTORS)
            return f"Invalid sector '{sector}'. Valid values: {valid}."

        search_query = query or (sector and _SECTORS[sector].split(" (")[0]) or "estadisticas mercados"

        try:
            result = await cnmc_client.search_datasets(
                query=search_query, sector=sector, page=page
            )
        except Exception as e:  # noqa: BLE001
            return f"Error accessing CNMC data: {e}"

        datasets = result.get("results", [])
        count = result.get("count", len(datasets))

        if not datasets:
            return (
                f"No CNMC datasets found"
                + (f" for sector='{sector}'" if sector else "")
                + (f" matching '{query}'" if query else "")
                + ".\nVisit https://data.cnmc.es for the full catalog."
            )

        sector_desc = _SECTORS.get(sector, "All sectors") if sector else "All sectors"
        content_parts = [
            f"CNMC Data — {sector_desc}",
            f"Found {count} dataset(s)"
            + (f" matching '{query}'" if query else "")
            + f" (page {page}):\n",
        ]

        for i, ds in enumerate(datasets, 1):
            title = ds.get("title") or "Unknown"
            ds_id = ds.get("id") or "?"
            desc = ds.get("description") or ""
            formats = ds.get("formats") or []
            modified = ds.get("last_modified") or ""

            content_parts.append(f"{i}. {title}")
            content_parts.append(f"   ID: {ds_id}")
            if desc:
                content_parts.append(f"   Description: {desc[:200]}...")
            if formats:
                content_parts.append(f"   Formats: {', '.join(formats[:5])}")
            if modified:
                content_parts.append(f"   Last updated: {str(modified)[:10]}")
            content_parts.append(f"   URL: {ds.get('url')}")
            content_parts.append("")

        content_parts.append(
            "Full CNMC Data portal: https://data.cnmc.es/"
        )
        return "\n".join(content_parts)
