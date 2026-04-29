from mcp.server.fastmcp import FastMCP

from helpers import airef_client
from helpers.http import source_footer, url_capture
from helpers.logging import log_tool

_TOPICS = airef_client.TOPIC_REGISTRY
_TOPICS_HELP = "\n".join(f'  "{k}" — {v["description"]}' for k, v in _TOPICS.items())


def register_get_airef_data_tool(mcp: FastMCP) -> None:
    @mcp.tool()
    @log_tool
    async def get_airef_data(
        topic: str = "previsiones",
        query: str | None = None,
        page: int = 1,
    ) -> str:
        """
        Retrieve data and guidance from AIReF (Autoridad Independiente de
        Responsabilidad Fiscal), Spain's independent fiscal watchdog.

        AIReF validates government macroeconomic forecasts, analyses fiscal
        sustainability, conducts spending reviews, and publishes fiscal-impact
        studies (immigration contribution to GDP, fiscal drag/bracket creep).

        Note: AIReF does NOT have a public machine-readable API. This tool
        searches datos.gob.es for related Hacienda/INE datasets and returns
        direct links to AIReF's own data portal and claim-specific guidance.

        Args:
            topic: Analysis area. Options:
                   "previsiones"           — AIReF macroeconomic and fiscal forecasts
                   "sostenibilidad_fiscal" — public debt, spending rule compliance
                   "spending_review"       — public expenditure efficiency evaluations
                   "inmigracion_pib"       — immigration's contribution to GDP growth
                   "fiscal_drag"           — bracket creep / progresividad en frío
                   "observatorio_ccaa"     — autonomous communities fiscal data
            query: Optional custom search override for datos.gob.es.
            page: Page number for results.

        Key AIReF portals:
          - Data access:  https://www.airef.es/en/data-access/
          - All reports:  https://www.airef.es/en/all-reports/
          - Forecasts:    https://www.airef.es/en/historical-macroeconomic-forecast/
          - Debt monitor: https://www.airef.es/en/public-debt-monitor/
        """
        if topic not in _TOPICS:
            valid = ", ".join(f'"{k}"' for k in _TOPICS)
            return f"Invalid topic '{topic}'. Valid values: {valid}."

        _urls: list[str] = []
        url_capture.set(_urls)

        try:
            result = await airef_client.search_airef_related_datasets(
                topic=topic,
                custom_query=query,
                page=page,
            )
        except Exception as e:  # noqa: BLE001
            return f"Error searching AIReF-related datasets: {e}"

        topic_info = result.get("topic_info", {})
        datasets = result.get("results", [])
        count = result.get("count", len(datasets))

        lines = [
            f"AIReF — {topic_info.get('description', topic)}",
            f"AIReF portal: {topic_info.get('airef_url', airef_client.AIREF_PORTAL)}",
            "",
            "NOTE: AIReF has no public API. For authoritative data, use the portal link above.",
            "The datasets below are related Hacienda/INE sources from datos.gob.es.\n",
        ]

        notes = topic_info.get("notes", "")
        if notes:
            lines.append("Claim verification guidance:")
            lines.append(notes)
            lines.append("")

        lines.append(
            f"Related datasets on datos.gob.es (found {count}, page {page}, "
            f"showing {len(datasets)}):\n"
        )

        for i, ds in enumerate(datasets, 1):
            ds_id = ds.get("id", "")
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
            if ds_id:
                lines.append(f"   dataset_id: {ds_id}")
                lines.append(
                    f"   → list_dataset_resources(dataset_id='{ds_id}', include_data=True)"
                )
            else:
                lines.append(f"   URL: {ds.get('url', '')}")
            lines.append("")

        if not datasets:
            lines.append(
                "No related datasets found on datos.gob.es. "
                "Use the AIReF portal link above for direct access."
            )

        lines.append(source_footer(_urls))
        return "\n".join(lines)
