import json
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
import streamlit as st


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
METNO_FORECAST_URL = "https://api.met.no/weatherapi/locationforecast/2.0/compact"
STATE_FILE = Path("last_weather_state.json")
OPEN_METEO_TIMEOUT_SECONDS = 4
METNO_TIMEOUT_SECONDS = 5
METNO_FALLBACK_HORIZON_DAYS = 9
METNO_REQUEST_HEADERS = {
    "User-Agent": "SkylineForecast/1.0 (local app fallback)",
}
PROVIDER_STATE = {"prefer_metno_until": None}
PROVIDER_DEGRADE_WINDOW = timedelta(minutes=20)
DAILY_EXPORT_FIELDS = [
    "weather_code",
    "temperature_2m_min",
    "temperature_2m_max",
    "precipitation_probability_max",
    "precipitation_sum",
    "sunrise",
    "sunset",
    "uv_index_max",
    "wind_speed_10m_max",
    "wind_gusts_10m_max",
]

CONDITION_MAP = {
    0: "Sunny",
    1: "Cloudy",
    2: "Cloudy",
    3: "Cloudy",
    45: "Foggy",
    48: "Foggy",
    51: "Rainy",
    53: "Rainy",
    55: "Rainy",
    56: "Rainy",
    57: "Rainy",
    61: "Rainy",
    63: "Rainy",
    65: "Rainy",
    66: "Rainy",
    67: "Rainy",
    71: "Snowy",
    73: "Snowy",
    75: "Snowy",
    77: "Snowy",
    80: "Rainy",
    81: "Rainy",
    82: "Rainy",
    85: "Snowy",
    86: "Snowy",
    95: "Thunderstorm",
    96: "Thunderstorm",
    99: "Thunderstorm",
}


class WeatherError(Exception):
    """Base error for weather-related failures."""


class CityNotFoundError(WeatherError):
    """Raised when the city search returns no results."""


class ForecastDataError(WeatherError):
    """Raised when the weather service returns incomplete forecast data."""


def weather_code_to_condition(weather_code):
    return CONDITION_MAP.get(weather_code, "Cloudy")


def format_day(date_str):
    return datetime.strptime(date_str, "%Y-%m-%d").strftime("%a")


def format_time(date_str):
    return datetime.fromisoformat(date_str).strftime("%I:%M %p").lstrip("0")


def _parse_iso_datetime(value):
    if not value:
        return None

    normalized_value = str(value).strip()
    if normalized_value.endswith("Z"):
        normalized_value = normalized_value[:-1] + "+00:00"

    try:
        return datetime.fromisoformat(normalized_value)
    except ValueError:
        return None


def _get_timezone_info(timezone_name):
    if not timezone_name:
        return None

    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return None


def _meters_per_second_to_kmh(value):
    try:
        return float(value) * 3.6
    except (TypeError, ValueError):
        return 0.0


def _fetch_geocoding_results(query, count=1, timeout_seconds=OPEN_METEO_TIMEOUT_SECONDS):
    response = requests.get(
        GEOCODING_URL,
        params={
            "name": str(query or "").strip(),
            "count": count,
            "language": "en",
            "format": "json",
        },
        timeout=timeout_seconds,
    )
    response.raise_for_status()
    return response.json().get("results", []) or []


def _enrich_location_metadata(location, city_query):
    if not isinstance(location, dict) or not city_query:
        return location

    if location.get("timezone") and location.get("country") and location.get("name"):
        return location

    candidate_queries = []
    for candidate in [
        city_query,
        location.get("name"),
        ", ".join(part.strip() for part in str(city_query).split(",")[:2] if part.strip()),
        str(city_query).split(",")[0].strip(),
    ]:
        normalized_candidate = str(candidate or "").strip()
        if normalized_candidate and normalized_candidate not in candidate_queries:
            candidate_queries.append(normalized_candidate)

    enriched = None
    for candidate_query in candidate_queries:
        try:
            results = _fetch_geocoding_results(candidate_query, count=1)
        except requests.RequestException:
            continue
        if results:
            enriched = results[0]
            break

    if not enriched:
        return location

    merged = dict(location)
    for key in ["name", "admin1", "country", "timezone"]:
        if merged.get(key) is None and enriched.get(key) is not None:
            merged[key] = enriched[key]
    return merged


