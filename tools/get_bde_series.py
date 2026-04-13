from mcp.server.fastmcp import FastMCP

from helpers import bde_client
from helpers.logging import log_tool

# Curated reference for common BdE series codes
_COMMON_SERIES = """
Common Banco de España series codes:
  Interest rates:
    TI_1_2_1   — ECB deposit facility rate (monthly)
    TI_1_1_1   — ECB main refinancing rate (monthly)
    TI_1_3_1   — ECB marginal lending facility rate (monthly)
    TI_2_1_1   — EURIBOR 1 month (daily)
    TI_2_3_1   — EURIBOR 3 months (daily)
    TI_2_12_1  — EURIBOR 12 months (daily)
  Exchange rates:
    TC_1_1_1   — EUR/USD exchange rate (daily)
    TC_1_2_1   — EUR/GBP exchange rate (daily)
    TC_1_3_1   — EUR/JPY exchange rate (daily)
  Credit & banking:
    BE_1_1_1   — Credit to private sector (monthly)
    BE_1_2_1   — Deposits of private sector (monthly)
  Find more series at: https://www.bde.es/webbe/en/estadisticas/
"""


def register_get_bde_series_tool(mcp: FastMCP) -> None:
    @mcp.tool()
    @log_tool
    async def get_bde_series(
        series_codes: str,
        time_range: str = "60M",
        latest_only: bool = False,
    ) -> str:
        """
        Retrieve financial and economic time series from Banco de España.

        Covers interest rates (ECB rates, EURIBOR), exchange rates, credit,
        banking statistics, balance of payments, and monetary aggregates.

        Args:
            series_codes: Comma-separated BdE series codes
                          (e.g. "TI_1_2_1" or "TI_1_1_1,TC_1_1_1").
                          Use '#' in codes where needed (e.g. "BE_1_1_1").
            time_range: Period of data to retrieve:
                        - "30M"  — last 30 months (or 30 quarters/years)
                        - "60M"  — last 60 months (default)
                        - "MAX"  — all available history
                        - "3M"   — last 3 months (for daily series)
                        - "2024" — data for a specific year
            latest_only: If True, return only the most recent value per series
                         instead of full history.

        Common series codes:
          TI_1_2_1  — ECB deposit facility rate
          TI_1_1_1  — ECB main refinancing rate
          TI_2_12_1 — EURIBOR 12 months
          TC_1_1_1  — EUR/USD exchange rate
        """
        codes = [c.strip() for c in series_codes.split(",") if c.strip()]
        if not codes:
            return "Error: Provide at least one series code.\n" + _COMMON_SERIES

        try:
            if latest_only:
                data = await bde_client.get_latest_data(series_codes=codes)
                if not data:
                    return (
                        f"No data found for series: {', '.join(codes)}.\n"
                        "Check the series codes are valid.\n" + _COMMON_SERIES
                    )

                content_parts = [f"Banco de España — Latest values for {len(data)} series:\n"]
                for s in data:
                    desc = s.get("descripcionCorta") or s.get("serie") or "Unknown"
                    code = s.get("serie") or "?"
                    value = s.get("valor")
                    symbol = s.get("simbolo") or ""
                    date = s.get("fechaValor") or "?"
                    freq = s.get("codFrecuencia") or ""
                    trend = s.get("tendencia") or ""

                    content_parts.append(f"Series: {desc}")
                    content_parts.append(f"  Code: {code}")
                    content_parts.append(f"  Latest value: {value} {symbol}".strip())
                    content_parts.append(f"  Date: {date}")
                    if freq:
                        content_parts.append(f"  Frequency: {freq}")
                    if trend:
                        content_parts.append(f"  Trend: {trend}")
                    content_parts.append("")
                return "\n".join(content_parts)

            else:
                data = await bde_client.get_series_history(
                    series_codes=codes, time_range=time_range
                )
                if not data:
                    return (
                        f"No data found for series: {', '.join(codes)}.\n"
                        "Check the series codes are valid.\n" + _COMMON_SERIES
                    )

                content_parts = [
                    f"Banco de España — Historical data ({time_range}) for {len(data)} series:\n"
                ]
                for s in data:
                    desc = s.get("descripcion") or s.get("descripcionCorta") or s.get("serie") or "Unknown"
                    code = s.get("serie") or "?"
                    symbol = s.get("simbolo") or ""
                    freq = s.get("codFrecuencia") or ""
                    decimals = s.get("decimales")
                    dates = s.get("fechas") or []
                    values = s.get("valores") or []
                    start = s.get("fechaInicio") or ""
                    end = s.get("fechaFin") or ""

                    content_parts.append(f"Series: {desc}")
                    content_parts.append(f"  Code: {code}")
                    if symbol:
                        content_parts.append(f"  Unit: {symbol}")
                    if freq:
                        content_parts.append(f"  Frequency: {freq}")
                    if start or end:
                        content_parts.append(f"  Available: {start} to {end}")
                    if decimals is not None:
                        content_parts.append(f"  Decimal places: {decimals}")

                    if dates and values:
                        content_parts.append(f"  Data ({len(dates)} observations):")
                        # Show last 20 points
                        pairs = list(zip(dates, values))[-20:]
                        for d, v in pairs:
                            content_parts.append(f"    {d}: {v}")
                        if len(dates) > 20:
                            content_parts.append(f"    ... ({len(dates) - 20} earlier observations)")
                    content_parts.append("")

                return "\n".join(content_parts)

        except Exception as e:  # noqa: BLE001
            return f"Error fetching Banco de España series: {e}\n" + _COMMON_SERIES
