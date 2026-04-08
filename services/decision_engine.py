from __future__ import annotations

from datetime import datetime, timedelta
from statistics import mean
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


DECISION_ACTIVITY_OPTIONS = [
    {
        "key": "run",
        "label": "Go for a run",
        "question": "Should I go for a run now?",
        "noun": "running",
        "block_hours": 2,
        "metric_keys": ["feels_like", "humidity", "rain_chance", "uv_index"],
        "label_mode": "standard",
    },
    {
        "key": "walk",
        "label": "Go for a walk",
        "question": "Is it a good time to walk outside?",
        "noun": "walking outside",
        "block_hours": 2,
        "metric_keys": ["temperature", "rain_chance", "wind", "local_time"],
        "label_mode": "standard",
    },
    {
        "key": "workout",
        "label": "Outdoor workout",
        "question": "Is it a good time for an outdoor workout?",
        "noun": "an outdoor workout",
        "block_hours": 2,
        "metric_keys": ["feels_like", "humidity", "wind", "rain_chance"],
        "label_mode": "standard",
    },
    {
        "key": "beach",
        "label": "Go to the beach",
        "question": "Is today good for the beach?",
        "noun": "the beach",
        "block_hours": 3,
        "metric_keys": ["temperature", "uv_index", "wind", "rain_chance"],
        "label_mode": "standard",
    },
    {
        "key": "errands",
        "label": "Run errands",
        "question": "Is it a good time to run errands?",
        "noun": "running errands",
        "block_hours": 2,
        "metric_keys": ["feels_like", "rain_chance", "wind", "local_time"],
        "label_mode": "standard",
    },
    {
        "key": "study",
        "label": "Outdoor study",
        "question": "Is it a good time to study outside?",
        "noun": "studying outside",
        "block_hours": 2,
        "metric_keys": ["temperature", "wind", "humidity", "rain_chance"],
        "label_mode": "standard",
    },
    {
        "key": "jacket",
        "label": "Wear a jacket",
        "question": "Should I wear a jacket?",
        "noun": "a jacket",
        "block_hours": 0,
        "metric_keys": ["feels_like", "wind", "rain_chance", "local_time"],
        "label_mode": "jacket",
    },
    {
        "key": "umbrella",
        "label": "Use an umbrella",
        "question": "Should I use an umbrella?",
        "noun": "an umbrella",
        "block_hours": 0,
        "metric_keys": ["rain_chance", "condition", "wind", "local_time"],
        "label_mode": "umbrella",
    },
    {
        "key": "windows",
        "label": "Open windows",
        "question": "Is it a good time to open the windows?",
        "noun": "opening the windows",
        "block_hours": 2,
        "metric_keys": ["temperature", "humidity", "wind", "condition"],
        "label_mode": "standard",
    },
    {
        "key": "travel",
        "label": "Drive comfortably",
        "question": "Is it comfortable to drive or travel right now?",
        "noun": "driving or travelling comfortably",
        "block_hours": 2,
        "metric_keys": ["visibility", "rain_chance", "wind", "condition"],
        "label_mode": "standard",
    },
    {
        "key": "cycling",
        "label": "Go cycling",
        "question": "Is it a good time to go cycling?",
        "noun": "cycling",
        "block_hours": 2,
        "metric_keys": ["feels_like", "wind", "rain_chance", "uv_index"],
        "label_mode": "standard",
    },
    {
        "key": "hiking",
        "label": "Go hiking",
        "question": "Is it a good time to go hiking?",
        "noun": "hiking",
        "block_hours": 3,
        "metric_keys": ["temperature", "wind", "rain_chance", "uv_index"],
        "label_mode": "standard",
    },
    {
        "key": "picnic",
        "label": "Have a picnic",
        "question": "Is it a good time for a picnic?",
        "noun": "a picnic",
        "block_hours": 3,
        "metric_keys": ["temperature", "rain_chance", "wind", "cloud_cover"],
        "label_mode": "standard",
    },
    {
        "key": "photo",
        "label": "Outdoor photography",
        "question": "Is it a good time for outdoor photography?",
        "noun": "outdoor photography",
        "block_hours": 2,
        "metric_keys": ["visibility", "cloud_cover", "rain_chance", "local_time"],
        "label_mode": "standard",
    },
]

DECISION_ACTIVITY_MAP = {item["key"]: item for item in DECISION_ACTIVITY_OPTIONS}


def get_decision_activity_options():
    return list(DECISION_ACTIVITY_OPTIONS)


def _normalize_personalization(personalization=None):
    source = personalization or {}
    preferred_time_key = str(source.get("preferred_time_key") or "").strip().lower()
    if not preferred_time_key:
        preferred_time_value = str(source.get("preferred_time") or "").strip().lower()
        preferred_time_key = {
            "morning": "morning",
            "afternoon": "afternoon",
            "evening": "evening",
            "night": "night",
        }.get(preferred_time_value, "")
    return {
        "temperature_offset": float(source.get("temperature_offset") or 0),
        "preferred_time_key": preferred_time_key,
    }


def evaluate_decision(activity_key, weather_to_show, use_fahrenheit=False, speed_unit="km/h", personalization=None):
    if activity_key not in DECISION_ACTIVITY_MAP:
        raise ValueError(f"Unsupported decision activity: {activity_key}")

    config = DECISION_ACTIVITY_MAP[activity_key]
    context = _build_current_context(weather_to_show, use_fahrenheit, speed_unit, personalization)
    score_details = _score_activity(activity_key, context)
    score = _clamp(score_details["score"], 0, 100)
    label = _label_from_score(score, config["label_mode"])
    explanation = _build_explanation(config, label, score, score_details["factors"])
    best_time = _build_best_time_recommendation(
        activity_key,
        config,
        weather_to_show,
        context,
        score,
        use_fahrenheit,
        speed_unit,
        personalization,
    )

    return {
        "activity_key": activity_key,
        "title": config["label"],
        "question": config["question"],
        "score": score,
        "label": label,
        "explanation": explanation,
        "best_time": best_time,
        "local_time_label": context["local_time_label"],
        "metrics": [_build_metric_item(metric_key, context) for metric_key in config["metric_keys"]],
        "factors": score_details["factors"],
    }


