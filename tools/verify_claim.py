"""
Meta-tool for political and economic claim verification.

This tool analyzes a Spanish-language claim, routes it to the appropriate
data sources, and returns a structured verification plan: what data to
retrieve, from which sources, and how to interpret the result.

It does NOT fetch data itself — it produces a structured routing plan
that tells the LLM which tool calls to make next. The LLM then executes
those tool calls and synthesizes the final verdict.

Routing uses four complementary signals:
  1. Keyword matching on claim_normalizado (broadest coverage)
  2. ambito_tematico taxonomy (catches claims that keywords miss)
  3. entidad_mencionada / fuente_citada (adds entity-specific hints)
  4. ambito_geografico (adds regional portal hints)
"""

from mcp.server.fastmcp import FastMCP

from helpers.logging import log_tool

# ---------------------------------------------------------------------------
# Claim classification rules
# Each rule: list of trigger keywords → routing plan
# ---------------------------------------------------------------------------

_ROUTING_RULES: list[dict] = [
    # ── GDP / Economic growth ──────────────────────────────────────────────
    {
        "keywords": ["pib", "crecimiento económico", "crecimiento del pib", "gdp", "producto interior bruto", "contabilidad nacional"],
        "category": "GDP / Economic Growth",
        "sources": [
            {
                "tool": "get_eurostat_data",
                "args": {"topic": "gdp_growth", "geo": "ES,EU27_2020,DE,FR", "since_year": "2018"},
                "rationale": "Official EU-harmonised real GDP growth rates. Compare ES vs EU average.",
            },
            {
                "tool": "query_ine_data",
                "args": {"operation_code": "CN"},
                "rationale": "INE National Accounts (Contabilidad Nacional) — Spain's official GDP source.",
            },
        ],
        "verification_notes": (
            "GDP growth claims typically cite INE quarterly flash estimates or Eurostat annual data. "
            "For cross-country comparisons ('double the EU average') use Eurostat tec00001. "
            "For absolute GDP figures use INE Contabilidad Nacional (CN)."
        ),
    },
    # ── Inflation / Prices ─────────────────────────────────────────────────
    {
        "keywords": ["inflación", "ipc", "indice de precios", "precio consumo", "cpi", "hicp", "encarecimiento", "sube el precio"],
        "category": "Inflation / Consumer Prices",
        "sources": [
            {
                "tool": "get_eurostat_data",
                "args": {"topic": "inflation_hicp", "geo": "ES,EU27_2020", "since_year": "2021"},
                "rationale": "Eurostat HICP — harmonised EU inflation metric (monthly). Compare with EU avg.",
            },
            {
                "tool": "query_ine_data",
                "args": {"series_code": "IPC251856", "last_n_periods": 24},
                "rationale": "INE IPC General Nacional — official Spanish CPI series.",
            },
        ],
        "verification_notes": (
            "Spanish inflation is officially measured by INE's IPC. "
            "Eurostat uses the harmonised HICP (slightly different methodology). "
            "For specific months, check both INE and Eurostat. "
            "INE series IPC251856 = General CPI national index."
        ),
    },
    # ── Housing prices ─────────────────────────────────────────────────────
    {
        "keywords": ["precio vivienda", "precio de la vivienda", "piso", "hipoteca", "inmobiliario", "comprar casa", "alquiler", "desahucio", "ejecucion hipotecaria", "construccion vivienda"],
        "category": "Housing Prices",
        "sources": [
            {
                "tool": "get_housing_stats",
                "args": {"stat_type": "precios_vivienda"},
                "rationale": "Ministerio de Vivienda + INE IPV (official Spanish House Price Index) via datos.gob.es.",
            },
            {
                "tool": "get_eurostat_data",
                "args": {"topic": "house_prices", "geo": "ES,EU27_2020", "since_year": "2015"},
                "rationale": "Eurostat House Price Index (2015=100). Good for % change vs EU claims.",
            },
            {
                "tool": "get_housing_stats",
                "args": {"stat_type": "hipotecas"},
                "rationale": "Mortgage lending statistics — for claims about mortgage counts or affordability.",
            },
        ],
        "verification_notes": (
            "For 'X% more expensive than in year Y', use Eurostat prc_hpi_a (annual index, 2015=100). "
            "INE's IPV (Índice de Precios de Vivienda) is the national reference. "
            "For eviction/foreclosure claims, use get_housing_stats(stat_type='ejecuciones_hipotecarias'). "
            "Note: indices measure existing + new homes; new-only prices may differ."
        ),
    },
    # ── Employment / Unemployment ──────────────────────────────────────────
    {
        "keywords": ["paro", "desempleo", "tasa de paro", "empleo", "ocupados", "afiliados", "seguridad social", "epa", "activos", "parados"],
        "category": "Employment / Unemployment",
        "sources": [
            {
                "tool": "get_eurostat_data",
                "args": {"topic": "unemployment", "geo": "ES,EU27_2020", "since_year": "2018"},
                "rationale": "Eurostat annual unemployment rates. Compare Spain vs EU average.",
            },
            {
                "tool": "query_ine_data",
                "args": {"operation_code": "EPA"},
                "rationale": "INE EPA (Encuesta de Población Activa) — official quarterly labour force survey.",
            },
            {
                "tool": "get_employment_stats",
                "args": {"stat_type": "registered_unemployment"},
                "rationale": "SEPE registered unemployment data — monthly, by province.",
            },
        ],
        "verification_notes": (
            "Two different unemployment metrics exist: (1) INE EPA = survey-based (ILO methodology); "
            "(2) SEPE paro registrado = administrative count of registered unemployed (different base). "
            "Social Security affiliation = affiliated workers (different concept). "
            "Specify which metric is claimed."
        ),
    },
    # ── Wages / Purchasing power ───────────────────────────────────────────
    {
        "keywords": ["salario", "sueldo", "poder adquisitivo", "poder de compra", "smi", "salario mínimo", "nómina", "retribución"],
        "category": "Wages / Purchasing Power",
        "sources": [
            {
                "tool": "get_eurostat_data",
                "args": {"topic": "wages", "geo": "ES,EU27_2020,DE,FR", "since_year": "2018"},
                "rationale": "Eurostat earnings statistics. Compare Spain vs EU purchasing power.",
            },
            {
                "tool": "search_datasets",
                "args": {"query": "encuesta anual estructura salarial INE"},
                "rationale": "INE Encuesta Anual de Estructura Salarial — official wage distribution.",
            },
            {
                "tool": "get_aeat_stats",
                "args": {"stat_type": "irpf"},
                "rationale": "AEAT IRPF statistics include earned income distribution by bracket.",
            },
        ],
        "verification_notes": (
            "Wage claims often confuse gross vs net, mean vs median. "
            "INE's Encuesta de Estructura Salarial gives median gross/net wages. "
            "AEAT IRPF data shows declared income distribution. "
            "For 'net average wage' use INE's Encuesta de Presupuestos Familiares or OCDE data."
        ),
    },
    # ── Electricity / Energy prices ────────────────────────────────────────
    {
        "keywords": ["precio electricidad", "luz", "tarifa eléctrica", "pvpc", "factura luz", "precio energia", "precio kwh"],
        "category": "Electricity Prices",
        "sources": [
            {
                "tool": "get_eurostat_data",
                "args": {"topic": "electricity_prices_households", "geo": "ES,EU27_2020,DE,FR,IT", "since_year": "2019"},
                "rationale": "Eurostat household electricity prices. For 'Spain X% above/below EU' claims.",
            },
            {
                "tool": "get_eurostat_data",
                "args": {"topic": "electricity_prices_industry", "geo": "ES,EU27_2020,DE,FR,IT", "since_year": "2019"},
                "rationale": "Eurostat industrial/SME electricity prices.",
            },
            {
                "tool": "get_energy_data",
                "args": {"data_type": "market_prices"},
                "rationale": "REData wholesale market prices.",
            },
        ],
        "verification_notes": (
            "Electricity price claims need careful specification: household vs industrial, "
            "with/without taxes, spot market vs regulated tariff. "
            "For SME comparison use Eurostat nrg_pc_202 (band IC)."
        ),
    },
    # ── Renewable energy ───────────────────────────────────────────────────
    {
        "keywords": ["renovable", "energía renovable", "solar", "eólica", "potencia instalada", "cobertura renovable", "descarbonización"],
        "category": "Renewable Energy",
        "sources": [
            {
                "tool": "get_energy_data",
                "args": {"data_type": "installed_capacity", "start_date": "2019-01-01T00:00", "end_date": "2026-12-31T23:59", "time_trunc": "year"},
                "rationale": "REData installed capacity by technology per year.",
            },
            {
                "tool": "get_energy_data",
                "args": {"data_type": "generation_mix", "start_date": "2019-01-01T00:00", "end_date": "2025-12-31T23:59", "time_trunc": "year"},
                "rationale": "REData generation mix — renewable % of total generation per year.",
            },
            {
                "tool": "get_eurostat_data",
                "args": {"topic": "renewable_share", "geo": "ES,EU27_2020", "since_year": "2015"},
                "rationale": "Eurostat renewable share in final energy consumption (broader methodology).",
            },
        ],
        "verification_notes": (
            "Two metrics: (1) installed capacity (GW) — use REData potencia-instalada; "
            "(2) generation share (%) — use REData estructura-generacion. "
            "Eurostat uses the broader 'final energy consumption' denominator (heat + transport)."
        ),
    },
    # ── Gas / fossil fuels ─────────────────────────────────────────────────
    {
        "keywords": ["gas natural", "combustibles fósiles", "hidrocarburos", "gasoil", "gasolina", "dependencia energética", "precio marginal", "marginalista"],
        "category": "Gas / Fossil Fuels",
        "sources": [
            {
                "tool": "get_energy_data",
                "args": {"data_type": "generation_mix", "start_date": "2019-01-01T00:00", "end_date": "2025-12-31T23:59", "time_trunc": "year"},
                "rationale": "REData generation mix — shows gas's share of electricity generation per year.",
            },
            {
                "tool": "get_eurostat_data",
                "args": {"topic": "fossil_fuel_imports", "geo": "ES,EU27_2020,DE,FR,IT", "since_year": "2018"},
                "rationale": "Eurostat energy imports — track reduction in fossil fuel import dependency.",
            },
        ],
        "verification_notes": (
            "For 'gas as marginal price setter X% of hours' — this is OMIE/ESIOS data. "
            "REData shows gas generation share but not % of hours as marginal setter directly."
        ),
    },
    # ── Public debt / deficit ──────────────────────────────────────────────
    {
        "keywords": ["deuda pública", "deuda del estado", "déficit", "superávit", "presupuesto", "endeudamiento", "deuda pib", "transferencias comunidades", "financiación autonómica"],
        "category": "Public Debt / Deficit",
        "sources": [
            {
                "tool": "get_eurostat_data",
                "args": {"topic": "government_debt", "geo": "ES,EU27_2020", "since_year": "2018"},
                "rationale": "Eurostat Maastricht government debt (% of GDP). EU-comparable.",
            },
            {
                "tool": "get_eurostat_data",
                "args": {"topic": "government_deficit", "geo": "ES,EU27_2020", "since_year": "2018"},
                "rationale": "Eurostat government deficit/surplus (% of GDP).",
            },
            {
                "tool": "search_datasets",
                "args": {"query": "financiacion autonomica transferencias estado comunidades hacienda"},
                "rationale": "Ministerio de Hacienda publishes annual data on fiscal transfers to regions.",
            },
        ],
        "verification_notes": (
            "For 'record transfers to communities' claims, use Ministerio de Hacienda's official liquidation data. "
            "For debt/deficit % of GDP, use Eurostat gov_10dd_edpt1 (Maastricht criteria). "
            "Eurostat and BdE figures use the same ESA2010 methodology."
        ),
    },
    # ── Tax / Fiscal policy ────────────────────────────────────────────────
    {
        "keywords": ["irpf", "impuesto renta", "tipo impositivo", "tramo fiscal", "exención", "tributar", "declaración renta", "iva", "impuesto valor añadido", "contribuyente"],
        "category": "Tax / Fiscal Policy",
        "sources": [
            {
                "tool": "get_aeat_stats",
                "args": {"stat_type": "irpf"},
                "rationale": "AEAT IRPF statistics — income brackets, minimum exemption thresholds.",
            },
            {
                "tool": "get_aeat_stats",
                "args": {"stat_type": "iva"},
                "rationale": "AEAT IVA statistics — declared VAT, exemptions, franchise threshold.",
            },
            {
                "tool": "search_legislation",
                "args": {"query": "IRPF minimo exento rendimientos trabajo"},
                "rationale": "BOE consolidated legislation — the actual legal threshold for IRPF exemption.",
            },
        ],
        "verification_notes": (
            "IRPF threshold claims need the BOE (legal norm) + AEAT statistics for actual taxpayer counts. "
            "The 'mínimo para tributar' depends on marital status, disability, etc. — not a single figure. "
            "AEAT publishes yearly distributions showing how many taxpayers are in each bracket."
        ),
    },
    # ── Public procurement / subsidies ─────────────────────────────────────
    {
        "keywords": ["contratos públicos", "licitación", "subvención", "ayuda pública", "gasóleo agrario", "bono social"],
        "category": "Public Procurement / Subsidies",
        "sources": [
            {
                "tool": "search_public_contracts",
                "args": {"query": ""},
                "rationale": "PLACE public procurement platform — find specific contract or tender.",
            },
            {
                "tool": "search_datasets",
                "args": {"query": "subvenciones ayudas publicas BDNS"},
                "rationale": "BDNS (Base de Datos Nacional de Subvenciones) — all public subsidies.",
            },
        ],
        "verification_notes": (
            "For specific subsidy amounts, use BDNS search at hacienda.gob.es/bdnstrans. "
            "For procurement amounts, use PLACE open data files filtered by CPV code."
        ),
    },
    # ── Legislative / Parliamentary ─────────────────────────────────────────
    {
        "keywords": ["decreto", "ley", "norma", "aprobado", "parlamento", "congreso", "senado", "presupuestos generales", "reforma", "boe", "legislatura", "votó", "voto parlamentario", "impuesto al sol"],
        "category": "Legislation / Parliamentary",
        "sources": [
            {
                "tool": "search_legislation",
                "args": {"query": ""},
                "rationale": "BOE consolidated legislation — verify if a law exists and its text.",
            },
            {
                "tool": "get_boe_summary",
                "args": {},
                "rationale": "BOE daily summary for a specific date — verify publication of a decree/law.",
            },
        ],
        "verification_notes": (
            "For vote claims ('PP voted for X'), search BOE for the specific law and its parliamentary record. "
            "For 'N años sin Presupuestos Generales', check BOE for Ley de Presupuestos Generales by year. "
            "Parliamentary voting records are at congreso.es/public_oficiales/L15/CONG/DS."
        ),
    },
    # ── Financial sector / Banking ──────────────────────────────────────────
    {
        "keywords": ["banco", "beneficio bancario", "caixabank", "santander", "bbva", "sector financiero", "tipo interés", "euribor"],
        "category": "Financial Sector / Banking",
        "sources": [
            {
                "tool": "get_bde_series",
                "args": {"series_codes": "TI_1_2_1,TI_2_12_1", "time_range": "60M"},
                "rationale": "Banco de España series for ECB rate and 12-month EURIBOR.",
            },
            {
                "tool": "search_datasets",
                "args": {"query": "estadisticas sector bancario banco españa"},
                "rationale": "BdE banking statistics on datos.gob.es.",
            },
        ],
        "verification_notes": (
            "For bank profit claims (e.g. 'CaixaBank beneficio récord'), the authoritative source "
            "is the bank's annual report filed with CNMV. "
            "BdE publishes aggregate sector profitability, not individual bank figures."
        ),
    },
    # ── Transport / Freight ────────────────────────────────────────────────
    {
        "keywords": ["flete", "transporte marítimo", "camión", "costes transporte", "navieras"],
        "category": "Transport / Freight",
        "sources": [
            {
                "tool": "get_renfe_data",
                "args": {"data_type": "statistics"},
                "rationale": "Renfe transport statistics.",
            },
            {
                "tool": "search_datasets",
                "args": {"query": "estadisticas transporte ministerio"},
                "rationale": "Ministry of Transport open data on datos.gob.es.",
            },
        ],
        "verification_notes": (
            "Maritime freight rates are published by Drewry WCI or Shanghai Containerized Freight Index "
            "— not in Spanish gov data. For inland transport statistics use Ministerio de Transportes."
        ),
    },
    # ── Income inequality / Poverty ────────────────────────────────────────
    {
        "keywords": ["pobreza", "desigualdad", "gini", "decil", "percentil", "distribución renta", "condiciones de vida"],
        "category": "Inequality / Poverty",
        "sources": [
            {
                "tool": "get_eurostat_data",
                "args": {"topic": "poverty_inequality", "geo": "ES,EU27_2020", "since_year": "2015"},
                "rationale": "Eurostat Gini coefficient — income inequality, comparable across EU.",
            },
            {
                "tool": "query_ine_data",
                "args": {"operation_code": "ECV"},
                "rationale": "INE ECV (Encuesta de Condiciones de Vida) — poverty risk rates by decile.",
            },
        ],
        "verification_notes": (
            "For 'pobreza se ha reducido' claims, use INE ECV and Eurostat ilc_li02 (poverty risk rate). "
            "Gini measures inequality; poverty rate measures relative poverty threshold. "
            "Specify the metric and year carefully."
        ),
    },
    # ── Healthcare ─────────────────────────────────────────────────────────
    {
        "keywords": ["sanidad", "salud", "enfermera", "médico", "hospital", "sanitario", "personal sanitario", "camas hospitalarias", "pacientes", "sistema nacional de salud", "sns", "gasto sanitario", "lista de espera", "vacunacion", "vacuna"],
        "category": "Healthcare",
        "sources": [
            {
                "tool": "get_health_stats",
                "args": {"stat_type": "profesionales"},
                "rationale": "Ministerio de Sanidad — annual SIAP report: healthcare workforce (doctors, nurses, specialists) per 1,000 inhabitants by CCAA.",
            },
            {
                "tool": "get_health_stats",
                "args": {"stat_type": "gasto_sanitario"},
                "rationale": "Ministerio de Sanidad — public health expenditure by CCAA as % of GDP and per capita.",
            },
            {
                "tool": "get_eurostat_data",
                "args": {"topic": "custom", "dataset_code": "hlth_rs_prshp", "geo": "ES,EU27_2020", "since_year": "2018"},
                "rationale": "Eurostat healthcare personnel by category (nurses, physicians, dentists) — for EU comparisons.",
            },
            {
                "tool": "query_ine_data",
                "args": {"operation_code": "ENSE"},
                "rationale": "INE Encuesta Nacional de Salud (ENSE) — health outcomes, access, and lifestyle habits.",
            },
        ],
        "verification_notes": (
            "For nurse/doctor count claims, the primary sources are: "
            "(1) Ministerio de Sanidad SIAP — active healthcare professionals by category and CCAA; "
            "(2) Eurostat hlth_rs_prshp — EU-comparable counts. "
            "Note: registered vs active vs full-time-equivalent figures differ significantly. "
            "For waiting list claims, use get_health_stats(stat_type='listas_espera'). "
            "For spending claims, use get_health_stats(stat_type='gasto_sanitario')."
        ),
    },
    # ── Education ──────────────────────────────────────────────────────────
    {
        "keywords": ["abandono escolar", "fracaso escolar", "educacion", "educación", "matriculados", "universitarios", "titulados", "tasa escolar", "alumnos", "escolarización", "becas educacion", "gasto educativo", "formacion profesional"],
        "category": "Education",
        "sources": [
            {
                "tool": "get_education_stats",
                "args": {"stat_type": "abandono_escolar"},
                "rationale": "Ministerio de Educación annual statistics including early school leaving rate by CCAA.",
            },
            {
                "tool": "get_eurostat_data",
                "args": {"topic": "custom", "dataset_code": "edat_lfse_14", "geo": "ES,EU27_2020", "since_year": "2000"},
                "rationale": "Eurostat early school leaving rate (% 18-24 with at most lower secondary) — historical series from 2000.",
            },
        ],
        "verification_notes": (
            "School dropout rate ('tasa de abandono escolar temprano') = % of 18-24 year olds "
            "with at most lower secondary education who are not in education or training. "
            "Sources: Eurostat edat_lfse_14, INE EPA (microdata), Ministerio de Educación. "
            "For 'lowest ever' claims, use Eurostat series going back to 2000 (Spain peaked ~31% in 2008). "
            "For spending claims, use get_education_stats(stat_type='gasto_educativo')."
        ),
    },
    # ── Social Security / Pensions ─────────────────────────────────────────
    {
        "keywords": ["pensiones", "pensionistas", "cotizantes", "seguridad social", "sistema de pensiones", "jubilacion", "jubilación", "pensión media", "ratio pensionistas", "sostenibilidad pensiones"],
        "category": "Social Security / Pensions",
        "sources": [
            {
                "tool": "get_social_security_stats",
                "args": {"stat_type": "pensiones"},
                "rationale": "INSS pension statistics — number of pensions, average amount, by type and CCAA.",
            },
            {
                "tool": "get_social_security_stats",
                "args": {"stat_type": "cotizantes"},
                "rationale": "Social security contributors by regime, sector, sex and province.",
            },
            {
                "tool": "get_social_security_stats",
                "args": {"stat_type": "ratio_sostenibilidad"},
                "rationale": "Contributor-to-pensioner ratio — key system sustainability indicator.",
            },
            {
                "tool": "get_eurostat_data",
                "args": {"topic": "custom", "dataset_code": "spr_exp_pens", "geo": "ES,EU27_2020", "since_year": "2010"},
                "rationale": "Eurostat pension expenditure as % of GDP — for EU comparisons.",
            },
        ],
        "verification_notes": (
            "For 'highest pension ever' claims, confirm the metric: total expenditure, "
            "number of pensioners, or average monthly amount. "
            "The ratio cotizantes/pensionistas is the standard sustainability indicator. "
            "Provisional monthly figures are published by Social Security ~40 days after month-end."
        ),
    },
    # ── Traffic / Road safety ──────────────────────────────────────────────
    {
        "keywords": ["accidentes trafico", "siniestralidad vial", "muertos en carretera", "fallecidos trafico", "victimas trafico", "seguridad vial", "parque vehiculos", "matriculaciones", "vehiculo electrico"],
        "category": "Traffic / Road Safety",
        "sources": [
            {
                "tool": "get_traffic_stats",
                "args": {"stat_type": "victimas"},
                "rationale": "DGT road fatalities and injuries — annual series by road type, vehicle and province.",
            },
            {
                "tool": "get_traffic_stats",
                "args": {"stat_type": "accidentes"},
                "rationale": "DGT full accident statistics including near-fatal accidents and injury severity.",
            },
        ],
        "verification_notes": (
            "DGT publishes two counts: provisional (within ~2 weeks) and definitive (30-day survival criterion). "
            "The 30-day count (muertes a 30 días) is the EU-comparable figure. "
            "For EV adoption claims, use get_traffic_stats(stat_type='matriculaciones') + parque_vehiculos."
        ),
    },
    # ── Justice / Crime ────────────────────────────────────────────────────
    {
        "keywords": ["criminalidad", "delitos", "crimen", "delincuencia", "presos", "reclusos", "violencia genero", "femicidio", "feminicidio", "condenas", "corrupcion", "juzgados"],
        "category": "Justice / Crime",
        "sources": [
            {
                "tool": "get_justice_stats",
                "args": {"stat_type": "criminalidad"},
                "rationale": "Ministerio de Justicia crime statistics — offences by type, province and year.",
            },
            {
                "tool": "get_justice_stats",
                "args": {"stat_type": "violencia_genero"},
                "rationale": "Gender-based violence statistics — complaints, convictions, femicides.",
            },
        ],
        "verification_notes": (
            "Two separate crime datasets exist: (1) Ministerio del Interior — police-recorded offences; "
            "(2) CGPJ — judicial statistics (charges, convictions). These differ in scope and timing. "
            "For corruption cases, confirm whether the claim refers to charges, trials or convictions. "
            "For gender-based violence, the Delegación del Gobierno contra la VG publishes monthly data."
        ),
    },
    # ── Demographics ───────────────────────────────────────────────────────
    {
        "keywords": ["nacimientos", "natalidad", "defunciones", "mortalidad", "población", "padrón", "migración", "inmigrantes", "migraciones", "demografía", "fecundidad", "esperanza de vida"],
        "category": "Demographics",
        "sources": [
            {
                "tool": "query_ine_data",
                "args": {"operation_code": "MNP"},
                "rationale": "INE Movimiento Natural de la Población (MNP) — births, deaths, marriages. Annual and monthly data.",
            },
            {
                "tool": "search_datasets",
                "args": {"query": "estadistica nacimientos defunciones demografica INE"},
                "rationale": "INE demographic datasets on datos.gob.es — downloadable microdata and summary tables.",
            },
        ],
        "verification_notes": (
            "For birth count claims, use INE MNP (Estadística de Nacimientos). "
            "Provisional data is published ~4 months after year-end; definitive data ~18 months later. "
            "The exact figure for a given year may differ slightly between provisional and definitive releases. "
            "Confirm which release the claimant used."
        ),
    },
    # ── Business structure ─────────────────────────────────────────────────
    {
        "keywords": ["pymes", "empresa", "tejido empresarial", "autónomos", "micropymes", "grandes empresas", "número de empresas"],
        "category": "Business Structure",
        "sources": [
            {
                "tool": "search_datasets",
                "args": {"query": "directorio central empresas DIRCE INE estructura empresarial"},
                "rationale": "INE DIRCE (Directorio Central de Empresas) — official business census by size, sector, region.",
            },
            {
                "tool": "get_eurostat_data",
                "args": {"topic": "custom", "dataset_code": "sbs_sc_sca_r2", "geo": "ES,EU27_2020", "since_year": "2018"},
                "rationale": "Eurostat SME statistics — share of enterprises by size class.",
            },
        ],
        "verification_notes": (
            "For 'X% of companies are SMEs/pymes', use INE DIRCE which classifies firms by size. "
            "The EU definition of SME: <250 employees and ≤€50M turnover or ≤€43M balance sheet. "
            "The figure ~99% for Spain refers to all firms <250 employees; '98%' may refer to a "
            "stricter subset (e.g. excluding medium-sized firms). Check the exact size threshold used."
        ),
    },
]

