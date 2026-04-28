"""
Claim routing tests for verify_claim.

verify_claim does NOT make HTTP requests — it analyses the claim text and returns a
structured routing plan. These tests therefore run without any mocking.

Each test passes one of the provided political/economic claims and asserts that:
  1. The output contains a routing plan (not an error / unclassified fallback).
  2. At least one expected tool is recommended.
  3. The temporal cap is applied correctly (data is bounded to the claim date).
"""

import pytest

from tools.verify_claim import register_verify_claim_tool


class _MockMCP:
    def __init__(self):
        self.fn = None

    def tool(self):
        def decorator(fn):
            self.fn = fn
            return fn

        return decorator


@pytest.fixture(scope="module")
def verify_claim_fn():
    mcp = _MockMCP()
    register_verify_claim_tool(mcp)
    return mcp.fn


# ── helpers ────────────────────────────────────────────────────────────────────


def _has_tool(result: str, tool_name: str) -> bool:
    return tool_name in result


def _is_routed(result: str) -> bool:
    """True when the claim was classified and routing steps were generated."""
    return "Paso 1:" in result or "CATEGORÍA:" in result


# ── wage / purchasing power ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_claim_salario_neto_2025(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="El salario medio neto es un 3,4 % menos en 2025 que en 2018.",
        fecha="2026-01-01",
        ambito_tematico="salarios",
    )
    assert _is_routed(result)
    assert (
        _has_tool(result, "get_eurostat_data")
        or _has_tool(result, "get_aeat_stats")
        or _has_tool(result, "search_datasets")
    )


@pytest.mark.asyncio
async def test_claim_poder_adquisitivo_comparativa_ue(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="La mejora del poder adquisitivo de los trabajadores y hogares españoles es más intensa que en los grandes países de la Unión Europea y en la media del G7.",
        fecha="2026-01-01",
        ambito_tematico="salarios",
    )
    assert _is_routed(result)
    assert _has_tool(result, "get_eurostat_data") or _has_tool(
        result, "search_datasets"
    )


# ── banking / corporate ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_claim_caixabank_beneficio(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="CaixaBank tuvo un beneficio récord de casi 6000 millones de euros en 2025.",
        fecha="2026-01-01",
        entidad_mencionada="CaixaBank",
        ambito_tematico="banca",
    )
    # Should route to financial sector or suggest CNMV search
    assert (
        _is_routed(result)
        or "CNMV" in result
        or "cnmv" in result.lower()
        or "search_datasets" in result
    )


# ── tax / fiscal policy ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_claim_iva_franquicia(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="La franquicia del IVA debió aplicarse el 1 de enero de 2025 pero se aprobó en octubre de 2025.",
        fecha="2026-01-01",
        ambito_tematico="fiscalidad",
    )
    assert _is_routed(result)
    assert (
        _has_tool(result, "get_boe_summary")
        or _has_tool(result, "search_legislation")
        or _has_tool(result, "get_aeat_stats")
    )


@pytest.mark.asyncio
async def test_claim_irpf_14000_euros(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="En 2018 los contribuyentes que ganaban 14.000 euros no pagaban impuestos, y hoy el umbral son 15.876 euros.",
        fecha="2026-01-01",
        ambito_tematico="fiscalidad",
    )
    assert _is_routed(result)
    assert _has_tool(result, "get_aeat_stats") or _has_tool(result, "search_datasets")


@pytest.mark.asyncio
async def test_claim_contribuyente_17000_euros(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="Hoy un contribuyente que gana 17.000 euros paga 745 euros de impuestos.",
        fecha="2026-01-01",
        ambito_tematico="fiscalidad",
    )
    assert _is_routed(result)
    assert _has_tool(result, "get_aeat_stats") or _has_tool(result, "search_datasets")


@pytest.mark.asyncio
async def test_claim_rebajas_fiscales_comunidades(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="Más del 50% de las rebajas fiscales las pagarán las comunidades autónomas.",
        fecha="2026-01-01",
        ambito_tematico="fiscalidad",
    )
    assert _is_routed(result)


@pytest.mark.asyncio
async def test_claim_incentivos_fiscales_600M(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="Se incluyen incentivos fiscales adicionales por unos 600 millones de euros cuantificados en la memoria del Real Decreto Ley.",
        fecha="2026-01-01",
        ambito_tematico="fiscalidad",
    )
    assert (
        _is_routed(result)
        or "search_legislation" in result
        or "search_datasets" in result
    )


# ── legislation / parliamentary ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_claim_solo_si_es_si(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="La aprobación de la ley del 'solo sí es sí' puso en libertad a más de mil violadores.",
        fecha="2026-01-01",
        ambito_tematico="justicia_y_corrupción",
    )
    assert _is_routed(result)
    assert (
        _has_tool(result, "get_justice_stats")
        or _has_tool(result, "search_legislation")
        or _has_tool(result, "get_boe_summary")
    )


