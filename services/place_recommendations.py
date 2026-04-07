import math
from urllib.parse import quote_plus

import requests
import streamlit as st


OVERPASS_URL = "https://overpass-api.de/api/interpreter"
PLACE_LOOKUP_TIMEOUT_SECONDS = 3

INDOOR_TOURISM_TAGS = {"museum", "gallery", "aquarium"}
OUTDOOR_TOURISM_TAGS = {"attraction", "viewpoint", "theme_park", "zoo", "artwork"}
LEISURE_OUTDOOR_TAGS = {"park", "garden", "nature_reserve", "water_park"}
INDOOR_AMENITY_TAGS = {"theatre", "cinema", "arts_centre", "library", "planetarium"}
HISTORIC_TAGS = {"castle", "ruins", "memorial", "monument"}
SCENIC_NATURAL_TAGS = {"beach", "peak"}
GENERIC_NAME_FRAGMENTS = {
    "bus stop",
    "charging station",
    "gate",
    "parking",
    "school",
    "station",
    "stop",
    "terminal",
}

PLACE_MODE_CONFIG = {
    "clear": {
        "indoor_weight": 3.5,
        "outdoor_weight": 9.5,
        "scenic_weight": 5.0,
        "fit_note": "Best fit for clear, drier weather when outdoor time is easier to enjoy.",
        "fallbacks": [
            ("Scenic viewpoints", "Stronger pick when the weather is open and visibility is better."),
            ("Public gardens", "Good for a lighter outdoor stop while the weather stays settled."),
            ("Historic landmarks", "Useful when you want a classic first-stop landmark in better daylight."),
            ("Waterfront walks", "Works best when the weather is calm enough for a longer outdoor stretch."),
        ],
    },
    "mixed": {
        "indoor_weight": 6.0,
        "outdoor_weight": 6.5,
        "scenic_weight": 3.0,
        "fit_note": "Balanced option when the weather is usable but not perfect all day.",
        "fallbacks": [
            ("Top attractions", "Solid all-round option when the weather does not clearly favor indoor or outdoor plans."),
            ("City parks", "Good if you want a lighter outdoor plan without committing to a full-day route."),
            ("Museums and galleries", "Easy backup if the weather shifts later."),
            ("Historic districts", "Flexible stop that usually works in mixed conditions."),
        ],
    },
    "hot": {
        "indoor_weight": 9.5,
        "outdoor_weight": 4.5,
        "scenic_weight": 2.5,
        "fit_note": "Better fit for hotter weather when climate-controlled stops are easier to handle.",
        "fallbacks": [
            ("Museums", "Useful in stronger heat when indoor time is easier to manage."),
            ("Aquariums or science centers", "Weather-protected option with more time indoors."),
            ("Shopping malls", "Practical fallback when you want air-conditioned movement."),
            ("Evening viewpoints", "Better later if the heat eases and you still want a scenic stop."),
        ],
    },
    "wet": {
        "indoor_weight": 10.0,
        "outdoor_weight": 2.5,
        "scenic_weight": 1.5,
        "fit_note": "Rain and rougher weather make covered or indoor stops the safer call.",
        "fallbacks": [
            ("Museums", "Stronger rainy-day fit when you want a stable indoor stop."),
            ("Theatres or arts centers", "Useful if you want a weather-protected plan."),
            ("Aquariums", "Good indoor fallback when outdoor movement is less appealing."),
            ("Shopping malls", "Practical covered option for rougher weather windows."),
        ],
    },
    "cold": {
        "indoor_weight": 8.0,
        "outdoor_weight": 4.5,
        "scenic_weight": 4.0,
        "fit_note": "Colder weather usually favors a shorter scenic stop or a stronger indoor visit.",
        "fallbacks": [
            ("Museums", "Reliable option when colder air makes longer outdoor time less appealing."),
            ("Historic landmarks", "Good if you want one memorable stop without staying outside too long."),
            ("Observation points", "Better when you want scenery in a shorter outdoor window."),
            ("Indoor attractions", "Useful when you want something simpler in colder conditions."),
        ],
    },
}


def _haversine_km(lat1, lon1, lat2, lon2):
    radius_km = 6371.0
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2) ** 2
    )
    return radius_km * (2 * math.atan2(math.sqrt(a), math.sqrt(1 - a)))