# ---------------------------------------------------------------------------
# Lookup index: category name → rule
# ---------------------------------------------------------------------------

_RULES_BY_CATEGORY: dict[str, dict] = {rule["category"]: rule for rule in _ROUTING_RULES}

# ---------------------------------------------------------------------------
# Thematic taxonomy routing
# Maps ambito_tematico values → list of _ROUTING_RULES category names
# ---------------------------------------------------------------------------

_TEMATIC_ROUTING: dict[str, list[str]] = {
    # ── Spanish canonical values ───────────────────────────────────────────
    "economía":                ["GDP / Economic Growth", "Public Debt / Deficit", "Wages / Purchasing Power"],
    "justicia_y_corrupción":   ["Legislation / Parliamentary", "Public Procurement / Subsidies"],
    "medio_ambiente":          ["Renewable Energy", "Gas / Fossil Fuels"],
    "energia":                 ["Electricity Prices", "Renewable Energy", "Gas / Fossil Fuels"],
    "empleo":                  ["Employment / Unemployment", "Wages / Purchasing Power"],
    "trabajo":                 ["Employment / Unemployment", "Wages / Purchasing Power"],
    "política_social":         ["Employment / Unemployment", "Inequality / Poverty", "Demographics"],
    "vivienda":                ["Housing Prices"],
    "fiscalidad":              ["Tax / Fiscal Policy"],
    "contratacion_publica":    ["Public Procurement / Subsidies"],
    "transporte":              ["Transport / Freight"],
    "presupuestos":            ["Public Debt / Deficit", "Legislation / Parliamentary"],
    "sanidad":                 ["Healthcare"],
    "educación":               ["Education"],
    "educacion":               ["Education"],
    "demografía":              ["Demographics"],
    "demografia":              ["Demographics"],
    "inflación":               ["Inflation / Consumer Prices"],
    "inflacion":               ["Inflation / Consumer Prices"],
    "banca":                   ["Financial Sector / Banking"],
    "empresas":                ["Business Structure"],
    "tejido_empresarial":      ["Business Structure"],
    "desigualdad":             ["Inequality / Poverty"],
    "pobreza":                 ["Inequality / Poverty"],
    "pensiones":               ["Social Security / Pensions"],
    "seguridad_social":        ["Social Security / Pensions"],
    "trafico":                 ["Traffic / Road Safety"],
    "tráfico":                 ["Traffic / Road Safety"],
    "siniestralidad":          ["Traffic / Road Safety"],
    "criminalidad":            ["Justice / Crime"],
    "violencia_genero":        ["Justice / Crime"],
    "legislacion":             ["Legislation / Parliamentary"],
    "legislación":             ["Legislation / Parliamentary"],
    "corrupcion":              ["Justice / Crime", "Legislation / Parliamentary", "Public Procurement / Subsidies"],
    "corrupción":              ["Justice / Crime", "Legislation / Parliamentary", "Public Procurement / Subsidies"],
    "impuestos":               ["Tax / Fiscal Policy"],
    "tributos":                ["Tax / Fiscal Policy"],
    "deuda":                   ["Public Debt / Deficit"],
    "deficit":                 ["Public Debt / Deficit"],
    "déficit":                 ["Public Debt / Deficit"],
    "salarios":                ["Wages / Purchasing Power"],
    "precios":                 ["Inflation / Consumer Prices", "Housing Prices"],
    "electricidad":            ["Electricity Prices", "Renewable Energy"],
    # ── English aliases (ExtractedClaim supports bilingual values) ─────────
    "economy":                 ["GDP / Economic Growth", "Public Debt / Deficit", "Wages / Purchasing Power"],
    "health":                  ["Healthcare"],
    "healthcare":              ["Healthcare"],
    "education":               ["Education"],
    "environment":             ["Renewable Energy", "Gas / Fossil Fuels"],
    "energy":                  ["Electricity Prices", "Renewable Energy", "Gas / Fossil Fuels"],
    "employment":              ["Employment / Unemployment", "Wages / Purchasing Power"],
    "labor":                   ["Employment / Unemployment", "Wages / Purchasing Power"],
    "labour":                  ["Employment / Unemployment", "Wages / Purchasing Power"],
    "housing":                 ["Housing Prices"],
    "taxation":                ["Tax / Fiscal Policy"],
    "fiscal_policy":           ["Tax / Fiscal Policy"],
    "public_debt":             ["Public Debt / Deficit"],
    "justice":                 ["Justice / Crime", "Legislation / Parliamentary"],
    "crime":                   ["Justice / Crime"],
    "corruption":              ["Justice / Crime", "Legislation / Parliamentary", "Public Procurement / Subsidies"],
    "traffic":                 ["Traffic / Road Safety"],
    "road_safety":             ["Traffic / Road Safety"],
    "pensions":                ["Social Security / Pensions"],
    "social_security":         ["Social Security / Pensions"],
    "demographics":            ["Demographics"],
    "social_policy":           ["Employment / Unemployment", "Inequality / Poverty", "Demographics"],
    "inequality":              ["Inequality / Poverty"],
    "poverty":                 ["Inequality / Poverty"],
    "transport":               ["Transport / Freight"],
    "business":                ["Business Structure"],
    "inflation":               ["Inflation / Consumer Prices"],
    "banking":                 ["Financial Sector / Banking"],
    "procurement":             ["Public Procurement / Subsidies"],
}

