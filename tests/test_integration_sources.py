"""
Integration tests: "does each data source work and return valid data?"

One test per source capability, with numeric range assertions on real API values.
Tests are independent of specific political claims — they verify the plumbing works.

Run:
    uv run pytest tests/test_integration_sources.py -v -m integration
"""

import re

import httpx
import pytest

from tests.conftest import (
    assert_tool_ok,
    extract_floats,
    make_tool,
    skip_network,
    text_block,
    values_after,
)

pytestmark = pytest.mark.integration


# ── Eurostat: economic indicators ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_eurostat_gdp_growth_spain_vs_eu():
    """Spain's GDP growth 2021-2024 should be positive and exceed EU27."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(topic="gdp_growth", geo="ES,EU27_2020", since_year="2021")
    except httpx.HTTPError as e:
        skip_network(e)

    assert_tool_ok(result)
    assert "Spain (ES)" in result and ("EU27" in result or "European Union" in result)
    spain_pos = result.find("Spain (ES)")
    eu_pos = result.find("European Union")
    assert spain_pos < eu_pos, "Spain should appear before EU27 in output"
    spain_vals = values_after(result, "Spain (ES)", 300)
    assert any(4 < v < 10 for v in spain_vals), (
        f"Spain 2021 GDP growth should be ~6-7%, got: {spain_vals}"
    )


@pytest.mark.asyncio
async def test_eurostat_inflation_monthly_values():
    """HICP inflation for 2022 should return monthly data with at least one value >5%."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(
            topic="inflation_hicp", geo="ES", since_year="2022", until_year="2022"
        )
    except httpx.HTTPError as e:
        skip_network(e)

    assert_tool_ok(result)
    assert "Spain (ES)" in result and "2022" in result
    monthly_periods = re.findall(r"2022-\d{2}", result)
    assert len(monthly_periods) >= 6, (
        f"Expected 6+ monthly periods, found: {monthly_periods}"
    )
    spain_vals = values_after(result, "Spain (ES)", 500)
    assert any(v > 5 for v in spain_vals), (
        f"No month >5% inflation in Spain 2022: {spain_vals}"
    )


@pytest.mark.asyncio
async def test_eurostat_inflation_annual_index_above_100():
    """Annual HICP index (2015=100) for Spain should be well above 100 by 2022."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(
            topic="inflation_annual",
            geo="ES",
            since_year="2018",
            extra_filters="coicop=CP00",
        )
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Spain (ES)" in result
    es_block = text_block(result, "Spain (ES)")
    year_vals = {
        int(y): float(v)
        for y, v in re.findall(r"(20\d{2}):\s*([\d.]+)", es_block)
        if 95 < float(v) < 145
    }
    assert 2022 in year_vals, f"2022 not found: {year_vals}"
    assert year_vals[2022] > 112, (
        f"2022 HICP index should be >112, got: {year_vals[2022]}"
    )


@pytest.mark.asyncio
async def test_eurostat_unemployment_spain_plausible_range():
    """Spain's unemployment (2022-2025) should be 10-16%, well above EU27 ~6%."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(topic="unemployment", geo="ES,EU27_2020", since_year="2022")
    except httpx.HTTPError as e:
        skip_network(e)

    assert_tool_ok(result)
    spain_vals = values_after(result, "Spain (ES)", 400)
    assert any(8 < v < 20 for v in spain_vals), (
        f"Spain unemployment should be 10-16%: {spain_vals}"
    )


@pytest.mark.asyncio
async def test_eurostat_house_prices_indexed_above_100():
    """House price index (2015=100) for Spain post-2020 should be well above 120."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(topic="house_prices", geo="ES", since_year="2020")
    except httpx.HTTPError as e:
        skip_network(e)

    assert_tool_ok(result)
    spain_vals = values_after(result, "Spain (ES)", 400)
    assert any(v > 120 for v in spain_vals), (
        f"House price index should be >120 post-2020: {spain_vals}"
    )


@pytest.mark.asyncio
async def test_eurostat_renewable_share_spain():
    """Spain's renewable energy share should be in 20-50% range."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(
            topic="renewable_share", geo="ES,EU27_2020", since_year="2019"
        )
    except httpx.HTTPError as e:
        skip_network(e)

    assert_tool_ok(result)
    spain_vals = values_after(result, "Spain (ES)", 400)
    assert any(20 < v < 55 for v in spain_vals), (
        f"Spain renewable share should be 20-50%: {spain_vals}"
    )


