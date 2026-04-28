from mcp.server.fastmcp import FastMCP

from helpers import eurostat_client
from helpers.http import source_footer, url_capture
from helpers.logging import log_tool

_CATALOG = eurostat_client.DATASET_CATALOG

_TOPIC_HELP = "\n".join(f'  "{k}" — {v["description"]}' for k, v in _CATALOG.items())


def _format_records(
    records: list[dict],
    geo_codes: list[str],
    max_per_geo: int = 15,
) -> list[str]:
    """Format parsed JSON-stat records grouped by geography."""
    lines: list[str] = []

    # Group by geo
    by_geo: dict[str, list[dict]] = {}
    for r in records:
        g = r.get("geo") or r.get("GEO") or "?"
        by_geo.setdefault(g, []).append(r)

    # Show requested geos first
    ordered_geos = [g for g in geo_codes if g in by_geo]
    for g in by_geo:
        if g not in ordered_geos:
            ordered_geos.append(g)

    for geo in ordered_geos:
        geo_records = by_geo[geo]
        geo_label = (geo_records[0].get("geo_label") or geo) if geo_records else geo
        lines.append(f"\n  {geo_label} ({geo}):")

        # Sort by time
        sorted_recs = sorted(
            geo_records, key=lambda r: str(r.get("time") or r.get("TIME_PERIOD") or "")
        )
        shown = sorted_recs[-max_per_geo:]
        for r in shown:
            period = r.get("time") or r.get("TIME_PERIOD") or "?"
            val = r.get("value")
            try:
                val_fmt = f"{float(val):,.2f}"
            except (TypeError, ValueError):
                val_fmt = str(val)
            lines.append(f"    {period}: {val_fmt}")

        if len(sorted_recs) > max_per_geo:
            lines.append(f"    ... ({len(sorted_recs) - max_per_geo} earlier periods)")

    return lines


