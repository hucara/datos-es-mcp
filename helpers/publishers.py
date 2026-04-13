"""
Known publisher IDs for datos.gob.es.

Maps common institution names and aliases to their CKAN organization slugs
on datos.gob.es. Pass these slugs as the `publisher` parameter to
`search_datasets` to restrict results to a specific institution.

Usage:
    from helpers.publishers import KNOWN_PUBLISHERS, find_publisher

    slug = find_publisher("ine")
    # → "instituto-nacional-de-estadistica"

    slug = find_publisher("Ministerio de Sanidad")
    # → "ministerio-de-sanidad"

    slug = find_publisher("unknown org")
    # → None
"""

# alias (lowercase) → datos.gob.es CKAN organization slug
KNOWN_PUBLISHERS: dict[str, str] = {
    # ---- National statistics ----
    "ine": "instituto-nacional-de-estadistica",
    "instituto nacional de estadistica": "instituto-nacional-de-estadistica",
    # ---- Meteorology ----
    "aemet": "agencia-estatal-de-meteorologia-aemet",
    "agencia estatal de meteorologia": "agencia-estatal-de-meteorologia-aemet",
    # ---- Finance & Treasury ----
    "hacienda": "ministerio-de-hacienda-y-funcion-publica",
    "ministerio de hacienda": "ministerio-de-hacienda-y-funcion-publica",
    "minhap": "ministerio-de-hacienda-y-funcion-publica",
    "agencia tributaria": "agencia-estatal-de-administracion-tributaria-aeat",
    "aeat": "agencia-estatal-de-administracion-tributaria-aeat",
    "banco de espana": "banco-de-espana",
    "bde": "banco-de-espana",
    # ---- Employment & Social ----
    "sepe": "servicio-publico-de-empleo-estatal-sepe",
    "ministerio de trabajo": "ministerio-de-trabajo-y-economia-social",
    "seguridad social": "ministerio-de-inclusion-seguridad-social-y-migraciones",
    # ---- Transport ----
    "renfe": "entidad-publica-empresarial-renfe-operadora",
    "dgt": "direccion-general-de-trafico",
    "mitma": "ministerio-de-transportes-movilidad-y-agenda-urbana",
    "ministerio de fomento": "ministerio-de-transportes-movilidad-y-agenda-urbana",
    "ministerio de transportes": "ministerio-de-transportes-movilidad-y-agenda-urbana",
    # ---- Energy & Environment ----
    "cnmc": "comision-nacional-de-los-mercados-y-la-competencia",
    "ree": "red-electrica-de-espana",
    "red electrica": "red-electrica-de-espana",
    "red electrica de espana": "red-electrica-de-espana",
    "miteco": "ministerio-para-la-transicion-ecologica",
    "ministerio de medio ambiente": "ministerio-para-la-transicion-ecologica",
    "ministerio de transicion ecologica": "ministerio-para-la-transicion-ecologica",
    # ---- Health ----
    "ministerio de sanidad": "ministerio-de-sanidad",
    "msssi": "ministerio-de-sanidad",
    "mscbs": "ministerio-de-sanidad",
    # ---- Education & Science ----
    "mefp": "ministerio-de-educacion-y-formacion-profesional",
    "ministerio de educacion": "ministerio-de-educacion-y-formacion-profesional",
    "ministerio de ciencia": "ministerio-de-ciencia-e-innovacion",
    # ---- Justice & Interior ----
    "ministerio del interior": "ministerio-del-interior",
    "ministerio de justicia": "ministerio-de-justicia",
    # ---- Defence & Foreign ----
    "ministerio de defensa": "ministerio-de-defensa",
    "ministerio de asuntos exteriores": "ministerio-de-asuntos-exteriores-union-europea-y-cooperacion",
    # ---- Agriculture ----
    "mapa": "ministerio-de-agricultura-pesca-y-alimentacion",
    "ministerio de agricultura": "ministerio-de-agricultura-pesca-y-alimentacion",
    # ---- Autonomous communities ----
    "junta de andalucia": "junta-de-andalucia",
    "generalitat de catalunya": "generalitat-de-catalunya",
    "comunidad de madrid": "comunidad-de-madrid",
    "generalitat valenciana": "generalitat-valenciana",
    "pais vasco": "gobierno-vasco",
    "gobierno vasco": "gobierno-vasco",
    "euskadi": "gobierno-vasco",
    "junta de castilla y leon": "junta-de-castilla-y-leon",
    "gobierno de aragon": "gobierno-de-aragon",
    "aragon": "gobierno-de-aragon",
    "junta de extremadura": "junta-de-extremadura",
    "gobierno de navarra": "gobierno-de-navarra",
    "navarra": "gobierno-de-navarra",
    "xunta de galicia": "xunta-de-galicia",
    "galicia": "xunta-de-galicia",
    "gobierno de canarias": "gobierno-de-canarias",
    "canarias": "gobierno-de-canarias",
    "gobierno de la rioja": "gobierno-de-la-rioja",
    "la rioja": "gobierno-de-la-rioja",
    "gobierno de cantabria": "gobierno-de-cantabria",
    "cantabria": "gobierno-de-cantabria",
    "region de murcia": "region-de-murcia",
    "murcia": "region-de-murcia",
    "illes balears": "govern-de-les-illes-balears",
    "govern balear": "govern-de-les-illes-balears",
    "gobierno de asturias": "gobierno-del-principado-de-asturias",
    "asturias": "gobierno-del-principado-de-asturias",
    "junta de castilla-la mancha": "junta-de-comunidades-de-castilla-la-mancha",
    "castilla la mancha": "junta-de-comunidades-de-castilla-la-mancha",
    # ---- Major cities ----
    "ayuntamiento de madrid": "ayuntamiento-de-madrid",
    "ajuntament de barcelona": "ajuntament-de-barcelona",
    "ayuntamiento de barcelona": "ajuntament-de-barcelona",
    "ayuntamiento de sevilla": "ayuntamiento-de-sevilla",
    "ayuntamiento de zaragoza": "ayuntamiento-de-zaragoza",
    "ayuntamiento de valencia": "ajuntament-de-valencia",
    "ajuntament de valencia": "ajuntament-de-valencia",
    "ayuntamiento de malaga": "ayuntamiento-de-malaga",
    "ayuntamiento de bilbao": "ayuntamiento-de-bilbao",
}


def find_publisher(query: str) -> str | None:
    """
    Look up a datos.gob.es publisher slug by alias or partial name.

    Tries an exact case-insensitive match first, then falls back to a
    substring search over aliases and slugs.

    Args:
        query: Institution name or alias (e.g. "INE", "hacienda", "Renfe").

    Returns:
        CKAN organization slug string, or None if no match found.
    """
    q = query.strip().lower()
    if not q:
        return None

    # 1. Exact alias match
    if q in KNOWN_PUBLISHERS:
        return KNOWN_PUBLISHERS[q]

    # 2. Substring search over aliases and slugs
    for alias, slug in KNOWN_PUBLISHERS.items():
        if q in alias or q in slug:
            return slug

    return None
