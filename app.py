import base64
import json
import unicodedata
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path
from textwrap import dedent
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import streamlit as st
import streamlit.components.v1 as components

from services.weather_client import (
    CityNotFoundError,
    ForecastDataError,
    WeatherError,
    get_daily_weather_range,
    get_weather,
    load_last_weather_state,
    save_last_weather_state,
)
from services.exporters import (
    build_csv_export,
    build_excel_export,
    build_pdf_export,
    build_trip_plan_pdf,
)
from services.clothing_catalog import (
    get_clothing_visual_bundle,
    get_clothing_visual_bundle_for_conditions,
)
from services.user_preferences import (
    load_user_preferences,
    save_user_preferences,
)
from services.place_recommendations import (
    get_local_place_recommendations,
)
from ui.components import (
    apply_theme,
    format_precipitation,
    get_background_profile,
    get_current_condition_display,
    render_persistent_nav_bridge,
    get_condition_icon,
    get_feels_like_icon,
    get_humidity_icon,
    get_temp_icon,
    get_wind_icon,
    render_expandable_metric_card,
    render_guidance_card_grid,
    render_live_weather_map,
    render_visual_clothing_grid,
    render_recommendation_card,
    render_section_transition,
    render_todays_insight_card,
    render_topbar,
    render_weather_alert_banner,
    render_weather_score_row,
)


SEARCH_COMPONENT = components.declare_component(
    "skyline_search_glass",
    path=str(Path(__file__).resolve().parent / "ui" / "search_component"),
)
APP_LOGO_PATH = Path(__file__).resolve().parent / "images" / "skyline_forecast_logo.svg"


# User-facing constants for unit controls.
TEMP_OPTIONS = ["Celsius (\u00b0C)", "Fahrenheit (\u00b0F)"]
SPEED_OPTIONS = ["km/h", "mph"]
EXPORT_RANGE_OPTIONS = [
    ("today", "Today"),
    ("next_3_days", "Next 3 Days"),
    ("next_7_days", "Next 7 Days"),
    ("next_10_days", "Next 10 Days"),
    ("past_3_days", "Past 3 Days"),
    ("past_7_days", "Past 7 Days"),
    ("past_10_days", "Past 10 Days"),
    ("custom_range", "Custom Range"),
]
EXPORT_FORMAT_OPTIONS = [
    ("csv", "CSV"),
    ("excel", "Excel"),
    ("pdf", "PDF"),
]
EXPORT_PAST_LOOKBACK_LIMIT_DAYS = 30
EXPORT_FUTURE_LOOKAHEAD_LIMIT_DAYS = 16
EXPORT_MAX_SELECTED_DAYS = 20
MAP_LAYER_OPTIONS = ["Clouds", "Temperature", "Rain", "Wind", "Pressure", "Radar", "Satellite"]
CONTENT_SECTIONS = ["Overview", "Insights", "What to Wear", "Activities", "Map", "Compare"]
TIME_SLOT_CONFIG = [
    {
        "key": "morning",
        "label": "Morning",
        "reference": "this morning",
        "eyebrow": "Morning Start",
        "icon": "\U0001f305",
        "visual_slot": "tops",
        "preferred_variant_index": 1,
    },
    {
        "key": "afternoon",
        "label": "Afternoon",
        "reference": "this afternoon",
        "eyebrow": "Midday Shift",
        "icon": "\u2600\ufe0f",
        "visual_slot": "tops",
        "preferred_variant_index": 2,
    },
    {
        "key": "evening",
        "label": "Evening",
        "reference": "this evening",
        "eyebrow": "Evening Drop",
        "icon": "\U0001f307",
        "visual_slot": "outerwear",
        "preferred_variant_index": 1,
    },
    {
        "key": "night",
        "label": "Night",
        "reference": "tonight",
        "eyebrow": "Night Layer",
        "icon": "\U0001f319",
        "visual_slot": "outerwear",
        "preferred_variant_index": 2,
    },
]
PERSONAL_ACTIVITY_OPTIONS = ["Mixed", "Walking", "Running / Exercise", "Outdoor Tasks", "Studying Outside"]
PERSONAL_TIME_OPTIONS = ["Flexible", "Morning", "Afternoon", "Evening", "Night"]
PERSONAL_TEMPERATURE_OPTIONS = ["Balanced", "I run cold", "I run warm"]
PERSONAL_OUTFIT_OPTIONS = ["Casual", "Sporty", "Smart Casual"]

PERSONAL_ACTIVITY_KEY_MAP = {
    "Mixed": "mixed",
    "Walking": "walking",
    "Running / Exercise": "running",
    "Outdoor Tasks": "outdoor_tasks",
    "Studying Outside": "studying_outside",
}
PERSONAL_ROUTINE_TITLE_MAP = {
    "walking": "Walking",
    "running": "Running",
    "outdoor_tasks": "Outdoor Tasks",
    "studying_outside": "Studying Outside",
}
PERSONAL_TIME_KEY_MAP = {
    "Flexible": "",
    "Morning": "morning",
    "Afternoon": "afternoon",
    "Evening": "evening",
    "Night": "night",
}
PERSONAL_TEMPERATURE_OFFSET_MAP = {
    "Balanced": 0,
    "I run cold": -3,
    "I run warm": 3,
}
PERSONAL_OUTFIT_KEY_MAP = {
    "Casual": "casual",
    "Sporty": "sporty",
    "Smart Casual": "smart_casual",
}
PERSONALIZATION_PROMPT_PENDING = "pending"
PERSONALIZATION_PROMPT_SAVED = "saved"
PERSONALIZATION_PROMPT_LATER = "later"
PERSONALIZATION_PROMPT_HIDDEN = "hidden"

ROUTINE_ACTIVITY_PROFILES = [
    {
        "key": "walking",
        "eyebrow": "Walking",
        "label": "walk",
        "title": "Best time to walk",
        "icon": "\U0001f6b6",
        "ideal_temp_range": (18, 28),
        "hard_temp_range": (10, 35),
        "rain_weight": 0.32,
        "wind_limit": 25,
        "wind_penalty": 1.1,
        "humidity_limit": 68,
        "humidity_penalty": 0.28,
        "minimum_score": 66,
        "hour_window": (6, 21),
        "target_block_hours": 3,
    },
    {
        "key": "running",
        "eyebrow": "Running",
        "label": "run",
        "title": "Best time to run",
        "icon": "\U0001f3c3",
        "ideal_temp_range": (16, 24),
        "hard_temp_range": (8, 32),
        "rain_weight": 0.36,
        "wind_limit": 22,
        "wind_penalty": 1.25,
        "humidity_limit": 60,
        "humidity_penalty": 0.42,
        "minimum_score": 68,
        "hour_window": (5, 20),
        "target_block_hours": 2,
    },
    {
        "key": "outdoor_tasks",
        "eyebrow": "Outdoor Tasks",
        "label": "outdoor tasks",
        "title": "Best time for outdoor tasks",
        "icon": "\U0001f6e0\ufe0f",
        "ideal_temp_range": (18, 30),
        "hard_temp_range": (10, 36),
        "rain_weight": 0.42,
        "wind_limit": 26,
        "wind_penalty": 1.05,
        "humidity_limit": 70,
        "humidity_penalty": 0.22,
        "minimum_score": 64,
        "hour_window": (7, 19),
        "target_block_hours": 3,
    },
    {
        "key": "studying_outside",
        "eyebrow": "Studying Outside",
        "label": "study outside",
        "title": "Best time to study outside",
        "icon": "\U0001f4da",
        "ideal_temp_range": (20, 27),
        "hard_temp_range": (12, 34),
        "rain_weight": 0.3,
        "wind_limit": 20,
        "wind_penalty": 1.15,
        "humidity_limit": 62,
        "humidity_penalty": 0.26,
        "minimum_score": 67,
        "hour_window": (7, 19),
        "target_block_hours": 3,
    },
]


# Unit conversion helpers keep display logic straightforward.
def celsius_to_fahrenheit(value):
    return (value * 9 / 5) + 32


def kmh_to_mph(value):
    return value * 0.621371


def format_temperature_value(value, use_fahrenheit=False):
    display_value = celsius_to_fahrenheit(value) if use_fahrenheit else value
    return round(display_value, 1)


def format_temperature_delta(value, use_fahrenheit=False):
    display_value = value * 9 / 5 if use_fahrenheit else value
    return round(abs(display_value), 1)


def format_temperature_text(value, temp_symbol, use_fahrenheit=False):
    return f"{format_temperature_value(value, use_fahrenheit)}{temp_symbol}"


def format_wind_value(value, speed_symbol):
    display_value = kmh_to_mph(value) if speed_symbol == "mph" else value
    return round(display_value, 1)


def format_wind_text(value, speed_symbol):
    return f"{format_wind_value(value, speed_symbol)} {speed_symbol}"


def clamp_score(value):
    return max(0, min(int(round(value)), 10))


def get_time_phase(hour):
    if 5 <= hour < 11:
        return {"key": "morning", "label": "Morning", "reference": "this morning"}
    if 11 <= hour < 17:
        return {"key": "afternoon", "label": "Afternoon", "reference": "this afternoon"}
    if 17 <= hour < 21:
        return {"key": "evening", "label": "Evening", "reference": "this evening"}
    return {"key": "night", "label": "Night", "reference": "tonight"}


def get_relative_day_label(target_date, reference_date):
    if target_date == reference_date:
        return "Today"
    if target_date == reference_date + timedelta(days=1):
        return "Tomorrow"
    if target_date == reference_date - timedelta(days=1):
        return "Yesterday"
    return target_date.strftime("%A")


def format_relative_phase_reference(target_dt, reference_dt):
    phase = get_time_phase(target_dt.hour)
    relative_day = get_relative_day_label(target_dt.date(), reference_dt.date())
    if relative_day == "Today":
        return "tonight" if phase["key"] == "night" else f"later this {phase['label'].lower()}"
    if relative_day == "Tomorrow":
        return f"tomorrow {phase['label'].lower()}"
    return f"{relative_day.lower()} {phase['label'].lower()}"


def get_hourly_point_datetime(point):
    if not point:
        return None

    if point.get("time_dt") and isinstance(point.get("time_dt"), datetime):
        return point["time_dt"]

    if point.get("time_iso"):
        try:
            return datetime.fromisoformat(point["time_iso"])
        except ValueError:
            pass

    try:
        return datetime.strptime(
            f"{point['date']} {point['time']}",
            "%Y-%m-%d %I:%M %p",
        )
    except (KeyError, TypeError, ValueError):
        return None


def collect_hourly_forecast_points(weather_to_show, limit_days=2):
    forecast = (weather_to_show or {}).get("forecast") or []
    entries = []
    for day in forecast[:limit_days]:
        for point in day.get("hourly") or []:
            point_dt = get_hourly_point_datetime(point)
            if not point_dt:
                continue
            entries.append((point_dt, {**point, "time_dt": point_dt}))
    entries.sort(key=lambda item: item[0])
    return entries


def build_local_time_context(weather_to_show):
    local_now = get_weather_local_now(weather_to_show)
    hourly_entries = collect_hourly_forecast_points(weather_to_show, limit_days=2)

    if hourly_entries and hourly_entries[0][0].tzinfo is None and local_now.tzinfo is not None:
        reference_now = local_now.replace(tzinfo=None)
    else:
        reference_now = local_now

    current_hour = reference_now.replace(minute=0, second=0, microsecond=0)
    current_phase = get_time_phase(reference_now.hour)
    future_entries = [entry for entry in hourly_entries if entry[0] >= current_hour]
    fallback_entries = future_entries or hourly_entries
    current_entry = fallback_entries[0] if fallback_entries else None
    current_point = current_entry[1] if current_entry else None

    today_entries = [entry for entry in hourly_entries if entry[0].date() == reference_now.date()]
    remaining_today_entries = [entry for entry in today_entries if entry[0] >= current_hour] or today_entries
    scheduler_entries = future_entries[:14] or remaining_today_entries or hourly_entries[:14]
    next_window_entries = future_entries[:8] or hourly_entries[:8]

    next_phase_entry = next(
        (entry for entry in future_entries if get_time_phase(entry[0].hour)["key"] != current_phase["key"]),
        None,
    )

    if current_point and next_window_entries:
        end_temperature = next_window_entries[-1][1].get("temperature", current_point.get("temperature", 0))
        temp_delta = end_temperature - current_point.get("temperature", 0)
    else:
        temp_delta = 0

    if temp_delta >= 2:
        temp_trend = "warming"
    elif temp_delta <= -2:
        temp_trend = "cooling"
    else:
        temp_trend = "steady"

    peak_rain = max((entry[1].get("rain_chance", 0) for entry in next_window_entries), default=0)
    peak_wind = max((entry[1].get("wind", 0) for entry in next_window_entries), default=0)
    low_next_temp = min((entry[1].get("temperature", 0) for entry in next_window_entries), default=0)
    high_next_temp = max((entry[1].get("temperature", 0) for entry in next_window_entries), default=0)
    next_phase_reference = (
        format_relative_phase_reference(next_phase_entry[0], reference_now)
        if next_phase_entry
        else current_phase["reference"]
    )

    return {
        "local_now": local_now,
        "reference_now": reference_now,
        "local_time_label": local_now.strftime("%I:%M %p").lstrip("0"),
        "local_day_label": local_now.strftime("%A"),
        "phase_key": current_phase["key"],
        "phase_label": current_phase["label"],
        "phase_reference": current_phase["reference"],
        "next_phase_reference": next_phase_reference,
        "current_point": current_point,
        "remaining_today_points": [entry[1] for entry in remaining_today_entries],
        "scheduler_points": [entry[1] for entry in scheduler_entries],
        "next_window_points": [entry[1] for entry in next_window_entries],
        "peak_rain": peak_rain,
        "peak_wind": peak_wind,
        "low_next_temp": low_next_temp,
        "high_next_temp": high_next_temp,
        "temp_trend": temp_trend,
    }


def resolve_context_snapshot(weather_to_show, time_context=None):
    time_context = time_context or build_local_time_context(weather_to_show)
    current = weather_to_show["current"]
    today = weather_to_show["forecast"][0] if weather_to_show.get("forecast") else {}
    hourly_point = time_context.get("current_point") or {}

    return {
        "temperature": hourly_point.get("temperature", current.get("temperature", 0)),
        "humidity": hourly_point.get("humidity", current.get("humidity", 0)),
        "wind": hourly_point.get("wind", current.get("wind", 0)),
        "condition": hourly_point.get("condition", current.get("condition", "Current conditions")),
        "rain_chance": hourly_point.get("rain_chance", today.get("rain_chance", 0)),
        "rain_total": hourly_point.get("rain_total", current.get("precipitation", 0)),
        "is_day": hourly_point.get("is_day", True),
    }


def describe_score_limiter(snapshot):
    if snapshot["condition"] == "Thunderstorm" or snapshot["rain_chance"] >= 60:
        return "rain pressure"
    if snapshot["temperature"] >= 32:
        return "heat buildup"
    if snapshot["temperature"] <= 10:
        return "cold air"
    if snapshot["wind"] >= 25:
        return "wind exposure"
    if snapshot["humidity"] >= 75:
        return "heavier humidity"
    return "very little immediate weather pressure"


def describe_temperature_shift(time_context, temp_symbol, use_fahrenheit):
    low_temp = format_temperature_text(time_context["low_next_temp"], temp_symbol, use_fahrenheit)
    high_temp = format_temperature_text(time_context["high_next_temp"], temp_symbol, use_fahrenheit)
    if time_context["temp_trend"] == "cooling":
        return f"temperatures ease back toward {low_temp}"
    if time_context["temp_trend"] == "warming":
        return f"temperatures climb closer to {high_temp}"
    return f"temperatures hold between {low_temp} and {high_temp}"


def tighten_preview_copy(text, max_length=118):
    cleaned = " ".join(str(text or "").split())
    if len(cleaned) <= max_length:
        return cleaned

    break_markers = [". ", "! ", "? ", "; ", " This ", " Later ", " Rain ", " Wind ", " UV ", " because ", " while ", " so "]
    for marker in break_markers:
        marker_index = cleaned.find(marker)
        if 0 < marker_index <= max_length:
            clipped = cleaned[:marker_index].rstrip(",;: ")
            return clipped if clipped.endswith((".", "!", "?")) else clipped + "."

    clipped = cleaned[:max_length].rsplit(" ", 1)[0].rstrip(",;: ")
    return clipped + "..."


def get_base_outfit_variant_index(item_id, phase_key):
    phase_preferences = {
        "morning": {
            "tops": 1,
            "bottoms": 0,
            "outerwear": 0,
            "shoes": 0,
            "accessories": 1,
            "weather-add-ons": 0,
        },
        "afternoon": {
            "tops": 2,
            "bottoms": 1,
            "outerwear": 0,
            "shoes": 1,
            "accessories": 2,
            "weather-add-ons": 0,
        },
        "evening": {
            "tops": 0,
            "bottoms": 1,
            "outerwear": 1,
            "shoes": 1,
            "accessories": 0,
            "weather-add-ons": 0,
        },
        "night": {
            "tops": 0,
            "bottoms": 1,
            "outerwear": 2,
            "shoes": 0,
            "accessories": 1,
            "weather-add-ons": 0,
        },
    }
    return int(phase_preferences.get(phase_key, {}).get(item_id, 0))


def get_personalization_profile(source=None):
    source = source or st.session_state
    activity_focus = str(source.get("personal_activity_focus", source.get("activity_focus", PERSONAL_ACTIVITY_OPTIONS[0])) or PERSONAL_ACTIVITY_OPTIONS[0])
    preferred_time = str(source.get("personal_preferred_time", source.get("preferred_time", PERSONAL_TIME_OPTIONS[0])) or PERSONAL_TIME_OPTIONS[0])
    temperature_preference = str(
        source.get("personal_temperature_preference", source.get("temperature_preference", PERSONAL_TEMPERATURE_OPTIONS[0]))
        or PERSONAL_TEMPERATURE_OPTIONS[0]
    )
    outfit_vibe = str(source.get("personal_outfit_vibe", source.get("outfit_vibe", PERSONAL_OUTFIT_OPTIONS[0])) or PERSONAL_OUTFIT_OPTIONS[0])

    return {
        "activity_focus": activity_focus,
        "activity_focus_key": PERSONAL_ACTIVITY_KEY_MAP.get(activity_focus, "mixed"),
        "preferred_time": preferred_time,
        "preferred_time_key": PERSONAL_TIME_KEY_MAP.get(preferred_time, ""),
        "temperature_preference": temperature_preference,
        "temperature_offset": PERSONAL_TEMPERATURE_OFFSET_MAP.get(temperature_preference, 0),
        "outfit_vibe": outfit_vibe,
        "outfit_vibe_key": PERSONAL_OUTFIT_KEY_MAP.get(outfit_vibe, "casual"),
        "is_customized": any(
            [
                activity_focus != PERSONAL_ACTIVITY_OPTIONS[0],
                preferred_time != PERSONAL_TIME_OPTIONS[0],
                temperature_preference != PERSONAL_TEMPERATURE_OPTIONS[0],
                outfit_vibe != PERSONAL_OUTFIT_OPTIONS[0],
            ]
        ),
    }


def get_personalization_prompt_state(source=None):
    source = source or st.session_state
    return str(source.get("personalization_prompt_status") or PERSONALIZATION_PROMPT_PENDING)


def should_show_personalization_prompt(source=None):
    source = source or st.session_state
    prompt_state = get_personalization_prompt_state(source)
    if prompt_state in {PERSONALIZATION_PROMPT_SAVED, PERSONALIZATION_PROMPT_HIDDEN}:
        return False
    if prompt_state != PERSONALIZATION_PROMPT_LATER:
        return True

    remind_after = str(source.get("personalization_remind_after") or "").strip()
    if not remind_after:
        return True
    try:
        remind_date = date.fromisoformat(remind_after)
    except ValueError:
        return True
    return date.today() >= remind_date


def phase_key_for_hourly_point(point):
    point_dt = get_hourly_point_datetime(point)
    if point_dt:
        return get_time_phase(point_dt.hour)["key"]
    moment = parse_scheduler_hour_label(point.get("time"))
    if moment:
        return get_time_phase(moment.hour)["key"]
    return ""


def apply_temperature_preference(temperature, personalization):
    personalization = get_personalization_profile(personalization)
    return temperature + personalization["temperature_offset"]


def choose_style_preferred_variant_index(variants, fallback_index, outfit_vibe_key):
    if not variants:
        return fallback_index
    if outfit_vibe_key not in {"casual", "sporty", "smart_casual"}:
        return fallback_index

    style_keywords = {
        "casual": ["tee", "hoodie", "relaxed", "casual", "denim", "soft", "simple", "everyday", "sandal"],
        "sporty": ["runner", "running", "trainer", "sport", "sporty", "shell", "cap", "active", "movement"],
        "smart_casual": ["polo", "shirt", "collared", "structured", "sharp", "smart", "polished", "leather", "clean", "classic"],
    }

    best_index = fallback_index
    best_score = -1
    for index, variant in enumerate(variants):
        haystack = " ".join(
            [
                str(variant.get("style_name") or ""),
                str(variant.get("note") or ""),
                " ".join(str(badge) for badge in variant.get("badges", [])),
                " ".join(str(tag) for tag in variant.get("tags", [])),
            ]
        ).lower()
        score = sum(1 for keyword in style_keywords[outfit_vibe_key] if keyword in haystack)
        if score > best_score or (score == best_score and abs(index - fallback_index) < abs(best_index - fallback_index)):
            best_score = score
            best_index = index

    return best_index if best_score > 0 else fallback_index


def get_personalization_draft_values(key_prefix):
    return {
        "personal_activity_focus": st.session_state.get(f"{key_prefix}_activity_focus_choice", PERSONAL_ACTIVITY_OPTIONS[0]),
        "personal_preferred_time": st.session_state.get(f"{key_prefix}_preferred_time_choice", PERSONAL_TIME_OPTIONS[0]),
        "personal_temperature_preference": st.session_state.get(f"{key_prefix}_temperature_preference_choice", PERSONAL_TEMPERATURE_OPTIONS[0]),
        "personal_outfit_vibe": st.session_state.get(f"{key_prefix}_outfit_vibe_choice", PERSONAL_OUTFIT_OPTIONS[0]),
    }


def sync_personalization_draft_state(key_prefix):
    st.session_state[f"{key_prefix}_activity_focus_choice"] = st.session_state.get("personal_activity_focus", PERSONAL_ACTIVITY_OPTIONS[0])
    st.session_state[f"{key_prefix}_preferred_time_choice"] = st.session_state.get("personal_preferred_time", PERSONAL_TIME_OPTIONS[0])
    st.session_state[f"{key_prefix}_temperature_preference_choice"] = st.session_state.get("personal_temperature_preference", PERSONAL_TEMPERATURE_OPTIONS[0])
    st.session_state[f"{key_prefix}_outfit_vibe_choice"] = st.session_state.get("personal_outfit_vibe", PERSONAL_OUTFIT_OPTIONS[0])


def apply_personalization_draft_state(key_prefix):
    st.session_state.update(get_personalization_draft_values(key_prefix))


def describe_personalization_summary(personalization):
    personalization = get_personalization_profile(personalization)
    return " | ".join(
        [
            f"Focus: {personalization['activity_focus']}",
            f"Best time: {personalization['preferred_time']}",
            f"Temperature: {personalization['temperature_preference']}",
            f"Style: {personalization['outfit_vibe']}",
        ]
    )


def calculate_weather_scores(weather_to_show, time_context=None, personalization=None):
    time_context = time_context or build_local_time_context(weather_to_show)
    personalization = get_personalization_profile(personalization)
    current = weather_to_show["current"]
    today = weather_to_show["forecast"][0] if weather_to_show.get("forecast") else {}
    snapshot = resolve_context_snapshot(weather_to_show, time_context)
    current_temp = apply_temperature_preference(snapshot["temperature"], personalization)
    humidity = snapshot["humidity"]
    wind_speed = snapshot["wind"]
    rain_chance = snapshot["rain_chance"]
    precipitation = max(snapshot["rain_total"], current.get("precipitation", 0))
    visibility = current.get("visibility", 10)
    condition = snapshot["condition"]
    phase_key = time_context["phase_key"]
    uv_index = today.get("uv_index", 0)

    current = weather_to_show["current"]

    comfort = 10.0
    comfort -= max(0, current_temp - 26) * 0.28
    comfort -= max(0, 18 - current_temp) * 0.34
    comfort -= max(0, humidity - 65) * 0.04
    comfort -= max(0, 30 - humidity) * 0.04
    comfort -= max(0, wind_speed - 25) * 0.07
    comfort -= min(rain_chance, 100) * 0.012
    comfort -= min(precipitation, 10) * 0.35
    if condition == "Thunderstorm":
        comfort -= 2.5
    elif condition == "Snowy":
        comfort -= 1.4

    outdoor = 10.0
    outdoor -= max(0, current_temp - 30) * 0.26
    outdoor -= max(0, 10 - current_temp) * 0.40
    outdoor -= min(rain_chance, 100) * 0.035
    outdoor -= min(precipitation, 10) * 0.40
    outdoor -= max(0, wind_speed - 18) * 0.09
    if condition in {"Thunderstorm", "Snowy"}:
        outdoor -= 2.8
    elif condition == "Rainy":
        outdoor -= 1.2

    travel = 10.0
    travel -= min(rain_chance, 100) * 0.025
    travel -= min(precipitation, 10) * 0.35
    travel -= max(0, wind_speed - 28) * 0.08
    if visibility < 4:
        travel -= (4 - visibility) * 0.9
    if condition == "Foggy":
        travel -= 1.8
    elif condition == "Thunderstorm":
        travel -= 3.0
    elif condition == "Snowy":
        travel -= 2.5

    if phase_key == "morning":
        if 16 <= current_temp <= 27 and humidity <= 72:
            comfort += 0.35
            outdoor += 0.25
        travel += 0.15
    elif phase_key == "afternoon":
        comfort -= max(0, uv_index - 5) * 0.18
        if current_temp >= 30:
            comfort -= 0.45
            outdoor -= 0.65
    elif phase_key == "evening":
        if current_temp <= 30 and rain_chance < 30 and wind_speed < 22:
            comfort += 0.35
            outdoor += 0.45
    else:
        outdoor -= 0.9
        if 14 <= current_temp <= 26 and rain_chance < 25 and wind_speed < 18:
            comfort += 0.25
        if visibility < 6 or condition in {"Foggy", "Rainy", "Thunderstorm", "Snowy"}:
            travel -= 0.45

    return {
        "comfort": clamp_score(comfort),
        "outdoor": clamp_score(outdoor),
        "travel": clamp_score(travel),
    }


def build_weather_alerts(weather_to_show, temp_symbol, speed_symbol, use_fahrenheit, time_context=None, personalization=None):
    time_context = time_context or build_local_time_context(weather_to_show)
    personalization = get_personalization_profile(personalization)
    current = weather_to_show["current"]
    today = weather_to_show["forecast"][0] if weather_to_show.get("forecast") else {}
    snapshot = resolve_context_snapshot(weather_to_show, time_context)
    alerts = []
    day_high = apply_temperature_preference(today.get("max", current["temperature"]), personalization)
    day_low = apply_temperature_preference(today.get("min", current["temperature"]), personalization)
    personal_now = apply_temperature_preference(snapshot["temperature"], personalization)
    rain_chance = max(today.get("rain_chance", 0), snapshot["rain_chance"])
    wind_speed = max(current["wind"], snapshot["wind"])
    phase_reference = time_context["phase_reference"]

    if snapshot["condition"] == "Thunderstorm":
        alerts.append(
            {
                "tone": "danger",
                "icon": "\u26c8\ufe0f",
                "title": "Storm conditions are active",
                "body": f"Thunderstorm activity is shaping {phase_reference}, so outdoor plans and longer travel are less reliable.",
            }
        )

    if day_high >= 35:
        alerts.append(
            {
                "tone": "warning",
                "icon": "\U0001f525",
                "title": "High temperature warning",
                "body": (
                    f"The day's high still reaches about {format_temperature_text(day_high, temp_symbol, use_fahrenheit)}, "
                    f"so heat remains part of the planning picture {phase_reference}."
                ),
            }
        )

    if rain_chance >= 55 or snapshot["rain_total"] >= 0.3:
        alerts.append(
            {
                "tone": "info",
                "icon": "\U0001f327\ufe0f",
                "title": "Rain is likely",
                "body": f"Rain risk is near {rain_chance}% across the next hours, so wet surfaces and showers are worth planning around.",
            }
        )

    if wind_speed >= 30:
        alerts.append(
            {
                "tone": "warning",
                "icon": "\U0001f32c\ufe0f",
                "title": "Strong wind warning",
                "body": f"Winds are near {format_wind_text(wind_speed, speed_symbol)} {phase_reference}, which can make outdoor time feel noticeably rougher.",
            }
        )

    if day_low <= 8 or personal_now <= 8:
        alerts.append(
            {
                "tone": "notice",
                "icon": "\u2744\ufe0f",
                "title": "Cold weather notice",
                "body": f"Temperatures dip toward {format_temperature_text(day_low, temp_symbol, use_fahrenheit)}, so warmer layers will help {phase_reference}.",
            }
        )

    if not alerts:
        alerts.append(
            {
                "tone": "calm",
                "icon": "\u2705",
                "title": "No major weather alerts",
                "body": f"{phase_reference.capitalize()} looks fairly steady, with no strong warning signals standing out from the local-time snapshot.",
            }
        )

    return alerts[:4]


def build_weather_score_cards(weather_to_show, time_context=None, personalization=None):
    time_context = time_context or build_local_time_context(weather_to_show)
    personalization = get_personalization_profile(personalization)
    current = weather_to_show["current"]
    snapshot = resolve_context_snapshot(weather_to_show, time_context)
    rain_chance = max(
        snapshot["rain_chance"],
        weather_to_show["forecast"][0].get("rain_chance", 0) if weather_to_show.get("forecast") else 0,
    )
    scores = calculate_weather_scores(weather_to_show, time_context, personalization)
    phase_reference = time_context["phase_reference"]
    limiter_text = describe_score_limiter(snapshot)

    score_cards = [
        {
            "key": "comfort",
            "label": "Comfort Score",
            "value": scores["comfort"],
            "summary": (
                f"Comfort is strongest {phase_reference}, so the air should feel balanced and easy to stay in."
                if scores["comfort"] >= 8
                else f"Comfort is workable {phase_reference}, but {limiter_text} is the main thing you will notice."
                if scores["comfort"] >= 5
                else f"Comfort is softer {phase_reference}, so {limiter_text} is the part to plan around."
            ),
        },
        {
            "key": "outdoor",
            "label": "Outdoor Score",
            "value": scores["outdoor"],
            "summary": (
                f"Open-air plans read well {phase_reference}, especially if you want a cleaner window for walking or errands."
                if scores["outdoor"] >= 8
                else f"Outdoor plans still work {phase_reference}, but timing and pacing matter more than usual."
                if scores["outdoor"] >= 5
                else f"Outdoor time is less appealing {phase_reference}, so shorter exposure or indoor backup makes more sense."
            ),
        },
        {
            "key": "travel",
            "label": "Travel Score",
            "value": scores["travel"],
            "summary": (
                f"Local movement should feel fairly smooth {phase_reference}."
                if scores["travel"] >= 8
                else f"Travel is still workable {phase_reference}, though weather may slow parts of the route down a bit."
                if scores["travel"] >= 5
                else f"Travel friction is higher {phase_reference}, so extra time and a steadier pace help."
            ),
        },
    ]

    if current["condition"] == "Foggy" and rain_chance < 35:
        score_cards[2]["summary"] = "Visibility is the main travel limiter even though precipitation is not the issue."

    return score_cards