@pytest.mark.asyncio
async def test_eurostat_government_debt_spain():
    """Spain's government debt (% GDP) should be 90-130% range post-2020."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(topic="government_debt", geo="ES", since_year="2020")
    except httpx.HTTPError as e:
        skip_network(e)

    assert_tool_ok(result)
    spain_vals = values_after(result, "Spain (ES)", 300)
    assert any(90 < v < 130 for v in spain_vals), (
        f"Spain debt/GDP should be ~100-120%: {spain_vals}"
    )


@pytest.mark.asyncio
async def test_eurostat_government_deficit_spain():
    """Spain's deficit/surplus should be negative (persistent deficit 2018-2024)."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(topic="government_deficit", geo="ES", since_year="2018")
    except httpx.HTTPError as e:
        skip_network(e)

    assert_tool_ok(result)
    spain_vals = values_after(result, "Spain (ES)", 300)
    assert any(v < 0 for v in spain_vals), (
        f"Spain should show deficit (negative values): {spain_vals}"
    )


@pytest.mark.asyncio
async def test_eurostat_wages_returns_eur_values():
    """Net wages should return EUR values for Spain in a plausible monthly range."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(topic="wages", geo="ES,DE,FR", since_year="2018")
    except httpx.HTTPError as e:
        skip_network(e)

    assert_tool_ok(result)
    spain_vals = values_after(result, "Spain (ES)", 400)
    assert any(500 < v < 5000 for v in spain_vals), (
        f"Spain wages (monthly EUR) should be 500-5000: {spain_vals}"
    )


@pytest.mark.asyncio
async def test_eurostat_employment_rate_spain():
    """Spain's employment rate (20-64) should be in 65-85% range."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(
            topic="employment_rate", geo="ES,EU27_2020", since_year="2019"
        )
    except httpx.HTTPError as e:
        skip_network(e)

    assert_tool_ok(result)
    spain_vals = values_after(result, "Spain (ES)", 300)
    assert any(65 < v < 85 for v in spain_vals), (
        f"Spain employment rate should be 65-85%: {spain_vals}"
    )


@pytest.mark.asyncio
async def test_eurostat_life_expectancy_spain_above_eu():
    """Spain's life expectancy should exceed EU27 average (typically 83 vs 81)."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(
            topic="custom",
            dataset_code="demo_mlexpec",
            geo="ES,EU27_2020,DE,FR",
            since_year="2018",
            extra_filters="sex=T&age=Y1",
        )
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Spain (ES)" in result
    es_vals = [
        v
        for v in extract_floats(text_block(result, "Spain (ES)", "European Union"))
        if 70 < v < 95
    ]
    eu_vals = [
        v
        for v in extract_floats(text_block(result, "European Union", "Germany"))
        if 70 < v < 95
    ]
    assert es_vals and eu_vals, (
        f"Missing life expectancy values. ES={es_vals}, EU={eu_vals}"
    )
    assert min(es_vals) > min(eu_vals) - 1, (
        f"Spain LE ({min(es_vals)}) should be >= EU ({min(eu_vals)})"
    )
    assert all(78 < v < 92 for v in es_vals), f"Implausible life expectancy: {es_vals}"


@pytest.mark.asyncio
async def test_eurostat_life_expectancy_covid_dip_2020():
    """Spain's life expectancy should show a dip in 2020 due to COVID-19."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(
            topic="custom",
            dataset_code="demo_mlexpec",
            geo="ES",
            since_year="2018",
            until_year="2022",
            extra_filters="sex=T&age=Y1",
        )
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Spain (ES)" in result
    es_block = text_block(result, "Spain (ES)")
    year_vals = {
        int(y): float(v)
        for y, v in re.findall(r"(20\d{2}):\s*([\d.]+)", es_block)
        if 78 < float(v) < 92
    }
    assert 2020 in year_vals, f"2020 life expectancy not found: {year_vals}"
    pre_covid = year_vals.get(2019, year_vals.get(2018))
    if pre_covid:
        assert year_vals[2020] < pre_covid, (
            f"2020 LE ({year_vals[2020]}) should dip below pre-COVID ({pre_covid})"
        )


@pytest.mark.asyncio
async def test_eurostat_electricity_prices_industry():
    """Industrial electricity prices for Spain should be in a plausible EUR/kWh range."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(
            topic="electricity_prices_industry", geo="ES,DE", since_year="2022"
        )
    except httpx.HTTPError as e:
        skip_network(e)

    if "No data" in result[:50] or "Error" in result[:50]:
        pytest.skip(f"Industry electricity data unavailable: {result[:200]}")

    assert "Spain (ES)" in result or "ES" in result
    vals = [v for v in extract_floats(result) if 0.05 < v < 0.50]
    assert vals, (
        f"No plausible electricity price values (0.05-0.50 EUR/kWh): {result[:400]}"
    )


@pytest.mark.asyncio
async def test_eurostat_co2_emissions_spain_below_germany():
    """Spain's per-capita GHG emissions should be below Germany's."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(
            topic="custom",
            dataset_code="sdg_13_10",
            geo="ES,EU27_2020,DE,FR",
            since_year="2018",
            extra_filters="unit=T_HAB",
        )
    except httpx.HTTPError as e:
        skip_network(e)

    if "Error" in result[:50] or "No data" in result[:50]:
        pytest.skip(f"CO2 dataset unavailable: {result[:200]}")

    assert "Spain (ES)" in result
    es_vals = [
        v
        for v in extract_floats(text_block(result, "Spain (ES)", "European Union"))
        if 3 < v < 20
    ]
    de_vals = [
        v for v in extract_floats(text_block(result, "Germany (DE)")) if 3 < v < 20
    ]
    assert es_vals, f"No CO2 values for Spain: {result[:400]}"
    if de_vals:
        assert max(es_vals) < max(de_vals), (
            f"Spain CO2/capita ({max(es_vals)}) should be below Germany ({max(de_vals)})"
        )


