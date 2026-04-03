import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import requests
import streamlit as st


GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
STATE_FILE = Path("last_weather_state.json")
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
        response = requests.get(
            GEOCODING_URL,
            params={
                "name": query.strip(),
                "count": 12,
                "language": "en",
                "format": "json",
            },
            timeout=8,
        )
        response.raise_for_status()
    except requests.RequestException:
        return []

    ranked_results = sorted(
        response.json().get("results", []),
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
    location = None
    city_query = city_name

    if isinstance(city_name, dict):
        city_query = city_name.get("query") or city_name.get("label") or ""
        if city_name.get("latitude") is not None and city_name.get("longitude") is not None:
            location = city_name

    try:
        if location is None:
            geocode_response = requests.get(
                GEOCODING_URL,
                params={
                    "name": city_query,
                    "count": 1,
                    "language": "en",
                    "format": "json",
                },
                timeout=10,
            )
            geocode_response.raise_for_status()
            geocode_data = geocode_response.json()
            results = geocode_data.get("results") or []
            if not results:
                raise CityNotFoundError("City not found.")

            location = results[0]
    except requests.RequestException as exc:
        raise WeatherError("Unable to connect to the weather service right now.") from exc

    try:
        hourly_fields = [
            "temperature_2m",
            "precipitation_probability",
            "precipitation",
            "weather_code",
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
                "daily": ",".join(
                    DAILY_EXPORT_FIELDS
                ),
                "hourly": ",".join(hourly_fields),
                "timezone": "auto",
                "forecast_days": 10,
            },
            timeout=10,
        )
        forecast_response.raise_for_status()
        forecast_data = forecast_response.json()
    except requests.RequestException as exc:
        raise WeatherError("Unable to fetch weather data right now.") from exc

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

    times = daily.get("time") or []
    hourly_times = hourly.get("time") or []
    hourly_temperatures = hourly.get("temperature_2m") or []
    hourly_rain_chances = hourly.get("precipitation_probability") or []
    hourly_rain_totals = hourly.get("precipitation") or []
    hourly_codes = hourly.get("weather_code") or []
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
                "time": format_time(iso_time),
                "temperature": round(hourly_temperatures[index], 1),
                "rain_chance": int(round(hourly_rain_chances[index] or 0)),
                "rain_total": round(hourly_rain_totals[index] or 0, 1),
                "condition": weather_code_to_condition(hourly_codes[index]),
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
        day_hourly_points = [point for point in hourly_points if point["date"] == day_key]
        forecast[index]["hourly"] = day_hourly_points

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


@st.cache_data(show_spinner=False, ttl=1800)
def get_daily_weather_range(latitude, longitude, start_date, end_date, timezone_name="auto"):
    if isinstance(start_date, date):
        start_date = start_date.isoformat()
    if isinstance(end_date, date):
        end_date = end_date.isoformat()

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
            timeout=10,
        )
        response.raise_for_status()
    except requests.RequestException as exc:
        raise WeatherError("Unable to load the selected date range right now.") from exc

    daily = (response.json() or {}).get("daily") or {}
    forecast_rows = _build_daily_forecast_rows(daily)
    if not forecast_rows:
        raise ForecastDataError("No weather data is available for the selected date range.")
    return forecast_rows
