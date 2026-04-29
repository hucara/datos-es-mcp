"""
Client for the Eurostat Statistics API.

Provides access to EU-wide statistical data, enabling cross-country comparisons
for Spain vs EU averages. Crucial for verifying claims like "Spain grew at double
the EU average" or "best reduction in fossil fuel dependence in the EU."

API docs: https://ec.europa.eu/eurostat/web/user-guides/data-browser/api-data-access
Base URL: https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data/{dataset_code}

No authentication required. Returns JSON-stat format.

Key dataset codes for political claim verification:
  Economy & Finance:
    nama_10_gdp       — GDP and main components (current prices)
    tec00001          — Real GDP growth rate (%)
    sdg_08_10         — Real GDP per capita growth
    earn_eses_annual  — Gross earnings, annual
    prc_hicp_manr     — HICP — monthly annual rate of change (inflation)
    prc_hicp_aind     — HICP — annual data (average index)
    gov_10dd_edpt1    — Government deficit/surplus (% of GDP)
    gov_10a_main      — Government revenue, expenditure, deficit (% of GDP)
  Labour Market:
    une_rt_m          — Unemployment rates monthly (%)
    une_rt_a          — Unemployment rates annual (%)
    lfsq_ergan        — Employment rates by sex, age, nationality (quarterly)
    lfsa_ergan        — Employment rates annual
  Housing:
    prc_hpi_a         — House price index (annual)
    prc_hpi_q         — House price index (quarterly)
  Energy:
    nrg_ind_ren       — Share of renewables in gross final energy consumption
    nrg_bal_c         — Energy balance and energy indicators
    nrg_d_hhq         — Household energy prices (gas, electricity)
    nrg_pc_202        — Electricity prices for non-household consumers
  Purchasing Power & Wages:
    earn_mw_avgr2     — Mean and median earnings
    spr_exp_sum       — Social protection expenditure
"""

import logging
from typing import Any

import httpx

from helpers.http import fetch_json
from helpers.logging import MAIN_LOGGER_NAME
from helpers.user_agent import USER_AGENT

logger = logging.getLogger(MAIN_LOGGER_NAME)

_BASE_URL = "https://ec.europa.eu/eurostat/api/dissemination/statistics/1.0/data"

# Curated map of topic → (dataset_code, description, useful_filters)
DATASET_CATALOG: dict[str, dict] = {
    "gdp_growth": {
        "code": "sdg_08_10",
        "description": "Real GDP per capita growth rate (%)",
        "unit": "CLV_PCH_PRE_HAB",
        "note": "Annual % change in real GDP per capita. Compare Spain (ES) vs EU27 (EU27_2020).",
    },
    "gdp_per_capita": {
        "code": "tec00114",
        "description": "GDP per capita in PPS as % of EU average (EU27_2020=100)",
        "note": "Spain typically 91-92 (gap ~8-9pp vs EU average of 100). Use for convergence/gap claims. geo=ES,EU27_2020,DE,FR",
        "extra_defaults": {"indic_ppp": "VI_PPS_EU27_2020_HAB", "ppp_cat18": "GDP"},
    },
    "inflation_hicp": {
        "code": "prc_hicp_manr",
        "description": "HICP inflation — monthly annual rate of change (%)",
        "unit": "RCH_A",
        "note": "Harmonised Consumer Price Index (equivalent to CPI). Monthly data.",
        "extra_defaults": {"coicop": "CP00"},
    },
    "inflation_annual": {
        "code": "prc_hicp_aind",
        "description": "HICP — annual average index (2015=100)",
        "unit": "INX_A_AVG",
        "note": "Annual average HICP index. Good for multi-year comparisons.",
    },
    "unemployment": {
        "code": "une_rt_a",
        "description": "Unemployment rate — annual (%)",
        "unit": "PC_ACT",
        "note": "Annual unemployment rate. age=TOTAL, sex=T.",
    },
    "employment_rate": {
        "code": "lfsi_emp_a",
        "description": "Employment rate — annual (%)",
        "unit": "PC_POP",
        "note": "% of working-age population (20–64) in employment.",
        "extra_defaults": {"sex": "T", "age": "Y20-64"},
    },
    "house_prices": {
        "code": "prc_hpi_a",
        "description": "House price index — annual (2015=100)",
        "unit": "I15_A_AVG",
        "note": "Residential property price index. Key for housing affordability claims.",
    },
    "renewable_share": {
        "code": "nrg_ind_ren",
        "description": "Share of renewable energy in gross final energy consumption (%)",
        "unit": "PC",
        "note": "Overall renewable % including electricity, heating, transport.",
    },
    "electricity_prices_households": {
        "code": "nrg_d_hhq",
        "description": "Electricity prices for household consumers",
        "unit": "KWH",
        "note": "Household electricity prices in EUR/kWh.",
    },
    "electricity_prices_industry": {
        "code": "nrg_pc_204",
        "description": "Electricity prices for non-household consumers (industry/SMEs)",
        "unit": "KWH",
        "note": "Industrial/SME electricity prices. Useful for competitiveness claims.",
    },
    "government_debt": {
        "code": "gov_10dd_edpt1",
        "description": "Government consolidated gross debt (% of GDP)",
        "unit": "PC_GDP",
        "note": "Maastricht debt criterion.",
    },
    "government_deficit": {
        "code": "gov_10dd_edpt1",
        "description": "Government deficit/surplus (% of GDP)",
        "unit": "PC_GDP",
        "note": "Net lending (+) / net borrowing (-) as % of GDP. Negative = deficit.",
        "extra_defaults": {"na_item": "B9", "sector": "S13"},
    },
    "wages": {
        "code": "earn_nt_net",
        "description": "Annual net earnings",
        "note": "Annual net earnings in EUR. For wage evolution and purchasing-power claims.",
        "extra_defaults": {"currency": "EUR", "estruct": "NET"},
    },
    "poverty_inequality": {
        "code": "ilc_di12",
        "description": "Gini coefficient of equivalised disposable income",
        "note": "Income inequality metric. Lower = more equal.",
        "extra_defaults": {"statinfo": "GINI_HND", "age": "TOTAL"},
    },
    "fossil_fuel_imports": {
        "code": "nrg_ti_eh",
        "description": "Energy imports by product",
        "unit": "TJ",
        "note": "Track reduction in fossil fuel import dependency.",
    },
    "tax_burden": {
        "code": "gov_10a_main",
        "description": "Total government revenue (taxes + social contributions, % of GDP)",
        "unit": "PC_GDP",
        "note": "Total receipts (na_item=TR). Spain ~37-38%, EU27 ~45%, DE ~44%, FR ~52%.",
        "extra_defaults": {"na_item": "TR", "sector": "S13"},
    },
    "gdp_pps_per_capita": {
        "code": "sdg_10_10",
        "description": "GDP per capita in PPS as volume index (EU27=100)",
        "unit": "PC",
        "note": "Spain typically 91-92 (gap ~8-9pp vs EU average of 100).",
        "extra_defaults": {"indic_ppp": "VI_PPS_EU27_2020_HAB", "ppp_cat18": "GDP"},
    },
}


