from mcp.server.fastmcp import FastMCP

from helpers import ministerios_client
from helpers.http import source_footer, url_capture
from helpers.logging import log_tool

_MINISTERIO = "seguridad_social"
_STAT_TYPES = ministerios_client.list_stat_types(_MINISTERIO)
_STAT_TYPES_HELP = ", ".join(f'"{s}"' for s in _STAT_TYPES)


def _format_results(result: dict) -> str:
    return ministerios_client.format_results(
        result, "Ministerio de Inclusión, Seguridad Social y Migraciones (INSS)"
    )


def register_get_social_security_stats_tool(mcp: FastMCP) -> None:
    @mcp.tool()
    @log_tool
    async def get_social_security_stats(
        stat_type: str = "pensiones",
        period: str | None = None,
        custom_query: str | None = None,
        page: int = 1,
    ) -> str:
        """
        Retrieve Spanish social security statistics from the Ministerio de Inclusión,
        Seguridad Social y Migraciones and the INSS.

        Useful for verifying claims about pension sustainability, contributor-to-pensioner
        ratios, average pension amounts, social security contributor counts, and sick
        leave or disability figures.

        Args:
            stat_type: Type of social security statistic. Options:
                       "pensiones"              — pension count, average amount, by type
                       "cotizantes"             — SS contributors by regime, sector, province
                       "ratio_sostenibilidad"   — contributor-to-pensioner ratio over time
                       "prestaciones_desempleo" — contributory and assistance unemployment
                       "incapacidad"            — sick leave and permanent disability stats
                       "accidentes_laborales"   — occupational accidents and diseases
                       "inmigracion"            — foreign national SS contributors
            period: Optional year or range to narrow results (e.g. "2023", "2020-2022").
            custom_query: Free-text query override (bypasses stat_type preset).
            page: Page number for paginated results.

        Data sources:
          - datos.gob.es (publisher: ministerio-de-inclusion-seguridad-social-y-migraciones)
          - INSS statistics: https://www.seg-social.es/wps/portal/wss/internet/EstadisticasPresupuestosEstudios
          - For unemployment benefits also use get_employment_stats (SEPE)
          - For EU pension comparisons use get_eurostat_data (spr_exp_pens, spr_exp_sum)
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
            return f"Error fetching social security stats: {e}"
