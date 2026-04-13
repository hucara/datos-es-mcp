from mcp.server.fastmcp import FastMCP

from helpers import aemet_client
from helpers.logging import log_tool


def register_get_weather_observations_tool(mcp: FastMCP) -> None:
    @mcp.tool()
    @log_tool
    async def get_weather_observations(
        station_id: str | None = None,
    ) -> str:
        """
        Get current meteorological observations from AEMET weather stations in Spain.

        Requires the AEMET_API_KEY environment variable (free from opendata.aemet.es).

        Args:
            station_id: AEMET station ID for a specific station (e.g. "3195" for
                        Madrid Retiro, "0076" for Barcelona airport, "5530" for Seville).
                        If omitted, returns a summary of all stations in Spain.

        Returns temperature, humidity, wind speed/direction, precipitation,
        atmospheric pressure, and visibility for each station.

        Common station IDs:
          3195  — Madrid Retiro
          0076  — Barcelona (El Prat airport)
          5530  — Seville (airport)
          1428  — Bilbao (airport)
          6155A — Málaga (airport)
          7031  — Palma de Mallorca
        """
        try:
            if station_id:
                observations = await aemet_client.get_station_observations(station_id)
            else:
                observations = await aemet_client.get_all_stations_observations()
        except ValueError as e:
            return str(e)
        except Exception as e:  # noqa: BLE001
            ctx = f"station {station_id}" if station_id else "all stations"
            return f"Error fetching AEMET observations for {ctx}: {e}"

        if not observations:
            ctx = f"station '{station_id}'" if station_id else "any station"
            return f"No current observations available for {ctx}."

        # Limit display for all-stations mode
        display = observations if station_id else observations[:30]

        content_parts = [
            f"AEMET Current Observations — "
            + (f"Station {station_id}" if station_id else f"{len(observations)} stations"),
            "",
        ]

        for obs in display:
            station = obs.get("idema") or obs.get("estacion") or "?"
            name = obs.get("ubi") or obs.get("nombre") or station
            fecha = obs.get("fint") or obs.get("fecha") or "?"
            temp = obs.get("ta")           # air temperature °C
            temp_max = obs.get("tamax")
            temp_min = obs.get("tamin")
            humidity = obs.get("hr")       # relative humidity %
            wind_speed = obs.get("vv")     # wind speed m/s
            wind_dir = obs.get("dv")       # wind direction degrees
            precip = obs.get("prec")       # precipitation mm
            pressure = obs.get("pres")     # sea-level pressure hPa
            visibility = obs.get("vis")    # visibility km
            snow_depth = obs.get("nieve")

            content_parts.append(f"Station: {name} ({station})")
            if str(fecha)[:16]:
                content_parts.append(f"  Time: {str(fecha)[:16]}")
            if temp is not None:
                t_line = f"  Temperature: {temp}°C"
                if temp_max is not None:
                    t_line += f" (max {temp_max}°C"
                    if temp_min is not None:
                        t_line += f", min {temp_min}°C"
                    t_line += ")"
                content_parts.append(t_line)
            if humidity is not None:
                content_parts.append(f"  Humidity: {humidity}%")
            if wind_speed is not None:
                w_line = f"  Wind: {wind_speed} m/s"
                if wind_dir is not None:
                    w_line += f" from {wind_dir}°"
                content_parts.append(w_line)
            if precip is not None and str(precip) not in ("0", "0.0", "Ip"):
                content_parts.append(f"  Precipitation: {precip} mm")
            if pressure is not None:
                content_parts.append(f"  Pressure: {pressure} hPa")
            if visibility is not None:
                content_parts.append(f"  Visibility: {visibility} km")
            if snow_depth is not None and str(snow_depth) != "0":
                content_parts.append(f"  Snow depth: {snow_depth} cm")
            content_parts.append("")

        if not station_id and len(observations) > 30:
            content_parts.append(
                f"... showing 30 of {len(observations)} stations. "
                "Use station_id= to query a specific station."
            )

        content_parts.append("Data source: AEMET OpenData (opendata.aemet.es)")
        return "\n".join(content_parts)
