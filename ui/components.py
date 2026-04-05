import base64
import hashlib
import json
from datetime import datetime, timedelta
from html import escape
from pathlib import Path
from textwrap import dedent
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import streamlit as st
import streamlit.components.v1 as components


BACKGROUND_MAP = {
    "Sunny": "images/sunny.png",
    "Rainy": "images/rainy.png",
    "Snowy": "images/snowy.png",
    "Thunderstorm": "images/thunderstorm.png",
    "Foggy": "images/foggy.png",
    "Cloudy": "images/cloudy.png",
}

CONDITION_ICON_MAP = {
    "Sunny": "\u2600\ufe0f",
    "Cloudy": "\u2601\ufe0f",
    "Rainy": "\U0001f327\ufe0f",
    "Snowy": "\u2744\ufe0f",
    "Thunderstorm": "\u26c8\ufe0f",
    "Foggy": "\U0001f32b\ufe0f",
}

SKY_PHASE_STYLE_MAP = {
    "night": {
        "image": "images/night.png",
        "body": "#0b1a2c",
        "top": "rgba(7, 18, 34, 0.74)",
        "bottom": "rgba(17, 45, 74, 0.82)",
        "horizon": "rgba(104, 138, 186, 0.24)",
        "glow": "rgba(218, 232, 255, 0.14)",
        "glow_position": "78% 18%",
    },
    "sunrise": {
        "image": "images/sunrise.png",
        "body": "#243753",
        "top": "rgba(52, 72, 108, 0.48)",
        "bottom": "rgba(245, 171, 122, 0.44)",
        "horizon": "rgba(255, 209, 147, 0.26)",
        "glow": "rgba(255, 216, 168, 0.28)",
        "glow_position": "18% 20%",
    },
    "morning": {
        "image": "images/morning.png",
        "body": "#324765",
        "top": "rgba(58, 92, 136, 0.40)",
        "bottom": "rgba(194, 222, 249, 0.24)",
        "horizon": "rgba(255, 234, 193, 0.16)",
        "glow": "rgba(255, 237, 192, 0.20)",
        "glow_position": "22% 16%",
    },
    "day": {
        "image": "images/sunny.jpg",
        "body": "#415a78",
        "top": "rgba(84, 121, 168, 0.34)",
        "bottom": "rgba(214, 232, 250, 0.18)",
        "horizon": "rgba(245, 250, 255, 0.12)",
        "glow": "rgba(255, 242, 209, 0.18)",
        "glow_position": "18% 14%",
    },
    "twilight": {
        "image": "images/sunset.png",
        "body": "#2a3551",
        "top": "rgba(54, 66, 98, 0.54)",
        "bottom": "rgba(149, 116, 133, 0.30)",
        "horizon": "rgba(219, 170, 143, 0.18)",
        "glow": "rgba(214, 184, 160, 0.18)",
        "glow_position": "82% 18%",
    },
    "sunset": {
        "image": "images/sunset.png",
        "body": "#35415c",
        "top": "rgba(78, 93, 135, 0.48)",
        "bottom": "rgba(232, 146, 108, 0.38)",
        "horizon": "rgba(255, 196, 144, 0.24)",
        "glow": "rgba(255, 197, 138, 0.24)",
        "glow_position": "80% 18%",
    },
    "evening": {
        "image": "images/evening.png",
        "body": "#202f47",
        "top": "rgba(38, 53, 81, 0.58)",
        "bottom": "rgba(92, 118, 159, 0.30)",
        "horizon": "rgba(153, 171, 204, 0.16)",
        "glow": "rgba(186, 208, 245, 0.14)",
        "glow_position": "82% 18%",
    },
}

WEATHER_STYLE_MAP = {
    "Sunny": {
        "tint_top": "rgba(255, 255, 255, 0.02)",
        "tint_bottom": "rgba(255, 209, 134, 0.04)",
        "texture": None,
        "texture_opacity": 0.0,
        "texture_blend": "normal",
    },
    "Cloudy": {
        "tint_top": "rgba(88, 113, 145, 0.16)",
        "tint_bottom": "rgba(45, 70, 98, 0.22)",
        "texture": "images/cloudy.jpg",
        "texture_opacity": 0.075,
        "texture_blend": "soft-light",
    },
    "Rainy": {
        "tint_top": "rgba(34, 62, 96, 0.22)",
        "tint_bottom": "rgba(11, 28, 50, 0.30)",
        "texture": "images/rainy.jpg",
        "texture_opacity": 0.13,
        "texture_blend": "soft-light",
    },
    "Snowy": {
        "tint_top": "rgba(201, 224, 255, 0.10)",
        "tint_bottom": "rgba(117, 151, 191, 0.16)",
        "texture": "images/snowy.jpg",
        "texture_opacity": 0.11,
        "texture_blend": "screen",
    },
    "Thunderstorm": {
        "tint_top": "rgba(16, 28, 52, 0.34)",
        "tint_bottom": "rgba(4, 12, 24, 0.42)",
        "texture": "images/thunderstorm.png",
        "texture_opacity": 0.22,
        "texture_blend": "overlay",
    },
    "Foggy": {
        "tint_top": "rgba(194, 207, 220, 0.14)",
        "tint_bottom": "rgba(120, 140, 160, 0.20)",
        "texture": "images/foggy.png",
        "texture_opacity": 0.14,
        "texture_blend": "screen",
    },
}


def get_background_path(condition):
    return BACKGROUND_MAP.get(condition, "images/default.png")


def _clamp(value, minimum, maximum):
    return max(minimum, min(maximum, value))


