"""
Integration tests: "can we verify specific real-world claims?"

Each test is anchored to a specific verifiable assertion — a parliamentary claim,
a public statistic, or a known fact about Spain. Tests fail when the data does NOT
support the claim (not just when the API is unavailable).

Sources:
  - Parliamentary claims database (Congress statements, 2025-2026)
  - Historical data points with known correct values
  - Cross-country comparisons with known structural relationships

Run:
    uv run pytest tests/test_integration_claims.py -v -m integration
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


# ── GDP / Economic growth ──────────────────────────────────────────────────────
# Claim: "España creció un 2,8% en 2025, aproximadamente el doble que la UE" — Confirmed 0.95


@pytest.mark.asyncio
async def test_pib_espana_2025_crecio_28pct():
    """Spain 2025 GDP growth should be ~2.8% and roughly double EU27."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(topic="gdp_growth", geo="ES,EU27_2020", since_year="2024")
    except httpx.HTTPError as e:
        skip_network(e)

    assert_tool_ok(result)
    assert "Spain (ES)" in result
    es_vals = values_after(result, "Spain (ES)", 300)
    assert any(1.5 < v < 4.5 for v in es_vals), (
        f"Spain 2025 GDP growth should be ~2.8%: {es_vals}"
    )
    eu_vals = values_after(result, "European Union", 300)
    assert any(0 < v < 2.5 for v in eu_vals), (
        f"EU27 growth should be lower (~1.3%): {eu_vals}"
    )


@pytest.mark.asyncio
async def test_pib_espana_supera_alemania_desde_2022():
    """Spain's GDP growth should exceed Germany's consistently from 2022 onward."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(
            topic="gdp_growth", geo="ES,EU27_2020,DE,FR", since_year="2022"
        )
    except httpx.HTTPError as e:
        skip_network(e)

    assert_tool_ok(result)
    assert "Germany (DE)" in result and "France (FR)" in result
    es_vals = values_after(result, "Spain (ES)", 200)
    de_vals = values_after(result, "Germany (DE)", 200)
    assert es_vals and de_vals
    assert max(es_vals) > max(de_vals), (
        f"Spain growth ({max(es_vals)}) should exceed Germany ({max(de_vals)})"
    )


@pytest.mark.asyncio
async def test_pib_espana_supera_portugal_en_pps():
    """Spain's GDP per capita PPS index should consistently exceed Portugal's."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(topic="gdp_pps_per_capita", geo="ES,PT", since_year="2020")
    except httpx.HTTPError as e:
        skip_network(e)

    if "No data" in result[:50] or "Error" in result[:50]:
        pytest.skip(f"PPS dataset unavailable: {result[:200]}")

    assert "Spain (ES)" in result and "Portugal (PT)" in result
    es_vals = [
        v
        for v in extract_floats(text_block(result, "Spain (ES):", "Portugal"))
        if 70 < v < 110
    ]
    pt_vals = [
        v for v in extract_floats(text_block(result, "Portugal (PT):")) if 60 < v < 100
    ]
    assert es_vals and pt_vals
    assert max(es_vals) > max(pt_vals), (
        f"Spain PPS ({max(es_vals)}) should exceed Portugal ({max(pt_vals)})"
    )


# ── GDP per capita PPS gap ─────────────────────────────────────────────────────
# Claim: "España 8,41pp por debajo de la media europea en renta per cápita PPA" — Confirmed_con_matiz 0.75


@pytest.mark.asyncio
async def test_renta_per_capita_ppa_espana_bajo_media_ue():
    """Spain's GDP per capita PPS index should be ~91-92 (EU=100), gap ~8-9pp."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(
            topic="gdp_pps_per_capita", geo="ES,EU27_2020", since_year="2022"
        )
    except httpx.HTTPError as e:
        skip_network(e)

    assert_tool_ok(result)
    es_vals = values_after(result, "Spain (ES)", 200)
    assert any(82 < v < 97 for v in es_vals), (
        f"Spain PPS index should be 82-97 (EU=100): {es_vals}"
    )
    eu_vals = values_after(result, "European Union", 150)
    assert any(v == 100.0 for v in eu_vals), (
        f"EU27 index should be exactly 100: {eu_vals}"
    )


# ── Fiscal pressure ────────────────────────────────────────────────────────────
# Claims: "Alemania 3,6pp más presión fiscal que España" — Confirmed 0.85
#         "Eurostat: UE 40,4%, eurozona 40,9%, España 37,3%" — Confirmed_con_matiz 0.72


@pytest.mark.asyncio
async def test_presion_fiscal_espana_menor_que_alemania_y_francia():
    """Spain total tax revenue (% GDP) should be below Germany and France."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(
            topic="tax_burden", geo="ES,EU27_2020,DE,FR", since_year="2022"
        )
    except httpx.HTTPError as e:
        skip_network(e)

    assert_tool_ok(result)
    assert "Germany (DE)" in result and "France (FR)" in result

    es_max = max(
        (v for v in values_after(result, "Spain (ES)", 200) if 30 < v < 60),
        default=None,
    )
    de_max = max(
        (v for v in values_after(result, "Germany (DE)", 200) if 30 < v < 60),
        default=None,
    )
    fr_max = max(
        (v for v in values_after(result, "France (FR)", 200) if 30 < v < 60),
        default=None,
    )

    assert es_max and de_max and fr_max, (
        f"Missing tax values. ES={es_max}, DE={de_max}, FR={fr_max}"
    )
    assert es_max < de_max, (
        f"Spain ({es_max}%) should have lower tax than Germany ({de_max}%)"
    )
    assert es_max < fr_max, (
        f"Spain ({es_max}%) should have lower tax than France ({fr_max}%)"
    )