def _fetch_open_meteo_forecast(location):
    hourly_fields = [
        "temperature_2m",
        "precipitation_probability",
        "precipitation",
        "weather_code",
        "is_day",
        "relative_humidity_2m",
        "wind_speed_10m",
        "cloud_cover",
    ]
    forecast_response = requests.get(
        FORECAST_URL,
        params={
            "latitude": location["latitude"],
            "longitude": location["longitude"],
            "current": ",".join(
                [
                    "temperature_2m",
                    "relative_humidity_2m",
                    "apparent_temperature",
                    "weather_code",
                    "wind_speed_10m",
                    "pressure_msl",
                    "visibility",
                    "precipitation",
                    "cloud_cover",
                ]
            ),
            "daily": ",".join(DAILY_EXPORT_FIELDS),
            "hourly": ",".join(hourly_fields),
            "timezone": "auto",
            "forecast_days": 10,
        },
        timeout=OPEN_METEO_TIMEOUT_SECONDS,
    )
    forecast_response.raise_for_status()
    return forecast_response.json()


def _resolve_location(city_name):
    location = None
    city_query = city_name

    if isinstance(city_name, dict):
        city_query = city_name.get("query") or city_name.get("label") or ""
        if city_name.get("latitude") is not None and city_name.get("longitude") is not None:
            location = city_name

    try:
        if location is None:
            results = _fetch_geocoding_results(city_query, count=1)
            if not results:
                raise CityNotFoundError("City not found.")
            location = results[0]
        else:
            location = _enrich_location_metadata(location, city_query)
    except requests.RequestException as exc:
        raise WeatherError("Unable to connect to the weather service right now.") from exc

    return location, city_query


def _should_prefer_metno():
    prefer_until = PROVIDER_STATE.get("prefer_metno_until")
    if not prefer_until:
        return False
    if datetime.now(timezone.utc) >= prefer_until:
        PROVIDER_STATE["prefer_metno_until"] = None
        return False
    return True


def _mark_open_meteo_degraded():
    PROVIDER_STATE["prefer_metno_until"] = datetime.now(timezone.utc) + PROVIDER_DEGRADE_WINDOW


def _clear_open_meteo_degraded():
    PROVIDER_STATE["prefer_metno_until"] = None

def build_local_time_payload(timezone_name, observed_at=None):
    local_now = None

    if timezone_name:
        try:
            local_now = datetime.now(ZoneInfo(timezone_name))
        except ZoneInfoNotFoundError:
            local_now = None

    if local_now is None and observed_at:
        try:
            local_now = datetime.fromisoformat(observed_at)
        except ValueError:
            local_now = None

    if local_now is None:
        local_now = datetime.now()

    return {
        "timezone": timezone_name or "",
        "timezone_abbr": local_now.strftime("%Z") or "",
        "local_time": local_now.strftime("%I:%M %p").lstrip("0"),
        "local_date": local_now.strftime("%a, %b %d"),
        "local_datetime_iso": local_now.isoformat(timespec="seconds"),
        "observed_at": observed_at or "",
    }


def _safe_daily_value(values, index, default):
    if index < len(values):
        value = values[index]
        if value is not None:
            return value
    return default


