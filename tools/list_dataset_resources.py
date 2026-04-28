import csv
import io
import json
import logging

import httpx
from mcp.server.fastmcp import FastMCP

from helpers import datos_gob_es_client
from helpers.http import source_footer, url_capture
from helpers.logging import MAIN_LOGGER_NAME, log_tool
from helpers.user_agent import USER_AGENT

logger = logging.getLogger(MAIN_LOGGER_NAME)

_DOWNLOAD_FORMATS = {"CSV", "JSON", "TSV", "TXT"}
_MAX_ROWS_PREVIEW = 50


def _format_size(size: int) -> str:
    if size < 1024:
        return f"{size} B"
    if size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    if size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    return f"{size / (1024 * 1024 * 1024):.1f} GB"


async def _download_and_parse(url: str, fmt: str, max_mb: int) -> str:
    """Download a CSV or JSON resource and return a formatted data preview."""
    max_bytes = max_mb * 1024 * 1024
    try:
        async with httpx.AsyncClient(headers={"User-Agent": USER_AGENT}) as client:
            async with client.stream("GET", url, timeout=30.0) as resp:
                resp.raise_for_status()
                chunks: list[bytes] = []
                total = 0
                async for chunk in resp.aiter_bytes(chunk_size=65536):
                    chunks.append(chunk)
                    total += len(chunk)
                    if total > max_bytes:
                        return (
                            f"   [Data download skipped — file exceeds {max_mb} MB limit. "
                            f"Download directly: {url}]"
                        )
                raw = b"".join(chunks)
    except Exception as exc:  # noqa: BLE001
        return f"   [Could not download file: {exc}]"

    text = raw.decode("utf-8", errors="replace")

    if fmt in ("CSV", "TSV"):
        delimiter = "\t" if fmt == "TSV" else ","
        try:
            reader = csv.reader(io.StringIO(text), delimiter=delimiter)
            rows = list(reader)
        except Exception as exc:  # noqa: BLE001
            return f"   [Could not parse {fmt}: {exc}]"

        if not rows:
            return "   [Empty file]"

        headers = rows[0]
        data_rows = rows[1:]
        lines = [
            f"   Columns ({len(headers)}): {', '.join(headers[:20])}"
            + (" ..." if len(headers) > 20 else ""),
            f"   Total rows (approx): {len(data_rows)}",
        ]
        if data_rows:
            lines.append(f"   First {min(_MAX_ROWS_PREVIEW, len(data_rows))} rows:")
            for row in data_rows[:_MAX_ROWS_PREVIEW]:
                lines.append("     " + " | ".join(str(v)[:40] for v in row[:10]))
        return "\n".join(lines)

    if fmt == "JSON":
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as exc:
            return f"   [Invalid JSON: {exc}]"

        if isinstance(parsed, list):
            lines = [f"   JSON array — {len(parsed)} item(s)"]
            for item in parsed[:_MAX_ROWS_PREVIEW]:
                if isinstance(item, dict):
                    lines.append("     " + str(item)[:120])
                else:
                    lines.append(f"     {item!r}")
            if len(parsed) > _MAX_ROWS_PREVIEW:
                lines.append(f"     ... ({len(parsed) - _MAX_ROWS_PREVIEW} more)")
            return "\n".join(lines)

        if isinstance(parsed, dict):
            keys = list(parsed.keys())
            return (
                f"   JSON object — {len(keys)} key(s): "
                + ", ".join(str(k) for k in keys[:20])
                + (" ..." if len(keys) > 20 else "")
            )

        return f"   JSON value: {str(parsed)[:200]}"

    return f"   [Unsupported format for preview: {fmt}]"


def register_list_dataset_resources_tool(mcp: FastMCP) -> None:
    @mcp.tool()
    @log_tool
    async def list_dataset_resources(
        dataset_id: str,
        include_data: bool = False,
        max_file_size_mb: int = 10,
    ) -> str:
        """
        List all resources (files/distributions) in a datos.gob.es dataset.

        Returns resource ID, name, format, size, last modified date, and download URL
        for each file. Use this after get_dataset_info to find the specific file you need.

        Set include_data=True to also download and preview small CSV/JSON files directly
        (up to max_file_size_mb, default 10 MB). Previews show column names and the first
        50 rows so you can evaluate the data without a separate download step.

        Args:
            dataset_id: Dataset ID (UUID) or slug from datos.gob.es.
            include_data: If True, download and preview CSV/JSON resources up to the
                          size limit. Default: False.
            max_file_size_mb: Maximum file size in MB to download when include_data=True.
                              Default: 10. Max recommended: 50.
        """
        _urls: list[str] = []
        url_capture.set(_urls)
        try:
            data = await datos_gob_es_client.get_dataset_details(dataset_id)

            if not data:
                return f"Error: Dataset '{dataset_id}' not found."

            resources = data.get("resources", [])
            title = data.get("title", "Unknown")

            content_parts = [
                f"Resources in dataset: {title}",
                f"Dataset ID: {data.get('id', dataset_id)}",
                f"Total resources: {len(resources)}\n",
            ]

            if not resources:
                content_parts.append("This dataset has no resources.")
                return "\n".join(content_parts)

            for i, r in enumerate(resources, 1):
                name = r.get("name") or r.get("description") or "Untitled"
                content_parts.append(f"{i}. {name}")
                content_parts.append(f"   Resource ID: {r.get('id', 'unknown')}")

                fmt = (r.get("format") or "").upper()
                if fmt:
                    content_parts.append(f"   Format: {fmt}")
                if r.get("mimetype"):
                    content_parts.append(f"   MIME type: {r['mimetype']}")

                size = r.get("size")
                if size:
                    try:
                        content_parts.append(f"   Size: {_format_size(int(size))}")
                    except (ValueError, TypeError):
                        content_parts.append(f"   Size: {size}")

                if r.get("last_modified"):
                    content_parts.append(
                        f"   Last modified: {str(r['last_modified'])[:10]}"
                    )
                url = r.get("url") or ""
                if url:
                    content_parts.append(f"   URL: {url}")
                if r.get("description") and r.get("description") != name:
                    content_parts.append(f"   Description: {r['description'][:150]}")

                # Data preview
                if include_data and url and fmt in _DOWNLOAD_FORMATS:
                    content_parts.append("   Data preview:")
                    preview = await _download_and_parse(url, fmt, max_file_size_mb)
                    content_parts.append(preview)

                content_parts.append("")

            content_parts.append(source_footer(_urls))
            return "\n".join(content_parts)

        except Exception as e:  # noqa: BLE001
            return f"Error: {e}"