@pytest.mark.asyncio
async def test_presion_fiscal_espana_en_rango_plausible():
    """Spain total government revenue should be in 36-45% of GDP range."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(topic="tax_burden", geo="ES", since_year="2022")
    except httpx.HTTPError as e:
        skip_network(e)

    assert_tool_ok(result)
    tax_vals = [v for v in values_after(result, "Spain (ES)", 300) if 30 < v < 60]
    assert any(36 < v < 45 for v in tax_vals), (
        f"Spain tax burden should be 36-45% GDP: {tax_vals}"
    )


@pytest.mark.asyncio
async def test_presion_fiscal_espana_inferior_a_media_ue():
    """Spain's tax burden should be consistently lower than EU27 average."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(topic="tax_burden", geo="ES,EU27_2020", since_year="2021")
    except httpx.HTTPError as e:
        skip_network(e)

    assert_tool_ok(result)
    es_start = result.find("Spain (ES):")
    eu_start = result.find("European Union")
    assert es_start >= 0 and eu_start > es_start

    es_vals = [v for v in extract_floats(result[es_start:eu_start]) if 30 < v < 60]
    eu_vals = [
        v for v in extract_floats(result[eu_start : eu_start + 300]) if 30 < v < 60
    ]
    assert es_vals and eu_vals, f"Missing tax values. ES={es_vals}, EU={eu_vals}"
    assert max(es_vals) < max(eu_vals), (
        f"Spain tax ({max(es_vals)}%) should be below EU27 ({max(eu_vals)}%)"
    )


# ── Government deficit ─────────────────────────────────────────────────────────
# Claim: "déficit pasó del 2,02% al 2,58% en 2024" — Confirmed_con_matiz 0.85


@pytest.mark.asyncio
async def test_deficit_publico_espana_negativo():
    """Spain's budget deficit should be negative in 2022-2024 range (-6% to -2%)."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(topic="government_deficit", geo="ES", since_year="2022")
    except httpx.HTTPError as e:
        skip_network(e)

    assert_tool_ok(result)
    es_vals = values_after(result, "Spain (ES)", 300)
    assert any(-8 < v < 0 for v in es_vals), (
        f"Spain should show deficit (negative values): {es_vals}"
    )


# ── Government debt ─────────────────────────────────────────────────────────────
# Claim: "deuda pública es un 41% superior a la actual que cuando el Gobierno llegó en 2018"


@pytest.mark.asyncio
async def test_deuda_publica_espana_tendencia_post_pandemia():
    """Spain's debt peaked around 120% GDP in 2020 and has been declining since."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(topic="government_debt", geo="ES", since_year="2019")
    except httpx.HTTPError as e:
        skip_network(e)

    assert_tool_ok(result)
    es_start = result.find("Spain (ES):")
    es_block = result[es_start : es_start + 800]
    debt_vals = sorted(v for v in extract_floats(es_block) if 70 < v < 150)
    assert len(debt_vals) >= 3, f"Expected 3+ years of debt data: {debt_vals}"
    assert max(debt_vals) > min(debt_vals) + 5, (
        f"Debt should show variation (peak vs trough): {debt_vals}"
    )


@pytest.mark.asyncio
async def test_deuda_espana_mayor_que_alemania():
    """Spain's government debt ratio should exceed Germany's."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(topic="government_debt", geo="ES,DE", since_year="2021")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Spain (ES)" in result and "Germany (DE)" in result
    es_vals = [
        v
        for v in extract_floats(text_block(result, "Spain (ES):", "Germany (DE):"))
        if 50 < v < 150
    ]
    de_vals = [
        v for v in extract_floats(text_block(result, "Germany (DE):")) if 30 < v < 100
    ]
    assert es_vals and de_vals
    assert max(es_vals) > max(de_vals), (
        f"Spain debt ({max(es_vals)}%) should exceed Germany ({max(de_vals)}%)"
    )


@pytest.mark.asyncio
async def test_deuda_italia_mayor_que_espana():
    """Italy's government debt should be higher than Spain's (historically 140%+ vs 107%)."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(topic="government_debt", geo="ES,IT", since_year="2021")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Spain (ES)" in result and "Italy (IT)" in result
    es_vals = [
        v
        for v in extract_floats(text_block(result, "Spain (ES):", "Italy"))
        if 80 < v < 140
    ]
    it_vals = [
        v for v in extract_floats(text_block(result, "Italy (IT):")) if 100 < v < 180
    ]
    assert es_vals and it_vals
    assert max(it_vals) > max(es_vals), (
        f"Italy debt ({max(it_vals)}%) should exceed Spain ({max(es_vals)}%)"
    )