def _build_daily_forecast_rows(daily):
    times = daily.get("time") or []
    min_values = daily.get("temperature_2m_min") or []
    max_values = daily.get("temperature_2m_max") or []
    codes = daily.get("weather_code") or []
    rain_chances = daily.get("precipitation_probability_max") or []
    rain_totals = daily.get("precipitation_sum") or []
    uv_indexes = daily.get("uv_index_max") or []
    wind_speeds = daily.get("wind_speed_10m_max") or []
    wind_gusts = daily.get("wind_gusts_10m_max") or []
    sunrise_times = daily.get("sunrise") or []
    sunset_times = daily.get("sunset") or []

    forecast = []
    for index, day_key in enumerate(times):
        forecast.append(
            {
                "date": day_key,
                "day": format_day(day_key),
                "min": round(_safe_daily_value(min_values, index, 0), 1),
                "max": round(_safe_daily_value(max_values, index, 0), 1),
                "condition": weather_code_to_condition(_safe_daily_value(codes, index, 1)),
                "rain_chance": int(round(_safe_daily_value(rain_chances, index, 0))),
                "rain_total": round(_safe_daily_value(rain_totals, index, 0), 1),
                "uv_index": round(_safe_daily_value(uv_indexes, index, 0), 1),
                "wind_speed": round(_safe_daily_value(wind_speeds, index, 0), 1),
                "wind_gust": round(_safe_daily_value(wind_gusts, index, 0), 1),
                "sunrise": format_time(_safe_daily_value(sunrise_times, index, "1970-01-01T06:00")) if sunrise_times else "--",
                "sunset": format_time(_safe_daily_value(sunset_times, index, "1970-01-01T18:00")) if sunset_times else "--",
                "hourly": [],
            }
        )
    return forecast


def build_location_label(location, fallback=""):
    city_parts = []
    for part in [location.get("name"), location.get("admin1"), location.get("country")]:
        if not part:
            continue
        if part in city_parts:
            continue
        city_parts.append(part)

    return ", ".join(part for part in city_parts if part) or fallback


def _build_open_meteo_weather_payload(location, city_query, forecast_data):
    current = forecast_data.get("current") or {}
    daily = forecast_data.get("daily") or {}
    hourly = forecast_data.get("hourly") or {}

    required_current_keys = [
        "temperature_2m",
        "relative_humidity_2m",
        "apparent_temperature",
        "weather_code",
        "wind_speed_10m",
    ]
    if any(current.get(key) is None for key in required_current_keys):
        raise WeatherError("Current weather data is incomplete.")

    hourly_times = hourly.get("time") or []
    hourly_temperatures = hourly.get("temperature_2m") or []
    hourly_rain_chances = hourly.get("precipitation_probability") or []
    hourly_rain_totals = hourly.get("precipitation") or []
    hourly_codes = hourly.get("weather_code") or []
    hourly_is_day = hourly.get("is_day") or [None] * len(hourly_times)
    hourly_humidity = hourly.get("relative_humidity_2m") or []
    hourly_wind = hourly.get("wind_speed_10m") or []
    hourly_cloud_cover = hourly.get("cloud_cover") or []

    hourly_points = []
    hourly_length = min(
        len(hourly_times),
        len(hourly_temperatures),
        len(hourly_rain_chances),
        len(hourly_rain_totals),
        len(hourly_codes),
        len(hourly_is_day),
        len(hourly_humidity),
        len(hourly_wind),
        len(hourly_cloud_cover),
    )
    for index in range(hourly_length):
        iso_time = hourly_times[index]
        day_key = iso_time.split("T", maxsplit=1)[0]
        hourly_points.append(
            {
                "date": day_key,
                "time_iso": iso_time,
                "time": format_time(iso_time),
                "temperature": round(hourly_temperatures[index], 1),
                "rain_chance": int(round(hourly_rain_chances[index] or 0)),
                "rain_total": round(hourly_rain_totals[index] or 0, 1),
                "condition": weather_code_to_condition(hourly_codes[index]),
                "is_day": bool(hourly_is_day[index]) if hourly_is_day[index] is not None else True,
                "humidity": int(round(hourly_humidity[index] or 0)),
                "wind": round(hourly_wind[index] or 0, 1),
                "cloud_cover": int(round(hourly_cloud_cover[index] or 0)),
            }
        )

    forecast = _build_daily_forecast_rows(daily)
    if not forecast:
        raise ForecastDataError("Forecast data is unavailable for this city.")

    for index, day in enumerate(forecast):
        day_key = day["date"]
        forecast[index]["hourly"] = [point for point in hourly_points if point["date"] == day_key]

    return {
        "resolved_city": build_location_label(location, fallback=str(city_query).title()),
        "location": {
            "latitude": round(location["latitude"], 4),
            "longitude": round(location["longitude"], 4),
            "timezone": forecast_data.get("timezone") or location.get("timezone"),
            "country": location.get("country"),
            "admin1": location.get("admin1"),
        },
        "time": build_local_time_payload(
            forecast_data.get("timezone") or location.get("timezone"),
            current.get("time"),
        ),
        "current": {
            "temperature": round(current["temperature_2m"], 1),
            "humidity": int(round(current["relative_humidity_2m"])),
            "feels_like": round(current["apparent_temperature"], 1),
            "wind": round(current["wind_speed_10m"], 1),
            "condition": weather_code_to_condition(current["weather_code"]),
            "pressure": int(round(current.get("pressure_msl", 0))),
            "visibility": round((current.get("visibility", 0) or 0) / 1000, 1),
            "precipitation": round(current.get("precipitation", 0) or 0, 1),
            "cloud_cover": int(round(current.get("cloud_cover", 0) or 0)),
        },
        "forecast": forecast,
    }


