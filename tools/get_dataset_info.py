import httpx
from mcp.server.fastmcp import FastMCP

from helpers import datos_gob_es_client
from helpers.http import source_footer, url_capture
from helpers.logging import log_tool


def register_get_dataset_info_tool(mcp: FastMCP) -> None:
    @mcp.tool()
    @log_tool
    async def get_dataset_info(dataset_id: str) -> str:
        """
        Get detailed metadata about a specific dataset from datos.gob.es.

        Returns title, description, publisher, themes, license, update frequency,
        spatial/temporal coverage, and the list of available resources.

        Args:
            dataset_id: Dataset ID (UUID) or slug from datos.gob.es.
        """
        _urls: list[str] = []
        url_capture.set(_urls)
        try:
            data = await datos_gob_es_client.get_dataset_details(dataset_id)

            if not data:
                return f"Error: Dataset '{dataset_id}' not found."

            content_parts = [f"Dataset: {data.get('title', 'Unknown')}", ""]

            if data.get("id"):
                content_parts.append(f"ID: {data['id']}")
            if data.get("name"):
                content_parts.append(
                    f"URL: https://datos.gob.es/es/catalogo/{data['name']}"
                )

            notes = data.get("notes") or data.get("description") or ""
            if notes:
                content_parts.append("")
                content_parts.append(f"Description: {notes[:500]}")

            # Publisher / organization
            org = data.get("organization") or {}
            if isinstance(org, dict) and org.get("title"):
                content_parts.append("")
                content_parts.append(f"Publisher: {org['title']}")
                if org.get("name"):
                    content_parts.append(f"  Slug: {org['name']}")

            # Themes
            themes = data.get("theme", [])
            if themes:
                theme_labels = [
                    t.get("label", t.get("id", ""))
                    for t in themes
                    if isinstance(t, dict)
                ]
                if theme_labels:
                    content_parts.append(f"Themes: {', '.join(theme_labels)}")

            # Tags
            tags = [
                t.get("display_name", t.get("name", "")) for t in data.get("tags", [])
            ]
            if tags:
                content_parts.append(f"Tags: {', '.join(tags[:10])}")

            # Spatial coverage
            if data.get("spatial"):
                content_parts.append(f"Spatial coverage: {data['spatial']}")

            # Temporal coverage
            if data.get("temporal_from") or data.get("temporal_to"):
                temporal = f"{data.get('temporal_from', '?')} to {data.get('temporal_to', '?')}"
                content_parts.append(f"Temporal coverage: {temporal}")

            # License
            if data.get("license_title"):
                content_parts.append(f"License: {data['license_title']}")
            elif data.get("license_id"):
                content_parts.append(f"License: {data['license_id']}")

            # Dates
            content_parts.append("")
            if data.get("metadata_created"):
                content_parts.append(f"Created: {data['metadata_created'][:10]}")
            if data.get("metadata_modified"):
                content_parts.append(f"Last updated: {data['metadata_modified'][:10]}")

            # Update frequency
            if data.get("accrual_periodicity"):
                content_parts.append(f"Update frequency: {data['accrual_periodicity']}")

            # Resources summary
            resources = data.get("resources", [])
            content_parts.append("")
            content_parts.append(f"Resources ({len(resources)} file(s)):")
            for r in resources[:10]:
                fmt = r.get("format", "unknown").upper()
                name = r.get("name") or r.get("description") or "Untitled"
                rid = r.get("id", "")
                content_parts.append(f"  - [{fmt}] {name} (ID: {rid})")
            if len(resources) > 10:
                content_parts.append(f"  ... and {len(resources) - 10} more")

            content_parts.append(source_footer(_urls))
            return "\n".join(content_parts)

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return f"Error: Dataset '{dataset_id}' not found."
            return f"Error: HTTP {e.response.status_code} — {e}"
        except Exception as e:  # noqa: BLE001
            return f"Error: {e}"