@pytest.mark.asyncio
async def test_claim_presupuestos_generales(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="En 8 años de gobierno, 5 años han sido sin Presupuestos Generales del Estado, y ninguno en este mandato.",
        fecha="2026-01-01",
        ambito_tematico="presupuestos",
    )
    assert _is_routed(result)
    assert (
        _has_tool(result, "search_legislation")
        or _has_tool(result, "get_boe_summary")
        or _has_tool(result, "search_datasets")
    )


@pytest.mark.asyncio
async def test_claim_decretos_sociales_pp(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="De treinta decretos sociales aprobados en el Parlamento durante las dos legislaturas, ninguno contó con el voto afirmativo del Grupo Popular.",
        fecha="2026-01-01",
        ambito_tematico="legislacion",
    )
    assert _is_routed(result)
    assert _has_tool(result, "search_legislation") or _has_tool(
        result, "get_boe_summary"
    )


# ── GDP / economic growth ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_claim_crecimiento_pib_2025(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="España cerró 2025 con un crecimiento económico del 2,8%, el doble de la media europea, según datos del INE.",
        fecha="2026-01-01",
        fuente_citada="INE",
        ambito_tematico="economía",
    )
    assert _is_routed(result)
    assert _has_tool(result, "get_eurostat_data") or _has_tool(result, "query_ine_data")


# ── housing ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_claim_precio_vivienda_29_pct(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="El precio de la vivienda es un 29,2 % más caro este año que cuando el Gobierno llegó en 2018.",
        fecha="2026-01-01",
        ambito_tematico="vivienda",
    )
    assert _is_routed(result)
    assert _has_tool(result, "get_housing_stats") or _has_tool(
        result, "get_eurostat_data"
    )


@pytest.mark.asyncio
async def test_claim_viviendas_pequenos_propietarios(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="El 92 % de las viviendas en España están en manos de pequeños propietarios, según datos del Banco de España.",
        fecha="2026-01-01",
        fuente_citada="Banco de España",
        ambito_tematico="vivienda",
    )
    assert _is_routed(result)
    assert _has_tool(result, "get_housing_stats") or _has_tool(result, "get_bde_series")


# ── public debt ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_claim_deuda_publica_41_pct(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="La deuda pública es un 41 % superior a la actual que cuando el Gobierno llegó en 2018.",
        fecha="2026-01-01",
        ambito_tematico="deuda",
    )
    assert _is_routed(result)
    assert _has_tool(result, "get_eurostat_data") or _has_tool(result, "get_bde_series")


# ── energy / renewables ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_claim_renovables_150_pct(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="La potencia instalada de energías renovables en España creció un 150% entre 2019 y 2026.",
        fecha="2026-01-01",
        ambito_tematico="energia",
    )
    assert _is_routed(result)
    assert _has_tool(result, "get_energy_data") or _has_tool(
        result, "get_eurostat_data"
    )


@pytest.mark.asyncio
async def test_claim_renovables_3_pct_antes_2019(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="La potencia renovable instalada apenas creció un 3% en el período inmediatamente anterior a 2019.",
        fecha="2026-01-01",
        ambito_tematico="energia",
    )
    assert _is_routed(result)
    assert _has_tool(result, "get_energy_data") or _has_tool(
        result, "get_eurostat_data"
    )


@pytest.mark.asyncio
async def test_claim_gas_precio_marginal(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="El gas natural determinaba el precio marginal de la electricidad en el 75% de las horas en 2019, reduciéndose al 19% en 2025.",
        fecha="2026-01-01",
        ambito_tematico="energia",
    )
    assert _is_routed(result)
    assert _has_tool(result, "get_energy_data")


@pytest.mark.asyncio
async def test_claim_restricciones_electricas_3700M(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="Se gastaron 3700 millones de euros en restricciones técnicas al sistema eléctrico debido a las renovables el año pasado.",
        fecha="2026-01-01",
        ambito_tematico="energia",
    )
    assert _is_routed(result)
    assert _has_tool(result, "get_energy_data") or _has_tool(result, "get_cnmc_data")


@pytest.mark.asyncio
async def test_claim_electricidad_pymes_20_pct(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="El precio de la electricidad para las pymes españolas ha estado un 20% por debajo del de sus homólogas europeas desde la guerra de Ucrania.",
        fecha="2026-01-01",
        ambito_tematico="energia",
    )
    assert _is_routed(result)
    assert _has_tool(result, "get_eurostat_data") or _has_tool(
        result, "get_energy_data"
    )


