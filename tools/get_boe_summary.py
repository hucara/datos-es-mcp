from mcp.server.fastmcp import FastMCP

from helpers import boe_client
from helpers.http import source_footer, url_capture
from helpers.logging import log_tool


def register_get_boe_summary_tool(mcp: FastMCP) -> None:
    @mcp.tool()
    @log_tool
    async def get_boe_summary(
        date: str,
        gazette: str = "BOE",
    ) -> str:
        """
        Get the daily summary of Spain's Official State Gazette (BOE) or the
        Mercantile Registry Gazette (BORME) for a specific date.

        The BOE publishes laws, royal decrees, ministerial orders, appointments,
        and other official acts. The BORME publishes commercial registry acts:
        company incorporations, dissolutions, capital changes, and insolvencies.

        Args:
            date: Date in YYYYMMDD format (e.g. "20241201" for December 1, 2024).
            gazette: "BOE" (default) or "BORME" (Mercantile Registry Gazette).
        """
        gazette_upper = gazette.upper()
        if gazette_upper not in ("BOE", "BORME"):
            return "Error: gazette must be 'BOE' or 'BORME'."

        _urls: list[str] = []
        url_capture.set(_urls)
        try:
            if gazette_upper == "BORME":
                data = await boe_client.get_borme_summary(date)
            else:
                data = await boe_client.get_boe_summary(date)
        except Exception as e:  # noqa: BLE001
            return f"Error fetching {gazette_upper} summary for {date}: {e}"

        # Parse the response.
        # API wraps the payload in {"status":..., "data": {"sumario": {...}}}
        raw_data = data.get("data") or data
        sumario = raw_data.get("sumario") or raw_data

        if not sumario:
            return (
                f"No {gazette_upper} published on {date} (may be a weekend or holiday)."
            )

        meta = sumario.get("metadatos") or {}
        pub_date = meta.get("fecha_publicacion") or date
        gazette_num = meta.get("numero_oficial") or ""

        content_parts = [
            f"{gazette_upper} Summary — {pub_date}"
            + (f" (No. {gazette_num})" if gazette_num else ""),
            "",
        ]

        # diario is a list of gazette issues (usually one per day)
        diario_raw = sumario.get("diario") or []
        if isinstance(diario_raw, dict):
            diario_raw = [diario_raw]

        # Collect all sections from all diario entries
        all_sections: list[dict] = []
        for diario_entry in diario_raw:
            secs = diario_entry.get("seccion") or []
            if isinstance(secs, dict):
                secs = [secs]
            all_sections.extend(secs)

        if not all_sections:
            content_parts.append(f"No documents found for {date}.")
            content_parts.append(source_footer(_urls))
            return "\n".join(content_parts)

        def _extract_items(dept: dict) -> list[dict]:
            """Extract document items from a departamento, handling epigrafe nesting."""
            items: list[dict] = []
            # Items can be directly under 'item' or nested under 'epigrafe[].item'
            direct = dept.get("item") or []
            if isinstance(direct, dict):
                direct = [direct]
            items.extend(direct)

            for epi in dept.get("epigrafe") or []:
                if isinstance(epi, dict):
                    sub = epi.get("item") or []
                    if isinstance(sub, dict):
                        sub = [sub]
                    items.extend(sub)
            return items

        total_docs = 0
        for section in all_sections:
            if not isinstance(section, dict):
                continue
            sec_name = section.get("nombre") or "Section"
            depts = section.get("departamento") or []
            if isinstance(depts, dict):
                depts = [depts]

            sec_docs = 0
            sec_lines = []
            for dept in depts:
                if not isinstance(dept, dict):
                    continue
                dept_name = dept.get("nombre") or "Unknown"
                for item in _extract_items(dept):
                    if not isinstance(item, dict):
                        continue
                    title = item.get("titulo") or "Untitled"
                    doc_id = item.get("identificador") or ""
                    sec_lines.append(f"  [{dept_name}] {title[:120]}")
                    if doc_id and not doc_id.startswith("http"):
                        sec_lines[-1] += f" (ID: {doc_id})"
                    sec_docs += 1

            total_docs += sec_docs
            if sec_lines:
                content_parts.append(f"\n{sec_name} ({sec_docs} item(s)):")
                content_parts.extend(sec_lines[:10])
                if sec_docs > 10:
                    content_parts.append(f"  ... and {sec_docs - 10} more items")

        content_parts.insert(2, f"Total documents: {total_docs}\n")
        content_parts.append(source_footer(_urls))
        return "\n".join(content_parts)
