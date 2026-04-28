from mcp.server.fastmcp import FastMCP

from helpers import aemet_client
from helpers.http import source_footer, url_capture
from helpers.logging import log_tool

_SKY_STATES = {
    "11": "Clear",
    "12": "Slightly cloudy",
    "13": "Partly cloudy",
    "14": "Cloudy",
    "15": "Very cloudy",
    "16": "Overcast",
    "17": "High clouds",
    "23": "Intervals of clouds and clear sky",
    "24": "Cloudy with intervals",
    "25": "Very cloudy with intervals",
    "26": "Overcast with intervals",
    "33": "Showers",
    "34": "Showers",
    "35": "Showers",
    "36": "Showers",
    "43": "Occasional rain",
    "44": "Occasional rain",
    "45": "Rain",
    "46": "Rain",
    "51": "Thunderstorms",
    "52": "Thunderstorms",
    "53": "Thunderstorms",
    "54": "Thunderstorms",
    "61": "Snow showers",
    "62": "Snow showers",
    "63": "Snow",
    "64": "Snow",
    "71": "Frost",
    "72": "Sleet",
    "73": "Hail",
    "74": "Hail",
    "81": "Fog",
    "82": "Fog",
    "83": "Mist",
}


def _sky_desc(code: str) -> str:
    c = str(code).replace("n", "").replace("p", "").strip()
    return _SKY_STATES.get(c, f"code {code}")


def register_get_weather_forecast_tool(mcp: FastMCP) -> None:
    @mcp.tool()
    @log_tool
    async def get_weather_forecast(
        municipio_code: str,
        detail: str = "daily",
    ) -> str:
        """
        Get weather forecast for a Spanish municipality from AEMET OpenData.

        Requires the AEMET_API_KEY environment variable (free from opendata.aemet.es).

        Args:
            municipio_code: INE 5-digit municipality code (with leading zeros).
                            Examples: "28079" (Madrid), "08019" (Barcelona),
                            "41091" (Seville), "46250" (Valencia), "03065" (Alicante).
            detail: "daily" (default, next 7 days) or "hourly" (next 48 hours).

        Returns weather including temperature, precipitation probability,
        wind speed/direction, humidity, and sky conditions.
        """
        _urls: list[str] = []
        url_capture.set(_urls)
        try:
            if detail == "hourly":
                data = await aemet_client.get_municipio_forecast_hourly(municipio_code)
            else:
                data = await aemet_client.get_municipio_forecast_daily(municipio_code)
        except ValueError as e:
            return str(e)
        except Exception as e:  # noqa: BLE001
            return f"Error fetching forecast for municipality {municipio_code}: {e}"

        if not data:
            return (
                f"No forecast data found for municipality code '{municipio_code}'. "
                "Check the INE 5-digit code (e.g. '28079' for Madrid)."
            )

        forecast = data[0]
        name = forecast.get("nombre") or municipio_code
        province = forecast.get("provincia") or ""
        elaborado = forecast.get("elaborado") or ""
        prediccion = forecast.get("prediccion") or {}

        content_parts = [
            f"AEMET Weather Forecast — {name}" + (f", {province}" if province else ""),
        ]
        if elaborado:
            content_parts.append(f"Prepared: {str(elaborado)[:16]}")
        content_parts.append("")

        if detail == "hourly":
            horas = prediccion.get("hora") or []
            if not horas:
                return "\n".join(content_parts) + "No hourly data available."

            content_parts.append(f"Hourly forecast ({len(horas)} periods):\n")
            for h in horas[:24]:
                fecha = h.get("fecha") or "?"
                hora_val = h.get("hora") or "?"
                temp = h.get("temperatura")
                precip = h.get("precipitacion")
                viento = h.get("vientoAndRachaMax") or [{}]
                sky = h.get("estadoCielo") or [{}]

                line = f"  {fecha} {hora_val}h:"
                if temp is not None:
                    line += f" {temp}°C"
                if precip is not None and str(precip) != "0":
                    line += f", {precip}mm precip"
                if sky and isinstance(sky, list) and sky[0].get("value"):
                    line += f", {_sky_desc(sky[0]['value'])}"
                if viento and isinstance(viento, list):
                    v = viento[0]
                    spd = v.get("velocidad")
                    if spd:
                        line += f", wind {spd}km/h"
                content_parts.append(line)
        else:
            dias = prediccion.get("dia") or []
            if not dias:
                return "\n".join(content_parts) + "No daily data available."

            content_parts.append(f"Daily forecast ({len(dias)} days):\n")
            for day in dias:
                fecha = day.get("fecha") or "?"
                tmax = (day.get("temperatura") or {}).get("maxima")
                tmin = (day.get("temperatura") or {}).get("minima")
                tmed = (day.get("temperatura") or {}).get("media")
                precip_prob = day.get("probPrecipitacion") or []
                sky_list = day.get("estadoCielo") or []
                wind = day.get("viento") or []
                humidity = day.get("humedadRelativa") or {}

                content_parts.append(f"  {str(fecha)[:10]}:")

                if tmax is not None or tmin is not None:
                    temp_str = ""
                    if tmax is not None:
                        temp_str += f"max {tmax}°C"
                    if tmin is not None:
                        temp_str += f", min {tmin}°C" if temp_str else f"min {tmin}°C"
                    if tmed is not None:
                        temp_str += f", avg {tmed}°C"
                    content_parts.append(f"    Temperature: {temp_str}")

                # Sky state (first interval of day)
                if sky_list and isinstance(sky_list, list):
                    sky_val = (
                        sky_list[0].get("value")
                        if isinstance(sky_list[0], dict)
                        else sky_list[0]
                    )
                    if sky_val:
                        content_parts.append(f"    Sky: {_sky_desc(str(sky_val))}")

                # Precipitation probability
                if precip_prob and isinstance(precip_prob, list):
                    max_prob = max(
                        (int(p.get("value", 0)) if isinstance(p, dict) else 0)
                        for p in precip_prob
                        if p
                    )
                    if max_prob:
                        content_parts.append(
                            f"    Precipitation probability: {max_prob}%"
                        )

                # Wind
                if wind and isinstance(wind, list) and wind[0]:
                    w = wind[0] if isinstance(wind[0], dict) else {}
                    direction = w.get("direccion")
                    speed = w.get("velocidad")
                    if direction or speed:
                        wind_str = ""
                        if direction:
                            wind_str += f"{direction}"
                        if speed:
                            wind_str += f" {speed}km/h"
                        content_parts.append(f"    Wind: {wind_str.strip()}")

                # Humidity
                hmax = humidity.get("maxima")
                hmin = humidity.get("minima")
                if hmax or hmin:
                    content_parts.append(f"    Humidity: {hmin}%–{hmax}%")

        content_parts.append("")
        content_parts.append("Data source: AEMET OpenData (opendata.aemet.es)")
        content_parts.append(source_footer(_urls))
        return "\n".join(content_parts)