def build_forecast_trend_insight(weather_to_show, temp_symbol, use_fahrenheit, time_context=None):
    time_context = time_context or build_local_time_context(weather_to_show)
    forecast = weather_to_show.get("forecast") or []
    current = weather_to_show.get("current") or {}
    actual_temp = current.get("temperature", 0)
    trend_window = forecast[:7]
    if len(trend_window) < 2:
        return None

    start_high = trend_window[0].get("max", actual_temp)
    end_high = trend_window[-1].get("max", actual_temp)
    rain_values = [day.get("rain_chance", 0) for day in trend_window]
    peak_rain = max(rain_values) if rain_values else 0
    average_rain = round(sum(rain_values) / len(rain_values)) if rain_values else 0
    high_shift = end_high - start_high
    low_span = min(day.get("max", actual_temp) for day in trend_window)
    high_span = max(day.get("max", actual_temp) for day in trend_window)

    if high_shift >= 3:
        trend_title = "Warming trend is building"
        trend_body = (
            f"After {time_context['phase_reference']}, forecast highs climb from {format_temperature_text(start_high, temp_symbol, use_fahrenheit)} "
            f"to {format_temperature_text(end_high, temp_symbol, use_fahrenheit)} across the next {len(trend_window)} days, "
            f"with rain chances reaching {peak_rain}%."
        )
    elif high_shift <= -3:
        trend_title = "Cooling trend is setting in"
        trend_body = (
            f"After {time_context['phase_reference']}, forecast highs ease from {format_temperature_text(start_high, temp_symbol, use_fahrenheit)} "
            f"to {format_temperature_text(end_high, temp_symbol, use_fahrenheit)} over the next {len(trend_window)} days, "
            f"while rain chances peak near {peak_rain}%."
        )
    else:
        trend_title = "Temperatures stay fairly stable"
        trend_body = (
            f"From {time_context['phase_reference']} forward, highs hold between {format_temperature_text(low_span, temp_symbol, use_fahrenheit)} "
            f"and {format_temperature_text(high_span, temp_symbol, use_fahrenheit)} through the next {len(trend_window)} days, "
            f"with average rain chances around {average_rain}%."
        )

    return {
        "eyebrow": "Forecast Trend",
        "title": trend_title,
        "body": trend_body,
        "icon": "\U0001f4c8",
    }


def build_smart_weather_insights(weather_to_show, temp_symbol, speed_symbol, use_fahrenheit, time_context=None):
    time_context = time_context or build_local_time_context(weather_to_show)
    personalization = get_personalization_profile()
    current = weather_to_show["current"]
    today = weather_to_show["forecast"][0] if weather_to_show.get("forecast") else {}
    snapshot = resolve_context_snapshot(weather_to_show, time_context)
    actual_temp = snapshot["temperature"]
    feels_like = current["feels_like"]
    humidity = snapshot["humidity"]
    wind_speed = snapshot["wind"]
    temp_gap = feels_like - actual_temp
    shift_text = describe_temperature_shift(time_context, temp_symbol, use_fahrenheit)

    if temp_gap >= 2:
        feels_like_title = "Feels warmer than the reading"
        feels_like_body = (
            f"{time_context['phase_reference'].capitalize()}, it feels about {format_temperature_delta(temp_gap, use_fahrenheit)}{temp_symbol} warmer than the measured "
            f"{format_temperature_text(actual_temp, temp_symbol, use_fahrenheit)} because moisture is reducing how quickly your body can cool."
        )
    elif temp_gap <= -2:
        feels_like_title = "Feels cooler than the reading"
        feels_like_body = (
            f"{time_context['phase_reference'].capitalize()}, it feels about {format_temperature_delta(temp_gap, use_fahrenheit)}{temp_symbol} cooler than the measured "
            f"{format_temperature_text(actual_temp, temp_symbol, use_fahrenheit)} because moving air is pulling heat away faster."
        )
    else:
        feels_like_title = "Feels close to the actual temperature"
        feels_like_body = (
            f"{time_context['phase_reference'].capitalize()}, feels-like and actual temperature are closely aligned, so conditions should feel near "
            f"{format_temperature_text(actual_temp, temp_symbol, use_fahrenheit)} for most people."
        )

    if humidity < 30:
        humidity_title = "Dry air setup"
        humidity_body = f"Humidity is {humidity}%, so {time_context['phase_reference']} can feel dry on the skin and throat during longer periods outside."
    elif humidity <= 60:
        humidity_title = "Comfortable humidity"
        humidity_body = f"Humidity is {humidity}%, keeping {time_context['phase_reference']} in a fairly balanced comfort range."
    elif humidity <= 75:
        humidity_title = "Slightly sticky air"
        humidity_body = f"Humidity is {humidity}%, so the air may feel a little heavier during walks or longer errands {time_context['phase_reference']}."
    else:
        humidity_title = "Muggy humidity"
        humidity_body = f"Humidity is {humidity}%, which can make {time_context['phase_reference']} feel warmer and reduce cooling comfort."

    if wind_speed < 10:
        wind_title = "Light air movement"
        wind_body = f"Winds are light at about {format_wind_text(wind_speed, speed_symbol)}, so the air should feel fairly still {time_context['phase_reference']}."
    elif wind_speed < 25:
        wind_title = "Steady breeze"
        wind_body = f"A breeze near {format_wind_text(wind_speed, speed_symbol)} keeps the air moving without feeling too rough {time_context['phase_reference']}."
    elif wind_speed < 35:
        wind_title = "Noticeable wind"
        wind_body = f"Winds near {format_wind_text(wind_speed, speed_symbol)} will be easy to notice {time_context['phase_reference']}, especially in open areas."
    else:
        wind_title = "Wind is a major factor"
        wind_body = f"Strong wind around {format_wind_text(wind_speed, speed_symbol)} can noticeably change comfort and outdoor plans {time_context['phase_reference']}."

    insights = [
        {
            "eyebrow": "Time Of Day Read",
            "title": f"{time_context['phase_label']} guidance is active",
            "body": (
                f"It is {time_context['local_time_label']} locally, so guidance is weighted toward {time_context['phase_reference']}. "
                f"{shift_text.capitalize()} over the next hours, with rain risk peaking near {time_context['peak_rain']}%."
                + (
                    f" Your profile leans toward {personalization['activity_focus'].lower()}, {personalization['preferred_time'].lower()}, and a {personalization['outfit_vibe'].lower()} outfit direction."
                    if personalization["is_customized"]
                    else ""
                )
            ),
            "icon": "\U0001f552",
        },
        {"eyebrow": "Feels-Like Logic", "title": feels_like_title, "body": feels_like_body, "icon": "\U0001f321\ufe0f"},
        {"eyebrow": "Humidity Comfort", "title": humidity_title, "body": humidity_body, "icon": "\U0001f4a7"},
        {"eyebrow": "Wind Summary", "title": wind_title, "body": wind_body, "icon": "\U0001f32c\ufe0f"},
    ]

    if today.get("uv_index", 0) >= 6 and time_context["phase_key"] in {"morning", "afternoon"}:
        insights.append(
            {
                "eyebrow": "Sun Pressure",
                "title": "Sun exposure is part of the read",
                "body": f"UV reaches about {today.get('uv_index', 0)} today, so midday comfort and what-to-wear guidance stay stricter than they would at night.",
                "icon": "\u2600\ufe0f",
            }
        )

    trend_insight = build_forecast_trend_insight(weather_to_show, temp_symbol, use_fahrenheit, time_context)
    if trend_insight:
        insights.append(trend_insight)

    return insights


def parse_scheduler_hour_label(hour_label):
    try:
        return datetime.strptime(hour_label, "%I:%M %p")
    except (TypeError, ValueError):
        return None


def format_scheduler_hour_label(moment):
    if not moment:
        return "--"
    return moment.strftime("%I %p").lstrip("0")


def format_scheduler_block_label(block_hours, reference_dt=None):
    if not block_hours:
        return "--"

    start_dt = get_hourly_point_datetime(block_hours[0])
    end_dt = get_hourly_point_datetime(block_hours[-1])
    if start_dt and end_dt:
        start_time = start_dt
        end_time = end_dt
    else:
        start_time = parse_scheduler_hour_label(block_hours[0]["time"])
        end_time = parse_scheduler_hour_label(block_hours[-1]["time"])
    if not start_time or not end_time:
        return block_hours[0]["time"]

    end_time = end_time + timedelta(hours=1)
    day_prefix = ""
    if reference_dt and hasattr(start_time, "date"):
        relative_day = get_relative_day_label(start_time.date(), reference_dt.date())
        if relative_day != "Today":
            day_prefix = f"{relative_day} "
    if len(block_hours) == 1:
        if start_time.strftime("%p") == end_time.strftime("%p"):
            return f"{day_prefix}{start_time.strftime('%I').lstrip('0')}-{end_time.strftime('%I %p').lstrip('0')}"
        return f"{day_prefix}{format_scheduler_hour_label(start_time)} - {format_scheduler_hour_label(end_time)}"
    if start_time.strftime("%p") == end_time.strftime("%p"):
        return f"{day_prefix}{start_time.strftime('%I').lstrip('0')}-{end_time.strftime('%I %p').lstrip('0')}"
    return f"{day_prefix}{format_scheduler_hour_label(start_time)} - {format_scheduler_hour_label(end_time)}"


def point_in_routine_hour_window(point, profile):
    hour_window = profile.get("hour_window")
    moment = parse_scheduler_hour_label(point.get("time"))
    if not hour_window or not moment:
        return True

    start_hour, end_hour = hour_window
    return start_hour <= moment.hour < end_hour


def score_routine_hour(point, profile, personalization=None):
    personalization = get_personalization_profile(personalization)
    temperature = apply_temperature_preference(point.get("temperature", 0), personalization)
    rain_chance = point.get("rain_chance", 0)
    wind_speed = point.get("wind", 0)
    humidity = point.get("humidity", 0)
    ideal_low, ideal_high = profile["ideal_temp_range"]
    hard_low, hard_high = profile["hard_temp_range"]
    ideal_midpoint = (ideal_low + ideal_high) / 2

    score = 100.0

    if temperature < ideal_low:
        score -= (ideal_low - temperature) * 4.2
    elif temperature > ideal_high:
        score -= (temperature - ideal_high) * 4.0
    else:
        score += max(0, 8 - abs(temperature - ideal_midpoint) * 1.25)

    if temperature < hard_low:
        score -= 18 + (hard_low - temperature) * 2.8
    elif temperature > hard_high:
        score -= 18 + (temperature - hard_high) * 2.5

    score -= rain_chance * profile["rain_weight"]
    if rain_chance > 50:
        score -= 12 + (rain_chance - 50) * 0.35
    else:
        score += max(0, 6 - rain_chance * 0.12)

    if wind_speed > profile["wind_limit"]:
        score -= 10 + (wind_speed - profile["wind_limit"]) * profile["wind_penalty"]
    else:
        score += max(0, 5 - wind_speed * 0.18)

    if humidity > profile["humidity_limit"]:
        score -= (humidity - profile["humidity_limit"]) * profile["humidity_penalty"]
    else:
        score += max(0, 4 - max(0, humidity - 45) * 0.12)

    if humidity < 30:
        score -= (30 - humidity) * 0.12

    preferred_time_key = personalization.get("preferred_time_key")
    if preferred_time_key and phase_key_for_hourly_point(point) == preferred_time_key:
        score += 6

    return max(0, min(int(round(score)), 100))


def build_routine_block(hour_slice, reference_dt=None):
    if not hour_slice:
        return None

    return {
        "hours": hour_slice,
        "label": format_scheduler_block_label(hour_slice, reference_dt),
        "avg_score": round(sum(hour["score"] for hour in hour_slice) / len(hour_slice)),
        "avg_temp": round(sum(hour["temperature"] for hour in hour_slice) / len(hour_slice), 1),
        "avg_rain": round(sum(hour["rain_chance"] for hour in hour_slice) / len(hour_slice)),
        "avg_wind": round(sum(hour["wind"] for hour in hour_slice) / len(hour_slice), 1),
        "avg_humidity": round(sum(hour["humidity"] for hour in hour_slice) / len(hour_slice)),
        "length": len(hour_slice),
    }


def build_best_routine_blocks(scored_hours, minimum_score, reference_dt=None):
    candidate_blocks = []
    current_block = []

    for hour in scored_hours:
        if hour["score"] >= minimum_score:
            current_block.append(hour)
        elif current_block:
            candidate_blocks.append(build_routine_block(current_block, reference_dt))
            current_block = []

    if current_block:
        candidate_blocks.append(build_routine_block(current_block, reference_dt))

    candidate_blocks = [block for block in candidate_blocks if block]
    candidate_blocks.sort(key=lambda block: (block["avg_score"], block["length"]), reverse=True)
    return candidate_blocks


def build_fallback_routine_block(scored_hours, reference_dt=None):
    if not scored_hours:
        return None
    if len(scored_hours) == 1:
        return build_routine_block([scored_hours[0]], reference_dt)

    best_window = None
    best_window_score = -1
    for index in range(len(scored_hours) - 1):
        window = scored_hours[index : index + 2]
        window_score = sum(hour["score"] for hour in window) / len(window)
        if window_score > best_window_score:
            best_window = window
            best_window_score = window_score

    return build_routine_block(best_window or [max(scored_hours, key=lambda hour: hour["score"])], reference_dt)


def trim_routine_block(block, target_hours, reference_dt=None):
    if not block or target_hours <= 0:
        return block
    hours = block.get("hours", [])
    if len(hours) <= target_hours:
        return block

    best_slice = None
    best_score = -1
    for index in range(len(hours) - target_hours + 1):
        window = hours[index : index + target_hours]
        window_score = sum(hour["score"] for hour in window) / len(window)
        if window_score > best_score:
            best_slice = window
            best_score = window_score

    return build_routine_block(best_slice or hours[:target_hours], reference_dt)


def build_routine_reason_text(block, profile, temp_symbol, speed_symbol, use_fahrenheit):
    reasons = []
    ideal_low, ideal_high = profile["ideal_temp_range"]

    if ideal_low <= block["avg_temp"] <= ideal_high:
        reasons.append("mild temperature")
    elif block["avg_temp"] < ideal_low:
        reasons.append("cooler air")
    else:
        reasons.append("warmer but still manageable air")

    if block["avg_rain"] <= 15:
        reasons.append("low rain risk")
    elif block["avg_rain"] <= 30:
        reasons.append("manageable rain risk")

    if block["avg_wind"] <= 12:
        reasons.append("low wind")
    elif block["avg_wind"] <= profile["wind_limit"]:
        reasons.append("steady breeze")

    if block["avg_humidity"] <= 55:
        reasons.append("lighter humidity")
    elif block["avg_humidity"] <= profile["humidity_limit"]:
        reasons.append("balanced humidity")

    summary = " + ".join(reasons[:3]) or "the most balanced weather window"
    detail = (
        f"Average conditions land near {format_temperature_text(block['avg_temp'], temp_symbol, use_fahrenheit)}, "
        f"{format_wind_text(block['avg_wind'], speed_symbol)}, {block['avg_humidity']}% humidity, "
        f"and {block['avg_rain']}% rain risk."
    )
    return summary, detail


def build_avoid_time_blocks(hourly_points, reference_dt=None):
    flagged_hours = []
    for point in hourly_points:
        reasons = []
        severity = 0
        if point.get("rain_chance", 0) > 50:
            reasons.append("rain peak")
            severity += 20 + (point["rain_chance"] - 50) * 0.6
        if point.get("temperature", 0) > 35:
            reasons.append("heat peak")
            severity += 18 + (point["temperature"] - 35) * 2.2
        if point.get("temperature", 0) < 10:
            reasons.append("cold snap")
            severity += 18 + (10 - point["temperature"]) * 2.0
        if point.get("wind", 0) > 25:
            reasons.append("gusty wind")
            severity += 12 + (point["wind"] - 25) * 1.2
        if reasons:
            flagged_hours.append({**point, "severity": round(severity), "reasons": reasons})

    avoid_blocks = []
    current_block = []
    for hour in hourly_points:
        matching_hour = next((item for item in flagged_hours if item["time"] == hour["time"]), None)
        if matching_hour:
            current_block.append(matching_hour)
        elif current_block:
            avoid_blocks.append(current_block)
            current_block = []

    if current_block:
        avoid_blocks.append(current_block)

    decorated_blocks = []
    for block in avoid_blocks:
        reason_counts = {}
        for hour in block:
            for reason in hour["reasons"]:
                reason_counts[reason] = reason_counts.get(reason, 0) + 1
        dominant_reasons = sorted(reason_counts.items(), key=lambda item: item[1], reverse=True)
        decorated_blocks.append(
            {
                "label": format_scheduler_block_label(block, reference_dt),
                "hours": block,
                "severity": round(sum(hour["severity"] for hour in block) / len(block)),
                "reason_text": " + ".join(reason for reason, _ in dominant_reasons[:2]),
            }
        )

    decorated_blocks.sort(key=lambda block: block["severity"], reverse=True)
    return decorated_blocks[:2]


def build_daily_routine_scheduler(weather_to_show, temp_symbol, speed_symbol, use_fahrenheit, time_context=None, personalization=None):
    time_context = time_context or build_local_time_context(weather_to_show)
    personalization = get_personalization_profile(personalization)
    forecast = weather_to_show.get("forecast") or []
    today = forecast[0] if forecast else {}
    hourly_points = time_context.get("scheduler_points") or today.get("hourly") or []
    if not hourly_points:
        return {}

    schedule_items = []
    summary_items = []
    reference_dt = time_context["reference_now"]

    for profile in ROUTINE_ACTIVITY_PROFILES:
        profile_points = [point for point in hourly_points if point_in_routine_hour_window(point, profile)] or hourly_points
        scored_hours = [{**point, "score": score_routine_hour(point, profile, personalization)} for point in profile_points]
        best_blocks = build_best_routine_blocks(scored_hours, profile["minimum_score"], reference_dt)
        selected_block = best_blocks[0] if best_blocks else build_fallback_routine_block(scored_hours, reference_dt)
        if not selected_block:
            continue
        selected_block = trim_routine_block(selected_block, profile.get("target_block_hours", 0), reference_dt)

        reason_text, detail_text = build_routine_reason_text(
            selected_block,
            profile,
            temp_symbol,
            speed_symbol,
            use_fahrenheit,
        )
        summary_items.append(
            {
                "title": profile["eyebrow"],
                "body": f"{selected_block['label']} works best ({reason_text}).",
            }
        )
        schedule_items.append(
            {
                "eyebrow": profile["eyebrow"],
                "title": selected_block["label"],
                "body": (
                    f"{selected_block['label']} scores best for {profile['label']} because of {reason_text}. "
                    f"{detail_text} This is the next strongest block from {time_context['phase_reference']} onward."
                ),
                "icon": profile["icon"],
            }
        )

    avoid_blocks = build_avoid_time_blocks(hourly_points, reference_dt)
    if avoid_blocks:
        avoid_summary = "; ".join(f"{block['label']} ({block['reason_text']})" for block in avoid_blocks)
        summary_items.append({"title": "Avoid Times", "body": tighten_preview_copy(avoid_summary, max_length=112)})
        avoid_body = "Avoid " + "; ".join(
            f"{block['label']} when {block['reason_text']} takes over"
            for block in avoid_blocks
        ) + "."
    else:
        avoid_body = f"No major heat, rain, or wind spike stands out strongly enough to flag a clear avoid window from {time_context['phase_reference']} forward."
        summary_items.append({"title": "Avoid Times", "body": f"No major avoid window stands out from {time_context['phase_reference']} onward."})

    schedule_items.append(
        {
            "eyebrow": "Avoid Times",
            "title": "Hours to skip if possible",
            "body": avoid_body,
            "icon": "\u26a0\ufe0f",
        }
    )

    focus_title = PERSONAL_ROUTINE_TITLE_MAP.get(personalization.get("activity_focus_key"))
    if focus_title:
        summary_items.sort(key=lambda item: (0 if item.get("title") == focus_title else 2 if item.get("title") == "Avoid Times" else 1))
        schedule_items.sort(key=lambda item: (0 if item.get("eyebrow") == focus_title else 2 if item.get("eyebrow") == "Avoid Times" else 1))

    return {
        "summary_items": summary_items,
        "cards": schedule_items,
    }


def build_activity_recommendations(weather_to_show, temp_symbol, speed_symbol, use_fahrenheit, time_context=None, routine_scheduler=None, personalization=None):
    time_context = time_context or build_local_time_context(weather_to_show)
    routine_scheduler = routine_scheduler or {}
    personalization = get_personalization_profile(personalization)
    current = weather_to_show["current"]
    snapshot = resolve_context_snapshot(weather_to_show, time_context)
    rain_chance = snapshot["rain_chance"]
    scores = calculate_weather_scores(weather_to_show, time_context, personalization)
    current_temp_text = format_temperature_text(snapshot["temperature"], temp_symbol, use_fahrenheit)
    wind_text = format_wind_text(snapshot["wind"], speed_symbol)
    schedule_cards = routine_scheduler.get("cards") or []
    walking_window = next((item for item in schedule_cards if item.get("eyebrow") == "Walking"), None)
    running_window = next((item for item in schedule_cards if item.get("eyebrow") == "Running"), None)
    task_window = next((item for item in schedule_cards if item.get("eyebrow") == "Outdoor Tasks"), None)

    def window_note(card, label="Best window"):
        if not card or not card.get("title"):
            return ""
        return f" {label}: {card['title']}."

    if scores["outdoor"] >= 8:
        walk_title = "Good time for a walk"
        walk_body = (
            f"{time_context['phase_reference'].capitalize()}, {snapshot['condition'].lower()} air near {current_temp_text} with {wind_text} should feel easy for walking."
            f"{window_note(walking_window)}"
        )
    elif scores["outdoor"] >= 5:
        walk_title = "Walking is better with timing"
        walk_body = (
            f"{time_context['phase_reference'].capitalize()}, walking still works, but the weather is less steady."
            f"{window_note(walking_window)}"
        )
    else:
        walk_title = "Walking can wait a bit"
        walk_body = (
            f"Longer walks look less comfortable {time_context['phase_reference']}."
            f"{window_note(walking_window, 'Better window')}"
        )

    if scores["comfort"] >= 8 and scores["outdoor"] >= 7:
        exercise_title = "Outdoor exercise works well"
        exercise_body = (
            f"{time_context['phase_reference'].capitalize()} supports lighter outdoor effort without much friction."
            f"{window_note(running_window, 'Best run window')}"
        )
    elif scores["comfort"] >= 5:
        exercise_title = "Keep exercise light"
        exercise_body = (
            f"{time_context['phase_reference'].capitalize()}, shorter sessions and steadier pacing will feel better."
            f"{window_note(running_window, 'Best run window')}"
        )
    else:
        exercise_title = "Indoor exercise has the edge"
        exercise_body = (
            f"Indoor training is the cleaner call {time_context['phase_reference']}."
            f"{window_note(task_window, 'Cleaner outdoor block')}"
        )

    if scores["outdoor"] <= 5 or rain_chance >= 55 or snapshot["condition"] in {"Thunderstorm", "Snowy"}:
        indoor_title = "Indoor plans look easier"
        indoor_body = f"Use {time_context['phase_reference']} for indoor errands, study time, or cafe stops if you want the steadier option."
    else:
        indoor_title = "Indoor backup can stay light"
        indoor_body = f"You likely will not need an indoor backup {time_context['phase_reference']} unless things shift into {time_context['next_phase_reference']}."

    if scores["travel"] >= 8:
        travel_title = "Travel looks smooth"
        travel_body = f"Errands, short drives, and general movement should feel straightforward {time_context['phase_reference']}."
    elif scores["travel"] >= 5:
        travel_title = "Leave a little extra time"
        travel_body = (
            f"Movement still works {time_context['phase_reference']}, but conditions may slow parts of the route."
        )
    elif snapshot["condition"] == "Foggy":
        travel_title = "Visibility can slow travel"
        travel_body = f"Fog and about {current['visibility']} km visibility can make driving and cycling feel less relaxed {time_context['phase_reference']}."
    else:
        travel_title = "Movement may feel rougher"
        travel_body = f"Short trips are still possible, but rougher weather makes movement less convenient {time_context['phase_reference']}."

    cards = [
        {"item_id": "walking", "eyebrow": "Walking", "title": walk_title, "body": walk_body, "icon": "\U0001f6b6"},
        {"item_id": "running", "eyebrow": "Outdoor Exercise", "title": exercise_title, "body": exercise_body, "icon": "\U0001f3c3"},
        {"item_id": "indoor_backup", "eyebrow": "Indoor Backup", "title": indoor_title, "body": indoor_body, "icon": "\U0001f3e0"},
        {"item_id": "travel", "eyebrow": "Travel / Movement", "title": travel_title, "body": travel_body, "icon": "\U0001f9ed"},
    ]

    focus_key = personalization.get("activity_focus_key")
    if focus_key in {"walking", "running"}:
        cards.sort(key=lambda item: (0 if item.get("item_id") == focus_key else 1))

    return cards


def get_local_highlight_mode(weather_to_show, time_context=None):
    snapshot = resolve_context_snapshot(weather_to_show, time_context)
    condition = str(snapshot.get("condition") or "").strip()
    temperature = float(snapshot.get("temperature", 0) or 0)
    rain_chance = int(round(snapshot.get("rain_chance", 0) or 0))
    rain_total = float(snapshot.get("rain_total", 0) or 0)

    if condition == "Thunderstorm" or rain_chance >= 65 or rain_total >= 1.0:
        return "wet"
    if condition in {"Rainy", "Foggy"} or rain_chance >= 40 or rain_total >= 0.2:
        return "wet"
    if condition == "Snowy" or temperature <= 6:
        return "cold"
    if temperature >= 34:
        return "hot"
    if condition == "Sunny" and rain_chance <= 20 and 12 <= temperature <= 33:
        return "clear"
    return "mixed"


def build_local_highlight_recommendations(weather_to_show, time_context=None):
    location = (weather_to_show or {}).get("location") or {}
    latitude = location.get("latitude")
    longitude = location.get("longitude")
    city_label = weather_to_show.get("resolved_city") or "Selected location"
    mode_key = get_local_highlight_mode(weather_to_show, time_context)
    return get_local_place_recommendations(latitude, longitude, city_label, mode_key=mode_key, max_items=4)


def build_clothing_quick_read(weather_to_show, time_context, temp_symbol, speed_symbol, use_fahrenheit, personalization=None):
    personalization = get_personalization_profile(personalization)
    snapshot = resolve_context_snapshot(weather_to_show, time_context)
    current_temp_text = format_temperature_text(snapshot["temperature"], temp_symbol, use_fahrenheit)
    shift_text = describe_temperature_shift(time_context, temp_symbol, use_fahrenheit)

    extras = []
    if snapshot["rain_chance"] >= 45 or snapshot["rain_total"] >= 0.2:
        extras.append("umbrella")
    if time_context["phase_key"] in {"morning", "afternoon"} and weather_to_show["forecast"][0].get("uv_index", 0) >= 6:
        extras.append("sun protection")
    if snapshot["wind"] >= 25:
        extras.append("a wind-ready outer layer")
    if snapshot["temperature"] <= 10:
        extras.append("a warmer layer")
    extra_text = ", ".join(extras) if extras else "no heavy extras"

    style_note = {
        "casual": "Keep the look relaxed and easy.",
        "sporty": "Keep the look easy to move in.",
        "smart_casual": "Keep the look a little sharper.",
    }.get(personalization["outfit_vibe_key"], "Keep the look easy to adapt.")
    temperature_note = {
        "I run cold": "Since you tend to run cold, lean one layer warmer.",
        "I run warm": "Since you tend to run warm, keep bulk under control.",
    }.get(personalization["temperature_preference"], "")

    return [
        {
            "title": "Wear Right Now",
            "body": f"{time_context['phase_reference'].capitalize()}, dress around {snapshot['condition'].lower()} conditions near {current_temp_text}. {style_note}",
        },
        {
            "title": "What Changes Next",
            "body": f"{time_context['next_phase_reference'].capitalize()}, {shift_text} so your outfit should stay flexible instead of locked to one moment.",
        },
        {
            "title": "Keep Ready",
            "body": f"Carry {extra_text} if you want the outfit to stay useful without a full change later on. {temperature_note}".strip(),
        },
    ]


def build_time_slot_clothing_plan(weather_to_show, time_context, temp_symbol, speed_symbol, use_fahrenheit):
    hourly_entries = collect_hourly_forecast_points(weather_to_show, limit_days=2)
    if not hourly_entries:
        return []

    reference_dt = time_context["reference_now"]
    timeline_reference = reference_dt.replace(minute=0, second=0, microsecond=0)
    timeline_items = []
    for slot in TIME_SLOT_CONFIG:
        matching_entry = next(
            (entry for entry in hourly_entries if entry[0] >= timeline_reference and get_time_phase(entry[0].hour)["key"] == slot["key"]),
            None,
        )
        if not matching_entry:
            matching_entry = next((entry for entry in hourly_entries if get_time_phase(entry[0].hour)["key"] == slot["key"]), None)
        if not matching_entry:
            continue

        slot_dt, slot_point = matching_entry
        relative_day = get_relative_day_label(slot_dt.date(), reference_dt.date())
        if relative_day == "Today":
            if slot["key"] == "night":
                slot_reference = "tonight"
                slot_title = "Tonight"
            else:
                slot_reference = slot["reference"]
                slot_title = slot["label"]
        elif relative_day == "Tomorrow":
            slot_reference = "tomorrow night" if slot["key"] == "night" else f"tomorrow {slot['label'].lower()}"
            slot_title = f"Tomorrow {'Night' if slot['key'] == 'night' else slot['label']}"
        else:
            day_reference = relative_day.lower()
            slot_reference = f"{day_reference} night" if slot["key"] == "night" else f"{day_reference} {slot['label'].lower()}"
            slot_title = f"{relative_day} {'Night' if slot['key'] == 'night' else slot['label']}"
        slot_temp_text = format_temperature_text(slot_point["temperature"], temp_symbol, use_fahrenheit)
        slot_rain = slot_point.get("rain_chance", 0)
        slot_uv = weather_to_show["forecast"][0].get("uv_index", 0) if slot["key"] in {"morning", "afternoon"} else 0

        if slot_point["temperature"] >= 28:
            body = f"{slot_reference.capitalize()} leans hot around {slot_temp_text}, so stay on breathable pieces and reduce bulk."
        elif slot_point["temperature"] >= 18:
            body = f"{slot_reference.capitalize()} stays balanced near {slot_temp_text}, so light layers with full-day flexibility make the most sense."
        elif slot_point["temperature"] >= 10:
            body = f"{slot_reference.capitalize()} cools to about {slot_temp_text}, so a knit, overshirt, or light outer layer starts to matter."
        else:
            body = f"{slot_reference.capitalize()} drops near {slot_temp_text}, so warmer layers and more coverage become the smarter move."

        if slot_rain >= 45:
            body += f" Rain risk is around {slot_rain}%, so keep the look weather-ready."
        elif slot_point.get("wind", 0) >= 25:
            body += f" Wind near {format_wind_text(slot_point['wind'], speed_symbol)} can make lighter pieces feel thinner."
        elif slot_uv >= 6:
            body += f" UV is still high in this block, so sun protection is part of the outfit."

        visual_bundle = get_clothing_visual_bundle_for_conditions(
            slot["visual_slot"],
            slot_point["temperature"],
            slot_rain,
            slot_uv,
            slot_point.get("wind", 0),
            slot_point.get("rain_total", 0),
            slot_point.get("condition", ""),
        )

        timeline_items.append(
            (
                slot_dt,
                {
                    "item_id": f"time-{slot['key']}",
                    "eyebrow": slot["eyebrow"],
                    "title": slot_title,
                    "body": body,
                    "icon": slot["icon"],
                    "visual_profile": visual_bundle["profile_key"],
                    "variants": visual_bundle["variants"],
                    "preferred_variant_index": slot["preferred_variant_index"],
                },
            )
        )

    timeline_items.sort(key=lambda entry: entry[0])
    return [item for _, item in timeline_items]


