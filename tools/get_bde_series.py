from mcp.server.fastmcp import FastMCP

from helpers import bde_client
from helpers.http import source_footer, url_capture
from helpers.logging import log_tool

# Curated reference for common BdE series codes
# Codes verified via the BdE CSV downloads (ti_1_1.csv, ti_1_7.csv, be2001.csv)
# and the BIEST browser at https://app.bde.es/bie_www/?Idioma=en
_COMMON_SERIES = """
Common Banco de España series codes:
  ECB monetary policy rates (daily, use time_range="12M" or "36M"):
    D_DTFK09A0  — ECB main refinancing rate
    D_DNBCEA72  — ECB marginal lending facility rate
    D_DNBCEB72  — ECB deposit facility rate
  EURIBOR (daily, use time_range="12M" or "36M"):
    D_DNBAC172  — 1-month EURIBOR
    D_DNBAD172  — 3-month EURIBOR
    D_DNBAE172  — 6-month EURIBOR
    D_DNBAF172  — 12-month EURIBOR
    D_DNBAA572  — €STR overnight rate
  Exchange rates (monthly, use time_range="60M" or "MAX"):
    D_1PFJ1001  — EUR/USD (US dollars per euro, monthly mean)
    D_1PFJ1004  — EUR/GBP (pounds per euro, monthly mean)
    D_1PFJ1017  — EUR/JPY (yen per euro, monthly mean)
  Find more series: download CSV files from
    https://www.bde.es/webbe/es/estadisticas/compartido/datos/csv/
    (e.g. ti_1_1.csv = ECB rates, ti_1_7.csv = EURIBOR, be2001.csv = FX rates)
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
                          (e.g. "D_DNBCEB72" or "D_DTFK09A0,D_DNBAD172").
                          Use '#' in codes where needed (encode as %23 internally).
            time_range: Period of data to retrieve. MUST match the series frequency:
                        - "12M"  — last 12 months (use for daily series D_DNBC...)
                        - "36M"  — last 36 months (use for daily series)
                        - "30M"  — last 30 months (use for monthly/quarterly series)
                        - "60M"  — last 60 months (default, monthly/quarterly)
                        - "MAX"  — all available history
                        - "2024" — data for a specific year
                        Mismatched ranges return 412 errors. Use latest_only=True
                        first to check frequency before requesting history.
            latest_only: If True, return only the most recent value per series
                         instead of full history. Use to verify series exist and
                         to check their frequency (codFrecuencia field).

        Common series codes:
          D_DNBCEB72  — ECB deposit facility rate (daily, use time_range="36M")
          D_DTFK09A0  — ECB main refinancing rate (daily, use time_range="36M")
          D_DNBAF172  — 12-month EURIBOR (daily, use time_range="12M")
          D_DNBAD172  — 3-month EURIBOR (daily, use time_range="12M")
          D_1PFJ1001  — EUR/USD exchange rate (monthly, use time_range="60M")
        """
        codes = [c.strip() for c in series_codes.split(",") if c.strip()]
        if not codes:
            return "Error: Provide at least one series code.\n" + _COMMON_SERIES

        _urls: list[str] = []
        url_capture.set(_urls)

        try:
            if latest_only:
                data = await bde_client.get_latest_data(series_codes=codes)
                if not data:
                    return (
                        f"No data found for series: {', '.join(codes)}.\n"
                        "Check the series codes are valid.\n" + _COMMON_SERIES
                    )

                content_parts = [
                    f"Banco de España — Latest values for {len(data)} series:\n"
                ]
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
                content_parts.append(source_footer(_urls))
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
                    desc = (
                        s.get("descripcion")
                        or s.get("descripcionCorta")
                        or s.get("serie")
                        or "Unknown"
                    )
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
                            content_parts.append(
                                f"    ... ({len(dates) - 20} earlier observations)"
                            )
                    content_parts.append("")

                content_parts.append(source_footer(_urls))
                return "\n".join(content_parts)

        except Exception as e:  # noqa: BLE001
            return f"Error fetching Banco de España series: {e}\n" + _COMMON_SERIES