def _stable_variant_index(parts, variant_count):
    normalized = "|".join(str(part or "") for part in parts)
    digest = hashlib.md5(normalized.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % max(1, variant_count)


def _get_weather_local_datetime(weather):
    if not weather:
        return datetime.now()

    time_info = weather.get("time") or {}
    location = weather.get("location") or {}
    timezone_name = time_info.get("timezone") or location.get("timezone")
    raw_value = time_info.get("local_datetime_iso") or time_info.get("observed_at") or ""

    if raw_value:
        try:
            parsed = datetime.fromisoformat(raw_value)
            if parsed.tzinfo is None and timezone_name:
                try:
                    return parsed.replace(tzinfo=ZoneInfo(timezone_name))
                except ZoneInfoNotFoundError:
                    return parsed
            return parsed
        except ValueError:
            pass

    if timezone_name:
        try:
            return datetime.now(ZoneInfo(timezone_name))
        except ZoneInfoNotFoundError:
            pass

    return datetime.now()


def _parse_clock_value(clock_label, reference_date, timezone_info):
    if not clock_label or clock_label == "--":
        return None

    try:
        parsed_time = datetime.strptime(clock_label.strip(), "%I:%M %p").time()
    except ValueError:
        return None

    combined = datetime.combine(reference_date, parsed_time)
    if timezone_info is not None:
        combined = combined.replace(tzinfo=timezone_info)
    return combined


def _get_sun_window(weather, local_now):
    forecast = weather.get("forecast") or []
    if not forecast:
        return None, None

    local_day_key = local_now.date().isoformat()
    forecast_today = next((day for day in forecast if day.get("date") == local_day_key), forecast[0])
    timezone_info = local_now.tzinfo
    sunrise = _parse_clock_value(forecast_today.get("sunrise"), local_now.date(), timezone_info)
    sunset = _parse_clock_value(forecast_today.get("sunset"), local_now.date(), timezone_info)
    return sunrise, sunset


def _get_sky_phase(local_now, sunrise, sunset):
    fallback_hour = local_now.hour + (local_now.minute / 60)
    if sunrise and sunset:
        sunrise_start = sunrise - timedelta(minutes=40)
        sunrise_end = sunrise + timedelta(minutes=55)
        sunset_start = sunset - timedelta(minutes=32)
        sunset_end = sunset + timedelta(minutes=14)
        twilight_end = sunset + timedelta(minutes=46)
        evening_end = sunset + timedelta(minutes=105)
        late_afternoon_cutoff = local_now.replace(hour=16, minute=30, second=0, microsecond=0)

        if sunrise_start <= local_now <= sunrise_end:
            return "sunrise"
        if sunset_start <= local_now <= sunset_end:
            return "sunset"
        if sunset_end < local_now <= twilight_end:
            return "twilight"
        if local_now < sunrise_start:
            return "night"
        if local_now > twilight_end:
            return "evening" if local_now < evening_end else "night"
        if local_now < local_now.replace(hour=11, minute=0, second=0, microsecond=0):
            return "morning"
        if local_now < late_afternoon_cutoff:
            return "day"
        return "evening"

    if fallback_hour < 5:
        return "night"
    if fallback_hour < 7:
        return "sunrise"
    if fallback_hour < 11:
        return "morning"
    if fallback_hour < 17:
        return "day"
    if fallback_hour < 19.5:
        return "sunset"
    if fallback_hour < 22:
        return "evening"
    return "night"


def _build_star_layers(star_opacity):
    if star_opacity <= 0:
        return []

    return [
        f"radial-gradient(circle at 12% 18%, rgba(255,255,255,{star_opacity:.3f}) 0 1.2px, transparent 2px)",
        f"radial-gradient(circle at 28% 32%, rgba(255,255,255,{star_opacity * 0.82:.3f}) 0 1px, transparent 1.8px)",
        f"radial-gradient(circle at 46% 12%, rgba(255,255,255,{star_opacity * 0.72:.3f}) 0 1.2px, transparent 2px)",
        f"radial-gradient(circle at 62% 26%, rgba(255,255,255,{star_opacity * 0.90:.3f}) 0 1px, transparent 1.8px)",
        f"radial-gradient(circle at 78% 20%, rgba(255,255,255,{star_opacity * 0.75:.3f}) 0 1.1px, transparent 1.9px)",
        f"radial-gradient(circle at 88% 34%, rgba(255,255,255,{star_opacity * 0.64:.3f}) 0 1px, transparent 1.8px)",
    ]


def _svg_data_uri(svg_markup):
    return f"data:image/svg+xml;base64,{base64.b64encode(svg_markup.encode('utf-8')).decode()}"


def _build_translucent_image_layer(image_path, opacity):
    if not image_path or opacity <= 0:
        return None

    encoded_image = encode_image(image_path)
    image_mime = get_image_mime_type(image_path)
    blur_amount = 0.8 if "cloudy" in str(image_path).lower() else 0.5 if "rainy" in str(image_path).lower() else 0.35
    svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900" preserveAspectRatio="xMidYMid slice">
        <defs>
            <filter id="textureBlur">
                <feGaussianBlur stdDeviation="{blur_amount:.2f}"/>
            </filter>
        </defs>
        <image href="data:{image_mime};base64,{encoded_image}" width="1600" height="900" opacity="{opacity:.3f}" preserveAspectRatio="xMidYMid slice" filter="url(#textureBlur)"/>
    </svg>
    """
    return f'url("{_svg_data_uri(svg)}") center/cover fixed'


def _get_nearest_hourly_snapshot(weather, local_now):
    forecast = (weather or {}).get("forecast") or []
    if not forecast:
        return None

    local_reference = local_now.replace(tzinfo=None)
    candidates = []
    for day in forecast[:2]:
        for point in day.get("hourly") or []:
            iso_value = point.get("time_iso")
            if not iso_value:
                continue
            try:
                point_dt = datetime.fromisoformat(iso_value).replace(tzinfo=None)
            except ValueError:
                continue
            delta_seconds = abs((point_dt - local_reference).total_seconds())
            candidates.append((delta_seconds, point))

    if not candidates:
        return None

    nearest_delta, nearest_point = min(candidates, key=lambda item: item[0])
    return nearest_point if nearest_delta <= 7200 else None


def _build_cloud_layers(phase, cloud_cover, variant_index=0):
    if cloud_cover <= 8:
        return []

    density = _clamp(cloud_cover / 100, 0.0, 1.0)
    if phase in {"night", "evening"}:
        cloud_color = f"rgba(183, 202, 232, {0.14 + density * 0.14:.3f})"
        edge_color = f"rgba(66, 88, 120, {0.10 + density * 0.10:.3f})"
    elif phase in {"sunrise", "sunset"}:
        cloud_color = f"rgba(244, 206, 185, {0.12 + density * 0.12:.3f})"
        edge_color = f"rgba(128, 103, 118, {0.08 + density * 0.08:.3f})"
    else:
        cloud_color = f"rgba(240, 247, 255, {0.10 + density * 0.12:.3f})"
        edge_color = f"rgba(122, 151, 183, {0.08 + density * 0.07:.3f})"

    blur = 30 + int(density * 30)
    cloud_profiles = [
        {
            "specs": [
                (170, 148, 260, 84, 0.88),
                (500, 128, 320, 90, 0.78),
                (860, 150, 300, 84, 0.84),
                (1185, 144, 264, 78, 0.70),
                (1410, 184, 230, 68, 0.64),
                (340, 244, 236, 68, 0.44),
                (1030, 246, 254, 74, 0.40),
                (678, 228, 220, 64, 0.34),
            ],
            "wash_height": 320,
        },
        {
            "specs": [
                (120, 118, 218, 70, 0.74),
                (370, 190, 244, 74, 0.56),
                (700, 122, 350, 94, 0.82),
                (1060, 168, 262, 78, 0.64),
                (1375, 126, 248, 72, 0.68),
                (510, 264, 206, 60, 0.34),
                (1220, 244, 224, 64, 0.32),
            ],
            "wash_height": 290,
        },
        {
            "specs": [
                (190, 212, 270, 80, 0.58),
                (530, 218, 336, 88, 0.64),
                (930, 196, 354, 96, 0.72),
                (1315, 220, 286, 84, 0.56),
                (360, 112, 206, 62, 0.32),
                (1080, 120, 218, 66, 0.36),
                (1470, 148, 182, 54, 0.28),
            ],
            "wash_height": 260,
        },
        {
            "specs": [
                (150, 150, 240, 74, 0.82),
                (430, 118, 276, 82, 0.72),
                (760, 172, 252, 74, 0.60),
                (1010, 124, 310, 92, 0.82),
                (1320, 170, 246, 74, 0.58),
                (270, 270, 196, 56, 0.26),
                (890, 262, 204, 58, 0.30),
                (1450, 236, 170, 48, 0.22),
            ],
            "wash_height": 300,
        },
    ]
    selected_profile = cloud_profiles[variant_index % len(cloud_profiles)]
    cloud_specs = selected_profile["specs"]
    visible_count = 5 if density < 0.34 else 6 if density < 0.58 else 7 if density < 0.82 else len(cloud_specs)
    cloud_markup = []
    for cx, cy, rx, ry, opacity in cloud_specs[:visible_count]:
        alpha = opacity * (0.52 + density * 0.44)
        cloud_markup.append(
            f"""
            <g opacity="{alpha:.3f}">
                <ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="{cloud_color}" filter="url(#cloudBlur)"/>
                <ellipse cx="{cx - (rx * 0.16):.1f}" cy="{cy + 10}" rx="{rx * 0.72:.1f}" ry="{ry * 0.78:.1f}" fill="{edge_color}" filter="url(#cloudBlurSoft)"/>
                <ellipse cx="{cx + (rx * 0.18):.1f}" cy="{cy - 4}" rx="{rx * 0.52:.1f}" ry="{ry * 0.64:.1f}" fill="{cloud_color}" filter="url(#cloudBlurSoft)"/>
            </g>
            """
        )
    svg = f"""
    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900" preserveAspectRatio="xMidYMin slice">
        <defs>
            <linearGradient id="topWash" x1="0" y1="0" x2="0" y2="1">
                <stop offset="0%" stop-color="{cloud_color}" stop-opacity="{0.10 + density * 0.10:.3f}"/>
                <stop offset="100%" stop-color="{edge_color}" stop-opacity="0"/>
            </linearGradient>
            <filter id="cloudBlur" x="-25%" y="-25%" width="150%" height="150%">
                <feGaussianBlur stdDeviation="{blur}"/>
            </filter>
            <filter id="cloudBlurSoft" x="-25%" y="-25%" width="150%" height="150%">
                <feGaussianBlur stdDeviation="{max(12, blur - 12)}"/>
            </filter>
        </defs>
        <rect width="1600" height="900" fill="transparent"/>
        <rect width="1600" height="{selected_profile['wash_height']}" fill="url(#topWash)"/>
        {''.join(cloud_markup)}
    </svg>
    """
    return [
        f'url("{_svg_data_uri(svg)}") center top / cover no-repeat',
        f"linear-gradient(180deg, rgba(255,255,255,{0.012 + density * 0.022:.3f}) 0%, rgba(255,255,255,0) 45%)",
    ]


def _build_weather_overlay_layers(condition, intensity, phase, variant_index=0):
    overlay_intensity = _clamp(intensity, 0.0, 1.0)
    if overlay_intensity <= 0:
        return []

    if condition == "Rainy":
        rain_variants = [
            {"count": 34, "x_step": 43, "y_step": 59, "dx": 26, "base": 46, "step": 14},
            {"count": 40, "x_step": 37, "y_step": 47, "dx": 18, "base": 38, "step": 11},
            {"count": 28, "x_step": 52, "y_step": 61, "dx": 34, "base": 58, "step": 18},
        ]
        rain = rain_variants[variant_index % len(rain_variants)]
        stroke_alpha = 0.12 + overlay_intensity * 0.18
        drops = []
        for index in range(rain["count"]):
            x = 40 + ((index * rain["x_step"]) % 1520)
            y = -120 + ((index * rain["y_step"]) % 760)
            length = rain["base"] + (index % 5) * rain["step"]
            drops.append(
                f'<line x1="{x}" y1="{y}" x2="{x - rain["dx"]}" y2="{y + length}" stroke="rgba(212,228,255,{stroke_alpha:.3f})" stroke-width="{1.0 + (index % 3) * 0.34:.2f}" stroke-linecap="round"/>'
            )
        svg = f"""
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900" preserveAspectRatio="none">
            <defs>
                <filter id="rainBlur"><feGaussianBlur stdDeviation="{0.24 + overlay_intensity * 0.5:.2f}"/></filter>
            </defs>
            <g filter="url(#rainBlur)">{''.join(drops)}</g>
        </svg>
        """
        return [
            f'url("{_svg_data_uri(svg)}") center/cover no-repeat',
            f"linear-gradient(180deg, rgba(157, 188, 232, {0.035 + overlay_intensity * 0.042:.3f}) 0%, rgba(255,255,255,0) 54%)",
        ]

    if condition == "Thunderstorm":
        storm_variants = [
            {"count": 34, "x_step": 37, "y_step": 53, "dx": 30, "base": 52, "step": 18, "lightning": True},
            {"count": 40, "x_step": 41, "y_step": 57, "dx": 36, "base": 66, "step": 20, "lightning": False},
            {"count": 36, "x_step": 35, "y_step": 49, "dx": 24, "base": 44, "step": 14, "lightning": True},
        ]
        storm = storm_variants[variant_index % len(storm_variants)]
        stroke_alpha = 0.16 + overlay_intensity * 0.18
        drops = []
        for index in range(storm["count"]):
            x = 34 + ((index * storm["x_step"]) % 1530)
            y = -140 + ((index * storm["y_step"]) % 760)
            length = storm["base"] + (index % 4) * storm["step"]
            drops.append(
                f'<line x1="{x}" y1="{y}" x2="{x - storm["dx"]}" y2="{y + length}" stroke="rgba(228,236,255,{stroke_alpha:.3f})" stroke-width="{1.2 + (index % 3) * 0.44:.2f}" stroke-linecap="round"/>'
            )
        lightning = ""
        if storm["lightning"]:
            lightning = '<polyline points="1240,110 1182,242 1236,242 1176,392" fill="none" stroke="rgba(248,250,255,0.42)" stroke-width="6" stroke-linecap="round" stroke-linejoin="round"/>'
        svg = f"""
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900" preserveAspectRatio="none">
            <defs>
                <filter id="stormBlur"><feGaussianBlur stdDeviation="{0.32 + overlay_intensity * 0.54:.2f}"/></filter>
            </defs>
            <g filter="url(#stormBlur)">{''.join(drops)}</g>
            {lightning}
        </svg>
        """
        return [
            f'url("{_svg_data_uri(svg)}") center/cover no-repeat',
            f"radial-gradient(circle at 78% 20%, rgba(240,245,255,{0.03 + overlay_intensity * 0.06:.3f}) 0%, rgba(255,255,255,0) 12%)",
        ]

    if condition == "Snowy":
        snow_variants = [
            {"count": 62, "x_step": 57, "y_step": 71, "radius": 0.52},
            {"count": 78, "x_step": 49, "y_step": 63, "radius": 0.42},
            {"count": 54, "x_step": 67, "y_step": 79, "radius": 0.68},
        ]
        snow = snow_variants[variant_index % len(snow_variants)]
        flake_alpha = 0.20 + overlay_intensity * 0.18
        flakes = []
        for index in range(snow["count"]):
            x = 28 + ((index * snow["x_step"]) % 1540)
            y = 22 + ((index * snow["y_step"]) % 860)
            radius = 0.9 + (index % 4) * snow["radius"]
            flakes.append(
                f'<circle cx="{x}" cy="{y}" r="{radius:.2f}" fill="rgba(255,255,255,{flake_alpha - (index % 3) * 0.05:.3f})"/>'
            )
        svg = f"""
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900" preserveAspectRatio="none">
            <defs>
                <filter id="snowBlur"><feGaussianBlur stdDeviation="{0.22 + overlay_intensity * 0.28:.2f}"/></filter>
            </defs>
            <g filter="url(#snowBlur)">{''.join(flakes)}</g>
        </svg>
        """
        return [
            f'url("{_svg_data_uri(svg)}") center/cover no-repeat',
            f"linear-gradient(180deg, rgba(226,236,255,{0.025 + overlay_intensity * 0.035:.3f}) 0%, rgba(255,255,255,0) 55%)",
        ]

    if condition == "Foggy":
        fog_variants = [
            [(320, 650, 360, 96, 0.72), (890, 610, 420, 110, 0.78), (1320, 690, 310, 88, 0.64)],
            [(260, 620, 410, 118, 0.68), (760, 570, 470, 122, 0.72), (1280, 640, 360, 96, 0.58)],
            [(360, 700, 320, 90, 0.62), (920, 640, 390, 108, 0.70), (1380, 600, 280, 78, 0.48)],
        ]
        fog_variant = fog_variants[variant_index % len(fog_variants)]
        fog_alpha = 0.06 + overlay_intensity * 0.08
        svg = f"""
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1600 900" preserveAspectRatio="none">
            <defs>
                <filter id="fogBlur"><feGaussianBlur stdDeviation="{22 + overlay_intensity * 18:.1f}"/></filter>
            </defs>
            <g filter="url(#fogBlur)">
                {''.join(
                    f'<ellipse cx="{cx}" cy="{cy}" rx="{rx}" ry="{ry}" fill="rgba(223,232,242,{fog_alpha * alpha:.3f})"/>'
                    for cx, cy, rx, ry, alpha in fog_variant
                )}
            </g>
        </svg>
        """
        return [
            f'url("{_svg_data_uri(svg)}") center/cover no-repeat',
            f"linear-gradient(180deg, rgba(228,236,245,{fog_alpha:.3f}) 0%, rgba(214,226,238,{fog_alpha * 0.45:.3f}) 36%, rgba(255,255,255,0) 72%)",
        ]

    if condition == "Cloudy" and phase in {"night", "evening"}:
        return [
            f"linear-gradient(180deg, rgba(110,128,158,{0.04 + overlay_intensity * 0.05:.3f}) 0%, rgba(255,255,255,0) 48%)",
        ]

    return []


def get_background_profile(weather):
    local_now = _get_weather_local_datetime(weather)
    current = (weather or {}).get("current") or {}
    hourly_snapshot = _get_nearest_hourly_snapshot(weather, local_now) or {}
    condition = hourly_snapshot.get("condition") or current.get("condition") or "Cloudy"
    cloud_cover = int(round(hourly_snapshot.get("cloud_cover", current.get("cloud_cover", 0)) or 0))
    precipitation = float(
        max(
            current.get("precipitation", 0) or 0,
            hourly_snapshot.get("rain_total", 0) or 0,
        )
    )
    rain_chance = int(round(hourly_snapshot.get("rain_chance", 0) or 0))
    temperature = float(hourly_snapshot.get("temperature", current.get("temperature", 0)) or 0)

    visual_condition = condition
    if condition in {"Rainy", "Cloudy"} and temperature <= 1 and max(rain_chance, precipitation * 100) >= 18:
        visual_condition = "Snowy"

    variant_seed = [
        (weather or {}).get("resolved_city"),
        (weather or {}).get("time", {}).get("local_date"),
        (weather or {}).get("time", {}).get("local_time"),
        visual_condition,
    ]
    sunrise, sunset = _get_sun_window(weather or {}, local_now)
    phase = _get_sky_phase(local_now, sunrise, sunset)
    phase_style = SKY_PHASE_STYLE_MAP.get(phase, SKY_PHASE_STYLE_MAP["day"])
    weather_style = WEATHER_STYLE_MAP.get(visual_condition, WEATHER_STYLE_MAP["Cloudy"])
    cloud_variant_index = _stable_variant_index(variant_seed + [phase, "clouds"], 4)
    weather_variant_index = _stable_variant_index(variant_seed + [phase, "weather"], 3)

    cloud_factor = _clamp(cloud_cover / 100, 0.0, 1.0)
    precipitation_factor = _clamp(precipitation / 2.0, 0.0, 1.0)
    atmospheric_weight = max(cloud_factor, precipitation_factor)

    precipitation_intensity = _clamp(max(precipitation / 1.2, rain_chance / 100), 0.0, 1.0)
    cloud_layers = _build_cloud_layers(phase, cloud_cover, cloud_variant_index)
    weather_overlay_layers = _build_weather_overlay_layers(
        visual_condition,
        precipitation_intensity if visual_condition in {"Rainy", "Thunderstorm", "Snowy"} else atmospheric_weight,
        phase,
        weather_variant_index,
    )
    weather_overlay_opacity = 0.0
    if weather_overlay_layers:
        weather_overlay_opacity = round(
            _clamp(weather_style["texture_opacity"] + (atmospheric_weight * 0.20), 0.08, 0.42),
            3,
        )

    star_opacity = 0.0
    if phase in {"night", "evening"} and condition in {"Sunny", "Cloudy"}:
        star_opacity = _clamp((1 - cloud_factor) * (0.24 if condition == "Sunny" else 0.07), 0.0, 0.24)

    effect_layers = [
        f"radial-gradient(circle at {phase_style['glow_position']}, {phase_style['glow']} 0%, rgba(255,255,255,0) 26%)",
        f"radial-gradient(circle at 50% 86%, {phase_style['horizon']} 0%, rgba(255,255,255,0) 58%)",
    ]
    effect_layers.extend(_build_star_layers(star_opacity))

    texture_gradient = (
        f"linear-gradient(180deg, {weather_style['tint_top']} 0%, {weather_style['tint_bottom']} 100%)"
    )
    day_dim_strength = 0.0
    if phase in {"day", "morning"}:
        day_dim_strength = 0.065 if visual_condition == "Sunny" else 0.085
    elif phase in {"sunrise", "sunset", "twilight"}:
        day_dim_strength = 0.04
    dim_layer = (
        f"linear-gradient(180deg, rgba(10, 16, 28, {day_dim_strength:.3f}) 0%, rgba(10, 16, 28, {day_dim_strength * 0.6:.3f}) 100%)"
        if day_dim_strength > 0
        else None
    )

    base_layers = []
    if dim_layer:
        base_layers.append(dim_layer)
    base_layers.extend(
        [
            f"linear-gradient(180deg, {phase_style['top']} 0%, {phase_style['bottom']} 100%)",
            texture_gradient,
        ]
    )
    return {
        "base_image_path": phase_style["image"],
        "texture_image_path": weather_style["texture"],
        "texture_opacity": round(
            _clamp(weather_style["texture_opacity"] + (atmospheric_weight * 0.08), 0.0, 0.26),
            3,
        ) if weather_style["texture"] else 0.0,
        "texture_blend_mode": weather_style["texture_blend"],
        "base_layers": base_layers,
        "effect_layers": effect_layers,
        "atmosphere_layers": cloud_layers,
        "weather_overlay_layers": weather_overlay_layers,
        "weather_overlay_opacity": weather_overlay_opacity,
        "weather_overlay_blend_mode": "screen" if visual_condition in {"Snowy", "Foggy"} else "soft-light",
        "has_dim_layer": bool(dim_layer),
        "phase_key": phase,
        "background_color": phase_style["body"],
    }


def get_condition_icon(condition):
    return CONDITION_ICON_MAP.get(condition, "\U0001f30d")


def get_temp_icon(value):
    if value > 30:
        return "\U0001f525"
    if value > 10:
        return "\U0001f324\ufe0f"
    return "\u2744\ufe0f"


def get_humidity_icon(value):
    if value > 60:
        return "\U0001f4a6"
    if value > 40:
        return "\U0001f32b\ufe0f"
    return "\U0001f335"


def get_feels_like_icon(value):
    if value > 30:
        return "\U0001f525"
    if value > 10:
        return "\U0001f324\ufe0f"
    return "\u2744\ufe0f"


def get_wind_icon(value):
    if value > 25:
        return "\U0001f32c\ufe0f"
    if value > 10:
        return "\U0001f4a8"
    return "\U0001f343"


def format_precipitation(value):
    return f"{round(value, 1)} mm"


def encode_image(image_path):
    return base64.b64encode(Path(image_path).read_bytes()).decode()


def get_image_mime_type(image_path):
    if Path(image_path).suffix.lower() == ".png":
        return "image/png"
    return "image/jpeg"


def get_weather_local_time_display(weather):
    if not weather:
        return {
            "local_time": "--",
            "local_date": "",
            "timezone_abbr": "",
        }

    location = weather.get("location") or {}
    time_info = weather.get("time") or {}
    timezone_name = time_info.get("timezone") or location.get("timezone")

    if timezone_name:
        try:
            local_now = datetime.now(ZoneInfo(timezone_name))
            return {
                "local_time": local_now.strftime("%I:%M %p").lstrip("0"),
                "local_date": local_now.strftime("%a, %b %d"),
                "timezone_abbr": local_now.strftime("%Z") or "",
            }
        except ZoneInfoNotFoundError:
            pass

    return {
        "local_time": time_info.get("local_time") or "--",
        "local_date": time_info.get("local_date") or "",
        "timezone_abbr": time_info.get("timezone_abbr") or "",
    }


def apply_theme(background_source):
    if isinstance(background_source, dict):
        profile = background_source
    else:
        profile = {
            "base_image_path": background_source,
            "texture_image_path": None,
            "texture_opacity": 0.0,
            "texture_blend_mode": "normal",
            "base_layers": [
                "linear-gradient(180deg, rgba(8, 31, 58, 0.50), rgba(15, 53, 88, 0.58))",
            ],
            "effect_layers": [],
            "atmosphere_layers": [],
            "weather_overlay_layers": [],
            "weather_overlay_opacity": 0.0,
            "weather_overlay_blend_mode": "normal",
            "background_color": "#102741",
        }

    base_image_path = profile["base_image_path"]
    background_image_layer = None
    if base_image_path:
        encoded_background = encode_image(base_image_path)
        background_mime = get_image_mime_type(base_image_path)
        background_image_layer = f'url("data:{background_mime};base64,{encoded_background}") center/cover fixed'

    base_layers = list(profile.get("base_layers") or [])
    atmosphere_layers = list(profile.get("atmosphere_layers") or [])
    effect_layers = list(profile.get("effect_layers") or [])
    weather_overlay_layers = list(profile.get("weather_overlay_layers") or [])
    texture_layer = _build_translucent_image_layer(
        profile.get("texture_image_path"),
        float(profile.get("texture_opacity", 0.0) or 0.0),
    )
    composed_background_layers = weather_overlay_layers.copy()
    background_blend_modes = [profile.get("weather_overlay_blend_mode", "soft-light")] * len(weather_overlay_layers)
    if texture_layer:
        composed_background_layers.append(texture_layer)
        background_blend_modes.append(profile.get("texture_blend_mode", "soft-light"))
    composed_background_layers.extend(atmosphere_layers)
    atmosphere_blend = "screen" if profile.get("phase_key") in {"night", "evening", "twilight"} else "soft-light"
    background_blend_modes.extend([atmosphere_blend] * len(atmosphere_layers))
    composed_background_layers.extend(effect_layers)
    background_blend_modes.extend(["screen"] * len(effect_layers))
    composed_background_layers.extend(base_layers)
    if base_layers:
        if profile.get("has_dim_layer"):
            background_blend_modes.extend(["multiply"] + ["normal"] * (len(base_layers) - 1))
        else:
            background_blend_modes.extend(["normal"] * len(base_layers))
    if background_image_layer:
        composed_background_layers.append(background_image_layer)
        background_blend_modes.append("normal")
    base_background_value = ",\n                ".join(composed_background_layers)
    background_blend_value = ", ".join(background_blend_modes)
    st.markdown(
        f"""
        <style>
        iframe[title="streamlit_searchbox.searchbox"] {{
            border-radius: 38px;
            overflow: hidden;
            background: transparent;
            box-shadow: none;
        }}
        div[data-testid="stElementContainer"]:has(iframe[title="streamlit_searchbox.searchbox"]) {{
            padding: 0.18rem;
            border-radius: 40px;
            background:
                linear-gradient(180deg, rgba(255,255,255,0.16), rgba(255,255,255,0.05)),
                linear-gradient(140deg, rgba(205, 232, 247, 0.12), rgba(255,255,255,0.02));
            border: 1px solid rgba(255,255,255,0.16);
            box-shadow:
                0 18px 42px rgba(4, 14, 28, 0.18),
                inset 0 1px 0 rgba(255,255,255,0.22);
            backdrop-filter: blur(24px);
        }}
        div[data-testid="stElementContainer"]:has(iframe[title="streamlit_searchbox.searchbox"]) iframe[title="streamlit_searchbox.searchbox"] {{
            box-shadow: none;
        }}
        iframe[title*="skyline_search"],
        iframe[src*="skyline_search"] {{
            border-radius: 42px;
            overflow: hidden;
            display: block;
            border: 0 !important;
            background: transparent !important;
            background-color: transparent !important;
            box-shadow: none;
        }}
        div[data-testid="stElementContainer"]:has(iframe[title*="skyline_search"]),
        div[data-testid="stElementContainer"]:has(iframe[src*="skyline_search"]),
        div[data-testid="stCustomComponentV1"]:has(iframe[title*="skyline_search"]),
        div[data-testid="stCustomComponentV1"]:has(iframe[src*="skyline_search"]) {{
            padding: 0;
            background: transparent !important;
            background-color: transparent !important;
            border: 0 !important;
            box-shadow: none !important;
            backdrop-filter: none !important;
        }}
        div[data-testid="stElementContainer"]:has(iframe[title*="skyline_search"]) iframe,
        div[data-testid="stElementContainer"]:has(iframe[src*="skyline_search"]) iframe,
        div[data-testid="stCustomComponentV1"]:has(iframe[title*="skyline_search"]) iframe,
        div[data-testid="stCustomComponentV1"]:has(iframe[src*="skyline_search"]) iframe {{
            box-shadow: none !important;
            background: transparent !important;
            background-color: transparent !important;
        }}
        div[data-testid="stCustomComponentV1"] {{
            border-radius: 34px;
            overflow: hidden;
            background: transparent !important;
            background-color: transparent !important;
        }}
        div[data-testid="stCustomComponentV1"] iframe {{
            border-radius: 34px !important;
            overflow: hidden !important;
            background: transparent !important;
            background-color: transparent !important;
            display: block;
        }}
        section[data-testid="stSidebar"] {{
            display: none;
        }}
        .stApp {{
            background:
                {base_background_value};
            background-blend-mode: {background_blend_value};
            background-color: {profile.get("background_color", "#102741")};
            color: #eef8ff;
        }}
        html, body {{
            background: {profile.get("background_color", "#102741")};
        }}
        .stApp [data-testid="stHeader"] {{
            background: transparent;
        }}
        .block-container {{
            max-width: 100%;
            padding-top: clamp(11rem, 17vw, 12.1rem);
            padding-bottom: 2rem;
            padding-left: clamp(1rem, 3vw, 2.5rem);
            padding-right: clamp(1rem, 3vw, 2.5rem);
        }}
        html {{
            scroll-padding-top: 10.8rem;
        }}
        .stTextInput [data-baseweb="base-input"] {{
            background: transparent !important;
        }}
        .stTextInput > div[data-baseweb="base-input"] > div,
        .stTextInput > div[data-baseweb="input"] {{
            min-height: 4.5rem;
            border-radius: 26px;
            background: linear-gradient(180deg, rgba(255, 255, 255, 0.22), rgba(255, 255, 255, 0.12));
            border: 1px solid rgba(255, 255, 255, 0.24);
            box-shadow: 0 16px 42px rgba(5, 19, 36, 0.18);
            backdrop-filter: blur(14px);
            overflow: hidden;
        }}
        .stTextInput div[data-baseweb="input"] > div {{
            background: transparent !important;
        }}
        .stTextInput input {{
            height: 4.5rem;
            font-size: 1.28rem;
            padding-left: 1.15rem;
            background: transparent;
            color: #f4fbff;
            border: 0;
        }}
        div[data-testid="stDateInput"] label p {{
            color: rgba(238, 248, 255, 0.84);
            font-weight: 600;
        }}
        div[data-testid="stDateInput"] [data-baseweb="input"] {{
            min-height: 3.15rem;
            border-radius: 22px;
            background: linear-gradient(180deg, rgba(255,255,255,0.16), rgba(255,255,255,0.08));
            border: 1px solid rgba(255,255,255,0.16);
            box-shadow: 0 12px 30px rgba(4, 15, 32, 0.14);
            backdrop-filter: blur(14px);
        }}
        div[data-testid="stDateInput"] input {{
            color: #f4fbff !important;
            background: transparent !important;
        }}
        div[data-testid="stDateInput"] button {{
            color: #eef8ff !important;
        }}
        div[data-baseweb="popover"],
        div[data-baseweb="calendar"] {{
            background: transparent !important;
        }}
        div[data-baseweb="popover"] div[data-baseweb="calendar"] {{
            padding: 0.55rem;
            border-radius: 24px !important;
            background: linear-gradient(180deg, rgba(17, 39, 67, 0.96), rgba(8, 24, 42, 0.94)) !important;
            border: 1px solid rgba(255,255,255,0.14) !important;
            box-shadow: 0 18px 42px rgba(4, 15, 32, 0.24) !important;
            backdrop-filter: blur(18px);
        }}
        div[data-baseweb="popover"] div[data-baseweb="calendar"] *,
        div[data-baseweb="popover"] div[data-baseweb="calendar"] span,
        div[data-baseweb="popover"] div[data-baseweb="calendar"] svg {{
            color: #eef8ff !important;
            fill: #eef8ff !important;
        }}
        div[data-baseweb="popover"] div[data-baseweb="calendar"] button {{
            border-radius: 14px !important;
            color: #eef8ff !important;
            background: transparent !important;
        }}
        div[data-baseweb="popover"] div[data-baseweb="calendar"] button:hover {{
            background: rgba(255,255,255,0.08) !important;
        }}
        div[data-baseweb="popover"] div[data-baseweb="calendar"] button[aria-selected="true"],
        div[data-baseweb="popover"] div[data-baseweb="calendar"] [data-selected="true"] {{
            background: linear-gradient(135deg, rgba(214, 239, 250, 0.3), rgba(169, 215, 235, 0.22)) !important;
            border-color: rgba(255,255,255,0.18) !important;
            box-shadow: 0 10px 24px rgba(4, 15, 32, 0.16) !important;
            color: #ffffff !important;
        }}
        div[data-baseweb="popover"] div[data-baseweb="calendar"] div[data-baseweb="select"] > div {{
            min-height: 2.45rem;
            border-radius: 14px;
            background: rgba(255,255,255,0.08) !important;
            border: 1px solid rgba(255,255,255,0.12) !important;
            box-shadow: none !important;
        }}
        div[data-baseweb="popover"] div[data-baseweb="calendar"] div[data-baseweb="select"] span,
        div[data-baseweb="popover"] div[data-baseweb="calendar"] div[data-baseweb="select"] input,
        div[data-baseweb="popover"] div[data-baseweb="calendar"] div[data-baseweb="select"] svg {{
            color: #eef8ff !important;
            fill: #eef8ff !important;
        }}
        .stButton button {{
            border-radius: 22px;
            font-weight: 600;
        }}
        .stButton button[kind="primary"] {{
            min-height: 4.45rem;
            border: 1px solid rgba(255, 255, 255, 0.20);
            background: linear-gradient(135deg, rgba(214, 239, 250, 0.28), rgba(169, 215, 235, 0.16));
            color: #f4fbff;
            box-shadow: 0 12px 30px rgba(6, 20, 37, 0.16);
        }}
        .stButton button[kind="primary"]:hover {{
            border-color: rgba(255, 255, 255, 0.30);
            background: linear-gradient(135deg, rgba(225, 246, 255, 0.36), rgba(177, 220, 239, 0.22));
        }}
        .stButton button[kind="secondary"] {{
            min-height: 2.8rem;
            border: 1px solid rgba(255, 255, 255, 0.14);
            background: linear-gradient(180deg, rgba(255, 255, 255, 0.18), rgba(255, 255, 255, 0.08));
            color: #eef8ff;
            box-shadow: 0 10px 24px rgba(4, 15, 32, 0.14);
        }}
        div[data-testid="stDialog"] div[role="dialog"] {{
            background: linear-gradient(180deg, rgba(17, 39, 67, 0.55), rgba(9, 28, 48, 0.45));
            backdrop-filter: blur(18px);
            border: 1px solid rgba(255, 255, 255, 0.14);
        }}
        div[data-testid="stDialog"] {{
            background: rgba(6, 16, 28, 0.32);
            backdrop-filter: blur(6px);
        }}
        div[data-testid="stExpander"] {{
            border-radius: 24px;
            background: linear-gradient(180deg, rgba(255,255,255,0.14), rgba(255,255,255,0.06));
            border: 1px solid rgba(255,255,255,0.12);
            box-shadow: 0 14px 36px rgba(4, 15, 32, 0.12);
            backdrop-filter: blur(14px);
        }}
        .glass,
        .topbar,
        .hero,
        .metric-card,
        .forecast-card,
        .suggestions {{
            background: linear-gradient(180deg, rgba(255, 255, 255, 0.18), rgba(255, 255, 255, 0.08));
            border: 1px solid rgba(255, 255, 255, 0.16);
            box-shadow: 0 16px 44px rgba(4, 15, 32, 0.18);
            backdrop-filter: blur(16px);
        }}
        .topbar {{
            border-radius: 0;
            padding: 0.6rem 0 1rem 0;
            margin-bottom: 1.15rem;
            text-align: center;
            background: transparent;
            border: 0;
            box-shadow: none;
            backdrop-filter: none;
        }}
        .summary-city {{
            font-size: clamp(1.5rem, 2.5vw, 2.15rem);
            font-weight: 700;
        }}
        .summary-time {{
            margin-top: 0.42rem;
            font-size: 0.9rem;
            letter-spacing: 0.04em;
            opacity: 0.8;
        }}
        .summary-temp {{
            margin-top: 0.3rem;
            font-size: clamp(2.6rem, 5vw, 4rem);
            font-weight: 800;
            line-height: 1;
        }}
        .summary-condition {{
            margin-top: 0.45rem;
            font-size: 1.05rem;
            opacity: 0.94;
        }}
        .summary-range {{
            margin-top: 0.45rem;
            font-size: 1rem;
            opacity: 0.84;
        }}
        .skyline-persistent-nav-anchor {{
            width: 0;
            height: 0;
            overflow: hidden;
        }}
        .skyline-persistent-nav-marker-block {{
            display: none !important;
            height: 0 !important;
            min-height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
        }}
        .skyline-persistent-nav-bridge-block {{
            display: none !important;
            height: 0 !important;
            min-height: 0 !important;
            margin: 0 !important;
            padding: 0 !important;
        }}
        .skyline-persistent-nav-bridge-block iframe {{
            display: block !important;
            height: 0 !important;
            min-height: 0 !important;
            border: 0 !important;
        }}
        div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell {{
            position: fixed;
            top: 0;
            left: 0;
            right: 0;
            width: auto;
            max-width: none !important;
            z-index: 140;
            margin: 0 !important;
            min-height: 9.55rem;
            padding-top: 1.76rem;
            padding-right: clamp(0.42rem, 1vw, 0.92rem);
            padding-bottom: 1.34rem;
            padding-left: clamp(0.14rem, 0.6vw, 0.42rem);
            border-radius: 0 0 32px 32px;
            overflow: hidden;
            background: linear-gradient(180deg, rgba(18, 35, 56, 0.34), rgba(18, 35, 56, 0.12) 62%, rgba(18, 35, 56, 0.02));
            border: 0;
            box-shadow: none;
            backdrop-filter: blur(10px);
            transition:
                min-height 0.28s ease,
                padding-top 0.28s ease,
                padding-bottom 0.28s ease,
                padding-left 0.28s ease,
                padding-right 0.28s ease,
                background 0.28s ease,
                backdrop-filter 0.28s ease;
        }}
        div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell::before {{
            content: "";
            position: absolute;
            inset: 0 0 0.12rem 0;
            border-radius: 0 0 32px 32px;
            background: linear-gradient(180deg, rgba(83, 104, 128, 0.2), rgba(56, 73, 96, 0.3));
            border-bottom: 1px solid rgba(255,255,255,0.14);
            box-shadow: 0 18px 38px rgba(4, 15, 32, 0.16);
            pointer-events: none;
            transition:
                inset 0.28s ease,
                border-radius 0.28s ease,
                box-shadow 0.28s ease,
                background 0.28s ease;
        }}
        div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell::after {{
            content: "";
            position: absolute;
            inset: 0 0 0.12rem 0;
            border-radius: 0 0 32px 32px;
            background:
                linear-gradient(180deg, rgba(255,255,255,0.1), transparent 38%),
                linear-gradient(90deg, rgba(255,255,255,0), rgba(255,255,255,0.08), rgba(255,255,255,0));
            pointer-events: none;
            transition:
                inset 0.28s ease,
                border-radius 0.28s ease,
                opacity 0.28s ease;
        }}
        div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell > div {{
            position: relative;
            z-index: 1;
        }}
        div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell div[data-testid="stHorizontalBlock"] {{
            align-items: center;
            gap: 0.04rem;
            min-height: 4.9rem;
            padding-top: 0.08rem;
            transition: min-height 0.28s ease, padding-top 0.28s ease;
        }}
        div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell div[data-testid="column"] {{
            display: flex;
            align-items: center;
            justify-content: flex-start;
            min-height: 4.9rem;
            transition: min-height 0.28s ease;
        }}
        div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell div[data-testid="column"] > div {{
            width: 100%;
            display: flex;
            align-items: center;
            justify-content: flex-start;
            min-height: 4.9rem;
            transition: min-height 0.28s ease;
        }}
        .skyline-nav-brand {{
            display: flex;
            align-items: center;
            justify-content: flex-start;
            min-height: 3.2rem;
            padding-left: 0.18rem;
            margin-top: -0.16rem;
            transition: min-height 0.28s ease, margin-top 0.28s ease;
        }}
        .skyline-nav-brand img {{
            display: block;
            width: min(100%, 318px);
            height: auto;
            object-fit: contain;
            transform: translateY(-0.06rem);
            filter: drop-shadow(0 8px 18px rgba(7, 19, 34, 0.24));
            transition: width 0.28s ease, transform 0.28s ease, filter 0.28s ease;
        }}
        div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell .stButton {{
            width: 100%;
            display: flex;
            align-items: center;
        }}
        div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell .stButton button[kind="primary"],
        div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell .stButton button[kind="secondary"] {{
            min-height: 2.42rem;
            border-radius: 12px;
            font-size: 1.24rem !important;
            font-weight: 600;
            border: 0 !important;
            padding: 0 0.16rem;
            line-height: 1.04;
            white-space: nowrap;
            box-shadow: none;
            transition:
                background 0.22s ease,
                color 0.22s ease,
                transform 0.22s ease,
                box-shadow 0.22s ease,
                min-height 0.28s ease;
        }}
        div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell .stButton button[kind="primary"] {{
            background: rgba(255, 255, 255, 0.055);
            color: #ffffff;
            box-shadow: inset 0 -1.5px 0 rgba(214, 239, 250, 0.58);
        }}
        div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell .stButton button[kind="secondary"] {{
            background: transparent;
            color: rgba(238, 248, 255, 0.84);
        }}
        div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell .stButton button:hover {{
            background: transparent;
            color: #ffffff;
            transform: translateY(-1px);
        }}
        div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell .stButton button p,
        div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell .stButton button span {{
            font-size: 1.24rem !important;
            font-weight: 600 !important;
            line-height: 1.04 !important;
        }}
        div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell.is-condensed {{
            min-height: 6.95rem;
            padding-top: 0.88rem;
            padding-bottom: 0.74rem;
            backdrop-filter: blur(8px);
        }}
        div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell.is-condensed::before,
        div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell.is-condensed::after {{
            inset: 0 0 0.08rem 0;
            border-radius: 0 0 26px 26px;
        }}
        div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell.is-condensed::before {{
            box-shadow: 0 12px 26px rgba(4, 15, 32, 0.13);
        }}
        div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell.is-condensed div[data-testid="stHorizontalBlock"] {{
            min-height: 3.64rem;
            padding-top: 0;
        }}
        div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell.is-condensed div[data-testid="column"],
        div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell.is-condensed div[data-testid="column"] > div {{
            min-height: 3.64rem;
        }}
        div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell.is-condensed .skyline-nav-brand {{
            min-height: 2.9rem;
            margin-top: -0.08rem;
        }}
        div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell.is-condensed .skyline-nav-brand img {{
            width: min(100%, 292px);
            transform: translateY(-0.02rem);
            filter: drop-shadow(0 6px 14px rgba(7, 19, 34, 0.2));
        }}
        div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell.is-condensed .stButton button[kind="primary"],
        div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell.is-condensed .stButton button[kind="secondary"] {{
            min-height: 2.18rem;
        }}
        .settings-shell {{
            display: flex;
            justify-content: flex-end;
            margin-bottom: 0.75rem;
        }}
        .stButton button[kind="tertiary"] {{
            min-height: 4.4rem;
            min-width: 4.4rem;
            height: 4.4rem;
            width: 4.4rem;
            padding: 0;
            background: linear-gradient(180deg, rgba(255,255,255,0.22), rgba(255,255,255,0.08));
            border: 1px solid rgba(255,255,255,0.2);
            box-shadow: 0 12px 30px rgba(4, 15, 32, 0.16);
            border-radius: 999px;
            font-size: 2.65rem;
            line-height: 1;
            transition: transform 0.28s ease, color 0.28s ease;
        }}
        .stButton button[kind="tertiary"]:hover {{
            background: linear-gradient(180deg, rgba(255,255,255,0.28), rgba(255,255,255,0.11));
            border: 1px solid rgba(255,255,255,0.26);
            color: #ffffff;
            transform: scale(1.05);
        }}
        .hero {{
            border-radius: 30px;
            padding: 1.55rem 1.7rem;
            color: #f6fbff;
        }}
        .hero-kicker {{
            font-size: 0.9rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            opacity: 0.82;
        }}
        .hero-city {{
            font-size: 2.25rem;
            font-weight: 700;
            margin-top: 0.25rem;
        }}
        .hero-condition {{
            font-size: 1.02rem;
            opacity: 0.93;
            margin-top: 0.45rem;
        }}
        .hero-temp {{
            text-align: right;
            font-size: 3rem;
            font-weight: 800;
            line-height: 1;
        }}
        .hero-feels {{
            text-align: right;
            margin-top: 0.55rem;
            font-size: 0.98rem;
            opacity: 0.9;
        }}
        .section-title {{
            font-size: 1.16rem;
            font-weight: 700;
            margin: 0.35rem 0 0.95rem 0;
        }}
        .section-divider {{
            display: block;
            width: 100%;
            clear: both;
            height: 1px;
            margin: 1.45rem 0 1.2rem;
            background: linear-gradient(90deg, rgba(255,255,255,0), rgba(255,255,255,0.22), rgba(255,255,255,0));
            opacity: 0.88;
        }}
        .section-divider--persistent {{
            position: relative;
            z-index: 2;
            margin: 1.8rem 0 1.45rem;
            opacity: 0.94;
        }}
        .section-subtitle {{
            margin-top: -0.45rem;
            margin-bottom: 0.95rem;
            opacity: 0.78;
        }}
        .insight-section-header {{
            margin: 0.2rem 0 1rem;
        }}
        .insight-section-kicker {{
            font-size: 0.74rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            color: rgba(232, 244, 255, 0.68);
        }}
        .insight-section-title {{
            margin-top: 0.24rem;
            font-size: 1.32rem;
            line-height: 1.14;
            font-weight: 700;
            color: #f8fbff;
        }}
        .insight-section-subtitle {{
            margin-top: 0.45rem;
            max-width: 68ch;
            font-size: 0.95rem;
            line-height: 1.68;
            color: rgba(234, 246, 255, 0.84);
        }}
        .metric-card {{
            min-height: 136px;
            border-radius: 22px;
            padding: 1rem 1.05rem;
            margin-bottom: 1rem;
            animation: fadeUp 0.55s ease both;
        }}
        .metric-card-shell {{
            margin-bottom: 1rem;
        }}
        .metric-toggle {{
            display: none;
        }}
        .metric-toggle + .metric-card.interactive {{
            display: block;
            cursor: pointer;
            overflow: hidden;
            transition: transform 0.85s cubic-bezier(0.22, 1, 0.36, 1), box-shadow 0.7s ease, padding-bottom 0.85s ease;
        }}
        .metric-toggle + .metric-card.interactive:hover {{
            transform: translateY(-2px);
        }}
        .metric-toggle:checked + .metric-card.interactive {{
            padding-bottom: 1.05rem;
            transform: translateY(-2px);
        }}
        details.metric-card {{
            min-height: 0;
            overflow: hidden;
            transition: transform 1s cubic-bezier(0.22, 1, 0.36, 1), box-shadow 1s cubic-bezier(0.22, 1, 0.36, 1), padding-bottom 1s cubic-bezier(0.22, 1, 0.36, 1);
        }}
        details.metric-card summary {{
            list-style: none;
            cursor: pointer;
        }}
        .metric-summary {{
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 0.75rem;
        }}
        .metric-summary-copy {{
            flex: 1;
        }}
        .metric-chevron {{
            flex-shrink: 0;
            width: 1.85rem;
            height: 1.85rem;
            border-radius: 999px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.12);
            font-size: 0.95rem;
            opacity: 0.88;
            transform: rotate(0deg);
            transition: transform 0.45s ease, background 0.3s ease;
        }}
        details.metric-card summary::-webkit-details-marker {{
            display: none;
        }}
        details.metric-card[open] {{
            padding-bottom: 1.05rem;
            transform: translateY(-2px);
        }}
        details.metric-card[open] .metric-chevron {{
            transform: rotate(180deg);
            background: rgba(255, 255, 255, 0.13);
        }}
        .metric-title {{
            font-size: 0.92rem;
            opacity: 0.82;
        }}
        .metric-value {{
            margin-top: 0.45rem;
            font-size: 1.55rem;
            font-weight: 700;
            line-height: 1.24;
        }}
        .metric-subtitle {{
            margin-top: 0.5rem;
            font-size: 0.88rem;
            opacity: 0.78;
        }}
        .metric-extra {{
            margin-top: 0.9rem;
            max-height: 0;
            opacity: 0;
            overflow: hidden;
            padding-top: 0;
            border-top: 1px solid transparent;
            font-size: 0.9rem;
            transform: translateY(-0.55rem);
            transition: max-height 1s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.85s ease, padding-top 1s cubic-bezier(0.22, 1, 0.36, 1), border-color 0.8s ease, transform 1s cubic-bezier(0.22, 1, 0.36, 1);
        }}
        .metric-extra-line + .metric-extra-line {{
            margin-top: 0.45rem;
        }}
        .metric-toggle:checked + .metric-card .metric-extra {{
            max-height: 14rem;
            opacity: 0.9;
            padding-top: 0.9rem;
            border-top-color: rgba(255, 255, 255, 0.10);
            transform: translateY(0);
        }}
        .metric-toggle:checked + .metric-card .metric-chevron {{
            transform: rotate(180deg);
            background: rgba(255, 255, 255, 0.13);
        }}
        details.metric-card[open] .metric-extra {{
            max-height: 14rem;
            opacity: 0.9;
            padding-top: 0.9rem;
            border-top-color: rgba(255, 255, 255, 0.10);
            transform: translateY(0);
        }}
        .search-caption {{
            margin-bottom: 0.65rem;
            opacity: 0.84;
            text-align: center;
            font-size: 1rem;
        }}
        .suggestions {{
            border-radius: 22px;
            padding: 0.35rem 0 0 0;
            margin-top: 0.1rem;
            margin-bottom: 0.2rem;
            background: transparent;
            border: 0;
            box-shadow: none;
            backdrop-filter: none;
        }}
        .forecast-list {{
            border-radius: 28px;
            padding: 1rem 1.1rem;
            margin-top: 0.65rem;
            background: linear-gradient(180deg, rgba(255, 255, 255, 0.16), rgba(255, 255, 255, 0.08));
            border: 1px solid rgba(255, 255, 255, 0.14);
            box-shadow: 0 16px 42px rgba(4, 15, 32, 0.16);
            backdrop-filter: blur(16px);
            animation: fadeUp 0.6s ease both;
        }}
        body:has(.forecast-modal-toggle:checked) {{
            overflow: hidden;
        }}
        .forecast-row-shell + .forecast-row-shell {{
            border-top: 1px solid rgba(255, 255, 255, 0.08);
        }}
        .forecast-modal-toggle {{
            display: none;
        }}
        .forecast-item-label {{
            display: block;
            border-radius: 18px;
            cursor: pointer;
            transition: transform 0.8s cubic-bezier(0.22, 1, 0.36, 1), background 0.8s cubic-bezier(0.22, 1, 0.36, 1);
        }}
        .forecast-item-label:hover {{
            background: rgba(255,255,255,0.04);
        }}
        .forecast-item-link {{
            color: inherit;
            text-decoration: none;
        }}
        .forecast-row-form {{
            margin: 0;
        }}
        .forecast-row-button {{
            width: 100%;
            border: 0;
            padding: 0;
            background: transparent;
            color: inherit;
            font: inherit;
        }}
        details.forecast-item {{
            border-radius: 18px;
            overflow: hidden;
            transition: transform 1s cubic-bezier(0.22, 1, 0.36, 1), background 1s cubic-bezier(0.22, 1, 0.36, 1);
        }}
        details.forecast-item[open] {{
            background: rgba(255, 255, 255, 0.05);
        }}
        details.forecast-item summary {{
            list-style: none;
            cursor: pointer;
        }}
        .forecast-row {{
            position: relative;
            display: grid;
            grid-template-columns: 3.2rem 2rem 3.3rem 1fr 3.3rem 1.9rem;
            gap: 0.6rem;
            align-items: center;
            padding: 0.62rem 0;
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
            transition: transform 0.45s ease, background 0.3s ease;
        }}
        details.forecast-item summary::-webkit-details-marker {{
            display: none;
        }}
        details.forecast-item + details.forecast-item {{
            border-top: 1px solid rgba(255, 255, 255, 0.08);
        }}
        details.forecast-item[open] .forecast-chevron {{
            transform: rotate(180deg);
            background: rgba(255,255,255,0.12);
        }}
        .forecast-modal-toggle:checked + .forecast-item-label .forecast-chevron {{
            transform: rotate(180deg);
            background: rgba(255,255,255,0.12);
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
        .forecast-extra-panel {{
            max-height: 0;
            opacity: 0;
            overflow: hidden;
            padding-left: 5.8rem;
            transform: translateY(-0.45rem);
            transition: max-height 1s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.85s ease, padding-bottom 1s cubic-bezier(0.22, 1, 0.36, 1), transform 1s cubic-bezier(0.22, 1, 0.36, 1);
        }}
        details.forecast-item[open] .forecast-extra-panel {{
            max-height: 10rem;
            opacity: 0.9;
            padding-bottom: 0.7rem;
            transform: translateY(0);
        }}
        .forecast-extra-line {{
            font-size: 0.84rem;
            opacity: 0.76;
            margin-top: 0.28rem;
        }}
        .forecast-modal {{
            position: fixed;
            inset: 0;
            z-index: 99999;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: clamp(0.9rem, 2vw, 1.75rem);
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.55s ease;
        }}
        .forecast-modal-backdrop {{
            position: absolute;
            inset: 0;
            background: rgba(4, 13, 24, 0.62);
            backdrop-filter: blur(14px);
        }}
        .forecast-modal-card {{
            position: relative;
            width: min(96vw, 1420px);
            min-height: min(84vh, 860px);
            max-height: 92vh;
            display: flex;
            flex-direction: column;
            border-radius: 34px;
            padding: 1.55rem 1.55rem 1.35rem;
            background: linear-gradient(180deg, rgba(255,255,255,0.18), rgba(255,255,255,0.08));
            border: 1px solid rgba(255,255,255,0.14);
            box-shadow: 0 28px 64px rgba(4, 15, 32, 0.3);
            backdrop-filter: blur(22px);
            overflow: hidden;
            transform: translateY(26px) scale(0.97);
            transition: transform 0.8s cubic-bezier(0.22, 1, 0.36, 1);
        }}
        .forecast-modal-close {{
            position: absolute;
            top: 1.1rem;
            right: 1.1rem;
            width: 2.5rem;
            height: 2.5rem;
            border-radius: 999px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.14);
            cursor: pointer;
            font-size: 1.22rem;
        }}
        .forecast-modal-kicker {{
            font-size: 0.82rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            opacity: 0.72;
        }}
        .forecast-modal-day {{
            margin-top: 0.3rem;
            font-size: clamp(2rem, 3.4vw, 2.9rem);
            font-weight: 700;
        }}
        .forecast-modal-condition {{
            margin-top: 0.55rem;
            font-size: 1.05rem;
            opacity: 0.88;
        }}
        .forecast-modal-range {{
            margin-top: 0.7rem;
            font-size: 1.05rem;
            opacity: 0.84;
        }}
        .forecast-modal-body {{
            display: grid;
            grid-template-columns: minmax(0, 1fr) minmax(0, 1.3fr);
            gap: 1rem;
            margin-top: 1.35rem;
            flex: 1;
            min-height: 0;
        }}
        .forecast-modal-story {{
            border-radius: 26px;
            padding: 1.2rem 1.25rem;
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.08);
            min-height: 0;
        }}
        .forecast-modal-story-title {{
            font-size: 0.9rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            opacity: 0.68;
        }}
        .forecast-modal-story-copy {{
            margin-top: 0.85rem;
            font-size: 1rem;
            line-height: 1.7;
            opacity: 0.9;
        }}
        .forecast-modal-story-highlight {{
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
            margin-top: 1.2rem;
            padding: 0.5rem 0.8rem;
            border-radius: 999px;
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.08);
            font-size: 0.88rem;
        }}
        .forecast-modal-grid {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.8rem;
            align-content: start;
            overflow: auto;
            padding-right: 0.2rem;
        }}
        .forecast-modal-stat {{
            border-radius: 24px;
            padding: 1rem 1.05rem;
            background: rgba(255,255,255,0.07);
            border: 1px solid rgba(255,255,255,0.08);
        }}
        .forecast-modal-stat-label {{
            font-size: 0.82rem;
            opacity: 0.68;
        }}
        .forecast-modal-stat-value {{
            margin-top: 0.35rem;
            font-size: 1rem;
            font-weight: 700;
        }}
        .forecast-modal-toggle:checked ~ .forecast-modal {{
            opacity: 1;
            pointer-events: auto;
        }}
        .forecast-modal-toggle:checked ~ .forecast-modal .forecast-modal-card {{
            transform: translateY(0) scale(1);
        }}
        @keyframes fadeUp {{
            from {{
                opacity: 0;
                transform: translateY(18px);
            }}
            to {{
                opacity: 1;
                transform: translateY(0);
            }}
        }}
        @media (max-width: 900px) {{
            .block-container {{
                padding-left: 1rem;
                padding-right: 1rem;
            }}
            .summary-temp {{
                font-size: 2.6rem;
            }}
            .forecast-row {{
                grid-template-columns: 2.8rem 1.6rem 2.9rem 1fr 2.9rem 1.7rem;
                gap: 0.45rem;
            }}
            .forecast-modal-card {{
                width: min(95vw, 760px);
                min-height: auto;
                max-height: 92vh;
                padding: 1.2rem 1.1rem 1.05rem;
            }}
            .forecast-modal-body {{
                grid-template-columns: 1fr;
            }}
            .forecast-modal-grid {{
                grid-template-columns: 1fr;
            }}
        }}
        .forecast-card {{
            min-height: 206px;
            border-radius: 22px;
            padding: 1rem;
            color: #f7fbff;
        }}
        .forecast-day {{
            font-size: 1.02rem;
            font-weight: 700;
        }}
        .forecast-condition {{
            margin-top: 0.35rem;
            opacity: 0.9;
        }}
        .forecast-range {{
            margin-top: 0.75rem;
            font-size: 0.98rem;
        }}
        .forecast-extra {{
            margin-top: 0.35rem;
            font-size: 0.88rem;
            opacity: 0.84;
        }}
        .intel-card,
        .intel-alert-banner,
        .intel-score-card-compact,
        .intel-recommend-card,
        .intel-mini-note {{
            border-radius: 28px;
            background: linear-gradient(180deg, rgba(255,255,255,0.16), rgba(255,255,255,0.08));
            border: 1px solid rgba(255,255,255,0.14);
            box-shadow: 0 16px 42px rgba(4, 15, 32, 0.16);
            backdrop-filter: blur(16px);
        }}
        .intel-alert-banner {{
            padding: 1rem 1.05rem;
            margin: 0.15rem 0 1rem 0;
        }}
        .intel-alert-banner-grid {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.75rem;
        }}
        .intel-alert-banner-grid > .intel-alert-banner-item:only-child {{
            grid-column: 1 / -1;
            width: 100%;
        }}
        .intel-alert-banner-item {{
            display: flex;
            align-items: flex-start;
            gap: 0.8rem;
            padding: 0.9rem 0.95rem;
            border-radius: 22px;
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.08);
        }}
        .intel-alert-banner-item--danger {{
            border-color: rgba(255, 125, 125, 0.24);
            background: linear-gradient(180deg, rgba(255, 115, 115, 0.12), rgba(255,255,255,0.05));
        }}
        .intel-alert-banner-item--warning {{
            border-color: rgba(255, 213, 117, 0.24);
            background: linear-gradient(180deg, rgba(255, 213, 117, 0.12), rgba(255,255,255,0.05));
        }}
        .intel-alert-banner-item--info {{
            border-color: rgba(117, 198, 255, 0.24);
            background: linear-gradient(180deg, rgba(117, 198, 255, 0.12), rgba(255,255,255,0.05));
        }}
        .intel-alert-banner-item--notice {{
            border-color: rgba(175, 205, 255, 0.22);
            background: linear-gradient(180deg, rgba(175, 205, 255, 0.11), rgba(255,255,255,0.05));
        }}
        .intel-alert-banner-item--calm {{
            border-color: rgba(150, 237, 197, 0.22);
            background: linear-gradient(180deg, rgba(150, 237, 197, 0.10), rgba(255,255,255,0.05));
        }}
        .intel-alert-icon {{
            flex-shrink: 0;
            width: 2.4rem;
            height: 2.4rem;
            border-radius: 999px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 1rem;
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.1);
        }}
        .intel-alert-title {{
            font-size: 1rem;
            font-weight: 700;
        }}
        .intel-alert-body {{
            margin-top: 0.28rem;
            font-size: 0.9rem;
            line-height: 1.55;
            opacity: 0.84;
        }}
        .intel-card {{
            padding: 1.1rem 1.15rem;
            margin-bottom: 1rem;
        }}
        .intel-card--insight-readable {{
            padding: 1.12rem 1.14rem 1.16rem;
            background: linear-gradient(180deg, rgba(255,255,255,0.14), rgba(255,255,255,0.07));
            border: 1px solid rgba(255,255,255,0.12);
            box-shadow: 0 16px 36px rgba(4, 15, 32, 0.16);
        }}
        .intel-card-kicker {{
            font-size: 0.76rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            opacity: 0.68;
        }}
        .intel-card-title {{
            margin-top: 0.35rem;
            font-size: 1.28rem;
            font-weight: 700;
            line-height: 1.25;
        }}
        .intel-card-body {{
            margin-top: 0.55rem;
            font-size: 0.96rem;
            line-height: 1.7;
            opacity: 0.88;
        }}
        .intel-card--insight-readable .intel-card-title {{
            font-size: 1.34rem;
            line-height: 1.22;
            color: #f9fbff;
        }}
        .intel-card--insight-readable .intel-card-body {{
            font-size: 0.96rem;
            line-height: 1.72;
            opacity: 0.95;
            max-width: 66ch;
        }}
        .intel-card-note {{
            margin-top: 0.6rem;
            font-size: 0.84rem;
            line-height: 1.55;
            color: rgba(233, 245, 255, 0.7);
        }}
        .intel-support-grid {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.75rem;
            margin-top: 0.95rem;
        }}
        .intel-mini-note {{
            padding: 0.85rem 0.9rem;
            background: rgba(255,255,255,0.06);
        }}
        .intel-support-grid--insight-readable .intel-mini-note {{
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.09);
        }}
        .intel-mini-note-label {{
            font-size: 0.72rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            opacity: 0.66;
        }}
        .intel-mini-note-title {{
            margin-top: 0.3rem;
            font-size: 0.96rem;
            font-weight: 700;
        }}
        .intel-mini-note-body {{
            margin-top: 0.35rem;
            font-size: 0.88rem;
            line-height: 1.55;
            opacity: 0.82;
        }}
        .intel-score-card-compact {{
            min-height: 136px;
            padding: 0.95rem 1rem 1rem;
            margin-bottom: 1rem;
        }}
        .intel-score-label {{
            font-size: 0.76rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            opacity: 0.68;
        }}
        .intel-score-value {{
            margin-top: 0.38rem;
            font-size: 2rem;
            line-height: 1;
            font-weight: 800;
        }}
        .intel-score-value span {{
            margin-left: 0.15rem;
            font-size: 0.88rem;
            opacity: 0.7;
            font-weight: 600;
        }}
        .intel-score-summary {{
            margin-top: 0.55rem;
            font-size: 0.9rem;
            line-height: 1.62;
            opacity: 0.9;
        }}
        .intel-score-card-compact--comfort .intel-score-value {{
            color: #9cf7d4;
        }}
        .intel-score-card-compact--outdoor .intel-score-value {{
            color: #ffe698;
        }}
        .intel-score-card-compact--travel .intel-score-value {{
            color: #9dd7ff;
        }}
        .intel-recommend-card {{
            padding: 1rem 1.05rem;
            margin-bottom: 1rem;
        }}
        .intel-recommend-card--insight-readable {{
            padding: 1.08rem 1.12rem 1.14rem;
            background: linear-gradient(180deg, rgba(255,255,255,0.13), rgba(255,255,255,0.07));
            border: 1px solid rgba(255,255,255,0.12);
            box-shadow: 0 16px 36px rgba(4, 15, 32, 0.16);
        }}
        .intel-recommend-header {{
            display: flex;
            align-items: baseline;
            justify-content: space-between;
            gap: 0.75rem;
        }}
        .intel-recommend-title {{
            font-size: 1.08rem;
            font-weight: 700;
        }}
        .intel-recommend-kicker {{
            font-size: 0.76rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            opacity: 0.68;
        }}
        .intel-recommend-list {{
            margin-top: 0.85rem;
            display: grid;
            gap: 0.7rem;
        }}
        .intel-recommend-item {{
            padding: 0.85rem 0.9rem;
            border-radius: 20px;
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.08);
        }}
        .intel-recommend-card--insight-readable .intel-recommend-item {{
            padding: 0.9rem 1rem 0.92rem;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.09);
            box-shadow: inset 3px 0 0 rgba(214, 239, 250, 0.22);
        }}
        .intel-recommend-item-title {{
            font-size: 0.95rem;
            font-weight: 700;
        }}
        .intel-recommend-item-body {{
            margin-top: 0.35rem;
            font-size: 0.9rem;
            line-height: 1.62;
            opacity: 0.9;
        }}
        .intel-recommend-card--insight-readable .intel-recommend-item-title {{
            font-size: 1rem;
            color: #f8fbff;
        }}
        .intel-recommend-card--insight-readable .intel-recommend-item-body {{
            font-size: 0.93rem;
            line-height: 1.68;
            opacity: 0.94;
            max-width: 64ch;
        }}
        .stTabs [data-baseweb="tab-list"] {{
            gap: 0.55rem;
            padding: 0.42rem;
            border-radius: 24px;
            background: linear-gradient(180deg, rgba(255,255,255,0.14), rgba(255,255,255,0.05));
            border: 1px solid rgba(255,255,255,0.12);
            box-shadow: 0 12px 30px rgba(4, 15, 32, 0.12);
            width: fit-content;
        }}
        .stTabs [data-baseweb="tab"] {{
            height: auto;
            min-height: 2.95rem;
            padding: 0.7rem 1rem;
            border-radius: 999px;
            border: 1px solid transparent;
            background: transparent;
            color: rgba(238, 248, 255, 0.72);
            font-weight: 600;
            transition: background 0.25s ease, border-color 0.25s ease, transform 0.25s ease;
        }}
        .stTabs [data-baseweb="tab"]:hover {{
            background: rgba(255,255,255,0.08);
            color: #f4fbff;
            transform: translateY(-1px);
        }}
        .stTabs [aria-selected="true"] {{
            background: linear-gradient(135deg, rgba(214, 239, 250, 0.28), rgba(169, 215, 235, 0.16));
            border-color: rgba(255,255,255,0.18);
            color: #f7fbff;
            box-shadow: 0 10px 24px rgba(4, 15, 32, 0.12);
        }}
        .stTabs [data-baseweb="tab-highlight"] {{
            display: none;
        }}
        .stTabs [data-baseweb="tab-panel"] {{
            padding-top: 1.1rem;
        }}
        .intel-focus-grid {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.85rem;
            margin-bottom: 0.5rem;
        }}
        .intel-focus-grid--wear {{
            grid-template-columns: repeat(3, minmax(0, 1fr));
        }}
        .intel-focus-grid--trip-days {{
            grid-template-columns: repeat(3, minmax(0, 1fr));
        }}
        .intel-focus-grid--insight-readable {{
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 1rem;
            margin-bottom: 0.65rem;
        }}
        .intel-focus-card {{
            padding: 1rem 1.05rem;
            border-radius: 24px;
            background: linear-gradient(180deg, rgba(255,255,255,0.12), rgba(255,255,255,0.06));
            border: 1px solid rgba(255,255,255,0.1);
            box-shadow: 0 14px 34px rgba(4, 15, 32, 0.14);
            backdrop-filter: blur(14px);
        }}
        .intel-focus-grid--insight-readable .intel-focus-card {{
            padding: 1.1rem 1.14rem 1.08rem;
            background: linear-gradient(180deg, rgba(255,255,255,0.14), rgba(255,255,255,0.07));
            border: 1px solid rgba(255,255,255,0.12);
            box-shadow: 0 16px 38px rgba(4, 15, 32, 0.16);
        }}
        .intel-focus-card-header {{
            display: flex;
            align-items: flex-start;
            gap: 0.85rem;
        }}
        .intel-focus-icon {{
            width: 2.7rem;
            height: 2.7rem;
            border-radius: 18px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.1);
            font-size: 1.15rem;
            flex-shrink: 0;
        }}
        .intel-focus-card-kicker {{
            font-size: 0.72rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            opacity: 0.66;
        }}
        .intel-focus-card-title {{
            margin-top: 0.3rem;
            font-size: 1rem;
            font-weight: 700;
            line-height: 1.35;
        }}
        .intel-focus-card-body {{
            margin-top: 0.75rem;
            font-size: 0.92rem;
            line-height: 1.66;
            opacity: 0.9;
        }}
        .intel-focus-grid--insight-readable .intel-focus-card-kicker {{
            color: rgba(234, 246, 255, 0.72);
        }}
        .intel-focus-grid--insight-readable .intel-focus-card-title {{
            font-size: 1.06rem;
            line-height: 1.34;
            color: #f9fbff;
        }}
        .intel-focus-grid--insight-readable .intel-focus-card-body {{
            margin-top: 0.7rem;
            font-size: 0.95rem;
            line-height: 1.72;
            opacity: 0.96;
            max-width: 42ch;
        }}
        .intel-score-card-compact--insight-readable {{
            min-height: 148px;
            padding: 1rem 1.05rem 1.05rem;
            background: linear-gradient(180deg, rgba(255,255,255,0.13), rgba(255,255,255,0.07));
            border: 1px solid rgba(255,255,255,0.12);
            box-shadow: 0 16px 34px rgba(4, 15, 32, 0.15);
        }}
        .wear-visual-card {{
            border-radius: 26px;
            padding: 0.95rem 0.95rem 5.35rem 0.95rem;
            margin-bottom: 0;
            background: linear-gradient(180deg, rgba(255,255,255,0.16), rgba(255,255,255,0.07));
            border: 1px solid rgba(255,255,255,0.12);
            box-shadow: 0 16px 38px rgba(4, 15, 32, 0.15);
            backdrop-filter: blur(14px);
        }}
        .wear-visual-header {{
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 0.85rem;
        }}
        .wear-visual-kicker {{
            font-size: 0.72rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            opacity: 0.7;
        }}
        .wear-visual-title {{
            margin-top: 0.28rem;
            font-size: 1.08rem;
            font-weight: 700;
            line-height: 1.3;
        }}
        .wear-visual-icon {{
            width: 2.9rem;
            height: 2.9rem;
            border-radius: 18px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.1);
            font-size: 1.2rem;
            flex-shrink: 0;
        }}
        .wear-visual-image-shell {{
            margin-top: 0.9rem;
            border-radius: 22px;
            overflow: hidden;
            border: 1px solid rgba(255,255,255,0.1);
            background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(242, 246, 251, 0.96));
            min-height: 182px;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 0.85rem;
        }}
        .wear-visual-image {{
            display: block;
            width: 100%;
            height: 150px;
            object-fit: contain;
            border-radius: 18px;
        }}
        .wear-visual-style {{
            margin-top: 0.85rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.75rem;
            flex-wrap: wrap;
        }}
        .wear-visual-style-name {{
            font-size: 0.96rem;
            font-weight: 700;
        }}
        .wear-visual-count {{
            font-size: 0.76rem;
            opacity: 0.68;
        }}
        .wear-visual-badges {{
            margin-top: 0.65rem;
            display: flex;
            gap: 0.45rem;
            flex-wrap: wrap;
        }}
        .wear-visual-badge {{
            padding: 0.3rem 0.6rem;
            border-radius: 999px;
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.08);
            font-size: 0.73rem;
            opacity: 0.88;
        }}
        .wear-visual-body {{
            margin-top: 0.8rem;
            font-size: 0.9rem;
            line-height: 1.62;
            opacity: 0.84;
        }}
        .wear-visual-note {{
            margin-top: 0.55rem;
            font-size: 0.83rem;
            line-height: 1.55;
            opacity: 0.72;
        }}
        .wear-visual-link {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 100%;
            min-height: 2.8rem;
            margin-top: 0.65rem;
            border-radius: 18px;
            text-decoration: none;
            color: #eef8ff;
            font-weight: 600;
            border: 1px solid rgba(255,255,255,0.12);
            background: linear-gradient(180deg, rgba(255,255,255,0.12), rgba(255,255,255,0.06));
        }}
        .wear-visual-link:hover {{
            border-color: rgba(255,255,255,0.2);
            color: #ffffff;
        }}
        .wear-refresh-anchor + div[data-testid="stButton"] {{
            margin-top: 0;
            margin-bottom: -4.95rem;
            padding: 0 0.95rem 0.95rem 0.95rem;
            position: relative;
            top: -5.15rem;
            z-index: 4;
        }}
        .wear-refresh-anchor + div[data-testid="stButton"] button {{
            min-height: 2.9rem;
            border-radius: 18px;
            box-shadow: none;
        }}
        @media (max-width: 1500px) {{
            .skyline-nav-brand img {{
                width: min(100%, 286px);
            }}
            div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell .stButton button[kind="primary"],
            div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell .stButton button[kind="secondary"] {{
                min-height: 2.3rem;
                font-size: 1.08rem !important;
                padding-left: 0.1rem;
                padding-right: 0.1rem;
            }}
            div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell .stButton button p,
            div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell .stButton button span {{
                font-size: 1.08rem !important;
            }}
        }}
        @media (max-width: 1220px) {{
            div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell {{
                min-height: 8.95rem;
                padding-top: 1.52rem;
                padding-right: 0.42rem;
                padding-bottom: 1.12rem;
                padding-left: 0.08rem;
            }}
            div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell div[data-testid="stHorizontalBlock"] {{
                min-height: 4.48rem;
                gap: 0.02rem;
            }}
            div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell div[data-testid="column"],
            div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell div[data-testid="column"] > div {{
                min-height: 4.48rem;
            }}
            .skyline-nav-brand {{
                padding-left: 0.1rem;
            }}
            .skyline-nav-brand img {{
                width: min(100%, 248px);
            }}
            div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell .stButton button[kind="primary"],
            div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell .stButton button[kind="secondary"] {{
                min-height: 2.18rem;
                font-size: 0.94rem !important;
                padding-left: 0.06rem;
                padding-right: 0.06rem;
            }}
            div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell .stButton button p,
            div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell .stButton button span {{
                font-size: 0.94rem !important;
            }}
            div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell.is-condensed {{
                min-height: 6.6rem;
                padding-top: 0.8rem;
                padding-bottom: 0.66rem;
            }}
            div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell.is-condensed div[data-testid="stHorizontalBlock"],
            div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell.is-condensed div[data-testid="column"],
            div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell.is-condensed div[data-testid="column"] > div {{
                min-height: 3.28rem;
            }}
            div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell.is-condensed .skyline-nav-brand img {{
                width: min(100%, 234px);
            }}
        }}
        @media (max-width: 900px) {{
            .intel-alert-banner-grid,
            .intel-support-grid,
            .intel-focus-grid,
            .intel-focus-grid--insight-readable,
            .intel-focus-grid--wear,
            .intel-focus-grid--trip-days {{
                grid-template-columns: 1fr;
            }}
            div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell {{
                min-height: 8.2rem;
                padding: 1.26rem 0.55rem 1rem;
            }}
            div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell::before,
            div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell::after {{
                inset: 0 0 0.08rem 0;
                border-radius: 0 0 26px 26px;
            }}
            div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell div[data-testid="stHorizontalBlock"] {{
                min-height: 4.22rem;
                padding-top: 0.22rem;
            }}
            .skyline-nav-brand {{
                min-height: 3.2rem;
                padding-left: 0.14rem;
                margin-top: -0.12rem;
            }}
            .skyline-nav-brand img {{
                width: min(100%, 214px);
                transform: translateY(-0.04rem);
            }}
            div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell .stButton button[kind="primary"],
            div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell .stButton button[kind="secondary"] {{
                font-size: 0.84rem !important;
                font-weight: 600 !important;
                padding-left: 0.02rem;
                padding-right: 0.02rem;
            }}
            div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell .stButton button p,
            div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell .stButton button span {{
                font-size: 0.84rem !important;
                font-weight: 600 !important;
            }}
            div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell.is-condensed {{
                min-height: 6.2rem;
                padding-top: 0.72rem;
                padding-bottom: 0.64rem;
            }}
            div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell.is-condensed div[data-testid="stHorizontalBlock"],
            div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell.is-condensed div[data-testid="column"],
            div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell.is-condensed div[data-testid="column"] > div {{
                min-height: 3.12rem;
            }}
            div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell.is-condensed .skyline-nav-brand img {{
                width: min(100%, 236px);
            }}
            div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell.is-condensed .stButton button[kind="primary"],
            div[data-testid="stVerticalBlock"].skyline-persistent-nav-shell.is-condensed .stButton button[kind="secondary"] {{
                min-height: 2.06rem;
            }}
            .block-container {{
                padding-top: 10.2rem;
            }}
            .wear-visual-image-shell {{
                min-height: 168px;
            }}
            .wear-visual-image {{
                height: 136px;
            }}
            .wear-refresh-anchor + div[data-testid="stButton"] {{
                margin-bottom: -4.45rem;
                top: -4.75rem;
            }}
            .stTabs [data-baseweb="tab-list"] {{
                width: 100%;
                overflow-x: auto;
            }}
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_section_transition(active_section, sections):
    components.html(
        f"""
        <script>
          const hostWindow = window.parent;
          const hostDoc = hostWindow.document;
          const currentSection = {json.dumps(active_section)};
          const sectionLabels = {json.dumps(list(sections))};
          const portalId = "skyline-section-transition-root";
          const styleId = "skyline-section-transition-style";
          const storageKey = "skyline-active-content-section";
          const initializedKey = "skyline-content-transition-ready";
          const pendingKey = "skyline-pending-content-section";
          const durationMs = 460;
          const exitMs = 180;

          const setFrameHeight = () => {{
            hostWindow.postMessage({{ isStreamlitMessage: true, type: "streamlit:setFrameHeight", height: 0 }}, "*");
          }};

          const readJson = (value) => {{
            if (!value) {{
              return null;
            }}
            try {{
              return JSON.parse(value);
            }} catch (error) {{
              return null;
            }}
          }};

          const ensureStyle = () => {{
            if (hostDoc.getElementById(styleId)) {{
              return;
            }}
            const style = hostDoc.createElement("style");
            style.id = styleId;
            style.textContent = `
              #${{portalId}} {{
                position: fixed;
                inset: 0;
                pointer-events: none;
                z-index: 999999;
              }}
              #${{portalId}} .skyline-section-transition {{
                position: absolute;
                inset: 0;
                display: flex;
                align-items: center;
                justify-content: center;
                padding: 1.5rem;
                opacity: 0;
                visibility: hidden;
                transition: opacity 180ms ease, visibility 180ms ease;
              }}
              #${{portalId}}.is-visible .skyline-section-transition {{
                opacity: 1;
                visibility: visible;
              }}
              #${{portalId}} .skyline-section-transition-backdrop {{
                position: absolute;
                inset: 0;
                background:
                  radial-gradient(circle at top, rgba(224, 242, 255, 0.16), transparent 44%),
                  linear-gradient(180deg, rgba(5, 14, 28, 0.02), rgba(5, 14, 28, 0.26));
                backdrop-filter: blur(9px) saturate(1.08);
              }}
              #${{portalId}} .skyline-section-transition-sheen,
              #${{portalId}} .skyline-section-transition-sheen-two {{
                position: absolute;
                left: 50%;
                width: min(68vw, 860px);
                height: 22vh;
                border-radius: 999px;
                transform: translate(-50%, -32px);
                filter: blur(30px);
                opacity: 0;
                transition: transform 420ms cubic-bezier(0.22, 1, 0.36, 1), opacity 280ms ease;
              }}
              #${{portalId}} .skyline-section-transition-sheen {{
                top: 9vh;
                background: linear-gradient(180deg, rgba(215, 240, 255, 0.34), rgba(215, 240, 255, 0.02));
              }}
              #${{portalId}} .skyline-section-transition-sheen-two {{
                top: 16vh;
                width: min(52vw, 620px);
                height: 16vh;
                background: linear-gradient(180deg, rgba(169, 215, 235, 0.24), rgba(169, 215, 235, 0.02));
              }}
              #${{portalId}}.is-visible .skyline-section-transition-sheen,
              #${{portalId}}.is-visible .skyline-section-transition-sheen-two {{
                transform: translate(-50%, 0);
                opacity: 1;
              }}
              #${{portalId}} .skyline-section-transition-card {{
                position: relative;
                width: min(420px, calc(100vw - 2rem));
                padding: 1.15rem 1.2rem 1.05rem;
                border-radius: 28px;
                overflow: hidden;
                background: linear-gradient(180deg, rgba(255, 255, 255, 0.22), rgba(255, 255, 255, 0.08));
                border: 1px solid rgba(255, 255, 255, 0.18);
                box-shadow: 0 26px 60px rgba(4, 15, 32, 0.24);
                backdrop-filter: blur(24px);
                transform: translateY(-22px) scale(0.98);
                opacity: 0;
                transition: transform 360ms cubic-bezier(0.22, 1, 0.36, 1), opacity 220ms ease;
              }}
              #${{portalId}}.is-visible .skyline-section-transition-card {{
                transform: translateY(0) scale(1);
                opacity: 1;
              }}
              #${{portalId}} .skyline-section-transition-card::before {{
                content: "";
                position: absolute;
                inset: 0;
                background:
                  linear-gradient(135deg, rgba(255,255,255,0.18), transparent 46%),
                  radial-gradient(circle at top right, rgba(224, 242, 255, 0.24), transparent 38%);
                pointer-events: none;
              }}
              #${{portalId}} .skyline-section-transition-meta {{
                position: relative;
                display: flex;
                align-items: center;
                gap: 0.78rem;
              }}
              #${{portalId}} .skyline-section-transition-pulse {{
                width: 0.9rem;
                height: 0.9rem;
                border-radius: 999px;
                background: rgba(214, 239, 250, 0.94);
                box-shadow: 0 0 0 0 rgba(214, 239, 250, 0.42);
                animation: skyline-section-pulse 1.05s ease infinite;
              }}
              #${{portalId}} .skyline-section-transition-kicker {{
                font-size: 0.72rem;
                font-weight: 700;
                letter-spacing: 0.14em;
                text-transform: uppercase;
                color: rgba(238, 248, 255, 0.74);
              }}
              #${{portalId}} .skyline-section-transition-title {{
                position: relative;
                margin-top: 0.72rem;
                font-size: clamp(1.45rem, 2.2vw, 1.9rem);
                font-weight: 700;
                color: #f7fbff;
              }}
              #${{portalId}} .skyline-section-transition-copy {{
                position: relative;
                margin-top: 0.28rem;
                font-size: 0.92rem;
                line-height: 1.45;
                color: rgba(238, 248, 255, 0.78);
              }}
              #${{portalId}} .skyline-section-transition-track {{
                position: relative;
                margin-top: 0.95rem;
                height: 0.34rem;
                border-radius: 999px;
                overflow: hidden;
                background: rgba(255,255,255,0.12);
              }}
              #${{portalId}} .skyline-section-transition-bar {{
                width: 100%;
                height: 100%;
                transform-origin: left center;
                background: linear-gradient(90deg, rgba(214, 239, 250, 0.98), rgba(169, 215, 235, 0.58));
                animation: skyline-section-progress ${{durationMs}}ms linear forwards;
              }}
              @keyframes skyline-section-pulse {{
                0% {{ box-shadow: 0 0 0 0 rgba(214, 239, 250, 0.42); }}
                70% {{ box-shadow: 0 0 0 14px rgba(214, 239, 250, 0); }}
                100% {{ box-shadow: 0 0 0 0 rgba(214, 239, 250, 0); }}
              }}
              @keyframes skyline-section-progress {{
                from {{ transform: scaleX(0.06); }}
                to {{ transform: scaleX(1); }}
              }}
            `;
            hostDoc.head.appendChild(style);
          }};

          const ensurePortal = () => {{
            let portal = hostDoc.getElementById(portalId);
            if (!portal) {{
              portal = hostDoc.createElement("div");
              portal.id = portalId;
              hostDoc.body.appendChild(portal);
            }}
            return portal;
          }};

          const showTransition = (sectionLabel, holdMs) => {{
            const portal = ensurePortal();
            if (hostWindow.__skylineSectionTransitionTimer) {{
              hostWindow.clearTimeout(hostWindow.__skylineSectionTransitionTimer);
            }}
            if (hostWindow.__skylineSectionTransitionExitTimer) {{
              hostWindow.clearTimeout(hostWindow.__skylineSectionTransitionExitTimer);
            }}
            portal.innerHTML = `
              <div class="skyline-section-transition" aria-hidden="true">
                <div class="skyline-section-transition-backdrop"></div>
                <div class="skyline-section-transition-sheen"></div>
                <div class="skyline-section-transition-sheen-two"></div>
                <div class="skyline-section-transition-card">
                  <div class="skyline-section-transition-meta">
                    <div class="skyline-section-transition-pulse"></div>
                    <div class="skyline-section-transition-kicker">Switching Section</div>
                  </div>
                  <div class="skyline-section-transition-title">${{sectionLabel}}</div>
                  <div class="skyline-section-transition-copy">Preparing the next weather view with the same live city context.</div>
                  <div class="skyline-section-transition-track">
                    <div class="skyline-section-transition-bar"></div>
                  </div>
                </div>
              </div>
            `;
            hostWindow.requestAnimationFrame(() => {{
              portal.classList.add("is-visible");
            }});
            hostWindow.__skylineSectionTransitionTimer = hostWindow.setTimeout(() => {{
              portal.classList.remove("is-visible");
              hostWindow.__skylineSectionTransitionExitTimer = hostWindow.setTimeout(() => {{
                if (!portal.classList.contains("is-visible")) {{
                  portal.innerHTML = "";
                }}
              }}, exitMs);
            }}, Math.max(220, holdMs || durationMs));
          }};

          const bindSectionButtons = () => {{
            Array.from(hostDoc.querySelectorAll("button")).forEach((button) => {{
              const label = (button.textContent || "").trim();
              if (!sectionLabels.includes(label)) {{
                return;
              }}
              if (button.dataset.skylineSectionTransitionBound === "true") {{
                return;
              }}
              button.dataset.skylineSectionTransitionBound = "true";
              const trigger = () => {{
                if (label === currentSection) {{
                  return;
                }}
                hostWindow.sessionStorage.setItem(
                  pendingKey,
                  JSON.stringify({{
                    section: label,
                    holdUntil: Date.now() + durationMs,
                  }})
                );
                showTransition(label, durationMs);
              }};
              button.addEventListener("pointerdown", trigger, {{ passive: true }});
              button.addEventListener("keydown", (event) => {{
                if (event.key === "Enter" || event.key === " ") {{
                  trigger();
                }}
              }});
            }});
          }};

          ensureStyle();
          ensurePortal();
          bindSectionButtons();

          const previousSection = hostWindow.sessionStorage.getItem(storageKey);
          const isInitialized = hostWindow.sessionStorage.getItem(initializedKey) === "true";
          const pendingSection = readJson(hostWindow.sessionStorage.getItem(pendingKey));
          if (pendingSection && pendingSection.section === currentSection) {{
            hostWindow.sessionStorage.removeItem(pendingKey);
            showTransition(currentSection, Math.max(220, pendingSection.holdUntil - Date.now()));
          }} else if (isInitialized && previousSection && previousSection !== currentSection) {{
            showTransition(currentSection, durationMs);
          }}
          hostWindow.sessionStorage.setItem(storageKey, currentSection);
          hostWindow.sessionStorage.setItem(initializedKey, "true");
          setFrameHeight();
        </script>
        """,
        height=0,
    )


def render_persistent_nav_bridge():
    components.html(
        """
        <script>
          const hostWindow = window.parent;
          const hostDoc = hostWindow.document;
          const bridgeFrame = window.frameElement;
          const bridgeKey = "__skylinePersistentNavBridge";
          const frameKey = "__skylinePersistentNavScrollFrame";
          const lastYKey = "__skylinePersistentNavLastY";
          const condensedKey = "__skylinePersistentNavIsCondensed";
          const readyAtKey = "__skylinePersistentNavReadyAt";
          const boundTargetsKey = "__skylinePersistentNavBoundTargets";
          const scrollHandlerKey = "__skylinePersistentNavScrollHandler";
          const resizeHandlerKey = "__skylinePersistentNavResizeHandler";

          const findShell = (marker) => {
            let node = marker;
            while (node && node !== hostDoc.body) {
              if (node.matches && node.matches('div[data-testid="stVerticalBlock"]')) {
                return node;
              }
              node = node.parentElement;
            }
            return null;
          };

          const readTargetScrollTop = (target) => {
            if (!target) {
              return 0;
            }
            if (target === hostWindow) {
              return hostWindow.scrollY || 0;
            }
            if (target === hostDoc) {
              return Math.max(hostDoc.documentElement?.scrollTop || 0, hostDoc.body?.scrollTop || 0);
            }
            return target.scrollTop || 0;
          };

          const resolveScrollTargets = () => {
            const targets = [];
            const push = (target) => {
              if (target && !targets.includes(target)) {
                targets.push(target);
              }
            };

            push(hostWindow);
            push(hostDoc);
            push(hostDoc.scrollingElement);
            push(hostDoc.querySelector('section[data-testid="stMain"]'));
            push(hostDoc.querySelector('div[data-testid="stAppViewContainer"]'));
            push(hostDoc.querySelector('div[data-testid="stApp"]'));
            push(hostDoc.documentElement);
            push(hostDoc.body);
            return targets;
          };

          const getScrollTop = () =>
            resolveScrollTargets().reduce((maxTop, target) => Math.max(maxTop, readTargetScrollTop(target)), 0);

          const syncCondensedState = () => {
            const isCondensed = Boolean(hostWindow[condensedKey]);
            hostDoc.querySelectorAll(".skyline-persistent-nav-shell").forEach((shell) => {
              shell.classList.toggle("is-condensed", isCondensed);
            });
          };

          const applyPersistentNav = () => {
            hostDoc.querySelectorAll(".skyline-persistent-nav-shell").forEach((shell) => {
              if (!shell.querySelector(".skyline-persistent-nav-anchor")) {
                shell.classList.remove("skyline-persistent-nav-shell");
                shell.classList.remove("is-condensed");
              }
            });

            hostDoc.querySelectorAll(".skyline-persistent-nav-anchor").forEach((marker) => {
              const shell = findShell(marker);
              if (!shell) {
                return;
              }
              shell.classList.add("skyline-persistent-nav-shell");
              const markerBlock = marker.closest('div[data-testid="stElementContainer"]');
              if (markerBlock) {
                markerBlock.classList.add("skyline-persistent-nav-marker-block");
              }
            });
            syncCondensedState();
          };

          const updateCondensedState = () => {
            const currentY = getScrollTop();
            const lastY = typeof hostWindow[lastYKey] === "number" ? hostWindow[lastYKey] : currentY;
            const readyAt = typeof hostWindow[readyAtKey] === "number" ? hostWindow[readyAtKey] : 0;

            if (Date.now() < readyAt) {
              hostWindow[lastYKey] = currentY;
              hostWindow[condensedKey] = false;
              syncCondensedState();
              return;
            }

            if (currentY <= 4) {
              hostWindow[condensedKey] = false;
            } else if (currentY > lastY + 1) {
              hostWindow[condensedKey] = true;
            } else if (currentY < lastY - 1) {
              hostWindow[condensedKey] = false;
            }

            hostWindow[lastYKey] = currentY;
            syncCondensedState();
          };

          const queueCondensedUpdate = () => {
            if (hostWindow[frameKey]) {
              return;
            }
            hostWindow[frameKey] = hostWindow.requestAnimationFrame(() => {
              hostWindow[frameKey] = null;
              updateCondensedState();
            });
          };

          const ensureScrollBindings = () => {
            const previousTargets = Array.isArray(hostWindow[boundTargetsKey]) ? hostWindow[boundTargetsKey] : [];
            const scrollHandler = hostWindow[scrollHandlerKey] || queueCondensedUpdate;
            const resizeHandler = hostWindow[resizeHandlerKey] || queueCondensedUpdate;

            previousTargets.forEach((target) => {
              if (target && target.removeEventListener) {
                try {
                  target.removeEventListener("scroll", scrollHandler);
                } catch (error) {
                }
              }
            });

            if (hostWindow.removeEventListener) {
              hostWindow.removeEventListener("resize", resizeHandler);
            }

            const nextTargets = resolveScrollTargets();
            nextTargets.forEach((target) => {
              if (target && target.addEventListener) {
                target.addEventListener("scroll", scrollHandler, { passive: true });
              }
            });

            hostWindow.addEventListener("resize", resizeHandler, { passive: true });
            hostWindow[boundTargetsKey] = nextTargets;
            hostWindow[scrollHandlerKey] = scrollHandler;
            hostWindow[resizeHandlerKey] = resizeHandler;
          };

          const collapseBridgeFrame = () => {
            const frameBlock = bridgeFrame && bridgeFrame.closest
              ? bridgeFrame.closest('div[data-testid="stElementContainer"]')
              : null;
            if (!frameBlock) {
              return;
            }
            frameBlock.classList.add("skyline-persistent-nav-bridge-block");
          };

          if (!hostWindow[bridgeKey]) {
            hostWindow[bridgeKey] = true;
            hostWindow[lastYKey] = getScrollTop();
            hostWindow[condensedKey] = false;
            hostWindow[readyAtKey] = Date.now() + 420;
            let attempts = 0;
            const refresh = () => {
              applyPersistentNav();
              attempts += 1;
              if (attempts < 24) {
                hostWindow.requestAnimationFrame(refresh);
              }
            };
            refresh();

            if (hostWindow.ResizeObserver) {
              const observer = new hostWindow.ResizeObserver(() => applyPersistentNav());
              observer.observe(hostDoc.body);
              hostWindow.__skylinePersistentNavObserver = observer;
            }
            collapseBridgeFrame();
            ensureScrollBindings();
          } else {
            collapseBridgeFrame();
            hostWindow[lastYKey] = getScrollTop();
            applyPersistentNav();
            ensureScrollBindings();
          }

          syncCondensedState();
          hostWindow.postMessage({ isStreamlitMessage: true, type: "streamlit:setFrameHeight", height: 0 }, "*");
        </script>
        """,
        height=0,
    )


def render_topbar(weather, city_name, temp_symbol, use_fahrenheit=False):
    today = weather["forecast"][0] if weather and weather.get("forecast") else None

    if weather:
        current_temp = round(weather["current"]["temperature"], 1)
        high_temp = today["max"] if today else "--"
        low_temp = today["min"] if today else "--"
        time_info = get_weather_local_time_display(weather)
        time_parts = [time_info.get("local_date"), time_info.get("local_time"), time_info.get("timezone_abbr")]
        time_text = " | ".join(part for part in time_parts if part)

        if use_fahrenheit:
            current_temp = round((current_temp * 9 / 5) + 32, 1)
            if today:
                high_temp = round((today["max"] * 9 / 5) + 32, 1)
                low_temp = round((today["min"] * 9 / 5) + 32, 1)

        st.markdown(
            f"""
            <div class="topbar glass">
                <div class="summary-city">{city_name}</div>
                <div class="summary-time">Local time {time_text}</div>
                <div class="summary-temp">{get_condition_icon(weather['current']['condition'])} {current_temp}{temp_symbol}</div>
                <div class="summary-condition">{weather['current']['condition']}</div>
                <div class="summary-range">H: {high_temp}{temp_symbol} | L: {low_temp}{temp_symbol}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    else:
        st.markdown(
            """
            <div class="topbar glass">
                <div class="summary-city">Weather Loading</div>
                <div class="summary-time">Local time unavailable</div>
                <div class="summary-temp">--</div>
                <div class="summary-condition">Waiting for weather data</div>
                <div class="summary-range">H: -- | L: --</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def render_live_weather_map(
    weather,
    temp_symbol,
    speed_symbol,
    use_fahrenheit=False,
    show_controls=True,
    expanded=False,
    preferred_layer="Clouds",
):
    location = (weather or {}).get("location") or {}
    current = (weather or {}).get("current") or {}
    forecast = (weather or {}).get("forecast") or []
    today = forecast[0] if forecast else {}

    latitude = location.get("latitude")
    longitude = location.get("longitude")
    if latitude is None or longitude is None:
        return

    current_temp = current.get("temperature", 0)
    feels_like = current.get("feels_like", 0)
    wind_speed = current.get("wind", 0)
    day_high = today.get("max", 0)
    day_low = today.get("min", 0)

    if use_fahrenheit:
        current_temp = round((current_temp * 9 / 5) + 32, 1)
        feels_like = round((feels_like * 9 / 5) + 32, 1)
        day_high = round((day_high * 9 / 5) + 32, 1)
        day_low = round((day_low * 9 / 5) + 32, 1)

    if speed_symbol == "mph":
        wind_speed = round(wind_speed * 0.621371, 1)

    title = weather.get("resolved_city", "Selected location")
    subtitle = f"{location.get('timezone') or 'Local time zone'} | H: {day_high}{temp_symbol} | L: {day_low}{temp_symbol}"
    layer_config = {
        "Clouds": {
            "overlay": "clouds",
            "pill": "Clouds Layer",
        },
        "Temperature": {
            "overlay": "temp",
            "pill": "Temperature Layer",
        },
        "Rain": {
            "overlay": "rain",
            "pill": "Rain Layer",
        },
        "Wind": {
            "overlay": "wind",
            "pill": "Wind Layer",
        },
        "Pressure": {
            "overlay": "pressure",
            "pill": "Pressure Layer",
        },
        "Radar": {
            "overlay": "radar",
            "pill": "Radar Layer",
        },
        "Satellite": {
            "overlay": "satellite",
            "pill": "Satellite Layer",
        },
    }
    layer_buttons_html = ""
    active_layer = preferred_layer if preferred_layer in layer_config else "Clouds"
    if show_controls:
        layer_buttons_html = "".join(
            f'<button type="button" class="weather-map-chip{" is-active" if name == active_layer else ""}" data-layer="{escape(name)}">{escape(name)}</button>'
            for name in layer_config
        )

    layer_json = json.dumps(layer_config)
    card_padding = "1.25rem 1.25rem 1.1rem" if expanded else "1rem 1rem 0.95rem"
    title_size = "1.65rem" if expanded else "1.28rem"
    frame_height = 640 if expanded else 540
    embed_height = frame_height + 42
    component_height = 880 if expanded else 720
    map_shadow = "0 16px 42px rgba(4,15,32,0.18)" if expanded else "none"
    layer_row_html = (
        f"""
          <div class="weather-map-layer-row">
            {layer_buttons_html}
          </div>
        """
        if show_controls
        else ""
    )
    coordinate_html = ""
    if expanded:
        coordinate_html = (
            f'<div class="weather-map-pill">Lat {latitude}</div>'
            f'<div class="weather-map-pill">Lon {longitude}</div>'
        )

    components.html(
        f"""
        <div class="weather-map-card" id="weather-map-card">
          <div class="weather-map-header">
            <div class="weather-map-copy">
              <div class="weather-map-kicker">Live Weather Map</div>
              <div class="weather-map-title">{escape(title)}</div>
              <div class="weather-map-subtitle">{escape(subtitle)}</div>
            </div>
          </div>
          {layer_row_html}
          <div class="weather-map-stage">
            <div class="weather-map-frame-shell">
              <iframe id="weather-map-frame" class="weather-map-embed" loading="lazy" referrerpolicy="no-referrer-when-downgrade"></iframe>
            </div>
          </div>
          <div class="weather-map-meta">
            <div class="weather-map-pill">Current {current_temp}{temp_symbol}</div>
            <div class="weather-map-pill">Feels {feels_like}{temp_symbol}</div>
            <div class="weather-map-pill">Wind {wind_speed} {speed_symbol}</div>
            <div class="weather-map-pill" id="weather-map-layer-pill">{escape(layer_config[active_layer]["pill"])}</div>
            {coordinate_html}
          </div>
        </div>
        <style>
          body {{
            margin: 0;
            background: transparent;
            font-family: "Segoe UI", sans-serif;
            color: #eef8ff;
          }}
          .weather-map-card {{
            border-radius: 32px;
            padding: {card_padding};
            background: linear-gradient(180deg, rgba(255,255,255,0.16), rgba(255,255,255,0.08));
            border: 1px solid rgba(255,255,255,0.14);
            box-shadow: {map_shadow};
            backdrop-filter: blur(16px);
          }}
          .weather-map-kicker {{
            font-size: 0.82rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            opacity: 0.72;
          }}
          .weather-map-header {{
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 1rem;
          }}
          .weather-map-copy {{
            min-width: 0;
            flex: 1;
          }}
          .weather-map-title {{
            margin-top: 0.35rem;
            font-size: {title_size};
            font-weight: 700;
          }}
          .weather-map-subtitle {{
            margin-top: 0.35rem;
            font-size: 0.92rem;
            opacity: 0.78;
          }}
          .weather-map-layer-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.55rem;
            margin-top: 1rem;
          }}
          .weather-map-chip {{
            border-radius: 999px;
            padding: 0.52rem 0.92rem;
            border: 1px solid rgba(255,255,255,0.1);
            background: rgba(255,255,255,0.06);
            color: #eef8ff;
            font-size: 0.86rem;
            cursor: pointer;
            transition: transform 0.28s ease, background 0.28s ease, border-color 0.28s ease;
          }}
          .weather-map-chip:hover,
          .weather-map-chip.is-active {{
            transform: translateY(-1px);
            background: rgba(255,255,255,0.12);
            border-color: rgba(255,255,255,0.18);
          }}
          .weather-map-stage {{
            margin-top: 0.95rem;
            border-radius: 28px;
            overflow: hidden;
          }}
          .weather-map-frame-shell {{
            overflow: hidden;
            border-radius: 28px;
            height: {frame_height}px;
            background: rgba(8, 20, 34, 0.45);
          }}
          .weather-map-embed {{
            width: 100%;
            height: {embed_height}px;
            border: 0;
            margin-bottom: -42px;
            background: rgba(8, 20, 34, 0.45);
          }}
          .weather-map-meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.55rem;
            margin-top: 0.8rem;
          }}
          .weather-map-pill {{
            border-radius: 999px;
            padding: 0.4rem 0.72rem;
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.1);
            font-size: 0.85rem;
          }}
          @media (max-width: 980px) {{
            .weather-map-header {{
              align-items: stretch;
            }}
            .weather-map-frame-shell {{
              height: {max(320, frame_height - 90)}px;
            }}
            .weather-map-embed {{
              height: {max(362, embed_height - 90)}px;
              margin-bottom: -36px;
            }}
          }}
          @media (max-width: 640px) {{
            .weather-map-card {{
              padding: 1rem 1rem 0.95rem;
            }}
            .weather-map-frame-shell {{
              height: {max(300, frame_height - 120)}px;
            }}
            .weather-map-embed {{
              height: {max(342, embed_height - 120)}px;
              margin-bottom: -30px;
            }}
          }}
        </style>
        <script>
          const mapFrame = document.getElementById("weather-map-frame");
          const layerPill = document.getElementById("weather-map-layer-pill");
          const layerButtons = Array.from(document.querySelectorAll(".weather-map-chip"));
          const layerConfig = {layer_json};
          const latitude = {latitude};
          const longitude = {longitude};

          const resizeFrame = () => {{
            const height = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight, {component_height});
            window.parent.postMessage({{ isStreamlitMessage: true, type: "streamlit:setFrameHeight", height }}, "*");
          }};

          const buildUrl = (overlay) =>
            `https://embed.windy.com/embed2.html?lat=${{latitude}}&lon=${{longitude}}&detailLat=${{latitude}}&detailLon=${{longitude}}&width=1400&height=560&zoom=5&level=surface&overlay=${{overlay}}&product=ecmwf&menu=&message=&marker=true&calendar=now&pressure=false&type=map&location=coordinates&detail=false&metricWind=default&metricTemp=default&radarRange=-1`;

          const setLayer = (name) => {{
            const config = layerConfig[name] || layerConfig.Clouds;
            mapFrame.src = buildUrl(config.overlay);
            layerPill.textContent = config.pill;
            layerButtons.forEach((button) => {{
              button.classList.toggle("is-active", button.dataset.layer === name);
            }});
          }};

          layerButtons.forEach((button) => {{
            button.addEventListener("click", () => {{
              setLayer(button.dataset.layer);
            }});
          }});

          setLayer({json.dumps(active_layer)});
          resizeFrame();
        </script>
        """,
        height=component_height,
    )


def render_weather_intelligence_panel(payload):
    hero_stats_html = "".join(
        dedent(
            f"""
            <div class="intel-hero-pill">
                <div class="intel-hero-pill-label">{escape(str(stat["label"]))}</div>
                <div class="intel-hero-pill-value">{escape(str(stat["value"]))}</div>
            </div>
            """
        ).strip()
        for stat in payload.get("hero_stats", [])
    )
    score_cards_html = "".join(
        dedent(
            f"""
            <div class="intel-score-card intel-score-card--{escape(str(card["key"]))}">
                <div class="intel-score-label">{escape(str(card["label"]))}</div>
                <div class="intel-score-value">{escape(str(card["value"]))}<span>/10</span></div>
                <div class="intel-score-summary">{escape(str(card["summary"]))}</div>
            </div>
            """
        ).strip()
        for card in payload.get("scores", [])
    )
    alert_cards_html = "".join(
        dedent(
            f"""
            <div class="intel-alert-card intel-alert-card--{escape(str(alert["tone"]))}">
                <div class="intel-alert-icon">{escape(str(alert["icon"]))}</div>
                <div class="intel-alert-copy">
                    <div class="intel-alert-title">{escape(str(alert["title"]))}</div>
                    <div class="intel-alert-body">{escape(str(alert["body"]))}</div>
                </div>
            </div>
            """
        ).strip()
        for alert in payload.get("alerts", [])
    )
    panel_specs = [
        ("insights", "Smart Insights", payload.get("insights", [])),
        ("activities", "Activities", payload.get("activities", [])),
        ("clothing", "Clothing", payload.get("clothing", [])),
    ]
    tab_buttons_html = "".join(
        f'<button class="intel-tab{" is-active" if index == 0 else ""}" type="button" data-panel="{escape(name)}">{escape(label)}</button>'
        for index, (name, label, _) in enumerate(panel_specs)
    )
    panel_markup = []
    for index, (name, _, cards) in enumerate(panel_specs):
        cards_html = "".join(
            dedent(
                f"""
                <div class="intel-panel-card">
                    <div class="intel-panel-eyebrow">{escape(str(card["eyebrow"]))}</div>
                    <div class="intel-panel-title">{escape(str(card["title"]))}</div>
                    <div class="intel-panel-body">{escape(str(card["body"]))}</div>
                </div>
                """
            ).strip()
            for card in cards
        )
        panel_markup.append(
            dedent(
                f"""
                <div class="intel-panel{" is-active" if index == 0 else ""}" data-panel="{escape(name)}">
                    {cards_html}
                </div>
                """
            ).strip()
        )

    components.html(
        f"""
        <div class="intel-shell" id="intel-shell">
          <div class="intel-hero">
            <div class="intel-hero-copy">
              <div class="intel-kicker">Version 2 Intelligence</div>
              <div class="intel-title">{escape(get_condition_icon(payload.get("condition")))} Decision-ready weather for {escape(str(payload.get("city", "Selected location")))}</div>
              <div class="intel-subtitle">Short alerts, practical guidance, and fast recommendations built from the current weather snapshot.</div>
            </div>
            <div class="intel-hero-stats">
              {hero_stats_html}
            </div>
          </div>

          <div class="intel-score-grid">
            {score_cards_html}
          </div>

          <div class="intel-alert-grid">
            {alert_cards_html}
          </div>

          <div class="intel-tab-row">
            {tab_buttons_html}
          </div>

          <div class="intel-panels">
            {''.join(panel_markup)}
          </div>
        </div>

        <style>
          html,
          body {{
            margin: 0;
            background: transparent;
            font-family: "Segoe UI", sans-serif;
            color: #eef8ff;
            border-radius: 32px;
            overflow: hidden;
          }}
          .intel-shell {{
            border-radius: 32px;
            overflow: hidden;
            padding: 1.2rem 1.2rem 1.1rem;
            background: linear-gradient(180deg, rgba(255,255,255,0.16), rgba(255,255,255,0.08));
            border: 1px solid rgba(255,255,255,0.14);
            box-shadow: 0 18px 44px rgba(4, 15, 32, 0.18);
            backdrop-filter: blur(16px);
          }}
          .intel-hero {{
            display: grid;
            grid-template-columns: minmax(0, 1.3fr) minmax(280px, 1fr);
            gap: 1rem;
            align-items: start;
          }}
          .intel-kicker {{
            font-size: 0.78rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            opacity: 0.72;
          }}
          .intel-title {{
            margin-top: 0.35rem;
            font-size: clamp(1.45rem, 2.4vw, 2rem);
            font-weight: 800;
            line-height: 1.1;
          }}
          .intel-subtitle {{
            margin-top: 0.55rem;
            font-size: 0.94rem;
            line-height: 1.6;
            opacity: 0.82;
            max-width: 56ch;
          }}
          .intel-hero-stats {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.7rem;
          }}
          .intel-hero-pill,
          .intel-score-card,
          .intel-alert-card,
          .intel-panel-card {{
            border-radius: 24px;
            background: rgba(255,255,255,0.07);
            border: 1px solid rgba(255,255,255,0.08);
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
          }}
          .intel-hero-pill {{
            padding: 0.9rem 0.95rem;
            min-height: 90px;
          }}
          .intel-hero-pill-label {{
            font-size: 0.75rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            opacity: 0.68;
          }}
          .intel-hero-pill-value {{
            margin-top: 0.38rem;
            font-size: 1.08rem;
            font-weight: 700;
          }}
          .intel-score-grid {{
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.8rem;
            margin-top: 1rem;
          }}
          .intel-score-card {{
            padding: 1rem 1rem 1.05rem;
            min-height: 170px;
            animation: fadeUp 0.45s ease both;
          }}
          .intel-score-label {{
            font-size: 0.78rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            opacity: 0.7;
          }}
          .intel-score-value {{
            margin-top: 0.42rem;
            font-size: 2.3rem;
            line-height: 1;
            font-weight: 800;
          }}
          .intel-score-value span {{
            margin-left: 0.18rem;
            font-size: 0.95rem;
            opacity: 0.72;
            font-weight: 600;
          }}
          .intel-score-summary {{
            margin-top: 0.7rem;
            font-size: 0.92rem;
            line-height: 1.55;
            opacity: 0.85;
          }}
          .intel-score-card--comfort .intel-score-value {{
            color: #9cf7d4;
          }}
          .intel-score-card--outdoor .intel-score-value {{
            color: #ffe698;
          }}
          .intel-score-card--travel .intel-score-value {{
            color: #9dd7ff;
          }}
          .intel-alert-grid {{
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.8rem;
            margin-top: 0.95rem;
          }}
          .intel-alert-card {{
            display: flex;
            gap: 0.8rem;
            align-items: flex-start;
            padding: 0.95rem 1rem;
            min-height: 122px;
            animation: fadeUp 0.55s ease both;
          }}
          .intel-alert-icon {{
            flex-shrink: 0;
            width: 2.65rem;
            height: 2.65rem;
            border-radius: 999px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            font-size: 1.15rem;
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.1);
          }}
          .intel-alert-title {{
            font-size: 1rem;
            font-weight: 700;
          }}
          .intel-alert-body {{
            margin-top: 0.32rem;
            font-size: 0.9rem;
            line-height: 1.55;
            opacity: 0.84;
          }}
          .intel-alert-card--danger {{
            border-color: rgba(255, 125, 125, 0.24);
            background: linear-gradient(180deg, rgba(255, 115, 115, 0.12), rgba(255,255,255,0.06));
          }}
          .intel-alert-card--warning {{
            border-color: rgba(255, 213, 117, 0.24);
            background: linear-gradient(180deg, rgba(255, 213, 117, 0.12), rgba(255,255,255,0.06));
          }}
          .intel-alert-card--info {{
            border-color: rgba(117, 198, 255, 0.24);
            background: linear-gradient(180deg, rgba(117, 198, 255, 0.12), rgba(255,255,255,0.06));
          }}
          .intel-alert-card--notice {{
            border-color: rgba(175, 205, 255, 0.22);
            background: linear-gradient(180deg, rgba(175, 205, 255, 0.11), rgba(255,255,255,0.06));
          }}
          .intel-alert-card--calm {{
            border-color: rgba(150, 237, 197, 0.22);
            background: linear-gradient(180deg, rgba(150, 237, 197, 0.1), rgba(255,255,255,0.06));
          }}
          .intel-tab-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.55rem;
            margin-top: 1rem;
          }}
          .intel-tab {{
            border: 1px solid rgba(255,255,255,0.12);
            background: rgba(255,255,255,0.05);
            color: #eef8ff;
            border-radius: 999px;
            padding: 0.62rem 0.92rem;
            font-size: 0.88rem;
            cursor: pointer;
            transition: transform 0.22s ease, background 0.22s ease, border-color 0.22s ease;
          }}
          .intel-tab:hover,
          .intel-tab.is-active {{
            transform: translateY(-1px);
            background: rgba(255,255,255,0.12);
            border-color: rgba(255,255,255,0.18);
          }}
          .intel-panels {{
            margin-top: 0.95rem;
          }}
          .intel-panel {{
            display: none;
          }}
          .intel-panel.is-active {{
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.8rem;
            animation: panelIn 0.34s ease both;
          }}
          .intel-panel-card {{
            padding: 1rem 1rem 1.02rem;
            min-height: 184px;
            transition: transform 0.22s ease, border-color 0.22s ease, background 0.22s ease;
          }}
          .intel-panel-card:hover {{
            transform: translateY(-2px);
            border-color: rgba(255,255,255,0.12);
            background: rgba(255,255,255,0.085);
          }}
          .intel-panel-eyebrow {{
            font-size: 0.75rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            opacity: 0.68;
          }}
          .intel-panel-title {{
            margin-top: 0.42rem;
            font-size: 1.08rem;
            font-weight: 700;
            line-height: 1.35;
          }}
          .intel-panel-body {{
            margin-top: 0.58rem;
            font-size: 0.92rem;
            line-height: 1.6;
            opacity: 0.86;
          }}
          @keyframes fadeUp {{
            from {{
              opacity: 0;
              transform: translateY(14px);
            }}
            to {{
              opacity: 1;
              transform: translateY(0);
            }}
          }}
          @keyframes panelIn {{
            from {{
              opacity: 0;
              transform: translateY(10px);
            }}
            to {{
              opacity: 1;
              transform: translateY(0);
            }}
          }}
          @media (max-width: 1100px) {{
            .intel-hero {{
              grid-template-columns: 1fr;
            }}
            .intel-score-grid,
            .intel-panel.is-active {{
              grid-template-columns: repeat(2, minmax(0, 1fr));
            }}
          }}
          @media (max-width: 760px) {{
            .intel-shell {{
              padding: 1rem;
            }}
            .intel-hero-stats,
            .intel-score-grid,
            .intel-alert-grid,
            .intel-panel.is-active {{
              grid-template-columns: 1fr;
            }}
            .intel-panel-card,
            .intel-score-card,
            .intel-alert-card {{
              min-height: 0;
            }}
          }}
        </style>

        <script>
          if (window.__skylineIntelligenceCleanup) {{
            window.__skylineIntelligenceCleanup();
          }}

          const root = document.getElementById("intel-shell");
          const tabs = Array.from(root.querySelectorAll(".intel-tab"));
          const panels = Array.from(root.querySelectorAll(".intel-panel"));

          const resizeFrame = () => {{
            const height = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight, 680);
            window.parent.postMessage({{ isStreamlitMessage: true, type: "streamlit:setFrameHeight", height }}, "*");
          }};

          const setActivePanel = (panelName) => {{
            tabs.forEach((tab) => {{
              tab.classList.toggle("is-active", tab.dataset.panel === panelName);
            }});
            panels.forEach((panel) => {{
              panel.classList.toggle("is-active", panel.dataset.panel === panelName);
            }});
            window.setTimeout(resizeFrame, 220);
          }};

          const listeners = tabs.map((tab) => {{
            const handler = () => setActivePanel(tab.dataset.panel);
            tab.addEventListener("click", handler);
            return {{ tab, handler }};
          }});

          window.__skylineIntelligenceCleanup = () => {{
            listeners.forEach((listener) => {{
              listener.tab.removeEventListener("click", listener.handler);
            }});
          }};

          resizeFrame();
        </script>
        """,
        height=680,
    )


def render_export_center(payload):
    component_payload = json.dumps(payload)
    components.html(
        f"""
        <div class="export-shell" id="export-shell">
          <div class="export-header">
            <div class="export-copy">
              <div class="export-kicker">Export Center</div>
              <div class="export-title">Download polished weather reports for {escape(str(payload.get("city", "Selected location")))}</div>
              <div class="export-subtitle">Each export includes current conditions plus the selected forecast range, formatted for spreadsheets, reports, and handoff-friendly sharing.</div>
            </div>
            <div class="export-meta">
              <div class="export-chip">{escape(str(payload.get("temperature_unit", "")))}</div>
              <div class="export-chip">{escape(str(payload.get("wind_unit", "")))}</div>
            </div>
          </div>

          <div class="export-range-row" id="export-range-row"></div>

          <div class="export-preview-card">
            <div class="export-preview-kicker">Selected Range</div>
            <div class="export-preview-title" id="export-preview-title"></div>
            <div class="export-preview-body" id="export-preview-body"></div>
          </div>

          <div class="export-download-grid" id="export-download-grid"></div>
        </div>

        <style>
          html,
          body {{
            margin: 0;
            background: transparent;
            font-family: "Segoe UI", sans-serif;
            color: #eef8ff;
            border-radius: 32px;
            overflow: hidden;
          }}
          .export-shell {{
            border-radius: 32px;
            overflow: hidden;
            padding: 1.15rem 1.2rem;
            background: linear-gradient(180deg, rgba(255,255,255,0.16), rgba(255,255,255,0.08));
            border: 1px solid rgba(255,255,255,0.14);
            box-shadow: 0 16px 42px rgba(4, 15, 32, 0.16);
            backdrop-filter: blur(16px);
          }}
          .export-header {{
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 1rem;
          }}
          .export-kicker,
          .export-preview-kicker,
          .export-file-kicker {{
            font-size: 0.76rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            opacity: 0.68;
          }}
          .export-title {{
            margin-top: 0.34rem;
            font-size: clamp(1.2rem, 2vw, 1.55rem);
            font-weight: 700;
            line-height: 1.25;
          }}
          .export-subtitle {{
            margin-top: 0.5rem;
            max-width: 60ch;
            font-size: 0.93rem;
            line-height: 1.65;
            opacity: 0.84;
          }}
          .export-meta {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.55rem;
            justify-content: flex-end;
          }}
          .export-chip {{
            border-radius: 999px;
            padding: 0.5rem 0.78rem;
            background: rgba(255,255,255,0.07);
            border: 1px solid rgba(255,255,255,0.1);
            font-size: 0.83rem;
            white-space: nowrap;
          }}
          .export-range-row {{
            display: flex;
            flex-wrap: wrap;
            gap: 0.55rem;
            margin-top: 1rem;
          }}
          .export-range-button {{
            border-radius: 999px;
            border: 1px solid rgba(255,255,255,0.12);
            background: rgba(255,255,255,0.05);
            color: #eef8ff;
            padding: 0.6rem 0.92rem;
            font-size: 0.88rem;
            cursor: pointer;
            transition: transform 0.22s ease, background 0.22s ease, border-color 0.22s ease;
          }}
          .export-range-button:hover,
          .export-range-button.is-active {{
            transform: translateY(-1px);
            background: rgba(255,255,255,0.12);
            border-color: rgba(255,255,255,0.18);
          }}
          .export-preview-card {{
            margin-top: 0.95rem;
            padding: 1rem 1.05rem;
            border-radius: 26px;
            background: rgba(255,255,255,0.07);
            border: 1px solid rgba(255,255,255,0.08);
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
          }}
          .export-preview-title {{
            margin-top: 0.3rem;
            font-size: 1.05rem;
            font-weight: 700;
          }}
          .export-preview-body {{
            margin-top: 0.4rem;
            font-size: 0.9rem;
            line-height: 1.6;
            opacity: 0.82;
          }}
          .export-download-grid {{
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.8rem;
            margin-top: 1rem;
          }}
          .export-file-card {{
            border-radius: 26px;
            padding: 1rem 1.05rem;
            background: rgba(255,255,255,0.07);
            border: 1px solid rgba(255,255,255,0.08);
            box-shadow: inset 0 1px 0 rgba(255,255,255,0.04);
            min-height: 212px;
            display: flex;
            flex-direction: column;
          }}
          .export-file-title {{
            margin-top: 0.35rem;
            font-size: 1.08rem;
            font-weight: 700;
          }}
          .export-file-description {{
            margin-top: 0.45rem;
            font-size: 0.9rem;
            line-height: 1.6;
            opacity: 0.82;
            flex: 1;
          }}
          .export-file-size {{
            margin-top: 0.8rem;
            font-size: 0.82rem;
            opacity: 0.7;
          }}
          .export-download-link {{
            margin-top: 0.9rem;
            border-radius: 18px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            min-height: 2.95rem;
            padding: 0.8rem 0.95rem;
            text-decoration: none;
            color: #f4fbff;
            background: linear-gradient(135deg, rgba(214, 239, 250, 0.28), rgba(169, 215, 235, 0.16));
            border: 1px solid rgba(255,255,255,0.16);
            box-shadow: 0 10px 24px rgba(4, 15, 32, 0.14);
            font-weight: 600;
            transition: transform 0.22s ease, background 0.22s ease, border-color 0.22s ease;
          }}
          .export-download-link:hover {{
            transform: translateY(-1px);
            background: linear-gradient(135deg, rgba(225, 246, 255, 0.36), rgba(177, 220, 239, 0.22));
            border-color: rgba(255,255,255,0.24);
          }}
          @media (max-width: 980px) {{
            .export-download-grid {{
              grid-template-columns: 1fr;
            }}
          }}
          @media (max-width: 760px) {{
            .export-shell {{
              padding: 1rem;
            }}
            .export-header {{
              flex-direction: column;
            }}
          }}
        </style>

        <script>
          const payload = {component_payload};
          const rangeRow = document.getElementById("export-range-row");
          const previewTitle = document.getElementById("export-preview-title");
          const previewBody = document.getElementById("export-preview-body");
          const downloadGrid = document.getElementById("export-download-grid");

          const resizeFrame = () => {{
            const height = Math.max(document.body.scrollHeight, document.documentElement.scrollHeight, 470);
            window.parent.postMessage({{ isStreamlitMessage: true, type: "streamlit:setFrameHeight", height }}, "*");
          }};

          const renderDownloads = (rangeItem) => {{
            previewTitle.textContent = rangeItem.label;
            previewBody.textContent = rangeItem.summary;
            downloadGrid.innerHTML = rangeItem.files.map((file) => `
              <div class="export-file-card">
                <div class="export-file-kicker">Download Format</div>
                <div class="export-file-title">${{file.label}}</div>
                <div class="export-file-description">${{file.description}}</div>
                <div class="export-file-size">${{file.size}}</div>
                <a class="export-download-link" href="${{file.href}}" download="${{file.filename}}">Download ${{file.label}}</a>
              </div>
            `).join("");
            window.setTimeout(resizeFrame, 100);
          }};

          const setActiveRange = (rangeKey) => {{
            const rangeItem = (payload.ranges || []).find((item) => item.key === rangeKey) || payload.ranges[0];
            Array.from(rangeRow.querySelectorAll(".export-range-button")).forEach((button) => {{
              button.classList.toggle("is-active", button.dataset.rangeKey === rangeItem.key);
            }});
            renderDownloads(rangeItem);
          }};

          rangeRow.innerHTML = (payload.ranges || []).map((rangeItem, index) => `
            <button
              type="button"
              class="export-range-button${{index === 0 ? " is-active" : ""}}"
              data-range-key="${{rangeItem.key}}"
            >
              ${{rangeItem.label}}
            </button>
          `).join("");

          Array.from(rangeRow.querySelectorAll(".export-range-button")).forEach((button) => {{
            button.addEventListener("click", () => setActiveRange(button.dataset.rangeKey));
          }});

          setActiveRange(payload.ranges[0]?.key || "today");
          resizeFrame();
        </script>
        """,
        height=470,
    )


def render_weather_alert_banner(alerts):
    if not alerts:
        return

    alert_items_html = "".join(
        dedent(
            f"""
            <div class="intel-alert-banner-item intel-alert-banner-item--{escape(str(alert["tone"]))}">
                <div class="intel-alert-icon">{escape(str(alert["icon"]))}</div>
                <div class="intel-alert-copy">
                    <div class="intel-alert-title">{escape(str(alert["title"]))}</div>
                    <div class="intel-alert-body">{escape(str(alert["body"]))}</div>
                </div>
            </div>
            """
        ).strip()
        for alert in alerts
    )
    st.markdown(
        f"""
        <div class="intel-alert-banner">
            <div class="intel-alert-banner-grid">{alert_items_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_todays_insight_card(city_name, condition, insights, show_supporting_notes=True, style_variant="standard", time_note=None):
    if not insights:
        return

    primary_insight = insights[0]
    supporting_insights = insights[1:] if show_supporting_notes else []
    supporting_html = "".join(
        dedent(
            f"""
            <div class="intel-mini-note">
                <div class="intel-mini-note-label">{escape(str(insight["eyebrow"]))}</div>
                <div class="intel-mini-note-title">{escape(str(insight["title"]))}</div>
                <div class="intel-mini-note-body">{escape(str(insight["body"]))}</div>
            </div>
            """
        ).strip()
        for insight in supporting_insights
    )
    support_block = (
        f"<div class='intel-support-grid intel-support-grid--{escape(str(style_variant))}'>{supporting_html}</div>"
        if supporting_html
        else ""
    )

    st.markdown(
        f"""
        <div class="intel-card intel-card--{escape(str(style_variant))}">
            <div class="intel-card-kicker">Today's Insight</div>
            <div class="intel-card-title">{escape(get_condition_icon(condition))} {escape(str(primary_insight["title"]))}</div>
            <div class="intel-card-body">{escape(str(primary_insight["body"]))}</div>
            <div class="intel-card-note">{escape(str(time_note or f'This summary is tuned to {city_name} using the current weather snapshot.'))}</div>
            {support_block}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_weather_score_row(scores, card_variant="standard"):
    if not scores:
        return

    score_columns = st.columns(len(scores))
    for column, score in zip(score_columns, scores):
        with column:
            st.markdown(
                f"""
                <div class="intel-score-card-compact intel-score-card-compact--{escape(str(score["key"]))} intel-score-card-compact--{escape(str(card_variant))}">
                    <div class="intel-score-label">{escape(str(score["label"]))}</div>
                    <div class="intel-score-value">{escape(str(score["value"]))}<span>/10</span></div>
                    <div class="intel-score-summary">{escape(str(score["summary"]))}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def render_recommendation_card(title, kicker, items, style_variant="standard"):
    items_html = "".join(
        dedent(
            f"""
            <div class="intel-recommend-item">
                <div class="intel-recommend-item-title">{escape(str(item["title"]))}</div>
                <div class="intel-recommend-item-body">{escape(str(item["body"]))}</div>
            </div>
            """
        ).strip()
        for item in items
    )
    st.markdown(
        f"""
        <div class="intel-recommend-card intel-recommend-card--{escape(str(style_variant))}">
            <div class="intel-recommend-header">
                <div class="intel-recommend-title">{escape(title)}</div>
                <div class="intel-recommend-kicker">{escape(kicker)}</div>
            </div>
            <div class="intel-recommend-list">{items_html}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_guidance_card_grid(items, grid_variant="standard"):
    if not items:
        return

    cards_html = "".join(
        dedent(
            f"""
            <div class="intel-focus-card">
                <div class="intel-focus-card-header">
                    <div class="intel-focus-icon">{escape(str(item.get("icon", "\u2022")))}</div>
                    <div>
                        <div class="intel-focus-card-kicker">{escape(str(item.get("eyebrow", "Recommendation")))}</div>
                        <div class="intel-focus-card-title">{escape(str(item["title"]))}</div>
                    </div>
                </div>
                <div class="intel-focus-card-body">{escape(str(item["body"]))}</div>
            </div>
            """
        ).strip()
        for item in items
    )
    st.markdown(
        f"""
        <div class="intel-focus-grid intel-focus-grid--{escape(str(grid_variant))}">
            {cards_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def _wear_variant_state_key(state_prefix, item):
    item_key = str(item.get("item_id") or item.get("eyebrow") or "wear").lower().replace(" ", "-")
    profile_key = str(item.get("visual_profile") or "default").lower().replace(" ", "-")
    return f"{state_prefix}-{item_key}-{profile_key}"


def _select_unique_wear_variant(variants, preferred_index, used_image_urls):
    if not variants:
        return 0, {}

    normalized_index = preferred_index % len(variants)
    for offset in range(len(variants)):
        candidate_index = (normalized_index + offset) % len(variants)
        candidate = variants[candidate_index]
        candidate_url = str(candidate.get("image_url") or "")
        if candidate_url and candidate_url not in used_image_urls:
            return candidate_index, candidate
    return normalized_index, variants[normalized_index]


def _render_visual_clothing_card_component(item, variants, initial_index, component_key):
    payload = {
        "eyebrow": str(item.get("eyebrow", "Recommendation")),
        "title": str(item.get("title", "Suggested Piece")),
        "icon": str(item.get("icon", "•")),
        "initial_index": int(initial_index),
        "variants": [
            {
                "style_name": str(variant.get("style_name", "Style option")),
                "image_url": str(variant.get("image_url", "")),
                "note": str(variant.get("note", "") or item.get("body", "")),
                "badges": [str(badge) for badge in variant.get("badges", [])],
            }
            for variant in variants
        ],
    }
    payload_json = json.dumps(payload)
    html = f"""
    <html>
      <head>
        <style>
          :root {{ color-scheme: dark; }}
          body {{
            margin: 0;
            background: transparent;
            font-family: "Segoe UI", Arial, sans-serif;
            color: #eef8ff;
          }}
          .wear-card {{
            border-radius: 26px;
            padding: 0.95rem;
            background: linear-gradient(180deg, rgba(112, 152, 200, 0.58), rgba(78, 120, 170, 0.38));
            border: 1px solid rgba(255, 255, 255, 0.14);
            box-shadow: 0 16px 38px rgba(4, 15, 32, 0.15);
            box-sizing: border-box;
            min-height: 100%;
          }}
          .wear-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            gap: 0.8rem;
          }}
          .wear-kicker {{
            font-size: 0.7rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            opacity: 0.74;
          }}
          .wear-title {{
            margin-top: 0.28rem;
            font-size: 1.05rem;
            font-weight: 700;
            line-height: 1.3;
          }}
          .wear-icon {{
            width: 2.85rem;
            height: 2.85rem;
            border-radius: 18px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.1);
            font-size: 1.18rem;
            flex-shrink: 0;
          }}
          .wear-image-shell {{
            margin-top: 0.9rem;
            border-radius: 22px;
            overflow: hidden;
            border: 1px solid rgba(255,255,255,0.1);
            background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(242, 246, 251, 0.96));
            min-height: 182px;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 0.85rem;
            box-sizing: border-box;
          }}
          .wear-image {{
            display: block;
            width: 100%;
            height: 150px;
            object-fit: contain;
          }}
          .wear-style-row {{
            margin-top: 0.85rem;
            display: flex;
            justify-content: space-between;
            gap: 0.75rem;
            align-items: center;
            flex-wrap: wrap;
          }}
          .wear-style-name {{
            font-size: 0.96rem;
            font-weight: 700;
          }}
          .wear-style-count {{
            font-size: 0.76rem;
            opacity: 0.68;
          }}
          .wear-badges {{
            margin-top: 0.65rem;
            display: flex;
            gap: 0.45rem;
            flex-wrap: wrap;
          }}
          .wear-badge {{
            padding: 0.3rem 0.6rem;
            border-radius: 999px;
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.08);
            font-size: 0.73rem;
            opacity: 0.88;
          }}
          .wear-copy {{
            margin-top: 0.82rem;
            font-size: 0.89rem;
            line-height: 1.62;
            opacity: 0.85;
          }}
          .wear-refresh {{
            width: 100%;
            min-height: 2.9rem;
            margin-top: 0.9rem;
            border-radius: 18px;
            border: 1px solid rgba(255,255,255,0.12);
            background: linear-gradient(180deg, rgba(255,255,255,0.14), rgba(255,255,255,0.06));
            color: #eef8ff;
            font-size: 0.9rem;
            font-weight: 600;
            cursor: pointer;
          }}
          .wear-refresh:hover {{
            border-color: rgba(255,255,255,0.22);
            color: #ffffff;
          }}
        </style>
      </head>
      <body>
        <div class="wear-card">
          <div class="wear-header">
            <div>
              <div class="wear-kicker" id="wear-kicker-{component_key}"></div>
              <div class="wear-title" id="wear-title-{component_key}"></div>
            </div>
            <div class="wear-icon" id="wear-icon-{component_key}"></div>
          </div>
          <div class="wear-image-shell">
            <img class="wear-image" id="wear-image-{component_key}" alt="">
          </div>
          <div class="wear-style-row">
            <div class="wear-style-name" id="wear-style-name-{component_key}"></div>
            <div class="wear-style-count" id="wear-style-count-{component_key}"></div>
          </div>
          <div class="wear-badges" id="wear-badges-{component_key}"></div>
          <div class="wear-copy" id="wear-copy-{component_key}"></div>
          <button class="wear-refresh" id="wear-refresh-{component_key}" type="button">Refresh Style</button>
        </div>
        <script>
          const payload = {payload_json};
          let index = payload.initial_index || 0;
          const kickerNode = document.getElementById("wear-kicker-{component_key}");
          const titleNode = document.getElementById("wear-title-{component_key}");
          const iconNode = document.getElementById("wear-icon-{component_key}");
          const imageNode = document.getElementById("wear-image-{component_key}");
          const styleNameNode = document.getElementById("wear-style-name-{component_key}");
          const styleCountNode = document.getElementById("wear-style-count-{component_key}");
          const badgesNode = document.getElementById("wear-badges-{component_key}");
          const copyNode = document.getElementById("wear-copy-{component_key}");
          const refreshNode = document.getElementById("wear-refresh-{component_key}");

          kickerNode.textContent = payload.eyebrow;
          titleNode.textContent = payload.title;
          iconNode.textContent = payload.icon;

          function renderCard() {{
            const variants = payload.variants || [];
            if (!variants.length) return;
            const safeIndex = ((index % variants.length) + variants.length) % variants.length;
            const variant = variants[safeIndex];
            imageNode.src = variant.image_url || "";
            imageNode.alt = variant.style_name || payload.title || "Clothing recommendation";
            styleNameNode.textContent = variant.style_name || "Style option";
            styleCountNode.textContent = `Style ${{safeIndex + 1}} / ${{variants.length}}`;
            copyNode.textContent = variant.note || "";
            badgesNode.innerHTML = (variant.badges || []).map((badge) => `<span class="wear-badge">${{badge}}</span>`).join("");
          }}

          refreshNode.addEventListener("click", () => {{
            const variants = payload.variants || [];
            if (!variants.length) return;
            index = (index + 1) % variants.length;
            renderCard();
          }});

          renderCard();
        </script>
      </body>
    </html>
    """
    components.html(html, height=430, scrolling=False)


def render_visual_clothing_grid(items, state_prefix="wear"):
    if not items:
        return

    used_image_urls = set()

    for row_start in range(0, len(items), 3):
        row_columns = st.columns(3)
        for item, column in zip(items[row_start : row_start + 3], row_columns):
            with column:
                variants = item.get("variants") or []
                if not variants:
                    render_guidance_card_grid([item], grid_variant="wear")
                    continue

                state_key = _wear_variant_state_key(state_prefix, item)
                current_index = int(st.session_state.get(state_key, 0)) % len(variants)
                resolved_index, variant = _select_unique_wear_variant(variants, current_index, used_image_urls)
                variant_url = str(variant.get("image_url") or "")
                if variant_url:
                    used_image_urls.add(variant_url)
                _render_visual_clothing_card_component(
                    item,
                    variants,
                    resolved_index,
                    component_key=state_key.replace("_", "-"),
                )

    return

    used_image_urls = set()

    for row_start in range(0, len(items), 3):
        row_columns = st.columns(3)
        for item, column in zip(items[row_start : row_start + 3], row_columns):
            with column:
                variants = item.get("variants") or []
                if not variants:
                    render_guidance_card_grid([item], grid_variant="wear")
                    continue

                state_key = _wear_variant_state_key(state_prefix, item)
                current_index = int(st.session_state.get(state_key, 0)) % len(variants)
                resolved_index, variant = _select_unique_wear_variant(variants, current_index, used_image_urls)
                variant_url = str(variant.get("image_url") or "")
                if variant_url:
                    used_image_urls.add(variant_url)
                badges_html = "".join(
                    f"<span class='wear-visual-badge'>{escape(str(badge))}</span>"
                    for badge in variant.get("badges", [])
                )
                card_html = f"""
                <div class="wear-visual-card">
                    <div class="wear-visual-header">
                        <div>
                            <div class="wear-visual-kicker">{escape(str(item.get("eyebrow", "Recommendation")))}</div>
                            <div class="wear-visual-title">{escape(str(item.get("title", "Suggested Piece")))}</div>
                        </div>
                        <div class="wear-visual-icon">{escape(str(item.get("icon", "•")))}</div>
                    </div>
                    <div class="wear-visual-image-shell">
                        <img class="wear-visual-image" src="{escape(str(variant.get("image_url") or ""), quote=True)}" alt="{escape(str(variant.get("style_name") or item.get("title") or "Clothing recommendation"), quote=True)}">
                    </div>
                    <div class="wear-visual-style">
                        <div class="wear-visual-style-name">{escape(str(variant.get("style_name") or "Style option"))}</div>
                        <div class="wear-visual-count">Style {resolved_index + 1} / {len(variants)}</div>
                    </div>
                    <div class="wear-visual-badges">{badges_html}</div>
                    <div class="wear-visual-body">{escape(str(variant.get("note") or item.get("body") or ""))}</div>
                </div>
                """
                st.markdown(card_html, unsafe_allow_html=True)
                st.markdown("<div class='wear-refresh-anchor'></div>", unsafe_allow_html=True)
                if len(variants) > 1 and st.button(
                    "Refresh Style",
                    key=f"{state_key}-refresh",
                    type="secondary",
                    use_container_width=True,
                ):
                    st.session_state[state_key] = (resolved_index + 1) % len(variants)
                    st.rerun()


def _render_visual_clothing_card_component(item, variants, initial_index, component_key):
    payload = {
        "eyebrow": str(item.get("eyebrow", "Recommendation")),
        "title": str(item.get("title", "Suggested Piece")),
        "icon": str(item.get("icon", "\u2022")),
        "initial_index": int(initial_index),
        "variants": [
            {
                "style_name": str(variant.get("style_name", "Style option")),
                "image_url": str(variant.get("image_url", "")),
                "note": str(variant.get("note", "") or item.get("body", "")),
                "badges": [str(badge) for badge in variant.get("badges", [])],
            }
            for variant in variants
        ],
    }
    payload_json = json.dumps(payload)
    html = f"""
    <html>
      <head>
        <style>
          :root {{ color-scheme: dark; }}
          html, body {{
            margin: 0;
            padding: 0;
            background: transparent;
            font-family: "Segoe UI", Arial, sans-serif;
            color: #eef8ff;
          }}
          .wear-card {{
            border-radius: 26px;
            padding: 0.95rem;
            background: linear-gradient(180deg, rgba(255,255,255,0.16), rgba(255,255,255,0.07));
            border: 1px solid rgba(255,255,255,0.12);
            box-shadow: 0 16px 38px rgba(4, 15, 32, 0.15);
            box-sizing: border-box;
            backdrop-filter: blur(14px);
          }}
          .wear-header {{
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 0.85rem;
          }}
          .wear-kicker {{
            font-size: 0.72rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            opacity: 0.7;
          }}
          .wear-title {{
            margin-top: 0.28rem;
            font-size: 1.08rem;
            font-weight: 700;
            line-height: 1.3;
          }}
          .wear-icon {{
            width: 2.9rem;
            height: 2.9rem;
            border-radius: 18px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.1);
            font-size: 1.2rem;
            flex-shrink: 0;
          }}
          .wear-image-shell {{
            margin-top: 0.9rem;
            border-radius: 22px;
            overflow: hidden;
            border: 1px solid rgba(255,255,255,0.1);
            background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(242, 246, 251, 0.96));
            min-height: 182px;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 0.85rem;
            box-sizing: border-box;
          }}
          .wear-image {{
            display: block;
            width: 100%;
            height: 150px;
            object-fit: contain;
            border-radius: 18px;
          }}
          .wear-style-row {{
            margin-top: 0.85rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.75rem;
            flex-wrap: wrap;
          }}
          .wear-style-name {{
            font-size: 0.96rem;
            font-weight: 700;
          }}
          .wear-style-count {{
            font-size: 0.76rem;
            opacity: 0.68;
          }}
          .wear-badges {{
            margin-top: 0.65rem;
            display: flex;
            gap: 0.45rem;
            flex-wrap: wrap;
          }}
          .wear-badge {{
            padding: 0.3rem 0.6rem;
            border-radius: 999px;
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.08);
            font-size: 0.73rem;
            opacity: 0.88;
          }}
          .wear-copy {{
            margin-top: 0.8rem;
            font-size: 0.9rem;
            line-height: 1.62;
            opacity: 0.84;
          }}
          .wear-refresh {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 100%;
            min-height: 2.9rem;
            margin-top: 0.9rem;
            border-radius: 18px;
            border: 1px solid rgba(255,255,255,0.12);
            background: linear-gradient(180deg, rgba(255,255,255,0.12), rgba(255,255,255,0.06));
            color: #eef8ff;
            font-size: 0.9rem;
            font-weight: 600;
            cursor: pointer;
            box-shadow: none;
          }}
          .wear-refresh:hover,
          .wear-refresh:focus {{
            border-color: rgba(255,255,255,0.2);
            color: #ffffff;
            outline: none;
          }}
        </style>
      </head>
      <body>
        <div class="wear-card">
          <div class="wear-header">
            <div>
              <div class="wear-kicker" id="wear-kicker-{component_key}"></div>
              <div class="wear-title" id="wear-title-{component_key}"></div>
            </div>
            <div class="wear-icon" id="wear-icon-{component_key}"></div>
          </div>
          <div class="wear-image-shell">
            <img class="wear-image" id="wear-image-{component_key}" alt="">
          </div>
          <div class="wear-style-row">
            <div class="wear-style-name" id="wear-style-name-{component_key}"></div>
            <div class="wear-style-count" id="wear-style-count-{component_key}"></div>
          </div>
          <div class="wear-badges" id="wear-badges-{component_key}"></div>
          <div class="wear-copy" id="wear-copy-{component_key}"></div>
          <button class="wear-refresh" id="wear-refresh-{component_key}" type="button">Refresh Style</button>
        </div>
        <script>
          const payload = {payload_json};
          let index = payload.initial_index || 0;
          const kickerNode = document.getElementById("wear-kicker-{component_key}");
          const titleNode = document.getElementById("wear-title-{component_key}");
          const iconNode = document.getElementById("wear-icon-{component_key}");
          const imageNode = document.getElementById("wear-image-{component_key}");
          const styleNameNode = document.getElementById("wear-style-name-{component_key}");
          const styleCountNode = document.getElementById("wear-style-count-{component_key}");
          const badgesNode = document.getElementById("wear-badges-{component_key}");
          const copyNode = document.getElementById("wear-copy-{component_key}");
          const refreshNode = document.getElementById("wear-refresh-{component_key}");

          kickerNode.textContent = payload.eyebrow;
          titleNode.textContent = payload.title;
          iconNode.textContent = payload.icon;

          function renderCard() {{
            const variants = payload.variants || [];
            if (!variants.length) return;
            const safeIndex = ((index % variants.length) + variants.length) % variants.length;
            const variant = variants[safeIndex];
            imageNode.src = variant.image_url || "";
            imageNode.alt = variant.style_name || payload.title || "Clothing recommendation";
            styleNameNode.textContent = variant.style_name || "Style option";
            styleCountNode.textContent = `Style ${{safeIndex + 1}} / ${{variants.length}}`;
            copyNode.textContent = variant.note || "";
            badgesNode.innerHTML = (variant.badges || [])
              .map((badge) => `<span class="wear-badge">${{badge}}</span>`)
              .join("");
          }}

          refreshNode.addEventListener("click", () => {{
            const variants = payload.variants || [];
            if (!variants.length) return;
            index = (index + 1) % variants.length;
            renderCard();
          }});

          renderCard();
        </script>
      </body>
    </html>
    """
    components.html(html, height=420, scrolling=False)


def render_visual_clothing_grid(items, state_prefix="wear"):
    if not items:
        return

    used_image_urls = set()

    for row_start in range(0, len(items), 3):
        row_columns = st.columns(3)
        for item, column in zip(items[row_start : row_start + 3], row_columns):
            with column:
                variants = item.get("variants") or []
                if not variants:
                    render_guidance_card_grid([item], grid_variant="wear")
                    continue

                state_key = _wear_variant_state_key(state_prefix, item)
                default_index = int(item.get("preferred_variant_index", 0))
                current_index = int(st.session_state.get(state_key, default_index)) % len(variants)
                resolved_index, variant = _select_unique_wear_variant(
                    variants,
                    current_index,
                    used_image_urls,
                )
                variant_url = str(variant.get("image_url") or "")
                if variant_url:
                    used_image_urls.add(variant_url)
                _render_visual_clothing_card_component(
                    item,
                    variants,
                    resolved_index,
                    component_key=f"{state_key.replace('_', '-')}-card",
                )


def _render_visual_clothing_card_component(item, variants, initial_index, component_key):
    payload = {
        "eyebrow": str(item.get("eyebrow", "Recommendation")),
        "title": str(item.get("title", "Suggested Piece")),
        "icon": str(item.get("icon", "\u2022")),
        "initial_index": int(initial_index),
        "variants": [
            {
                "style_name": str(variant.get("style_name", "Style option")),
                "image_url": str(variant.get("image_url", "")),
                "note": str(variant.get("note", "") or item.get("body", "")),
                "badges": [str(badge) for badge in variant.get("badges", [])],
            }
            for variant in variants
        ],
    }
    payload_json = json.dumps(payload)
    html = f"""
    <html>
      <head>
        <style>
          :root {{ color-scheme: dark; }}
          html, body {{
            margin: 0;
            padding: 0;
            background: transparent;
            font-family: "Segoe UI", Arial, sans-serif;
            color: #eef8ff;
          }}
          .wear-visual-card {{
            border-radius: 26px;
            padding: 0.95rem;
            background: linear-gradient(180deg, rgba(255,255,255,0.16), rgba(255,255,255,0.07));
            border: 1px solid rgba(255,255,255,0.12);
            box-shadow: 0 16px 38px rgba(4, 15, 32, 0.15);
            backdrop-filter: blur(14px);
            box-sizing: border-box;
          }}
          .wear-visual-header {{
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 0.85rem;
          }}
          .wear-visual-kicker {{
            font-size: 0.72rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            opacity: 0.7;
          }}
          .wear-visual-title {{
            margin-top: 0.28rem;
            font-size: 1.08rem;
            font-weight: 700;
            line-height: 1.3;
          }}
          .wear-visual-icon {{
            width: 2.9rem;
            height: 2.9rem;
            border-radius: 18px;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.1);
            font-size: 1.2rem;
            flex-shrink: 0;
          }}
          .wear-visual-image-shell {{
            margin-top: 0.9rem;
            border-radius: 22px;
            overflow: hidden;
            border: 1px solid rgba(255,255,255,0.1);
            background: linear-gradient(180deg, rgba(255,255,255,0.98), rgba(242, 246, 251, 0.96));
            min-height: 182px;
            display: flex;
            align-items: center;
            justify-content: center;
            padding: 0.85rem;
            box-sizing: border-box;
          }}
          .wear-visual-image {{
            display: block;
            width: 100%;
            height: 150px;
            object-fit: contain;
            border-radius: 18px;
          }}
          .wear-visual-style {{
            margin-top: 0.85rem;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 0.75rem;
            flex-wrap: wrap;
          }}
          .wear-visual-style-name {{
            font-size: 0.96rem;
            font-weight: 700;
          }}
          .wear-visual-count {{
            font-size: 0.76rem;
            opacity: 0.68;
          }}
          .wear-visual-badges {{
            margin-top: 0.65rem;
            display: flex;
            gap: 0.45rem;
            flex-wrap: wrap;
          }}
          .wear-visual-badge {{
            padding: 0.3rem 0.6rem;
            border-radius: 999px;
            background: rgba(255,255,255,0.08);
            border: 1px solid rgba(255,255,255,0.08);
            font-size: 0.73rem;
            opacity: 0.88;
          }}
          .wear-visual-body {{
            margin-top: 0.8rem;
            font-size: 0.9rem;
            line-height: 1.62;
            opacity: 0.84;
          }}
          .wear-visual-refresh {{
            display: inline-flex;
            align-items: center;
            justify-content: center;
            width: 100%;
            min-height: 2.9rem;
            margin-top: 0.95rem;
            border-radius: 18px;
            border: 1px solid rgba(255,255,255,0.12);
            background: linear-gradient(180deg, rgba(255,255,255,0.12), rgba(255,255,255,0.06));
            color: #eef8ff;
            font-size: 0.9rem;
            font-weight: 600;
            cursor: pointer;
            box-sizing: border-box;
          }}
          .wear-visual-refresh:hover,
          .wear-visual-refresh:focus {{
            border-color: rgba(255,255,255,0.2);
            color: #ffffff;
            outline: none;
          }}
        </style>
      </head>
      <body>
        <div class="wear-visual-card">
          <div class="wear-visual-header">
            <div>
              <div class="wear-visual-kicker" id="wear-kicker-{component_key}"></div>
              <div class="wear-visual-title" id="wear-title-{component_key}"></div>
            </div>
            <div class="wear-visual-icon" id="wear-icon-{component_key}"></div>
          </div>
          <div class="wear-visual-image-shell">
            <img class="wear-visual-image" id="wear-image-{component_key}" alt="">
          </div>
          <div class="wear-visual-style">
            <div class="wear-visual-style-name" id="wear-style-name-{component_key}"></div>
            <div class="wear-visual-count" id="wear-style-count-{component_key}"></div>
          </div>
          <div class="wear-visual-badges" id="wear-badges-{component_key}"></div>
          <div class="wear-visual-body" id="wear-copy-{component_key}"></div>
          <button class="wear-visual-refresh" id="wear-refresh-{component_key}" type="button">Refresh Style</button>
        </div>
        <script>
          const payload = {payload_json};
          let index = payload.initial_index || 0;
          const kickerNode = document.getElementById("wear-kicker-{component_key}");
          const titleNode = document.getElementById("wear-title-{component_key}");
          const iconNode = document.getElementById("wear-icon-{component_key}");
          const imageNode = document.getElementById("wear-image-{component_key}");
          const styleNameNode = document.getElementById("wear-style-name-{component_key}");
          const styleCountNode = document.getElementById("wear-style-count-{component_key}");
          const badgesNode = document.getElementById("wear-badges-{component_key}");
          const copyNode = document.getElementById("wear-copy-{component_key}");
          const refreshNode = document.getElementById("wear-refresh-{component_key}");

          kickerNode.textContent = payload.eyebrow;
          titleNode.textContent = payload.title;
          iconNode.textContent = payload.icon;

          function renderCard() {{
            const variants = payload.variants || [];
            if (!variants.length) return;
            const safeIndex = ((index % variants.length) + variants.length) % variants.length;
            const variant = variants[safeIndex];
            imageNode.src = variant.image_url || "";
            imageNode.alt = variant.style_name || payload.title || "Clothing recommendation";
            styleNameNode.textContent = variant.style_name || "Style option";
            styleCountNode.textContent = `Style ${{safeIndex + 1}} / ${{variants.length}}`;
            copyNode.textContent = variant.note || "";
            badgesNode.innerHTML = (variant.badges || [])
              .map((badge) => `<span class="wear-visual-badge">${{badge}}</span>`)
              .join("");
          }}

          refreshNode.addEventListener("click", () => {{
            const variants = payload.variants || [];
            if (!variants.length) return;
            index = (index + 1) % variants.length;
            renderCard();
          }});

          renderCard();
        </script>
      </body>
    </html>
    """
    components.html(html, height=420, scrolling=False)


def render_visual_clothing_grid(items, state_prefix="wear"):
    if not items:
        return

    used_image_urls = set()

    for row_start in range(0, len(items), 3):
        row_columns = st.columns(3)
        for item, column in zip(items[row_start : row_start + 3], row_columns):
            with column:
                variants = item.get("variants") or []
                if not variants:
                    render_guidance_card_grid([item], grid_variant="wear")
                    continue

                state_key = _wear_variant_state_key(state_prefix, item)
                preferred_index = int(item.get("preferred_variant_index", 0))
                current_index = int(st.session_state.get(state_key, preferred_index)) % len(variants)
                resolved_index, variant = _select_unique_wear_variant(
                    variants,
                    current_index,
                    used_image_urls,
                )
                variant_url = str(variant.get("image_url") or "")
                if variant_url:
                    used_image_urls.add(variant_url)
                _render_visual_clothing_card_component(
                    item,
                    variants,
                    resolved_index,
                    component_key=f"{state_key.replace('_', '-')}-original-card",
                )


def render_visual_clothing_grid(items, state_prefix="wear"):
    if not items:
        return

    used_image_urls = set()

    for row_start in range(0, len(items), 3):
        row_columns = st.columns(3)
        for item, column in zip(items[row_start : row_start + 3], row_columns):
            with column:
                variants = item.get("variants") or []
                if not variants:
                    render_guidance_card_grid([item], grid_variant="wear")
                    continue

                state_key = _wear_variant_state_key(state_prefix, item)
                current_index = int(st.session_state.get(state_key, 0)) % len(variants)
                resolved_index, variant = _select_unique_wear_variant(
                    variants,
                    current_index,
                    used_image_urls,
                )
                variant_url = str(variant.get("image_url") or "")
                if variant_url:
                    used_image_urls.add(variant_url)

                badges_html = "".join(
                    f"<span class='wear-visual-badge'>{escape(str(badge))}</span>"
                    for badge in variant.get("badges", [])
                )
                card_html = f"""
                <div class="wear-visual-card">
                    <div class="wear-visual-header">
                        <div>
                            <div class="wear-visual-kicker">{escape(str(item.get("eyebrow", "Recommendation")))}</div>
                            <div class="wear-visual-title">{escape(str(item.get("title", "Suggested Piece")))}</div>
                        </div>
                        <div class="wear-visual-icon">{escape(str(item.get("icon", "\u2022")))}</div>
                    </div>
                    <div class="wear-visual-image-shell">
                        <img class="wear-visual-image" src="{escape(str(variant.get("image_url") or ""), quote=True)}" alt="{escape(str(variant.get("style_name") or item.get("title") or "Clothing recommendation"), quote=True)}">
                    </div>
                    <div class="wear-visual-style">
                        <div class="wear-visual-style-name">{escape(str(variant.get("style_name") or "Style option"))}</div>
                        <div class="wear-visual-count">Style {resolved_index + 1} / {len(variants)}</div>
                    </div>
                    <div class="wear-visual-badges">{badges_html}</div>
                    <div class="wear-visual-body">{escape(str(variant.get("note") or item.get("body") or ""))}</div>
                </div>
                """
                st.markdown(card_html, unsafe_allow_html=True)
                st.markdown("<div class='wear-refresh-anchor'></div>", unsafe_allow_html=True)
                if len(variants) > 1 and st.button(
                    "Refresh Style",
                    key=f"{state_key}-refresh-active",
                    type="secondary",
                    use_container_width=True,
                ):
                    st.session_state[state_key] = (resolved_index + 1) % len(variants)
                    st.rerun()


def render_weather_intelligence_sections(payload):
    render_weather_alert_banner(payload.get("alerts", []))
    render_todays_insight_card(
        payload.get("city"),
        payload.get("condition"),
        payload.get("insights", []),
        time_note=(payload.get("time_context") or {}).get("time_note"),
    )

    st.markdown("<div class='section-title'>Weather Scores</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='section-subtitle'>Comfort, outdoor conditions, and travel readiness scored from the same live weather logic.</div>",
        unsafe_allow_html=True,
    )
    render_weather_score_row(payload.get("scores", []))

    st.markdown("<div class='section-title'>Recommendations</div>", unsafe_allow_html=True)
    st.markdown(
        "<div class='section-subtitle'>Activity and clothing guidance split into separate cards for faster scanning.</div>",
        unsafe_allow_html=True,
    )
    recommendation_columns = st.columns(2)
    with recommendation_columns[0]:
        render_recommendation_card("Activity Recommendations", "Movement", payload.get("activities", []))
    with recommendation_columns[1]:
        render_recommendation_card("Clothing Recommendations", "What To Wear", payload.get("clothing", []))


def render_metric_card(title, value, subtitle=""):
    subtitle_html = f"<div class='metric-subtitle'>{subtitle}</div>" if subtitle else ""
    st.markdown(
        f"""
        <div class="metric-card glass">
            <div class="metric-title">{title}</div>
            <div class="metric-value">{value}</div>
            {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_expandable_metric_card(title, value, subtitle="", extra_lines=None):
    extra_lines = extra_lines or []
    extra_html = "".join(
        f"<div class='metric-extra-line'>{line}</div>" for line in extra_lines
    )
    card_id = f"metric-{title.lower().replace(' ', '-')}"
    content = dedent(
        f"""
        <div class="metric-card-shell">
            <input class="metric-toggle" type="checkbox" id="{card_id}">
            <label class="metric-card glass interactive" for="{card_id}">
                <div class="metric-summary">
                    <div class="metric-summary-copy">
                        <div class="metric-title">{title}</div>
                        <div class="metric-value">{value}</div>
                        <div class="metric-subtitle">{subtitle}</div>
                    </div>
                    <div class="metric-chevron">&#9662;</div>
                </div>
                <div class="metric-extra">{extra_html}</div>
            </label>
        </div>
        """
    ).strip()
    st.markdown(content, unsafe_allow_html=True)


def render_forecast_card(day, low_value, high_value, temp_symbol):
    st.markdown(
        f"""
        <div class="forecast-card glass">
            <div class="forecast-day">{day['day']}</div>
            <div class="forecast-condition">{get_condition_icon(day['condition'])} {day['condition']}</div>
            <div class="forecast-range">Low: {low_value}{temp_symbol}</div>
            <div class="forecast-range">High: {high_value}{temp_symbol}</div>
            <div class="forecast-extra">Rain chance: {day['rain_chance']}%</div>
            <div class="forecast-extra">Rain total: {format_precipitation(day['rain_total'])}</div>
            <div class="forecast-extra">UV: {day['uv_index']}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_forecast_list(forecast_rows):
    rows_html = "".join(forecast_rows)
    st.markdown(f"<div class='forecast-list'>{rows_html}</div>", unsafe_allow_html=True)


def build_forecast_row(day_label, condition, low_value, high_value, temp_symbol, fill_percent, forecast_index=0):
    fill_percent = max(18, min(fill_percent, 100))
    return dedent(
        f"""
        <div class="forecast-row-shell">
            <form class="forecast-row-form" method="get">
                <input type="hidden" name="forecast_index" value="{forecast_index}">
                <button class="forecast-item-label forecast-row-button" type="submit">
                    <div class="forecast-row">
                        <div class="forecast-day-name">{escape(day_label)}</div>
                        <div class="forecast-icon">{get_condition_icon(condition)}</div>
                        <div class="forecast-low">{low_value}{temp_symbol}</div>
                        <div class="forecast-bar"><div class="forecast-bar-fill" style="width:{fill_percent}%"></div></div>
                        <div class="forecast-high">{high_value}{temp_symbol}</div>
                        <div class="forecast-chevron">&#9662;</div>
                    </div>
                </button>
            </form>
        </div>
        """
    ).strip()