# ---------------------------------------------------------------------------
# Entity-specific hints
# Maps lowercased entity name fragment → additional source entries
# ---------------------------------------------------------------------------

_ENTITY_HINTS: dict[str, list[dict]] = {
    "ine": [
        {
            "tool": "get_ine_operations",
            "args": {},
            "rationale": "INE is the cited source — browse available statistical operations first.",
        },
    ],
    "eurostat": [
        {
            "tool": "get_eurostat_data",
            "args": {"topic": "custom"},
            "rationale": "Eurostat is the cited source — use topic='custom' with dataset_code= for precise lookup.",
        },
    ],
    "banco de españa": [
        {
            "tool": "get_bde_series",
            "args": {"series_codes": ""},
            "rationale": "Banco de España is mentioned — search its statistical series.",
        },
    ],
    "tribunal de cuentas": [
        {
            "tool": "search_datasets",
            "args": {"query": "tribunal de cuentas informe fiscalización"},
            "rationale": "Tribunal de Cuentas publishes audit and investigation reports as open data.",
        },
        {
            "tool": "search_legislation",
            "args": {"query": "tribunal de cuentas"},
            "rationale": "Check BOE for Tribunal de Cuentas resolutions and procedures.",
        },
    ],
    "ministerio de hacienda": [
        {
            "tool": "search_datasets",
            "args": {"query": "transferencias financiacion autonomica liquidacion presupuestos hacienda"},
            "rationale": "Ministerio de Hacienda publishes annual fiscal transfer and budget execution data.",
        },
        {
            "tool": "get_aeat_stats",
            "args": {"stat_type": "recaudacion"},
            "rationale": "AEAT (under Hacienda) publishes annual tax revenue totals.",
        },
    ],
    "congreso": [
        {
            "tool": "search_legislation",
            "args": {"query": ""},
            "rationale": "Congressional votes are recorded in the BOE and official parliamentary gazette.",
        },
        {
            "tool": "get_boe_summary",
            "args": {},
            "rationale": "BOE publishes legislation passed by Congress on the date of approval.",
        },
    ],
    "enfermería": [
        {
            "tool": "search_datasets",
            "args": {"query": "profesionales sanitarios enfermeras ministerio sanidad SIAP"},
            "rationale": "Ministerio de Sanidad SIAP tracks active healthcare professionals by category.",
        },
    ],
    "ministerio de sanidad": [
        {
            "tool": "search_datasets",
            "args": {"query": "estadisticas sanitarias recursos humanos ministerio sanidad"},
            "rationale": "Ministerio de Sanidad publishes workforce and activity statistics (SNS).",
        },
    ],
    "aeat": [
        {
            "tool": "get_aeat_stats",
            "args": {"stat_type": "anuario_estadistico"},
            "rationale": "AEAT is the cited source — start with the full statistical yearbook.",
        },
    ],
    "agencia tributaria": [
        {
            "tool": "get_aeat_stats",
            "args": {"stat_type": "anuario_estadistico"},
            "rationale": "Agencia Tributaria is the cited source — start with the full statistical yearbook.",
        },
    ],
    "red electrica": [
        {
            "tool": "get_energy_data",
            "args": {"data_type": "generation_mix"},
            "rationale": "Red Eléctrica REData is the primary source for electricity generation data.",
        },
    ],
    "cnmv": [
        {
            "tool": "search_datasets",
            "args": {"query": "CNMV resultados empresas cotizadas cuentas anuales"},
            "rationale": "CNMV is the regulator for listed companies — corporate profits are filed here.",
        },
    ],
    "sepe": [
        {
            "tool": "get_employment_stats",
            "args": {"stat_type": "registered_unemployment"},
            "rationale": "SEPE publishes registered unemployment (paro registrado) monthly.",
        },
    ],
    "departament d'empresa": [
        {
            "tool": "search_regional_contracts",
            "args": {"region": "cataluña", "query": "empreses estructura empresarial"},
            "rationale": "Departament d'Empresa i Treball (Generalitat de Catalunya) publishes regional business data.",
        },
    ],
    "ministerio de educación": [
        {
            "tool": "search_datasets",
            "args": {"query": "estadistica educacion abandono escolar ministerio educacion"},
            "rationale": "Ministerio de Educación publishes annual education statistics.",
        },
    ],
}