def _build_current_context(weather_to_show, use_fahrenheit, speed_unit, personalization=None):
    forecast = (weather_to_show or {}).get("forecast") or []
    current = (weather_to_show or {}).get("current") or {}
    today = forecast[0] if forecast else {}
    local_now = _get_local_now(weather_to_show)
    hourly_points = _collect_hourly_points(weather_to_show)
    current_hour = local_now.replace(minute=0, second=0, microsecond=0)

    comparison_now = current_hour.replace(tzinfo=None) if hourly_points and hourly_points[0]["time_dt"].tzinfo is None else current_hour
    future_points = [point for point in hourly_points if point["time_dt"] >= comparison_now]
    active_point = future_points[0] if future_points else (hourly_points[0] if hourly_points else None)

    temperature = (
        active_point.get("temperature")
        if active_point and active_point.get("temperature") is not None
        else current.get("temperature", 0)
    )
    humidity = (
        active_point.get("humidity")
        if active_point and active_point.get("humidity") is not None
        else current.get("humidity", 0)
    )
    wind = active_point.get("wind") if active_point and active_point.get("wind") is not None else current.get("wind", 0)
    condition = active_point.get("condition") if active_point and active_point.get("condition") else current.get("condition", "Cloudy")
    rain_chance = (
        active_point.get("rain_chance")
        if active_point and active_point.get("rain_chance") is not None
        else today.get("rain_chance", 0)
    )
    rain_total = (
        active_point.get("rain_total")
        if active_point and active_point.get("rain_total") is not None
        else current.get("precipitation", 0)
    )
    cloud_cover = (
        active_point.get("cloud_cover")
        if active_point and active_point.get("cloud_cover") is not None
        else current.get("cloud_cover", 0)
    )
    is_day = active_point.get("is_day") if active_point and active_point.get("is_day") is not None else 6 <= local_now.hour < 18

    feels_like = current.get("feels_like")
    if feels_like is None:
        feels_like = _estimate_feels_like(temperature, humidity, wind)

    uv_index = _estimate_hourly_uv(today.get("uv_index", 0), local_now.hour, is_day)
    visibility = current.get("visibility")
    if visibility in (None, 0):
        visibility = _estimate_visibility(condition, cloud_cover)

    profile = _normalize_personalization(personalization)

    return {
        "time_dt": comparison_now,
        "hour": local_now.hour,
        "local_time_label": local_now.strftime("%I:%M %p").lstrip("0"),
        "temperature": float(temperature or 0) + profile["temperature_offset"],
        "feels_like": float(feels_like or 0) + profile["temperature_offset"],
        "humidity": int(round(humidity or 0)),
        "wind": float(wind or 0),
        "rain_chance": int(round(rain_chance or 0)),
        "rain_total": float(rain_total or 0),
        "condition": str(condition or "Cloudy"),
        "uv_index": float(uv_index or 0),
        "visibility": float(visibility or 0),
        "cloud_cover": int(round(cloud_cover or 0)),
        "is_day": bool(is_day),
        "use_fahrenheit": bool(use_fahrenheit),
        "speed_unit": speed_unit or "km/h",
        "preferred_time_key": profile["preferred_time_key"],
    }


def _build_metric_item(metric_key, context):
    if metric_key == "temperature":
        return {"label": "Temperature", "value": _format_temperature(context["temperature"], context)}
    if metric_key == "feels_like":
        return {"label": "Feels Like", "value": _format_temperature(context["feels_like"], context)}
    if metric_key == "humidity":
        return {"label": "Humidity", "value": f'{context["humidity"]}%'}
    if metric_key == "wind":
        return {"label": "Wind", "value": _format_wind(context["wind"], context)}
    if metric_key == "rain_chance":
        return {"label": "Rain Chance", "value": f'{context["rain_chance"]}%'}
    if metric_key == "uv_index":
        return {"label": "UV Index", "value": f'{round(context["uv_index"], 1)}'}
    if metric_key == "visibility":
        return {"label": "Visibility", "value": f'{round(context["visibility"], 1)} km'}
    if metric_key == "cloud_cover":
        return {"label": "Cloud Cover", "value": f'{context["cloud_cover"]}%'}
    if metric_key == "condition":
        return {"label": "Condition", "value": context["condition"]}
    if metric_key == "local_time":
        return {"label": "Local Time", "value": context["local_time_label"]}
    return {"label": metric_key.replace("_", " ").title(), "value": "--"}


def _score_activity(activity_key, context):
    scorers = {
        "run": _score_run,
        "walk": _score_walk,
        "workout": _score_workout,
        "beach": _score_beach,
        "errands": _score_errands,
        "study": _score_study,
        "jacket": _score_jacket,
        "umbrella": _score_umbrella,
        "windows": _score_windows,
        "travel": _score_travel,
        "cycling": _score_cycling,
        "hiking": _score_hiking,
        "picnic": _score_picnic,
        "photo": _score_photo,
    }
    return scorers[activity_key](context)


def _score_run(context):
    score = 100.0
    factors = []
    score = _apply_temperature(
        score,
        factors,
        context,
        source_key="feels_like",
        label="feels-like temperature",
        ideal_range=(12, 22),
        hard_range=(6, 34),
        warm_scale=3.0,
        cold_scale=2.8,
    )
    score = _apply_humidity(score, factors, context, comfortable_max=60, caution_max=75, weight=0.55)
    score = _apply_rain(score, factors, context, low_risk=15, caution_risk=35, weight=0.38, storm_penalty=24)
    score = _apply_wind(score, factors, context, calm_max=18, caution_max=28, weight=0.9)
    score = _apply_uv(score, factors, context, caution_uv=6, severe_uv=8, weight=4.0)
    score = _apply_hour_preference(
        score,
        factors,
        context,
        preferred_windows=[(5, 9), (17, 21)],
        late_penalty=(11, 16, 9),
        positive_text="the timing is favorable for a run",
        caution_text="midday timing adds extra heat stress",
    )
    return {"score": score, "factors": factors}