def _infer_scope(city_label):
    parts = [part.strip() for part in str(city_label or "").split(",") if part.strip()]
    if len(parts) >= 3:
        return "city", 22000
    if len(parts) == 2:
        return "region", 180000
    return "country", 260000


def _build_overpass_query(latitude, longitude, radius_m):
    return f"""
[out:json][timeout:3];
(
  nwr(around:{radius_m},{latitude},{longitude})["name"]["tourism"~"attraction|museum|gallery|aquarium|theme_park|zoo|viewpoint|artwork"];
  nwr(around:{radius_m},{latitude},{longitude})["name"]["leisure"~"park|garden|nature_reserve|water_park"];
  nwr(around:{radius_m},{latitude},{longitude})["name"]["amenity"~"theatre|cinema|arts_centre|library|planetarium"];
  nwr(around:{radius_m},{latitude},{longitude})["name"]["historic"~"castle|ruins|memorial|monument"];
  nwr(around:{radius_m},{latitude},{longitude})["name"]["natural"~"beach|peak"];
  nwr(around:{radius_m},{latitude},{longitude})["name"]["shop"="mall"];
);
out center tags;
""".strip()


@st.cache_data(show_spinner=False, ttl=21600)
def _fetch_place_candidates(latitude, longitude, radius_m):
    try:
        response = requests.post(
            OVERPASS_URL,
            data=_build_overpass_query(latitude, longitude, radius_m),
            headers={"Content-Type": "text/plain"},
            timeout=PLACE_LOOKUP_TIMEOUT_SECONDS,
        )
        response.raise_for_status()
        return response.json().get("elements", [])
    except (requests.RequestException, ValueError):
        return []


def _build_maps_link(place_name, city_label, latitude=None, longitude=None):
    if latitude is not None and longitude is not None:
        return f"https://www.google.com/maps/search/?api=1&query={latitude},{longitude}"
    query = quote_plus(f"{place_name} {city_label}".strip())
    return f"https://www.google.com/maps/search/?api=1&query={query}"


def _build_maps_search_link(query_text, city_label):
    query = quote_plus(f"{query_text} near {city_label}".strip())
    return f"https://www.google.com/maps/search/?api=1&query={query}"


def _clean_place_name(value):
    name = " ".join(str(value or "").split())
    if len(name) < 3:
        return ""
    lowered = name.lower()
    if any(fragment in lowered for fragment in GENERIC_NAME_FRAGMENTS):
        return ""
    return name


def _classify_place(tags):
    tourism = str(tags.get("tourism") or "")
    leisure = str(tags.get("leisure") or "")
    amenity = str(tags.get("amenity") or "")
    historic = str(tags.get("historic") or "")
    natural = str(tags.get("natural") or "")
    shop = str(tags.get("shop") or "")

    is_indoor = tourism in INDOOR_TOURISM_TAGS or amenity in INDOOR_AMENITY_TAGS or shop == "mall"
    is_outdoor = (
        tourism in OUTDOOR_TOURISM_TAGS
        or leisure in LEISURE_OUTDOOR_TAGS
        or historic in HISTORIC_TAGS
        or natural in SCENIC_NATURAL_TAGS
    )
    is_scenic = tourism == "viewpoint" or leisure in {"park", "garden", "nature_reserve"} or natural in SCENIC_NATURAL_TAGS

    if tourism == "museum":
        type_label = "Museum"
        descriptor = "Indoor cultural stop"
    elif tourism == "gallery":
        type_label = "Gallery"
        descriptor = "Indoor gallery stop"
    elif tourism == "aquarium":
        type_label = "Aquarium"
        descriptor = "Indoor attraction"
    elif tourism == "theme_park":
        type_label = "Theme Park"
        descriptor = "Larger attraction stop"
    elif tourism == "zoo":
        type_label = "Zoo"
        descriptor = "Outdoor animal park"
    elif tourism == "viewpoint":
        type_label = "Viewpoint"
        descriptor = "Scenic lookout"
    elif leisure == "park":
        type_label = "Park"
        descriptor = "Open-air park stop"
    elif leisure == "garden":
        type_label = "Garden"
        descriptor = "Scenic garden stop"
    elif amenity in {"theatre", "cinema", "arts_centre", "planetarium"}:
        type_label = "Indoor Venue"
        descriptor = "Weather-sheltered venue"
    elif shop == "mall":
        type_label = "Mall"
        descriptor = "Covered shopping stop"
    elif historic in HISTORIC_TAGS:
        type_label = "Historic Site"
        descriptor = "Historic landmark stop"
    elif natural in {"beach", "peak"}:
        type_label = "Scenic Spot"
        descriptor = "Scenic outdoor stop"
    else:
        type_label = "Landmark"
        descriptor = "Popular local stop"

    return {
        "type_label": type_label,
        "descriptor": descriptor,
        "is_indoor": is_indoor,
        "is_outdoor": is_outdoor,
        "is_scenic": is_scenic,
    }