# ---------------------------------------------------------------------------
# Geographic scope hints
# Maps normalized region name fragment → additional regional source entries
# ---------------------------------------------------------------------------

def _geo_ckan(region_slug: str, label: str, portal_url: str) -> list[dict]:
    """Helper to build a standard datos.gob.es publisher hint for a CCAA."""
    return [
        {
            "tool": "search_datasets",
            "args": {"query": f"estadistica {label.lower()}", "publisher": region_slug},
            "rationale": f"{label} datasets indexed on datos.gob.es (publisher: {region_slug}). Portal: {portal_url}",
        }
    ]


_GEO_HINTS: dict[str, list[dict]] = {
    # ── Communities with native CKAN portals ──────────────────────────────
    "cataluña": [
        {
            "tool": "search_regional_contracts",
            "args": {"region": "cataluña", "query": ""},
            "rationale": "Generalitat de Catalunya — analisi.transparenciacatalunya.cat (CKAN).",
        },
        {
            "tool": "search_datasets",
            "args": {"query": "generalitat catalunya estadistica", "publisher": "generalitat-de-catalunya"},
            "rationale": "Catalan government datasets indexed on datos.gob.es.",
        },
    ],
    "catalunya": [  # Catalan spelling alias
        {
            "tool": "search_regional_contracts",
            "args": {"region": "cataluña", "query": ""},
            "rationale": "Generalitat de Catalunya — analisi.transparenciacatalunya.cat (CKAN).",
        },
    ],
    "madrid": [
        {
            "tool": "search_regional_contracts",
            "args": {"region": "madrid", "query": ""},
            "rationale": "Comunidad de Madrid — datos.comunidad.madrid (CKAN).",
        },
    ],
    "comunidad valenciana": [
        {
            "tool": "search_regional_contracts",
            "args": {"region": "valencia", "query": ""},
            "rationale": "Generalitat Valenciana — dadesobertes.gva.es (CKAN).",
        },
    ],
    "valencia": [  # short form alias
        {
            "tool": "search_regional_contracts",
            "args": {"region": "valencia", "query": ""},
            "rationale": "Generalitat Valenciana — dadesobertes.gva.es (CKAN).",
        },
    ],
    "país vasco": [
        {
            "tool": "search_datasets",
            "args": {"query": "euskadi estadistica", "publisher": "gobierno-vasco"},
            "rationale": "Gobierno Vasco — opendata.euskadi.eus (CKAN). Extensive open data portal.",
        },
    ],
    "aragón": [
        {
            "tool": "search_datasets",
            "args": {"query": "aragon estadistica", "publisher": "gobierno-de-aragon"},
            "rationale": "Gobierno de Aragón — opendata.aragon.es (CKAN). Portal: opendata.aragon.es",
        },
    ],
    "navarra": [
        {
            "tool": "search_datasets",
            "args": {"query": "navarra estadistica", "publisher": "gobierno-de-navarra"},
            "rationale": "Gobierno de Navarra — gobiernoabierto.navarra.es/es/open-data (CKAN).",
        },
    ],
    "canarias": [
        {
            "tool": "search_datasets",
            "args": {"query": "canarias estadistica", "publisher": "gobierno-de-canarias"},
            "rationale": "Gobierno de Canarias — datos.canarias.es (CKAN).",
        },
    ],
    "castilla y león": [
        {
            "tool": "search_datasets",
            "args": {"query": "castilla leon estadistica", "publisher": "junta-de-castilla-y-leon"},
            "rationale": "Junta de Castilla y León — datosabiertos.jcyl.es (CKAN).",
        },
    ],
    # ── Communities with datos.gob.es presence ────────────────────────────
    "andalucía": _geo_ckan(
        "junta-de-andalucia", "Andalucía",
        "juntadeandalucia.es/institutodeestadisticaycartografia"
    ),
    "asturias": _geo_ckan(
        "gobierno-del-principado-de-asturias", "Asturias",
        "sadei.es"
    ),
    "islas baleares": _geo_ckan(
        "govern-de-les-illes-balears", "Illes Balears",
        "ibestat.caib.es"
    ),
    "cantabria": _geo_ckan(
        "gobierno-de-cantabria", "Cantabria",
        "icane.es"
    ),
    "castilla-la mancha": _geo_ckan(
        "junta-de-comunidades-de-castilla-la-mancha", "Castilla-La Mancha",
        "estadistica.castillalamancha.es"
    ),
    "extremadura": _geo_ckan(
        "junta-de-extremadura", "Extremadura",
        "estadistica.gobex.es"
    ),
    "galicia": _geo_ckan(
        "xunta-de-galicia", "Galicia",
        "ige.eu / abertos.xunta.gal"
    ),
    "murcia": _geo_ckan(
        "region-de-murcia", "Murcia",
        "crem.es"
    ),
    "la rioja": _geo_ckan(
        "gobierno-de-la-rioja", "La Rioja",
        "larioja.org/estadistica"
    ),
    "ceuta": _geo_ckan(
        "ciudad-autonoma-de-ceuta", "Ceuta",
        "ceuta.es"
    ),
    "melilla": _geo_ckan(
        "ciudad-autonoma-de-melilla", "Melilla",
        "melilla.es"
    ),
}

