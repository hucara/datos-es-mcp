from mcp.server.fastmcp import FastMCP

from helpers import ministerios_client
from helpers.http import source_footer, url_capture
from helpers.logging import log_tool

_MINISTERIO = "sanidad"
_STAT_TYPES = ministerios_client.list_stat_types(_MINISTERIO)
_STAT_TYPES_HELP = ", ".join(f'"{s}"' for s in _STAT_TYPES)


def _format_results(result: dict) -> str:
    return ministerios_client.format_results(result, "Ministerio de Sanidad / SNS")


def register_get_health_stats_tool(mcp: FastMCP) -> None:
    @mcp.tool()
    @log_tool
    async def get_health_stats(
        stat_type: str = "gasto_sanitario",
        period: str | None = None,
        custom_query: str | None = None,
        page: int = 1,
    ) -> str:
        """
        Retrieve Spanish public health statistics from the Ministerio de Sanidad and
        the Sistema Nacional de Salud (SNS).

        Useful for verifying claims about healthcare spending, waiting lists,
        hospital capacity, health workforce, vaccination coverage, and mortality.

        Args:
            stat_type: Type of health statistic to retrieve. Options:
                       "gasto_sanitario"  — public health expenditure by CCAA
                       "camas_hospitalarias" — hospital beds and facility capacity
                       "profesionales"    — doctors, nurses, specialists per 1,000
                       "listas_espera"    — surgical and diagnostic waiting lists
                       "mortalidad"       — mortality rates and causes of death
                       "enfermedades"     — chronic disease prevalence, hospitalisations
                       "salud_mental"     — mental health and psychiatric care stats
                       "vacunacion"       — vaccination coverage by age group and CCAA
                       "encuesta_salud"   — National Health Survey (ENSE) lifestyle data
            period: Optional year or range to narrow results (e.g. "2023", "2020-2022").
            custom_query: Free-text query override (bypasses stat_type preset).
            page: Page number for paginated results.

        Data sources:
          - datos.gob.es (publisher: ministerio-de-sanidad)
          - SNS statistics portal: https://www.sanidad.gob.es/estadEstudios/
          - For EU comparisons use get_eurostat_data (HLTH_* datasets)
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
            return f"Error fetching health stats: {e}"