def _score_walk(context):
    score = 100.0
    factors = []
    score = _apply_temperature(
        score,
        factors,
        context,
        source_key="feels_like",
        label="feels-like temperature",
        ideal_range=(14, 28),
        hard_range=(6, 36),
        warm_scale=2.2,
        cold_scale=2.4,
    )
    score = _apply_rain(score, factors, context, low_risk=20, caution_risk=45, weight=0.3, storm_penalty=22)
    score = _apply_wind(score, factors, context, calm_max=20, caution_max=30, weight=0.72)
    score = _apply_humidity(score, factors, context, comfortable_max=65, caution_max=80, weight=0.32)
    score = _apply_uv(score, factors, context, caution_uv=7, severe_uv=9, weight=2.8)
    return {"score": score, "factors": factors}


def _score_workout(context):
    score = 100.0
    factors = []
    score = _apply_temperature(
        score,
        factors,
        context,
        source_key="feels_like",
        label="feels-like temperature",
        ideal_range=(11, 21),
        hard_range=(5, 33),
        warm_scale=3.2,
        cold_scale=2.8,
    )
    score = _apply_humidity(score, factors, context, comfortable_max=58, caution_max=72, weight=0.62)
    score = _apply_rain(score, factors, context, low_risk=12, caution_risk=30, weight=0.42, storm_penalty=26)
    score = _apply_wind(score, factors, context, calm_max=16, caution_max=26, weight=0.95)
    score = _apply_uv(score, factors, context, caution_uv=5.5, severe_uv=8, weight=4.4)
    score = _apply_hour_preference(
        score,
        factors,
        context,
        preferred_windows=[(5, 9), (17, 21)],
        late_penalty=(11, 16, 10),
        positive_text="the timing suits harder outdoor effort",
        caution_text="midday timing makes outdoor effort tougher",
    )
    return {"score": score, "factors": factors}


def _score_beach(context):
    score = 100.0
    factors = []
    score = _apply_temperature(
        score,
        factors,
        context,
        source_key="temperature",
        label="temperature",
        ideal_range=(24, 32),
        hard_range=(18, 38),
        warm_scale=1.8,
        cold_scale=3.0,
    )
    score = _apply_rain(score, factors, context, low_risk=15, caution_risk=30, weight=0.45, storm_penalty=30)
    score = _apply_wind(score, factors, context, calm_max=18, caution_max=28, weight=1.0)
    score = _apply_cloud_cover(score, factors, context, ideal_range=(5, 45), caution_max=75, weight=0.34)
    score = _apply_hour_preference(
        score,
        factors,
        context,
        preferred_windows=[(8, 16)],
        late_penalty=(18, 23, 8),
        positive_text="daytime lines up well with beach weather",
        caution_text="later timing trims down beach energy",
    )
    if context["uv_index"] >= 9 and context["is_day"]:
        penalty = 6 + (context["uv_index"] - 9) * 2.2
        score -= penalty
        _record_factor(
            factors,
            penalty,
            "negative",
            f"UV is very strong ({round(context['uv_index'], 1)}) and needs extra sun care",
        )
    elif context["uv_index"] >= 4 and context["is_day"]:
        bonus = 4.5
        score += bonus
        _record_factor(factors, bonus, "positive", "sun levels still support a beach day")
    return {"score": score, "factors": factors}


def _score_errands(context):
    score = 100.0
    factors = []
    score = _apply_temperature(
        score,
        factors,
        context,
        source_key="feels_like",
        label="feels-like temperature",
        ideal_range=(18, 30),
        hard_range=(8, 37),
        warm_scale=1.8,
        cold_scale=2.0,
    )
    score = _apply_rain(score, factors, context, low_risk=20, caution_risk=50, weight=0.32, storm_penalty=24)
    score = _apply_wind(score, factors, context, calm_max=20, caution_max=34, weight=0.55)
    score = _apply_visibility(score, factors, context, clear_min=8, caution_min=4.5, weight=5.0)
    return {"score": score, "factors": factors}


def _score_study(context):
    score = 100.0
    factors = []
    score = _apply_temperature(
        score,
        factors,
        context,
        source_key="temperature",
        label="temperature",
        ideal_range=(18, 27),
        hard_range=(10, 34),
        warm_scale=2.4,
        cold_scale=2.2,
    )
    score = _apply_wind(score, factors, context, calm_max=12, caution_max=22, weight=1.05)
    score = _apply_rain(score, factors, context, low_risk=10, caution_risk=25, weight=0.36, storm_penalty=26)
    score = _apply_humidity(score, factors, context, comfortable_max=60, caution_max=75, weight=0.36)
    score = _apply_uv(score, factors, context, caution_uv=6, severe_uv=8, weight=3.4)
    score = _apply_cloud_cover(score, factors, context, ideal_range=(20, 65), caution_max=88, weight=0.2, allow_bonus=True)
    return {"score": score, "factors": factors}