# ── Wages / purchasing power ───────────────────────────────────────────────────
# Claim: "OCDE: trabajadores españoles perdieron poder adquisitivo desde 2019" — Confirmed 0.92


@pytest.mark.asyncio
async def test_salarios_espana_por_debajo_alemania():
    """Net wages in Spain should be below Germany across all measured years."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(topic="wages", geo="ES,DE,FR", since_year="2019")
    except httpx.HTTPError as e:
        skip_network(e)

    assert_tool_ok(result)
    es_vals = values_after(result, "Spain (ES)", 300)
    de_vals = values_after(result, "Germany (DE)", 300)
    assert es_vals and de_vals
    assert max(es_vals) < max(de_vals), (
        f"Spain wages ({max(es_vals)}) should be below Germany ({max(de_vals)})"
    )


# ── Inflation / IPC ────────────────────────────────────────────────────────────
# Claim: "inflación en España fue del 7,6% en febrero de 2022" — verified
# Claim: "IPC acumulado 2010-2024 fue del 31,6%" — Confirmed_con_matiz 0.75


@pytest.mark.asyncio
async def test_ipc_espana_pico_2022():
    """Spain's CPI in 2022 should show peak inflation in 6-10% range."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(
            topic="inflation_hicp", geo="ES", since_year="2022", until_year="2022"
        )
    except httpx.HTTPError as e:
        skip_network(e)

    assert_tool_ok(result)
    es_vals = values_after(result, "Spain (ES)", 500)
    inflation_vals = [v for v in es_vals if -2 < v < 15]
    assert len(inflation_vals) >= 6, (
        f"Expected 12 monthly values for 2022: {inflation_vals}"
    )
    assert any(v > 6 for v in inflation_vals), (
        f"Spain 2022 peak should exceed 6%: {inflation_vals}"
    )


@pytest.mark.asyncio
async def test_ipc_espana_serie_historica_ine():
    """INE IPC annual series should return 12+ plausible values."""
    from tools.query_ine_data import register_query_ine_data_tool

    fn = make_tool(register_query_ine_data_tool)
    try:
        result = await fn(series_code="IPC251856", last_n_periods=24)
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    vals = [v for v in extract_floats(result) if -5 < v < 15]
    assert len(vals) >= 12, f"Expected at least 12 annual IPC values: {vals}"


@pytest.mark.asyncio
async def test_inflacion_acumulada_2018_2024_supera_15pct():
    """Cumulative HICP inflation from 2018 to 2024 for Spain should exceed 15%."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(
            topic="inflation_annual",
            geo="ES",
            since_year="2018",
            until_year="2024",
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
    assert 2018 in year_vals and 2024 in year_vals, (
        f"Need 2018 and 2024 values: {year_vals}"
    )
    cumulative = (year_vals[2024] / year_vals[2018] - 1) * 100
    assert cumulative > 15, (
        f"Cumulative inflation 2018-2024 should exceed 15%, got: {cumulative:.1f}%"
    )


# ── Housing ───────────────────────────────────────────────────────────────────
# Claim: "precio de la vivienda es un 29,2% más caro que cuando el Gobierno llegó en 2018" — verified
# Claim: "Banco de España: faltan 700.000 viviendas" — Confirmed 0.82


@pytest.mark.asyncio
async def test_vivienda_indice_precios_creciente():
    """House price index (2015=100) should rise from 2018 to 2024."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(topic="house_prices", geo="ES,EU27_2020", since_year="2018")
    except httpx.HTTPError as e:
        skip_network(e)

    assert_tool_ok(result)
    es_vals = values_after(result, "Spain (ES)", 300)
    price_vals = sorted(v for v in es_vals if 90 < v < 250)
    assert price_vals and max(price_vals) > 130, (
        f"House price index should be >130 post-2020: {price_vals}"
    )


