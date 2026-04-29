from mcp.server.fastmcp import FastMCP

from helpers import ministerios_client
from helpers.http import source_footer, url_capture
from helpers.logging import log_tool

_MINISTERIO = "vivienda"
_STAT_TYPES = ministerios_client.list_stat_types(_MINISTERIO)
_STAT_TYPES_HELP = ", ".join(f'"{s}"' for s in _STAT_TYPES)


def _format_results(result: dict) -> str:
    return ministerios_client.format_results(
        result, "Ministerio de Vivienda, Agenda Urbana y Territorio"
    )


def register_get_housing_stats_tool(mcp: FastMCP) -> None:
    @mcp.tool()
    @log_tool
    async def get_housing_stats(
        stat_type: str = "precios_vivienda",
        period: str | None = None,
        custom_query: str | None = None,
        page: int = 1,
    ) -> str:
        """
        Retrieve Spanish housing market statistics from the Ministerio de Vivienda
        and related agencies.

        Useful for verifying claims about house prices, rental costs, mortgage
        activity, new construction, housing stock and evictions.

        Args:
            stat_type: Type of housing statistic. Options:
                       "precios_vivienda"        — house price index (IPV), transactions
                       "alquileres"              — rental prices and market trends
                       "hipotecas"               — new mortgages, amounts, interest rates
                       "construccion"            — building permits, new housing starts
                       "parque_viviendas"        — housing stock (primary/secondary/vacant)
                       "vivienda_protegida"      — social / protected housing
                       "ejecuciones_hipotecarias"— foreclosures and evictions
            period: Optional year or range to narrow results (e.g. "2023", "2020-2022").
            custom_query: Free-text query override (bypasses stat_type preset).
            page: Page number for paginated results.

        Data sources:
          - datos.gob.es (publisher: ministerio-de-vivienda)
          - Ministerio de Vivienda: https://www.mivau.gob.es/vivienda/estadisticas-y-publicaciones
          - INE publishes the official IPV (Índice de Precios de Vivienda):
            use get_ine_operations(search="precio vivienda") then query_ine_data
          - For EU comparisons use get_eurostat_data with dataset "prc_hpi_a" or "prc_hpi_q"
        """
        _urls: list[str] = []
        url_capture.set(_urls)
        try:
            result = await ministerios_client.search_ministerio_stats(
                ministerio=_MINISTERIO,
                stat_type=stat_type if not custom_query else None,
                custom_query=custom_query,
                period=period,
                page=page,
            )
            return _format_results(result) + source_footer(_urls)
        except ValueError as e:
            return (
                f"Invalid stat_type '{stat_type}'. "
                f"Valid options: {_STAT_TYPES_HELP}.\n"
                f"Error: {e}"
            )
        except Exception as e:  # noqa: BLE001
            return f"Error fetching housing stats: {e}"
