from mcp.server.fastmcp import FastMCP

from helpers import ministerios_client
from helpers.http import source_footer, url_capture
from helpers.logging import log_tool

_MINISTERIO = "educacion"
_STAT_TYPES = ministerios_client.list_stat_types(_MINISTERIO)
_STAT_TYPES_HELP = ", ".join(f'"{s}"' for s in _STAT_TYPES)


def _format_results(result: dict) -> str:
    return ministerios_client.format_results(
        result, "Ministerio de Educación y FP (MEFP)"
    )


def register_get_education_stats_tool(mcp: FastMCP) -> None:
    @mcp.tool()
    @log_tool
    async def get_education_stats(
        stat_type: str = "abandono_escolar",
        period: str | None = None,
        custom_query: str | None = None,
        page: int = 1,
    ) -> str:
        """
        Retrieve Spanish education statistics from the Ministerio de Educación y FP (MEFP).

        Useful for verifying claims about school dropout rates, university enrolment,
        teaching staff ratios, scholarship coverage, and public spending on education.

        Args:
            stat_type: Type of education statistic. Options:
                       "abandono_escolar"  — early school leaving rate by CCAA and year
                       "matriculados"      — non-university enrolment by stage and sex
                       "universitarios"    — university enrolment and graduate statistics
                       "profesorado"       — teaching staff and student-to-teacher ratios
                       "becas"             — scholarships — recipients and total amounts
                       "gasto_educativo"   — public spending on education (% GDP, per pupil)
                       "fp"                — vocational training enrolment and graduates
                       "pisa"              — PISA results and educational assessments
            period: Optional year or range to narrow results (e.g. "2023", "2020-2022").
            custom_query: Free-text query override (bypasses stat_type preset).
            page: Page number for paginated results.

        Data sources:
          - datos.gob.es (publisher: ministerio-de-educacion-y-formacion-profesional)
          - MEFP statistics: https://www.educacionyfp.gob.es/servicios-al-ciudadano/estadisticas.html
          - INE also publishes education stats — use get_ine_operations(search="educacion")
          - For EU comparisons use get_eurostat_data (EDUC_* datasets)
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
            return f"Error fetching education stats: {e}"