def _score_jacket(context):
    score = 8.0
    factors = []
    feels_like = context["feels_like"]
    if feels_like <= 10:
        bonus = 62 + (10 - feels_like) * 2.4
        score += bonus
        _record_factor(factors, bonus, "positive", f"it feels cold outside ({_format_temperature(feels_like, context)})")
    elif feels_like <= 17:
        bonus = 34 + (17 - feels_like) * 1.6
        score += bonus
        _record_factor(factors, bonus, "positive", f"the air feels cool ({_format_temperature(feels_like, context)})")
    elif feels_like <= 22:
        bonus = 16 + (22 - feels_like) * 1.2
        score += bonus
        _record_factor(factors, bonus, "positive", "a light extra layer could add comfort")
    else:
        penalty = min(45, (feels_like - 22) * 4.0)
        score -= penalty
        _record_factor(factors, penalty, "negative", f"it feels fairly warm ({_format_temperature(feels_like, context)})")

    if context["wind"] >= 20:
        bonus = 12 + (context["wind"] - 20) * 0.7
        score += bonus
        _record_factor(factors, bonus, "positive", f"wind is noticeable ({_format_wind(context['wind'], context)})")
    elif context["wind"] <= 10:
        penalty = 7
        score -= penalty
        _record_factor(factors, penalty, "negative", "wind is light, so extra layering matters less")

    if context["rain_chance"] >= 45:
        bonus = 10 + (context["rain_chance"] - 45) * 0.35
        score += bonus
        _record_factor(factors, bonus, "positive", f"rain risk is high ({context['rain_chance']}%)")

    if context["hour"] >= 18 or context["hour"] < 7:
        bonus = 6
        score += bonus
        _record_factor(factors, bonus, "positive", "evening or night air usually feels cooler")

    return {"score": score, "factors": factors}


def _score_umbrella(context):
    score = 2.0
    factors = []
    if context["condition"] == "Thunderstorm":
        bonus = 82
        score += bonus
        _record_factor(factors, bonus, "positive", "storm conditions are active")
    elif context["condition"] == "Rainy" and context["rain_total"] >= 0.2:
        bonus = 58
        score += bonus
        _record_factor(factors, bonus, "positive", "rain is already showing up in the current conditions")

    if context["rain_chance"] >= 70:
        bonus = 32 + (context["rain_chance"] - 70) * 0.45
        score += bonus
        _record_factor(factors, bonus, "positive", f"rain chance is high ({context['rain_chance']}%)")
    elif context["rain_chance"] >= 40:
        bonus = 14 + (context["rain_chance"] - 40) * 0.4
        score += bonus
        _record_factor(factors, bonus, "positive", f"rain chances are unsettled ({context['rain_chance']}%)")
    else:
        penalty = 18
        score -= penalty
        _record_factor(factors, penalty, "negative", f"rain risk is low ({context['rain_chance']}%)")

    if context["wind"] >= 30:
        penalty = 10 + (context["wind"] - 30) * 0.5
        score -= penalty
        _record_factor(factors, penalty, "negative", f"strong wind can make an umbrella less comfortable ({_format_wind(context['wind'], context)})")

    return {"score": score, "factors": factors}


def _score_windows(context):
    score = 100.0
    factors = []
    score = _apply_temperature(
        score,
        factors,
        context,
        source_key="temperature",
        label="temperature",
        ideal_range=(18, 27),
        hard_range=(12, 33),
        warm_scale=2.6,
        cold_scale=2.4,
    )
    score = _apply_humidity(score, factors, context, comfortable_max=60, caution_max=72, weight=0.58, dry_penalty=0.28)
    score = _apply_wind(score, factors, context, calm_max=18, caution_max=28, weight=0.62)
    score = _apply_rain(score, factors, context, low_risk=10, caution_risk=25, weight=0.42, storm_penalty=28)
    if context["condition"] in {"Foggy", "Thunderstorm"}:
        penalty = 18
        score -= penalty
        _record_factor(factors, penalty, "negative", f"{context['condition'].lower()} conditions are less fresh for open windows")
    return {"score": score, "factors": factors}


def _score_travel(context):
    score = 100.0
    factors = []
    score = _apply_visibility(score, factors, context, clear_min=9, caution_min=5, weight=7.5)
    score = _apply_rain(score, factors, context, low_risk=15, caution_risk=40, weight=0.34, storm_penalty=28)
    score = _apply_wind(score, factors, context, calm_max=22, caution_max=35, weight=0.7)
    if context["condition"] == "Thunderstorm":
        penalty = 24
        score -= penalty
        _record_factor(factors, penalty, "negative", "storm conditions make travel less comfortable")
    elif context["condition"] == "Foggy":
        penalty = 18
        score -= penalty
        _record_factor(factors, penalty, "negative", "fog softens road visibility")
    return {"score": score, "factors": factors}


def _score_cycling(context):
    score = 100.0
    factors = []
    score = _apply_temperature(
        score,
        factors,
        context,
        source_key="feels_like",
        label="feels-like temperature",
        ideal_range=(12, 24),
        hard_range=(5, 34),
        warm_scale=2.9,
        cold_scale=2.7,
    )
    score = _apply_humidity(score, factors, context, comfortable_max=62, caution_max=75, weight=0.42)
    score = _apply_rain(score, factors, context, low_risk=10, caution_risk=25, weight=0.45, storm_penalty=28)
    score = _apply_wind(score, factors, context, calm_max=14, caution_max=24, weight=1.25)
    score = _apply_uv(score, factors, context, caution_uv=6, severe_uv=8, weight=3.9)
    score = _apply_hour_preference(
        score,
        factors,
        context,
        preferred_windows=[(5, 10), (17, 21)],
        late_penalty=(11, 16, 9),
        positive_text="the timing supports cycling more cleanly",
        caution_text="midday timing adds extra heat and glare",
    )
    return {"score": score, "factors": factors}


def _score_hiking(context):
    score = 100.0
    factors = []
    score = _apply_temperature(
        score,
        factors,
        context,
        source_key="temperature",
        label="temperature",
        ideal_range=(14, 26),
        hard_range=(6, 34),
        warm_scale=2.5,
        cold_scale=2.3,
    )
    score = _apply_rain(score, factors, context, low_risk=15, caution_risk=35, weight=0.34, storm_penalty=24)
    score = _apply_wind(score, factors, context, calm_max=16, caution_max=28, weight=0.98)
    score = _apply_humidity(score, factors, context, comfortable_max=65, caution_max=78, weight=0.28)
    score = _apply_uv(score, factors, context, caution_uv=6.5, severe_uv=8.5, weight=3.1)
    score = _apply_hour_preference(
        score,
        factors,
        context,
        preferred_windows=[(6, 10), (16, 20)],
        late_penalty=(11, 15, 7),
        positive_text="the timing is better for a longer outdoor block",
        caution_text="midday hiking adds more heat pressure",
    )
    return {"score": score, "factors": factors}