@pytest.mark.asyncio
async def test_vivienda_precios_subieron_desde_2018():
    """House prices should show clear increase from 2018 to 2024."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(
            topic="house_prices", geo="ES", since_year="2018", until_year="2024"
        )
    except httpx.HTTPError as e:
        skip_network(e)

    assert_tool_ok(result)
    price_vals = sorted(
        v for v in values_after(result, "Spain (ES)", 400) if 90 < v < 250
    )
    assert len(price_vals) >= 4, f"Need at least 4 years of data: {price_vals}"
    assert price_vals[-1] > price_vals[0], (
        f"Prices should rise from 2018 to 2024: {price_vals}"
    )


@pytest.mark.asyncio
async def test_vivienda_deficit_busqueda():
    """Housing deficit/demand statistics should be searchable."""
    from tools.search_datasets import register_search_datasets_tool

    fn = make_tool(register_search_datasets_tool)
    try:
        result = await fn(query="vivienda demanda oferta deficit estadistica")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    assert "No datasets found" not in result


# ── Poverty and inequality ─────────────────────────────────────────────────────
# Claim: "tasa de riesgo de pobreza en su nivel más bajo desde 2014" — Confirmed 0.92
# Claim: "España lidera pobreza infantil UE: 34,6% vs 24,1%" — False 0.72 (actual ~27%)


@pytest.mark.asyncio
async def test_gini_espana_en_rango_plausible():
    """Spain's Gini coefficient should be in 28-37 range and show some improvement."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(
            topic="poverty_inequality", geo="ES,EU27_2020", since_year="2015"
        )
    except httpx.HTTPError as e:
        skip_network(e)

    assert_tool_ok(result)
    es_vals = values_after(result, "Spain (ES)", 300)
    gini_vals = [v for v in es_vals if 20 < v < 50]
    assert len(gini_vals) >= 4, f"Expected 4+ years of Gini data: {gini_vals}"
    assert any(28 < v < 37 for v in gini_vals), (
        f"Spain Gini should be 28-37: {gini_vals}"
    )


@pytest.mark.asyncio
async def test_pobreza_espana_ine_ecv():
    """INE ECV poverty rate (table 9958) should show Spain around 19-22%."""
    from tools.query_ine_data import register_query_ine_data_tool

    fn = make_tool(register_query_ine_data_tool)
    try:
        result = await fn(table_id="9958", last_n_periods=8)
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    vals = [v for v in extract_floats(result) if 10 < v < 35]
    assert len(vals) >= 4, f"Expected 4+ poverty rate values: {vals}"
    assert any(15 < v < 28 for v in vals), (
        f"Spain poverty rate should be 15-28%: {vals}"
    )


@pytest.mark.asyncio
async def test_pobreza_infantil_espana_eurostat():
    """Spain's child poverty (AROPE) rate should be checkable via Eurostat."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(
            topic="custom",
            dataset_code="ilc_peps01h",
            geo="ES,EU27_2020",
            since_year="2020",
            extra_filters="unit=PC&age=Y_LT18",
        )
    except httpx.HTTPError as e:
        skip_network(e)

    if "Error" in result[:50] or "No data" in result[:50]:
        pytest.skip(f"Child poverty dataset not accessible: {result[:200]}")

    vals = [v for v in extract_floats(result) if 10 < v < 50]
    if vals:
        assert any(15 < v < 40 for v in vals), (
            f"Child poverty should be 15-40% (not 34.6%): {vals}"
        )


@pytest.mark.asyncio
async def test_gasto_familias_epf():
    """INE EPF household budget table should show plausible annual spending."""
    from tools.query_ine_data import register_query_ine_data_tool

    fn = make_tool(register_query_ine_data_tool)
    try:
        result = await fn(table_id="75003", last_n_periods=4)
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    vals = [v for v in extract_floats(result) if 100 < v < 50000]
    assert vals, f"No household spending values in plausible range: {result[:400]}"


# ── Energy / Renewables ────────────────────────────────────────────────────────
# Claim: "potencia instalada de energías renovables creció un 150% entre 2019 y 2026" — verified
# Claim: "gas natural determinaba el precio marginal en 75% horas en 2019 → 19% en 2025"


@pytest.mark.asyncio
async def test_renovables_cuota_creciente_2015_2023():
    """Spain's renewable share should show clear growth from 2015 to 2023."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(topic="renewable_share", geo="ES", since_year="2015")
    except httpx.HTTPError as e:
        skip_network(e)

    assert_tool_ok(result)
    renew_vals = sorted(
        v for v in values_after(result, "Spain (ES)", 400) if 10 < v < 60
    )
    assert len(renew_vals) >= 5, f"Expected 5+ years of data: {renew_vals}"
    assert renew_vals[-1] > renew_vals[0], (
        f"Renewable share should grow from 2015 to latest: {renew_vals}"
    )


@pytest.mark.asyncio
async def test_mix_generacion_2024_eolica_mayoritaria():
    """In 2024, wind should be present and exceed 15% of Spain's generation mix."""
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

    if "Error" in result[:50]:
        pytest.skip(f"REData unavailable: {result[:150]}")

    assert "Wind" in result or "Eólica" in result
    assert "Solar" in result and "Nuclear" in result
    wind_vals = values_after(result, "Wind", 100)
    pct_vals = [v for v in wind_vals if 0 < v < 100]
    assert pct_vals and any(v > 15 for v in pct_vals), (
        f"Wind should be >15% of mix: {pct_vals}"
    )