def build_clothing_recommendations(weather_to_show, temp_symbol, speed_symbol, use_fahrenheit, time_context=None, personalization=None):
    time_context = time_context or build_local_time_context(weather_to_show)
    personalization = get_personalization_profile(personalization)
    current = weather_to_show["current"]
    today = weather_to_show["forecast"][0] if weather_to_show.get("forecast") else {}
    snapshot = resolve_context_snapshot(weather_to_show, time_context)
    current_temp = apply_temperature_preference(snapshot["temperature"], personalization)
    rain_chance = snapshot["rain_chance"]
    uv_index = today.get("uv_index", 0) if time_context["phase_key"] in {"morning", "afternoon"} else 0
    wind_speed = snapshot["wind"]
    precipitation = max(snapshot["rain_total"], current.get("precipitation", 0))
    shift_text = describe_temperature_shift(time_context, temp_symbol, use_fahrenheit)

    if current_temp >= 28:
        tops_body = f"{time_context['phase_reference'].capitalize()}, breathable tees, polos, or airy short sleeves make the most sense. {shift_text.capitalize()} later, so keep the outfit easy to vent."
        bottoms_body = "Shorts or lightweight trousers will feel better than heavy denim while the warmer part of the day still holds."
    elif current_temp >= 18:
        tops_body = f"{time_context['phase_reference'].capitalize()}, a light tee, polo, or breathable long-sleeve top gives enough flexibility. {shift_text.capitalize()} without demanding a full outfit change."
        bottoms_body = "Light jeans, chinos, or relaxed full-length pants should stay comfortable while the day remains balanced."
    elif current_temp >= 10:
        tops_body = f"{time_context['phase_reference'].capitalize()}, a long-sleeve top, knit, or tee with a mid-layer will handle the cooler air better. {shift_text.capitalize()} over the next hours."
        bottoms_body = "Full-length pants are the safer base, especially once the breeze or the later temperature drop becomes more noticeable."
    else:
        tops_body = f"{time_context['phase_reference'].capitalize()}, use a warmer knit, thermal base, or heavier long-sleeve layer to hold heat more effectively."
        bottoms_body = "Heavier pants or lined trousers will feel more balanced than lightweight fabrics while the colder air is active."

    if current_temp < 12 or wind_speed >= 25 or rain_chance >= 45:
        outer_title = f"Outerwear matters {time_context['phase_reference']}"
        outer_body = (
            f"A jacket, shell, or wind-resistant layer will help while wind reaches {format_wind_text(wind_speed, speed_symbol)} "
            f"or showers push rain risk toward {rain_chance}%."
        )
    elif time_context["temp_trend"] == "cooling":
        outer_title = f"Layer for {time_context['next_phase_reference']}"
        outer_body = f"Outerwear can stay light right now, but keep a cardigan, overshirt, or packable layer ready because {shift_text}."
    else:
        outer_title = "Outerwear can stay light"
        outer_body = f"A cardigan, overshirt, or packable layer is enough {time_context['phase_reference']} unless you tend to get cold easily."

    if snapshot["condition"] in {"Rainy", "Snowy"} or precipitation >= 0.2:
        shoes_body = f"Closed shoes with decent grip are the safer choice while surfaces stay damp {time_context['phase_reference']}."
    elif current_temp >= 28 and rain_chance < 20:
        shoes_body = "Breathable sneakers or comfortable sandals work well if you are mostly staying on dry ground."
    else:
        shoes_body = f"Comfortable sneakers or everyday closed shoes are the easiest choice for this {time_context['phase_label'].lower()} block."

    accessory_notes = []
    if uv_index >= 6 or (snapshot["condition"] == "Sunny" and rain_chance < 20 and time_context["phase_key"] in {"morning", "afternoon"}):
        accessory_notes.append("sunglasses or a cap for sun exposure")
    if current_temp < 10 or time_context["phase_key"] == "night":
        accessory_notes.append("a scarf or warmer extra for the cooler air")
    if wind_speed >= 25:
        accessory_notes.append("secure accessories that will not shift in the breeze")
    if not accessory_notes:
        accessory_notes.append("your usual watch, bag, or light extras")

    add_ons = []
    if rain_chance >= 45 or precipitation >= 0.2:
        add_ons.append("Umbrella")
    if uv_index >= 6 or (snapshot["condition"] == "Sunny" and rain_chance < 20 and time_context["phase_key"] in {"morning", "afternoon"}):
        add_ons.append("Sunscreen")
    if wind_speed >= 30:
        add_ons.append("Wind-resistant layer")
    if snapshot["condition"] in {"Rainy", "Snowy"}:
        add_ons.append("Water-resistant bag or cover")
    if not add_ons:
        add_ons.append("No special extras stand out right now")

    tops_visual = get_clothing_visual_bundle_for_conditions("tops", current_temp, rain_chance, uv_index, wind_speed, precipitation, snapshot["condition"])
    bottoms_visual = get_clothing_visual_bundle_for_conditions("bottoms", current_temp, rain_chance, uv_index, wind_speed, precipitation, snapshot["condition"])
    outerwear_visual = get_clothing_visual_bundle_for_conditions("outerwear", current_temp, rain_chance, uv_index, wind_speed, precipitation, snapshot["condition"])
    shoes_visual = get_clothing_visual_bundle_for_conditions("shoes", current_temp, rain_chance, uv_index, wind_speed, precipitation, snapshot["condition"])
    accessories_visual = get_clothing_visual_bundle_for_conditions("accessories", current_temp, rain_chance, uv_index, wind_speed, precipitation, snapshot["condition"])
    add_ons_visual = get_clothing_visual_bundle_for_conditions("weather_add_ons", current_temp, rain_chance, uv_index, wind_speed, precipitation, snapshot["condition"])

    def preferred_index(item_id, variants):
        phase_index = get_base_outfit_variant_index(item_id, time_context["phase_key"])
        return choose_style_preferred_variant_index(variants, phase_index, personalization["outfit_vibe_key"])

    return [
        {
            "item_id": "tops",
            "eyebrow": "Tops",
            "title": f"Top layers for {time_context['phase_reference']}",
            "body": tops_body,
            "icon": "\U0001f455",
            "visual_profile": tops_visual["profile_key"],
            "variants": tops_visual["variants"],
            "preferred_variant_index": preferred_index("tops", tops_visual["variants"]),
        },
        {
            "item_id": "bottoms",
            "eyebrow": "Bottoms",
            "title": "Bottom layers",
            "body": bottoms_body,
            "icon": "\U0001f456",
            "visual_profile": bottoms_visual["profile_key"],
            "variants": bottoms_visual["variants"],
            "preferred_variant_index": preferred_index("bottoms", bottoms_visual["variants"]),
        },
        {
            "item_id": "outerwear",
            "eyebrow": "Outerwear",
            "title": outer_title,
            "body": outer_body,
            "icon": "\U0001f9e5",
            "visual_profile": outerwear_visual["profile_key"],
            "variants": outerwear_visual["variants"],
            "preferred_variant_index": preferred_index("outerwear", outerwear_visual["variants"]),
        },
        {
            "item_id": "shoes",
            "eyebrow": "Shoes",
            "title": "Footwear",
            "body": shoes_body,
            "icon": "\U0001f45f",
            "visual_profile": shoes_visual["profile_key"],
            "variants": shoes_visual["variants"],
            "preferred_variant_index": preferred_index("shoes", shoes_visual["variants"]),
        },
        {
            "item_id": "accessories",
            "eyebrow": "Accessories",
            "title": "Accessory guidance",
            "body": f"Add {', '.join(accessory_notes)} to round out the outfit without overpacking.",
            "icon": "\U0001f9e2",
            "visual_profile": accessories_visual["profile_key"],
            "variants": accessories_visual["variants"],
            "preferred_variant_index": preferred_index("accessories", accessories_visual["variants"]),
        },
        {
            "item_id": "weather-add-ons",
            "eyebrow": "Weather Add-Ons",
            "title": "Extra gear",
            "body": ", ".join(add_ons) + ".",
            "icon": "\u2602\ufe0f",
            "visual_profile": add_ons_visual["profile_key"],
            "variants": add_ons_visual["variants"],
            "preferred_variant_index": preferred_index("weather-add-ons", add_ons_visual["variants"]),
        },
    ]


def build_weather_intelligence_payload(weather_to_show, city_to_show, temp_symbol, speed_symbol, use_fahrenheit):
    current = weather_to_show["current"]
    today = weather_to_show["forecast"][0] if weather_to_show.get("forecast") else {}
    condition_display = get_current_condition_display(weather_to_show)
    time_context = build_local_time_context(weather_to_show)
    personalization = get_personalization_profile()
    routine_scheduler = build_daily_routine_scheduler(
        weather_to_show,
        temp_symbol,
        speed_symbol,
        use_fahrenheit,
        time_context,
        personalization,
    )
    clothing_cards = build_clothing_recommendations(
        weather_to_show,
        temp_symbol,
        speed_symbol,
        use_fahrenheit,
        time_context,
        personalization,
    )

    return {
        "city": city_to_show or weather_to_show.get("resolved_city") or "Selected location",
        "condition": condition_display["label"],
        "condition_icon": condition_display["icon"],
        "raw_condition": current["condition"],
        "time_context": {
            "phase_label": time_context["phase_label"],
            "phase_reference": time_context["phase_reference"],
            "next_phase_reference": time_context["next_phase_reference"],
            "local_time_label": time_context["local_time_label"],
            "local_day_label": time_context["local_day_label"],
            "time_note": (
                f"It is {time_context['local_time_label']} on {time_context['local_day_label']} there, "
                f"so guidance is weighted toward {time_context['phase_reference']} instead of a generic all-day read."
            ),
        },
        "personalization": personalization,
        "hero_stats": [
            {"label": "Current", "value": format_temperature_text(current["temperature"], temp_symbol, use_fahrenheit)},
            {"label": "Feels Like", "value": format_temperature_text(current["feels_like"], temp_symbol, use_fahrenheit)},
            {"label": "Rain Chance", "value": f"{today.get('rain_chance', 0)}%"},
            {"label": "Wind", "value": format_wind_text(current["wind"], speed_symbol)},
        ],
        "scores": build_weather_score_cards(weather_to_show, time_context, personalization),
        "alerts": build_weather_alerts(weather_to_show, temp_symbol, speed_symbol, use_fahrenheit, time_context, personalization),
        "insights": build_smart_weather_insights(weather_to_show, temp_symbol, speed_symbol, use_fahrenheit, time_context),
        "routine_scheduler": routine_scheduler,
        "activities": build_activity_recommendations(weather_to_show, temp_symbol, speed_symbol, use_fahrenheit, time_context, routine_scheduler, personalization),
        "local_highlights": build_local_highlight_recommendations(weather_to_show, time_context),
        "clothing": clothing_cards,
        "clothing_quick_read": build_clothing_quick_read(weather_to_show, time_context, temp_symbol, speed_symbol, use_fahrenheit, personalization),
        "clothing_timeline": build_time_slot_clothing_plan(weather_to_show, time_context, temp_symbol, speed_symbol, use_fahrenheit),
    }


def normalize_recent_searches(entries):
    normalized = []
    seen_labels = set()
    for entry in entries or []:
        if not isinstance(entry, dict):
            continue
        label = str(entry.get("label") or "").strip()
        if not label:
            continue
        label_key = label.lower()
        if label_key in seen_labels:
            continue
        seen_labels.add(label_key)
        normalized.append(
            {
                "label": label,
                "query": str(entry.get("query") or label).strip(),
                "latitude": entry.get("latitude"),
                "longitude": entry.get("longitude"),
                "meta": str(entry.get("meta") or "Recent search"),
            }
        )
    return normalized[:8]


def build_location_search_entry(label, query=None, latitude=None, longitude=None, meta="Suggested location"):
    resolved_label = str(label or query or "").strip()
    if not resolved_label:
        return None

    resolved_query = str(query or resolved_label).strip() or resolved_label
    return {
        "label": resolved_label,
        "query": resolved_query,
        "latitude": latitude,
        "longitude": longitude,
        "meta": str(meta or "Suggested location"),
    }


def build_weather_search_entry(weather, meta="Current city"):
    if not weather:
        return None

    location = weather.get("location") or {}
    return build_location_search_entry(
        weather.get("resolved_city") or "Selected location",
        query=weather.get("resolved_city") or "Selected location",
        latitude=location.get("latitude"),
        longitude=location.get("longitude"),
        meta=meta,
    )


def get_search_component_recent_entries():
    current_entry = build_weather_search_entry(
        st.session_state.get("last_weather"),
        meta="Recent search",
    )
    recent_entries = st.session_state.get("recent_searches", [])
    if current_entry:
        return normalize_recent_searches([current_entry, *recent_entries])
    return normalize_recent_searches(recent_entries)


def remember_recent_search(weather):
    if not weather:
        return

    recent_entry = build_weather_search_entry(weather, meta="Recent search")
    if not recent_entry:
        return

    existing = [item for item in st.session_state.get("recent_searches", []) if item.get("label", "").lower() != recent_entry["label"].lower()]
    st.session_state["recent_searches"] = normalize_recent_searches([recent_entry, *existing])
    save_user_preferences(
        {
            "recent_searches": st.session_state["recent_searches"],
            "last_selected_city": weather.get("resolved_city"),
        }
    )


def build_preferences_payload(prompt_status=None, remind_after=None):
    return {
        "temp_unit": st.session_state.get("temp_unit", TEMP_OPTIONS[0]),
        "speed_unit": st.session_state.get("speed_unit", SPEED_OPTIONS[0]),
        "weather_map_layer": st.session_state.get("weather_map_layer", MAP_LAYER_OPTIONS[0]),
        "last_selected_city": st.session_state.get("last_city_display") or st.session_state.get("search_query") or "Dubai",
        "recent_searches": st.session_state.get("recent_searches", []),
        "personal_activity_focus": st.session_state.get("personal_activity_focus", PERSONAL_ACTIVITY_OPTIONS[0]),
        "personal_preferred_time": st.session_state.get("personal_preferred_time", PERSONAL_TIME_OPTIONS[0]),
        "personal_temperature_preference": st.session_state.get("personal_temperature_preference", PERSONAL_TEMPERATURE_OPTIONS[0]),
        "personal_outfit_vibe": st.session_state.get("personal_outfit_vibe", PERSONAL_OUTFIT_OPTIONS[0]),
        "personalization_prompt_status": prompt_status if prompt_status is not None else st.session_state.get("personalization_prompt_status", PERSONALIZATION_PROMPT_PENDING),
        "personalization_remind_after": remind_after if remind_after is not None else st.session_state.get("personalization_remind_after", ""),
    }


def sync_settings_draft_state():
    st.session_state["settings_temp_unit_choice"] = st.session_state.get("temp_unit", TEMP_OPTIONS[0])
    st.session_state["settings_speed_unit_choice"] = st.session_state.get("speed_unit", SPEED_OPTIONS[0])
    st.session_state["settings_map_layer_choice"] = st.session_state.get("weather_map_layer", MAP_LAYER_OPTIONS[0])
    sync_personalization_draft_state("settings")


def render_personalization_controls(key_prefix):
    top_row = st.columns(2)
    with top_row[0]:
        st.selectbox(
            "Main activity focus",
            PERSONAL_ACTIVITY_OPTIONS,
            key=f"{key_prefix}_activity_focus_choice",
            help="This shifts which time blocks and guidance the app puts first.",
        )
    with top_row[1]:
        st.selectbox(
            "Best time of day",
            PERSONAL_TIME_OPTIONS,
            key=f"{key_prefix}_preferred_time_choice",
            help="This gives the scheduler a gentle push toward the hours you usually care about most.",
        )

    lower_row = st.columns(2)
    with lower_row[0]:
        st.selectbox(
            "Temperature preference",
            PERSONAL_TEMPERATURE_OPTIONS,
            key=f"{key_prefix}_temperature_preference_choice",
            help="Use this if you usually feel colder or warmer than other people in the same weather.",
        )
    with lower_row[1]:
        st.selectbox(
            "Outfit vibe",
            PERSONAL_OUTFIT_OPTIONS,
            key=f"{key_prefix}_outfit_vibe_choice",
            help="This nudges the base outfit visuals toward a more casual, sporty, or sharper direction.",
        )


def save_personalization_choices(key_prefix, prompt_status=PERSONALIZATION_PROMPT_SAVED, remind_after=""):
    apply_personalization_draft_state(key_prefix)
    st.session_state["personalization_prompt_status"] = prompt_status
    st.session_state["personalization_remind_after"] = remind_after
    save_user_preferences(build_preferences_payload(prompt_status=prompt_status, remind_after=remind_after))


def render_personalization_panel():
    inject_dialog_surface("skyline-personalization-dialog-anchor", "min(86vw, 840px)")
    st.markdown("**Make Skyline Forecast feel more like your app**")
    st.caption(
        "A few quick choices help activity timing, clothing guidance, and summary cards lean toward the way you actually plan your day. "
        "These preferences are saved locally on this device."
    )
    render_personalization_controls("personalization")
    st.caption("You can change these anytime from the settings gear.")

    action_columns = st.columns(3)
    with action_columns[0]:
        if st.button("Save Personalization", key="save_personalization_button", type="primary", use_container_width=True):
            save_personalization_choices("personalization", PERSONALIZATION_PROMPT_SAVED, "")
            st.success("Personalization saved.")
            st.rerun()
    with action_columns[1]:
        if st.button("Remind Me Later", key="remind_personalization_button", type="secondary", use_container_width=True):
            remind_after = (date.today() + timedelta(days=1)).isoformat()
            st.session_state["personalization_prompt_status"] = PERSONALIZATION_PROMPT_LATER
            st.session_state["personalization_remind_after"] = remind_after
            save_user_preferences(build_preferences_payload(prompt_status=PERSONALIZATION_PROMPT_LATER, remind_after=remind_after))
            st.rerun()
    with action_columns[2]:
        if st.button("Never Show Again", key="hide_personalization_button", type="secondary", use_container_width=True):
            st.session_state["personalization_prompt_status"] = PERSONALIZATION_PROMPT_HIDDEN
            st.session_state["personalization_remind_after"] = ""
            save_user_preferences(build_preferences_payload(prompt_status=PERSONALIZATION_PROMPT_HIDDEN, remind_after=""))
            st.rerun()


def sanitize_export_filename(value):
    normalized = unicodedata.normalize("NFKD", str(value)).encode("ascii", "ignore").decode("ascii")
    cleaned = "".join(char if char.isalnum() else "_" for char in normalized)
    cleaned = "_".join(part for part in cleaned.split("_") if part)
    return cleaned.lower() or "location"


def get_export_picker_bounds():
    today = date.today()
    return (
        today - timedelta(days=EXPORT_PAST_LOOKBACK_LIMIT_DAYS),
        today + timedelta(days=EXPORT_FUTURE_LOOKAHEAD_LIMIT_DAYS),
    )


def get_default_export_custom_dates():
    today = date.today()
    end_date = min(today + timedelta(days=6), today + timedelta(days=EXPORT_FUTURE_LOOKAHEAD_LIMIT_DAYS))
    return today, end_date


def normalize_export_custom_dates(custom_dates):
    default_start, default_end = get_default_export_custom_dates()
    if isinstance(custom_dates, (tuple, list)):
        if len(custom_dates) >= 2:
            return custom_dates[0], custom_dates[1]
        if len(custom_dates) == 1:
            return custom_dates[0], custom_dates[0]
    if hasattr(custom_dates, "year"):
        return custom_dates, custom_dates
    return default_start, default_end


def resolve_export_window(range_key, custom_dates=None):
    today = date.today()
    preset_windows = {
        "today": (0, 0),
        "next_3_days": (0, 2),
        "next_7_days": (0, 6),
        "next_10_days": (0, 9),
        "past_3_days": (-2, 0),
        "past_7_days": (-6, 0),
        "past_10_days": (-9, 0),
    }
    option_key, option_label = get_export_range_option(range_key)

    if option_key != "custom_range":
        start_offset, end_offset = preset_windows.get(option_key, (0, 0))
        start_date = today + timedelta(days=start_offset)
        end_date = today + timedelta(days=end_offset)
        return {
            "key": option_key,
            "label": option_label,
            "filename_tag": option_key,
            "start_date": start_date,
            "end_date": end_date,
            "days_count": (end_date - start_date).days + 1,
        }

    start_date, end_date = normalize_export_custom_dates(custom_dates)
    if start_date > end_date:
        start_date, end_date = end_date, start_date

    min_date, max_date = get_export_picker_bounds()
    if start_date < min_date or end_date > max_date:
        raise ValueError(
            f"Choose dates between {min_date.strftime('%b %d')} and {max_date.strftime('%b %d')}."
        )

    selected_days = (end_date - start_date).days + 1
    if selected_days > EXPORT_MAX_SELECTED_DAYS:
        raise ValueError(f"Choose a date window of {EXPORT_MAX_SELECTED_DAYS} days or fewer.")

    return {
        "key": option_key,
        "label": f"{start_date.strftime('%b %d, %Y')} to {end_date.strftime('%b %d, %Y')}",
        "filename_tag": f"{start_date.isoformat()}_to_{end_date.isoformat()}",
        "start_date": start_date,
        "end_date": end_date,
        "days_count": selected_days,
    }


def load_export_window_rows(weather_to_show, window_config):
    location = weather_to_show.get("location") or {}
    latitude = location.get("latitude")
    longitude = location.get("longitude")
    if latitude is None or longitude is None:
        raise WeatherError("Location data is missing for this export.")

    return get_daily_weather_range(
        latitude,
        longitude,
        window_config["start_date"],
        window_config["end_date"],
        location.get("timezone") or "auto",
    )


def build_export_bundle(
    weather_to_show,
    city_to_show,
    temp_symbol,
    speed_symbol,
    use_fahrenheit,
    intelligence_payload,
    range_key,
    range_label,
    export_rows,
):
    current = weather_to_show["current"]
    city_name = city_to_show or weather_to_show.get("resolved_city") or "Selected location"
    primary_insight = (intelligence_payload.get("insights") or [{}])[0]

    return {
        "city": city_name,
        "range_key": range_key,
        "range_label": range_label,
        "days_count": len(export_rows),
        "generated_at": datetime.now().strftime("%b %d, %Y %I:%M %p"),
        "temperature_unit": temp_symbol.strip(),
        "wind_unit": speed_symbol,
        "current": {
            "Condition": current["condition"],
            "Temperature": format_temperature_text(current["temperature"], temp_symbol, use_fahrenheit),
            "Feels Like": format_temperature_text(current["feels_like"], temp_symbol, use_fahrenheit),
            "Humidity": f'{current["humidity"]}%',
            "Wind": format_wind_text(current["wind"], speed_symbol),
            "Pressure": f'{current["pressure"]} hPa',
            "Visibility": f'{current["visibility"]} km',
            "Precipitation": format_precipitation(current["precipitation"]),
        },
        "primary_insight": {
            "title": primary_insight.get("title", "Today's weather summary"),
            "body": primary_insight.get("body", "Current conditions are available for export."),
        },
        "alerts": intelligence_payload.get("alerts", []),
        "scores": intelligence_payload.get("scores", []),
        "forecast_rows": [
            {
                "Date": day["date"],
                "Day": day["day"],
                "Condition": day["condition"],
                "Low": format_temperature_text(day["min"], temp_symbol, use_fahrenheit),
                "High": format_temperature_text(day["max"], temp_symbol, use_fahrenheit),
                "Rain Chance": f'{day["rain_chance"]}%',
                "Rain Total": format_precipitation(day["rain_total"]),
                "UV Index": str(day["uv_index"]),
                "Sunrise": day["sunrise"],
                "Sunset": day["sunset"],
            }
            for day in export_rows
        ],
    }


def build_data_uri(file_bytes, mime_type):
    encoded = base64.b64encode(file_bytes).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def format_file_size(byte_count):
    if byte_count < 1024:
        return f"{byte_count} B"
    if byte_count < 1024 * 1024:
        return f"{round(byte_count / 1024, 1)} KB"
    return f"{round(byte_count / (1024 * 1024), 1)} MB"


def build_export_panel_payload(weather_to_show, city_to_show, temp_symbol, speed_symbol, use_fahrenheit):
    intelligence_payload = build_weather_intelligence_payload(
        weather_to_show,
        city_to_show,
        temp_symbol,
        speed_symbol,
        use_fahrenheit,
    )
    safe_city = sanitize_export_filename(city_to_show or weather_to_show.get("resolved_city") or "selected_location")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    range_items = []

    for range_key, range_label in EXPORT_RANGE_OPTIONS:
        window_config = resolve_export_window(range_key, get_default_export_custom_dates())
        export_rows = load_export_window_rows(weather_to_show, window_config)
        bundle = build_export_bundle(
            weather_to_show,
            city_to_show,
            temp_symbol,
            speed_symbol,
            use_fahrenheit,
            intelligence_payload,
            range_key,
            window_config["label"],
            export_rows,
        )
        csv_bytes = build_csv_export(bundle)
        excel_bytes = build_excel_export(bundle)
        pdf_bytes = build_pdf_export(bundle)

        file_prefix = f"skyline_forecast_{safe_city}_{window_config['filename_tag']}_{timestamp}"
        range_items.append(
            {
                "key": range_key,
                "label": window_config["label"],
                "summary": f'Selected weather window with {bundle["days_count"]} daily row{"s" if bundle["days_count"] != 1 else ""}.',
                "files": [
                    {
                        "label": "CSV",
                        "description": "Structured report sections for spreadsheets and quick imports.",
                        "filename": f"{file_prefix}.csv",
                        "href": build_data_uri(csv_bytes, "text/csv"),
                        "size": format_file_size(len(csv_bytes)),
                    },
                    {
                        "label": "Excel",
                        "description": "Styled workbook with Overview and Forecast sheets.",
                        "filename": f"{file_prefix}.xlsx",
                        "href": build_data_uri(
                            excel_bytes,
                            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        ),
                        "size": format_file_size(len(excel_bytes)),
                    },
                    {
                        "label": "PDF",
                        "description": "Presentation-ready report with summary blocks and a forecast table.",
                        "filename": f"{file_prefix}.pdf",
                        "href": build_data_uri(pdf_bytes, "application/pdf"),
                        "size": format_file_size(len(pdf_bytes)),
                    },
                ],
            }
        )

    return {
        "city": city_to_show or weather_to_show.get("resolved_city") or "Selected location",
        "temperature_unit": temp_symbol.strip(),
        "wind_unit": speed_symbol,
        "ranges": range_items,
    }


def get_export_range_option(range_key):
    for option_key, label in EXPORT_RANGE_OPTIONS:
        if option_key == range_key:
            return option_key, label
    return EXPORT_RANGE_OPTIONS[0]


def get_export_format_option(format_key):
    for option_key, label in EXPORT_FORMAT_OPTIONS:
        if option_key == format_key:
            return option_key, label
    return EXPORT_FORMAT_OPTIONS[0]


def build_export_download_artifact(
    weather_to_show,
    city_to_show,
    temp_symbol,
    speed_symbol,
    use_fahrenheit,
    range_key,
    format_key,
    custom_dates=None,
):
    window_config = resolve_export_window(range_key, custom_dates)
    format_key, format_label = get_export_format_option(format_key)
    intelligence_payload = build_weather_intelligence_payload(
        weather_to_show,
        city_to_show,
        temp_symbol,
        speed_symbol,
        use_fahrenheit,
    )
    export_rows = load_export_window_rows(weather_to_show, window_config)
    bundle = build_export_bundle(
        weather_to_show,
        city_to_show,
        temp_symbol,
        speed_symbol,
        use_fahrenheit,
        intelligence_payload,
        window_config["key"],
        window_config["label"],
        export_rows,
    )
    safe_city = sanitize_export_filename(city_to_show or weather_to_show.get("resolved_city") or "selected_location")
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename_root = f"skyline_forecast_{safe_city}_{window_config['filename_tag']}_{timestamp}"

    if format_key == "csv":
        return {
            "format_label": format_label,
            "filename": f"{filename_root}.csv",
            "mime": "text/csv",
            "description": f'Daily weather rows for {window_config["label"].lower()}.',
            "bytes": build_csv_export(bundle),
            "bundle": bundle,
        }
    if format_key == "excel":
        return {
            "format_label": format_label,
            "filename": f"{filename_root}.xlsx",
            "mime": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "description": f'Styled workbook for {window_config["label"].lower()}.',
            "bytes": build_excel_export(bundle),
            "bundle": bundle,
        }
    return {
        "format_label": format_label,
        "filename": f"{filename_root}.pdf",
        "mime": "application/pdf",
        "description": f'Presentation-ready export for {window_config["label"].lower()}.',
        "bytes": build_pdf_export(bundle),
        "bundle": bundle,
    }


def get_trip_planner_picker_bounds():
    today = date.today()
    return today, today + timedelta(days=EXPORT_FUTURE_LOOKAHEAD_LIMIT_DAYS)


def get_default_trip_planner_dates():
    min_date, max_date = get_trip_planner_picker_bounds()
    default_start = min(min_date + timedelta(days=1), max_date)
    default_end = min(default_start + timedelta(days=2), max_date)
    return default_start, default_end


def describe_trip_temperature_band(avg_temp):
    if avg_temp >= 30:
        return "hot"
    if avg_temp >= 23:
        return "warm"
    if avg_temp >= 15:
        return "mild"
    if avg_temp >= 8:
        return "cool"
    return "cold"


def describe_trip_rain_profile(avg_rain_chance, wet_days, days_count):
    if avg_rain_chance >= 60 or wet_days * 2 >= days_count:
        return "consistently wet"
    if avg_rain_chance >= 35 or wet_days >= 1:
        return "mixed with some rain risk"
    return "mostly dry"


def describe_trip_wind_profile(avg_wind_speed, peak_gust):
    if avg_wind_speed >= 28 or peak_gust >= 42:
        return "quite windy"
    if avg_wind_speed >= 18 or peak_gust >= 30:
        return "noticeably breezy"
    return "fairly calm"