def _get_metno_period_details(data):
    for key in ["next_1_hours", "next_6_hours", "next_12_hours"]:
        period = data.get(key) or {}
        summary = period.get("summary") or {}
        details = period.get("details") or {}
        if summary.get("symbol_code") or details.get("precipitation_amount") is not None:
            return key, summary.get("symbol_code") or "", details
    return "", "", {}


def _metno_symbol_is_day(symbol_code, point_dt=None):
    normalized_symbol = str(symbol_code or "").lower()
    if normalized_symbol.endswith("_night"):
        return False
    if normalized_symbol.endswith("_day"):
        return True
    if normalized_symbol.endswith("_polartwilight"):
        return False
    if point_dt is None:
        return True
    return 6 <= point_dt.hour < 18


def _metno_symbol_to_condition(symbol_code, cloud_cover=0, precipitation_amount=0):
    normalized_symbol = str(symbol_code or "").lower()
    precipitation_amount = float(precipitation_amount or 0)
    cloud_cover = float(cloud_cover or 0)

    if "thunder" in normalized_symbol:
        return "Thunderstorm"
    if "fog" in normalized_symbol:
        return "Foggy"
    if "snow" in normalized_symbol or "sleet" in normalized_symbol:
        return "Snowy"
    if (
        "rain" in normalized_symbol
        or "showers" in normalized_symbol
        or "drizzle" in normalized_symbol
        or precipitation_amount >= 0.2
    ):
        return "Rainy"
    if "cloud" in normalized_symbol or "fair" in normalized_symbol or cloud_cover >= 35:
        return "Cloudy"
    return "Sunny"


def _estimate_precipitation_probability(symbol_code, precipitation_amount, cloud_cover):
    normalized_symbol = str(symbol_code or "").lower()
    precipitation_amount = float(precipitation_amount or 0)
    cloud_cover = float(cloud_cover or 0)

    if "thunder" in normalized_symbol:
        return 95
    if "snow" in normalized_symbol or "sleet" in normalized_symbol:
        if precipitation_amount >= 2:
            return 90
        if precipitation_amount >= 0.5:
            return 78
        return 56
    if "rain" in normalized_symbol or "showers" in normalized_symbol or "drizzle" in normalized_symbol:
        if precipitation_amount >= 4:
            return 95
        if precipitation_amount >= 1:
            return 84
        if precipitation_amount >= 0.2:
            return 66
        return 48
    if precipitation_amount >= 1:
        return 70
    if precipitation_amount > 0:
        return 42
    if cloud_cover >= 95:
        return 28
    if cloud_cover >= 80:
        return 18
    if cloud_cover >= 60:
        return 10
    return 4


