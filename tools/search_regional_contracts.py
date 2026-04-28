from mcp.server.fastmcp import FastMCP

from helpers import regional_contracts_client
from helpers.http import source_footer, url_capture
from helpers.logging import log_tool

_ALL_REGIONS = regional_contracts_client.list_regions()
_REGIONS_HELP = ", ".join(f'"{r}"' for r in _ALL_REGIONS)


def _format_datasets(
    datasets: list[dict],
    portal_name: str,
    source: str,
) -> list[str]:
    """Format a list of CKAN dataset dicts into human-readable lines."""
    lines: list[str] = []
    for i, ds in enumerate(datasets, 1):
        if not isinstance(ds, dict):
            continue
        title = ds.get("title") or "Unknown"
        ds_id = ds.get("id") or "?"
        ds_name = ds.get("name") or ds_id
        notes = (ds.get("notes") or ds.get("description") or "")[:250]
        resources = ds.get("resources") or []
        modified = ds.get("metadata_modified") or ds.get("last_modified") or ""
        org = ds.get("organization") or {}
        org_title = (
            org.get("title") if isinstance(org, dict) else str(org or "")
        ) or ""

        lines.append(f"{i}. {title}")
        if org_title and org_title.lower() not in title.lower():
            lines.append(f"   Publisher: {org_title}")
        if notes:
            lines.append(f"   Description: {notes}...")
        if modified:
            lines.append(f"   Last updated: {str(modified)[:10]}")
        lines.append(f"   Resources: {len(resources)} file(s)")

        for r in resources[:4]:
            fmt = (r.get("format") or "?").upper()
            name = r.get("name") or r.get("description") or "File"
            url = r.get("url") or ""
            if url:
                lines.append(f"   [{fmt}] {name}: {url}")

        if source == "datos_gob_es":
            lines.append(f"   Portal: https://datos.gob.es/es/catalogo/{ds_name}")
        lines.append("")
    return lines


def register_search_regional_contracts_tool(mcp: FastMCP) -> None:
    @mcp.tool()
    @log_tool
    async def search_regional_contracts(
        query: str,
        region: str = "all",
        page: int = 1,
    ) -> str:
        """
        Search public procurement data from Spain's major autonomous communities.

        Each community publishes its own procurement data beyond what appears on
        the national PLACE platform. This tool searches Madrid, Cataluña, and
        Valencia regional open data portals for contract awards, tenders, and
        public spending data.

        Useful for:
          - Verifying regional government contract claims
          - Comparing procurement volumes across communities
          - Finding contracts by department, amount range, or sector
          - Investigating regional public spending patterns

        Args:
            query: Search terms in Spanish or Catalan/Valencian
                   (e.g. "obras publicas", "servicios informatica", "contratos menores",
                   "adjudicaciones sanidad", "licitaciones educacion").
            region: Which community to search:
                    - "madrid"   — Comunidad de Madrid (datos.comunidad.madrid)
                    - "cataluña" — Generalitat de Catalunya (analisi.transparenciacatalunya.cat)
                    - "valencia" — Generalitat Valenciana (dadesobertes.gva.es)
                    - "all"      — Search all three communities (default)
            page: Page number for paginated results.

        Portal URLs for direct access:
          - Madrid contracts:   https://www.contratacionpublicamadrid.es
          - Cataluña contracts: https://contractaciopublica.gencat.cat
          - Valencia contracts: https://contratacion.gva.es
          - National (PLACE):   https://contrataciondelestado.es
        """
        _urls: list[str] = []
        url_capture.set(_urls)

        regions_to_search = _ALL_REGIONS if region == "all" else [region]

        if region != "all" and region not in _ALL_REGIONS:
            return (
                f"Unknown region '{region}'. Valid values: {_REGIONS_HELP}, or \"all\"."
            )

        content_parts: list[str] = []
        any_results = False

        for reg in regions_to_search:
            portal_info = regional_contracts_client.get_portal_info(reg)
            portal_name = portal_info.get("name", reg)
            contracts_url = portal_info.get("contracts_portal_url", "")

            content_parts.append(f"{'=' * 60}")
            content_parts.append(f"{portal_name}")
            if contracts_url:
                content_parts.append(f"Procurement portal: {contracts_url}")
            content_parts.append("")

            # Try the regional CKAN portal first
            datasets: list[dict] = []
            source = "regional_ckan"
            count = 0

            try:
                result = await regional_contracts_client.search_regional_ckan(
                    region=reg,
                    query=query,
                    page=page,
                )
                datasets = result.get("results", [])
                count = result.get("count", 0)
                source = "regional_ckan"
            except Exception:
                pass  # Fall through to datos.gob.es

            # Fall back to datos.gob.es if regional portal failed or returned nothing
            if not datasets:
                try:
                    result = await regional_contracts_client.search_datos_gob_by_region(
                        region=reg,
                        query=query,
                        page=page,
                    )
                    datasets = result.get("results", [])
                    count = result.get("count", 0)
                    source = "datos_gob_es"
                except Exception as e:  # noqa: BLE001
                    content_parts.append(f"Error searching {portal_name}: {e}")
                    content_parts.append("")
                    continue

            if not datasets:
                content_parts.append(
                    f"No procurement datasets found for '{query}' in {portal_name}.\n"
                )
                continue

            any_results = True
            source_label = (
                "regional portal" if source == "regional_ckan" else "datos.gob.es"
            )
            content_parts.append(
                f"Found {count} dataset(s) via {source_label} (page {page}, showing {len(datasets)}):\n"
            )
            content_parts.extend(_format_datasets(datasets, portal_name, source))

        if not any_results:
            regions_str = "all communities" if region == "all" else region
            content_parts.append(
                f"\nNo results found for '{query}' in {regions_str}.\n"
                "Try broader terms: 'contratos', 'licitaciones', or 'adjudicaciones'.\n"
                "For live tenders, use search_public_contracts(source='feed')."
            )

        content_parts.append("=" * 60)
        content_parts.append(
            "National procurement platform: https://contrataciondelestado.es\n"
            "National open data catalog: https://datos.gob.es"
        )
        content_parts.append(source_footer(_urls))
        return "\n".join(content_parts)