def build_trip_uv_sentence(has_uv_data, avg_uv, peak_uv):
    if not has_uv_data:
        return "UV data is limited for this range."
    if peak_uv >= 8:
        return f"UV peaks around {peak_uv}, so midday sun protection matters."
    if peak_uv >= 6:
        return f"UV stays moderate to high, averaging about {avg_uv} across the trip."
    return f"UV remains on the lighter side with a peak near {peak_uv}."


def compute_trip_planner_day_score(day):
    midpoint = (day.get("min", 0) + day.get("max", 0)) / 2
    rain_chance = day.get("rain_chance", 0)
    wind_speed = day.get("wind_speed", 0) or 0
    condition = day.get("condition") or "Cloudy"

    score = 10.0
    score -= max(0, midpoint - 30) * 0.22
    score -= max(0, 12 - midpoint) * 0.34
    score -= min(rain_chance, 100) * 0.03
    score -= max(0, wind_speed - 18) * 0.08

    if condition == "Thunderstorm":
        score -= 3.2
    elif condition in {"Snowy", "Rainy"}:
        score -= 1.4

    return clamp_score(score)


def build_trip_planner_analysis(city_name, forecast_rows, temp_symbol, speed_symbol, use_fahrenheit):
    days_count = len(forecast_rows)
    start_date = datetime.strptime(forecast_rows[0]["date"], "%Y-%m-%d").date()
    end_date = datetime.strptime(forecast_rows[-1]["date"], "%Y-%m-%d").date()

    daily_midpoints = [(day["min"] + day["max"]) / 2 for day in forecast_rows]
    avg_temp = round(sum(daily_midpoints) / days_count, 1)
    trip_low = min(day["min"] for day in forecast_rows)
    trip_high = max(day["max"] for day in forecast_rows)

    rain_chances = [day.get("rain_chance", 0) for day in forecast_rows]
    avg_rain_chance = round(sum(rain_chances) / days_count, 1)
    wet_days = sum(1 for chance in rain_chances if chance >= 40)
    peak_rain_chance = max(rain_chances)

    wind_speeds = [float(day.get("wind_speed", 0) or 0) for day in forecast_rows]
    gust_values = [max(float(day.get("wind_gust", 0) or 0), wind) for day, wind in zip(forecast_rows, wind_speeds)]
    avg_wind_speed = round(sum(wind_speeds) / days_count, 1)
    peak_gust = round(max(gust_values), 1)

    uv_candidates = [float(day.get("uv_index", 0) or 0) for day in forecast_rows]
    has_uv_data = any(value > 0 for value in uv_candidates)
    avg_uv = round(sum(uv_candidates) / len(uv_candidates), 1) if has_uv_data else None
    peak_uv = round(max(uv_candidates), 1) if has_uv_data else None

    condition_counts = {}
    for day in forecast_rows:
        condition = day.get("condition") or "Cloudy"
        condition_counts[condition] = condition_counts.get(condition, 0) + 1
    dominant_condition, dominant_condition_count = max(condition_counts.items(), key=lambda item: item[1])
    if dominant_condition_count * 2 >= days_count:
        condition_summary = f"mostly {dominant_condition.lower()} conditions"
    else:
        condition_summary = "a mixed set of conditions"

    day_scores = [{"day": day, "score": compute_trip_planner_day_score(day)} for day in forecast_rows]
    best_day_entry = max(day_scores, key=lambda item: item["score"])
    caution_day_entry = min(day_scores, key=lambda item: item["score"])
    best_day = best_day_entry["day"]
    caution_day = caution_day_entry["day"]

    range_delta = format_temperature_delta(trip_high - trip_low, use_fahrenheit)
    temp_descriptor = describe_trip_temperature_band(avg_temp)
    rain_descriptor = describe_trip_rain_profile(avg_rain_chance, wet_days, days_count)
    wind_descriptor = describe_trip_wind_profile(avg_wind_speed, peak_gust)
    uv_sentence = build_trip_uv_sentence(has_uv_data, avg_uv, peak_uv)

    avg_temp_text = format_temperature_text(avg_temp, temp_symbol, use_fahrenheit)
    trip_low_text = format_temperature_text(trip_low, temp_symbol, use_fahrenheit)
    trip_high_text = format_temperature_text(trip_high, temp_symbol, use_fahrenheit)

    overview_notes = [
        {
            "label": "Trip Window",
            "title": f"{days_count} day{'s' if days_count != 1 else ''}",
            "body": f"{start_date.strftime('%b %d, %Y')} to {end_date.strftime('%b %d, %Y')}",
        },
        {
            "label": "Average Temp",
            "title": avg_temp_text,
            "body": "Calculated from each day's midpoint across the full trip.",
        },
        {
            "label": "Min / Max",
            "title": f"{trip_low_text} to {trip_high_text}",
            "body": f"Overall temperature span is {range_delta}{temp_symbol}.",
        },
        {
            "label": "Rain Probability",
            "title": f"Avg {avg_rain_chance}%",
            "body": f"{wet_days} of {days_count} day{'s' if days_count != 1 else ''} reach at least 40% rain risk. Peak {peak_rain_chance}%.",
        },
        {
            "label": "Wind Conditions",
            "title": format_wind_text(avg_wind_speed, speed_symbol),
            "body": f"Peak gust reaches {format_wind_text(peak_gust, speed_symbol)}.",
        },
        {
            "label": "UV Index",
            "title": f"Peak {peak_uv}" if has_uv_data else "Unavailable",
            "body": f"Average daily UV max is {avg_uv}." if has_uv_data else "The selected range did not return usable UV values.",
        },
    ]

    packing_items = []
    if avg_temp >= 28:
        base_title = "Pack light and breathable layers"
        base_body = "Short-sleeve tops, lighter trousers, and airy fabrics will handle the warmer range more comfortably."
    elif avg_temp >= 18:
        base_title = "Pack flexible everyday layers"
        base_body = "T-shirts, light long sleeves, and easy layering pieces should cover most of the trip without overpacking."
    elif avg_temp >= 10:
        base_title = "Plan for cooler layers"
        base_body = "A mix of tees, knitwear, and a light mid-layer will handle the cooler portions of the range better."
    else:
        base_title = "Pack warmer layers"
        base_body = "Thermals, heavier tops, and insulating basics will matter more than lightweight pieces on this trip."
    packing_items.append({"eyebrow": "Core Layers", "title": base_title, "body": base_body, "icon": "\U0001f455"})

    if trip_low < 14 or (trip_high - trip_low) >= 10 or avg_wind_speed >= 18:
        outer_title = "Keep a light outer layer ready"
        outer_body = "A jacket, overshirt, or wind-resistant shell will help with cooler starts, late hours, or breezier stretches."
    else:
        outer_title = "Heavy outerwear is unlikely"
        outer_body = "A very light extra layer should be enough unless you usually run cold."
    packing_items.append({"eyebrow": "Outer Layer", "title": outer_title, "body": outer_body, "icon": "\U0001f9e5"})

    if wet_days >= 2 or peak_rain_chance >= 55:
        rain_title = "Rain gear is worth packing"
        rain_body = "A compact umbrella or water-resistant layer makes sense because multiple days carry meaningful rain risk."
    elif wet_days == 1 or avg_rain_chance >= 25:
        rain_title = "Pack a compact rain backup"
        rain_body = "Rain does not dominate the trip, but one wetter day is enough to justify a small umbrella or shell."
    else:
        rain_title = "Rain extras can stay minimal"
        rain_body = "The trip trends mostly dry, so rain protection can stay light unless your plans depend on being outdoors for long periods."
    packing_items.append({"eyebrow": "Rain Plan", "title": rain_title, "body": rain_body, "icon": "\u2602\ufe0f"})

    if has_uv_data and peak_uv >= 8:
        sun_title = "Sun protection is essential"
        sun_body = "Pack sunscreen, sunglasses, and a cap because the strongest UV periods will hit hard during clearer midday hours."
    elif has_uv_data and peak_uv >= 6:
        sun_title = "Keep sun coverage handy"
        sun_body = "Basic sun protection will be useful on the brighter days, especially if you expect longer outdoor time."
    else:
        sun_title = "Sun exposure stays manageable"
        sun_body = "Standard daily coverage should be enough unless your plans keep you outside for extended periods."
    packing_items.append({"eyebrow": "Sun Protection", "title": sun_title, "body": sun_body, "icon": "\U0001f9f4"})

    if wet_days >= 1 or peak_rain_chance >= 45:
        shoes_title = "Choose shoes that handle mixed ground"
        shoes_body = "Closed shoes with reasonable grip will be easier to live with if pavements or paths turn slick."
    else:
        shoes_title = "Comfortable walking shoes should be enough"
        shoes_body = "You can prioritize comfort and lighter footwear because the trip does not lean heavily toward wet conditions."
    packing_items.append({"eyebrow": "Footwear", "title": shoes_title, "body": shoes_body, "icon": "\U0001f45f"})

    best_day_label = datetime.strptime(best_day["date"], "%Y-%m-%d").strftime("%a, %b %d")
    caution_day_label = datetime.strptime(caution_day["date"], "%Y-%m-%d").strftime("%a, %b %d")
    activity_body = (
        f"{best_day_label} looks strongest for longer outdoor plans with {best_day['rain_chance']}% rain risk and "
        f"{format_wind_text(best_day.get('wind_speed', 0), speed_symbol)} wind."
    )
    if days_count > 1 and caution_day["date"] != best_day["date"] and caution_day_entry["score"] <= 6:
        activity_body += f" {caution_day_label} is the rougher day, so keep indoor backups or lighter plans there."
    packing_items.append({"eyebrow": "Trip Rhythm", "title": "Use the smoother days for outdoor plans", "body": activity_body, "icon": "\U0001f5d3\ufe0f"})

    daily_cards = []
    for day in forecast_rows:
        date_label = datetime.strptime(day["date"], "%Y-%m-%d").strftime("%b %d, %Y")
        daily_parts = [
            f"Low {format_temperature_text(day['min'], temp_symbol, use_fahrenheit)}",
            f"High {format_temperature_text(day['max'], temp_symbol, use_fahrenheit)}",
            f"Rain {day.get('rain_chance', 0)}%",
            f"Wind {format_wind_text(day.get('wind_speed', 0), speed_symbol)}",
        ]
        if (day.get("uv_index", 0) or 0) > 0:
            daily_parts.append(f"UV {day['uv_index']}")

        daily_cards.append(
            {
                "eyebrow": date_label,
                "title": f"{day['day']} - {day['condition']}",
                "body": " | ".join(daily_parts),
                "icon": get_condition_icon(day["condition"]),
            }
        )

    return {
        "city": city_name,
        "days_count": days_count,
        "date_range_label": f"{start_date.strftime('%b %d, %Y')} to {end_date.strftime('%b %d, %Y')}",
        "overview_title": f"{days_count}-day trip outlook",
        "overview_body": (
            f"{city_name} looks {temp_descriptor} overall from {start_date.strftime('%b %d, %Y')} to {end_date.strftime('%b %d, %Y')}, "
            f"with {condition_summary} and a range from {trip_low_text} to {trip_high_text}. "
            f"Rain stays {rain_descriptor}, winds look {wind_descriptor}, and {uv_sentence}"
        ),
        "overview_notes": overview_notes,
        "packing_items": packing_items,
        "daily_cards": daily_cards,
        "best_day_label": best_day_label,
        "best_day_condition": best_day.get("condition") or "",
        "best_day_rain_chance": best_day.get("rain_chance", 0),
        "caution_day_label": caution_day_label,
        "caution_day_condition": caution_day.get("condition") or "",
        "caution_day_rain_chance": caution_day.get("rain_chance", 0),
    }


def clamp_trip_map_point(value, minimum=0.12, maximum=0.88):
    return max(minimum, min(value, maximum))


def build_trip_plan_map_points(origin_weather, destination_weather, trip_analysis):
    origin_city = (origin_weather or {}).get("resolved_city") or ""
    destination_city = destination_weather.get("resolved_city") or trip_analysis.get("city") or "Destination"

    if origin_city:
        origin_point = {"kind": "origin", "label": "Start", "subtitle": origin_city.split(",")[0].strip(), "x": 0.18, "y": 0.68}
        destination_point = {
            "kind": "destination",
            "label": "Destination",
            "subtitle": destination_city.split(",")[0].strip(),
            "x": 0.72,
            "y": 0.34,
        }
    else:
        origin_point = None
        destination_point = {
            "kind": "destination",
            "label": "Destination",
            "subtitle": destination_city.split(",")[0].strip(),
            "x": 0.52,
            "y": 0.46,
        }

    activity_points = [
        {
            "kind": "outdoor",
            "label": "Outdoor window",
            "subtitle": trip_analysis.get("best_day_label") or "Best day",
            "x": clamp_trip_map_point(destination_point["x"] + 0.16),
            "y": clamp_trip_map_point(destination_point["y"] - 0.16),
        },
        {
            "kind": "indoor",
            "label": "Indoor backup",
            "subtitle": trip_analysis.get("caution_day_label") or "Flexible option",
            "x": clamp_trip_map_point(destination_point["x"] + 0.12),
            "y": clamp_trip_map_point(destination_point["y"] + 0.18),
        },
        {
            "kind": "evening",
            "label": "Easy evening",
            "subtitle": "Lighter plans near stay",
            "x": clamp_trip_map_point(destination_point["x"] - 0.18),
            "y": clamp_trip_map_point(destination_point["y"] + 0.08),
        },
    ]

    points = [point for point in [origin_point, destination_point, *activity_points] if point]
    route_line = None
    if origin_point:
        route_line = {
            "start_x": origin_point["x"],
            "start_y": origin_point["y"],
            "end_x": destination_point["x"],
            "end_y": destination_point["y"],
        }

    return points, route_line


def build_trip_plan_pdf_bundle(
    origin_weather,
    destination_weather,
    forecast_rows,
    trip_analysis,
    temp_symbol,
    speed_symbol,
    use_fahrenheit,
):
    origin_city = origin_weather.get("resolved_city") if origin_weather else ""
    destination_city = destination_weather.get("resolved_city") or trip_analysis["city"]
    destination_current = destination_weather.get("current") or {}
    origin_current = (origin_weather or {}).get("current") or {}

    overview_notes = {note["label"]: note for note in trip_analysis.get("overview_notes", [])}
    avg_temp_note = overview_notes.get("Average Temp", {"title": "--", "body": ""})
    temp_range_note = overview_notes.get("Min / Max", {"title": "--", "body": ""})
    rain_note = overview_notes.get("Rain Probability", {"title": "--", "body": ""})
    wind_note = overview_notes.get("Wind Conditions", {"title": "--", "body": ""})
    uv_note = overview_notes.get("UV Index", {"title": "--", "body": ""})

    if origin_city:
        route_label = f"{origin_city} to {destination_city}"
        origin_body = (
            f'{format_temperature_text(origin_current.get("temperature", 0), temp_symbol, use_fahrenheit)} | '
            f'{origin_current.get("condition", "Current conditions")}'
        )
    else:
        route_label = f"Trip plan to {destination_city}"
        origin_body = "Optional starting location left blank for this plan."

    destination_body = (
        f'{format_temperature_text(destination_current.get("temperature", 0), temp_symbol, use_fahrenheit)} | '
        f'{destination_current.get("condition", "Current conditions")}'
    )

    daily_rows = []
    visual_days = []
    for day in forecast_rows:
        display_date = datetime.strptime(day["date"], "%Y-%m-%d").strftime("%b %d, %Y")
        display_high = format_temperature_text(day["max"], temp_symbol, use_fahrenheit)
        display_low = format_temperature_text(day["min"], temp_symbol, use_fahrenheit)
        daily_rows.append(
            {
                "Date": display_date,
                "Day": day["day"],
                "Condition": day["condition"],
                "Low": display_low,
                "High": display_high,
                "Rain": f'{day.get("rain_chance", 0)}%',
                "Wind": format_wind_text(day.get("wind_speed", 0), speed_symbol),
                "UV": str(day.get("uv_index", 0)) if (day.get("uv_index", 0) or 0) > 0 else "--",
            }
        )
        visual_days.append(
            {
                "label": datetime.strptime(day["date"], "%Y-%m-%d").strftime("%b %d"),
                "day": day["day"],
                "condition": day["condition"],
                "high_value": format_temperature_value(day["max"], use_fahrenheit),
                "low_value": format_temperature_value(day["min"], use_fahrenheit),
                "high_text": display_high,
                "low_text": display_low,
            }
        )

    map_points, route_line = build_trip_plan_map_points(origin_weather, destination_weather, trip_analysis)

    return {
        "route_label": route_label,
        "from_city": origin_city or "Not specified",
        "to_city": destination_city,
        "date_range_label": trip_analysis["date_range_label"],
        "generated_at": datetime.now().strftime("%b %d, %Y %I:%M %p"),
        "temperature_unit": temp_symbol.strip(),
        "overview_body": trip_analysis["overview_body"],
        "snapshot_cards": [
            {
                "label": "From",
                "value": origin_city or "Not specified",
                "body": origin_body,
            },
            {
                "label": "Destination Now",
                "value": destination_city,
                "body": destination_body,
            },
            {
                "label": "Temperature Profile",
                "value": avg_temp_note["title"],
                "body": temp_range_note["title"],
            },
            {
                "label": "Trip Conditions",
                "value": rain_note["title"],
                "body": f'{wind_note["title"]} wind | {uv_note["title"]} UV',
            },
        ],
        "packing_items": trip_analysis.get("packing_items", []),
        "daily_rows": daily_rows,
        "visual_days": visual_days,
        "map_points": map_points,
        "route_line": route_line,
    }


def build_trip_plan_pdf_artifact(
    origin_query,
    origin_selection,
    destination_query,
    destination_selection,
    start_date,
    end_date,
    temp_symbol,
    speed_symbol,
    use_fahrenheit,
):
    if not destination_query:
        raise ValueError("Choose a destination before creating the trip plan PDF.")
    if start_date > end_date:
        raise ValueError("Start date must be on or before the end date.")

    destination_lookup = (
        destination_selection
        if destination_selection and destination_selection.get("latitude") is not None and destination_selection.get("longitude") is not None
        else destination_query
    )
    destination_weather = get_weather(destination_lookup)

    origin_weather = None
    if origin_query:
        origin_lookup = (
            origin_selection
            if origin_selection and origin_selection.get("latitude") is not None and origin_selection.get("longitude") is not None
            else origin_query
        )
        if str(origin_query).strip().lower() == str(destination_weather.get("resolved_city") or "").strip().lower():
            origin_weather = destination_weather
        else:
            origin_weather = get_weather(origin_lookup)

    destination_location = destination_weather.get("location") or {}
    if destination_location.get("latitude") is None or destination_location.get("longitude") is None:
        raise WeatherError("Location data is missing for the selected destination.")

    forecast_rows = get_daily_weather_range(
        destination_location.get("latitude"),
        destination_location.get("longitude"),
        start_date,
        end_date,
        destination_location.get("timezone") or "auto",
    )
    trip_analysis = build_trip_planner_analysis(
        destination_weather.get("resolved_city") or destination_query,
        forecast_rows,
        temp_symbol,
        speed_symbol,
        use_fahrenheit,
    )
    bundle = build_trip_plan_pdf_bundle(
        origin_weather,
        destination_weather,
        forecast_rows,
        trip_analysis,
        temp_symbol,
        speed_symbol,
        use_fahrenheit,
    )
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    route_slug = sanitize_export_filename(
        f'{bundle["from_city"]}_to_{bundle["to_city"]}' if origin_weather else f'trip_to_{bundle["to_city"]}'
    )
    filename = f"skyline_trip_plan_{route_slug}_{start_date.isoformat()}_to_{end_date.isoformat()}_{timestamp}.pdf"

    return {
        "bundle": bundle,
        "bytes": build_trip_plan_pdf(bundle),
        "filename": filename,
        "origin_weather": origin_weather,
        "destination_weather": destination_weather,
    }


def reset_searchbox_state(search_value=""):
    if search_value:
        st.session_state["city_input_value"] = search_value
        st.session_state["search_query"] = search_value


def get_search_display_value(search_value):
    if isinstance(search_value, dict):
        return (search_value.get("label") or search_value.get("query") or "").strip()

    return str(search_value or "").strip()


def _legacy_render_search_experience():
    current_value = json.dumps(st.session_state.get("search_query", ""))
    components.html(
        f"""
        <div class="search-shell" id="search-shell">
          <div class="search-panel" id="search-panel">
            <div class="search-control">
              <div class="search-icon" aria-hidden="true">
                <svg viewBox="0 0 24 24" fill="none">
                  <circle cx="11" cy="11" r="6.25"></circle>
                  <path d="M16.2 16.2L20 20"></path>
                </svg>
              </div>
              <input
                id="city-search-input"
                class="search-input"
                type="text"
                placeholder="Search any city worldwide"
                autocomplete="off"
                spellcheck="false"
              />
              <button id="city-search-submit" class="search-submit" type="button" aria-label="Search city">
                <svg viewBox="0 0 24 24" fill="none">
                  <path d="M5 12H19"></path>
                  <path d="M13 6L19 12L13 18"></path>
                </svg>
              </button>
            </div>
            <div id="city-search-results" class="search-results" role="listbox" aria-label="City suggestions"></div>
          </div>
        </div>
        <style>
          body {{
            margin: 0;
            background: transparent;
            font-family: "Segoe UI", sans-serif;
            overflow: hidden;
          }}
          .search-shell {{
            width: 100%;
            position: relative;
          }}
          .search-panel {{
            position: relative;
            padding: 0.38rem;
            border-radius: 34px;
            overflow: hidden;
            background:
              linear-gradient(180deg, rgba(255,255,255,0.18), rgba(255,255,255,0.07)),
              linear-gradient(135deg, rgba(162, 210, 232, 0.14), rgba(255,255,255,0.02));
            border: 1px solid rgba(255,255,255,0.18);
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.16);
            backdrop-filter: blur(18px);
            transition: border-radius 0.45s ease, border-color 0.3s ease;
          }}
          .search-panel.is-open {{
            border-radius: 34px 34px 24px 24px;
            border-color: rgba(255,255,255,0.22);
          }}
          .search-control {{
            display: grid;
            grid-template-columns: 3.55rem 1fr 3.55rem;
            align-items: center;
            min-height: 4.95rem;
            border-radius: 30px;
            background:
              radial-gradient(circle at top left, rgba(255,255,255,0.1), transparent 40%),
              linear-gradient(180deg, rgba(9, 20, 34, 0.76), rgba(10, 21, 33, 0.58));
            border: 1px solid rgba(255,255,255,0.1);
            overflow: hidden;
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.05);
          }}
          .search-icon {{
            display: flex;
            align-items: center;
            justify-content: center;
            color: rgba(232, 245, 255, 0.7);
          }}
          .search-icon svg,
          .search-submit svg {{
            width: 1.24rem;
            height: 1.24rem;
            stroke: currentColor;
            stroke-width: 1.85;
            stroke-linecap: round;
            stroke-linejoin: round;
          }}
          .search-input {{
            width: 100%;
            min-height: 4.95rem;
            border: 0;
            background: transparent;
            color: #f5fbff;
            font-size: 1.12rem;
            font-weight: 600;
            padding: 0;
            outline: none;
            box-sizing: border-box;
          }}
          .search-input::placeholder {{
            color: rgba(226, 240, 251, 0.5);
          }}
          .search-input:focus {{
            border-color: transparent;
            box-shadow: none;
          }}
          .search-submit {{
            width: 3rem;
            height: 3rem;
            justify-self: center;
            border-radius: 999px;
            border: 1px solid rgba(255,255,255,0.14);
            background: linear-gradient(135deg, rgba(214,239,250,0.24), rgba(169,215,235,0.08));
            color: #f5fbff;
            cursor: pointer;
            transition: transform 0.3s ease, background 0.3s ease, border-color 0.3s ease;
          }}
          .search-submit:hover {{
            transform: translateX(1px) scale(1.03);
            background: linear-gradient(135deg, rgba(228, 247, 255, 0.32), rgba(175, 219, 237, 0.14));
            border-color: rgba(255,255,255,0.22);
          }}
          .search-results {{
            display: none;
          }}
          @media (max-width: 760px) {{
            .search-control {{
              grid-template-columns: 3.15rem 1fr 3.15rem;
              min-height: 4.55rem;
            }}
            .search-input {{
              min-height: 4.55rem;
              font-size: 1.02rem;
            }}
          }}
        </style>
        <script>
          if (window.__skylineSearchCleanup) {{
            window.__skylineSearchCleanup();
          }}

          const shell = document.getElementById("search-shell");
          const panel = document.getElementById("search-panel");
          const input = document.getElementById("city-search-input");
          const submit = document.getElementById("city-search-submit");
          const hostWindow = window.parent;
          const hostDoc = hostWindow.document;
          const frameElement = window.frameElement;
          const geocodingUrl = "https://geocoding-api.open-meteo.com/v1/search";
          const portalId = "skyline-search-portal";
          const styleId = "skyline-search-portal-style";
          let debounceHandle = null;
          let activeQuery = "";
          let activeIndex = -1;
          let currentResults = [];

          let portal = hostDoc.getElementById(portalId);
          if (!portal) {{
            portal = hostDoc.createElement("div");
            portal.id = portalId;
            hostDoc.body.appendChild(portal);
          }}

          if (!hostDoc.getElementById(styleId)) {{
            const style = hostDoc.createElement("style");
            style.id = styleId;
            style.textContent = `
              #skyline-search-portal {{
                position: fixed;
                z-index: 9998;
                pointer-events: none;
                opacity: 0;
                transform: translateY(-0.7rem);
                transition: opacity 0.26s ease, transform 0.32s cubic-bezier(0.22, 1, 0.36, 1);
              }}
              #skyline-search-portal.is-open {{
                opacity: 1;
                transform: translateY(0);
                pointer-events: auto;
              }}
              .skyline-search-dropdown {{
                overflow: hidden;
                border-radius: 0 0 28px 28px;
                background:
                  linear-gradient(180deg, rgba(7, 18, 31, 0.96), rgba(7, 18, 29, 0.92)),
                  linear-gradient(135deg, rgba(255,255,255,0.08), transparent 55%);
                border: 1px solid rgba(255,255,255,0.12);
                box-shadow:
                  0 28px 72px rgba(4, 14, 28, 0.34),
                  inset 0 1px 0 rgba(255,255,255,0.08);
                backdrop-filter: blur(24px);
              }}
              .skyline-search-scroll {{
                max-height: min(25rem, calc(100vh - 10rem));
                overflow-y: auto;
                padding: 0.3rem;
              }}
              .skyline-search-scroll::-webkit-scrollbar {{
                width: 8px;
              }}
              .skyline-search-scroll::-webkit-scrollbar-thumb {{
                background: rgba(255,255,255,0.16);
                border-radius: 999px;
              }}
              .skyline-search-scroll::-webkit-scrollbar-track {{
                background: transparent;
              }}
              .skyline-search-option {{
                width: 100%;
                display: block;
                border: 1px solid transparent;
                background: transparent;
                color: #f3f9ff;
                padding: 0.94rem 1rem;
                border-radius: 18px;
                cursor: pointer;
                text-align: left;
                transition: background 0.22s ease, transform 0.22s ease, border-color 0.22s ease;
              }}
              .skyline-search-option + .skyline-search-option {{
                margin-top: 0.08rem;
              }}
              .skyline-search-option:hover,
              .skyline-search-option.is-active {{
                background: rgba(255,255,255,0.08);
                border-color: rgba(255,255,255,0.08);
                transform: translateX(2px);
              }}
              .skyline-search-option-primary {{
                font-size: 0.98rem;
                font-weight: 600;
                line-height: 1.24;
              }}
              .skyline-search-option-secondary {{
                margin-top: 0.22rem;
                font-size: 0.8rem;
                letter-spacing: 0.02em;
                color: rgba(224, 239, 248, 0.62);
              }}
              .skyline-search-empty {{
                padding: 1rem 1.05rem;
                color: rgba(224, 239, 248, 0.74);
                font-size: 0.9rem;
              }}
            `;
            hostDoc.head.appendChild(style);
          }}

          portal.innerHTML = '<div class="skyline-search-dropdown"><div class="skyline-search-scroll" id="skyline-search-scroll"></div></div>';
          const scrollArea = portal.querySelector("#skyline-search-scroll");

          input.value = {current_value};

          const resizeFrame = () => {{
            window.parent.postMessage({{ isStreamlitMessage: true, type: "streamlit:setFrameHeight", height: 104 }}, "*");
          }};

          const escapeHtml = (value) => String(value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");

          const redirectWithPayload = (params) => {{
            const nextUrl = new URL(hostWindow.location.href);
            nextUrl.search = "";
            Object.entries(params).forEach(([key, value]) => nextUrl.searchParams.set(key, value));
            const submitForm = hostDoc.createElement("form");
            submitForm.method = "GET";
            submitForm.action = `${{nextUrl.origin}}${{nextUrl.pathname}}`;
            submitForm.target = "_top";
            nextUrl.searchParams.forEach((value, key) => {{
              const field = hostDoc.createElement("input");
              field.type = "hidden";
              field.name = key;
              field.value = value;
              submitForm.appendChild(field);
            }});
            hostDoc.body.appendChild(submitForm);
            submitForm.submit();
          }};

          const assignPayload = (params) => {{
            const nextUrl = new URL(hostWindow.location.href);
            nextUrl.search = "";
            Object.entries(params).forEach(([key, value]) => nextUrl.searchParams.set(key, value));
            hostWindow.location.assign(nextUrl.toString());
          }};

          const updatePortalPosition = () => {{
            const rect = frameElement.getBoundingClientRect();
            portal.style.top = `${{rect.bottom - 14}}px`;
            portal.style.left = `${{Math.max(rect.left + 6, 8)}}px`;
            portal.style.width = `${{Math.max(rect.width - 12, 260)}}px`;
          }};

          const setOpen = (isOpen) => {{
            const shouldOpen = isOpen && (currentResults.length > 0 || scrollArea.textContent.trim());
            panel.classList.toggle("is-open", shouldOpen);
            portal.classList.toggle("is-open", shouldOpen);
            if (shouldOpen) {{
              updatePortalPosition();
            }}
            resizeFrame();
          }};

          const hideResults = () => {{
            currentResults = [];
            activeIndex = -1;
            scrollArea.innerHTML = "";
            setOpen(false);
          }};

          const applyActiveState = () => {{
            const options = Array.from(scrollArea.querySelectorAll(".skyline-search-option"));
            options.forEach((option, index) => {{
              option.classList.toggle("is-active", index === activeIndex);
              option.setAttribute("aria-selected", index === activeIndex ? "true" : "false");
              if (index === activeIndex) {{
                option.scrollIntoView({{ block: "nearest" }});
              }}
            }});
          }};

          const renderResults = (items) => {{
            if (!items.length) {{
              currentResults = [];
              activeIndex = -1;
              scrollArea.innerHTML = '<div class="skyline-search-empty">No matches yet. Try another city or country.</div>';
              setOpen(true);
              return;
            }}
            currentResults = items;
            activeIndex = 0;
            scrollArea.innerHTML = items.map((item, index) => `
              <button
                class="skyline-search-option"
                type="button"
                role="option"
                data-index="${{index}}"
                aria-selected="${{index === 0 ? "true" : "false"}}"
              >
                <div class="skyline-search-option-primary">${{escapeHtml(item.label)}}</div>
                <div class="skyline-search-option-secondary">${{escapeHtml(item.meta)}}</div>
              </button>
            `).join("");
            applyActiveState();
            setOpen(true);
          }};

          const normalizeResults = (items, query) => {{
            const loweredQuery = query.trim().toLowerCase();
            const seenLabels = new Set();
            return items
              .map((item) => {{
                const parts = [];
                [item.name, item.admin1, item.country].forEach((part) => {{
                  if (part && !parts.includes(part)) {{
                    parts.push(part);
                  }}
                }});
                const label = parts.join(", ");
                return {{
                  label,
                  meta: [item.admin1, item.country].filter(Boolean).join(" • ") || "Suggested location",
                  latitude: item.latitude,
                  longitude: item.longitude,
                  population: item.population || 0,
                  rank:
                    ((item.name || "").toLowerCase() === loweredQuery ? 0 : 1) +
                    ((item.name || "").toLowerCase().startsWith(loweredQuery) ? 0 : 2) +
                    (label.toLowerCase().startsWith(loweredQuery) ? 0 : 3),
                }};
              }})
              .filter((item) => item.label)
              .sort((left, right) => {{
                if (left.rank !== right.rank) {{
                  return left.rank - right.rank;
                }}
                if (left.population !== right.population) {{
                  return right.population - left.population;
                }}
                return left.label.localeCompare(right.label);
              }})
              .filter((item) => {{
                if (seenLabels.has(item.label)) {{
                  return false;
                }}
                seenLabels.add(item.label);
                return true;
              }})
              .slice(0, 8);
          }};

          const submitTypedSearch = () => {{
            const query = input.value.trim();
            if (!query) {{
              return;
            }}
            hideResults();
            redirectWithPayload({{ search_query: query }});
          }};

          const selectItem = (index) => {{
            const item = currentResults[index];
            if (!item) {{
              submitTypedSearch();
              return;
            }}
            input.value = item.label;
            hideResults();
            redirectWithPayload({{
              search_label: item.label,
              search_lat: item.latitude,
              search_lon: item.longitude,
            }});
          }};

          const searchCities = async (query) => {{
            activeQuery = query;
            if (query.trim().length < 2) {{
              hideResults();
              return;
            }}
            try {{
              const url = `${{geocodingUrl}}?name=${{encodeURIComponent(query)}}&count=12&language=en&format=json`;
              const response = await fetch(url);
              const data = await response.json();
              if (activeQuery !== query) {{
                return;
              }}
              renderResults(normalizeResults(data.results || [], query));
            }} catch (error) {{
              hideResults();
            }}
          }};

          input.addEventListener("input", (event) => {{
            clearTimeout(debounceHandle);
            debounceHandle = setTimeout(() => searchCities(event.target.value), 180);
          }});

          input.addEventListener("focus", () => {{
            if (input.value.trim().length >= 2) {{
              searchCities(input.value);
            }}
            updatePortalPosition();
            resizeFrame();
          }});

          submit.addEventListener("click", () => {{
            if (currentResults.length && activeIndex >= 0 && panel.classList.contains("is-open")) {{
              selectItem(activeIndex);
            }} else {{
              submitTypedSearch();
            }}
          }});

          input.addEventListener("keydown", (event) => {{
            if (event.key === "ArrowDown" && currentResults.length) {{
              event.preventDefault();
              activeIndex = Math.min(activeIndex + 1, currentResults.length - 1);
              applyActiveState();
              return;
            }}
            if (event.key === "ArrowUp" && currentResults.length) {{
              event.preventDefault();
              activeIndex = Math.max(activeIndex - 1, 0);
              applyActiveState();
              return;
            }}
            if (event.key === "Enter") {{
              event.preventDefault();
              if (currentResults.length && panel.classList.contains("is-open") && activeIndex >= 0) {{
                selectItem(activeIndex);
              }} else {{
                submitTypedSearch();
              }}
            }}
            if (event.key === "Escape") {{
              hideResults();
            }}
          }});

          scrollArea.addEventListener("click", (event) => {{
            const option = event.target.closest(".skyline-search-option");
            if (!option) {{
              return;
            }}
            selectItem(Number(option.dataset.index));
          }});

          scrollArea.addEventListener("mousemove", (event) => {{
            const option = event.target.closest(".skyline-search-option");
            if (!option) {{
              return;
            }}
            activeIndex = Number(option.dataset.index);
            applyActiveState();
          }});

          const handleHostPointerDown = (event) => {{
            if (portal.contains(event.target)) {{
              return;
            }}
            hideResults();
          }};

          const handleWindowChange = () => {{
            if (portal.classList.contains("is-open")) {{
              updatePortalPosition();
            }}
          }};

          hostDoc.addEventListener("pointerdown", handleHostPointerDown, true);
          hostWindow.addEventListener("resize", handleWindowChange);
          hostWindow.addEventListener("scroll", handleWindowChange, true);

          const storage = (() => {{
            try {{
              return hostWindow.localStorage;
            }} catch (error) {{
              return window.localStorage;
            }}
          }})();

          const currentUrl = new URL(hostWindow.location.href);
          const hasPendingExternalSearch =
            currentUrl.searchParams.has("search_lat") ||
            currentUrl.searchParams.has("search_lon") ||
            currentUrl.searchParams.has("search_query") ||
            currentUrl.searchParams.has("geo_lat") ||
            currentUrl.searchParams.has("geo_lon");

          if (!storage.getItem("skyline-location-prompted-v2") && !hasPendingExternalSearch && "geolocation" in navigator) {{
            storage.setItem("skyline-location-prompted-v2", "1");
            navigator.geolocation.getCurrentPosition(
              (position) => {{
                assignPayload({{
                  geo_lat: position.coords.latitude.toFixed(4),
                  geo_lon: position.coords.longitude.toFixed(4),
                }});
              }},
              () => {{}},
              {{ enableHighAccuracy: true, timeout: 10000, maximumAge: 600000 }}
            );
          }}

          window.__skylineSearchCleanup = () => {{
            hostDoc.removeEventListener("pointerdown", handleHostPointerDown, true);
            hostWindow.removeEventListener("resize", handleWindowChange);
            hostWindow.removeEventListener("scroll", handleWindowChange, true);
            if (portal && portal.parentNode) {{
              portal.parentNode.removeChild(portal);
            }}
          }};

          resizeFrame();
        </script>
        """,
        height=104,
    )