def _score_place(classification, tags, distance_km, mode_key):
    mode = PLACE_MODE_CONFIG.get(mode_key, PLACE_MODE_CONFIG["mixed"])
    score = 0.0
    if classification["is_indoor"]:
        score += mode["indoor_weight"]
    if classification["is_outdoor"]:
        score += mode["outdoor_weight"]
    if classification["is_scenic"]:
        score += mode["scenic_weight"]
    if tags.get("wikipedia") or tags.get("wikidata"):
        score += 3.8
    if tags.get("website") or tags.get("contact:website"):
        score += 1.2
    if distance_km <= 3:
        score += 2.4
    elif distance_km <= 12:
        score += 1.4
    elif distance_km >= 90:
        score -= 1.5
    if len(str(tags.get("name") or "")) <= 4:
        score -= 1.0
    return score


def _format_scope_title(base_title, city_label):
    scope, _ = _infer_scope(city_label)
    lead = city_label.split(",")[0].strip() or city_label
    if scope == "city":
        return f"{base_title} near {lead}"
    if scope == "region":
        return f"{base_title} across {lead}"
    return f"{base_title} in {lead}"


def _build_fallback_items(city_label, mode_key, count):
    mode = PLACE_MODE_CONFIG.get(mode_key, PLACE_MODE_CONFIG["mixed"])
    items = []
    for title, body in mode["fallbacks"][:count]:
        items.append(
            {
                "title": _format_scope_title(title, city_label),
                "meta": "Maps search",
                "body": body,
                "action_label": "Open Maps",
                "action_url": _build_maps_search_link(title, city_label),
            }
        )
    return items


def get_local_place_recommendations(latitude, longitude, city_label, mode_key="mixed", max_items=4):
    if latitude is None or longitude is None or not city_label:
        return _build_fallback_items(city_label or "this area", mode_key, max_items)

    scope, radius_m = _infer_scope(city_label)
    if scope != "city":
        return _build_fallback_items(city_label, mode_key, max_items)

    raw_candidates = _fetch_place_candidates(latitude, longitude, radius_m)
    mode = PLACE_MODE_CONFIG.get(mode_key, PLACE_MODE_CONFIG["mixed"])

    places = []
    seen_names = set()
    for element in raw_candidates:
        tags = element.get("tags") or {}
        name = _clean_place_name(tags.get("name"))
        if not name:
            continue
        name_key = name.lower()
        if name_key in seen_names:
            continue

        center = element.get("center") or {}
        place_lat = center.get("lat", element.get("lat"))
        place_lon = center.get("lon", element.get("lon"))
        if place_lat is None or place_lon is None:
            continue

        classification = _classify_place(tags)
        distance_km = _haversine_km(latitude, longitude, float(place_lat), float(place_lon))
        score = _score_place(classification, tags, distance_km, mode_key)
        if score < 6.2:
            continue

        distance_note = (
            f"About {distance_km:.1f} km away."
            if distance_km < 100
            else "Broader-area highlight for this location."
        )
        places.append(
            {
                "title": name,
                "meta": classification["type_label"],
                "body": f"{classification['descriptor']}. {mode['fit_note']} {distance_note}",
                "action_label": "Open Maps",
                "action_url": _build_maps_link(name, city_label, float(place_lat), float(place_lon)),
                "_score": score,
                "_distance": distance_km,
            }
        )
        seen_names.add(name_key)

    ranked = sorted(
        places,
        key=lambda item: (-item["_score"], item["_distance"], item["title"].lower()),
    )

    cleaned = [
        {
            "title": item["title"],
            "meta": item["meta"],
            "body": item["body"],
            "action_label": item["action_label"],
            "action_url": item["action_url"],
        }
        for item in ranked[:max_items]
    ]

    if len(cleaned) < max_items:
        cleaned.extend(_build_fallback_items(city_label, mode_key, max_items - len(cleaned)))

    return cleaned[:max_items]