# ---------------------------------------------------------------------------
# Claim type verification strategies
# Maps tipo value → strategy description
# ---------------------------------------------------------------------------

_TYPE_STRATEGIES: dict[str, str] = {
    "estadistica_puntual": (
        "STRATEGY — Point-in-time statistic:\n"
        "  1. Locate the exact official figure for the stated metric in the stated year.\n"
        "  2. Compare directly with valor_afirmado.\n"
        "  3. Note any definitional differences (gross/net, survey/administrative, provisional/definitive).\n"
        "  4. If the source is cited (fuente_citada), check that source first and verify it supports the claim."
    ),
    "historico": (
        "STRATEGY — Historical fact or past action:\n"
        "  1. Search BOE/BORME for the specific legislation, vote, or administrative act.\n"
        "  2. If a date is known, use get_boe_summary for that date.\n"
        "  3. Check parliamentary records at congreso.es for voting history.\n"
        "  4. For events without a legal record (e.g. political decisions), use news archives or official press releases."
    ),
    "ranking": (
        "STRATEGY — Superlative or record claim (highest/lowest/best/worst ever):\n"
        "  1. CRITICAL: retrieve the longest available time series, not just recent years.\n"
        "     Use since_year='2000' or earlier, or time_range='MAX'.\n"
        "  2. Identify the true minimum/maximum across the entire series.\n"
        "  3. Be precise: 'lowest since 2008' is different from 'lowest ever'.\n"
        "  4. Check if the record is provisional data (may be revised) or definitive."
    ),
    "tendencia": (
        "STRATEGY — Trend claim (growing/declining/fastest):\n"
        "  1. Get the time series covering the stated or implied period.\n"
        "  2. Calculate the direction and magnitude of the trend.\n"
        "  3. Compare with the EU or peer-country trend for relative claims.\n"
        "  4. Check if the trend holds under different base years (cherry-pick risk)."
    ),
    "comparacion": (
        "STRATEGY — Comparative claim (vs another country/region/average):\n"
        "  1. Use Eurostat for EU-comparable data (same harmonised methodology).\n"
        "  2. Ensure the same reference year is used for all compared entities.\n"
        "  3. Verify the comparison group — 'EU average' can mean EU27, EU15, or eurozone.\n"
        "  4. Check if outliers or definitional differences distort the comparison."
    ),
    "proyeccion": (
        "STRATEGY — Projection or forecast claim:\n"
        "  1. Identify the model/institution that produced the projection (IMF, EC, Banco de España).\n"
        "  2. Verify the projection is from the stated institution and date.\n"
        "  3. Note that projections are not facts — compare with actual outturns if the projected period has passed.\n"
        "  4. Check if the projection has been revised since the claim was made."
    ),
}