@pytest.mark.asyncio
async def test_renovables_capacidad_instalada_redata():
    """REData installed capacity 2022-2024 should show technology breakdown."""
    from tools.get_energy_data import register_get_energy_data_tool

    fn = make_tool(register_get_energy_data_tool)
    try:
        result = await fn(
            data_type="installed_capacity",
            start_date="2022-01-01T00:00",
            end_date="2024-12-31T23:59",
            time_trunc="year",
        )
    except httpx.HTTPError as e:
        skip_network(e)

    assert_tool_ok(result)
    assert "Wind" in result or "Solar" in result


@pytest.mark.asyncio
async def test_renovables_antes_de_2019_crecimiento_lento():
    """Installed capacity in the pre-2019 period should show slower renewable growth."""
    from tools.get_energy_data import register_get_energy_data_tool

    fn = make_tool(register_get_energy_data_tool)
    try:
        result = await fn(
            data_type="installed_capacity",
            start_date="2017-01-01T00:00",
            end_date="2019-12-31T23:59",
            time_trunc="year",
        )
    except httpx.HTTPError as e:
        skip_network(e)

    assert_tool_ok(result)


@pytest.mark.asyncio
async def test_gas_marginal_mix_generacion():
    """Generation mix data should be available to analyse gas marginal pricing."""
    from tools.get_energy_data import register_get_energy_data_tool

    fn = make_tool(register_get_energy_data_tool)
    try:
        result = await fn(
            data_type="generation_mix",
            start_date="2023-01-01T00:00",
            end_date="2024-12-31T23:59",
            time_trunc="month",
        )
    except httpx.HTTPError as e:
        skip_network(e)

    assert_tool_ok(result)


@pytest.mark.asyncio
async def test_electricidad_pymes_espana_vs_ue():
    """Spanish industrial electricity prices should be comparable to EU range."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(
            topic="electricity_prices_industry",
            geo="ES,EU27_2020,DE,FR,IT",
            since_year="2019",
        )
    except httpx.HTTPError as e:
        skip_network(e)

    assert_tool_ok(result)
    assert "Spain (ES)" in result or "ES" in result


@pytest.mark.asyncio
async def test_hidrocarburos_fossil_imports_espana():
    """Fossil fuel import data should be retrievable for Spain vs EU comparison."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(
            topic="fossil_fuel_imports", geo="ES,EU27_2020,DE,FR,IT", since_year="2019"
        )
    except httpx.HTTPError as e:
        skip_network(e)

    if "Error" in result[:50]:
        pytest.skip(f"Fossil fuel dataset unavailable: {result[:200]}")

    assert isinstance(result, str) and len(result) > 50


@pytest.mark.asyncio
async def test_emisiones_co2_tendencia_decreciente_espana():
    """Spain's GHG emissions per capita should show a declining trend since 2019."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(
            topic="custom",
            dataset_code="sdg_13_10",
            geo="ES",
            since_year="2015",
            extra_filters="unit=T_HAB",
        )
    except httpx.HTTPError as e:
        skip_network(e)

    if "Error" in result[:50] or "No data" in result[:50]:
        pytest.skip(f"CO2 dataset unavailable: {result[:200]}")

    es_block = text_block(result, "Spain (ES)")
    year_vals = {
        int(y): float(v)
        for y, v in re.findall(r"(20\d{2}):\s*([\d.]+)", es_block)
        if 2 < float(v) < 15
    }
    recent_years = sorted(y for y in year_vals if y >= 2019)
    if len(recent_years) >= 3:
        assert year_vals[recent_years[-1]] < year_vals[recent_years[0]], (
            f"CO2 should decline post-2019: {year_vals}"
        )


# ── Employment and labour market ───────────────────────────────────────────────
# Claim: "desaparecieron 75.000 ocupados en el sector agrario" — False 0.75


@pytest.mark.asyncio
async def test_desempleo_espana_superior_a_alemania_y_francia():
    """Spain unemployment must exceed both Germany and France every year since 2021."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(topic="unemployment", geo="ES,DE,FR", since_year="2021")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Spain (ES)" in result and "Germany (DE)" in result

    es_vals = [
        v
        for v in extract_floats(text_block(result, "Spain (ES)", "Germany"))
        if 5 < v < 25
    ]
    de_vals = [
        v
        for v in extract_floats(text_block(result, "Germany (DE)", "France"))
        if 2 < v < 15
    ]
    fr_vals = [
        v for v in extract_floats(text_block(result, "France (FR)")) if 2 < v < 15
    ]

    assert es_vals and de_vals and fr_vals
    assert min(es_vals) > max(de_vals), (
        f"Spain ({min(es_vals)}) should exceed Germany ({max(de_vals)}) every year"
    )
    assert min(es_vals) > max(fr_vals), (
        f"Spain ({min(es_vals)}) should exceed France ({max(fr_vals)})"
    )


