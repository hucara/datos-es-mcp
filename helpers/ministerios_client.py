"""
Shared client for Spanish ministry and government agency statistical data.

All these institutions publish their datasets on datos.gob.es. This module
provides:
  - A curated registry of each ministry's datos.gob.es publisher slug,
    stat_type queries, and known direct dataset IDs.
  - A generic search function that queries datos.gob.es by publisher + topic.

Covered institutions:
  Sanidad          — Ministerio de Sanidad / Sistema Nacional de Salud (SNS)
  Educación        — Ministerio de Educación y FP (MEFP)
  Vivienda         — Ministerio de Vivienda, Agenda Urbana y Territorio
  Tráfico (DGT)    — Dirección General de Tráfico
  Seguridad Social — Ministerio de Inclusión, Seguridad Social y Migraciones (INSS)
  Justicia         — Ministerio de Justicia / estadísticas judiciales y penales

Uses datos.gob.es semantic API (title/{keyword} endpoint).
"""

import logging
from typing import Any

import httpx

from helpers import datos_gob_es_client
from helpers.logging import MAIN_LOGGER_NAME
from helpers.user_agent import USER_AGENT

logger = logging.getLogger(MAIN_LOGGER_NAME)

# Registry: key → ministry config
_MINISTERIOS: dict[str, dict[str, Any]] = {
    # ------------------------------------------------------------------
    "sanidad": {
        "name": "Ministerio de Sanidad / Sistema Nacional de Salud",
        "publishers": [
            "ministerio-de-sanidad",
            "ministerio-de-sanidad-consumo-y-bienestar-social",
        ],
        "portal_url": "https://www.sanidad.gob.es/estadEstudios/estadisticas/home.htm",
        "stat_types": {
            "gasto_sanitario": {
                "query": "gasto sanitario financiacion publica comunidades autonomas",
                "description": "Public health expenditure by autonomous community and concept",
            },
            "camas_hospitalarias": {
                "query": "camas hospitalarias capacidad hospitalaria centros sanitarios",
                "description": "Hospital beds and healthcare centre capacity",
            },
            "profesionales": {
                "query": "profesionales sanitarios medicos enfermeras personal SNS",
                "description": "Healthcare professionals — doctors, nurses, specialists",
            },
            "listas_espera": {
                "query": "listas de espera cirugia diagnostica consultas SNS",
                "description": "Waiting lists for surgery, diagnostics and specialist consultations",
            },
            "mortalidad": {
                "query": "mortalidad defunciones causas muerte estadistica",
                "description": "Mortality statistics and causes of death",
            },
            "enfermedades": {
                "query": "enfermedades cronicas morbilidad hospitalizaciones",
                "description": "Chronic disease prevalence, hospitalisation rates",
            },
            "salud_mental": {
                "query": "salud mental trastornos psiquiatricos hospitalizacion",
                "description": "Mental health statistics and psychiatric care",
            },
            "vacunacion": {
                "query": "vacunacion cobertura vacunal programa vacunacion",
                "description": "Vaccination coverage by age group and autonomous community",
            },
            "encuesta_salud": {
                "query": "encuesta nacional salud ENSE habitos vida estilos",
                "description": "National Health Survey — lifestyle habits, self-assessed health",
            },
        },
        "default_stat_type": "gasto_sanitario",
    },
    # ------------------------------------------------------------------
    "educacion": {
        "name": "Ministerio de Educación y Formación Profesional (MEFP)",
        "publishers": [
            "ministerio-de-educacion-y-formacion-profesional",
            "ministerio-de-educacion-cultura-y-deporte",
        ],
        "portal_url": "https://www.educacionyfp.gob.es/servicios-al-ciudadano/estadisticas.html",
        "stat_types": {
            "abandono_escolar": {
                "query": "abandono escolar temprano tasa fracaso escolar",
                "description": "Early school leaving rate — overall and by autonomous community",
            },
            "matriculados": {
                "query": "matriculados alumnos escolarizacion enseñanzas no universitarias",
                "description": "Enrolment by educational stage, sex and autonomous community",
            },
            "universitarios": {
                "query": "matriculados universitarios enseñanza superior egresados",
                "description": "University enrolment, graduates and dropouts",
            },
            "profesorado": {
                "query": "profesorado ratio alumnos profesor personal docente",
                "description": "Teaching staff and student-to-teacher ratios",
            },
            "becas": {
                "query": "becas ayudas estudio becarios convocatorias",
                "description": "Scholarship grants — number of recipients and amounts",
            },
            "gasto_educativo": {
                "query": "gasto educativo financiacion publica educacion presupuesto",
                "description": "Public expenditure on education — % of GDP and per student",
            },
            "fp": {
                "query": "formacion profesional FP titulaciones ciclos",
                "description": "Vocational training — enrolment and graduate statistics",
            },
            "pisa": {
                "query": "PISA resultados evaluacion competencias lectura matematicas",
                "description": "PISA results and educational performance assessments",
            },
        },
        "default_stat_type": "abandono_escolar",
    },
    # ------------------------------------------------------------------
    "vivienda": {
        "name": "Ministerio de Vivienda, Agenda Urbana y Territorio",
        "publishers": [
            "ministerio-de-vivienda",
            "ministerio-de-transportes-movilidad-y-agenda-urbana",
        ],
        "portal_url": "https://www.mivau.gob.es/vivienda/estadisticas-y-publicaciones",
        "ine_operations": [
            "IPV",
            "IPVA",
            "HPT",
        ],  # House price index (IPV), rental index (IPVA), mortgages (HPT)
        "stat_types": {
            "precios_vivienda": {
                "query": "precio vivienda indice precios IPV compraventa transacciones",
                "description": "House price index (IPV) and property transaction statistics",
            },
            "alquileres": {
                "query": "alquiler vivienda precio renta indice arrendamiento",
                "description": "Rental prices and rental market statistics",
            },
            "hipotecas": {
                "query": "hipotecas prestamos hipotecarios estadistica notarial registral",
                "description": "Mortgage lending — new mortgages, amounts, interest rates",
            },
            "construccion": {
                "query": "visados construccion obra nueva licencias edificacion",
                "description": "Building permits and new housing starts",
            },
            "parque_viviendas": {
                "query": "parque de viviendas censo de viviendas stock vivienda",
                "description": "Housing stock — primary, secondary and vacant dwellings",
            },
            "vivienda_protegida": {
                "query": "vivienda protegida VPO vivienda de proteccion oficial social",
                "description": "Social and protected housing — new builds and allocations",
            },
            "ejecuciones_hipotecarias": {
                "query": "ejecuciones hipotecarias lanzamientos desahucios",
                "description": "Mortgage foreclosures and eviction statistics",
            },
        },
        "default_stat_type": "precios_vivienda",
    },
    # ------------------------------------------------------------------
    "trafico": {
        "name": "Dirección General de Tráfico (DGT)",
        "publishers": [
            "direccion-general-de-trafico",
        ],
        "portal_url": "https://www.dgt.es/inicio/estadisticas-e-indicadores/",
        "stat_types": {
            "accidentes": {
                "query": "accidentes trafico siniestralidad vial estadisticas",
                "description": "Road accident statistics — frequency, location, cause",
            },
            "victimas": {
                "query": "victimas fallecidos heridos accidentes trafico muertos",
                "description": "Road fatalities and injuries by road type, vehicle and cause",
            },
            "parque_vehiculos": {
                "query": "parque vehiculos matriculaciones censo vehiculos turismos",
                "description": "Vehicle fleet — cars, motorcycles, trucks by type and province",
            },
            "matriculaciones": {
                "query": "matriculaciones nuevos vehiculos registro vehiculos",
                "description": "New vehicle registrations — combustion vs electric, by province",
            },
            "carnet": {
                "query": "permisos conduccion carnet conductores licencias",
                "description": "Driving licences issued and holders by type and age",
            },
            "alcoholemia": {
                "query": "alcoholemia drogas conduccion controles",
                "description": "Drink/drug-driving controls and positive detection rates",
            },
            "velocidad": {
                "query": "velocidad cinemometros radares excesos velocidad",
                "description": "Speed control statistics and excess speed rates",
            },
        },
        "default_stat_type": "accidentes",
    },
    # ------------------------------------------------------------------
    "seguridad_social": {
        "name": "Ministerio de Inclusión, Seguridad Social y Migraciones (INSS)",
        "publishers": [
            "ministerio-de-inclusion-seguridad-social-y-migraciones",
            "secretaria-de-estado-de-la-seguridad-social",
            "instituto-nacional-de-la-seguridad-social",
        ],
        "portal_url": "https://www.seg-social.es/wps/portal/wss/internet/EstadisticasPresupuestosEstudios",
        "stat_types": {
            "pensiones": {
                "query": "pensiones numero pensionistas importe medio jubilacion vejez",
                "description": "Pension statistics — number of pensions, average amounts, by type",
            },
            "cotizantes": {
                "query": "afiliados cotizantes seguridad social trabajadores alta",
                "description": "Social security contributors — by regime, sector, province",
            },
            "ratio_sostenibilidad": {
                "query": "ratio cotizantes pensionistas sostenibilidad sistema pensiones",
                "description": "Contributor-to-pensioner ratio — system sustainability indicator",
            },
            "prestaciones_desempleo": {
                "query": "prestaciones desempleo paro contributivo subsidio",
                "description": "Unemployment benefits — contributory and assistance level",
            },
            "incapacidad": {
                "query": "incapacidad temporal permanente bajas laborales IT",
                "description": "Sick leave and disability — temporary and permanent incapacity",
            },
            "accidentes_laborales": {
                "query": "accidentes laborales trabajo lesiones enfermedades profesionales",
                "description": "Occupational accidents and work-related diseases",
            },
            "inmigracion": {
                "query": "extranjeros afiliados inmigrantes seguridad social cotizantes",
                "description": "Foreign national contributors to the social security system",
            },
        },
        "default_stat_type": "pensiones",
    },
    # ------------------------------------------------------------------
    "justicia": {
        "name": "Ministerio de Justicia / Consejo General del Poder Judicial (CGPJ)",
        "publishers": [
            "ministerio-de-justicia",
            "consejo-general-del-poder-judicial",
        ],
        "portal_url": "https://www.poderjudicial.es/cgpj/es/Temas/Estadistica-Judicial/",
        "stat_types": {
            "criminalidad": {
                "query": "estadisticas criminalidad delitos infracciones penales",
                "description": "Crime statistics — offences by type, province and year",
            },
            "condenas": {
                "query": "condenas sentencias penales condenados penas privativas libertad",
                "description": "Criminal convictions — sentences, types of punishment, recidivism",
            },
            "presos": {
                "query": "presos reclusos poblacion penitenciaria establecimientos",
                "description": "Prison population — inmates by regime, sex, nationality",
            },
            "juzgados": {
                "query": "juzgados tribunales asuntos registrados resueltos pendientes",
                "description": "Court workload — cases filed, resolved and pending by court type",
            },
            "violencia_genero": {
                "query": "violencia genero victimas denuncias femicidio maltrato",
                "description": "Gender-based violence — complaints, convictions, femicides",
            },
            "menores": {
                "query": "menores infractores justicia juvenil responsabilidad penal",
                "description": "Juvenile justice — offences and sentences for minors",
            },
            "corrupcion": {
                "query": "corrupcion delitos economicos malversacion prevaricacion",
                "description": "Economic crime and corruption — charges, trials, convictions",
            },
        },
        "default_stat_type": "criminalidad",
    },
}


