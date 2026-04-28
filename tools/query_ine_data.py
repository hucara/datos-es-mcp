from mcp.server.fastmcp import FastMCP

from helpers import ine_client
from helpers.http import source_footer, url_capture
from helpers.logging import log_tool


def _format_data_points(data_list: list, max_points: int = 20) -> list[str]:
    """Format a list of INE data points {Fecha, Valor} into readable lines."""
    lines = []
    shown = data_list[:max_points]
    for point in shown:
        fecha = point.get("Fecha") or point.get("fecha") or "?"
        valor = point.get("Valor")
        if valor is None:
            valor = point.get("valor")
        # Convert epoch ms to readable date if numeric
        if isinstance(fecha, (int, float)):
            from datetime import datetime, timezone

            try:
                dt = datetime.fromtimestamp(fecha / 1000, tz=timezone.utc)
                fecha = dt.strftime("%Y-%m")
            except Exception:
                pass
        lines.append(f"    {fecha}: {valor}")
    if len(data_list) > max_points:
        lines.append(f"    ... ({len(data_list) - max_points} more periods)")
    return lines


def register_query_ine_data_tool(mcp: FastMCP) -> None:
    @mcp.tool()
    @log_tool
    async def query_ine_data(
        operation_code: str | None = None,
        table_id: str | None = None,
        series_code: str | None = None,
        last_n_periods: int = 12,
        date_range: str | None = None,
    ) -> str:
        """
        Retrieve statistical data from INE (Instituto Nacional de Estadística).

        Provide one of: operation_code (lists tables), table_id (retrieves table data),
        or series_code (retrieves a specific series). Use get_ine_operations to find codes.

        Args:
            operation_code: INE operation code to list available tables
                            (e.g. "IPC", "EPA", "CN", "PADRON").
            table_id: Numeric INE table ID to fetch data (e.g. "50902" for IPC general).
            series_code: INE series code for a specific indicator
                         (e.g. "IPC251856" for CPI national monthly index).
            last_n_periods: Number of most recent periods to return (default: 12).
                            Ignored if date_range is provided.
            date_range: Date range filter in format "YYYYMMDD:YYYYMMDD"
                        (e.g. "20200101:20241231").

        Examples:
            - query_ine_data(operation_code="IPC") — list IPC tables
            - query_ine_data(table_id="50902", last_n_periods=24) — last 24 months of IPC
            - query_ine_data(series_code="IPC251856", last_n_periods=6) — last 6 CPI values
        """
        if not any([operation_code, table_id, series_code]):
            return (
                "Error: Provide one of operation_code, table_id, or series_code.\n"
                "Use get_ine_operations to discover available operation codes."
            )

        _urls: list[str] = []
        url_capture.set(_urls)

        try:
            # Mode 1: list tables for an operation
            if operation_code and not table_id and not series_code:
                tables = await ine_client.get_tables_for_operation(operation_code)
                if not tables:
                    return f"No tables found for operation '{operation_code}'. Check the code with get_ine_operations."

                content_parts = [
                    f"Tables for INE operation '{operation_code}':",
                    f"Found {len(tables)} table(s):\n",
                ]
                for t in tables[:30]:
                    tid = t.get("Id") or "?"
                    name = t.get("Nombre") or "Unknown"
                    modified = t.get("Ultima_Modificacion") or ""
                    if modified:
                        modified = f" [updated: {str(modified)[:10]}]"
                    content_parts.append(f"  ID {tid}: {name}{modified}")
                if len(tables) > 30:
                    content_parts.append(f"  ... and {len(tables) - 30} more tables")
                content_parts.append(
                    "\nUse query_ine_data(table_id=<ID>) to fetch data from a specific table."
                )
                content_parts.append(source_footer(_urls))
                return "\n".join(content_parts)

            # Mode 2: fetch table data
            if table_id:
                series_list = await ine_client.get_table_data(
                    table_id=table_id,
                    last_n=last_n_periods,
                    date_range=date_range,
                )
                if not series_list:
                    return f"No data found for table ID '{table_id}'."

                content_parts = [
                    f"INE Table {table_id} — {len(series_list)} series:",
                    "",
                ]
                for s in series_list[:10]:
                    name = s.get("Nombre") or s.get("nombre") or "Unknown series"
                    unit = s.get("Unidad") or {}
                    unit_name = (
                        unit.get("Nombre", "") if isinstance(unit, dict) else str(unit)
                    )
                    data_pts = s.get("Data") or s.get("data") or []

                    content_parts.append(f"Series: {name}")
                    if unit_name:
                        content_parts.append(f"  Unit: {unit_name}")
                    if data_pts:
                        content_parts.append(
                            f"  Last {min(len(data_pts), last_n_periods)} periods:"
                        )
                        content_parts.extend(
                            _format_data_points(data_pts, last_n_periods)
                        )
                    content_parts.append("")

                if len(series_list) > 10:
                    content_parts.append(
                        f"... and {len(series_list) - 10} more series in this table."
                    )
                content_parts.append(source_footer(_urls))
                return "\n".join(content_parts)

            # Mode 3: fetch specific series
            if series_code:
                s = await ine_client.get_series_data(
                    series_code=series_code,
                    last_n=last_n_periods,
                    date_range=date_range,
                )
                if not s:
                    return f"No data found for series '{series_code}'."

                name = s.get("Nombre") or s.get("nombre") or series_code
                unit = s.get("Unidad") or {}
                unit_name = (
                    unit.get("Nombre", "") if isinstance(unit, dict) else str(unit)
                )
                period = s.get("Periodicidad") or {}
                period_name = (
                    period.get("Nombre", "")
                    if isinstance(period, dict)
                    else str(period)
                )
                data_pts = s.get("Data") or s.get("data") or []

                content_parts = [f"INE Series: {name}", f"Code: {series_code}"]
                if unit_name:
                    content_parts.append(f"Unit: {unit_name}")
                if period_name:
                    content_parts.append(f"Frequency: {period_name}")
                content_parts.append("")
                if data_pts:
                    content_parts.append(
                        f"Last {min(len(data_pts), last_n_periods)} values:"
                    )
                    content_parts.extend(_format_data_points(data_pts, last_n_periods))
                else:
                    content_parts.append("No data points available.")
                content_parts.append(source_footer(_urls))
                return "\n".join(content_parts)

        except Exception as e:  # noqa: BLE001
            return f"Error querying INE data: {e}"

        return "Error: Unexpected state."
