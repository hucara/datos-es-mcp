from mcp.server.fastmcp import FastMCP

from helpers import renfe_client
from helpers.http import source_footer, url_capture
from helpers.logging import log_tool


def register_get_renfe_data_tool(mcp: FastMCP) -> None:
    @mcp.tool()
    @log_tool
    async def get_renfe_data(
        data_type: str = "schedules",
        service_type: str | None = None,
        page: int = 1,
    ) -> str:
        """
        Search and retrieve datasets from the Renfe open data portal (data.renfe.com).

        Renfe publishes train schedule files (GTFS), station data, real-time
        vehicle positions, and operational statistics for Spain's rail network.

        Args:
            data_type: Type of train data to retrieve:
                       - "schedules"  — GTFS schedule files (timetables, stops, routes)
                       - "stations"   — station locations and metadata
                       - "realtime"   — real-time vehicle GPS positions
                       - "statistics" — operational and traffic statistics
                       - "all"        — search all available datasets
            service_type: Filter by train service type:
                          - "ave"        — high-speed trains (AVE, AVLO)
                          - "larga"      — long-distance trains (Intercity, Alvia)
                          - "cercanias"  — commuter trains (Cercanías/Rodalies)
                          - "media"      — medium-distance trains
                          Leave empty for all services.
            page: Page number for results.
        """
        query_map = {
            "schedules": "GTFS horarios",
            "stations": "estaciones",
            "realtime": "tiempo real posiciones GPS",
            "statistics": "estadisticas trafico",
            "all": "",
        }

        if data_type not in query_map:
            valid = ", ".join(f'"{k}"' for k in query_map)
            return f"Invalid data_type '{data_type}'. Valid values: {valid}."

        query = query_map[data_type]
        if service_type:
            svc_queries = {
                "ave": "AVE alta velocidad",
                "larga": "larga distancia",
                "cercanias": "cercanias rodalies",
                "media": "media distancia",
            }
            query = f"{query} {svc_queries.get(service_type, service_type)}".strip()

        _urls: list[str] = []
        url_capture.set(_urls)
        try:
            result = await renfe_client.search_datasets(query=query, page=page)
        except Exception as e:  # noqa: BLE001
            return f"Error accessing Renfe open data: {e}"

        datasets = result.get("results", [])
        count = result.get("count", len(datasets))

        if not datasets:
            return (
                f"No Renfe datasets found for type='{data_type}'"
                + (f", service='{service_type}'" if service_type else "")
                + ".\nVisit https://data.renfe.com for the full catalog."
            )

        content_parts = [
            f"Renfe Open Data — {count} dataset(s) for '{data_type}'"
            + (f" ({service_type})" if service_type else ""),
            f"Page {page}:\n",
        ]

        for i, ds in enumerate(datasets, 1):
            title = ds.get("title") or "Unknown"
            ds_id = ds.get("id") or "?"
            desc = ds.get("description") or ""
            formats = ds.get("formats") or []
            modified = ds.get("last_modified") or ""
            resources = ds.get("resources") or []

            content_parts.append(f"{i}. {title}")
            content_parts.append(f"   ID: {ds_id}")
            if desc:
                content_parts.append(f"   Description: {desc[:200]}...")
            if formats:
                content_parts.append(f"   Formats: {', '.join(formats[:5])}")
            if modified:
                content_parts.append(f"   Last updated: {str(modified)[:10]}")

            # Show download URLs for GTFS/CSV resources directly
            for r in resources[:3]:
                if r.get("url") and r.get("format") in ("GTFS", "CSV", "JSON"):
                    content_parts.append(f"   Download ({r['format']}): {r['url']}")

            content_parts.append(f"   Portal URL: {ds.get('url')}")
            content_parts.append("")

        content_parts.append("Full catalog: https://data.renfe.com/dataset")
        content_parts.append(source_footer(_urls))
        return "\n".join(content_parts)
