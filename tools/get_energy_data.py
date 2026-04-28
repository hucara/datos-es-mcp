from mcp.server.fastmcp import FastMCP

from helpers import redata_client
from helpers.http import source_footer, url_capture
from helpers.logging import log_tool

_DATA_TYPES = {
    "generation_mix": "Electricity generation mix by technology (renewable %)",
    "installed_capacity": "Installed generation capacity by technology (GW)",
    "balance": "Electrical balance (generation, imports, exports, demand)",
    "demand": "Electricity demand evolution",
    "market_prices": "Electricity market adjustment services costs",
}

_TIME_TRUNCS = ("hour", "day", "month", "year")


def _parse_included(data: dict) -> list[dict]:
    """Extract the 'included' list from a JSON:API response."""
    return data.get("included") or []


def _format_series(items: list[dict], max_values: int = 12) -> list[str]:
    """Format a list of JSON:API technology/series items into readable lines."""
    lines = []
    for item in items:
        attrs = item.get("attributes") or {}
        title = attrs.get("title") or item.get("id") or "Unknown"
        item_type = attrs.get("type") or ""
        values = attrs.get("values") or []

        if not values:
            continue

        type_tag = f" [{item_type}]" if item_type else ""
        lines.append(f"\n  {title}{type_tag}:")

        shown = values[-max_values:] if len(values) > max_values else values
        for v in shown:
            dt = str(v.get("datetime") or v.get("date") or "?")[:10]
            val = v.get("value")
            pct = v.get("percentage")
            line = f"    {dt}: {val}"
            if val is not None:
                try:
                    line = f"    {dt}: {float(val):,.1f}"
                except (TypeError, ValueError):
                    pass
            if pct is not None:
                try:
                    line += f"  ({float(pct) * 100:.1f}%)"
                except (TypeError, ValueError):
                    line += f"  ({pct})"
            lines.append(line)

        if len(values) > max_values:
            lines.append(f"    ... ({len(values) - max_values} earlier periods)")
    return lines


def register_get_energy_data_tool(mcp: FastMCP) -> None:
    @mcp.tool()
    @log_tool
    async def get_energy_data(
        data_type: str = "generation_mix",
        start_date: str | None = None,
        end_date: str | None = None,
        time_trunc: str = "month",
    ) -> str:
        """
        Retrieve Spanish electricity system data from Red Eléctrica (REData API).

        No API key required. Covers generation mix, installed renewable capacity,
        electrical balance, demand evolution, and market prices.

        Useful for verifying claims about:
        - Renewable energy share and growth (potencia renovable instalada, cobertura)
        - Natural gas as marginal price setter (% of hours)
        - Electricity demand trends
        - Energy balance (imports/exports)
        - Cost of technical restrictions

        Args:
            data_type: Type of energy data to retrieve:
                       - "generation_mix"    — generation by technology with renewable %
                         (e.g. wind, solar, hydro, nuclear, gas, coal)
                       - "installed_capacity" — installed capacity per technology in GW
                         (use time_trunc="year" to see capacity growth over years)
                       - "balance"           — electrical balance: total generation,
                         imports, exports, and demand
                       - "demand"            — electricity demand variation and trends
                       - "market_prices"     — adjustment services market costs
            start_date: Start of period in format "YYYY-MM-DDTHH:MM"
                        (e.g. "2019-01-01T00:00"). Defaults to 2 years ago.
            end_date: End of period in format "YYYY-MM-DDTHH:MM"
                      (e.g. "2025-12-31T23:59"). Defaults to today.
            time_trunc: Time aggregation level:
                        - "hour"  — hourly values
                        - "day"   — daily values
                        - "month" — monthly values (default)
                        - "year"  — annual values (best for multi-year comparisons)

        Examples for claim verification:
          - Renewable capacity growth 2019→2026:
            get_energy_data("installed_capacity", "2019-01-01T00:00", "2026-12-31T23:59", "year")
          - Gas as price setter (generation mix by year):
            get_energy_data("generation_mix", "2019-01-01T00:00", "2025-12-31T23:59", "year")
          - Recent electricity balance:
            get_energy_data("balance", "2024-01-01T00:00", "2025-12-31T23:59", "month")
        """
        if data_type not in _DATA_TYPES:
            valid = ", ".join(f'"{k}"' for k in _DATA_TYPES)
            return f"Invalid data_type '{data_type}'. Valid values: {valid}."

        if time_trunc not in _TIME_TRUNCS:
            return f"Invalid time_trunc '{time_trunc}'. Valid values: {', '.join(_TIME_TRUNCS)}."

        _urls: list[str] = []
        url_capture.set(_urls)

        # Set default date range
        if not start_date or not end_date:
            default_start, default_end = redata_client._default_date_range(
                years_back=5 if time_trunc == "year" else 2
            )
            start_date = start_date or default_start
            end_date = end_date or default_end

        try:
            if data_type == "generation_mix":
                raw = await redata_client.get_generation_mix(
                    start_date, end_date, time_trunc
                )
            elif data_type == "installed_capacity":
                raw = await redata_client.get_installed_capacity(
                    start_date, end_date, time_trunc
                )
            elif data_type == "balance":
                raw = await redata_client.get_electricity_balance(
                    start_date, end_date, time_trunc
                )
            elif data_type == "demand":
                raw = await redata_client.get_demand(start_date, end_date, time_trunc)
            elif data_type == "market_prices":
                raw = await redata_client.get_market_prices(
                    start_date, end_date, time_trunc
                )
            else:
                return f"Unknown data_type: {data_type}"
        except Exception as e:  # noqa: BLE001
            return f"Error fetching REData energy data: {e}"

        top_data = raw.get("data") or {}
        top_attrs = (
            top_data.get("attributes") or {} if isinstance(top_data, dict) else {}
        )
        title = top_attrs.get("title") or _DATA_TYPES.get(data_type, data_type)
        last_update = top_attrs.get("last-update") or ""

        included = _parse_included(raw)

        if not included:
            return (
                f"No data returned for {data_type} between {start_date} and {end_date}.\n"
                "Try adjusting the date range or time_trunc."
            )

        content_parts = [
            f"Red Eléctrica — {title}",
            f"Period: {start_date[:10]} to {end_date[:10]} (by {time_trunc})",
        ]
        if last_update:
            content_parts.append(f"Last updated: {str(last_update)[:16]}")
        content_parts.append(f"Technologies/series: {len(included)}\n")

        # Separate renewables from non-renewables for generation_mix
        if data_type in ("generation_mix", "installed_capacity"):
            renewables = [
                i
                for i in included
                if (i.get("attributes") or {}).get("type") == "Renovable"
            ]
            non_renewables = [
                i
                for i in included
                if (i.get("attributes") or {}).get("type") == "No-Renovable"
            ]
            other = [
                i
                for i in included
                if (i.get("attributes") or {}).get("type")
                not in ("Renovable", "No-Renovable")
            ]

            if renewables:
                unit = "GW" if data_type == "installed_capacity" else "MWh"
                content_parts.append(f"Renewable sources ({unit}):")
                content_parts.extend(_format_series(renewables))

            if non_renewables:
                content_parts.append(f"\nNon-renewable sources ({unit}):")
                content_parts.extend(_format_series(non_renewables))

            if other:
                content_parts.append("\nOther:")
                content_parts.extend(_format_series(other))
        else:
            content_parts.extend(_format_series(included))

        content_parts.append("\nData source: Red Eléctrica (REData) — apidatos.ree.es")
        content_parts.append(source_footer(_urls))
        return "\n".join(content_parts)