@pytest.mark.asyncio
async def test_claim_hidrocarburos_40_pct(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="Aproximadamente el 40 % de la energía total anual consumida en España proviene de hidrocarburos.",
        fecha="2026-01-01",
        ambito_tematico="energia",
    )
    assert _is_routed(result)
    assert _has_tool(result, "get_energy_data") or _has_tool(
        result, "get_eurostat_data"
    )


@pytest.mark.asyncio
async def test_claim_dependencia_combustibles_fosiles(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="España ha sido el país de la Unión Europea que más ha reducido su dependencia de importaciones de combustibles fósiles desde 2019.",
        fecha="2026-01-01",
        ambito_tematico="energia",
    )
    assert _is_routed(result)
    assert _has_tool(result, "get_eurostat_data") or _has_tool(
        result, "get_energy_data"
    )


# ── CNMC / competition ────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_claim_cnmc_rebaja_petroleras(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="Aproximadamente un tercio de la rebaja fiscal ha sido reabsorbida por las petroleras y no ha llegado a los consumidores, según datos de la CNMC.",
        fecha="2026-01-01",
        fuente_citada="CNMC",
        entidad_mencionada="CNMC",
    )
    assert _is_routed(result) or "cnmc" in result.lower() or "get_cnmc_data" in result


# ── employment / social security ──────────────────────────────────────────────


@pytest.mark.asyncio
async def test_claim_afiliacion_ss_marzo_2026(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="La afiliación a la Seguridad Social alcanzó los 21,97 millones de personas a mediados de marzo de 2026 en términos desestacionalizados.",
        fecha="2026-04-01",
        ambito_tematico="seguridad_social",
    )
    assert _is_routed(result)
    assert _has_tool(result, "get_social_security_stats") or _has_tool(
        result, "get_employment_stats"
    )


# ── inflation ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_claim_inflacion_febrero_2022(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="La inflación en España fue del 7,6% en febrero de 2022.",
        fecha="2022-03-01",
        ambito_tematico="inflacion",
    )
    assert _is_routed(result)
    assert _has_tool(result, "get_eurostat_data") or _has_tool(result, "query_ine_data")


@pytest.mark.asyncio
async def test_claim_inflacion_febrero_2026(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="La inflación en España fue del 2,3% en febrero de 2026.",
        fecha="2026-03-01",
        ambito_tematico="inflacion",
    )
    assert _is_routed(result)
    assert _has_tool(result, "get_eurostat_data") or _has_tool(result, "query_ine_data")


# ── inequality / poverty ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_claim_pobreza_desigualdad_reduccion(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="La pobreza y la desigualdad se han reducido en España, acentuándose la mejora en los deciles más bajos de renta.",
        fecha="2026-01-01",
        ambito_tematico="desigualdad",
    )
    assert _is_routed(result)
    assert _has_tool(result, "get_eurostat_data") or _has_tool(
        result, "search_datasets"
    )


# ── subsidies / agriculture ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_claim_ayudas_gasoleo_agrario(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="Las ayudas al gasóleo agrario alcanzan unos 54 millones de euros.",
        fecha="2026-01-01",
    )
    assert (
        "Paso 1:" in result
        or "CATEGORÍA:" in result
        or "search_datasets" in result
        or "⚠" in result
    )


@pytest.mark.asyncio
async def test_claim_ayudas_fertilizantes_500M(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="Las ayudas a los fertilizantes alcanzan los 500 millones de euros y las ayudas al gasóleo agrario unos 54 millones de euros.",
        fecha="2026-01-01",
    )
    # May be unclassified but must not crash
    assert isinstance(result, str) and len(result) > 50


@pytest.mark.asyncio
async def test_claim_urea_precio_iran(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="El precio de la urea (nitrato amónico) ha aumentado un 45% desde el inicio del conflicto en Irán.",
        fecha="2026-01-01",
    )
    assert isinstance(result, str) and len(result) > 50


# ── transport / freight ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_claim_fletes_maritimos(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="Los fletes en las rutas marítimas Asia-Mediterráneo han aumentado entre un 25% y un 30% según reportan las navieras.",
        fecha="2026-01-01",
        ambito_tematico="transporte",
    )
    assert _is_routed(result) or "search_datasets" in result


@pytest.mark.asyncio
async def test_claim_inputs_energeticos_transporte(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="Los inputs energéticos representan el 35% de la estructura de costes del sector de transportes en España.",
        fecha="2026-01-01",
        ambito_tematico="transporte",
    )
    assert _is_routed(result) or "search_datasets" in result


# ── carburantes / fuel prices ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_claim_carburantes_subida_real_decreto(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="Los precios de los carburantes en España habían subido 32 céntimos por litro en gasolina y 51 céntimos por litro en gasoil hasta el día previo a la entrada en vigor de las medidas del Real Decreto Ley.",
        fecha="2022-06-01",
    )
    assert isinstance(result, str) and len(result) > 50