# ---------------------------------------------------------------------------
# Routing helpers
# ---------------------------------------------------------------------------


def _route_by_keywords(claim: str) -> list[dict]:
    """Match routing rules by keyword scanning of the claim text."""
    claim_lower = claim.lower()
    return [rule for rule in _ROUTING_RULES if any(kw in claim_lower for kw in rule["keywords"])]


def _route_by_topic(ambito_tematico: str | None) -> list[dict]:
    """Map thematic taxonomy value to routing rules."""
    if not ambito_tematico:
        return []
    cats = _TEMATIC_ROUTING.get(ambito_tematico.lower().strip(), [])
    return [_RULES_BY_CATEGORY[c] for c in cats if c in _RULES_BY_CATEGORY]


def _get_entity_hints(entidad: str | None, fuente: str | None) -> list[dict]:
    """Return entity-specific tool hints based on entity name and/or cited source."""
    hints: list[dict] = []
    seen: set[str] = set()
    for text in [entidad, fuente]:
        if not text:
            continue
        text_lower = text.lower()
        for key, sources in _ENTITY_HINTS.items():
            if key in text_lower:
                for s in sources:
                    dedup_key = s["tool"] + str(sorted((s.get("args") or {}).items()))
                    if dedup_key not in seen:
                        seen.add(dedup_key)
                        hints.append(s)
    return hints


def _get_geo_hints(ambito_geografico: str | None) -> list[dict]:
    """Return regional portal hints for sub-national geographic scope."""
    if not ambito_geografico:
        return []
    geo_lower = ambito_geografico.lower().strip()
    hints: list[dict] = []
    seen: set[str] = set()
    for key, sources in _GEO_HINTS.items():
        if key in geo_lower or geo_lower in key:
            for s in sources:
                dedup_key = s["tool"] + str(sorted((s.get("args") or {}).items()))
                if dedup_key not in seen:
                    seen.add(dedup_key)
                    hints.append(s)
    return hints


def _merge_rules(keyword_rules: list[dict], topic_rules: list[dict]) -> list[dict]:
    """Combine keyword and topic rules, deduplicating by category."""
    seen: set[str] = set()
    merged: list[dict] = []
    for rule in keyword_rules + topic_rules:
        if rule["category"] not in seen:
            seen.add(rule["category"])
            merged.append(rule)
    return merged