def register_get_eurostat_data_tool(mcp: FastMCP) -> None:
    @mcp.tool()
    @log_tool
    async def get_eurostat_data(
        topic: str,
        geo: str = "ES,EU27_2020",
        since_year: str | None = None,
        until_year: str | None = None,
        dataset_code: str | None = None,
        extra_filters: str | None = None,
    ) -> str:
        """
        Retrieve Eurostat statistical data for Spain and EU comparisons.

        Essential for verifying claims that compare Spain to European averages:
        GDP growth, inflation, unemployment, housing prices, renewable energy share,
        electricity prices, government debt, wages, and income inequality.

        Args:
            topic: Pre-configured topic shortcut. Available topics:
                   - "gdp_growth"                — Real GDP growth rate (%)
                   - "gdp_per_capita"            — Real GDP per capita growth (%)
                   - "inflation_hicp"            — HICP monthly inflation (%)
                   - "inflation_annual"          — HICP annual average index
                   - "unemployment"              — Annual unemployment rate (%)
                   - "employment_rate"           — Employment rate (%)
                   - "house_prices"              — House price index (2015=100)
                   - "renewable_share"           — Renewable energy share (%)
                   - "electricity_prices_households" — Household electricity prices
                   - "electricity_prices_industry"   — Industrial/SME electricity prices
                   - "government_debt"           — Government debt (% of GDP)
                   - "government_deficit"        — Government deficit/surplus (% of GDP)
                   - "wages"                     — Mean/median earnings
                   - "poverty_inequality"        — Gini coefficient
                   - "fossil_fuel_imports"       — Energy imports by product
                   Use "custom" with dataset_code= to query any Eurostat dataset.
            geo: Comma-separated geo codes to include.
                 Default: "ES,EU27_2020" (Spain + EU27 average).
                 Common codes: ES=Spain, EU27_2020=EU27, DE=Germany, FR=France,
                               IT=Italy, PT=Portugal, G7=G7 average.
            since_year: Start year filter (e.g. "2018").
            until_year: End year filter (e.g. "2025").
            dataset_code: Eurostat dataset code for custom queries (e.g. "nama_10_gdp").
                          Only used when topic="custom".
            extra_filters: Additional dimension filters as "key=value" pairs
                           separated by "&" (e.g. "unit=PC_GDP&sex=T").

        Data availability notes:
          - Most annual series lag ~1 year: 2026 queries may return no data; use 2025.
          - "wages" uses dataset earn_nt_net — requires no unit filter (uses currency=EUR).
          - "poverty_inequality" uses ilc_di12 (Gini) — no unit filter needed.
          - inflation_hicp is monthly; all others are annual unless noted.

        Examples for claim verification:
          - "Spain grew at double the EU average":
            get_eurostat_data("gdp_growth", "ES,EU27_2020", "2018", "2025")
          - "Housing 29% more expensive than in 2018":
            get_eurostat_data("house_prices", "ES", "2018", "2025")
          - "Inflation was 7.6% in Feb 2022":
            get_eurostat_data("inflation_hicp", "ES", "2022", "2022")
          - "Spain reduced fossil fuel dependence most in EU":
            get_eurostat_data("fossil_fuel_imports", "ES,EU27_2020,DE,FR,IT", "2019", "2025")
        """
        geo_list = [g.strip() for g in geo.split(",") if g.strip()]
        _urls: list[str] = []
        url_capture.set(_urls)

        # Resolve topic to dataset code
        if topic == "custom":
            if not dataset_code:
                return (
                    "For topic='custom', provide dataset_code= with a Eurostat dataset code.\n"
                    f"Available pre-configured topics:\n{_TOPIC_HELP}"
                )
            code = dataset_code
            description = f"Custom dataset: {dataset_code}"
            notes = ""
        elif topic in _CATALOG:
            entry = _CATALOG[topic]
            code = entry["code"]
            description = entry["description"]
            notes = entry.get("note", "")
        else:
            return (
                f"Unknown topic '{topic}'. Available topics:\n{_TOPIC_HELP}\n\n"
                f"Or use topic='custom' with dataset_code='<code>'."
            )

        # Parse extra_filters
        filters: dict[str, str] = {}
        if extra_filters:
            for part in extra_filters.split("&"):
                if "=" in part:
                    k, v = part.split("=", 1)
                    filters[k.strip()] = v.strip()

        # Apply default filters from catalog (unit + any extra_defaults)
        if topic in _CATALOG:
            entry = _CATALOG[topic]
            if "unit" in entry and "unit" not in filters:
                filters["unit"] = entry["unit"]
            for k, v in entry.get("extra_defaults", {}).items():
                if k not in filters:
                    filters[k] = v

        try:
            raw = await eurostat_client.get_dataset(
                dataset_code=code,
                geo=geo_list,
                since_period=since_year,
                until_period=until_year,
                filters=filters if filters else None,
            )
        except Exception as e:  # noqa: BLE001
            if "404" in str(e):
                return (
                    f"Dataset not found: '{code}' returned HTTP 404 — this code does not "
                    "exist in Eurostat.\n"
                    "Look up the correct code at https://ec.europa.eu/eurostat/databrowser/\n"
                    f"Available named topics: {', '.join(sorted(_CATALOG.keys()))}"
                )
            return (
                f"Error fetching Eurostat data for '{topic}' (dataset: {code}): {e}\n"
                "Tip: Some datasets require additional filters. "
                "Try extra_filters='unit=<value>' to narrow the query."
            )

        records = eurostat_client.parse_jsonstat(raw)

        if not records:
            # Try returning raw metadata
            label = raw.get("label") or ""
            dims = list((raw.get("dimension") or {}).keys())
            return (
                f"No data returned for '{topic}' with geo={geo}, "
                f"since={since_year}, until={until_year}.\n"
                f"Dataset: {code} — {label}\n"
                f"Dimensions available: {', '.join(dims)}\n"
                "Tip: Try adding extra_filters= to select a specific unit or category."
            )

        # Build output
        dataset_label = raw.get("label") or description
        updated = raw.get("updated") or ""

        content_parts = [
            f"Eurostat — {dataset_label}",
            f"Dataset: {code}",
            f"Geo: {', '.join(geo_list)} | Period: {since_year or 'all'}–{until_year or 'latest'}",
        ]
        if updated:
            content_parts.append(f"Last updated: {updated[:10]}")
        if notes:
            content_parts.append(f"Note: {notes}")

        content_parts.append(f"\nRecords: {len(records)}")
        content_parts.extend(_format_records(records, geo_list))
        content_parts.append("\nData source: Eurostat (ec.europa.eu/eurostat)")
        content_parts.append(source_footer(_urls))
        return "\n".join(content_parts)