def _score_picnic(context):
    score = 100.0
    factors = []
    score = _apply_temperature(
        score,
        factors,
        context,
        source_key="temperature",
        label="temperature",
        ideal_range=(20, 29),
        hard_range=(12, 35),
        warm_scale=2.4,
        cold_scale=2.6,
    )
    score = _apply_rain(score, factors, context, low_risk=12, caution_risk=28, weight=0.42, storm_penalty=30)
    score = _apply_wind(score, factors, context, calm_max=14, caution_max=24, weight=0.88)
    score = _apply_humidity(score, factors, context, comfortable_max=65, caution_max=80, weight=0.22)
    score = _apply_cloud_cover(score, factors, context, ideal_range=(15, 55), caution_max=82, weight=0.24, allow_bonus=True)
    score = _apply_hour_preference(
        score,
        factors,
        context,
        preferred_windows=[(9, 18)],
        late_penalty=(19, 23, 8),
        positive_text="daylight timing lines up well for a picnic",
        caution_text="later timing cuts into picnic comfort",
    )
    return {"score": score, "factors": factors}


def _score_photo(context):
    score = 100.0
    factors = []
    score = _apply_visibility(score, factors, context, clear_min=9, caution_min=5.5, weight=7.2)
    score = _apply_cloud_cover(score, factors, context, ideal_range=(20, 70), caution_max=92, weight=0.16, allow_bonus=True)
    score = _apply_rain(score, factors, context, low_risk=10, caution_risk=25, weight=0.36, storm_penalty=26)
    score = _apply_wind(score, factors, context, calm_max=18, caution_max=30, weight=0.46)
    score = _apply_hour_preference(
        score,
        factors,
        context,
        preferred_windows=[(6, 9), (16, 19)],
        late_penalty=(11, 15, 4),
        positive_text="the light is more favorable for outdoor photos",
        caution_text="flat midday light makes outdoor shots less dynamic",
    )
    return {"score": score, "factors": factors}


def _apply_temperature(
    score,
    factors,
    context,
    source_key,
    label,
    ideal_range,
    hard_range,
    warm_scale,
    cold_scale,
):
    value = context[source_key]
    ideal_low, ideal_high = ideal_range
    hard_low, hard_high = hard_range
    midpoint = (ideal_low + ideal_high) / 2

    if ideal_low <= value <= ideal_high:
        bonus = max(4.0, 9.0 - abs(value - midpoint) * 0.9)
        score += bonus
        _record_factor(factors, bonus, "positive", f"{label} is comfortable ({_format_temperature(value, context)})")
        return score

    if value > ideal_high:
        penalty = (value - ideal_high) * warm_scale
        if value > hard_high:
            penalty += 12 + (value - hard_high) * (warm_scale + 0.8)
        score -= penalty
        descriptor = "feels-like heat is high" if source_key == "feels_like" else "temperature is running hot"
        _record_factor(factors, penalty, "negative", f"{descriptor} ({_format_temperature(value, context)})")
        return score

    penalty = (ideal_low - value) * cold_scale
    if value < hard_low:
        penalty += 10 + (hard_low - value) * (cold_scale + 0.6)
    score -= penalty
    descriptor = "it feels cold" if source_key == "feels_like" else "temperature is on the cold side"
    _record_factor(factors, penalty, "negative", f"{descriptor} ({_format_temperature(value, context)})")
    return score


def _apply_humidity(score, factors, context, comfortable_max, caution_max, weight, dry_penalty=0.18):
    humidity = context["humidity"]
    if humidity <= comfortable_max:
        bonus = max(2.0, 6.0 - max(0, humidity - 45) * 0.12)
        score += bonus
        _record_factor(factors, bonus, "positive", f"humidity feels manageable ({humidity}%)")
        if humidity < 28:
            dry_penalty_points = (28 - humidity) * dry_penalty
            score -= dry_penalty_points
            _record_factor(factors, dry_penalty_points, "negative", f"air is quite dry ({humidity}%)")
        return score

    penalty = (humidity - comfortable_max) * weight
    if humidity > caution_max:
        penalty += 8 + (humidity - caution_max) * (weight + 0.08)
    score -= penalty
    _record_factor(factors, penalty, "negative", f"humidity is elevated ({humidity}%)")
    return score


def _apply_rain(score, factors, context, low_risk, caution_risk, weight, storm_penalty):
    rain_chance = context["rain_chance"]
    if rain_chance <= low_risk and context["condition"] not in {"Rainy", "Thunderstorm"}:
        bonus = max(2.0, 7.0 - rain_chance * 0.18)
        score += bonus
        _record_factor(factors, bonus, "positive", f"rain risk is low ({rain_chance}%)")
        return score

    penalty = max(0.0, rain_chance - low_risk) * weight
    if rain_chance > caution_risk:
        penalty += 12 + (rain_chance - caution_risk) * (weight + 0.1)
    if context["condition"] == "Rainy" and context["rain_total"] >= 0.2:
        penalty += 10
        _record_factor(factors, 10, "negative", "rain is already active")
    if context["condition"] == "Thunderstorm":
        penalty += storm_penalty
        _record_factor(factors, storm_penalty, "negative", "storm conditions are active")
    if penalty > 0:
        _record_factor(factors, penalty, "negative", f"rain risk is elevated ({rain_chance}%)")
    score -= penalty
    return score