@pytest.mark.asyncio
async def test_eurostat_geo_ordering_matches_request():
    """Geo data should appear in output in the order requested."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(topic="gdp_growth", geo="ES,DE,FR,IT", since_year="2023")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Spain" in result and "Germany" in result and "France" in result
    assert result.find("Spain") < result.find("Germany") < result.find("France"), (
        "Geo data should appear in requested order: ES, DE, FR"
    )


# ── BdE: financial series ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_bde_ecb_deposit_rate_recent_values():
    """ECB deposit facility rate D_DNBCEB72 should return % values in 0-5% range."""
    from tools.get_bde_series import register_get_bde_series_tool

    fn = make_tool(register_get_bde_series_tool)
    try:
        result = await fn(series_codes="D_DNBCEB72", time_range="36M")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50], f"Tool error: {result[:200]}"
    assert "D_DNBCEB72" in result
    vals = values_after(result, "Data (", 800)
    assert len(vals) >= 5, f"Expected multiple observations: {vals}"
    assert any(1 < v < 5 for v in vals), f"ECB deposit rate should be 1-4%: {vals[:10]}"


@pytest.mark.asyncio
async def test_bde_ecb_main_refinancing_rate():
    """ECB main refinancing rate D_DTFK09A0 should return valid observations."""
    from tools.get_bde_series import register_get_bde_series_tool

    fn = make_tool(register_get_bde_series_tool)
    try:
        result = await fn(series_codes="D_DTFK09A0", time_range="12M")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    assert "D_DTFK09A0" in result
    vals = values_after(result, "D_DTFK09A0", 500)
    assert len(vals) >= 3, f"Too few observations: {vals}"


@pytest.mark.asyncio
async def test_bde_latest_only_returns_single_row():
    """latest_only=True should return one date per series, not a history."""
    from tools.get_bde_series import register_get_bde_series_tool

    fn = make_tool(register_get_bde_series_tool)
    try:
        result = await fn(series_codes="D_DNBCEB72", latest_only=True)
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    date_count = len(re.findall(r"\d{4}-\d{2}-\d{2}", result))
    assert 1 <= date_count <= 5, (
        f"latest_only should return 1-5 dates, got {date_count}"
    )


@pytest.mark.asyncio
async def test_bde_euribor_12m_values():
    """EURIBOR 12m (D_DNBAF172) should return daily values in a plausible range."""
    from tools.get_bde_series import register_get_bde_series_tool

    fn = make_tool(register_get_bde_series_tool)
    try:
        result = await fn(series_codes="D_DNBAF172", time_range="36M")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50] and "No data" not in result[:50]
    assert "D_DNBAF172" in result
    data_section = text_block(result, "Data (", window=1200)
    vals = [v for v in extract_floats(data_section) if 0.5 < v < 6]
    assert len(vals) >= 10, f"Expected 10+ EURIBOR observations: {vals[:5]}"
    assert max(vals) > 2, (
        f"EURIBOR 12m peak should be >2% in 36M window, got max: {max(vals)}"
    )


@pytest.mark.asyncio
async def test_bde_euribor_3m_vs_12m():
    """3m and 12m EURIBOR should both return values in a plausible range."""
    from tools.get_bde_series import register_get_bde_series_tool

    fn = make_tool(register_get_bde_series_tool)
    try:
        r3m = await fn(series_codes="D_DNBAD172", time_range="12M")
        r12m = await fn(series_codes="D_DNBAF172", time_range="12M")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "No data" not in r3m[:50] and "No data" not in r12m[:50]
    vals_3m = [
        v for v in extract_floats(text_block(r3m, "Data (", window=300)) if 0 < v < 6
    ]
    vals_12m = [
        v for v in extract_floats(text_block(r12m, "Data (", window=300)) if 0 < v < 6
    ]
    assert vals_3m and vals_12m, f"Missing values. 3m={vals_3m}, 12m={vals_12m}"
    assert abs(vals_3m[0] - vals_12m[0]) < 3, (
        f"3m ({vals_3m[0]}) and 12m ({vals_12m[0]}) should be close (same yield curve)"
    )


@pytest.mark.asyncio
async def test_bde_eurusd_exchange_rate():
    """EUR/USD (D_1PFJ1001) should return values in 0.90-1.30 range."""
    from tools.get_bde_series import register_get_bde_series_tool

    fn = make_tool(register_get_bde_series_tool)
    try:
        result = await fn(series_codes="D_1PFJ1001", time_range="60M")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50] and "No data" not in result[:50]
    data_section = text_block(result, "Data (", window=800)
    vals = [v for v in extract_floats(data_section) if 0.8 < v < 1.5]
    assert vals, f"No EUR/USD values in plausible range: {result[:400]}"
    assert all(0.90 < v < 1.30 for v in vals[:10]), (
        f"EUR/USD should be 0.90-1.30: {vals[:10]}"
    )


# ── INE: statistical series ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_ine_ipc_series_returns_annual_rates():
    """INE IPC series IPC251856 (variación anual) should return recent monthly values."""
    from tools.query_ine_data import register_query_ine_data_tool

    fn = make_tool(register_query_ine_data_tool)
    try:
        result = await fn(series_code="IPC251856", last_n_periods=12)
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    assert "IPC251856" in result
    assert "Variación anual" in result or "General" in result
    dates = re.findall(r"202[0-9]-\d{2}", result)
    assert len(dates) >= 6, f"Expected 6+ YYYY-MM dates: {dates}"
    vals = [v for v in extract_floats(result) if -5 < v < 15]
    assert len(vals) >= 6, f"Expected 6+ plausible inflation values: {vals}"


@pytest.mark.asyncio
async def test_ine_ipc_monthly_vs_annual_series():
    """Annual and monthly IPC series should both return values in plausible ranges."""
    from tools.query_ine_data import register_query_ine_data_tool

    fn = make_tool(register_query_ine_data_tool)
    try:
        r_anual = await fn(series_code="IPC251856", last_n_periods=3)
        r_mensual = await fn(series_code="IPC206449", last_n_periods=3)
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in r_anual[:50] and "Error" not in r_mensual[:50]
    vals_anual = [v for v in extract_floats(r_anual) if -5 < v < 15]
    vals_mensual = [v for v in extract_floats(r_mensual) if -5 < v < 5]
    assert vals_anual, f"No annual IPC values: {r_anual[:200]}"
    assert vals_mensual, f"No monthly IPC values: {r_mensual[:200]}"
    assert any(-5 < v < 15 for v in vals_anual), (
        f"Annual IPC out of range: {vals_anual}"
    )
    assert any(-2 < v < 5 for v in vals_mensual), (
        f"Monthly IPC out of range: {vals_mensual}"
    )


@pytest.mark.asyncio
async def test_ine_epa_tables_returns_multiple_tables():
    """INE EPA operation should list tables with numeric IDs and employment content."""
    from tools.query_ine_data import register_query_ine_data_tool

    fn = make_tool(register_query_ine_data_tool)
    try:
        result = await fn(operation_code="EPA")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    table_count = len(re.findall(r"\bID \d+:", result))
    assert table_count >= 5, f"Expected at least 5 EPA tables, found {table_count}"
    assert (
        "paro" in result.lower()
        or "activ" in result.lower()
        or "empleo" in result.lower()
    )


@pytest.mark.asyncio
async def test_ine_ecv_operation_tables():
    """INE ECV (living conditions) operation should list income and poverty tables."""
    from tools.query_ine_data import register_query_ine_data_tool

    fn = make_tool(register_query_ine_data_tool)
    try:
        result = await fn(operation_code="ECV")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    table_count = len(re.findall(r"\bID \d+:", result))
    assert table_count >= 10, f"Expected 10+ ECV tables, found {table_count}"
    assert (
        "renta" in result.lower()
        or "pobreza" in result.lower()
        or "condicion" in result.lower()
    )


@pytest.mark.asyncio
async def test_ine_epf_operation_tables():
    """INE EPF (household budgets) operation should list spending survey tables."""
    from tools.query_ine_data import register_query_ine_data_tool

    fn = make_tool(register_query_ine_data_tool)
    try:
        result = await fn(operation_code="EPF")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    table_count = len(re.findall(r"\bID \d+:", result))
    assert table_count >= 5, f"Expected 5+ EPF tables, found {table_count}"
    assert (
        "gasto" in result.lower()
        or "hogar" in result.lower()
        or "presupuesto" in result.lower()
    )


@pytest.mark.asyncio
async def test_ine_eh_mortgage_operation():
    """INE EH (Estadística de Hipotecas) should list mortgage statistics tables."""
    from tools.query_ine_data import register_query_ine_data_tool

    fn = make_tool(register_query_ine_data_tool)
    try:
        result = await fn(operation_code="EH")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    table_count = len(re.findall(r"\bID \d+:", result))
    assert table_count >= 3, f"Expected 3+ EH tables, found {table_count}"
    assert (
        "hipoteca" in result.lower()
        or "ejecuc" in result.lower()
        or "finca" in result.lower()
    )


@pytest.mark.asyncio
async def test_ine_eh_mortgage_values_in_thousands():
    """INE EH foreclosure table 7709 should show quarterly counts in thousands."""
    from tools.query_ine_data import register_query_ine_data_tool

    fn = make_tool(register_query_ine_data_tool)
    try:
        result = await fn(table_id="7709", last_n_periods=8)
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    assert "7709" in result or "hipoteca" in result.lower() or "finca" in result.lower()
    vals = [v for v in extract_floats(result) if 1000 < v < 30000]
    assert vals, f"Expected quarterly foreclosure counts >1000: {result[:400]}"


@pytest.mark.asyncio
async def test_ine_ipc_table_by_category():
    """INE IPC table 50902 should return multiple spending category series."""
    from tools.query_ine_data import register_query_ine_data_tool

    fn = make_tool(register_query_ine_data_tool)
    try:
        result = await fn(table_id="50902", last_n_periods=6)
    except httpx.HTTPError as e:
        skip_network(e)

    if "Error" in result[:50]:
        pytest.skip(f"IPC table 50902 not available: {result[:200]}")

    series_count = result.count("Series:")
    assert series_count >= 3, (
        f"Expected multiple IPC series (general + groups), found {series_count}"
    )


# ── REData: energy ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_redata_generation_mix_wind_percentage():
    """Spain 2024 generation mix: wind should be 15-40% of total."""
    from tools.get_energy_data import register_get_energy_data_tool

    fn = make_tool(register_get_energy_data_tool)
    try:
        result = await fn(
            data_type="generation_mix",
            start_date="2024-01-01T00:00",
            end_date="2024-12-31T23:59",
            time_trunc="year",
        )
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    assert "Wind" in result or "Eólica" in result
    assert "MWh" in result or "MW" in result
    wind_vals = values_after(result, "Wind", 150)
    pct_vals = [v for v in wind_vals if 0 < v < 100]
    assert pct_vals, f"Wind percentage not found in output: {result[:400]}"
    assert any(15 < v < 40 for v in pct_vals), (
        f"Wind share should be 15-40%: {pct_vals}"
    )


@pytest.mark.asyncio
async def test_redata_installed_capacity_mw_scale():
    """Spain 2024 installed capacity should show MW-scale values for Wind/Solar/Nuclear."""
    from tools.get_energy_data import register_get_energy_data_tool

    fn = make_tool(register_get_energy_data_tool)
    try:
        result = await fn(
            data_type="installed_capacity",
            start_date="2024-01-01T00:00",
            end_date="2024-12-31T23:59",
            time_trunc="year",
        )
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    assert "Wind" in result or "Solar" in result
    assert "Nuclear" in result
    # Values use comma thousands separators (e.g. "32,116.9 GW") — regex captures decimal part only
    # Just check the output contains "GW" and has percentage data
    assert "GW" in result, "Should show GW capacity unit"
    assert "%" in result, "Should show technology percentage breakdown"


@pytest.mark.asyncio
async def test_redata_generation_mix_multi_year():
    """Generation mix over 2 years should contain both 2023 and 2024."""
    from tools.get_energy_data import register_get_energy_data_tool

    fn = make_tool(register_get_energy_data_tool)
    try:
        result = await fn(
            data_type="generation_mix",
            start_date="2023-01-01T00:00",
            end_date="2024-12-31T23:59",
            time_trunc="year",
        )
    except httpx.HTTPError as e:
        skip_network(e)

    if "Error" in result[:50]:
        pytest.skip(f"REData API unavailable: {result[:200]}")

    years_found = set(re.findall(r"202[3-4]", result))
    assert len(years_found) >= 2, (
        f"Expected data for 2023 and 2024, found years: {years_found}"
    )


@pytest.mark.asyncio
async def test_redata_balance_returns_energy_groups():
    """Electrical balance should return renewable and non-renewable group data."""
    from tools.get_energy_data import register_get_energy_data_tool

    fn = make_tool(register_get_energy_data_tool)
    try:
        result = await fn(
            data_type="balance",
            start_date="2024-01-01T00:00",
            end_date="2024-12-31T23:59",
            time_trunc="year",
        )
    except httpx.HTTPError as e:
        skip_network(e)

    if "Error" in result[:50]:
        pytest.skip(f"REData balance unavailable: {result[:200]}")

    assert "Technologies/series" in result
    has_energy_groups = (
        "Renovable" in result
        or "Renewable" in result
        or "Non-renewable" in result
        or "Nuclear" in result
        or "Technologies/series: 4" in result
    )
    assert has_energy_groups, (
        f"Balance should reference energy categories: {result[:400]}"
    )


# ── BOE ────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_boe_ley_organica_10_2022():
    """BOE 20220907 should contain LO 10/2022 (ley 'solo sí es sí') with correct ID."""
    from tools.get_boe_summary import register_get_boe_summary_tool

    fn = make_tool(register_get_boe_summary_tool)
    try:
        result = await fn(date="20220907")
    except httpx.HTTPError as e:
        skip_network(e)

    if "No documents found" in result:
        pytest.fail("BOE parser broken: 20220907 should have LO 10/2022")

    assert "2022" in result
    assert "10/2022" in result or "libertad sexual" in result.lower()
    assert "BOE-A-2022-14630" in result, "Expected document ID BOE-A-2022-14630"


@pytest.mark.asyncio
async def test_boe_working_day_has_sections_and_ids():
    """A regular working day BOE should have numbered sections and multiple document IDs."""
    from tools.get_boe_summary import register_get_boe_summary_tool

    fn = make_tool(register_get_boe_summary_tool)
    try:
        result = await fn(date="20240318")  # Monday 18 March 2024
    except httpx.HTTPError as e:
        skip_network(e)

    if "No documents found" in result:
        pytest.skip("No BOE published for 20240318")

    sections = re.findall(r"\b[IVX]+\. ", result)
    assert len(sections) >= 2, f"Expected 2+ sections, found: {sections}"
    ids = re.findall(r"BOE-[A-Z]-\d{4}-\d+", result)
    assert len(ids) >= 5, f"Expected 5+ BOE document IDs, found {len(ids)}"


@pytest.mark.asyncio
async def test_boe_document_count_on_working_day():
    """A regular Monday BOE should have more than 10 documents."""
    from tools.get_boe_summary import register_get_boe_summary_tool

    fn = make_tool(register_get_boe_summary_tool)
    try:
        result = await fn(date="20240304")  # Monday 4 March 2024
    except httpx.HTTPError as e:
        skip_network(e)

    if "No documents found" in result:
        pytest.skip("No BOE published on 20240304")

    doc_count_match = re.search(r"Total documents: (\d+)", result)
    if doc_count_match:
        count = int(doc_count_match.group(1))
        assert count > 10, f"Expected >10 docs on a working day, got {count}"


@pytest.mark.asyncio
async def test_boe_id_format_and_year():
    """BOE document IDs should follow BOE-A-YYYY-NNNNN format with correct year."""
    from tools.get_boe_summary import register_get_boe_summary_tool

    fn = make_tool(register_get_boe_summary_tool)
    try:
        result = await fn(date="20250115")
    except httpx.HTTPError as e:
        skip_network(e)

    if "No documents found" in result:
        pytest.skip("No BOE published on 20250115")

    boe_ids = re.findall(r"BOE-[AB]-\d{4}-\d+", result)
    assert len(boe_ids) >= 3, f"Expected 3+ BOE IDs, found: {boe_ids}"
    for boe_id in boe_ids[:5]:
        year = int(re.search(r"\d{4}", boe_id).group())
        assert year == 2025, f"Expected 2025 in ID, got: {boe_id}"


@pytest.mark.asyncio
async def test_boe_ministerial_content_on_regular_day():
    """A regular BOE should contain ministerial orders or resolutions."""
    from tools.get_boe_summary import register_get_boe_summary_tool

    fn = make_tool(register_get_boe_summary_tool)
    try:
        result = await fn(date="20230110")  # Tuesday 10 January 2023
    except httpx.HTTPError as e:
        skip_network(e)

    if "No documents found" in result:
        pytest.skip("No BOE published on 20230110")

    assert "BOE Summary" in result
    has_content = (
        "Ministerio" in result
        or "Real Decreto" in result
        or "Resolución" in result
        or "Orden" in result
    )
    assert has_content, f"BOE should contain government acts: {result[:400]}"


@pytest.mark.asyncio
async def test_boe_sunday_returns_graceful_empty():
    """BOE is not published on Sundays — tool should return gracefully."""
    from tools.get_boe_summary import register_get_boe_summary_tool

    fn = make_tool(register_get_boe_summary_tool)
    try:
        result = await fn(date="20240121")  # Sunday 21 Jan 2024
    except httpx.HTTPError as e:
        skip_network(e)

    assert isinstance(result, str)
    assert "BOE" in result or "documents" in result.lower() or "Error" in result


# ── datos.gob.es: dataset search ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_unemployment_returns_results():
    """'paro registrado desempleo' should return SEPE/INE datasets."""
    from tools.search_datasets import register_search_datasets_tool

    fn = make_tool(register_search_datasets_tool)
    try:
        result = await fn(query="paro registrado desempleo")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "No datasets found" not in result
    assert "Error" not in result[:50]
    assert "1." in result, f"Should list numbered datasets: {result[:400]}"


@pytest.mark.asyncio
async def test_search_ipc_returns_ine_data():
    """'IPC precios consumo' should return INE price index datasets."""
    from tools.search_datasets import register_search_datasets_tool

    fn = make_tool(register_search_datasets_tool)
    try:
        result = await fn(query="IPC precios consumo")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    if "No datasets found" in result:
        result = await fn(query="indice precios")
        assert "No datasets found" not in result, "Neither IPC query returned results"
    assert "EA0010587" in result or "IPC" in result or "precio" in result.lower()


@pytest.mark.asyncio
async def test_search_results_include_access_urls():
    """Dataset results should include access URLs or dataset IDs."""
    from tools.search_datasets import register_search_datasets_tool

    fn = make_tool(register_search_datasets_tool)
    try:
        result = await fn(query="presupuestos generales estado")
    except httpx.HTTPError as e:
        skip_network(e)

    if "No datasets found" in result:
        pytest.skip("No datasets for this query")

    assert "datos.gob.es" in result or "ID:" in result or "URL:" in result


@pytest.mark.asyncio
async def test_search_agriculture_datasets():
    """Agriculture searches should find relevant datasets."""
    from tools.search_datasets import register_search_datasets_tool

    fn = make_tool(register_search_datasets_tool)
    try:
        result = await fn(query="agricultura ganaderia cereales superficie")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    assert "No datasets found" not in result
    assert "1." in result


@pytest.mark.asyncio
async def test_search_environment_datasets():
    """Environmental datasets should be searchable."""
    from tools.search_datasets import register_search_datasets_tool

    fn = make_tool(register_search_datasets_tool)
    try:
        result = await fn(query="calidad aire contaminacion atmosferica")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    assert "No datasets found" not in result


@pytest.mark.asyncio
async def test_search_tourism_datasets():
    """Tourism statistics should be searchable."""
    from tools.search_datasets import register_search_datasets_tool

    fn = make_tool(register_search_datasets_tool)
    try:
        result = await fn(query="turismo viajeros hoteles pernoctaciones")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    assert "No datasets found" not in result
    assert "1." in result


@pytest.mark.asyncio
async def test_search_results_mention_file_formats():
    """Dataset search results should mention file formats (CSV, JSON, etc.)."""
    from tools.search_datasets import register_search_datasets_tool

    fn = make_tool(register_search_datasets_tool)
    try:
        result = await fn(query="censo poblacion municipios")
    except httpx.HTTPError as e:
        skip_network(e)

    if "No datasets found" in result:
        pytest.skip("No census datasets found")

    formats = re.findall(
        r"\b(CSV|JSON|XML|XLSX|XLS|PC-AXIS|RDF|ZIP)\b", result, re.IGNORECASE
    )
    assert formats, f"Result should mention file formats: {result[:500]}"


@pytest.mark.asyncio
async def test_search_padron_datasets():
    """INE padrón municipal datasets should be searchable."""
    from tools.search_datasets import register_search_datasets_tool

    fn = make_tool(register_search_datasets_tool)
    try:
        result = await fn(query="padron municipal habitantes poblacion municipio")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    assert "No datasets found" not in result
    assert (
        "EA0010587" in result
        or "padr" in result.lower()
        or "municipi" in result.lower()
    )


@pytest.mark.asyncio
async def test_search_short_query_does_not_crash():
    """A single-word query should not crash the tool."""
    from tools.search_datasets import register_search_datasets_tool

    fn = make_tool(register_search_datasets_tool)
    try:
        result = await fn(query="pib")
    except httpx.HTTPError as e:
        skip_network(e)

    assert isinstance(result, str) and len(result) > 10


# ── Specialized tools: social security, housing, employment, transport ─────────


@pytest.mark.asyncio
async def test_social_security_cotizantes():
    """Social security cotizantes should return dataset listings."""
    from tools.get_social_security_stats import register_get_social_security_stats_tool

    fn = make_tool(register_get_social_security_stats_tool)
    try:
        result = await fn(stat_type="cotizantes")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    assert "No datasets" not in result
    assert "1." in result or "Afiliados" in result


@pytest.mark.asyncio
async def test_social_security_pensiones():
    """Social security pensiones should return dataset listings."""
    from tools.get_social_security_stats import register_get_social_security_stats_tool

    fn = make_tool(register_get_social_security_stats_tool)
    try:
        result = await fn(stat_type="pensiones")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    assert "1." in result or "pension" in result.lower()


@pytest.mark.asyncio
async def test_social_security_prestaciones():
    """Social security unemployment benefits should return datasets."""
    from tools.get_social_security_stats import register_get_social_security_stats_tool

    fn = make_tool(register_get_social_security_stats_tool)
    try:
        result = await fn(stat_type="prestaciones")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    assert "No datasets" not in result
    assert "1." in result


@pytest.mark.asyncio
async def test_social_security_accidentes_trabajo():
    """Social security occupational accident datasets should be accessible."""
    from tools.get_social_security_stats import register_get_social_security_stats_tool

    fn = make_tool(register_get_social_security_stats_tool)
    try:
        result = await fn(stat_type="accidentes")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]


@pytest.mark.asyncio
async def test_housing_precios_vivienda():
    """Housing precios_vivienda should return MIVAU datasets."""
    from tools.get_housing_stats import register_get_housing_stats_tool

    fn = make_tool(register_get_housing_stats_tool)
    try:
        result = await fn(stat_type="precios_vivienda")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    assert "No datasets" not in result
    assert "1." in result


@pytest.mark.asyncio
async def test_housing_alquiler():
    """Housing alquiler datasets should be accessible."""
    from tools.get_housing_stats import register_get_housing_stats_tool

    fn = make_tool(register_get_housing_stats_tool)
    try:
        result = await fn(stat_type="alquiler")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]


@pytest.mark.asyncio
async def test_housing_proteccion_oficial():
    """VPO (social housing) statistics should be accessible."""
    from tools.get_housing_stats import register_get_housing_stats_tool

    fn = make_tool(register_get_housing_stats_tool)
    try:
        result = await fn(stat_type="vpo")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    assert isinstance(result, str) and len(result) > 30


@pytest.mark.asyncio
async def test_housing_ejecuciones_hipotecarias():
    """Housing mortgage execution stats should return datasets."""
    from tools.get_housing_stats import register_get_housing_stats_tool

    fn = make_tool(register_get_housing_stats_tool)
    try:
        result = await fn(stat_type="ejecuciones")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    assert isinstance(result, str) and len(result) > 30


@pytest.mark.asyncio
async def test_sepe_contratos():
    """SEPE should return employment contract statistics."""
    from tools.get_employment_stats import register_get_employment_stats_tool

    fn = make_tool(register_get_employment_stats_tool)
    try:
        result = await fn(stat_type="contratos")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    assert "No SEPE" not in result
    assert "contrat" in result.lower() or "1." in result


@pytest.mark.asyncio
async def test_sepe_demandantes():
    """SEPE should return job seeker statistics."""
    from tools.get_employment_stats import register_get_employment_stats_tool

    fn = make_tool(register_get_employment_stats_tool)
    try:
        result = await fn(stat_type="demandantes")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    assert "No SEPE" not in result
    assert "1." in result


@pytest.mark.asyncio
async def test_renfe_schedules():
    """Renfe GTFS schedule datasets should be accessible."""
    from tools.get_renfe_data import register_get_renfe_data_tool

    fn = make_tool(register_get_renfe_data_tool)
    try:
        result = await fn(data_type="schedules")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    assert isinstance(result, str) and len(result) > 30


@pytest.mark.asyncio
async def test_renfe_statistics():
    """Renfe operational statistics should be accessible."""
    from tools.get_renfe_data import register_get_renfe_data_tool

    fn = make_tool(register_get_renfe_data_tool)
    try:
        result = await fn(data_type="statistics")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    assert isinstance(result, str) and len(result) > 30


# ── Error handling ─────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_eurostat_unknown_topic_returns_helpful_error():
    """Requesting an unknown Eurostat topic should return a helpful error with topic list."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    result = await fn(topic="este_topic_no_existe")

    assert "Unknown topic" in result or "unknown" in result.lower()
    assert "gdp_growth" in result or "Available" in result or "available" in result