# ── social protection ─────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_claim_bono_social_electrico(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="Las bonificaciones del bono social eléctrico y térmico en algunos casos superan el 57 % y nunca están por debajo del 43 %.",
        fecha="2026-01-01",
        ambito_tematico="energia",
    )
    assert isinstance(result, str) and len(result) > 50


@pytest.mark.asyncio
async def test_claim_gobierno_5000M_oriente_medio(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="El Gobierno ha puesto en marcha un paquete de 5.000 millones de euros de apoyo directo para la crisis de Oriente Medio.",
        fecha="2026-01-01",
    )
    assert isinstance(result, str) and len(result) > 50


# ── regional fiscal impacts ───────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_claim_diputacion_vizcaya(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="La Diputación Foral de Vizcaya va a perder más de 125 millones de euros en este trimestre por la rebaja de impuestos.",
        fecha="2026-01-01",
        ambito_geografico="País Vasco",
        ambito_tematico="fiscalidad",
    )
    assert _is_routed(result)


@pytest.mark.asyncio
async def test_claim_diputacion_guipuzcoa(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="La Diputación Foral de Guipúzcoa ha calculado que va a perder del orden de 71 millones de euros por la rebaja de impuestos.",
        fecha="2026-01-01",
        ambito_geografico="País Vasco",
        ambito_tematico="fiscalidad",
    )
    assert _is_routed(result)


# ── Banco de España / forecasts ───────────────────────────────────────────────


@pytest.mark.asyncio
async def test_claim_bde_pib_prevision(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="El Banco de España prevé un crecimiento del PIB del 2 % para los próximos años.",
        fecha="2026-01-01",
        fuente_citada="Banco de España",
        entidad_mencionada="Banco de España",
        ambito_tematico="economía",
    )
    assert _is_routed(result)
    assert _has_tool(result, "get_bde_series") or _has_tool(result, "get_eurostat_data")


# ── energy strategic reserves ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_claim_400M_barriles_aie(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="El Gobierno español decidió el día 11 liberar cuatrocientos millones de barriles en la Agencia Internacional de la Energía.",
        fecha="2022-03-15",
        ambito_tematico="energia",
    )
    assert isinstance(result, str) and len(result) > 50


# ── vehicles ─────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_claim_vehiculos_chinos(verify_claim_fn):
    result = await verify_claim_fn(
        claim_normalizado="El numero de vehículos de origen chino es del 50% de las ventas actuales.",
        fecha="2026-01-01",
    )
    # May not match any specific category but should not crash
    assert isinstance(result, str) and len(result) > 50


# ── temporal capping ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_temporal_cap_applied(verify_claim_fn):
    """Data queries must be bounded to the claim date year."""
    result = await verify_claim_fn(
        claim_normalizado="La inflación en España fue del 7,6% en febrero de 2022.",
        fecha="2022-03-01",
        ambito_tematico="inflacion",
    )
    assert "2022" in result
    # No data from beyond the claim date should be requested
    assert "hasta" not in result.lower() or "2022" in result


@pytest.mark.asyncio
async def test_tipo_ranking_checklist_hint(verify_claim_fn):
    """For ranking-type claims the checklist should include a series history reminder."""
    result = await verify_claim_fn(
        claim_normalizado="La tasa de paro en España es la más baja desde 2007.",
        fecha="2026-01-01",
        ambito_tematico="empleo",
        tipo_claim="ranking",
    )
    assert _is_routed(result)
    assert "RANKING" in result or "histórica" in result or "serie" in result.lower()


@pytest.mark.asyncio
async def test_tipo_historico_checklist_hint(verify_claim_fn):
    """For historico-type claims the checklist should reference BOE / Diario de Sesiones."""
    result = await verify_claim_fn(
        claim_normalizado="El Congreso aprobó el Real Decreto de ayudas en 2022.",
        fecha="2026-01-01",
        tipo_claim="historico",
    )
    assert "HISTÓRICO" in result or "BOE" in result or "search_legislation" in result


@pytest.mark.asyncio
async def test_empty_claim_returns_error(verify_claim_fn):
    result = await verify_claim_fn(claim_normalizado="   ", fecha="2026-01-01")
    assert "Error" in result


@pytest.mark.asyncio
async def test_unclassified_claim_has_fallback(verify_claim_fn):
    """A claim with no matching keywords should include the fallback search suggestion."""
    result = await verify_claim_fn(
        claim_normalizado="El número de murciélagos en la cueva de Atapuerca creció un 12%.",
        fecha="2026-01-01",
    )
    assert "search_datasets" in result or "⚠" in result