def format_results(result: dict, header: str) -> str:
    """
    Shared formatter for ministerio tool results.

    Returns a text block listing datasets found, with explicit next-step
    instructions for retrieving actual data values via list_dataset_resources.
    """
    info = result.get("ministerio_info", {})
    datasets = result.get("results", [])
    count = result.get("count", 0)
    page = result.get("page", 1)
    stat_desc = result.get("stat_description", "")

    lines = [
        header,
        f"Portal: {info.get('portal_url', '')}",
    ]
    if stat_desc:
        lines.append(f"Topic: {stat_desc}")
    lines.append(
        "\nIMPORTANT: This tool returns dataset references, NOT data values.\n"
        "To retrieve actual numbers, call:\n"
        "  list_dataset_resources(dataset_id='<id from result>', include_data=True)\n"
    )
    lines.append(f"Found {count} dataset(s) (page {page}, showing {len(datasets)}):\n")

    for i, ds in enumerate(datasets, 1):
        ds_id = ds.get("id", "")
        lines.append(f"{i}. {ds.get('title', 'Untitled')}")
        if ds.get("organization"):
            lines.append(f"   Publisher: {ds['organization']}")
        if ds.get("description"):
            lines.append(f"   Description: {ds['description'][:200]}...")
        if ds.get("last_modified"):
            lines.append(f"   Last updated: {ds['last_modified'][:10]}")
        lines.append(f"   Formats: {', '.join(ds.get('formats', [])) or 'unknown'}")
        lines.append(f"   Resources: {ds.get('resources_count', 0)} file(s)")
        for r in (ds.get("resources") or [])[:3]:
            fmt = r.get("format") or "?"
            name = r.get("name") or "File"
            url = r.get("url") or ""
            if url:
                lines.append(f"   [{fmt}] {name}: {url}")
        if ds_id:
            lines.append(f"   dataset_id: {ds_id}")
            lines.append(
                f"   → list_dataset_resources(dataset_id='{ds_id}', include_data=True)"
            )
        else:
            lines.append(f"   URL: {ds.get('url', '')}")
        lines.append("")

    if not datasets:
        lines.append("No datasets found. Try a broader stat_type or use custom_query.")

    return "\n".join(lines)