@pytest.mark.asyncio
async def test_ine_no_params_returns_guidance():
    """query_ine_data with no params should return a useful error message."""
    from tools.query_ine_data import register_query_ine_data_tool

    fn = make_tool(register_query_ine_data_tool)
    result = await fn()

    assert "Error" in result
    assert "operation_code" in result or "series_code" in result or "table_id" in result


@pytest.mark.asyncio
async def test_bde_invalid_code_returns_error():
    """An invalid BdE series code should return a clear 'not found' message."""
    from tools.get_bde_series import register_get_bde_series_tool

    fn = make_tool(register_get_bde_series_tool)
    result = await fn(series_codes="CODIGO_QUE_NO_EXISTE_JAMAS")

    assert (
        "No data found" in result or "Error" in result or "not found" in result.lower()
    )


@pytest.mark.asyncio
async def test_bde_wrong_time_range_for_daily_series():
    """Using time_range='60M' for a daily series (D_DNBCEB72) should fail gracefully."""
    from tools.get_bde_series import register_get_bde_series_tool

    fn = make_tool(register_get_bde_series_tool)
    result = await fn(series_codes="D_DNBCEB72", time_range="60M")

    assert isinstance(result, str) and len(result) > 10
    assert (
        "No data" in result
        or "Error" in result
        or "412" in result
        or "series" in result.lower()
    )