def _apply_wind(score, factors, context, calm_max, caution_max, weight):
    wind = context["wind"]
    if wind <= calm_max:
        bonus = max(1.5, 5.5 - wind * 0.16)
        score += bonus
        _record_factor(factors, bonus, "positive", f"wind stays fairly light ({_format_wind(wind, context)})")
        return score

    penalty = (wind - calm_max) * weight
    if wind > caution_max:
        penalty += 9 + (wind - caution_max) * (weight + 0.18)
    score -= penalty
    _record_factor(factors, penalty, "negative", f"wind is stronger than ideal ({_format_wind(wind, context)})")
    return score


def _apply_uv(score, factors, context, caution_uv, severe_uv, weight):
    if not context["is_day"] or context["uv_index"] <= 0:
        return score

    uv_index = context["uv_index"]
    if uv_index <= caution_uv:
        return score

    penalty = (uv_index - caution_uv) * weight
    if uv_index > severe_uv:
        penalty += 5 + (uv_index - severe_uv) * (weight * 0.55)
    score -= penalty
    _record_factor(factors, penalty, "negative", f"UV is high for this time of day ({round(uv_index, 1)})")
    return score


def _apply_visibility(score, factors, context, clear_min, caution_min, weight):
    visibility = context["visibility"]
    if visibility >= clear_min:
        bonus = min(6.0, 2.5 + (visibility - clear_min) * 0.35)
        score += bonus
        _record_factor(factors, bonus, "positive", f"visibility is clear ({round(visibility, 1)} km)")
        return score

    if visibility >= caution_min:
        penalty = (clear_min - visibility) * weight * 0.5
        score -= penalty
        _record_factor(factors, penalty, "negative", f"visibility is softer than usual ({round(visibility, 1)} km)")
        return score

    penalty = (clear_min - visibility) * weight
    score -= penalty
    _record_factor(factors, penalty, "negative", f"visibility is reduced ({round(visibility, 1)} km)")
    return score


def _apply_cloud_cover(score, factors, context, ideal_range, caution_max, weight, allow_bonus=False):
    cloud_cover = context["cloud_cover"]
    ideal_low, ideal_high = ideal_range
    if ideal_low <= cloud_cover <= ideal_high:
        if allow_bonus:
            bonus = 4.0
            score += bonus
            _record_factor(factors, bonus, "positive", f"cloud cover looks balanced ({cloud_cover}%)")
        return score

    if cloud_cover > caution_max:
        penalty = (cloud_cover - caution_max) * weight + 8
        score -= penalty
        _record_factor(factors, penalty, "negative", f"cloud cover is heavy ({cloud_cover}%)")
        return score

    if cloud_cover > ideal_high:
        penalty = (cloud_cover - ideal_high) * weight
        score -= penalty
        _record_factor(factors, penalty, "negative", f"cloud cover is higher than ideal ({cloud_cover}%)")
        return score

    if cloud_cover < ideal_low:
        if allow_bonus:
            bonus = 2.0
            score += bonus
            _record_factor(factors, bonus, "positive", "the sky looks open enough")
        return score

    return score


def _apply_hour_preference(score, factors, context, preferred_windows, late_penalty, positive_text, caution_text):
    hour = context["hour"]
    preferred_time_key = str(context.get("preferred_time_key") or "").strip().lower()
    if preferred_time_key and _phase_key_for_hour(hour) == preferred_time_key:
        bonus = 5.0
        score += bonus
        _record_factor(factors, bonus, "positive", "this lines up with your preferred time of day")
    in_preferred_window = any(start <= hour < end for start, end in preferred_windows)
    if in_preferred_window:
        bonus = 7.0
        score += bonus
        _record_factor(factors, bonus, "positive", positive_text)
        return score

    penalty_start, penalty_end, penalty_value = late_penalty
    if penalty_start <= hour < penalty_end:
        score -= penalty_value
        _record_factor(factors, penalty_value, "negative", caution_text)
    return score


def _record_factor(factors, impact, direction, text):
    if impact <= 1.5:
        return
    factors.append(
        {
            "impact": round(float(impact), 1),
            "direction": direction,
            "text": text,
        }
    )


def _build_explanation(config, label, score, factors):
    positives = sorted((item for item in factors if item["direction"] == "positive"), key=lambda item: item["impact"], reverse=True)
    negatives = sorted((item for item in factors if item["direction"] == "negative"), key=lambda item: item["impact"], reverse=True)

    if config["label_mode"] == "jacket":
        return _build_jacket_explanation(label, positives, negatives)
    if config["label_mode"] == "umbrella":
        return _build_umbrella_explanation(label, positives, negatives)

    if score >= 70:
        chosen = positives[:3] or negatives[:2]
        connector = "thanks to" if positives else "because"
        return f"{label} for {config['noun']} right now {connector} {_join_reason_texts(chosen)}."

    if score >= 50:
        chosen_negatives = negatives[:2]
        chosen_positives = positives[:1]
        if chosen_negatives and chosen_positives:
            return (
                f"{label} for {config['noun']} right now, but {_join_reason_texts(chosen_negatives)} "
                f"hold it back even though {_join_reason_texts(chosen_positives)}."
            )
        if chosen_negatives:
            return f"{label} for {config['noun']} right now because {_join_reason_texts(chosen_negatives)}."
        return f"{label} for {config['noun']} right now thanks to {_join_reason_texts(chosen_positives)}."

    chosen = negatives[:3] or positives[:2]
    return f"{label} for {config['noun']} right now because {_join_reason_texts(chosen)}."


def _build_jacket_explanation(label, positives, negatives):
    if label == "Recommended":
        chosen = positives[:3] or negatives[:2]
        return f"A jacket is recommended because {_join_reason_texts(chosen)}."
    if label == "Optional / light layer":
        chosen = positives[:2] or negatives[:1]
        return f"A light jacket could help because {_join_reason_texts(chosen)}."
    chosen = negatives[:2] or positives[:1]
    return f"A jacket is not needed because {_join_reason_texts(chosen)}."


