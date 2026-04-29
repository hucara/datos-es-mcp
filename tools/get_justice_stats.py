from mcp.server.fastmcp import FastMCP

from helpers import ministerios_client
from helpers.http import source_footer, url_capture
from helpers.logging import log_tool

_MINISTERIO = "justicia"
_STAT_TYPES = ministerios_client.list_stat_types(_MINISTERIO)
_STAT_TYPES_HELP = ", ".join(f'"{s}"' for s in _STAT_TYPES)


def _format_results(result: dict) -> str:
    return ministerios_client.format_results(
        result, "Ministerio de Justicia / Consejo General del Poder Judicial (CGPJ)"
    )


def register_get_justice_stats_tool(mcp: FastMCP) -> None:
    @mcp.tool()
    @log_tool
    async def get_justice_stats(
        stat_type: str = "criminalidad",
        period: str | None = None,
        custom_query: str | None = None,
        page: int = 1,
    ) -> str:
        """
        Retrieve Spanish criminal justice and judicial statistics from the Ministerio
        de Justicia and the Consejo General del Poder Judicial (CGPJ).

        Useful for verifying claims about crime rates, criminal convictions, prison
        population, court workload, gender-based violence, and corruption cases.

        Args:
            stat_type: Type of justice statistic. Options:
                       "criminalidad"     — crime statistics by type, province and year
                       "condenas"         — criminal convictions and sentences
                       "presos"           — prison population by regime, sex, nationality
                       "juzgados"         — court caseload (filed, resolved, pending)
                       "violencia_genero" — gender-based violence: complaints, convictions
                       "menores"          — juvenile justice statistics
                       "corrupcion"       — economic crime and corruption charges/trials
            period: Optional year or range to narrow results (e.g. "2023", "2020-2022").
            custom_query: Free-text query override (bypasses stat_type preset).
            page: Page number for paginated results.

        Data sources:
          - datos.gob.es (publishers: ministerio-de-justicia, consejo-general-del-poder-judicial)
          - CGPJ statistics: https://www.poderjudicial.es/cgpj/es/Temas/Estadistica-Judicial/
          - Ministerio del Interior also publishes crime stats:
            use search_datasets(query="estadistica criminalidad", publisher="ministerio del interior")
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
            return f"Error fetching justice stats: {e}"