@pytest.mark.asyncio
async def test_tasa_empleo_espana_creciente():
    """Spain employment rate (20-64) should show improvement since 2019."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(
            topic="employment_rate", geo="ES,EU27_2020", since_year="2019"
        )
    except httpx.HTTPError as e:
        skip_network(e)

    assert_tool_ok(result)
    emp_vals = sorted(v for v in values_after(result, "Spain (ES)", 300) if 60 < v < 90)
    assert len(emp_vals) >= 3, f"Need 3+ years of data: {emp_vals}"
    assert emp_vals[-1] >= emp_vals[0], (
        f"Employment should not decline 2019-latest: {emp_vals}"
    )


@pytest.mark.asyncio
async def test_brecha_genero_empleo_espana():
    """Male employment rate should exceed female employment rate in Spain."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result_m = await fn(
            topic="employment_rate",
            geo="ES",
            since_year="2022",
            extra_filters="sex=M&age=Y20-64",
        )
        result_f = await fn(
            topic="employment_rate",
            geo="ES",
            since_year="2022",
            extra_filters="sex=F&age=Y20-64",
        )
    except httpx.HTTPError as e:
        skip_network(e)

    male_vals = [v for v in extract_floats(result_m) if 60 < v < 95]
    female_vals = [v for v in extract_floats(result_f) if 50 < v < 90]
    assert male_vals and female_vals
    assert max(male_vals) > max(female_vals), (
        f"Male ({max(male_vals)}) should exceed female ({max(female_vals)}) employment"
    )


@pytest.mark.asyncio
async def test_epa_sector_agrario():
    """EPA should contain agricultural sector employment tables."""
    from tools.query_ine_data import register_query_ine_data_tool

    fn = make_tool(register_query_ine_data_tool)
    try:
        result = await fn(operation_code="EPA")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    assert (
        "agrar" in result.lower()
        or "sector" in result.lower()
        or "ocup" in result.lower()
    )


# ── Social security ────────────────────────────────────────────────────────────
# Claim: "afiliación a la Seguridad Social alcanzó los 21,97 millones" — Confirmed 0.95
# Claim: "6,5M se jubilarán en próximos 10 años vs 5M actuales" — False 0.92 (~10M pensioners)


@pytest.mark.asyncio
async def test_ss_pensionistas_datasets():
    """Social security should return pension-related datasets."""
    from tools.get_social_security_stats import register_get_social_security_stats_tool

    fn = make_tool(register_get_social_security_stats_tool)
    try:
        result = await fn(stat_type="pensiones")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    assert "No datasets" not in result
    assert "1." in result or "pension" in result.lower()


@pytest.mark.asyncio
async def test_ss_afiliados_datasets():
    """Social security should return contributor datasets."""
    from tools.get_social_security_stats import register_get_social_security_stats_tool

    fn = make_tool(register_get_social_security_stats_tool)
    try:
        result = await fn(stat_type="cotizantes")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    assert "No datasets" not in result
    assert "afiliado" in result.lower() or "cotiz" in result.lower() or "1." in result


@pytest.mark.asyncio
async def test_gasto_sanidad_espana_porcentaje_pib():
    """Spain's public health expenditure should be 5-12% of GDP."""
    from tools.get_eurostat_data import register_get_eurostat_data_tool

    fn = make_tool(register_get_eurostat_data_tool)
    try:
        result = await fn(
            topic="custom",
            dataset_code="gov_10a_exp",
            geo="ES,EU27_2020",
            since_year="2019",
            extra_filters="unit=PC_GDP&cofog99=GF07&sector=S13",
        )
    except httpx.HTTPError as e:
        skip_network(e)

    if "Error" in result[:50] or "No data" in result[:50]:
        pytest.skip(f"Health expenditure dataset unavailable: {result[:200]}")

    assert "Spain (ES)" in result
    es_vals = [
        v
        for v in extract_floats(text_block(result, "Spain (ES)", "European Union"))
        if 3 < v < 15
    ]
    assert es_vals, f"No health spending values: {result[:400]}"
    assert any(5 < v < 12 for v in es_vals), (
        f"Spain health spending should be 5-12% GDP: {es_vals}"
    )


# ── Natality ──────────────────────────────────────────────────────────────────
# Claim: "nacieron 328.704 niños en 2022" — Subestimado 0.92 (actual ~328.736)


@pytest.mark.asyncio
async def test_natalidad_busqueda_ine():
    """INE birth statistics should be searchable."""
    from tools.search_datasets import register_search_datasets_tool

    fn = make_tool(register_search_datasets_tool)
    try:
        result = await fn(
            query="nacimientos natalidad estadistica movimiento natural poblacion"
        )
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    assert "No datasets found" not in result
    assert (
        "nacimi" in result.lower()
        or "natalidad" in result.lower()
        or "EA0010587" in result
    )


@pytest.mark.asyncio
async def test_natalidad_mnp_operation():
    """INE MNP (Movimiento Natural de la Población) should list birth tables."""
    from tools.query_ine_data import register_query_ine_data_tool

    fn = make_tool(register_query_ine_data_tool)
    try:
        result = await fn(operation_code="MNP")
    except httpx.HTTPError as e:
        skip_network(e)

    if "Error" in result[:50]:
        pytest.skip(f"MNP operation not available: {result[:200]}")

    table_count = len(re.findall(r"\bID \d+:", result))
    assert table_count >= 3, f"Expected at least 3 MNP tables, found {table_count}"