def _estimate_visibility_km(condition, cloud_cover):
    if condition == "Foggy":
        return 1.2
    if condition == "Thunderstorm":
        return 4.0
    if condition == "Snowy":
        return 3.5
    if condition == "Rainy":
        return 7.0
    if cloud_cover >= 90:
        return 10.0
    if cloud_cover >= 65:
        return 12.0
    return 16.0


def _estimate_apparent_temperature(temp_c, humidity_pct, wind_kmh):
    temperature_c = float(temp_c or 0)
    humidity_pct = float(humidity_pct or 0)
    wind_kmh = float(wind_kmh or 0)

    if temperature_c <= 10 and wind_kmh > 4.8:
        temperature_f = (temperature_c * 9 / 5) + 32
        wind_mph = max(wind_kmh * 0.621371, 0.1)
        wind_chill_f = (
            35.74
            + (0.6215 * temperature_f)
            - (35.75 * (wind_mph ** 0.16))
            + (0.4275 * temperature_f * (wind_mph ** 0.16))
        )
        return round(min(temperature_c, (wind_chill_f - 32) * 5 / 9), 1)

    if temperature_c >= 27 and humidity_pct >= 40:
        temperature_f = (temperature_c * 9 / 5) + 32
        heat_index_f = (
            -42.379
            + (2.04901523 * temperature_f)
            + (10.14333127 * humidity_pct)
            - (0.22475541 * temperature_f * humidity_pct)
            - (0.00683783 * (temperature_f ** 2))
            - (0.05481717 * (humidity_pct ** 2))
            + (0.00122874 * (temperature_f ** 2) * humidity_pct)
            + (0.00085282 * temperature_f * (humidity_pct ** 2))
            - (0.00000199 * (temperature_f ** 2) * (humidity_pct ** 2))
        )
        return round(max(temperature_c, (heat_index_f - 32) * 5 / 9), 1)

    return round(temperature_c, 1)


def _calculate_solar_event(local_date, latitude, longitude, timezone_name, is_sunrise):
    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except (TypeError, ValueError):
        return None

    timezone_info = _get_timezone_info(timezone_name)
    if timezone_info is None:
        return None

    day_of_year = local_date.timetuple().tm_yday
    longitude_hour = longitude / 15
    base_hour = 6 if is_sunrise else 18
    time_fraction = day_of_year + ((base_hour - longitude_hour) / 24)
    mean_anomaly = (0.9856 * time_fraction) - 3.289
    true_longitude = mean_anomaly + (1.916 * math.sin(math.radians(mean_anomaly))) + (0.020 * math.sin(math.radians(2 * mean_anomaly))) + 282.634
    true_longitude %= 360

    right_ascension = math.degrees(math.atan(0.91764 * math.tan(math.radians(true_longitude))))
    right_ascension %= 360
    longitude_quadrant = math.floor(true_longitude / 90) * 90
    ascension_quadrant = math.floor(right_ascension / 90) * 90
    right_ascension = (right_ascension + (longitude_quadrant - ascension_quadrant)) / 15

    sin_declination = 0.39782 * math.sin(math.radians(true_longitude))
    cos_declination = math.cos(math.asin(sin_declination))
    zenith = 90.833
    cos_hour_angle = (
        math.cos(math.radians(zenith))
        - (sin_declination * math.sin(math.radians(latitude)))
    ) / (cos_declination * math.cos(math.radians(latitude)))

    if cos_hour_angle < -1 or cos_hour_angle > 1:
        return None

    if is_sunrise:
        hour_angle = 360 - math.degrees(math.acos(cos_hour_angle))
    else:
        hour_angle = math.degrees(math.acos(cos_hour_angle))
    hour_angle /= 15

    local_mean_time = hour_angle + right_ascension - (0.06571 * time_fraction) - 6.622
    universal_time_hours = (local_mean_time - longitude_hour) % 24
    hour_component = int(universal_time_hours)
    minute_float = (universal_time_hours - hour_component) * 60
    minute_component = int(minute_float)
    second_component = int(round((minute_float - minute_component) * 60))

    if second_component == 60:
        second_component = 0
        minute_component += 1
    if minute_component == 60:
        minute_component = 0
        hour_component = (hour_component + 1) % 24

    utc_dt = datetime(
        local_date.year,
        local_date.month,
        local_date.day,
        hour_component,
        minute_component,
        second_component,
        tzinfo=timezone.utc,
    )
    return utc_dt.astimezone(timezone_info)