def _build_umbrella_explanation(label, positives, negatives):
    if label == "Recommended":
        chosen = positives[:3] or negatives[:1]
        return f"An umbrella is recommended because {_join_reason_texts(chosen)}."
    if label == "Maybe carry one":
        chosen = positives[:2] or negatives[:1]
        return f"A compact umbrella could help because {_join_reason_texts(chosen)}."
    chosen = negatives[:2] or positives[:1]
    return f"An umbrella is not needed because {_join_reason_texts(chosen)}."


def _join_reason_texts(items):
    texts = [str(item["text"]).strip() for item in items if str(item.get("text") or "").strip()]
    if not texts:
        return "conditions are fairly balanced"
    if len(texts) == 1:
        return texts[0]
    if len(texts) == 2:
        return f"{texts[0]} and {texts[1]}"
    return f"{texts[0]}, {texts[1]}, and {texts[2]}"


def _build_best_time_recommendation(activity_key, config, weather_to_show, current_context, current_score, use_fahrenheit, speed_unit, personalization=None):
    if config["label_mode"] != "standard" or config["block_hours"] <= 0:
        return ""

    local_now = _get_local_now(weather_to_show)
    current_hour = local_now.replace(minute=0, second=0, microsecond=0)
    hourly_points = _collect_hourly_points(weather_to_show)
    if not hourly_points:
        return ""

    comparison_now = current_hour.replace(tzinfo=None) if hourly_points[0]["time_dt"].tzinfo is None else current_hour
    future_points = [point for point in hourly_points if point["time_dt"] >= comparison_now][:18]
    if len(future_points) < config["block_hours"]:
        return ""

    scored_points = []
    for point in future_points:
        context = _build_hourly_context(point, use_fahrenheit, speed_unit, personalization)
        score_details = _score_activity(activity_key, context)
        scored_points.append({**point, "context": context, "score": _clamp(score_details["score"], 0, 100)})

    block_hours = max(1, min(config["block_hours"], len(scored_points)))
    best_block = None
    best_score = -1
    for index in range(0, len(scored_points) - block_hours + 1):
        block = scored_points[index : index + block_hours]
        block_score = mean(item["score"] for item in block)
        if block_score > best_score:
            best_block = block
            best_score = block_score

    if not best_block:
        return ""

    best_start = best_block[0]["time_dt"]
    best_end = best_block[-1]["time_dt"] + timedelta(hours=1)
    best_is_now = abs((best_start - comparison_now).total_seconds()) < 3600

    if best_is_now and best_score >= current_score - 5:
        if current_score < 55:
            return "Now is one of the better windows today, but conditions still stay limited."
        return "Now is one of the best times today."

    if current_score >= 80 and best_score <= current_score + 6:
        return "Now is one of the best times today."

    if best_score < current_score + 8 and current_score >= 55:
        return ""

    current_reference = _summarize_context(current_context)
    best_reference = _summarize_context(_summarize_block_context(best_block, use_fahrenheit, speed_unit))
    reason = _describe_improvement(current_reference, best_reference)
    window_label = _format_time_window(best_start, best_end, comparison_now)
    return f"Better {window_label} when {reason}."


def _build_hourly_context(point, use_fahrenheit, speed_unit, personalization=None):
    hour = point["time_dt"].hour
    temperature = float(point.get("temperature") or 0)
    humidity = int(round(point.get("humidity") or 0))
    wind = float(point.get("wind") or 0)
    condition = str(point.get("condition") or "Cloudy")
    cloud_cover = int(round(point.get("cloud_cover") or 0))
    profile = _normalize_personalization(personalization)
    return {
        "time_dt": point["time_dt"],
        "hour": hour,
        "local_time_label": point["time_dt"].strftime("%I:%M %p").lstrip("0"),
        "temperature": temperature + profile["temperature_offset"],
        "feels_like": _estimate_feels_like(temperature, humidity, wind) + profile["temperature_offset"],
        "humidity": humidity,
        "wind": wind,
        "rain_chance": int(round(point.get("rain_chance") or 0)),
        "rain_total": float(point.get("rain_total") or 0),
        "condition": condition,
        "uv_index": _estimate_hourly_uv(point.get("day_uv", 0), hour, point.get("is_day", 6 <= hour < 18)),
        "visibility": _estimate_visibility(condition, cloud_cover),
        "cloud_cover": cloud_cover,
        "is_day": bool(point.get("is_day", 6 <= hour < 18)),
        "use_fahrenheit": bool(use_fahrenheit),
        "speed_unit": speed_unit or "km/h",
        "preferred_time_key": profile["preferred_time_key"],
    }


def _summarize_block_context(block, use_fahrenheit, speed_unit):
    first = block[0]["context"]
    return {
        "time_dt": first["time_dt"],
        "hour": first["hour"],
        "local_time_label": first["local_time_label"],
        "temperature": mean(item["context"]["temperature"] for item in block),
        "feels_like": mean(item["context"]["feels_like"] for item in block),
        "humidity": round(mean(item["context"]["humidity"] for item in block)),
        "wind": mean(item["context"]["wind"] for item in block),
        "rain_chance": round(mean(item["context"]["rain_chance"] for item in block)),
        "rain_total": mean(item["context"]["rain_total"] for item in block),
        "condition": first["condition"],
        "uv_index": mean(item["context"]["uv_index"] for item in block),
        "visibility": mean(item["context"]["visibility"] for item in block),
        "cloud_cover": round(mean(item["context"]["cloud_cover"] for item in block)),
        "is_day": any(item["context"]["is_day"] for item in block),
        "use_fahrenheit": bool(use_fahrenheit),
        "speed_unit": speed_unit or "km/h",
    }


