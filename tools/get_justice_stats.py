from mcp.server.fastmcp import FastMCP

from helpers import ministerios_client
from helpers.http import source_footer, url_capture
from helpers.logging import log_tool

_MINISTERIO = "justicia"
_STAT_TYPES = ministerios_client.list_stat_types(_MINISTERIO)
_STAT_TYPES_HELP = ", ".join(f'"{s}"' for s in _STAT_TYPES)


def _format_results(result: dict) -> str:
    info = result.get("ministerio_info", {})
    datasets = result.get("results", [])
    count = result.get("count", 0)
    page = result.get("page", 1)
    stat_desc = result.get("stat_description", "")

    lines = [
        "Ministerio de Justicia / Consejo General del Poder Judicial (CGPJ)",
        f"Portal: {info.get('portal_url', '')}",
    ]
    if stat_desc:
        lines.append(f"Topic: {stat_desc}")
    lines.append(
        f"\nFound {count} dataset(s) (page {page}, showing {len(datasets)}):\n"
    )

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
            "Tip: detailed judicial statistics are also available at "
            "https://www.poderjudicial.es/cgpj/es/Temas/Estadistica-Judicial/"
        )

    return "\n".join(lines)


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
