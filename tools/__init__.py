from mcp.server.fastmcp import FastMCP

from tools.get_aeat_stats import register_get_aeat_stats_tool
from tools.get_bde_series import register_get_bde_series_tool
from tools.get_boe_summary import register_get_boe_summary_tool
from tools.get_cnmc_data import register_get_cnmc_data_tool
from tools.get_dataset_info import register_get_dataset_info_tool
from tools.get_education_stats import register_get_education_stats_tool
from tools.get_employment_stats import register_get_employment_stats_tool
from tools.get_energy_data import register_get_energy_data_tool
from tools.get_eurostat_data import register_get_eurostat_data_tool
from tools.get_health_stats import register_get_health_stats_tool
from tools.get_housing_stats import register_get_housing_stats_tool
from tools.get_ine_operations import register_get_ine_operations_tool
from tools.get_justice_stats import register_get_justice_stats_tool
from tools.get_renfe_data import register_get_renfe_data_tool
from tools.get_social_security_stats import register_get_social_security_stats_tool
from tools.get_traffic_stats import register_get_traffic_stats_tool
from tools.get_weather_forecast import register_get_weather_forecast_tool
from tools.get_weather_observations import register_get_weather_observations_tool
from tools.list_dataset_resources import register_list_dataset_resources_tool
from tools.query_ine_data import register_query_ine_data_tool
from tools.search_datasets import register_search_datasets_tool
from tools.search_legislation import register_search_legislation_tool
from tools.search_public_contracts import register_search_public_contracts_tool
from tools.search_regional_contracts import register_search_regional_contracts_tool
from tools.verify_claim import register_verify_claim_tool


def register_tools(mcp: FastMCP) -> None:
    """Register all MCP tools with the provided FastMCP instance."""
    # datos.gob.es — national open data catalog
    register_search_datasets_tool(mcp)
    register_get_dataset_info_tool(mcp)
    register_list_dataset_resources_tool(mcp)
    # INE — Instituto Nacional de Estadística
    register_get_ine_operations_tool(mcp)
    register_query_ine_data_tool(mcp)
    # Banco de España — financial and monetary statistics
    register_get_bde_series_tool(mcp)
    # AEMET — meteorological data
    register_get_weather_forecast_tool(mcp)
    register_get_weather_observations_tool(mcp)
    # BOE — official gazette and legislation
    register_get_boe_summary_tool(mcp)
    register_search_legislation_tool(mcp)
    # PLACE — national public procurement
    register_search_public_contracts_tool(mcp)
    # Regional procurement — Madrid, Cataluña, Valencia
    register_search_regional_contracts_tool(mcp)
    # SEPE — employment statistics
    register_get_employment_stats_tool(mcp)
    # Renfe — train data
    register_get_renfe_data_tool(mcp)
    # CNMC — energy and competition markets
    register_get_cnmc_data_tool(mcp)
    # REData / Red Eléctrica — electricity generation and prices
    register_get_energy_data_tool(mcp)
    # Eurostat — EU comparative statistics
    register_get_eurostat_data_tool(mcp)
    # AEAT — fiscal and tax statistics
    register_get_aeat_stats_tool(mcp)
    # Ministerio de Sanidad / SNS — public health statistics
    register_get_health_stats_tool(mcp)
    # Ministerio de Educación y FP — education statistics
    register_get_education_stats_tool(mcp)
    # Ministerio de Vivienda — housing market statistics
    register_get_housing_stats_tool(mcp)
    # DGT — road traffic and vehicle statistics
    register_get_traffic_stats_tool(mcp)
    # Seguridad Social / INSS — pension and contributor statistics
    register_get_social_security_stats_tool(mcp)
    # Ministerio de Justicia / CGPJ — criminal justice statistics
    register_get_justice_stats_tool(mcp)
    # Claim verification meta-tool
    register_verify_claim_tool(mcp)
