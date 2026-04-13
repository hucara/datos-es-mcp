from mcp.server.fastmcp import FastMCP

from helpers import boe_client
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

        try:
            if gazette_upper == "BORME":
                data = await boe_client.get_borme_summary(date)
            else:
                data = await boe_client.get_boe_summary(date)
        except Exception as e:  # noqa: BLE001
            return f"Error fetching {gazette_upper} summary for {date}: {e}"

        # Parse the response — BOE API wraps everything in a 'sumario' or 'data' key
        sumario = (
            data.get("sumario")
            or data.get("data")
            or data
        )

        if not sumario:
            return f"No {gazette_upper} published on {date} (may be a weekend or holiday)."

        meta = sumario.get("metadatos") or {}
        pub_date = meta.get("fecha_publicacion") or date
        gazette_num = meta.get("numero_oficial") or ""

        content_parts = [
            f"{gazette_upper} Summary — {pub_date}" + (f" (No. {gazette_num})" if gazette_num else ""),
            "",
        ]

        diario = sumario.get("diario") or {}
        sections = diario.get("seccion") or []
        if isinstance(sections, dict):
            sections = [sections]

        if not sections:
            # Try flat structure
            docs = sumario.get("documento") or []
            if isinstance(docs, dict):
                docs = [docs]
            if docs:
                content_parts.append(f"Documents: {len(docs)}")
                for doc in docs[:20]:
                    title = doc.get("titulo") or doc.get("title") or "Unknown"
                    dept = doc.get("departamento") or ""
                    doc_id = doc.get("identificador") or ""
                    line = f"  • {title}"
                    if dept:
                        line += f" [{dept}]"
                    if doc_id:
                        line += f" (ID: {doc_id})"
                    content_parts.append(line)
            else:
                content_parts.append(f"No documents found for {date}.")
            return "\n".join(content_parts)

        total_docs = 0
        for section in sections:
            if isinstance(section, dict):
                sec_name = section.get("nombre") or section.get("@nombre") or "Section"
                depts = section.get("departamento") or []
                if isinstance(depts, dict):
                    depts = [depts]

                sec_docs = 0
                sec_lines = []
                for dept in depts:
                    if not isinstance(dept, dict):
                        continue
                    dept_name = dept.get("nombre") or dept.get("@nombre") or "Unknown"
                    items = dept.get("item") or dept.get("epigrafe") or []
                    if isinstance(items, dict):
                        items = [items]

                    for item in (items if isinstance(items, list) else []):
                        if not isinstance(item, dict):
                            continue
                        title = item.get("titulo") or "Untitled"
                        doc_id = item.get("identificador") or item.get("urlHtml") or ""
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
        return "\n".join(content_parts)
