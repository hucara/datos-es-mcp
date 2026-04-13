"""
API base URL configuration for datos-es-mcp.

All APIs are public and require no authentication, except AEMET which requires
a free API key (AEMET_API_KEY environment variable).
"""

# Static base URLs — these APIs don't have staging/demo environments
API_URLS: dict[str, str] = {
    # datos.gob.es — national open data catalog (CKAN)
    "datos_gob_es": "https://datos.gob.es/",
    # INE — Instituto Nacional de Estadística
    "ine": "https://servicios.ine.es/wstempus/js/",
    # Banco de España — financial and monetary statistics
    "bde": "https://app.bde.es/bierest/resources/srdatosapp/",
    # AEMET OpenData — meteorological data (requires API key)
    "aemet": "https://opendata.aemet.es/opendata/api/",
    # BOE — Boletín Oficial del Estado (official gazette + legislation)
    "boe": "https://www.boe.es/datosabiertos/api/",
    # PLACE — Plataforma de Contratación del Sector Público (public procurement)
    "place": "https://contrataciondelestado.es/",
    # SEPE — Servicio Público de Empleo Estatal (employment statistics)
    "sepe": "https://sede.sepe.gob.es/",
    # Renfe open data portal (CKAN)
    "renfe": "https://data.renfe.com/",
    # CNMC — Comisión Nacional de los Mercados y la Competencia (CKAN)
    "cnmc": "https://data.cnmc.es/",
}


def get_api_url(api_name: str) -> str:
    """
    Get the base URL for a specific API.

    Args:
        api_name: One of the keys in API_URLS.

    Returns:
        The API base URL as a string.

    Raises:
        KeyError: If api_name is not a valid API name.
    """
    if api_name not in API_URLS:
        raise KeyError(
            f"Invalid api_name: '{api_name}'. "
            f"Valid values are: {', '.join(API_URLS.keys())}"
        )
    return API_URLS[api_name]
