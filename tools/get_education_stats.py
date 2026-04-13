from mcp.server.fastmcp import FastMCP

from helpers import ministerios_client
from helpers.logging import log_tool

_MINISTERIO = "educacion"
_STAT_TYPES = ministerios_client.list_stat_types(_MINISTERIO)
_STAT_TYPES_HELP = ", ".join(f'"{s}"' for s in _STAT_TYPES)


def _format_results(result: dict) -> str:
    info = result.get("ministerio_info", {})
    datasets = result.get("results", [])
    count = result.get("count", 0)
    page = result.get("page", 1)
    stat_desc = result.get("stat_description", "")

    lines = [
        f"Ministerio de Educación y FP (MEFP)",
        f"Portal: {info.get('portal_url', '')}",
    ]
    if stat_desc:
        lines.append(f"Topic: {stat_desc}")
    lines.append(f"\nFound {count} dataset(s) (page {page}, showing {len(datasets)}):\n")

    for i, ds in enumerate(datasets, 1):
        lines.append(f"{i}. {ds.get('title', 'Untitled')}")
        if ds.get("organization"):
            lines.append(f"   Publisher: {ds['organization']}")
        if ds.get("description"):
            lines.append(f"   Description: {ds['description'][:200]}...")
        if ds.get("last_modified"):
            lines.append(f"   Last updated: {ds['last_modified'][:10]}")
        lines.append(f"   Formats: {', '.join(ds.get('formats', [])) or 'unknown'}")
        lines.append(f"   Resources: {ds.get('resources_count', 0)} file(s)")
        for r in (ds.get("resources") or [])[:3]:
            fmt = r.get("format") or "?"
            name = r.get("name") or "File"
            url = r.get("url") or ""
            if url:
                lines.append(f"   [{fmt}] {name}: {url}")
        lines.append(f"   URL: {ds.get('url', '')}")
        lines.append("")

    if not datasets:
        lines.append("No datasets found. Try a broader stat_type or use custom_query.")
        lines.append(
            "Tip: INE also publishes education statistics — "
            "try get_ine_operations(search='educacion')."
        )

    return "\n".join(lines)


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
        try:
            result = await ministerios_client.search_ministerio_stats(
                ministerio=_MINISTERIO,
                stat_type=stat_type if not custom_query else None,
                custom_query=custom_query,
                period=period,
                page=page,
            )
            return _format_results(result)
        except ValueError as e:
            return (
                f"Invalid stat_type '{stat_type}'. "
                f"Valid options: {_STAT_TYPES_HELP}.\n"
                f"Error: {e}"
            )
        except Exception as e:  # noqa: BLE001
            return f"Error fetching education stats: {e}"