def process_location_request():
    search_lat = st.query_params.get("search_lat")
    search_lon = st.query_params.get("search_lon")
    geo_lat = st.query_params.get("geo_lat")
    geo_lon = st.query_params.get("geo_lon")
    search_query = st.query_params.get("search_query")

    if search_lat and search_lon:
        latitude = search_lat
        longitude = search_lon
        query_label = st.query_params.get("search_label") or "Selected Location"
    elif geo_lat and geo_lon:
        latitude = geo_lat
        longitude = geo_lon
        query_label = "Your Location"
    elif search_query:
        try:
            weather = get_weather(search_query)
        except WeatherError as exc:
            st.query_params.clear()
            st.error(str(exc))
            return

        resolved_key = weather["resolved_city"].strip().upper()
        st.session_state["last_weather"] = weather
        st.session_state["last_city_display"] = weather["resolved_city"]
        st.session_state["last_city_key"] = resolved_key
        st.session_state["city_input_value"] = weather["resolved_city"]
        st.session_state["search_query"] = weather["resolved_city"]
        save_last_weather_state(weather, resolved_key)
        remember_recent_search(weather)
        st.query_params.clear()
        return
    else:
        return

    try:
        latitude = float(latitude)
        longitude = float(longitude)
    except ValueError:
        st.query_params.clear()
        return

    try:
        weather = get_weather(
            {
                "label": query_label,
                "query": query_label,
                "latitude": latitude,
                "longitude": longitude,
            }
        )
    except WeatherError as exc:
        st.query_params.clear()
        st.error(str(exc))
        return

    resolved_key = weather["resolved_city"].strip().upper()
    st.session_state["last_weather"] = weather
    st.session_state["last_city_display"] = weather["resolved_city"]
    st.session_state["last_city_key"] = resolved_key
    st.session_state["city_input_value"] = weather["resolved_city"]
    st.session_state["search_query"] = weather["resolved_city"]
    save_last_weather_state(weather, resolved_key)
    remember_recent_search(weather)
    st.query_params.clear()


def process_forecast_dialog_request():
    forecast_index = st.query_params.get("forecast_index")
    if forecast_index is None:
        return

    try:
        st.session_state["pending_forecast_dialog_index"] = int(forecast_index)
    except ValueError:
        st.session_state.pop("pending_forecast_dialog_index", None)

    st.query_params.clear()


# Session setup keeps the app stable across reruns.
def initialize_session_state():
    defaults = {
        "saved_cities": ["DUBAI", "LONDON"],
        "city_input_value": "Dubai",
        "search_query": "Dubai",
        "temp_unit": TEMP_OPTIONS[0],
        "speed_unit": SPEED_OPTIONS[0],
        "settings_selected_city": "DUBAI",
        "recent_searches": [],
        "export_range": EXPORT_RANGE_OPTIONS[0][0],
        "export_format": EXPORT_FORMAT_OPTIONS[0][0],
        "export_custom_dates": get_default_export_custom_dates(),
        "show_export_dialog": False,
        "show_settings_dialog": False,
        "weather_map_layer": "Clouds",
        "compare_primary_city_query": "",
        "compare_primary_city_seed": "",
        "compare_primary_city_selection": None,
        "compare_secondary_city_query": "",
        "compare_secondary_city_selection": None,
        "compare_primary_weather": None,
        "compare_secondary_weather": None,
        "compare_primary_search_event_id": "",
        "compare_secondary_search_event_id": "",
        "trip_planner_origin_query": "",
        "trip_planner_origin_selection": None,
        "trip_planner_origin_search_event_id": "",
        "trip_planner_destination_query": "",
        "trip_planner_destination_selection": None,
        "trip_planner_destination_search_event_id": "",
        "trip_planner_start_date": get_default_trip_planner_dates()[0],
        "trip_planner_end_date": get_default_trip_planner_dates()[1],
        "trip_planner_error": "",
        "preferences_loaded": False,
        "personal_activity_focus": PERSONAL_ACTIVITY_OPTIONS[0],
        "personal_preferred_time": PERSONAL_TIME_OPTIONS[0],
        "personal_temperature_preference": PERSONAL_TEMPERATURE_OPTIONS[0],
        "personal_outfit_vibe": PERSONAL_OUTFIT_OPTIONS[0],
        "personalization_prompt_status": PERSONALIZATION_PROMPT_PENDING,
        "personalization_remind_after": "",
        "show_personalization_dialog": False,
        "personalization_prompt_evaluated": False,
        "active_content_section": CONTENT_SECTIONS[0],
        "nav_layout_bootstrap_done": False,
    }

    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value

    if not st.session_state.get("preferences_loaded"):
        saved_preferences = load_user_preferences()
        st.session_state["temp_unit"] = saved_preferences.get("temp_unit", st.session_state["temp_unit"])
        st.session_state["speed_unit"] = saved_preferences.get("speed_unit", st.session_state["speed_unit"])
        st.session_state["weather_map_layer"] = saved_preferences.get("weather_map_layer", st.session_state["weather_map_layer"])
        st.session_state["recent_searches"] = normalize_recent_searches(saved_preferences.get("recent_searches", []))
        st.session_state["personal_activity_focus"] = saved_preferences.get("personal_activity_focus", st.session_state["personal_activity_focus"])
        st.session_state["personal_preferred_time"] = saved_preferences.get("personal_preferred_time", st.session_state["personal_preferred_time"])
        st.session_state["personal_temperature_preference"] = saved_preferences.get("personal_temperature_preference", st.session_state["personal_temperature_preference"])
        st.session_state["personal_outfit_vibe"] = saved_preferences.get("personal_outfit_vibe", st.session_state["personal_outfit_vibe"])
        st.session_state["personalization_prompt_status"] = saved_preferences.get("personalization_prompt_status", st.session_state["personalization_prompt_status"])
        st.session_state["personalization_remind_after"] = saved_preferences.get("personalization_remind_after", st.session_state["personalization_remind_after"])
        last_selected_city = saved_preferences.get("last_selected_city")
        if last_selected_city:
            st.session_state["city_input_value"] = last_selected_city
            st.session_state["search_query"] = last_selected_city
        st.session_state["preferences_loaded"] = True

    if not st.session_state.get("personalization_prompt_evaluated"):
        st.session_state["show_personalization_dialog"] = should_show_personalization_prompt()
        st.session_state["personalization_prompt_evaluated"] = True

    saved_state = load_last_weather_state()
    if "last_weather" not in st.session_state and saved_state:
        st.session_state["last_weather"] = saved_state.get("last_weather")
        st.session_state["last_city_display"] = saved_state.get("last_city_display")
        st.session_state["last_city_key"] = saved_state.get("last_city_key")

        if saved_state.get("last_city_display"):
            st.session_state["city_input_value"] = saved_state["last_city_display"]
            st.session_state["search_query"] = saved_state["last_city_display"]


# First-load weather avoids showing an empty placeholder header.
def bootstrap_default_weather():
    if st.session_state.get("last_weather"):
        return

    default_city = st.session_state["city_input_value"].strip() or "Dubai"

    try:
        weather = get_weather(default_city)
    except WeatherError:
        return

    city_key = weather["resolved_city"].strip().upper()
    st.session_state["last_weather"] = weather
    st.session_state["last_city_display"] = weather["resolved_city"]
    st.session_state["last_city_key"] = city_key
    st.session_state["city_input_value"] = weather["resolved_city"]
    reset_searchbox_state(weather["resolved_city"])
    save_last_weather_state(weather, city_key)
    remember_recent_search(weather)


# Current weather state drives the background and header content.
def get_active_weather_state():
    weather = st.session_state.get("last_weather")
    city_name = st.session_state.get("last_city_display")
    return weather, city_name


def inject_dialog_surface(anchor_class, dialog_width):
    st.markdown(
        dedent(
            f"""
            <style>
            div[data-testid="stDialog"]:has(.{anchor_class}) {{
                background: rgba(6, 16, 28, 0.18);
                backdrop-filter: blur(4px);
                animation: skylineDialogBackdropIn 0.22s ease both;
                transition: opacity 0.2s ease, backdrop-filter 0.2s ease;
            }}
            div[data-testid="stDialog"]:has(.{anchor_class}).skyline-dialog-closing {{
                opacity: 0;
                backdrop-filter: blur(0px);
            }}
            div[data-testid="stDialog"] div[role="dialog"]:has(.{anchor_class}) {{
                width: {dialog_width};
                max-width: {dialog_width};
                border-radius: 30px;
                background: linear-gradient(180deg, rgba(120, 154, 187, 0.18), rgba(17, 43, 72, 0.28));
                border: 1px solid rgba(255,255,255,0.16);
                box-shadow: 0 24px 58px rgba(4, 15, 32, 0.26);
                backdrop-filter: blur(24px);
                transform-origin: top center;
                animation: skylineDialogPanelIn 0.28s cubic-bezier(0.22, 1, 0.36, 1) both;
                transition: opacity 0.2s ease, transform 0.22s cubic-bezier(0.22, 1, 0.36, 1);
            }}
            div[data-testid="stDialog"] div[role="dialog"]:has(.{anchor_class}).skyline-dialog-closing {{
                opacity: 0;
                transform: translateY(18px) scale(0.975);
            }}
            div[data-testid="stDialog"] div[role="dialog"]:has(.{anchor_class}) > div[data-testid="stVerticalBlock"] {{
                gap: 1rem;
                padding-bottom: 0.8rem;
            }}
            div[data-testid="stDialog"] div[role="dialog"]:has(.{anchor_class}) button[aria-label="Close"] {{
                border-radius: 999px;
                width: 2.15rem;
                height: 2.15rem;
                min-width: 2.15rem;
                padding: 0;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                border: 1px solid rgba(255,255,255,0.14);
                background: rgba(255,255,255,0.06);
                color: rgba(242,248,255,0.82);
                top: 0.75rem;
                right: 0.95rem;
                line-height: 1;
                box-shadow: 0 8px 20px rgba(4, 15, 32, 0.14);
            }}
            div[data-testid="stDialog"] div[role="dialog"]:has(.{anchor_class}) button[aria-label="Close"]:hover {{
                background: rgba(255,255,255,0.1);
                color: #f8fbff;
            }}
            div[data-testid="stDialog"] div[role="dialog"]:has(.{anchor_class}) .stButton button[kind="primary"],
            div[data-testid="stDialog"] div[role="dialog"]:has(.{anchor_class}) .stDownloadButton button {{
                min-height: 3.05rem;
                border-radius: 16px;
                border: 1px solid rgba(255,255,255,0.14);
                background: linear-gradient(180deg, rgba(214, 239, 250, 0.24), rgba(169, 215, 235, 0.12));
                color: #f4fbff;
                box-shadow: 0 14px 30px rgba(4, 15, 32, 0.18);
            }}
            div[data-testid="stDialog"] div[role="dialog"]:has(.{anchor_class}) .stButton button[kind="primary"]:hover,
            div[data-testid="stDialog"] div[role="dialog"]:has(.{anchor_class}) .stDownloadButton button:hover {{
                border-color: rgba(255,255,255,0.2);
                background: linear-gradient(180deg, rgba(224, 246, 255, 0.3), rgba(180, 222, 240, 0.16));
            }}
            div[data-testid="stDialog"] div[role="dialog"]:has(.{anchor_class}) .stButton button[kind="secondary"] {{
                border: 1px solid rgba(255,255,255,0.14);
                background: linear-gradient(180deg, rgba(255,255,255,0.18), rgba(255,255,255,0.08));
                color: #eef8ff;
                box-shadow: 0 10px 24px rgba(4, 15, 32, 0.14);
            }}
            div[data-testid="stDialog"] div[role="dialog"]:has(.{anchor_class}) .stButton button[kind="secondary"]:hover {{
                border-color: rgba(255,255,255,0.18);
                background: linear-gradient(180deg, rgba(255,255,255,0.22), rgba(255,255,255,0.1));
            }}
            div[data-testid="stDialog"] div[role="dialog"]:has(.{anchor_class}) div[data-baseweb="select"] > div {{
                background: linear-gradient(180deg, rgba(255,255,255,0.12), rgba(255,255,255,0.05));
                border: 1px solid rgba(255,255,255,0.12);
                box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
            }}
            div[data-testid="stDialog"] div[role="dialog"]:has(.{anchor_class}) div[data-baseweb="select"] span,
            div[data-testid="stDialog"] div[role="dialog"]:has(.{anchor_class}) div[data-baseweb="select"] input,
            div[data-testid="stDialog"] div[role="dialog"]:has(.{anchor_class}) div[data-baseweb="select"] svg {{
                color: #eef8ff;
            }}
            div[data-testid="stDialog"] div[role="dialog"]:has(.{anchor_class}) hr {{
                border-color: rgba(255,255,255,0.12);
            }}
            @keyframes skylineDialogBackdropIn {{
                from {{
                    opacity: 0;
                }}
                to {{
                    opacity: 1;
                }}
            }}
            @keyframes skylineDialogPanelIn {{
                from {{
                    opacity: 0;
                    transform: translateY(18px) scale(0.975);
                }}
                to {{
                    opacity: 1;
                    transform: translateY(0) scale(1);
                }}
            }}
            </style>
            <div class="{anchor_class}" aria-hidden="true"></div>
            """
        ).strip(),
        unsafe_allow_html=True,
    )
    components.html(
        f"""
        <script>
          const hostWindow = window.parent;
          const hostDoc = hostWindow.document;
          const anchorClass = {json.dumps(anchor_class)};
          const cleanupKey = "__skylineDialogCleanup_" + anchorClass.replace(/[^a-zA-Z0-9_-]/g, "_");

          if (hostWindow[cleanupKey]) {{
            hostWindow[cleanupKey]();
          }}

          const dialogRoot = Array.from(hostDoc.querySelectorAll('div[data-testid="stDialog"]'))
            .find((node) => node.querySelector("." + anchorClass));
          const dialogCard = dialogRoot?.querySelector('div[role="dialog"]');
          const closeButton = dialogCard?.querySelector('button[aria-label="Close"]');

          if (!dialogRoot || !dialogCard || !closeButton) {{
            hostWindow[cleanupKey] = null;
            return;
          }}

          const closeDelay = 190;
          let closeTimer = null;

          dialogRoot.classList.remove("skyline-dialog-closing");
          dialogCard.classList.remove("skyline-dialog-closing");
          dialogRoot.dataset.skylineClosing = "false";

          const finishClose = () => {{
            closeButton.dataset.skylineBypassClose = "true";
            closeButton.click();
          }};

          const startClose = () => {{
            if (dialogRoot.dataset.skylineClosing === "true") {{
              return;
            }}
            dialogRoot.dataset.skylineClosing = "true";
            dialogRoot.classList.add("skyline-dialog-closing");
            dialogCard.classList.add("skyline-dialog-closing");
            closeTimer = hostWindow.setTimeout(finishClose, closeDelay);
          }};

          const handleCloseClick = (event) => {{
            if (closeButton.dataset.skylineBypassClose === "true") {{
              closeButton.dataset.skylineBypassClose = "false";
              return;
            }}
            event.preventDefault();
            event.stopPropagation();
            startClose();
          }};

          const handleOverlayPointerDown = (event) => {{
            if (!dialogRoot.contains(event.target)) {{
              return;
            }}
            if (event.target.closest('div[role="dialog"]')) {{
              return;
            }}
            event.preventDefault();
            event.stopPropagation();
            startClose();
          }};

          const handleEscape = (event) => {{
            if (event.key !== "Escape") {{
              return;
            }}
            event.preventDefault();
            event.stopPropagation();
            startClose();
          }};

          closeButton.addEventListener("click", handleCloseClick, true);
          hostDoc.addEventListener("pointerdown", handleOverlayPointerDown, true);
          hostWindow.addEventListener("keydown", handleEscape, true);

          hostWindow[cleanupKey] = () => {{
            if (closeTimer) {{
              hostWindow.clearTimeout(closeTimer);
              closeTimer = null;
            }}
            closeButton.removeEventListener("click", handleCloseClick, true);
            hostDoc.removeEventListener("pointerdown", handleOverlayPointerDown, true);
            hostWindow.removeEventListener("keydown", handleEscape, true);
          }};
        </script>
        """,
        height=0,
    )


# Settings content is shared between dialog-capable and fallback modes.
def render_settings_panel():
    inject_dialog_surface("skyline-settings-dialog-anchor", "min(84vw, 760px)")
    st.markdown("**Preferences**")
    st.radio("Temperature Unit", TEMP_OPTIONS, key="settings_temp_unit_choice")
    st.radio("Wind Speed", SPEED_OPTIONS, key="settings_speed_unit_choice")
    st.selectbox("Preferred Map Layer", MAP_LAYER_OPTIONS, key="settings_map_layer_choice")

    st.divider()
    st.markdown("**Saved Behavior**")
    current_city = st.session_state.get("last_city_display") or st.session_state.get("search_query") or "Dubai"
    st.caption(f"Last selected city to save: {current_city}")
    recent_labels = [item.get("label", "") for item in st.session_state.get("recent_searches", [])[:4]]
    if recent_labels:
        st.caption("Recent searches are saved automatically and prioritized in the main search suggestions.")
        st.caption("Recent: " + " | ".join(recent_labels))

    st.divider()
    st.markdown("**Personalization**")
    st.caption("These choices tune the scheduler, activity emphasis, and what-to-wear guidance.")
    render_personalization_controls("settings")
    st.caption(describe_personalization_summary(get_personalization_profile(get_personalization_draft_values("settings"))))

    personalization_actions = st.columns(2)
    with personalization_actions[0]:
        if st.button("Open Guided Personalization", key="open_personalization_dialog_from_settings", type="secondary", use_container_width=True):
            sync_personalization_draft_state("personalization")
            st.session_state["show_personalization_dialog"] = True
            st.rerun()
    with personalization_actions[1]:
        if st.button("Disable Startup Popup", key="disable_personalization_prompt_button", type="secondary", use_container_width=True):
            st.session_state["personalization_prompt_status"] = PERSONALIZATION_PROMPT_HIDDEN
            st.session_state["personalization_remind_after"] = ""
            save_user_preferences(build_preferences_payload(prompt_status=PERSONALIZATION_PROMPT_HIDDEN, remind_after=""))
            st.success("Startup personalization popup disabled.")
            st.rerun()

    if st.button("Save Preferences", key="save_preferences_button", type="primary", use_container_width=True):
        st.session_state["temp_unit"] = st.session_state["settings_temp_unit_choice"]
        st.session_state["speed_unit"] = st.session_state["settings_speed_unit_choice"]
        st.session_state["weather_map_layer"] = st.session_state["settings_map_layer_choice"]
        apply_personalization_draft_state("settings")
        st.session_state["personalization_prompt_status"] = PERSONALIZATION_PROMPT_SAVED
        st.session_state["personalization_remind_after"] = ""
        save_user_preferences(build_preferences_payload())
        st.success("Preferences saved.")
        st.rerun()


# Settings open from the gear button and use a dialog when available.
def open_settings():
    sync_settings_draft_state()
    if hasattr(st, "dialog"):
        @st.dialog("Settings")
        def settings_dialog():
            render_settings_panel()

        settings_dialog()
    else:
        with st.popover("Settings", use_container_width=True):
            render_settings_panel()


def open_personalization_dialog():
    sync_personalization_draft_state("personalization")
    if hasattr(st, "dialog"):
        @st.dialog("Personalize Skyline Forecast")
        def personalization_dialog():
            render_personalization_panel()

        personalization_dialog()
    else:
        with st.popover("Personalize Skyline Forecast", use_container_width=True):
            render_personalization_panel()


def render_export_dialog_panel(weather_to_show, city_to_show, temp_symbol, speed_symbol, use_fahrenheit):
    inject_dialog_surface("skyline-export-dialog-anchor", "min(84vw, 960px)")
    st.markdown(
        dedent(
            """
            <style>
            div[data-testid="stDialog"] div[role="dialog"]:has(.skyline-export-dialog-anchor) {
                background: linear-gradient(180deg, rgba(120, 154, 187, 0.18), rgba(17, 43, 72, 0.28));
            }
            div[data-testid="stDialog"] div[role="dialog"]:has(.skyline-export-dialog-anchor) > div[data-testid="stVerticalBlock"] {
                gap: 1.1rem;
                padding-bottom: 1.6rem;
            }
            div[data-testid="stDialog"] div[role="dialog"]:has(.skyline-export-dialog-anchor) .intel-card,
            div[data-testid="stDialog"] div[role="dialog"]:has(.skyline-export-dialog-anchor) .intel-mini-note {
                border-radius: 22px;
                background: rgba(255,255,255,0.065);
                border: 1px solid rgba(255,255,255,0.08);
                box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
            }
            div[data-testid="stDialog"] div[role="dialog"]:has(.skyline-export-dialog-anchor) .skyline-export-intro-card {
                margin-top: -0.4rem;
            }
            div[data-testid="stDialog"] div[role="dialog"]:has(.skyline-export-dialog-anchor) .skyline-export-preview-card {
                padding-bottom: 1.9rem;
            }
            div[data-testid="stDialog"] div[role="dialog"]:has(.skyline-export-dialog-anchor) .skyline-export-preview-card .intel-support-grid {
                margin-bottom: 0.3rem;
            }
            div[data-testid="stDialog"] div[role="dialog"]:has(.skyline-export-dialog-anchor) .stDownloadButton {
                margin-top: 1.05rem;
                margin-bottom: 0.9rem;
            }
            div[data-testid="stDialog"] div[role="dialog"]:has(.skyline-export-dialog-anchor) p {
                line-height: 1.55;
            }
            </style>
            """
        ).strip(),
        unsafe_allow_html=True,
    )
    current_city = city_to_show or weather_to_show.get("resolved_city") or "Selected location"
    range_labels = {key: label for key, label in EXPORT_RANGE_OPTIONS}
    format_labels = {key: label for key, label in EXPORT_FORMAT_OPTIONS}

    st.markdown(
        dedent(
                f"""
            <div class="intel-card skyline-export-intro-card" style="margin-top: -0.9rem; margin-bottom: 0.3rem;">
                <div class="intel-card-kicker">Export Weather Data</div>
                <div class="intel-card-title">Create a clean weather file for {escape(current_city)}</div>
                <div class="intel-card-body">Choose a quick date window or define your own range, then export the selected period in CSV, Excel, or PDF. The export always uses the currently selected location from the home page.</div>
            </div>
            """
        ).strip(),
        unsafe_allow_html=True,
    )

    range_options = [key for key, _ in EXPORT_RANGE_OPTIONS]
    format_options = [key for key, _ in EXPORT_FORMAT_OPTIONS]
    range_index = next(
        (index for index, key in enumerate(range_options) if key == st.session_state.get("export_range")),
        0,
    )
    format_index = next(
        (index for index, key in enumerate(format_options) if key == st.session_state.get("export_format")),
        0,
    )

    controls = st.columns(2)
    custom_dates = st.session_state.get("export_custom_dates", get_default_export_custom_dates())
    with controls[0]:
        selected_range = st.selectbox(
            "Date Window",
            options=range_options,
            index=range_index,
            format_func=lambda key: range_labels[key],
            key="export_range_selector",
        )
        if selected_range == "custom_range":
            min_date, max_date = get_export_picker_bounds()
            custom_dates = st.date_input(
                "Custom Date Range",
                value=custom_dates,
                min_value=min_date,
                max_value=max_date,
                key="export_custom_dates",
            )
            st.caption(
                f"Choose up to {EXPORT_MAX_SELECTED_DAYS} days between {min_date.strftime('%b %d, %Y')} and {max_date.strftime('%b %d, %Y')}."
            )
        else:
            st.caption(
                f"Quick windows include recent history and upcoming days. Custom ranges can span up to {EXPORT_MAX_SELECTED_DAYS} days."
            )
    with controls[1]:
        selected_format = st.radio(
            "File Format",
            options=format_options,
            index=format_index,
            format_func=lambda key: format_labels[key],
            key="export_format_selector",
            horizontal=True,
        )

    st.session_state["export_range"] = selected_range
    st.session_state["export_format"] = selected_format

    try:
        artifact = build_export_download_artifact(
            weather_to_show,
            city_to_show,
            temp_symbol,
            speed_symbol,
            use_fahrenheit,
            selected_range,
            selected_format,
            custom_dates=custom_dates,
        )
    except (ValueError, ForecastDataError, WeatherError) as exc:
        st.warning(str(exc))
        return

    bundle = artifact["bundle"]

    preview_columns = st.columns([1.5, 0.9])
    with preview_columns[0]:
        st.markdown(
            dedent(
                f"""
                <div class="intel-card skyline-export-preview-card" style="margin-bottom: 0; padding-bottom: 2.15rem;">
                    <div class="intel-card-kicker">Export Preview</div>
                    <div class="intel-card-title">{escape(bundle["range_label"])} in {escape(artifact["format_label"])}</div>
                    <div class="intel-card-body">{escape(artifact["description"])}</div>
                    <div class="intel-support-grid" style="margin-bottom: 0.35rem;">
                        <div class="intel-mini-note">
                            <div class="intel-mini-note-label">Current Location</div>
                            <div class="intel-mini-note-title">{escape(current_city)}</div>
                            <div class="intel-mini-note-body">{escape(bundle["current"]["Condition"])} | {escape(bundle["current"]["Temperature"])} | {escape(bundle["current"]["Wind"])}</div>
                        </div>
                        <div class="intel-mini-note">
                            <div class="intel-mini-note-label">Included Window</div>
                            <div class="intel-mini-note-title">{escape(bundle["range_label"])}</div>
                            <div class="intel-mini-note-body">Includes {bundle["days_count"]} daily row{"s" if bundle["days_count"] != 1 else ""} across the selected weather window.</div>
                        </div>
                    </div>
                </div>
                """
            ).strip(),
            unsafe_allow_html=True,
        )
    with preview_columns[1]:
        st.markdown(
            dedent(
                f"""
                <div class="intel-card" style="margin-bottom: 0;">
                    <div class="intel-card-kicker">Download Ready</div>
                    <div class="intel-card-title">{escape(artifact["filename"])}</div>
                    <div class="intel-card-body">Generated size: {format_file_size(len(artifact["bytes"]))}</div>
                </div>
                """
            ).strip(),
            unsafe_allow_html=True,
        )
        st.download_button(
            label=f'Download {artifact["format_label"]}',
            data=artifact["bytes"],
            file_name=artifact["filename"],
            mime=artifact["mime"],
            key=f'export_download_{selected_range}_{selected_format}_{bundle["range_key"]}_{bundle["days_count"]}',
            use_container_width=True,
            type="primary",
        )
    st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)