def _summarize_context(context):
    return {
        "temperature": float(context["temperature"]),
        "feels_like": float(context["feels_like"]),
        "humidity": int(round(context["humidity"])),
        "wind": float(context["wind"]),
        "rain_chance": int(round(context["rain_chance"])),
        "uv_index": float(context["uv_index"]),
        "visibility": float(context["visibility"]),
    }


def _describe_improvement(current_context, future_context):
    improvements = []
    if future_context["feels_like"] <= current_context["feels_like"] - 4:
        improvements.append("temperatures feel more comfortable")
    if future_context["rain_chance"] <= current_context["rain_chance"] - 18:
        improvements.append("rain chances drop")
    if future_context["wind"] <= current_context["wind"] - 7:
        improvements.append("wind eases")
    if future_context["humidity"] <= current_context["humidity"] - 10:
        improvements.append("humidity backs off")
    if future_context["uv_index"] <= current_context["uv_index"] - 2:
        improvements.append("UV softens")
    if future_context["visibility"] >= current_context["visibility"] + 2:
        improvements.append("visibility improves")

    if not improvements:
        return "conditions balance out more cleanly"
    if len(improvements) == 1:
        return improvements[0]
    return f"{improvements[0]} and {improvements[1]}"


def _label_from_score(score, label_mode):
    if label_mode == "jacket":
        if score >= 75:
            return "Recommended"
        if score >= 45:
            return "Optional / light layer"
        return "Not needed"

    if label_mode == "umbrella":
        if score >= 70:
            return "Recommended"
        if score >= 35:
            return "Maybe carry one"
        return "Not needed"

    if score >= 85:
        return "Great"
    if score >= 70:
        return "Good"
    if score >= 50:
        return "Okay"
    if score >= 30:
        return "Caution"
    return "Avoid"


def _collect_hourly_points(weather_to_show):
    forecast = (weather_to_show or {}).get("forecast") or []
    hourly_points = []
    for day in forecast[:2]:
        for point in day.get("hourly") or []:
            point_dt = _parse_point_datetime(point)
            if not point_dt:
                continue
            hourly_points.append({**point, "time_dt": point_dt, "day_uv": day.get("uv_index", 0)})
    hourly_points.sort(key=lambda item: item["time_dt"])
    return hourly_points


def _parse_point_datetime(point):
    time_iso = point.get("time_iso")
    if time_iso:
        try:
            return datetime.fromisoformat(str(time_iso))
        except ValueError:
            return None

    try:
        return datetime.strptime(f"{point['date']} {point['time']}", "%Y-%m-%d %I:%M %p")
    except (KeyError, TypeError, ValueError):
        return None


def _get_local_now(weather_to_show):
    time_info = (weather_to_show or {}).get("time") or {}
    location = (weather_to_show or {}).get("location") or {}
    timezone_name = time_info.get("timezone") or location.get("timezone")

    if timezone_name:
        try:
            return datetime.now(ZoneInfo(timezone_name))
        except ZoneInfoNotFoundError:
            pass

    for key in ["local_datetime_iso", "observed_at"]:
        raw_value = time_info.get(key)
        if not raw_value:
            continue
        try:
            return datetime.fromisoformat(str(raw_value))
        except ValueError:
            continue

    return datetime.now()


def _estimate_hourly_uv(day_uv, hour, is_day):
    if not is_day or not day_uv:
        return 0.0
    if 11 <= hour <= 15:
        return float(day_uv)
    if 9 <= hour < 11 or 15 < hour <= 17:
        return round(float(day_uv) * 0.72, 1)
    if 7 <= hour < 9 or 17 < hour <= 18:
        return round(float(day_uv) * 0.38, 1)
    return round(float(day_uv) * 0.2, 1)


def _estimate_feels_like(temperature, humidity, wind):
    feels_like = float(temperature or 0)
    if feels_like >= 24:
        feels_like += max(0.0, float(humidity or 0) - 55) * 0.08
    if feels_like <= 14:
        feels_like -= min(float(wind or 0), 35.0) * 0.05
    else:
        feels_like -= min(float(wind or 0), 28.0) * 0.018
    return round(feels_like, 1)


def _estimate_visibility(condition, cloud_cover):
    if condition == "Foggy":
        return 1.8
    if condition == "Thunderstorm":
        return 3.8
    if condition == "Snowy":
        return 4.6
    if condition == "Rainy":
        return 6.4
    if cloud_cover >= 90:
        return 8.0
    return 10.0


def _phase_key_for_hour(hour):
    if 5 <= hour < 11:
        return "morning"
    if 11 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 21:
        return "evening"
    return "night"


def _format_time_window(start_dt, end_dt, reference_dt):
    day_prefix = ""
    if start_dt.date() == reference_dt.date() + timedelta(days=1):
        day_prefix = "tomorrow "
    elif start_dt.date() != reference_dt.date():
        day_prefix = f"{start_dt.strftime('%A').lower()} "

    start_label = start_dt.strftime("%I %p").lstrip("0")
    end_label = end_dt.strftime("%I %p").lstrip("0")
    if start_dt.strftime("%p") == end_dt.strftime("%p"):
        return f"{day_prefix}{start_dt.strftime('%I').lstrip('0')}-{end_label}".strip()
    return f"{day_prefix}{start_label} - {end_label}".strip()


def _format_temperature(value, context):
    if context.get("use_fahrenheit"):
        return f'{round((float(value) * 9 / 5) + 32, 1)}°F'
    return f'{round(float(value), 1)}°C'


def _format_wind(value, context):
    if str(context.get("speed_unit") or "km/h").lower() == "mph":
        return f'{round(float(value) * 0.621371, 1)} mph'
    return f'{round(float(value), 1)} km/h'


def _format_temperature(value, context):
    if context.get("use_fahrenheit"):
        converted = round((float(value) * 9 / 5) + 32, 1)
        return f"{converted}\u00b0F"
    return f"{round(float(value), 1)}\u00b0C"


def _clamp(value, minimum, maximum):
    return max(minimum, min(int(round(value)), maximum))