async def get_dataset(
    dataset_code: str,
    geo: list[str] | None = None,
    since_period: str | None = None,
    until_period: str | None = None,
    last_n_periods: int | None = None,
    filters: dict[str, str] | None = None,
    lang: str = "EN",
    session: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """
    Fetch data from a Eurostat dataset.

    Args:
        dataset_code: Eurostat dataset code (e.g. "tec00001", "prc_hicp_manr").
        geo: List of geo codes to include (e.g. ["ES", "EU27_2020", "DE", "FR"]).
             Defaults to Spain + EU27 if not provided.
        since_period: Start period (e.g. "2018", "2018-01").
        until_period: End period (e.g. "2025", "2025-12").
        last_n_periods: Return only the last N periods.
        filters: Additional dimension filters as dict (e.g. {"unit": "PC_GDP", "sex": "T"}).
        lang: Response language ("EN" or "FR").

    Returns:
        JSON-stat formatted response dict.
    """
    own = session is None
    if own:
        session = httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
    assert session is not None
    try:
        url = f"{_BASE_URL}/{dataset_code}"

        params: dict[str, Any] = {"lang": lang, "format": "JSON"}

        # Geographic filter — default to Spain + EU27
        geos = geo or ["ES", "EU27_2020"]
        for g in geos:
            params.setdefault("geo", [])
            if isinstance(params["geo"], list):
                params["geo"].append(g)
            else:
                params["geo"] = [params["geo"], g]

        if since_period:
            params["sinceTimePeriod"] = since_period
        if until_period:
            params["untilTimePeriod"] = until_period
        if last_n_periods:
            params["lastTimePeriod"] = last_n_periods

        if filters:
            params.update(filters)

        # httpx handles list params as repeated keys
        return await fetch_json(
            session, url, log_prefix="Eurostat", timeout=30.0, params=params
        )
    finally:
        if own:
            await session.aclose()


def parse_jsonstat(data: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Parse a Eurostat JSON-stat response into a flat list of records.

    Returns:
        List of dicts with geo, time, and value keys (plus any other dimensions).
    """
    dims = data.get("dimension") or {}
    values = data.get("value") or {}
    size = data.get("size") or []
    ids = data.get("id") or []

    if not dims or not values or not size or not ids:
        return []

    # Build dimension label maps
    dim_labels: dict[str, dict] = {}
    for dim_id in ids:
        dim_info = dims.get(dim_id) or {}
        cat = dim_info.get("category") or {}
        label_map = cat.get("label") or {}
        index_map = cat.get("index") or {}
        # index_map: code → position
        if isinstance(index_map, dict):
            # reverse to position → code
            pos_to_code = {v: k for k, v in index_map.items()}
        else:
            pos_to_code = {i: c for i, c in enumerate(index_map)}
        dim_labels[dim_id] = {
            "pos_to_code": pos_to_code,
            "code_to_label": label_map,
        }

    # Iterate over all dimension combinations
    records = []
    total = 1
    for s in size:
        total *= s

    for flat_idx in range(total):
        # Decode position to dimension indices
        idx = flat_idx
        dim_indices = []
        for s in reversed(size):
            dim_indices.append(idx % s)
            idx //= s
        dim_indices.reverse()

        record: dict[str, Any] = {}
        for i, dim_id in enumerate(ids):
            dl = dim_labels[dim_id]
            code = dl["pos_to_code"].get(dim_indices[i], str(dim_indices[i]))
            label = dl["code_to_label"].get(code, code)
            record[dim_id] = code
            record[f"{dim_id}_label"] = label

        val = values.get(str(flat_idx))
        record["value"] = val
        records.append(record)

    return [r for r in records if r.get("value") is not None]