def _estimate_uv_index_max(latitude, target_date, average_cloud_cover):
    try:
        latitude = float(latitude)
    except (TypeError, ValueError):
        latitude = 0.0

    day_of_year = target_date.timetuple().tm_yday
    declination = 23.44 * math.sin(math.radians((360 / 365) * (day_of_year - 81)))
    solar_altitude = max(0.0, 90 - abs(latitude - declination))
    clear_sky_uv = min(12.0, (solar_altitude / 90) * 12)
    cloud_factor = max(0.22, 1 - (float(average_cloud_cover or 0) / 100) * 0.7)
    return round(clear_sky_uv * cloud_factor, 1)


def _summarize_daily_condition(day_points):
    conditions = [point.get("condition") for point in day_points]
    if "Thunderstorm" in conditions:
        return "Thunderstorm"
    if "Snowy" in conditions:
        return "Snowy"
    if "Rainy" in conditions:
        return "Rainy"
    if "Foggy" in conditions:
        return "Foggy"

    cloudy_points = sum(1 for point in day_points if point.get("condition") == "Cloudy" or point.get("cloud_cover", 0) >= 45)
    if cloudy_points >= max(1, len(day_points) // 3):
        return "Cloudy"
    return "Sunny"


def _fetch_metno_timeseries(latitude, longitude):
    response = requests.get(
        METNO_FORECAST_URL,
        params={"lat": latitude, "lon": longitude},
        headers=METNO_REQUEST_HEADERS,
        timeout=METNO_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return (response.json() or {}).get("properties", {}).get("timeseries") or []


def _build_metno_weather_payload(location, city_query):
    timezone_name = location.get("timezone")
    timezone_info = _get_timezone_info(timezone_name)
    timeseries = _fetch_metno_timeseries(location["latitude"], location["longitude"])
    if not timeseries:
        raise ForecastDataError("Forecast data is unavailable for this city.")

    hourly_points = []
    for entry in timeseries:
        point_dt = _parse_iso_datetime(entry.get("time"))
        if point_dt is None:
            continue

        local_dt = point_dt.astimezone(timezone_info) if timezone_info and point_dt.tzinfo else point_dt
        data = entry.get("data") or {}
        instant_details = (data.get("instant") or {}).get("details") or {}
        period_key, symbol_code, period_details = _get_metno_period_details(data)

        temperature = instant_details.get("air_temperature")
        humidity = instant_details.get("relative_humidity")
        cloud_cover = instant_details.get("cloud_area_fraction")
        if temperature is None or humidity is None or cloud_cover is None:
            continue

        precipitation_amount = float(period_details.get("precipitation_amount") or 0)
        wind_kmh = _meters_per_second_to_kmh(instant_details.get("wind_speed"))
        condition = _metno_symbol_to_condition(symbol_code, cloud_cover, precipitation_amount)
        hourly_points.append(
            {
                "date": local_dt.date().isoformat(),
                "time_iso": local_dt.isoformat(timespec="seconds"),
                "time": local_dt.strftime("%I:%M %p").lstrip("0"),
                "temperature": round(float(temperature), 1),
                "rain_chance": _estimate_precipitation_probability(symbol_code, precipitation_amount, cloud_cover),
                "rain_total": round(precipitation_amount, 1),
                "condition": condition,
                "is_day": _metno_symbol_is_day(symbol_code, local_dt),
                "humidity": int(round(float(humidity))),
                "wind": round(wind_kmh, 1),
                "cloud_cover": int(round(float(cloud_cover))),
                "pressure": int(round(float(instant_details.get("air_pressure_at_sea_level") or 0))),
                "_period_key": period_key,
                "_symbol_code": symbol_code,
            }
        )

    if not hourly_points:
        raise ForecastDataError("Forecast data is unavailable for this city.")

    hourly_points.sort(key=lambda point: point["time_iso"])
    now_utc = datetime.now(timezone.utc)
    current_point = min(
        hourly_points,
        key=lambda point: abs(((_parse_iso_datetime(point.get("time_iso")) or now_utc) - now_utc).total_seconds()),
    )

    daily_groups = {}
    for point in hourly_points:
        daily_groups.setdefault(point["date"], []).append(point)

    forecast = []
    for day_key, day_points in list(daily_groups.items())[:10]:
        target_date = datetime.fromisoformat(day_key).date()
        average_cloud_cover = sum(point.get("cloud_cover", 0) for point in day_points) / len(day_points)
        sunrise_dt = _calculate_solar_event(target_date, location["latitude"], location["longitude"], timezone_name, True)
        sunset_dt = _calculate_solar_event(target_date, location["latitude"], location["longitude"], timezone_name, False)
        max_wind = max((point.get("wind", 0) for point in day_points), default=0)
        forecast.append(
            {
                "date": day_key,
                "day": format_day(day_key),
                "min": round(min(point["temperature"] for point in day_points), 1),
                "max": round(max(point["temperature"] for point in day_points), 1),
                "condition": _summarize_daily_condition(day_points),
                "rain_chance": max((point.get("rain_chance", 0) for point in day_points), default=0),
                "rain_total": round(sum(point.get("rain_total", 0) for point in day_points), 1),
                "uv_index": _estimate_uv_index_max(location["latitude"], target_date, average_cloud_cover),
                "wind_speed": round(max_wind, 1),
                "wind_gust": round(max_wind * 1.35, 1),
                "sunrise": sunrise_dt.strftime("%I:%M %p").lstrip("0") if sunrise_dt else "--",
                "sunset": sunset_dt.strftime("%I:%M %p").lstrip("0") if sunset_dt else "--",
                "hourly": day_points,
            }
        )

    if not forecast:
        raise ForecastDataError("Forecast data is unavailable for this city.")

    return {
        "resolved_city": build_location_label(location, fallback=str(city_query).title()),
        "location": {
            "latitude": round(location["latitude"], 4),
            "longitude": round(location["longitude"], 4),
            "timezone": timezone_name,
            "country": location.get("country"),
            "admin1": location.get("admin1"),
        },
        "time": build_local_time_payload(timezone_name, current_point.get("time_iso")),
        "current": {
            "temperature": current_point["temperature"],
            "humidity": current_point["humidity"],
            "feels_like": _estimate_apparent_temperature(
                current_point["temperature"],
                current_point["humidity"],
                current_point["wind"],
            ),
            "wind": current_point["wind"],
            "condition": current_point["condition"],
            "pressure": current_point.get("pressure", 0),
            "visibility": _estimate_visibility_km(current_point["condition"], current_point["cloud_cover"]),
            "precipitation": current_point.get("rain_total", 0),
            "cloud_cover": current_point.get("cloud_cover", 0),
        },
        "forecast": forecast,
    }


def _build_metno_daily_range(latitude, longitude, start_date, end_date, timezone_name=""):
    weather_payload = _build_metno_weather_payload(
        {
            "latitude": latitude,
            "longitude": longitude,
            "timezone": timezone_name if timezone_name != "auto" else "",
        },
        "",
    )
    return [
        day
        for day in weather_payload.get("forecast", [])
        if start_date <= datetime.fromisoformat(day["date"]).date() <= end_date
    ]


def save_last_weather_state(weather, city_key):
    payload = {
        "last_weather": weather,
        "last_city_display": weather.get("resolved_city"),
        "last_city_key": city_key,
    }
    STATE_FILE.write_text(json.dumps(payload), encoding="utf-8")


def load_last_weather_state():
    if not STATE_FILE.exists():
        return None

    try:
        return json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None


def clear_last_weather_state():
    if STATE_FILE.exists():
        STATE_FILE.unlink()


@st.cache_data(show_spinner=False, ttl=600)
def get_city_suggestions(query):
    if not query or len(query.strip()) < 2:
        return []

    normalized_query = query.strip().lower()

    try:
        results = _fetch_geocoding_results(query.strip(), count=12)
    except requests.RequestException:
        return []

    ranked_results = sorted(
        results,
        key=lambda result: (
            0 if (result.get("name") or "").lower() == normalized_query else 1,
            0 if (result.get("name") or "").lower().startswith(normalized_query) else 1,
            0 if build_location_label(result).lower().startswith(normalized_query) else 1,
            0 if normalized_query in build_location_label(result).lower() else 1,
            -(result.get("population") or 0),
            build_location_label(result).lower(),
        ),
    )

    suggestions = []
    seen_labels = set()
    for result in ranked_results:
        label = build_location_label(result, fallback=query.strip().title())
        if label in seen_labels:
            continue
        seen_labels.add(label)

        suggestions.append(
            {
                "label": label,
                "query": label,
                "name": result.get("name", query.strip()),
                "admin1": result.get("admin1"),
                "country": result.get("country"),
                "latitude": result.get("latitude"),
                "longitude": result.get("longitude"),
            }
        )

        if len(suggestions) == 8:
            break

    return suggestions


@st.cache_data(show_spinner=False, ttl=1800)
def get_weather(city_name):
    location, city_query = _resolve_location(city_name)

    try:
        return _build_metno_weather_payload(location, city_query)
    except (requests.RequestException, ForecastDataError):
        pass

    try:
        forecast_data = _fetch_open_meteo_forecast(location)
        _clear_open_meteo_degraded()
        return _build_open_meteo_weather_payload(location, city_query, forecast_data)
    except (requests.RequestException, ForecastDataError, WeatherError):
        _mark_open_meteo_degraded()
        try:
            return _build_metno_weather_payload(location, city_query)
        except (requests.RequestException, ForecastDataError) as exc:
            raise WeatherError("Unable to fetch weather data right now.") from exc


@st.cache_data(show_spinner=False, ttl=1800)
def get_daily_weather_range(latitude, longitude, start_date, end_date, timezone_name="auto"):
    if isinstance(start_date, date):
        start_date = start_date.isoformat()
    if isinstance(end_date, date):
        end_date = end_date.isoformat()

    start_dt = datetime.fromisoformat(start_date).date()
    end_dt = datetime.fromisoformat(end_date).date()
    today = datetime.now().date()
    can_use_metno_range = start_dt >= today and end_dt <= today + timedelta(days=METNO_FALLBACK_HORIZON_DAYS)

    if can_use_metno_range and _should_prefer_metno():
        try:
            forecast_rows = _build_metno_daily_range(latitude, longitude, start_dt, end_dt, timezone_name or "")
            if forecast_rows:
                return forecast_rows
        except (requests.RequestException, ForecastDataError):
            pass

    try:
        response = requests.get(
            FORECAST_URL,
            params={
                "latitude": latitude,
                "longitude": longitude,
                "daily": ",".join(DAILY_EXPORT_FIELDS),
                "timezone": timezone_name or "auto",
                "start_date": start_date,
                "end_date": end_date,
            },
            timeout=OPEN_METEO_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
    except requests.RequestException:
        if can_use_metno_range:
            _mark_open_meteo_degraded()
            try:
                forecast_rows = _build_metno_daily_range(latitude, longitude, start_dt, end_dt, timezone_name or "")
                if forecast_rows:
                    return forecast_rows
            except (requests.RequestException, ForecastDataError):
                pass
        raise WeatherError("Unable to load the selected date range right now.")

    _clear_open_meteo_degraded()
    daily = (response.json() or {}).get("daily") or {}
    forecast_rows = _build_daily_forecast_rows(daily)
    if not forecast_rows:
        raise ForecastDataError("No weather data is available for the selected date range.")
    return forecast_rows