def _parse_claim_year(date_str: str | None) -> int | None:
    """Extract a 4-digit year from a date string (YYYY, YYYY-MM, or YYYY-MM-DD)."""
    if not date_str:
        return None
    try:
        return int(str(date_str).strip()[:4])
    except (ValueError, IndexError):
        return None


def _apply_temporal_bounds(args: dict, cap_year: int | None) -> dict:
    """
    Adjust date-range arguments so that no query requests data beyond cap_year.

    Rules:
      - until_year → capped at cap_year
      - since_year with no until_year → until_year added (= cap_year)
      - end_date (ISO datetime "YYYY-...") → year portion capped at cap_year
    """
    if cap_year is None:
        return args
    modified = dict(args)
    if "until_year" in modified:
        try:
            modified["until_year"] = str(min(int(modified["until_year"]), cap_year))
        except (ValueError, TypeError):
            modified["until_year"] = str(cap_year)
    elif "since_year" in modified:
        modified["until_year"] = str(cap_year)
    if "end_date" in modified and modified["end_date"]:
        try:
            end_year = int(str(modified["end_date"])[:4])
            if end_year > cap_year:
                modified["end_date"] = f"{cap_year}-12-31T23:59"
        except (ValueError, IndexError):
            pass
    return modified


# ---------------------------------------------------------------------------
# Tool registration
# ---------------------------------------------------------------------------