def list_ministerios() -> list[str]:
    """Return all supported ministerio keys."""
    return list(_MINISTERIOS)


def get_ministerio_info(ministerio: str) -> dict[str, Any]:
    """Return config dict for the given ministerio key."""
    return _MINISTERIOS.get(ministerio, {})


def list_stat_types(ministerio: str) -> list[str]:
    """Return available stat_type values for a ministerio."""
    cfg = _MINISTERIOS.get(ministerio, {})
    return list(cfg.get("stat_types", {}).keys())


async def search_ministerio_stats(
    ministerio: str,
    stat_type: str | None = None,
    custom_query: str | None = None,
    period: str | None = None,
    page: int = 1,
    page_size: int = 10,
    session: httpx.AsyncClient | None = None,
) -> dict[str, Any]:
    """
    Search datos.gob.es for statistical datasets from a Spanish ministry.

    Uses the datos.gob.es semantic API title/{keyword} endpoint.

    Args:
        ministerio: Registry key (e.g. "sanidad", "educacion", "vivienda",
                    "trafico", "seguridad_social", "justicia").
        stat_type: Topic within the ministry (see _MINISTERIOS[...]["stat_types"]).
                   Defaults to the ministerio's default_stat_type.
        custom_query: Override the curated query with a free-text search.
        period: Optional year or range to append to the query (e.g. "2023", "2020-2023").
        page: Page number (1-based).
        page_size: Results per page (max 100).

    Returns:
        dict with "results" (list of normalized datasets), "count", "page", "page_size",
        "ministerio_info" (name + portal URL), and "stat_description".
    """
    if ministerio not in _MINISTERIOS:
        raise ValueError(
            f"Unknown ministerio '{ministerio}'. "
            f"Valid values: {', '.join(_MINISTERIOS)}"
        )

    cfg = _MINISTERIOS[ministerio]
    stat_types: dict[str, dict] = cfg.get("stat_types", {})

    # Resolve stat_type
    effective_stat = stat_type or cfg.get("default_stat_type", "")
    stat_cfg = stat_types.get(effective_stat, {})
    stat_description = stat_cfg.get("description", "")

    # Build query — use the curated query string (first meaningful keyword for title search)
    if custom_query:
        query = custom_query
    else:
        query = stat_cfg.get("query", effective_stat)

    if period:
        query = f"{query} {period}"

    own = session is None
    if own:
        session = httpx.AsyncClient(headers={"User-Agent": USER_AGENT})
    assert session is not None

    try:
        raw = await datos_gob_es_client.search_datasets(
            query=query,
            page=page,
            page_size=min(page_size, 100),
            session=session,
        )
        normalized = raw.get("results", [])
        count = raw.get("count", len(normalized))

        return {
            "results": normalized,
            "count": count,
            "page": page,
            "page_size": len(normalized),
            "ministerio_info": {
                "name": cfg["name"],
                "portal_url": cfg["portal_url"],
            },
            "stat_description": stat_description,
            "effective_query": query,
        }

    finally:
        if own:
            await session.aclose()
