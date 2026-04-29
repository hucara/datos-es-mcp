"""
Client for AIReF (Autoridad Independiente de Responsabilidad Fiscal) data.

AIReF is Spain's independent fiscal watchdog. It does NOT have a machine-readable
API and is not registered as a publisher on datos.gob.es.

AIReF publishes:
  - Macroeconomic and fiscal forecasts (GDP growth, deficit, debt)
  - Spending reviews (evaluación del gasto público)
  - Public debt sustainability analysis
  - CCAA and local-authority fiscal observatories
  - Immigration's contribution to GDP growth
  - Fiscal drag (progresividad del sistema fiscal) analysis

Data portal: https://www.airef.es/en/data-access/
Historical forecasts: https://www.airef.es/en/historical-macroeconomic-forecast/
All reports: https://www.airef.es/en/all-reports/

Because there is no structured API, this client searches datos.gob.es for
related fiscal-responsibility datasets and returns AIReF's own portal URLs
for the authoritative source.
"""

import logging
from typing import Any

import httpx

from helpers import datos_gob_es_client
from helpers.logging import MAIN_LOGGER_NAME

logger = logging.getLogger(MAIN_LOGGER_NAME)

# AIReF portal URLs for each topic area
AIREF_PORTAL = "https://www.airef.es/en/data-access/"
AIREF_REPORTS = "https://www.airef.es/en/all-reports/"
AIREF_FORECASTS = "https://www.airef.es/en/historical-macroeconomic-forecast/"
AIREF_SPENDING_REVIEW = "https://www.airef.es/en/evaluations-spending-review-2022-2026/"
AIREF_DEBT = "https://www.airef.es/en/public-debt-monitor/"
AIREF_CCAA = "https://www.airef.es/en/datalab/ccll-lab-en/"

# Curated topic registry
TOPIC_REGISTRY: dict[str, dict[str, str]] = {
    "previsiones": {
        "query": "previsiones macroeconómicas crecimiento PIB deficit fiscales",
        "description": "AIReF macroeconomic and fiscal forecasts — GDP growth, deficit, debt trajectory",
        "airef_url": AIREF_FORECASTS,
        "notes": (
            "AIReF publishes historical and current macroeconomic forecasts as Excel files "
            "at https://www.airef.es/en/historical-macroeconomic-forecast/. "
            "For immigration's share of GDP growth, see their quarterly GDP reports. "
            "For fiscal drag (progresividad / bracket creep), see the annual recaudación "
            "reports cross-referenced with AEAT's Informe de Recaudación Tributaria."
        ),
    },
    "sostenibilidad_fiscal": {
        "query": "sostenibilidad fiscal deuda publica regla de gasto estabilidad presupuestaria",
        "description": "Fiscal sustainability, public debt rule compliance and budget stability reports",
        "airef_url": AIREF_DEBT,
        "notes": (
            "AIReF's debt sustainability analysis is published in its Informe de "
            "Ejecución Presupuestaria, Deuda Pública y Regla de Gasto (annual). "
            "The interactive Public Debt Monitor is at https://www.airef.es/en/public-debt-monitor/."
        ),
    },
    "spending_review": {
        "query": "evaluacion gasto publico eficiencia inversion publica programas",
        "description": "Spending reviews — public expenditure efficiency evaluations by programme",
        "airef_url": AIREF_SPENDING_REVIEW,
        "notes": (
            "AIReF's Spending Review 2022-2026 covers education, healthcare, pensions, "
            "housing subsidies, disability benefits and official development aid. "
            "Full methodology and microdata are published as PDFs and Excel files."
        ),
    },
    "inmigracion_pib": {
        "query": "inmigracion crecimiento economico PIB contribucion extranjeros poblacion",
        "description": "Immigration's contribution to Spanish GDP growth and labour market",
        "airef_url": AIREF_FORECASTS,
        "notes": (
            "AIReF estimated that foreign population accounted for ~3.4 of the 9 pp "
            "GDP growth between 2022-2025 (>one third). See their quarterly forecast "
            "updates and the METCAP regional GDP model. "
            "Cross-reference with INE Padrón, SEPE afiliados extranjeros, and "
            "Seguridad Social data via get_social_security_stats(stat_type='inmigracion')."
        ),
    },
    "fiscal_drag": {
        "query": "progresividad fiscal recaudacion bracket creep IRPF inflacion",
        "description": "Fiscal drag (bracket creep) — inflation-driven tax revenue increases",
        "airef_url": AIREF_REPORTS,
        "notes": (
            "AIReF has analysed fiscal drag (ilusión fiscal / progresividad en frío) "
            "in the context of IRPF and social contributions. "
            "The authoritative dataset for the 40% fiscal-drag claim is AEAT's "
            "Informe de Recaudación Tributaria — use get_aeat_stats(stat_type='recaudacion'). "
            "AIReF's report 'Actualización de Previsiones Macroeconómicas y Fiscales' "
            "provides the breakdown of revenue increase by tax type and cycle component."
        ),
    },
    "observatorio_ccaa": {
        "query": "comunidades autonomas objetivo deficit liquidacion presupuestaria CCAA",
        "description": "Autonomous communities fiscal observatory — deficit targets and budget execution",
        "airef_url": AIREF_CCAA,
        "notes": (
            "AIReF's CCAA Observatory provides fiscal and macroeconomic data for all "
            "17 autonomous communities. The interactive tool and downloadable data "
            "are at https://www.airef.es/en/data-access/interactive-tools/."
        ),
    },
}


async def search_airef_related_datasets(
    topic: str = "previsiones",
    custom_query: str | None = None,
    page: int = 1,
    page_size: int = 10,
    session: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """
    Search datos.gob.es for datasets related to AIReF's areas of analysis.

    Since AIReF has no public API or datos.gob.es publisher entry, this returns
    related datasets from datos.gob.es (mostly from Hacienda and INE) plus
    direct links to AIReF's own data portal for the authoritative source.

    Args:
        topic: Analysis area. See TOPIC_REGISTRY for valid values.
        custom_query: Override the curated query with a free-text search.
        page: Page number (1-based).
        page_size: Results per page.

    Returns:
        dict with "results", "count", "page", "page_size",
        "topic_info" (description + AIReF URL + guidance notes).
    """
    entry = TOPIC_REGISTRY.get(topic, TOPIC_REGISTRY["previsiones"])
    query = custom_query or entry["query"]

    own = session is None
    if own:
        import httpx as _httpx

        from helpers.user_agent import USER_AGENT

        session = _httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
    assert session is not None

    try:
        raw = await datos_gob_es_client.search_datasets(
            query=query,
            page=page,
            page_size=page_size,
            session=session,
        )
        results = raw.get("results", [])

        return {
            "results": results,
            "count": raw.get("count", len(results)),
            "page": page,
            "page_size": len(results),
            "topic_info": {
                "topic": topic,
                "description": entry["description"],
                "airef_url": entry["airef_url"],
                "notes": entry["notes"],
            },
        }
    finally:
        if own:
            await session.aclose()