def register_verify_claim_tool(mcp: FastMCP) -> None:
    @mcp.tool()
    @log_tool
    async def verify_claim(
        claim_normalizado: str,
        fecha: str,
        claim_raw: str | None = None,
        afirmado_por: str | None = None,
        entidad_mencionada: str | None = None,
        metrica: str | None = None,
        valor_afirmado: str | None = None,
        periodo_temporal: str | None = None,
        ambito_geografico: str | None = None,
        ambito_tematico: str | None = None,
        fuente_citada: str | None = None,
        idioma: str = "es",
        tipo_claim: str | None = None,
        intervention_orden: int | None = None,
        return_data: bool = False,
    ) -> str:
        """
        Analyze a Spanish political or economic claim and return a structured
        verification plan: which data sources to query, which tool calls to make,
        and how to interpret the results.

        This tool does NOT fetch data itself. It produces a routing plan that
        the LLM should follow by executing the recommended tool calls in order.

        Routing uses four signals in combination:
          - claim_normalizado: keyword matching against known economic/political topics
          - ambito_tematico: thematic taxonomy catches claims that keywords miss
          - entidad_mencionada + fuente_citada: entity-specific tool hints
          - ambito_geografico: adds regional portal hints for sub-national claims

        Args:
            claim_normalizado: The claim in clean, normalized Spanish. Names, dates,
                               and context should be made explicit
                               (e.g. "Santiago Abascal tiene 3 investigaciones en el Tribunal de Cuentas"
                               rather than "Usted tiene 3 investigaciones").
            fecha: Date when the claim was made — REQUIRED (YYYY, YYYY-MM, or YYYY-MM-DD).
                   All data queries are hard-capped at the year of this date: no source
                   will look at data published after this point, preventing anachronistic
                   fact-checking with data the speaker could not have known.
                   This is NOT the same as periodo_temporal (the period the claim talks about).
                   Example: "2026-03-25" (a claim made on 25 March 2026)
            claim_raw: Verbatim original text of the claim, including speaker context,
                       interjections, or original language (Catalan, Galician, etc.).
                       Used for display and audit trail only.
            afirmado_por: Who made the claim (person, party, or institution).
                          Example: "Pedro Sánchez", "Partido Popular", "Banco de España"
            entidad_mencionada: The institution or entity the claim is about.
                                Adds entity-specific data source hints.
                                Example: "INE", "Tribunal de Cuentas", "Ministerio de Hacienda"
            metrica: The specific metric being claimed.
                     Example: "número de investigaciones abiertas", "tasa de abandono escolar"
            valor_afirmado: The specific value being asserted. Used in the checklist.
                            Example: "3", "98%", "más baja de la historia", "más de 1500 millones"
            periodo_temporal: The time period the claim is talking about — distinct from fecha.
                              Used to focus queries on the relevant year/range, but never used
                              as the data cap (that is always fecha).
                              Example: "2022" (claim made in 2026 about births in 2022),
                              "2018-2023", "primer trimestre de 2024", "actual"
            ambito_geografico: Geographic scope of the claim. Canonical values:
                               All 17 CCAA + "España" + "Europa" / "Unión Europea" + "Internacional".
                               Example: "España", "Cataluña", "Madrid", "Comunidad Valenciana"
            ambito_tematico: Thematic category. Triggers routing rules even when
                             keyword matching fails. Accepts Spanish and English values.
                             Spanish: "sanidad", "educación", "economía", "justicia_y_corrupción",
                             "medio_ambiente", "vivienda", "demografía", "fiscalidad",
                             "contratacion_publica", "presupuestos", "empresas", "banca".
                             English: "health", "education", "economy", "environment",
                             "housing", "demographics", "taxation", "business", "banking".
            fuente_citada: Source cited by the claimant, or "No citada" / "No especificada".
                           Example: "INE", "Eurostat", "No citada"
            idioma: ISO 639-1 language code of claim_raw. Does not affect routing
                    (claim_normalizado is always Spanish). Example: "es", "ca", "gl", "eu"
            tipo_claim: Structural type of the claim — shapes the verification strategy:
                        - "estadistica_puntual": verify an exact figure in official data
                        - "historico": verify a past action or event via BOE/records
                        - "ranking": verify a superlative (lowest/highest ever) via full time series
                        - "tendencia": verify a directional trend over time
                        - "comparacion": verify a cross-country or cross-region comparison
                        - "proyeccion": verify a forecast or projection claim
            intervention_orden: Sequential position of the source intervention within
                                its session (1-based). Used for audit trail only.
            return_data: If True, note the first recommended source in the output.
                         Does not execute tool calls.

        Returns:
            For I1/I2/I3: explanation of why the claim is not data-verifiable.
            For V1–V5 and unset: structured verification plan with claim metadata,
            category routing, recommended tool calls with temporal bounds applied,
            type-specific strategy, and interpretation checklist.
        """
        if not claim_normalizado.strip():
            return "Error: claim_normalizado is required."

        # ── Resolve temporal cap (always from fecha) ──────────────────────
        # fecha = when the claim was made → hard upper bound for all data queries
        # periodo_temporal = what period the claim talks about → query focus only
        cap_year = _parse_claim_year(fecha)  # always set; fecha is required
        effective_cap = cap_year

        # Extract a reference year from periodo_temporal for query focus (since_year hint)
        ref_year_str: str | None = None
        if periodo_temporal and periodo_temporal.lower() not in ("actual", "actualidad", "presente"):
            candidate = periodo_temporal.strip()[:4]
            ref_year_str = candidate if candidate.isdigit() else None

        # ── Routing ───────────────────────────────────────────────────────
        keyword_rules = _route_by_keywords(claim_normalizado)
        topic_rules = _route_by_topic(ambito_tematico)
        matched_rules = _merge_rules(keyword_rules, topic_rules)
        entity_hints = _get_entity_hints(entidad_mencionada, fuente_citada)
        geo_hints = _get_geo_hints(ambito_geografico)

        # ── Header ────────────────────────────────────────────────────────
        lines: list[str] = [
            "CLAIM VERIFICATION PLAN",
            "─" * 64,
        ]
        if intervention_orden is not None:
            lines.append(f"Intervención: #{intervention_orden}")
        if claim_raw:
            lines.append(f"Original:   {claim_raw[:200]}")
        lines.append(f"Claim:      {claim_normalizado}")
        if afirmado_por:
            lines.append(f"Afirmado por: {afirmado_por}")
        cap_note = f"  → datos acotados al año {cap_year}" if cap_year else ""
        lines.append(f"Fecha:      {fecha}{cap_note}")
        if periodo_temporal:
            lines.append(f"Período referenciado: {periodo_temporal}")
        if metrica:
            lines.append(f"Métrica:    {metrica}")
        if valor_afirmado:
            lines.append(f"Valor afirmado: {valor_afirmado}")
        if ambito_geografico:
            lines.append(f"Ámbito geográfico: {ambito_geografico}")
        if ambito_tematico:
            lines.append(f"Ámbito temático: {ambito_tematico}")
        if fuente_citada and fuente_citada.lower() not in ("no especificada", "no citada", "not cited"):
            lines.append(f"Fuente citada: {fuente_citada}")
        if tipo_claim:
            lines.append(f"Tipo: {tipo_claim}")
        if idioma and idioma != "es":
            lines.append(f"Idioma original: {idioma}")
        lines.append("─" * 64)
        lines.append("")

        # ── Temporal note ─────────────────────────────────────────────────
        if cap_year:
            lines.append(
                f"⏱  Temporal scope: todas las consultas están acotadas al año {cap_year}.\n"
                f"   No se consultarán datos publicados después de {fecha}.\n"
            )

        # ── Unclassified fallback ─────────────────────────────────────────
        if not matched_rules and not entity_hints and not geo_hints:
            fallback_q = metrica or claim_normalizado[:60]
            lines += [
                "⚠  Esta afirmación no pudo clasificarse automáticamente.",
                "   Approach sugerido:",
                f'  1. search_datasets(query="{fallback_q}")',
                "  2. search_legislation o get_boe_summary — para afirmaciones legales",
                "  3. get_eurostat_data(topic='gdp_growth') — para contexto macroeconómico",
                "",
                "Portales de verificación manual:",
                "  • datos.gob.es — catálogo nacional",
                "  • ine.es — estadísticas nacionales",
                "  • bde.es — datos financieros y monetarios",
                "  • boe.es — boletín oficial y legislación",
            ]
            return "\n".join(lines)

        if matched_rules:
            lines.append(f"Categorías identificadas: {', '.join(r['category'] for r in matched_rules)}\n")

        # ── Type-specific strategy ────────────────────────────────────────
        if tipo and tipo in _TYPE_STRATEGIES:
            lines.append("═" * 50)
            lines.append(_TYPE_STRATEGIES[tipo])
            lines.append("")

        # ── Per-category routing plan ─────────────────────────────────────
        step_counter = 1
        for rule in matched_rules:
            lines.append("═" * 50)
            lines.append(f"CATEGORÍA: {rule['category']}")
            lines.append("─" * 50)
            lines.append("")

            for source_entry in rule["sources"]:
                tool_name = source_entry["tool"]
                raw_args = dict(source_entry.get("args") or {})
                rationale = source_entry["rationale"]

                # Inject reference period from año if available
                if ref_year_str:
                    if "since_year" in raw_args:
                        # keep since_year as-is; just bound the until_year
                        pass
                    # For ranking/full-history claims, don't override since_year

                # Cap temporal bounds at fecha year
                bounded_args = _apply_temporal_bounds(raw_args, effective_cap)

                # For ranking type, extend since_year as far back as possible
                if tipo == "ranking" and "since_year" in bounded_args:
                    bounded_args["since_year"] = "2000"

                args_str = ", ".join(
                    f'{k}="{v}"' if isinstance(v, str) else f"{k}={v}"
                    for k, v in bounded_args.items()
                    if v != ""
                )
                lines.append(f"  Paso {step_counter}: {tool_name}({args_str})")
                lines.append(f"  Por qué: {rationale}")

                changed = {
                    k: bounded_args[k]
                    for k in bounded_args
                    if bounded_args.get(k) != raw_args.get(k) or k not in raw_args
                }
                if effective_cap and changed:
                    changes_str = ", ".join(f"{k}={v}" for k, v in changed.items())
                    lines.append(f"  [Acotación temporal aplicada: {changes_str}]")
                lines.append("")
                step_counter += 1

            notes = rule.get("verification_notes", "")
            if notes:
                lines.append(f"Notas de interpretación:\n  {notes}")
            lines.append("")

        # ── Entity hints ──────────────────────────────────────────────────
        if entity_hints:
            lines.append("═" * 50)
            lines.append("FUENTES ESPECÍFICAS DE LA ENTIDAD MENCIONADA")
            lines.append("─" * 50)
            lines.append("")
            for hint in entity_hints:
                tool_name = hint["tool"]
                bounded_args = _apply_temporal_bounds(dict(hint.get("args") or {}), effective_cap)
                args_str = ", ".join(
                    f'{k}="{v}"' if isinstance(v, str) else f"{k}={v}"
                    for k, v in bounded_args.items()
                    if v != ""
                )
                lines.append(f"  Paso {step_counter}: {tool_name}({args_str})")
                lines.append(f"  Por qué: {hint['rationale']}")
                lines.append("")
                step_counter += 1

        # ── Geo hints ─────────────────────────────────────────────────────
        if geo_hints:
            lines.append("═" * 50)
            lines.append(f"FUENTES REGIONALES — {ambito_geografico}")
            lines.append("─" * 50)
            lines.append("")
            for hint in geo_hints:
                tool_name = hint["tool"]
                bounded_args = _apply_temporal_bounds(dict(hint.get("args") or {}), effective_cap)
                args_str = ", ".join(
                    f'{k}="{v}"' if isinstance(v, str) else f"{k}={v}"
                    for k, v in bounded_args.items()
                    if v != ""
                )
                lines.append(f"  Paso {step_counter}: {tool_name}({args_str})")
                lines.append(f"  Por qué: {hint['rationale']}")
                lines.append("")
                step_counter += 1

        # ── General checklist ─────────────────────────────────────────────
        lines.append("═" * 50)
        lines.append("CHECKLIST DE VERIFICACIÓN:")
        checklist_items = [
            "  □ Confirmar la métrica exacta (bruto/neto, encuesta/administrativo, %/absoluto)",
            "  □ Confirmar que el período de referencia coincide con la afirmación",
            "  □ Si se cita fuente, verificar primero en esa fuente y comprobar que respalda el claim",
            "  □ Para comparativas UE, asegurar que se usa el mismo dataset y metodología",
            "  □ Para afirmaciones legislativas, verificar en BOE (boe.es) fuente primaria",
            "  □ Para cifras de empresas (beneficios, inversiones), consultar registros CNMV",
        ]
        if valor_afirmado:
            checklist_items.append(
                f"  □ Localizar el valor oficial y comparar con el valor afirmado: {valor_afirmado}"
            )
        if cap_year:
            checklist_items.append(
                f"  □ Verificar el calendario de publicación: confirmar que los datos de {año or cap_year} "
                f"estaban publicados antes de {fecha}"
            )
        if afirmado_por:
            checklist_items.append(
                f"  □ Considerar el contexto retórico: afirmación de '{afirmado_por}' "
                f"puede omitir datos que contradicen la narrativa"
            )
        if tipo == "ranking":
            checklist_items.append(
                "  □ RANKING: verificar la serie histórica completa — 'mínimo histórico' requiere "
                "datos desde el inicio de la serie, no solo años recientes"
            )
        if tipo == "historico":
            checklist_items.append(
                "  □ HISTÓRICO: buscar el acto legislativo o administrativo concreto en BOE; "
                "las actas de votación están en el Diario de Sesiones del Congreso"
            )

        lines.append("\n".join(checklist_items))

        return "\n".join(lines)