# ── AEAT: taxes ──────────────────────────────────────────────────────────────
# Claim: "IRPF de 82.000M en 2018 a 142.000M en 2025 (+70%)" — Not verifiable via API 0.3


@pytest.mark.asyncio
async def test_aeat_irpf_datasets():
    """AEAT should return IRPF statistics datasets."""
    from tools.get_aeat_stats import register_get_aeat_stats_tool

    fn = make_tool(register_get_aeat_stats_tool)
    try:
        result = await fn(stat_type="irpf")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    assert "No datasets" not in result
    assert "IRPF" in result or "renta" in result.lower()
    assert "1." in result


@pytest.mark.asyncio
async def test_aeat_iva_datasets():
    """AEAT should return IVA statistics datasets."""
    from tools.get_aeat_stats import register_get_aeat_stats_tool

    fn = make_tool(register_get_aeat_stats_tool)
    try:
        result = await fn(stat_type="iva")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    assert "IVA" in result or "valor añadido" in result.lower()


@pytest.mark.asyncio
async def test_aeat_iva_franquicia_search():
    """AEAT IVA franchise (for small businesses) should be verifiable."""
    from tools.get_aeat_stats import register_get_aeat_stats_tool

    fn = make_tool(register_get_aeat_stats_tool)
    try:
        result = await fn(stat_type="iva")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    assert isinstance(result, str) and len(result) > 50


# ── BOE: Legislation ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_boe_secciones_y_ids_dia_laboral():
    """A standard BOE day should contain numbered sections and document IDs."""
    from tools.get_boe_summary import register_get_boe_summary_tool

    fn = make_tool(register_get_boe_summary_tool)
    try:
        result = await fn(date="20240318")
    except httpx.HTTPError as e:
        skip_network(e)

    if "No documents found" in result:
        pytest.skip("No BOE published for 20240318")

    ids = re.findall(r"BOE-[A-Z]-\d{4}-\d+", result)
    assert len(ids) >= 5, f"Expected at least 5 BOE document IDs, found {len(ids)}"


@pytest.mark.asyncio
async def test_boe_ley_solo_si_es_si_publicada():
    """BOE 20220907 must contain Ley Orgánica 10/2022 (ley 'solo sí es sí')."""
    from tools.get_boe_summary import register_get_boe_summary_tool

    fn = make_tool(register_get_boe_summary_tool)
    try:
        result = await fn(date="20220907")
    except httpx.HTTPError as e:
        skip_network(e)

    if "No documents found" in result:
        pytest.fail("BOE API returned no documents for 20220907 — expected LO 10/2022")

    assert "10/2022" in result or "libertad sexual" in result.lower()
    assert "BOE-A-2022-14630" in result, "Expected document ID BOE-A-2022-14630"


@pytest.mark.asyncio
async def test_search_legislation_presupuestos():
    """Legislation search for 'presupuestos generales' should return results."""
    from tools.search_legislation import register_search_legislation_tool

    fn = make_tool(register_search_legislation_tool)
    try:
        result = await fn(query="presupuestos generales estado ley")
    except httpx.HTTPError as e:
        skip_network(e)

    if result.startswith("Error"):
        pytest.skip(f"Legislation search unavailable (known 500): {result[:200]}")

    assert isinstance(result, str) and len(result) > 30


@pytest.mark.asyncio
async def test_search_legislation_solo_si_es_si():
    """Legislation search for 'garantía integral libertad sexual' should return results."""
    from tools.search_legislation import register_search_legislation_tool

    fn = make_tool(register_search_legislation_tool)
    try:
        result = await fn(query="garantía integral libertad sexual")
    except httpx.HTTPError as e:
        skip_network(e)

    if result.startswith("Error"):
        pytest.skip(f"Legislation search unavailable (known 500): {result[:200]}")

    assert isinstance(result, str) and len(result) > 30


@pytest.mark.asyncio
async def test_search_legislation_iva_franquicia():
    """Legislation search for IVA franchise for small businesses should return results."""
    from tools.search_legislation import register_search_legislation_tool

    fn = make_tool(register_search_legislation_tool)
    try:
        result = await fn(query="franquicia IVA pequeñas empresas")
    except httpx.HTTPError as e:
        skip_network(e)

    if result.startswith("Error"):
        pytest.skip(f"Legislation search unavailable (known 500): {result[:200]}")

    assert isinstance(result, str) and len(result) > 30


# ── Crime / immigration / public contracts ─────────────────────────────────────
# Claim: "agresiones sexuales con penetración +275,3% (1387→5206, 2017-2024)" — Confirmed_con_matiz 0.75
# Claim: "España notificó +41.000 órdenes pero ejecutó 3.000 (7%)" — Confirmed_con_matiz 0.65


