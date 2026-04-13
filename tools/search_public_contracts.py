import xml.etree.ElementTree as ET

from mcp.server.fastmcp import FastMCP

from helpers import place_client
from helpers.logging import log_tool

_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "cac": "urn:oasis:names:specification:ubl:schema:xsd:CommonAggregateComponents-2",
    "cbc": "urn:oasis:names:specification:ubl:schema:xsd:CommonBasicComponents-2",
    "ns3": "http://www.w3.org/2005/Atom",
}


def _parse_atom_entries(xml_text: str, keyword: str | None = None) -> list[dict]:
    """Parse ATOM XML entries from PLACE feed into dicts."""
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return []

    # Handle namespace
    ns = "http://www.w3.org/2005/Atom"
    entries = []

    for entry in root.findall(f"{{{ns}}}entry"):
        def txt(tag: str) -> str:
            el = entry.find(f"{{{ns}}}{tag}")
            return el.text.strip() if el is not None and el.text else ""

        title = txt("title")
        updated = txt("updated")
        summary = txt("summary")

        link_el = entry.find(f"{{{ns}}}link")
        link = link_el.get("href", "") if link_el is not None else ""

        # Optional UBL fields
        contracting = ""
        amount = ""
        cpv = ""

        # Search within content/summary for extra info
        content_el = entry.find(f"{{{ns}}}content")
        content_text = content_el.text if content_el is not None and content_el.text else summary

        if keyword:
            kw_lower = keyword.lower()
            if kw_lower not in title.lower() and kw_lower not in content_text.lower():
                continue

        entries.append({
            "title": title,
            "updated": updated[:10] if updated else "",
            "summary": (content_text or summary)[:300],
            "link": link,
        })

    return entries


def register_search_public_contracts_tool(mcp: FastMCP) -> None:
    @mcp.tool()
    @log_tool
    async def search_public_contracts(
        query: str,
        source: str = "datasets",
    ) -> str:
        """
        Search for Spanish public procurement data from PLACE
        (Plataforma de Contratación del Sector Público).

        PLACE is Spain's central platform where all public entities publish
        tenders and contract award notices (covering state, autonomous communities,
        local entities, and public enterprises).

        Args:
            query: Search terms for contracts/tenders
                   (e.g. "obras carretera", "servicios informatica", "suministros medicamentos").
            source: Data source to query:
                    - "datasets" (default): search datos.gob.es catalog for bulk
                      procurement data files (CSV/XML with full historical data).
                    - "feed": fetch the live PLACE ATOM feed with the latest tender
                      notices published in the last few days.

        Note: For detailed real-time tender search, visit
        https://contrataciondelestado.es directly.
        """
        if source == "feed":
            try:
                xml_text = await place_client.get_atom_feed()
            except Exception as e:  # noqa: BLE001
                return f"Error fetching PLACE tender feed: {e}"

            entries = _parse_atom_entries(xml_text, keyword=query if query else None)
            if not entries:
                return (
                    f"No recent tenders found matching '{query}' in the PLACE feed.\n"
                    "The feed contains only the last few days. For historical data, "
                    "use source='datasets'."
                )

            content_parts = [
                f"PLACE Live Feed — {len(entries)} tender notice(s)"
                + (f" matching '{query}'" if query else "") + ":\n",
            ]
            for i, e in enumerate(entries[:20], 1):
                content_parts.append(f"{i}. {e['title']}")
                if e["updated"]:
                    content_parts.append(f"   Published: {e['updated']}")
                if e["summary"]:
                    content_parts.append(f"   Summary: {e['summary'][:200]}")
                if e["link"]:
                    content_parts.append(f"   URL: {e['link']}")
                content_parts.append("")

            content_parts.append(
                "Full search: https://contrataciondelestado.es/wps/portal/plataforma"
            )
            return "\n".join(content_parts)

        else:
            # Search datos.gob.es for procurement datasets
            search_query = f"contratacion {query}" if query else "licitaciones contratacion publica"
            try:
                result = await place_client.search_datasets(query=search_query)
            except Exception as e:  # noqa: BLE001
                return f"Error searching procurement datasets: {e}"

            datasets = result.get("results", [])
            count = result.get("count", len(datasets))

            if not datasets:
                return (
                    f"No public procurement datasets found for '{query}'.\n"
                    "Try source='feed' for live tender notices."
                )

            content_parts = [
                f"Public Procurement Datasets — {count} result(s) for '{query}':\n",
            ]
            for i, ds in enumerate(datasets, 1):
                title = ds.get("title") or "Unknown"
                ds_id = ds.get("id") or "?"
                org = ds.get("organization") or ""
                modified = ds.get("metadata_modified") or ""
                resources = ds.get("resources", [])
                fmt_list = list({r.get("format", "").upper() for r in resources if r.get("format")})

                content_parts.append(f"{i}. {title}")
                content_parts.append(f"   ID: {ds_id}")
                if org:
                    content_parts.append(f"   Publisher: {org}")
                if fmt_list:
                    content_parts.append(f"   Formats: {', '.join(fmt_list[:5])}")
                if modified:
                    content_parts.append(f"   Last updated: {str(modified)[:10]}")
                content_parts.append(
                    f"   URL: https://datos.gob.es/es/catalogo/{ds.get('name', ds_id)}"
                )
                content_parts.append("")

            content_parts.append(
                "For live tender search: https://contrataciondelestado.es"
            )
            return "\n".join(content_parts)
