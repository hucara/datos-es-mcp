from mcp.server.fastmcp import FastMCP

from helpers import ministerios_client
from helpers.http import source_footer, url_capture
from helpers.logging import log_tool

_MINISTERIO = "trafico"
_STAT_TYPES = ministerios_client.list_stat_types(_MINISTERIO)
_STAT_TYPES_HELP = ", ".join(f'"{s}"' for s in _STAT_TYPES)


def _format_results(result: dict) -> str:
    return ministerios_client.format_results(
        result, "Dirección General de Tráfico (DGT)"
    )


def register_get_traffic_stats_tool(mcp: FastMCP) -> None:
    @mcp.tool()
    @log_tool
    async def get_traffic_stats(
        stat_type: str = "accidentes",
        period: str | None = None,
        custom_query: str | None = None,
        page: int = 1,
    ) -> str:
        """
        Retrieve Spanish road traffic and vehicle statistics from the Dirección
        General de Tráfico (DGT).

        Useful for verifying claims about road fatalities, accident rates,
        electric vehicle adoption, and driving licence data.

        Args:
            stat_type: Type of traffic statistic. Options:
                       "accidentes"       — road accident frequency, location, cause
                       "victimas"         — fatalities and injuries by road type and vehicle
                       "parque_vehiculos" — vehicle fleet by type, fuel and province
                       "matriculaciones"  — new vehicle registrations (EV vs ICE)
                       "carnet"           — driving licences issued and holders
                       "alcoholemia"      — drink/drug-driving controls and positive rates
                       "velocidad"        — speed camera controls and excess-speed rates
            period: Optional year or range to narrow results (e.g. "2023", "2020-2022").
            custom_query: Free-text query override (bypasses stat_type preset).
            page: Page number for paginated results.

        Data sources:
          - datos.gob.es (publisher: direccion-general-de-trafico)
          - DGT statistics: https://www.dgt.es/inicio/estadisticas-e-indicadores/
          - For EU road safety comparisons use get_eurostat_data (tran_sf_* datasets)
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
            return f"Error fetching traffic stats: {e}"