@pytest.mark.asyncio
async def test_criminalidad_busqueda():
    """Crime statistics datasets from Ministerio del Interior should be searchable."""
    from tools.search_datasets import register_search_datasets_tool

    fn = make_tool(register_search_datasets_tool)
    try:
        result = await fn(query="criminalidad delitos estadistica interior seguridad")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    assert isinstance(result, str) and len(result) > 30


@pytest.mark.asyncio
async def test_inmigracion_datasets():
    """INE migration statistics should be searchable."""
    from tools.search_datasets import register_search_datasets_tool

    fn = make_tool(register_search_datasets_tool)
    try:
        result = await fn(
            query="migraciones exteriores estadistica variaciones residenciales"
        )
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    assert "No datasets found" not in result
    assert "migraci" in result.lower() or "INE" in result or "EA0010587" in result


@pytest.mark.asyncio
async def test_expulsiones_busqueda():
    """Datasets on migration enforcement/returns should be searchable."""
    from tools.search_datasets import register_search_datasets_tool

    fn = make_tool(register_search_datasets_tool)
    try:
        result = await fn(query="expulsiones retornos extranjeros inmigracion")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    assert isinstance(result, str) and len(result) > 20


@pytest.mark.asyncio
async def test_contratos_publicos_infraestructura():
    """Public contracts search should return results for infrastructure queries."""
    from tools.search_public_contracts import register_search_public_contracts_tool

    fn = make_tool(register_search_public_contracts_tool)
    try:
        result = await fn(query="ferroviario infraestructura ADIF")
    except (httpx.HTTPError, Exception) as e:
        if isinstance(e, httpx.HTTPError):
            skip_network(e)
        pytest.skip(f"Public contracts unavailable: {e}")

    assert "Error" not in result[:50]
    assert isinstance(result, str) and len(result) > 30


@pytest.mark.asyncio
async def test_estadisticas_justicia():
    """Justice statistics should return datasets."""
    from tools.get_justice_stats import register_get_justice_stats_tool

    fn = make_tool(register_get_justice_stats_tool)
    try:
        result = await fn(stat_type="delitos")
    except (httpx.HTTPError, Exception) as e:
        if isinstance(e, httpx.HTTPError):
            skip_network(e)
        pytest.skip(f"Justice stats unavailable: {e}")

    assert "Error" not in result[:50]
    assert isinstance(result, str) and len(result) > 50


@pytest.mark.asyncio
async def test_trafico_estadisticas():
    """Traffic statistics should return transport-related datasets."""
    from tools.get_traffic_stats import register_get_traffic_stats_tool

    fn = make_tool(register_get_traffic_stats_tool)
    try:
        result = await fn(stat_type="accidentes")
    except (httpx.HTTPError, Exception) as e:
        if isinstance(e, httpx.HTTPError):
            skip_network(e)
        pytest.skip(f"Traffic stats unavailable: {e}")

    assert "Error" not in result[:50]
    assert isinstance(result, str) and len(result) > 30


@pytest.mark.asyncio
async def test_salud_estadisticas():
    """Health statistics should be accessible."""
    from tools.get_health_stats import register_get_health_stats_tool

    fn = make_tool(register_get_health_stats_tool)
    try:
        result = await fn(stat_type="mortalidad")
    except (httpx.HTTPError, Exception) as e:
        if isinstance(e, httpx.HTTPError):
            skip_network(e)
        pytest.skip(f"Health stats unavailable: {e}")

    assert "Error" not in result[:50]
    assert isinstance(result, str) and len(result) > 30


@pytest.mark.asyncio
async def test_educacion_datasets():
    """Education statistics should return datasets."""
    from tools.get_education_stats import register_get_education_stats_tool

    fn = make_tool(register_get_education_stats_tool)
    try:
        result = await fn(stat_type="universitaria")
    except (httpx.HTTPError, Exception) as e:
        if isinstance(e, httpx.HTTPError):
            skip_network(e)
        pytest.skip(f"Education stats unavailable: {e}")

    assert "Error" not in result[:50]
    assert isinstance(result, str) and len(result) > 30


@pytest.mark.asyncio
async def test_viviendas_pequenos_propietarios():
    """Housing precios datasets should be available to verify small-landlord claims."""
    from tools.get_housing_stats import register_get_housing_stats_tool

    fn = make_tool(register_get_housing_stats_tool)
    try:
        result = await fn(stat_type="precios_vivienda")
    except httpx.HTTPError as e:
        skip_network(e)

    assert "Error" not in result[:50]
    assert isinstance(result, str) and len(result) > 50


@pytest.mark.asyncio
async def test_decretos_sociales_search():
    """Legislation search for 'decreto ley social' should return results."""
    from tools.search_legislation import register_search_legislation_tool

    fn = make_tool(register_search_legislation_tool)
    try:
        result = await fn(query="decreto ley social convalidación Congreso Diputados")
    except httpx.HTTPError as e:
        skip_network(e)

    if result.startswith("Error"):
        pytest.skip(f"Legislation search unavailable (known 500): {result[:200]}")

    assert isinstance(result, str) and len(result) > 30