def open_export_dialog(weather_to_show, city_to_show, temp_symbol, speed_symbol, use_fahrenheit):
    if hasattr(st, "dialog"):
        @st.dialog("Export Weather Data")
        def export_dialog():
            render_export_dialog_panel(weather_to_show, city_to_show, temp_symbol, speed_symbol, use_fahrenheit)

        export_dialog()
    else:
        with st.popover("Export", use_container_width=True):
            render_export_dialog_panel(weather_to_show, city_to_show, temp_symbol, speed_symbol, use_fahrenheit)


# Search handles validation, API errors, and persistence.
def run_weather_search(search_value, rerun_after=True, show_feedback=True):
    search_display_value = get_search_display_value(search_value)
    city_key = search_display_value.upper()

    if city_key == "":
        st.warning("Please enter a city name.")
        return

    try:
        weather = get_weather(search_value)
    except CityNotFoundError:
        st.error("City not found. Please check the spelling and try again.")
        return
    except ForecastDataError as exc:
        st.error(str(exc))
        return
    except WeatherError as exc:
        st.error(str(exc))
        return

    st.session_state["last_weather"] = weather
    st.session_state["last_city_display"] = weather["resolved_city"]
    st.session_state["last_city_key"] = weather["resolved_city"].strip().upper()
    st.session_state["city_input_value"] = weather["resolved_city"]
    reset_searchbox_state(weather["resolved_city"])

    save_last_weather_state(weather, weather["resolved_city"].strip().upper())
    remember_recent_search(weather)
    if show_feedback:
        st.success(f"Weather loaded for {weather['resolved_city']}.")
    if rerun_after:
        st.rerun()


def handle_search_component_event(search_event):
    if not isinstance(search_event, dict):
        return False

    event_id = str(search_event.get("event_id") or "").strip()
    if not event_id:
        return False

    if st.session_state.get("last_search_component_event_id") == event_id:
        return False

    st.session_state["last_search_component_event_id"] = event_id
    action = search_event.get("action")
    payload = search_event.get("payload") or {}

    if action not in {"search", "geolocation"}:
        return False

    latitude = payload.get("latitude")
    longitude = payload.get("longitude")

    if latitude is not None and longitude is not None:
        search_value = {
            "label": payload.get("label") or payload.get("query") or "Selected Location",
            "query": payload.get("query") or payload.get("label") or "Selected Location",
            "latitude": latitude,
            "longitude": longitude,
        }
    else:
        search_value = payload.get("query") or payload.get("label") or ""

    run_weather_search(search_value, rerun_after=True, show_feedback=False)
    return True


def handle_compare_search_component_event(search_event, query_state_key, selection_state_key, event_state_key):
    if not isinstance(search_event, dict):
        return False

    event_id = str(search_event.get("event_id") or "").strip()
    if not event_id:
        return False

    if st.session_state.get(event_state_key) == event_id:
        return False

    st.session_state[event_state_key] = event_id
    action = search_event.get("action")
    payload = search_event.get("payload") or {}

    if action not in {"search", "draft"}:
        return False

    next_query = get_search_display_value(payload)
    if not next_query:
        return False

    st.session_state[query_state_key] = next_query
    selection = build_location_search_entry(
        payload.get("label") or next_query,
        query=payload.get("query") or next_query,
        latitude=payload.get("latitude"),
        longitude=payload.get("longitude"),
        meta=payload.get("meta") or "Suggested location",
    )
    if selection and selection.get("latitude") is not None and selection.get("longitude") is not None:
        st.session_state[selection_state_key] = selection
    else:
        st.session_state[selection_state_key] = None
    return True


def render_search_experience():
    return SEARCH_COMPONENT(
        initial_value=st.session_state.get("search_query", ""),
        recent_searches=get_search_component_recent_entries(),
        placeholder="Search any city worldwide",
        enable_geolocation=True,
        key="skyline_search_component_recent_v2",
        default=None,
    )


def render_search_section():
    return render_search_experience()


# Header section replaces the plain title with a stronger top bar.
def render_header_section(weather_to_show, city_to_show, temp_symbol, speed_symbol, use_fahrenheit):
    export_disabled = weather_to_show is None
    active_section = st.session_state.get("active_content_section", CONTENT_SECTIONS[0])
    if active_section not in CONTENT_SECTIONS:
        active_section = CONTENT_SECTIONS[0]
    summary_columns = st.columns([1, 3.4, 1])
    with summary_columns[1]:
        render_topbar(weather_to_show, city_to_show, temp_symbol, use_fahrenheit)

    nav_container = st.container()
    with nav_container:
        st.markdown("<div class='skyline-persistent-nav-anchor' aria-hidden='true'></div>", unsafe_allow_html=True)
        logo_data_uri = "data:image/svg+xml;base64," + base64.b64encode(APP_LOGO_PATH.read_bytes()).decode("ascii")
        action_row = st.columns([1.04, 0.72, 0.7, 1.02, 0.92, 0.52, 0.76, 2.66, 0.66, 0.2], gap="small")

        with action_row[0]:
            st.markdown(
                f"<div class='skyline-nav-brand'><img src='{logo_data_uri}' alt='Skyline Forecast logo' /></div>",
                unsafe_allow_html=True,
            )

        for column, section_name in zip(action_row[1 : 1 + len(CONTENT_SECTIONS)], CONTENT_SECTIONS):
            section_key = section_name.lower().replace(" ", "_")
            button_type = "primary" if section_name == active_section else "secondary"
            with column:
                if st.button(section_name, key=f"content_section_{section_key}", type=button_type, use_container_width=True, disabled=export_disabled):
                    st.session_state["active_content_section"] = section_name
                    st.rerun()

        with action_row[8]:
            if st.button("Export", key="export_button", type="secondary", use_container_width=True, disabled=export_disabled):
                st.session_state["show_export_dialog"] = True

        with action_row[9]:
            if st.button("\u2699", key="gear_button", help="Settings", type="secondary", use_container_width=True):
                st.session_state["show_settings_dialog"] = True

    render_persistent_nav_bridge()

    if st.session_state.get("show_export_dialog") and weather_to_show:
        st.session_state["show_export_dialog"] = False
        open_export_dialog(weather_to_show, city_to_show, temp_symbol, speed_symbol, use_fahrenheit)

    if st.session_state.get("show_settings_dialog"):
        st.session_state["show_settings_dialog"] = False
        open_settings()
    if st.session_state.get("show_personalization_dialog"):
        st.session_state["show_personalization_dialog"] = False
        open_personalization_dialog()


# Current conditions keeps the common data always visible.
def render_current_conditions_section(weather_to_show, speed_symbol, converted_wind, temp_symbol, use_fahrenheit):
    current = weather_to_show["current"]
    today = weather_to_show["forecast"][0] if weather_to_show["forecast"] else None
    display_temperature = (
        round(celsius_to_fahrenheit(current["temperature"]), 1)
        if use_fahrenheit
        else current["temperature"]
    )
    display_feels_like = (
        round(celsius_to_fahrenheit(current["feels_like"]), 1)
        if use_fahrenheit
        else current["feels_like"]
    )

    render_insight_section_header(
        "Current Conditions",
        "Tap any glass card to expand the secondary details connected to that metric.",
        "Live Snapshot",
    )

    row1 = st.columns(4)
    with row1[0]:
        render_expandable_metric_card(
            "Temperature",
            f"{get_temp_icon(current['temperature'])} {display_temperature}{temp_symbol}",
            current["condition"],
            [
                f"Feels like {display_feels_like}{temp_symbol}",
                f"Today's high {round(celsius_to_fahrenheit(today['max']), 1) if use_fahrenheit and today else today['max'] if today else '--'}{temp_symbol}",
                f"Today's low {round(celsius_to_fahrenheit(today['min']), 1) if use_fahrenheit and today else today['min'] if today else '--'}{temp_symbol}",
            ],
        )
    with row1[1]:
        render_expandable_metric_card(
            "Feels Like",
            f"{get_feels_like_icon(current['feels_like'])} {display_feels_like}{temp_symbol}",
            "How it feels outside",
            [
                f"Cloud cover {current['cloud_cover']}%",
                f"Visibility {current['visibility']} km",
                f"Pressure {current['pressure']} hPa",
            ],
        )
    with row1[2]:
        render_expandable_metric_card(
            "Humidity",
            f"{get_humidity_icon(current['humidity'])} {current['humidity']}%",
            "Air moisture right now",
            [
                f"Rain chance {today['rain_chance'] if today else 0}%",
                f"Rain volume {format_precipitation(today['rain_total'] if today else 0)}",
                f"Current precipitation {format_precipitation(current['precipitation'])}",
            ],
        )
    with row1[3]:
        render_expandable_metric_card(
            "Wind",
            f"{get_wind_icon(current['wind'])} {converted_wind} {speed_symbol}",
            "10m wind speed",
            [
                f"Sunrise {today['sunrise'] if today else '--'}",
                f"Sunset {today['sunset'] if today else '--'}",
                f"UV index {today['uv_index'] if today else 0}",
            ],
        )

def build_overview_preview_items(intelligence_payload):
    preview_items = []
    activity_items = intelligence_payload.get("activities", [])
    clothing_items = intelligence_payload.get("clothing", [])
    clothing_quick_read = intelligence_payload.get("clothing_quick_read") or []
    routine_items = (intelligence_payload.get("routine_scheduler") or {}).get("summary_items", [])
    personalization = get_personalization_profile(intelligence_payload.get("personalization"))
    focus_title = PERSONAL_ROUTINE_TITLE_MAP.get(personalization.get("activity_focus_key"))
    focus_item = next((item for item in routine_items if item.get("title") == focus_title), None)

    if focus_item:
        preview_items.append(
            {
                "title": "🎯 Your Focus",
                "body": tighten_preview_copy(focus_item["body"], max_length=112),
            }
        )
    elif activity_items:
        preview_items.append(
            {
                "title": "🚶 Walking",
                "body": tighten_preview_copy(activity_items[0]["body"], max_length=112),
            }
        )
    if clothing_quick_read:
        preview_items.append(
            {
                "title": "👕 What To Wear",
                "body": tighten_preview_copy(clothing_quick_read[0]["body"], max_length=110),
            }
        )
    elif clothing_items:
        preview_items.append(
            {
                "title": "👕 What To Wear",
                "body": tighten_preview_copy(clothing_items[0]["body"], max_length=110),
            }
        )

    return preview_items


def render_insight_section_header(title, subtitle, kicker):
    st.markdown(
        f"""
        <div class="insight-section-header">
            <div class="insight-section-kicker">{escape(kicker)}</div>
            <div class="insight-section-title">{escape(title)}</div>
            <div class="insight-section-subtitle">{escape(subtitle)}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_soft_section_divider(variant="default"):
    divider_class = "section-divider"
    if variant == "persistent":
        divider_class += " section-divider--persistent"
    st.markdown(f"<div class='{divider_class}'></div>", unsafe_allow_html=True)


def build_insights_quick_read_items(intelligence_payload):
    quick_items = []
    insights = intelligence_payload.get("insights", [])
    trend_card = next((item for item in insights if item.get("eyebrow") == "Forecast Trend"), None)
    if trend_card:
        quick_items.append({"title": "📈 Forecast Trend", "body": tighten_preview_copy(trend_card["body"], max_length=118)})

    routine_scheduler = intelligence_payload.get("routine_scheduler") or {}
    routine_items = routine_scheduler.get("summary_items", [])
    personalization = get_personalization_profile(intelligence_payload.get("personalization"))
    focus_title = PERSONAL_ROUTINE_TITLE_MAP.get(personalization.get("activity_focus_key"))
    focus_item = next((item for item in routine_items if item.get("title") == focus_title), None)
    walking_item = next((item for item in routine_items if item.get("title") == "Walking"), None)
    if focus_item:
        quick_items.append({"title": "🎯 Your Focus", "body": tighten_preview_copy(focus_item["body"], max_length=108)})
    elif walking_item:
        quick_items.append({"title": "🌤️ Best Outdoor Window", "body": tighten_preview_copy(walking_item["body"], max_length=108)})

    avoid_item = next((item for item in routine_items if item.get("title") == "Avoid Times"), None)
    if avoid_item and "No major avoid window" not in avoid_item.get("body", ""):
        quick_items.append({"title": "⚠️ Watch First", "body": tighten_preview_copy(avoid_item["body"], max_length=108)})
    else:
        scores = intelligence_payload.get("scores", [])
        if scores:
            strongest_score = max(scores, key=lambda score: score.get("value", 0))
            weakest_score = min(scores, key=lambda score: score.get("value", 0))
            if weakest_score.get("value", 0) <= 6:
                quick_items.append(
                    {
                        "title": "⚠️ Main Watch-Out",
                        "body": tighten_preview_copy(
                            f"{weakest_score['label']} is the softer signal at {weakest_score['value']}/10. "
                            f"{weakest_score['summary']}"
                        ),
                    }
                )
            else:
                quick_items.append(
                    {
                        "title": "✨ Current Edge",
                        "body": tighten_preview_copy(
                            f"{strongest_score['label']} leads at {strongest_score['value']}/10. "
                            f"{strongest_score['summary']}"
                        ),
                    }
                )

    return quick_items[:3]


def build_activities_quick_read_items(intelligence_payload):
    quick_items = []
    activities = intelligence_payload.get("activities", [])
    activity_map = {item.get("item_id"): item for item in activities}
    routine_items = (intelligence_payload.get("routine_scheduler") or {}).get("summary_items", [])
    personalization = get_personalization_profile(intelligence_payload.get("personalization"))
    focus_title = PERSONAL_ROUTINE_TITLE_MAP.get(personalization.get("activity_focus_key"))
    focus_item = next((item for item in routine_items if item.get("title") == focus_title), None)
    if focus_item:
        quick_items.append({"title": "🎯 Your Focus", "body": tighten_preview_copy(focus_item["body"], max_length=108)})
    walking_item = activity_map.get("walking")
    running_item = activity_map.get("running")
    travel_item = activity_map.get("travel")
    if walking_item:
        quick_items.append({"title": "🚶 Walking", "body": tighten_preview_copy(walking_item["body"], max_length=108)})
    if running_item:
        quick_items.append({"title": "🏃 Outdoor Effort", "body": tighten_preview_copy(running_item["body"], max_length=108)})
    if travel_item:
        quick_items.append({"title": "🧭 Travel", "body": tighten_preview_copy(travel_item["body"], max_length=108)})
    return quick_items[:3]


def render_overview_tab(weather_to_show, intelligence_payload, city_to_show, temp_symbol, use_fahrenheit):
    time_context = intelligence_payload.get("time_context") or {}
    render_weather_alert_banner(intelligence_payload.get("alerts", []))
    render_soft_section_divider()
    render_insight_section_header(
        "Overview",
        f"Start with the strongest signal for {time_context.get('phase_reference', 'right now')}, then use the quick action preview underneath to decide what to do next.",
        "At A Glance",
    )
    render_todays_insight_card(
        intelligence_payload.get("city") or city_to_show,
        intelligence_payload.get("condition"),
        intelligence_payload.get("insights", []),
        show_supporting_notes=False,
        style_variant="insight-readable",
        time_note=time_context.get("time_note"),
    )
    render_soft_section_divider()
    render_insight_section_header(
        "Next Best Actions",
        f"This keeps the overview short: one quick movement signal and one practical clothing takeaway for {time_context.get('phase_reference', 'the current window')} instead of multiple full sections.",
        "Quick Moves",
    )
    render_recommendation_card(
        "Recommendation preview",
        "Quick Scan",
        build_overview_preview_items(intelligence_payload),
        style_variant="insight-readable",
    )


def render_insights_tab(intelligence_payload):
    time_context = intelligence_payload.get("time_context") or {}
    quick_read_items = build_insights_quick_read_items(intelligence_payload)
    if quick_read_items:
        render_insight_section_header(
            "Quick Read",
            f"Start with the highest-signal takeaways for {time_context.get('phase_reference', 'right now')} before moving into the detailed weather explanation below.",
            "Scan First",
        )
        render_recommendation_card(
            "What matters most right now",
            "Fast Scan",
            quick_read_items,
            style_variant="insight-readable",
        )

    detail_insights = [
        item for item in intelligence_payload.get("insights", [])
        if item.get("eyebrow") != "Forecast Trend"
    ]
    if detail_insights:
        render_soft_section_divider()
        render_insight_section_header(
            "Weather Interpretation",
            f"Feels-like, humidity, and wind are now read through the local clock, so each signal is easier to understand for {time_context.get('phase_reference', 'the current window')}.",
            "Read Next",
        )
        render_guidance_card_grid(detail_insights, grid_variant="insight-readable")

    routine_scheduler = intelligence_payload.get("routine_scheduler") or {}
    if routine_scheduler.get("summary_items"):
        render_soft_section_divider()
        render_insight_section_header(
            "Daily Routine Recommendations",
            f"Hourly scoring is now weighted from {time_context.get('phase_reference', 'now')} forward, so the routine planner stays relevant instead of showing stale earlier blocks.",
            "Smart Scheduler",
        )
        render_recommendation_card(
            "Best time blocks today",
            "Smart Scheduler",
            routine_scheduler.get("summary_items", []),
            style_variant="insight-readable",
        )

    render_soft_section_divider()
    render_insight_section_header(
        "Weather Scores",
        f"Comfort, outdoor conditions, and travel readiness now shift with local time, not just the overall daily forecast.",
        "Scored View",
    )
    render_weather_score_row(intelligence_payload.get("scores", []), card_variant="insight-readable")


def render_clothing_tab(intelligence_payload):
    time_context = intelligence_payload.get("time_context") or {}
    render_insight_section_header(
        "What To Wear",
        f"Start with the outfit read for {time_context.get('phase_reference', 'right now')}. The base look and refreshable visuals now shift with the local time block instead of staying static all day.",
        "Style Guide",
    )
    quick_read = intelligence_payload.get("clothing_quick_read") or []
    if quick_read:
        render_recommendation_card(
            "Wear right now",
            "Time-Aware",
            quick_read,
            style_variant="insight-readable",
        )
    render_soft_section_divider()
    render_insight_section_header(
        "Core Pieces",
        "These visual pieces are tuned to the current local block, so the base outfit and starting visuals change with the clock.",
        "Base Outfit",
    )
    render_visual_clothing_grid(intelligence_payload.get("clothing", []), state_prefix="wear-core")


def render_trip_planner_section(temp_symbol, speed_symbol, use_fahrenheit):
    render_soft_section_divider()
    render_insight_section_header(
        "Packing / Trip Planner",
        "Set an optional starting point, choose a destination, and export the full trip plan as a clean PDF instead of opening a large on-page result.",
        "Trip Export",
    )

    route_columns = st.columns(2)
    with route_columns[0]:
        st.markdown("<div class='intel-card-kicker' style='margin-bottom: 0.35rem;'>Starting Location (Optional)</div>", unsafe_allow_html=True)
        origin_event = SEARCH_COMPONENT(
            initial_value=st.session_state.get("trip_planner_origin_query", ""),
            recent_searches=get_search_component_recent_entries(),
            placeholder="Where the trip starts",
            enable_geolocation=False,
            key="trip_planner_origin_search_component",
            default=None,
        )
        handle_compare_search_component_event(
            origin_event,
            "trip_planner_origin_query",
            "trip_planner_origin_selection",
            "trip_planner_origin_search_event_id",
        )
    with route_columns[1]:
        st.markdown("<div class='intel-card-kicker' style='margin-bottom: 0.35rem;'>Destination</div>", unsafe_allow_html=True)
        destination_event = SEARCH_COMPONENT(
            initial_value=st.session_state.get("trip_planner_destination_query", ""),
            recent_searches=get_search_component_recent_entries(),
            placeholder="Where the trip ends",
            enable_geolocation=False,
            key="trip_planner_destination_search_component",
            default=None,
        )
        handle_compare_search_component_event(
            destination_event,
            "trip_planner_destination_query",
            "trip_planner_destination_selection",
            "trip_planner_destination_search_event_id",
        )

    min_date, max_date = get_trip_planner_picker_bounds()
    date_columns = st.columns(2)
    with date_columns[0]:
        start_date = st.date_input(
            "Start Date",
            value=st.session_state.get("trip_planner_start_date"),
            min_value=min_date,
            max_value=max_date,
            key="trip_planner_start_date",
        )
    with date_columns[1]:
        end_date = st.date_input(
            "End Date",
            value=st.session_state.get("trip_planner_end_date"),
            min_value=min_date,
            max_value=max_date,
            key="trip_planner_end_date",
        )

    st.caption(
        f"Trip forecasts are currently available from {min_date.strftime('%b %d, %Y')} through {max_date.strftime('%b %d, %Y')}."
    )

    create_trip_pdf = st.button(
        "Create Trip Plan PDF",
        key="trip_planner_build_button",
        type="primary",
        use_container_width=True,
    )

    if create_trip_pdf:
        origin_query = str(st.session_state.get("trip_planner_origin_query") or "").strip()
        origin_selection = st.session_state.get("trip_planner_origin_selection")
        destination_query = str(st.session_state.get("trip_planner_destination_query") or "").strip()
        destination_selection = st.session_state.get("trip_planner_destination_selection")

        try:
            with st.spinner("Creating trip plan PDF..."):
                artifact = build_trip_plan_pdf_artifact(
                    origin_query,
                    origin_selection,
                    destination_query,
                    destination_selection,
                    start_date,
                    end_date,
                    temp_symbol,
                    speed_symbol,
                    use_fahrenheit,
                )
            st.session_state["trip_planner_error"] = ""

            origin_weather = artifact.get("origin_weather")
            destination_weather = artifact.get("destination_weather")
            if origin_weather:
                st.session_state["trip_planner_origin_query"] = origin_weather.get("resolved_city") or origin_query
                st.session_state["trip_planner_origin_selection"] = build_weather_search_entry(origin_weather, meta="Recent search")
                remember_recent_search(origin_weather)
            if destination_weather:
                st.session_state["trip_planner_destination_query"] = destination_weather.get("resolved_city") or destination_query
                st.session_state["trip_planner_destination_selection"] = build_weather_search_entry(destination_weather, meta="Recent search")
                remember_recent_search(destination_weather)

            download_payload = {
                "href": build_data_uri(artifact["bytes"], "application/pdf"),
                "filename": artifact["filename"],
            }
            components.html(
                f"""
                <html>
                  <body style="margin:0;background:transparent;">
                    <script>
                      const payload = {json.dumps(download_payload)};
                      const link = document.createElement("a");
                      link.href = payload.href;
                      link.download = payload.filename;
                      document.body.appendChild(link);
                      link.click();
                      setTimeout(() => link.remove(), 0);
                    </script>
                  </body>
                </html>
                """,
                height=0,
            )
        except (ValueError, CityNotFoundError, ForecastDataError, WeatherError) as exc:
            st.session_state["trip_planner_error"] = str(exc)

    trip_planner_error = str(st.session_state.get("trip_planner_error") or "").strip()
    if trip_planner_error:
        st.warning(trip_planner_error)


def render_activities_tab(intelligence_payload, temp_symbol, speed_symbol, use_fahrenheit):
    time_context = intelligence_payload.get("time_context") or {}
    local_highlights = intelligence_payload.get("local_highlights") or []
    render_insight_section_header(
        "Activity Recommendations",
        f"This section now leads with a short activity scan for {time_context.get('phase_reference', 'right now')}, then keeps the detailed guidance and trip tools below.",
        "Move Smart",
    )
    quick_items = build_activities_quick_read_items(intelligence_payload)
    if quick_items:
        render_recommendation_card(
            "Activity quick read",
            "Fast Scan",
            quick_items,
            style_variant="insight-readable",
        )
        render_soft_section_divider()
        render_insight_section_header(
            "Detailed Activity Guidance",
            f"Shorter reads for walking, exercise, indoor backup, and travel, all tuned to {time_context.get('phase_reference', 'the local time window')}.",
            "Read Next",
        )
    render_guidance_card_grid(intelligence_payload.get("activities", []), grid_variant="insight-readable")
    if local_highlights:
        render_soft_section_divider()
        render_insight_section_header(
            "Local Highlights",
            "Live nearby place picks, weighted toward the current weather, with a direct handoff into Google Maps.",
            "Go Nearby",
        )
        render_recommendation_card(
            "Where to go nearby",
            "Weather-Aware Places",
            local_highlights,
            style_variant="insight-readable",
        )
    render_trip_planner_section(temp_symbol, speed_symbol, use_fahrenheit)


def render_map_tab(weather_to_show, temp_symbol, speed_symbol, use_fahrenheit):
    render_insight_section_header(
        "Weather Map",
        "Switch between multiple live layers here, including clouds, temperature, rain, wind, and additional map views.",
        "Live Layers",
    )
    render_live_weather_map(
        weather_to_show,
        temp_symbol,
        speed_symbol,
        use_fahrenheit,
        show_controls=True,
        expanded=True,
        preferred_layer=st.session_state.get("weather_map_layer", MAP_LAYER_OPTIONS[0]),
    )


def build_compare_time_summary(primary_weather, secondary_weather, temp_symbol, speed_symbol, use_fahrenheit):
    personalization = get_personalization_profile()
    primary_context = build_local_time_context(primary_weather)
    secondary_context = build_local_time_context(secondary_weather)
    primary_scores = calculate_weather_scores(primary_weather, primary_context)
    secondary_scores = calculate_weather_scores(secondary_weather, secondary_context)
    primary_city = (primary_weather.get("resolved_city") or "First city").split(",")[0].strip()
    secondary_city = (secondary_weather.get("resolved_city") or "Second city").split(",")[0].strip()

    if primary_scores["outdoor"] >= secondary_scores["outdoor"]:
        edge_city = primary_city
        edge_context = primary_context
    else:
        edge_city = secondary_city
        edge_context = secondary_context

    return [
        {
            "title": "Local Time Split",
            "body": (
                f"{primary_city} is at {primary_context['local_time_label']} ({primary_context['phase_reference']}) while "
                f"{secondary_city} is at {secondary_context['local_time_label']} ({secondary_context['phase_reference']})."
            ),
        },
        {
            "title": "Immediate Outdoor Edge",
            "body": (
                f"For {personalization['preferred_time'].lower()} plans, {edge_city} has the cleaner immediate outdoor setup."
                if personalization.get("preferred_time_key")
                else f"{edge_city} has the cleaner immediate outdoor setup because its local-time score is stronger for {edge_context['phase_reference']}."
            ),
        },
        {
            "title": "Next Shift",
            "body": f"{primary_city} next leans into {primary_context['next_phase_reference']}, while {secondary_city} moves toward {secondary_context['next_phase_reference']}.",
        },
    ]


def build_compare_city_card(weather, city_name, temp_symbol, speed_symbol, use_fahrenheit, label):
    display_city = city_name.split(",")[0].strip() if city_name else "Selected city"
    time_context = build_local_time_context(weather)
    current = weather.get("current") or {}
    snapshot = resolve_context_snapshot(weather, time_context)
    display_temperature = (
        format_temperature_text(snapshot.get("temperature", 0), temp_symbol, use_fahrenheit)
        if snapshot.get("temperature") is not None
        else f"--{temp_symbol}"
    )
    display_feels_like = (
        format_temperature_text(current.get("feels_like", 0), temp_symbol, use_fahrenheit)
        if current.get("feels_like") is not None
        else f"--{temp_symbol}"
    )
    humidity_value = f"{snapshot.get('humidity')}%" if snapshot.get("humidity") is not None else "--"
    condition_text = f"{snapshot.get('condition') or 'Current conditions'} {time_context['phase_reference']}"
    return dedent(
        f"""
        <div class="intel-card">
            <div class="intel-card-kicker">{escape(label)}</div>
            <div class="intel-card-title">{escape(display_city)}</div>
            <div class="intel-card-body">{escape(condition_text)}</div>
            <div class="intel-support-grid">
                <div class="intel-mini-note">
                    <div class="intel-mini-note-label">Local Time</div>
                    <div class="intel-mini-note-title">{escape(time_context['local_time_label'])}</div>
                </div>
                <div class="intel-mini-note">
                    <div class="intel-mini-note-label">Temperature</div>
                    <div class="intel-mini-note-title">{escape(display_temperature)}</div>
                </div>
                <div class="intel-mini-note">
                    <div class="intel-mini-note-label">Feels Like</div>
                    <div class="intel-mini-note-title">{escape(display_feels_like)}</div>
                </div>
                <div class="intel-mini-note">
                    <div class="intel-mini-note-label">Humidity</div>
                    <div class="intel-mini-note-title">{escape(humidity_value)}</div>
                </div>
            </div>
        </div>
        """
    ).strip()


def render_compare_tab(weather_to_show, city_to_show, temp_symbol, speed_symbol, use_fahrenheit):
    render_insight_section_header(
        "Compare Two Cities",
        "Compare two cities side by side without changing the main city shown across the rest of the app.",
        "Side By Side",
    )

    auto_primary_city = city_to_show or weather_to_show.get("resolved_city") or "Current city"
    if st.session_state.get("compare_primary_city_seed") != auto_primary_city:
        st.session_state["compare_primary_city_query"] = auto_primary_city
        st.session_state["compare_primary_city_seed"] = auto_primary_city
        st.session_state["compare_primary_city_selection"] = build_weather_search_entry(weather_to_show, meta="Current city")
        st.session_state["compare_primary_weather"] = weather_to_show

    input_columns = st.columns(2)
    with input_columns[0]:
        primary_event = SEARCH_COMPONENT(
            initial_value=st.session_state.get("compare_primary_city_query", ""),
            recent_searches=get_search_component_recent_entries(),
            placeholder="First city",
            enable_geolocation=False,
            key="compare_primary_city_search_component",
            default=None,
        )
        handle_compare_search_component_event(
            primary_event,
            "compare_primary_city_query",
            "compare_primary_city_selection",
            "compare_primary_search_event_id",
        )
        primary_query = st.session_state.get("compare_primary_city_query", "")
    with input_columns[1]:
        secondary_event = SEARCH_COMPONENT(
            initial_value=st.session_state.get("compare_secondary_city_query", ""),
            recent_searches=get_search_component_recent_entries(),
            placeholder="Second city",
            enable_geolocation=False,
            key="compare_secondary_city_search_component",
            default=None,
        )
        handle_compare_search_component_event(
            secondary_event,
            "compare_secondary_city_query",
            "compare_secondary_city_selection",
            "compare_secondary_search_event_id",
        )
        secondary_query = st.session_state.get("compare_secondary_city_query", "")

    if st.button("Compare Cities", key="compare_city_button", type="secondary", use_container_width=False):
        if not primary_query.strip() or not secondary_query.strip():
            st.warning("Enter both cities to compare.")
        else:
            try:
                primary_selection = st.session_state.get("compare_primary_city_selection")
                secondary_selection = st.session_state.get("compare_secondary_city_selection")
                primary_search_value = (
                    primary_selection
                    if primary_selection
                    and primary_query.strip().lower() in {
                        str(primary_selection.get("label") or "").strip().lower(),
                        str(primary_selection.get("query") or "").strip().lower(),
                    }
                    else primary_query.strip()
                )
                secondary_search_value = (
                    secondary_selection
                    if secondary_selection
                    and secondary_query.strip().lower() in {
                        str(secondary_selection.get("label") or "").strip().lower(),
                        str(secondary_selection.get("query") or "").strip().lower(),
                    }
                    else secondary_query.strip()
                )

                primary_weather = (
                    weather_to_show
                    if primary_query.strip().lower() == auto_primary_city.strip().lower()
                    else get_weather(primary_search_value)
                )
                secondary_weather = get_weather(secondary_search_value)
                st.session_state["compare_primary_city_query"] = primary_weather.get("resolved_city") or primary_query.strip()
                st.session_state["compare_secondary_city_query"] = secondary_weather.get("resolved_city") or secondary_query.strip()
                st.session_state["compare_primary_city_selection"] = build_weather_search_entry(primary_weather, meta="Recent search")
                st.session_state["compare_secondary_city_selection"] = build_weather_search_entry(secondary_weather, meta="Recent search")
                st.session_state["compare_primary_weather"] = primary_weather
                st.session_state["compare_secondary_weather"] = secondary_weather
                remember_recent_search(primary_weather)
                remember_recent_search(secondary_weather)
            except WeatherError as exc:
                st.error(str(exc))

    primary_weather = st.session_state.get("compare_primary_weather") or weather_to_show
    secondary_weather = st.session_state.get("compare_secondary_weather")
    if not secondary_weather:
        st.info("Load a second city to compare it with the current city.")
        return

    primary_city = primary_weather.get("resolved_city") or auto_primary_city
    compare_city = secondary_weather.get("resolved_city") or "Comparison city"

    render_soft_section_divider()
    hero_columns = st.columns(2)
    with hero_columns[0]:
        st.markdown(
            build_compare_city_card(primary_weather, primary_city, temp_symbol, speed_symbol, use_fahrenheit, "First city"),
            unsafe_allow_html=True,
        )
    with hero_columns[1]:
        st.markdown(
            build_compare_city_card(secondary_weather, compare_city, temp_symbol, speed_symbol, use_fahrenheit, "Second city"),
            unsafe_allow_html=True,
        )

    render_soft_section_divider()
    render_insight_section_header(
        "Local Time Comparison",
        "Each city is read in its own local clock, so morning, evening, and night are not treated like the same planning window.",
        "Clock-Aware",
    )
    render_recommendation_card(
        "How the cities differ right now",
        "Clock-Aware",
        build_compare_time_summary(primary_weather, secondary_weather, temp_symbol, speed_symbol, use_fahrenheit),
        style_variant="insight-readable",
    )

    render_soft_section_divider()
    forecast_columns = st.columns(2)
    with forecast_columns[0]:
        render_forecast_section(
            primary_weather,
            temp_symbol,
            use_fahrenheit,
            day_limit=5,
            section_title=f"{primary_city.split(',')[0].strip()} 5-Day Forecast",
            section_subtitle="Tap any day to open the full forecast detail view for that date.",
            instance_id="compare_primary",
        )
    with forecast_columns[1]:
        render_forecast_section(
            secondary_weather,
            temp_symbol,
            use_fahrenheit,
            day_limit=5,
            section_title=f"{compare_city.split(',')[0].strip()} 5-Day Forecast",
            section_subtitle="Tap any day to open the full forecast detail view for that date.",
            instance_id="compare_secondary",
        )

    trend_items = []
    for label, weather in [("First city", primary_weather), ("Second city", secondary_weather)]:
        trend_card = build_forecast_trend_insight(weather, temp_symbol, use_fahrenheit)
        if trend_card:
            trend_items.append({"title": f"{label}: {trend_card['title']}", "body": trend_card["body"]})
    if trend_items:
        render_soft_section_divider()
        render_insight_section_header(
            "Forecast Trend Comparison",
            "This keeps the side-by-side read focused on the biggest forecast shift instead of making you scan both columns again.",
            "Trend Snapshot",
        )
        render_recommendation_card("Forecast Trend Comparison", "Trend Snapshot", trend_items, style_variant="insight-readable")


def render_weather_tabbed_section(weather_to_show, city_to_show, temp_symbol, speed_symbol, use_fahrenheit):
    intelligence_payload = build_weather_intelligence_payload(
        weather_to_show,
        city_to_show,
        temp_symbol,
        speed_symbol,
        use_fahrenheit,
    )
    active_section = st.session_state.get("active_content_section", CONTENT_SECTIONS[0])
    if active_section not in CONTENT_SECTIONS:
        active_section = CONTENT_SECTIONS[0]
        st.session_state["active_content_section"] = active_section

    if active_section == "Overview":
        render_overview_tab(weather_to_show, intelligence_payload, city_to_show, temp_symbol, use_fahrenheit)
    elif active_section == "Insights":
        render_insights_tab(intelligence_payload)
    elif active_section == "What to Wear":
        render_clothing_tab(intelligence_payload)
    elif active_section == "Activities":
        render_activities_tab(intelligence_payload, temp_symbol, speed_symbol, use_fahrenheit)
    elif active_section == "Map":
        render_map_tab(weather_to_show, temp_symbol, speed_symbol, use_fahrenheit)
    elif active_section == "Compare":
        render_compare_tab(weather_to_show, city_to_show, temp_symbol, speed_symbol, use_fahrenheit)


# Forecast rows sit directly under current conditions with a lighter visual style.
def _legacy_render_forecast_section(weather_to_show, temp_symbol, use_fahrenheit):
    forecast = weather_to_show["forecast"]

    render_insight_section_header(
        "10-Day Forecast",
        "Tap any day to open the full forecast detail view for that date.",
        "Forecast View",
    )

    if len(forecast) < 10:
        st.warning("Forecast data is partially available right now.")

    low_values = []
    high_values = []
    for day in forecast[:day_limit]:
        low_value = round(celsius_to_fahrenheit(day["min"]), 1) if use_fahrenheit else day["min"]
        high_value = round(celsius_to_fahrenheit(day["max"]), 1) if use_fahrenheit else day["max"]
        low_values.append(low_value)
        high_values.append(high_value)

    overall_low = min(low_values) if low_values else 0
    overall_high = max(high_values) if high_values else 1
    spread = max(overall_high - overall_low, 1)

    forecast_rows = []
    for index, day in enumerate(forecast[:day_limit]):
        low_value = low_values[index]
        high_value = high_values[index]
        fill_percent = ((high_value - overall_low) / spread) * 100
        forecast_rows.append(
            build_forecast_row(
                day["day"],
                day["condition"],
                low_value,
                high_value,
                temp_symbol,
                fill_percent,
                forecast_index=index,
            )
        )

    render_forecast_list(forecast_rows)


def build_hourly_temperature_chart(hourly_points, use_fahrenheit, temp_symbol):
    if not hourly_points:
        return dedent(
            """
            <div class="forecast-chart-empty">
                Hourly temperature detail is unavailable for this day right now.
            </div>
            """
        ).strip()

    chart_points = []
    for point in hourly_points:
        display_temp = round(celsius_to_fahrenheit(point["temperature"]), 1) if use_fahrenheit else point["temperature"]
        chart_points.append({"time": point["time"], "temperature": display_temp})

    temperatures = [point["temperature"] for point in chart_points]
    min_temp = min(temperatures)
    max_temp = max(temperatures)
    temp_range = max(max_temp - min_temp, 1)
    width = 900
    height = 220
    padding_left = 44
    padding_right = 18
    padding_top = 20
    padding_bottom = 34
    usable_width = width - padding_left - padding_right
    usable_height = height - padding_top - padding_bottom

    svg_points = []
    for index, point in enumerate(chart_points):
        x_position = padding_left if len(chart_points) == 1 else padding_left + (usable_width * index / (len(chart_points) - 1))
        y_position = padding_top + ((max_temp - point["temperature"]) / temp_range) * usable_height
        svg_points.append((x_position, y_position, point))

    polyline_points = " ".join(f"{x:.2f},{y:.2f}" for x, y, _ in svg_points)
    area_points = (
        f"{padding_left},{padding_top + usable_height} "
        + polyline_points
        + f" {svg_points[-1][0]:.2f},{padding_top + usable_height}"
    )
    grid_lines = []
    y_axis_labels = []
    for step in range(5):
        y_position = padding_top + (usable_height * step / 4)
        label_value = max_temp - ((temp_range * step) / 4)
        grid_lines.append(
            f'<line x1="{padding_left}" y1="{y_position:.2f}" x2="{width - padding_right}" y2="{y_position:.2f}" />'
        )
        y_axis_labels.append(
            f'<text x="10" y="{y_position + 4:.2f}">{label_value:.1f}{temp_symbol.strip()}</text>'
        )
    x_labels = []
    step_size = max(1, len(svg_points) // 6)
    for index, (x_position, _, point) in enumerate(svg_points):
        if index % step_size != 0 and index != len(svg_points) - 1:
            continue
        x_labels.append(
            f'<text x="{x_position:.2f}" y="{height - 18}" text-anchor="middle">{point["time"]}</text>'
        )
    dot_markup = "".join(
        f'<circle cx="{x_position:.2f}" cy="{y_position:.2f}" r="4" />'
        for x_position, y_position, _ in svg_points
    )
    dot_labels = "".join(
        f'<text x="{x_position:.2f}" y="{y_position - 10:.2f}" text-anchor="middle">{point["temperature"]:.1f}{temp_symbol.strip()}</text>'
        for x_position, y_position, point in svg_points
    )
    svg_markup = dedent(
        f"""
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" preserveAspectRatio="none" aria-label="Hourly temperature chart">
            <defs>
                <linearGradient id="forecast-temp-area" x1="0" x2="0" y1="0" y2="1">
                    <stop offset="0%" stop-color="#FFE292" stop-opacity="0.48" />
                    <stop offset="100%" stop-color="#FFE292" stop-opacity="0.02" />
                </linearGradient>
            </defs>
            <g stroke="rgba(255,255,255,0.12)" stroke-width="1" fill="none">
                {''.join(grid_lines)}
            </g>
            <g fill="rgba(242,248,255,0.76)" font-size="11" font-family="Segoe UI, sans-serif">
                {''.join(y_axis_labels)}
            </g>
            <polygon points="{area_points}" fill="url(#forecast-temp-area)" />
            <polyline points="{polyline_points}" fill="none" stroke="#FFE292" stroke-width="3" stroke-linecap="round" stroke-linejoin="round" />
            <g fill="#F6FBFF" stroke="#FFE292" stroke-width="2">
                {dot_markup}
            </g>
            <g fill="rgba(242,248,255,0.76)" font-size="11" font-family="Segoe UI, sans-serif">
                {dot_labels}
                {''.join(x_labels)}
            </g>
        </svg>
        """
    ).strip()
    svg_encoded = base64.b64encode(svg_markup.encode("utf-8")).decode("ascii")
    return dedent(
        f"""
        <div class="forecast-chart-shell">
            <div class="forecast-chart-title">Temperature through the day</div>
            <img class="forecast-chart-image" src="data:image/svg+xml;base64,{svg_encoded}" alt="Hourly temperature chart" />
        </div>
        """
    ).strip()


def calculate_daylight_duration(sunrise, sunset):
    try:
        sunrise_time = datetime.strptime(sunrise, "%I:%M %p")
        sunset_time = datetime.strptime(sunset, "%I:%M %p")
    except (TypeError, ValueError):
        return "--"

    total_minutes = int((sunset_time - sunrise_time).total_seconds() // 60)
    if total_minutes <= 0:
        return "--"

    hours, minutes = divmod(total_minutes, 60)
    return f"{hours}h {minutes}m"


def build_forecast_modal_markup(day, temp_symbol, speed_symbol, use_fahrenheit):
    low_value = round(celsius_to_fahrenheit(day["min"]), 1) if use_fahrenheit else day["min"]
    high_value = round(celsius_to_fahrenheit(day["max"]), 1) if use_fahrenheit else day["max"]
    hourly_points = day.get("hourly") or []
    hourly_snapshot = hourly_points[len(hourly_points) // 2] if hourly_points else {}
    snapshot_temperature = (
        round(celsius_to_fahrenheit(hourly_snapshot["temperature"]), 1)
        if hourly_snapshot and use_fahrenheit
        else hourly_snapshot.get("temperature", "--")
        if hourly_snapshot
        else "--"
    )
    snapshot_wind = (
        round(kmh_to_mph(hourly_snapshot["wind"]), 1)
        if hourly_snapshot and speed_symbol == "mph"
        else hourly_snapshot.get("wind", "--")
        if hourly_snapshot
        else "--"
    )
    daylight_duration = calculate_daylight_duration(day["sunrise"], day["sunset"])
    hourly_chart_html = build_hourly_temperature_chart(hourly_points, use_fahrenheit, temp_symbol)
    hero_stats = [
        ("Rain chance", f"{day['rain_chance']}%"),
        ("Rain total", format_precipitation(day["rain_total"])),
        ("Daylight", daylight_duration),
        ("UV peak", day["uv_index"]),
    ]
    detail_stats = [
        ("Condition", day["condition"]),
        ("Day low", f"{low_value}{temp_symbol}"),
        ("Day high", f"{high_value}{temp_symbol}"),
        ("Sunrise", day["sunrise"]),
        ("Sunset", day["sunset"]),
        ("Midday temp", f"{snapshot_temperature}{temp_symbol}" if hourly_snapshot else "--"),
        ("Midday wind", f"{snapshot_wind} {speed_symbol}" if hourly_snapshot else "--"),
    ]
    hero_stats_html = "".join(
        dedent(
            f"""
            <div class="skyline-forecast-hero-stat">
                <div class="skyline-forecast-hero-stat-label">{escape(str(label))}</div>
                <div class="skyline-forecast-hero-stat-value">{escape(str(value))}</div>
            </div>
            """
        ).strip()
        for label, value in hero_stats
    )
    detail_stats_html = "".join(
        dedent(
            f"""
            <div class="skyline-forecast-detail-stat">
                <div class="skyline-forecast-detail-stat-label">{escape(str(label))}</div>
                <div class="skyline-forecast-detail-stat-value">{escape(str(value))}</div>
            </div>
            """
        ).strip()
        for label, value in detail_stats
    )
    story_copy = (
        f"Conditions stay {day['condition'].lower()} through the day with a {day['rain_chance']}% rain chance, "
        f"around {format_precipitation(day['rain_total'])} of precipitation, sunrise at {day['sunrise']}, "
        f"sunset at {day['sunset']}, and a UV peak near {day['uv_index']}."
    )

    return dedent(
        f"""
        <div class="skyline-forecast-dialog-shell">
            <div class="skyline-forecast-dialog-hero">
                <div class="skyline-forecast-dialog-hero-main">
                    <div class="skyline-forecast-dialog-kicker">Expanded day forecast</div>
                    <div class="skyline-forecast-dialog-title">{escape(day['day'])}</div>
                    <div class="skyline-forecast-dialog-condition">{escape(get_condition_icon(day['condition']))} {escape(day['condition'])}</div>
                    <div class="skyline-forecast-dialog-range">Low {escape(str(low_value))}{escape(temp_symbol)} | High {escape(str(high_value))}{escape(temp_symbol)}</div>
                </div>
                <div class="skyline-forecast-dialog-hero-side">
                    <div class="skyline-forecast-dialog-kicker">Key pulse</div>
                    <div class="skyline-forecast-hero-stat-grid">{hero_stats_html}</div>
                </div>
            </div>
            <div class="skyline-forecast-dialog-story">{escape(story_copy)}</div>
            <div class="skyline-forecast-detail-grid">{detail_stats_html}</div>
            {hourly_chart_html}
        </div>
        """
    ).strip()


def render_forecast_section(
    weather_to_show,
    temp_symbol,
    use_fahrenheit,
    day_limit=10,
    section_title="10-Day Forecast",
    section_subtitle="Tap any day to open the full forecast detail view for that date.",
    instance_id="main",
):
    forecast = weather_to_show["forecast"]
    visible_forecast = forecast[:day_limit]

    render_insight_section_header(
        section_title,
        section_subtitle,
        "Forecast View",
    )

    if len(forecast) < day_limit:
        st.warning("Forecast data is partially available right now.")

    if not visible_forecast:
        return

    speed_symbol = "mph" if st.session_state["speed_unit"] == "mph" else "km/h"
    low_values = []
    high_values = []
    for day in visible_forecast:
        low_value = round(celsius_to_fahrenheit(day["min"]), 1) if use_fahrenheit else day["min"]
        high_value = round(celsius_to_fahrenheit(day["max"]), 1) if use_fahrenheit else day["max"]
        low_values.append(low_value)
        high_values.append(high_value)

    overall_low = min(low_values) if low_values else 0
    overall_high = max(high_values) if high_values else 1
    spread = max(overall_high - overall_low, 1)
    modal_markup = []
    row_markup = []

    for index, day in enumerate(visible_forecast):
        low_value = low_values[index]
        high_value = high_values[index]
        fill_percent = max(18, min(((high_value - overall_low) / spread) * 100, 100))
        modal_markup.append(build_forecast_modal_markup(day, temp_symbol, speed_symbol, use_fahrenheit))
        row_markup.append(
            dedent(
                f"""
                <div class="forecast-row-shell">
                    <button class="forecast-item-label forecast-row-trigger" type="button" data-forecast-index="{index}">
                        <div class="forecast-row">
                            <div class="forecast-day-name">{escape(day["day"])}</div>
                            <div class="forecast-icon">{escape(get_condition_icon(day["condition"]))}</div>
                            <div class="forecast-low">{escape(str(low_value))}{escape(temp_symbol)}</div>
                            <div class="forecast-bar"><div class="forecast-bar-fill" style="width:{fill_percent}%"></div></div>
                            <div class="forecast-high">{escape(str(high_value))}{escape(temp_symbol)}</div>
                            <div class="forecast-chevron">&#9662;</div>
                        </div>
                    </button>
                </div>
                """
            ).strip()
        )

    components.html(
        f"""
        <div class="forecast-list">
            {''.join(row_markup)}
        </div>
        <style>
          body {{
            margin: 0;
            background: transparent;
            font-family: "Segoe UI", sans-serif;
            overflow: visible;
          }}
          .forecast-list {{
            border-radius: 28px;
            padding: 1rem 1.1rem 1.22rem;
            margin-top: 0.65rem;
            background: linear-gradient(180deg, rgba(255, 255, 255, 0.16), rgba(255, 255, 255, 0.08));
            border: 1px solid rgba(255, 255, 255, 0.14);
            box-shadow: none;
            backdrop-filter: blur(16px);
          }}
          .forecast-row-shell + .forecast-row-shell {{
            border-top: 1px solid rgba(255, 255, 255, 0.08);
          }}
          .forecast-item-label {{
            width: 100%;
            display: block;
            border: 0;
            border-radius: 18px;
            padding: 0;
            background: transparent;
            color: inherit;
            cursor: pointer;
            text-align: left;
            transition: transform 0.25s ease, background 0.25s ease;
          }}
          .forecast-item-label:hover {{
            background: rgba(255,255,255,0.04);
            transform: translateY(-1px);
          }}
          .forecast-row {{
            position: relative;
            display: grid;
            grid-template-columns: 3.2rem 2rem 3.3rem 1fr 3.3rem 1.9rem;
            gap: 0.6rem;
            align-items: center;
            padding: 0.62rem 0;
            color: #f6fbff;
          }}
          .forecast-day-name {{
            font-weight: 700;
          }}
          .forecast-icon {{
            font-size: 1.1rem;
          }}
          .forecast-low,
          .forecast-high {{
            opacity: 0.92;
            font-size: 0.96rem;
          }}
          .forecast-bar {{
            position: relative;
            height: 0.28rem;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.14);
            overflow: hidden;
          }}
          .forecast-bar-fill {{
            height: 100%;
            border-radius: 999px;
            background: linear-gradient(90deg, rgba(251, 196, 111, 0.9), rgba(255, 228, 134, 0.98));
          }}
          .forecast-chevron {{
            justify-self: end;
            width: 1.65rem;
            height: 1.65rem;
            border-radius: 999px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.1);
            font-size: 0.9rem;
          }}
          @media (max-width: 900px) {{
            .forecast-row {{
              grid-template-columns: 2.8rem 1.6rem 2.9rem 1fr 2.9rem 1.7rem;
              gap: 0.45rem;
            }}
          }}
        </style>
        <script>
          const forecastInstanceId = {json.dumps(instance_id)};
          const cleanupKey = `__skylineForecastCleanup_${{forecastInstanceId}}`;
          if (window[cleanupKey]) {{
            window[cleanupKey]();
          }}

          const modalMarkup = {json.dumps(modal_markup, ensure_ascii=False)};
          const hostWindow = window.parent;
          const hostDoc = hostWindow.document;
          const portalId = `skyline-forecast-modal-portal-${{forecastInstanceId}}`;
          const styleId = `skyline-forecast-modal-style-${{forecastInstanceId}}`;
          let portal = hostDoc.getElementById(portalId);

          if (!portal) {{
            portal = hostDoc.createElement("div");
            portal.id = portalId;
            hostDoc.body.appendChild(portal);
          }}

          let style = hostDoc.getElementById(styleId);
          if (!style) {{
            style = hostDoc.createElement("style");
            style.id = styleId;
            hostDoc.head.appendChild(style);
          }}
          style.textContent = `
              body.skyline-forecast-modal-open {{
                overflow: hidden;
              }}
              #${{portalId}} {{
                position: fixed;
                inset: 0;
                z-index: 9999;
                pointer-events: none;
              }}
              #${{portalId}}.is-open {{
                pointer-events: auto;
              }}
              .skyline-forecast-overlay {{
                position: absolute;
                inset: 0;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: clamp(0.9rem, 2vw, 1.75rem);
              }}
              .skyline-forecast-backdrop {{
                position: absolute;
                inset: 0;
                background: rgba(6, 16, 28, 0.32);
                backdrop-filter: blur(6px);
                animation: skylineForecastBackdropIn 0.22s ease both;
              }}
              .skyline-forecast-overlay.is-closing .skyline-forecast-backdrop {{
                animation: skylineForecastBackdropOut 0.18s ease both;
              }}
              .skyline-forecast-card {{
                position: relative;
                width: min(84vw, 920px);
                max-width: min(84vw, 920px);
                max-height: 92vh;
                overflow-y: auto;
                border-radius: 30px;
                padding: 1.95rem 1rem 1rem;
                background: linear-gradient(180deg, rgba(120, 154, 187, 0.18), rgba(17, 43, 72, 0.28));
                border: 1px solid rgba(255,255,255,0.16);
                box-shadow: 0 24px 58px rgba(4, 15, 32, 0.26);
                backdrop-filter: blur(24px);
                color: #f6fbff;
                transform-origin: top center;
                animation: skylineForecastCardIn 0.28s cubic-bezier(0.22, 1, 0.36, 1) both;
              }}
              .skyline-forecast-overlay.is-closing .skyline-forecast-card {{
                animation: skylineForecastCardOut 0.2s cubic-bezier(0.22, 1, 0.36, 1) both;
              }}
              .skyline-forecast-close {{
                position: absolute;
                top: 0.7rem;
                right: 0.95rem;
                border-radius: 999px;
                width: 2.15rem;
                height: 2.15rem;
                min-width: 2.15rem;
                padding: 0;
                display: inline-flex;
                align-items: center;
                justify-content: center;
                border: 1px solid rgba(255,255,255,0.14);
                background: rgba(255,255,255,0.06);
                color: rgba(242,248,255,0.82);
                font-size: 1.1rem;
                line-height: 1;
                cursor: pointer;
                box-shadow: 0 8px 20px rgba(4, 15, 32, 0.14);
              }}
              .skyline-forecast-close:hover {{
                background: rgba(255,255,255,0.1);
                color: #f8fbff;
              }}
              .skyline-forecast-dialog-shell {{
                padding-top: 0.45rem;
              }}
              .skyline-forecast-dialog-hero {{
                display: grid;
                grid-template-columns: minmax(0, 1.15fr) minmax(240px, 0.85fr);
                gap: 0.8rem;
                align-items: stretch;
              }}
              .skyline-forecast-dialog-hero-main,
              .skyline-forecast-dialog-hero-side,
              .skyline-forecast-dialog-story,
              .skyline-forecast-dialog-shell .forecast-chart-shell,
              .skyline-forecast-detail-grid {{
                border-radius: 22px;
                background: rgba(255,255,255,0.065);
                border: 1px solid rgba(255,255,255,0.08);
                box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
              }}
              .skyline-forecast-dialog-hero-main,
              .skyline-forecast-dialog-hero-side {{
                padding: 0.95rem 1rem;
              }}
              .skyline-forecast-dialog-kicker,
              .skyline-forecast-dialog-shell .forecast-chart-title,
              .skyline-forecast-hero-stat-label,
              .skyline-forecast-detail-stat-label {{
                font-size: 0.76rem;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                opacity: 0.7;
              }}
              .skyline-forecast-dialog-title {{
                margin-top: 0.25rem;
                font-size: clamp(1.8rem, 3vw, 2.45rem);
                font-weight: 800;
                line-height: 1;
              }}
              .skyline-forecast-dialog-condition {{
                margin-top: 0.45rem;
                font-size: 0.98rem;
                opacity: 0.9;
              }}
              .skyline-forecast-dialog-range {{
                margin-top: 0.45rem;
                font-size: 0.94rem;
                opacity: 0.82;
              }}
              .skyline-forecast-dialog-story {{
                margin-top: 0.8rem;
                padding: 0.85rem 0.95rem;
                line-height: 1.55;
                font-size: 0.92rem;
                opacity: 0.92;
              }}
              .skyline-forecast-hero-stat-grid {{
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 0.55rem;
              }}
              .skyline-forecast-hero-stat,
              .skyline-forecast-detail-stat {{
                padding: 0.72rem 0.8rem;
                border-radius: 18px;
                background: rgba(255,255,255,0.06);
                border: 1px solid rgba(255,255,255,0.08);
              }}
              .skyline-forecast-hero-stat-value,
              .skyline-forecast-detail-stat-value {{
                margin-top: 0.28rem;
                font-size: 1rem;
                font-weight: 700;
              }}
              .skyline-forecast-dialog-shell .forecast-chart-shell {{
                margin-top: 0.8rem;
                padding: 0.85rem 0.95rem 0.75rem;
              }}
              .skyline-forecast-dialog-shell .forecast-chart-image {{
                width: 100%;
                height: 220px;
                margin-top: 0.7rem;
                display: block;
              }}
              .skyline-forecast-dialog-shell .forecast-chart-empty {{
                margin-top: 0.8rem;
                padding: 0.85rem 0.95rem;
                font-size: 0.92rem;
                opacity: 0.86;
              }}
              .skyline-forecast-detail-grid {{
                margin-top: 0.8rem;
                padding: 0.85rem 0.95rem;
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 0.55rem;
              }}
              .skyline-forecast-dialog-shell svg text {{
                fill: rgba(242,248,255,0.76);
              }}
              @keyframes skylineForecastBackdropIn {{
                from {{
                  opacity: 0;
                }}
                to {{
                  opacity: 1;
                }}
              }}
              @keyframes skylineForecastBackdropOut {{
                from {{
                  opacity: 1;
                }}
                to {{
                  opacity: 0;
                }}
              }}
              @keyframes skylineForecastCardIn {{
                from {{
                  opacity: 0;
                  transform: translateY(18px) scale(0.975);
                }}
                to {{
                  opacity: 1;
                  transform: translateY(0) scale(1);
                }}
              }}
              @keyframes skylineForecastCardOut {{
                from {{
                  opacity: 1;
                  transform: translateY(0) scale(1);
                }}
                to {{
                  opacity: 0;
                  transform: translateY(18px) scale(0.975);
                }}
              }}
              @media (max-width: 1100px) {{
                .skyline-forecast-dialog-hero {{
                  grid-template-columns: 1fr;
                }}
                .skyline-forecast-detail-grid {{
                  grid-template-columns: repeat(2, minmax(0, 1fr));
                }}
              }}
              @media (max-width: 720px) {{
                .skyline-forecast-hero-stat-grid,
                .skyline-forecast-detail-grid {{
                  grid-template-columns: 1fr;
                }}
                .skyline-forecast-card {{
                  width: min(95vw, 760px);
                  max-width: min(95vw, 760px);
                  padding: 1.65rem 0.85rem 0.85rem;
                }}
              }}
            `;

          const forecastList = document.querySelector(".forecast-list");
          let resizeObserver = null;
          let closeTimer = null;

          const resizeFrame = () => {{
            const listHeight = forecastList ? Math.ceil(forecastList.getBoundingClientRect().height) : 0;
            const height = Math.max(listHeight + 28, 308);
            hostWindow.postMessage({{ isStreamlitMessage: true, type: "streamlit:setFrameHeight", height }}, "*");
          }};

          const finalizeCloseModal = () => {{
            if (closeTimer) {{
              hostWindow.clearTimeout(closeTimer);
              closeTimer = null;
            }}
            portal.classList.remove("is-open");
            portal.innerHTML = "";
            hostDoc.body.classList.remove("skyline-forecast-modal-open");
          }};

          const closeModal = (animate = true) => {{
            const overlay = portal.querySelector(".skyline-forecast-overlay");
            if (animate && overlay && !overlay.classList.contains("is-closing")) {{
              overlay.classList.add("is-closing");
              closeTimer = hostWindow.setTimeout(() => finalizeCloseModal(), 180);
              return;
            }}
            finalizeCloseModal();
          }};

          const openModal = (index) => {{
            const modalBody = modalMarkup[index];
            if (!modalBody) {{
              return;
            }}

            portal.innerHTML = `
              <div class="skyline-forecast-overlay">
                <div class="skyline-forecast-backdrop" data-close="true"></div>
                <div class="skyline-forecast-card" role="dialog" aria-modal="true" aria-label="{escape(section_title)}">
                  <button class="skyline-forecast-close" type="button" data-close="true" aria-label="Close">&times;</button>
                  ${{modalBody}}
                </div>
              </div>
            `;
            portal.classList.add("is-open");
            hostDoc.body.classList.add("skyline-forecast-modal-open");
          }};

          const handlePortalClick = (event) => {{
            if (event.target.closest("[data-close='true']")) {{
              closeModal(true);
            }}
          }};

          const handleEscape = (event) => {{
            if (event.key === "Escape") {{
              closeModal(true);
            }}
          }};

          portal.addEventListener("click", handlePortalClick);
          hostWindow.addEventListener("keydown", handleEscape);
          Array.from(document.querySelectorAll(".forecast-row-trigger")).forEach((button) => {{
            button.addEventListener("click", () => openModal(Number(button.dataset.forecastIndex)));
          }});

          window[cleanupKey] = () => {{
            if (resizeObserver) {{
              resizeObserver.disconnect();
              resizeObserver = null;
            }}
            portal.removeEventListener("click", handlePortalClick);
            hostWindow.removeEventListener("keydown", handleEscape);
            closeModal(false);
            if (portal.parentNode) {{
              portal.parentNode.removeChild(portal);
            }}
          }};

          if (window.ResizeObserver && forecastList) {{
            resizeObserver = new ResizeObserver(() => resizeFrame());
            resizeObserver.observe(forecastList);
          }}

          resizeFrame();
        </script>
        """,
        height=max(308, 116 + (len(row_markup) * 48)),
    )


def _legacy_render_forecast_dialog(weather_to_show, temp_symbol, speed_symbol, use_fahrenheit):
    return


def get_weather_local_now(weather_to_show):
    time_info = (weather_to_show or {}).get("time") or {}
    location = (weather_to_show or {}).get("location") or {}
    timezone_name = time_info.get("timezone") or location.get("timezone")

    if timezone_name:
        try:
            return datetime.now(ZoneInfo(timezone_name))
        except ZoneInfoNotFoundError:
            pass

    for candidate in [time_info.get("local_datetime_iso"), time_info.get("observed_at")]:
        if not candidate:
            continue
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            continue

    return datetime.now()


def get_hourly_outlook_icon(condition, is_day):
    if condition == "Sunny":
        return "\u2600\ufe0f" if is_day else "\U0001f319"
    if condition == "Cloudy":
        return "\u26c5" if is_day else "\u2601\ufe0f"
    if condition == "Rainy":
        return "\U0001f327\ufe0f"
    if condition == "Snowy":
        return "\u2744\ufe0f"
    if condition == "Thunderstorm":
        return "\u26c8\ufe0f"
    if condition == "Foggy":
        return "\U0001f32b\ufe0f"
    return get_condition_icon(condition)


def build_hourly_outlook_items(weather_to_show, use_fahrenheit, temp_symbol):
    forecast = (weather_to_show or {}).get("forecast") or []
    if not forecast:
        return []

    hourly_points = []
    for day in forecast:
        for point in day.get("hourly") or []:
            try:
                if point.get("time_iso"):
                    point_dt = datetime.fromisoformat(point["time_iso"])
                else:
                    point_dt = datetime.strptime(
                        f"{point['date']} {point['time']}",
                        "%Y-%m-%d %I:%M %p",
                    )
            except (KeyError, TypeError, ValueError):
                continue
            hourly_points.append((point_dt, point))

    if not hourly_points:
        return []

    hourly_points.sort(key=lambda item: item[0])
    local_now = get_weather_local_now(weather_to_show)
    if hourly_points and hourly_points[0][0].tzinfo is None and local_now.tzinfo is not None:
        local_now = local_now.replace(tzinfo=None)
    current_hour = local_now.replace(minute=0, second=0, microsecond=0)
    window_end = (current_hour + timedelta(days=2)).replace(hour=1, minute=0, second=0, microsecond=0)
    upcoming_points = [
        (point_dt, point)
        for point_dt, point in hourly_points
        if point_dt >= current_hour and point_dt < window_end
    ]
    if not upcoming_points:
        upcoming_points = [item for item in hourly_points if item[0] >= current_hour] or hourly_points

    items = []
    last_date = None
    for index, (point_dt, point) in enumerate(upcoming_points):
        display_temp = round(celsius_to_fahrenheit(point["temperature"]), 1) if use_fahrenheit else point["temperature"]
        rounded_temp = int(round(display_temp))
        is_day = point.get("is_day")
        if is_day is None:
            is_day = 6 <= point_dt.hour < 18
        time_label = point_dt.strftime("%I%p").lstrip("0")
        if index == 0 and point_dt.date() == current_hour.date() and point_dt.hour == current_hour.hour:
            time_label = "Now"

        day_marker = ""
        if last_date is not None and point_dt.date() != last_date:
            if point_dt.date() == current_hour.date() + timedelta(days=1):
                day_marker = "Tomorrow"
            else:
                day_marker = point_dt.strftime("%a")

        items.append(
            {
                "time_label": time_label,
                "day_marker": day_marker,
                "icon": get_hourly_outlook_icon(point["condition"], is_day),
                "temp_label": f"{rounded_temp}\u00b0",
                "condition": point["condition"],
                "is_now": index == 0 and time_label == "Now",
                "aria_label": (
                    f"{point_dt.strftime('%a %I %p').replace(' 0', ' ')}. "
                    f"{point['condition']}. {rounded_temp}{temp_symbol.strip()}."
                ),
            }
        )
        last_date = point_dt.date()

    return items


def render_hourly_outlook_strip(weather_to_show, use_fahrenheit, temp_symbol, instance_id="main"):
    items = build_hourly_outlook_items(weather_to_show, use_fahrenheit, temp_symbol)
    if not items:
        return False

    component_id = f"skyline-hourly-outlook-{instance_id}"
    components.html(
        f"""
        <div class="skyline-hourly-shell" id="{escape(component_id)}">
          <div class="skyline-hourly-header">
            <div class="skyline-hourly-header-copy">
              <div class="skyline-hourly-kicker">Hourly Outlook</div>
              <div class="skyline-hourly-subtitle">Live conditions from now through tomorrow night</div>
            </div>
            <div class="skyline-hourly-meta">Through 1AM</div>
          </div>
          <div class="skyline-hourly-stage">
            <button class="skyline-hourly-arrow skyline-hourly-arrow--left" type="button" aria-label="Scroll hourly forecast left" data-direction="prev">&#10094;</button>
            <div class="skyline-hourly-fade skyline-hourly-fade--left" aria-hidden="true"></div>
            <div class="skyline-hourly-track-shell">
              <div class="skyline-hourly-track" role="list" aria-label="Hourly weather outlook"></div>
            </div>
            <div class="skyline-hourly-fade skyline-hourly-fade--right" aria-hidden="true"></div>
            <button class="skyline-hourly-arrow skyline-hourly-arrow--right" type="button" aria-label="Scroll hourly forecast right" data-direction="next">&#10095;</button>
          </div>
        </div>
        <style>
          body {{
            margin: 0;
            background: transparent;
            font-family: "Segoe UI", sans-serif;
            overflow: hidden;
          }}
          * {{
            box-sizing: border-box;
          }}
          .skyline-hourly-shell {{
            position: relative;
            width: 100%;
            border-radius: 26px;
            padding: 0.78rem 0.82rem 1rem;
            background:
              linear-gradient(180deg, rgba(255,255,255,0.13), rgba(255,255,255,0.06)),
              linear-gradient(140deg, rgba(99, 127, 158, 0.14), rgba(28, 45, 66, 0.12));
            border: 1px solid rgba(255,255,255,0.11);
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.08);
            backdrop-filter: blur(18px);
            color: #f6fbff;
            overflow: hidden;
          }}
          .skyline-hourly-shell::before {{
            content: "";
            position: absolute;
            inset: 0 0 auto 0;
            height: 42%;
            background: linear-gradient(180deg, rgba(255,255,255,0.06), rgba(255,255,255,0));
            pointer-events: none;
          }}
          .skyline-hourly-header {{
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 1rem;
            margin-bottom: 0.38rem;
            position: relative;
            z-index: 1;
          }}
          .skyline-hourly-header-copy {{
            min-width: 0;
          }}
          .skyline-hourly-kicker,
          .skyline-hourly-meta {{
            font-size: 0.68rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: rgba(234, 245, 255, 0.68);
            white-space: nowrap;
          }}
          .skyline-hourly-subtitle {{
            margin-top: 0.12rem;
            font-size: 0.8rem;
            line-height: 1.28;
            color: rgba(232, 244, 255, 0.66);
          }}
          .skyline-hourly-stage {{
            position: relative;
            padding: 0 1.92rem;
          }}
          .skyline-hourly-track-shell {{
            position: relative;
            border-radius: 18px;
            overflow: hidden;
            padding: 0;
            background: transparent;
            border: 0;
            box-shadow: none;
            -webkit-mask-image: linear-gradient(90deg, rgba(0,0,0,0) 0%, rgba(0,0,0,1) 1.05rem, rgba(0,0,0,1) calc(100% - 1.05rem), rgba(0,0,0,0) 100%);
            mask-image: linear-gradient(90deg, rgba(0,0,0,0) 0%, rgba(0,0,0,1) 1.05rem, rgba(0,0,0,1) calc(100% - 1.05rem), rgba(0,0,0,0) 100%);
          }}
          .skyline-hourly-track {{
            display: flex;
            gap: 0;
            overflow-x: auto;
            overflow-y: hidden;
            scroll-behavior: smooth;
            scroll-snap-type: x proximity;
            padding: 0.08rem 0 0.16rem;
            scrollbar-width: none;
          }}
          .skyline-hourly-track::-webkit-scrollbar {{
            display: none;
          }}
          .skyline-hourly-item-shell {{
            position: relative;
            flex: 0 0 4.35rem;
            min-width: 4.35rem;
            padding: 0 0.18rem;
            scroll-snap-align: start;
          }}
          .skyline-hourly-divider {{
            position: absolute;
            top: 1.2rem;
            left: -1px;
            bottom: 0.62rem;
            width: 2px;
            background:
              linear-gradient(90deg, rgba(255,255,255,0) 0%, rgba(255,255,255,0.1) 50%, rgba(255,255,255,0) 100%),
              linear-gradient(180deg, rgba(255,255,255,0.03), rgba(255,255,255,0.14), rgba(255,255,255,0.02));
            pointer-events: none;
            z-index: 1;
          }}
          .skyline-hourly-day-marker {{
            min-height: 0.62rem;
            margin-bottom: 0.14rem;
            font-size: 0.62rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: rgba(232, 244, 255, 0.48);
            white-space: nowrap;
            text-align: center;
          }}
          .skyline-hourly-item {{
            position: relative;
            z-index: 2;
            min-height: 4.78rem;
            border-radius: 18px;
            padding: 0.52rem 0.22rem 0.42rem;
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: flex-start;
            gap: 0.2rem;
            background: transparent;
            border: 1px solid transparent;
            box-shadow: none;
          }}
          .skyline-hourly-item-shell.is-now .skyline-hourly-item {{
            background: linear-gradient(180deg, rgba(255,255,255,0.11), rgba(255,255,255,0.04));
            border-color: rgba(214, 239, 250, 0.14);
            box-shadow:
              inset 0 -2px 0 rgba(214, 239, 250, 0.36),
              0 8px 18px rgba(6, 18, 33, 0.1);
          }}
          .skyline-hourly-time {{
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.02em;
            color: rgba(244, 250, 255, 0.9);
          }}
          .skyline-hourly-icon {{
            font-size: 1.04rem;
            line-height: 1;
            filter: drop-shadow(0 5px 10px rgba(6, 18, 33, 0.16));
          }}
          .skyline-hourly-temp {{
            font-size: 0.9rem;
            font-weight: 700;
            line-height: 1;
            color: rgba(246, 251, 255, 0.92);
          }}
          .skyline-hourly-arrow {{
            position: absolute;
            top: 50%;
            transform: translateY(-50%);
            z-index: 3;
            width: 1.68rem;
            height: 1.68rem;
            border-radius: 999px;
            border: 1px solid rgba(255,255,255,0.1);
            background: linear-gradient(180deg, rgba(35, 58, 85, 0.84), rgba(21, 38, 59, 0.8));
            color: #f6fbff;
            cursor: pointer;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            box-shadow: 0 8px 16px rgba(4, 15, 32, 0.14);
            backdrop-filter: blur(12px);
            transition: background 0.22s ease, opacity 0.22s ease, transform 0.22s ease, box-shadow 0.22s ease;
          }}
          .skyline-hourly-arrow:hover {{
            background: linear-gradient(180deg, rgba(49, 77, 109, 0.92), rgba(27, 46, 72, 0.88));
            box-shadow: 0 10px 20px rgba(4, 15, 32, 0.18);
            transform: translateY(-50%) scale(1.02);
          }}
          .skyline-hourly-arrow:disabled {{
            opacity: 0.18;
            cursor: default;
          }}
          .skyline-hourly-arrow--left {{
            left: 0.02rem;
          }}
          .skyline-hourly-arrow--right {{
            right: 0.02rem;
          }}
          .skyline-hourly-fade {{
            position: absolute;
            top: 0.08rem;
            bottom: 0.12rem;
            width: 1.48rem;
            z-index: 2;
            pointer-events: none;
            opacity: 0.74;
            transition: opacity 0.2s ease;
            backdrop-filter: blur(10px);
          }}
          .skyline-hourly-fade--left {{
            left: 1.68rem;
            border-radius: 18px 0 0 18px;
            background:
              linear-gradient(90deg, rgba(12, 22, 37, 0.18) 0%, rgba(12, 22, 37, 0.08) 46%, rgba(12, 22, 37, 0) 100%),
              linear-gradient(90deg, rgba(255,255,255,0.09) 0%, rgba(255,255,255,0.03) 40%, rgba(255,255,255,0) 100%);
          }}
          .skyline-hourly-fade--right {{
            right: 1.68rem;
            border-radius: 0 18px 18px 0;
            background:
              linear-gradient(270deg, rgba(12, 22, 37, 0.18) 0%, rgba(12, 22, 37, 0.08) 46%, rgba(12, 22, 37, 0) 100%),
              linear-gradient(270deg, rgba(255,255,255,0.09) 0%, rgba(255,255,255,0.03) 40%, rgba(255,255,255,0) 100%);
          }}
          @media (max-width: 900px) {{
            .skyline-hourly-shell {{
              padding: 0.72rem 0.74rem 0.8rem;
            }}
            .skyline-hourly-subtitle {{
              font-size: 0.76rem;
            }}
            .skyline-hourly-stage {{
              padding-left: 1.72rem;
              padding-right: 1.72rem;
            }}
            .skyline-hourly-fade {{
              width: 1.34rem;
            }}
            .skyline-hourly-item-shell {{
              flex-basis: 4rem;
              min-width: 4rem;
            }}
            .skyline-hourly-item {{
              min-height: 4.5rem;
            }}
            .skyline-hourly-fade--left {{
              left: 1.52rem;
            }}
            .skyline-hourly-fade--right {{
              right: 1.52rem;
            }}
          }}
        </style>
        <script>
          const payload = {json.dumps(items, ensure_ascii=False)};
          const root = document.getElementById({json.dumps(component_id)});
          const track = root.querySelector(".skyline-hourly-track");
          const prevButton = root.querySelector('[data-direction="prev"]');
          const nextButton = root.querySelector('[data-direction="next"]');
          const leftFade = root.querySelector(".skyline-hourly-fade--left");
          const rightFade = root.querySelector(".skyline-hourly-fade--right");

          const cardMarkup = payload.map((item, index) => `
            <div class="skyline-hourly-item-shell${{item.is_now ? " is-now" : ""}}" role="listitem">
              ${{index > 0 ? '<div class="skyline-hourly-divider" aria-hidden="true"></div>' : ""}}
              <div class="skyline-hourly-day-marker">${{item.day_marker || "&nbsp;"}}</div>
              <div class="skyline-hourly-item" title="${{item.aria_label}}" aria-label="${{item.aria_label}}">
                <div class="skyline-hourly-time">${{item.time_label}}</div>
                <div class="skyline-hourly-icon">${{item.icon}}</div>
                <div class="skyline-hourly-temp">${{item.temp_label}}</div>
              </div>
            </div>
          `).join("");
          track.innerHTML = cardMarkup;

          const setFrameHeight = () => {{
            const height = Math.max(document.body.scrollHeight + 10, 164);
            window.parent.postMessage({{ isStreamlitMessage: true, type: "streamlit:setFrameHeight", height }}, "*");
          }};

          const getScrollStep = () => {{
            const firstItem = root.querySelector(".skyline-hourly-item-shell");
            if (!firstItem) {{
              return 320;
            }}
            const gap = parseFloat(window.getComputedStyle(track).gap || "0");
            return (firstItem.getBoundingClientRect().width + gap) * 4;
          }};

          const updateControls = () => {{
            const maxScrollLeft = Math.max(track.scrollWidth - track.clientWidth, 0);
            const atStart = track.scrollLeft <= 4;
            const atEnd = track.scrollLeft >= maxScrollLeft - 4;
            prevButton.disabled = atStart;
            nextButton.disabled = atEnd;
            leftFade.style.opacity = atStart ? "0" : "0.74";
            rightFade.style.opacity = atEnd ? "0" : "0.74";
            const hasOverflow = maxScrollLeft > 10;
            prevButton.style.display = hasOverflow ? "inline-flex" : "none";
            nextButton.style.display = hasOverflow ? "inline-flex" : "none";
            leftFade.style.display = hasOverflow ? "block" : "none";
            rightFade.style.display = hasOverflow ? "block" : "none";
          }};

          prevButton.addEventListener("click", () => {{
            track.scrollBy({{ left: -getScrollStep(), behavior: "smooth" }});
          }});

          nextButton.addEventListener("click", () => {{
            track.scrollBy({{ left: getScrollStep(), behavior: "smooth" }});
          }});

          track.addEventListener("scroll", () => updateControls(), {{ passive: true }});
          track.addEventListener("wheel", (event) => {{
            if (Math.abs(event.deltaY) <= Math.abs(event.deltaX)) {{
              return;
            }}
            track.scrollLeft += event.deltaY;
            event.preventDefault();
          }}, {{ passive: false }});

          if (window.ResizeObserver) {{
            const observer = new ResizeObserver(() => {{
              updateControls();
              setFrameHeight();
            }});
            observer.observe(root);
            observer.observe(track);
          }}

          window.setTimeout(() => {{
            updateControls();
            setFrameHeight();
          }}, 40);
        </script>
        """,
        height=170,
    )
    return True


def refresh_weather_with_hourly_data(weather_to_show, forecast_index):
    forecast = (weather_to_show or {}).get("forecast") or []
    if forecast_index < len(forecast) and forecast[forecast_index].get("hourly"):
        return weather_to_show

    location = (weather_to_show or {}).get("location") or {}
    latitude = location.get("latitude")
    longitude = location.get("longitude")
    if latitude is None or longitude is None:
        return weather_to_show

    try:
        refreshed_weather = get_weather(
            {
                "label": weather_to_show.get("resolved_city") or "Selected Location",
                "query": weather_to_show.get("resolved_city") or "Selected Location",
                "latitude": latitude,
                "longitude": longitude,
            }
        )
    except WeatherError:
        return weather_to_show

    resolved_key = refreshed_weather["resolved_city"].strip().upper()
    st.session_state["last_weather"] = refreshed_weather
    st.session_state["last_city_display"] = refreshed_weather["resolved_city"]
    st.session_state["last_city_key"] = resolved_key
    save_last_weather_state(refreshed_weather, resolved_key)
    remember_recent_search(refreshed_weather)
    return refreshed_weather


def render_forecast_dialog(weather_to_show, temp_symbol, speed_symbol, use_fahrenheit):
    pending_index = st.session_state.pop("pending_forecast_dialog_index", None)
    if pending_index is None:
        return

    weather_to_show = refresh_weather_with_hourly_data(weather_to_show, pending_index)
    forecast = weather_to_show.get("forecast") or []
    if pending_index < 0 or pending_index >= len(forecast):
        return

    day = forecast[pending_index]
    low_value = round(celsius_to_fahrenheit(day["min"]), 1) if use_fahrenheit else day["min"]
    high_value = round(celsius_to_fahrenheit(day["max"]), 1) if use_fahrenheit else day["max"]
    hourly_points = day.get("hourly") or []
    hourly_snapshot = hourly_points[len(hourly_points) // 2] if hourly_points else {}
    snapshot_temperature = (
        round(celsius_to_fahrenheit(hourly_snapshot["temperature"]), 1)
        if hourly_snapshot and use_fahrenheit
        else hourly_snapshot.get("temperature", "--")
        if hourly_snapshot
        else "--"
    )
    snapshot_wind = (
        round(kmh_to_mph(hourly_snapshot["wind"]), 1)
        if hourly_snapshot and speed_symbol == "mph"
        else hourly_snapshot.get("wind", "--")
        if hourly_snapshot
        else "--"
    )
    daylight_duration = calculate_daylight_duration(day["sunrise"], day["sunset"])
    hourly_chart_html = build_hourly_temperature_chart(hourly_points, use_fahrenheit, temp_symbol)
    hero_stats = [
        ("Rain chance", f"{day['rain_chance']}%"),
        ("Rain total", format_precipitation(day["rain_total"])),
        ("Daylight", daylight_duration),
        ("UV peak", day["uv_index"]),
    ]
    detail_stats = [
        ("Condition", day["condition"]),
        ("Day low", f"{low_value}{temp_symbol}"),
        ("Day high", f"{high_value}{temp_symbol}"),
        ("Sunrise", day["sunrise"]),
        ("Sunset", day["sunset"]),
        ("Midday temp", f"{snapshot_temperature}{temp_symbol}" if hourly_snapshot else "--"),
        ("Midday wind", f"{snapshot_wind} {speed_symbol}" if hourly_snapshot else "--"),
    ]
    hero_stats_html = "".join(
        dedent(
            f"""
            <div class="forecast-hero-stat">
                <div class="forecast-hero-stat-label">{label}</div>
                <div class="forecast-hero-stat-value">{value}</div>
            </div>
            """
        ).strip()
        for label, value in hero_stats
    )
    detail_stats_html = "".join(
        dedent(
            f"""
            <div class="forecast-detail-stat">
                <div class="forecast-detail-stat-label">{label}</div>
                <div class="forecast-detail-stat-value">{value}</div>
            </div>
            """
        ).strip()
        for label, value in detail_stats
    )

    @st.dialog("10-Day Forecast")
    def forecast_dialog():
        st.markdown(
            """
            <style>
            div[data-testid="stDialog"] {
                background: rgba(6, 16, 28, 0.18);
                backdrop-filter: blur(4px);
            }
            div[data-testid="stDialog"] div[role="dialog"] {
                width: min(84vw, 920px);
                max-width: min(84vw, 920px);
                border-radius: 30px;
                background: linear-gradient(180deg, rgba(120, 154, 187, 0.18), rgba(17, 43, 72, 0.28));
                border: 1px solid rgba(255,255,255,0.16);
                box-shadow: 0 24px 58px rgba(4, 15, 32, 0.26);
                backdrop-filter: blur(24px);
            }
            div[data-testid="stDialog"] button[aria-label="Close"] {
                border-radius: 999px;
                width: 2rem;
                height: 2rem;
                min-width: 2rem;
                padding: 0;
                border: 1px solid rgba(255,255,255,0.14);
                background: rgba(255,255,255,0.06);
                color: rgba(242,248,255,0.82);
                top: 0.8rem;
                right: 0.9rem;
            }
            div[data-testid="stDialog"] button[aria-label="Close"]:hover {
                background: rgba(255,255,255,0.1);
                color: #f8fbff;
            }
            .forecast-dialog-shell {
                padding-top: 0.1rem;
            }
            .forecast-dialog-hero {
                display: grid;
                grid-template-columns: minmax(0, 1.15fr) minmax(240px, 0.85fr);
                gap: 0.8rem;
                align-items: stretch;
            }
            .forecast-dialog-hero-main,
            .forecast-dialog-hero-side,
            .forecast-dialog-story,
            .forecast-chart-shell,
            .forecast-detail-grid {
                border-radius: 22px;
                background: rgba(255,255,255,0.065);
                border: 1px solid rgba(255,255,255,0.08);
                box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
            }
            .forecast-dialog-hero-main,
            .forecast-dialog-hero-side {
                padding: 0.95rem 1rem;
            }
            .forecast-dialog-kicker {
                font-size: 0.76rem;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                opacity: 0.72;
            }
            .forecast-dialog-title {
                margin-top: 0.25rem;
                font-size: clamp(1.8rem, 3vw, 2.45rem);
                font-weight: 800;
                line-height: 1;
            }
            .forecast-dialog-condition {
                margin-top: 0.45rem;
                font-size: 0.98rem;
                opacity: 0.9;
            }
            .forecast-dialog-range {
                margin-top: 0.45rem;
                font-size: 0.94rem;
                opacity: 0.82;
            }
            .forecast-dialog-story {
                margin-top: 0.8rem;
                padding: 0.85rem 0.95rem;
                line-height: 1.55;
                font-size: 0.92rem;
                opacity: 0.92;
            }
            .forecast-hero-stat-grid {
                display: grid;
                grid-template-columns: repeat(2, minmax(0, 1fr));
                gap: 0.55rem;
            }
            .forecast-hero-stat {
                padding: 0.72rem 0.8rem;
                border-radius: 18px;
                background: rgba(255,255,255,0.06);
                border: 1px solid rgba(255,255,255,0.08);
            }
            .forecast-hero-stat-label,
            .forecast-detail-stat-label {
                font-size: 0.72rem;
                letter-spacing: 0.06em;
                text-transform: uppercase;
                opacity: 0.66;
            }
            .forecast-hero-stat-value {
                margin-top: 0.28rem;
                font-size: 1.02rem;
                font-weight: 700;
            }
            .forecast-chart-shell {
                margin-top: 0.8rem;
                padding: 0.85rem 0.95rem 0.75rem;
            }
            .forecast-chart-title {
                font-size: 0.78rem;
                letter-spacing: 0.08em;
                text-transform: uppercase;
                opacity: 0.7;
            }
            .forecast-chart-image {
                width: 100%;
                height: 220px;
                margin-top: 0.7rem;
                display: block;
            }
            .forecast-chart-empty {
                margin-top: 0.8rem;
                padding: 0.85rem 0.95rem;
                font-size: 0.92rem;
                opacity: 0.86;
            }
            .forecast-detail-grid {
                margin-top: 0.8rem;
                padding: 0.85rem 0.95rem;
                display: grid;
                grid-template-columns: repeat(3, minmax(0, 1fr));
                gap: 0.55rem;
            }
            .forecast-detail-stat {
                padding: 0.72rem 0.8rem;
                border-radius: 18px;
                background: rgba(255,255,255,0.06);
                border: 1px solid rgba(255,255,255,0.08);
            }
            .forecast-detail-stat-value {
                margin-top: 0.3rem;
                font-size: 0.98rem;
                font-weight: 700;
            }
            @media (max-width: 1100px) {
                .forecast-dialog-hero {
                    grid-template-columns: 1fr;
                }
                .forecast-detail-grid {
                    grid-template-columns: repeat(2, minmax(0, 1fr));
                }
            }
            @media (max-width: 720px) {
                .forecast-hero-stat-grid,
                .forecast-detail-grid {
                    grid-template-columns: 1fr;
                }
            }
            </style>
            """,
            unsafe_allow_html=True,
        )

        st.markdown(
            dedent(
                f"""
                <div class="forecast-dialog-shell">
                    <div class="forecast-dialog-hero">
                        <div class="forecast-dialog-hero-main">
                            <div class="forecast-dialog-kicker">Expanded day forecast</div>
                            <div class="forecast-dialog-title">{day['day']}</div>
                            <div class="forecast-dialog-condition">{get_condition_icon(day['condition'])} {day['condition']}</div>
                            <div class="forecast-dialog-range">Low {low_value}{temp_symbol} | High {high_value}{temp_symbol}</div>
                        </div>
                        <div class="forecast-dialog-hero-side">
                            <div class="forecast-dialog-kicker">Key pulse</div>
                            <div class="forecast-hero-stat-grid">{hero_stats_html}</div>
                        </div>
                    </div>
                    <div class="forecast-dialog-story">
                        Conditions stay {day['condition'].lower()} through the day with a {day['rain_chance']}% rain chance,
                        around {format_precipitation(day['rain_total'])} of precipitation, sunrise at {day['sunrise']},
                        sunset at {day['sunset']}, and a UV peak near {day['uv_index']}.
                    </div>
                    <div class="forecast-detail-grid">{detail_stats_html}</div>
                </div>
                """
            ).strip(),
            unsafe_allow_html=True,
        )

        st.markdown(hourly_chart_html, unsafe_allow_html=True)

        if st.button("Close Forecast", key=f"close_forecast_{pending_index}", use_container_width=True):
            st.rerun()

    forecast_dialog()


# Main app flow keeps the page readable and easy to extend.
def main():
    st.set_page_config(page_title="Skyline Forecast", page_icon="\u2601\ufe0f", layout="wide")

    initialize_session_state()
    if not st.session_state.get("nav_layout_bootstrap_done"):
        st.session_state["nav_layout_bootstrap_done"] = True
        st.rerun()
    process_location_request()
    process_forecast_dialog_request()
    bootstrap_default_weather()
    use_fahrenheit = st.session_state["temp_unit"] == TEMP_OPTIONS[1]
    use_mph = st.session_state["speed_unit"] == "mph"
    header_container = st.container()
    search_container = st.container()

    with search_container:
        search_event = render_search_section()

    handle_search_component_event(search_event)
    weather_to_show, city_to_show = get_active_weather_state()

    apply_theme(get_background_profile(weather_to_show))

    temp_symbol = " \u00b0F" if use_fahrenheit else " \u00b0C"
    speed_symbol = "mph" if use_mph else "km/h"
    with header_container:
        render_header_section(weather_to_show, city_to_show, temp_symbol, speed_symbol, use_fahrenheit)

    weather_to_show, city_to_show = get_active_weather_state()
    if not weather_to_show:
        st.info("Search for a city to load live weather details and a 10-day forecast.")
        return

    current = weather_to_show["current"]
    wind_speed = current["wind"]

    if use_mph:
        converted_wind = round(kmh_to_mph(wind_speed), 1)
    else:
        converted_wind = wind_speed

    active_section = st.session_state.get("active_content_section", CONTENT_SECTIONS[0])
    render_section_transition(active_section, CONTENT_SECTIONS)
    render_current_conditions_section(weather_to_show, speed_symbol, converted_wind, temp_symbol, use_fahrenheit)
    if active_section == "Overview":
        if render_hourly_outlook_strip(weather_to_show, use_fahrenheit, temp_symbol, instance_id="overview_main"):
            render_soft_section_divider()
        else:
            render_soft_section_divider("persistent")
        render_forecast_section(weather_to_show, temp_symbol, use_fahrenheit)
    else:
        render_soft_section_divider("persistent")
    render_weather_tabbed_section(weather_to_show, city_to_show, temp_symbol, speed_symbol, use_fahrenheit)


if __name__ == "__main__":
    main()
