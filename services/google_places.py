from __future__ import annotations

import difflib
import os
import re
from typing import Any

import requests


PLACES_TEXT_SEARCH_URL = "https://places.googleapis.com/v1/places:searchText"
PLACES_DETAILS_URL = "https://places.googleapis.com/v1/places/{place_id}"

DEFAULT_TIMEOUT = 30

TEXT_SEARCH_FIELDS = ",".join(
    [
        "places.id",
        "places.displayName",
        "places.formattedAddress",
        "places.location",
        "places.googleMapsUri",
        "places.primaryType",
        "places.businessStatus",
    ]
)

DETAILS_FIELDS = ",".join(
    [
        "id",
        "displayName",
        "formattedAddress",
        "location",
        "googleMapsUri",
        "primaryType",
        "businessStatus",
        "regularOpeningHours.weekdayDescriptions",
        "websiteUri",
        "nationalPhoneNumber",
        "rating",
        "userRatingCount",
    ]
)


CATEGORY_TYPE_HINTS = {
    "bubble-tea": {"bubble_tea_shop", "tea_house", "cafe"},
    "cafeteria": {"cafe", "coffee_shop"},
    "heladeria": {
        "ice_cream_shop",
        "dessert_shop",
        "pastry_shop",
        "deli",
        "candy_store",
        "store",
        "cafe",
    },
    "hamburgueseria": {
        "hamburger_restaurant",
        "fast_food_restaurant",
        "restaurant",
    },
    "pizza": {"pizza_restaurant", "restaurant"},
    "restaurante": {"restaurant", "meal_takeaway", "meal_delivery"},
    "escape-room": {"escape_room_center", "amusement_center"},
    "jump-park": {"amusement_center", "sports_complex"},
    "arcade": {"video_arcade", "amusement_center"},
    "bolera": {"bowling_alley", "amusement_center"},
    "cine": {"movie_theater"},
    "museo": {"museum", "art_museum"},
    "ropa": {
        "clothing_store",
        "womens_clothing_store",
        "mens_clothing_store",
        "childrens_clothing_store",
        "shoe_store",
        "store",
    },
    "sneakers": {"shoe_store", "sporting_goods_store", "store"},
    "manga": {"book_store", "comic_book_store", "store"},
    "regalos": {"gift_shop", "store", "candy_store"},
    "belleza": {"cosmetics_store", "beauty_salon", "store"},
    "compras": {"shopping_mall", "department_store", "store"},
    "actividad": {
        "amusement_center",
        "sports_complex",
        "museum",
        "movie_theater",
    },
    "nightlife": {"bar", "pub", "night_club"},
}


BAD_MATCH_TYPES_BY_CATEGORY = {
    "bubble-tea": {
        "restaurant",
        "japanese_restaurant",
        "sushi_restaurant",
        "meal_takeaway",
        "meal_delivery",
        "bar",
        "pub",
    },
    "escape-room": {
        "restaurant",
        "japanese_restaurant",
        "sushi_restaurant",
        "meal_takeaway",
        "meal_delivery",
        "cafe",
        "bar",
        "pub",
    },
    "jump-park": {
        "restaurant",
        "japanese_restaurant",
        "sushi_restaurant",
        "meal_takeaway",
        "meal_delivery",
        "cafe",
        "bar",
        "pub",
    },
    "arcade": {
        "restaurant",
        "meal_takeaway",
        "meal_delivery",
        "bar",
        "pub",
    },
    "bolera": {
        "restaurant",
        "meal_takeaway",
        "meal_delivery",
        "bar",
        "pub",
    },
    "cine": {
        "restaurant",
        "meal_takeaway",
        "meal_delivery",
        "bar",
        "pub",
    },
    "museo": {
        "restaurant",
        "meal_takeaway",
        "meal_delivery",
        "bar",
        "pub",
    },
    "ropa": {
        "restaurant",
        "meal_takeaway",
        "meal_delivery",
        "bar",
        "pub",
    },
    "sneakers": {
        "restaurant",
        "meal_takeaway",
        "meal_delivery",
        "bar",
        "pub",
    },
    "manga": {
        "restaurant",
        "meal_takeaway",
        "meal_delivery",
        "bar",
        "pub",
    },
    "regalos": {
        "restaurant",
        "meal_takeaway",
        "meal_delivery",
        "bar",
        "pub",
    },
    "belleza": {
        "restaurant",
        "meal_takeaway",
        "meal_delivery",
        "bar",
        "pub",
    },
    "compras": {
        "restaurant",
        "meal_takeaway",
        "meal_delivery",
        "bar",
        "pub",
    },
}


def _api_key() -> str:
    key = (os.getenv("GOOGLE_MAPS_API_KEY") or "").strip()
    if not key:
        raise RuntimeError("Falta GOOGLE_MAPS_API_KEY")
    return key


def _headers(field_mask: str) -> dict[str, str]:
    return {
        "Content-Type": "application/json",
        "X-Goog-Api-Key": _api_key(),
        "X-Goog-FieldMask": field_mask,
    }


def _clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _norm(value: Any) -> str:
    value = _clean(value).lower()
    value = (
        value.replace("á", "a")
        .replace("é", "e")
        .replace("í", "i")
        .replace("ó", "o")
        .replace("ú", "u")
        .replace("ü", "u")
        .replace("ñ", "n")
    )
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _tokens(value: Any) -> set[str]:
    ignored = {
        "bilbao",
        "bizkaia",
        "vizcaya",
        "kalea",
        "calle",
        "avenida",
        "avda",
        "plaza",
        "local",
        "bajo",
        "the",
        "and",
        "de",
        "del",
        "la",
        "el",
        "los",
        "las",
        "y",
        "en",
        "shop",
        "store",
        "center",
        "centre",
    }
    return {x for x in _norm(value).split() if len(x) >= 3 and x not in ignored}


def _number_tokens(value: Any) -> set[str]:
    return set(re.findall(r"\d+", _norm(value)))


def _first_distinctive_token(value: Any) -> str:
    generic = {
        "moda",
        "infantil",
        "complementos",
        "ropa",
        "tienda",
        "zapatos",
        "calzado",
        "fashion",
        "store",
        "shop",
        "woman",
        "women",
        "men",
        "kids",
        "actual",
        "tallas",
        "grandes",
        "pequenas",
        "pequeñas",
        "delicados",
        "boutique",
        "clothing",
    }

    for token in _tokens(value):
        if token not in generic and not token.isdigit():
            return token

    return ""


def _similarity(a: Any, b: Any) -> float:
    na = _norm(a)
    nb = _norm(b)
    if not na or not nb:
        return 0.0
    return difflib.SequenceMatcher(None, na, nb).ratio()


def _token_overlap(a: Any, b: Any) -> float:
    ta = _tokens(a)
    tb = _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(1, len(ta))


def _location_bias() -> dict[str, Any]:
    return {
        "circle": {
            "center": {"latitude": 43.2630, "longitude": -2.9350},
            "radius": 12000.0,
        }
    }


def _category_hints(category: str) -> set[str]:
    return CATEGORY_TYPE_HINTS.get(_clean(category).lower(), set())


def _bad_types_for_category(category: str) -> set[str]:
    return BAD_MATCH_TYPES_BY_CATEGORY.get(_clean(category).lower(), set())


def _type_compatibility_score(category: str, primary_type: str) -> float:
    category = _clean(category).lower()
    primary_type = _clean(primary_type).lower()

    if not primary_type:
        return 0.0

    bad_types = _bad_types_for_category(category)
    if primary_type in bad_types:
        return -8.0

    if "restaurant" in primary_type and category in {
        "bubble-tea",
        "cafeteria",
        "heladeria",
        "escape-room",
        "jump-park",
        "arcade",
        "bolera",
        "cine",
        "museo",
        "ropa",
        "sneakers",
        "manga",
        "regalos",
        "belleza",
        "compras",
    }:
        return -6.0

    hints = _category_hints(category)
    if primary_type in hints:
        return 4.0

    if category == "bubble-tea" and primary_type in {
        "bubble_tea_shop",
        "tea_house",
        "cafe",
    }:
        return 5.0

    if category == "heladeria" and primary_type in {
        "ice_cream_shop",
        "dessert_shop",
        "pastry_shop",
        "deli",
        "candy_store",
        "store",
        "cafe",
    }:
        return 3.0

    if category in {"cafeteria", "heladeria"} and primary_type in {
        "cafe",
        "dessert_shop",
        "pastry_shop",
        "store",
    }:
        return 2.0

    if category in {"actividad", "escape-room", "jump-park", "arcade", "bolera"} and primary_type in {
        "amusement_center",
        "sports_complex",
        "movie_theater",
        "museum",
        "bowling_alley",
        "escape_room_center",
    }:
        return 3.0

    if category in {"ropa", "sneakers", "manga", "regalos", "belleza", "compras"} and primary_type in {
        "store",
        "shopping_mall",
        "department_store",
        "clothing_store",
        "womens_clothing_store",
        "mens_clothing_store",
        "childrens_clothing_store",
        "shoe_store",
        "book_store",
        "gift_shop",
    }:
        return 2.0

    return 0.0


def _is_closed_permanently(place: dict) -> bool:
    return _clean(place.get("businessStatus", "")).upper() == "CLOSED_PERMANENTLY"


def _has_address_signal(item: dict) -> bool:
    address = _clean(item.get("direccion", ""))
    if not address:
        return False

    low = address.lower()
    if low in {"bilbao", "bizkaia", "vizcaya", "centro de bilbao"}:
        return False

    return bool(re.search(r"\d", low)) or any(
        x in low
        for x in [
            "kalea",
            "calle",
            "plaza",
            "avenida",
            "avda",
            "alameda",
            "camino",
            "etorbidea",
            "etorb.",
            "480",
        ]
    )


def build_text_query(item: dict) -> str:
    nombre = _clean(item.get("nombre", ""))
    direccion = _clean(item.get("direccion", ""))
    barrio = _clean(item.get("barrio", ""))
    categoria = _clean(item.get("categoria", ""))

    pieces = [nombre]

    if categoria and categoria.lower() not in nombre.lower():
        pieces.append(categoria)

    if direccion and _has_address_signal(item):
        pieces.append(direccion)
    elif barrio:
        pieces.append(barrio)

    pieces.append("Bilbao")
    return ", ".join([x for x in pieces if x])


def search_text(item: dict, max_results: int = 5) -> list[dict]:
    payload = {
        "textQuery": build_text_query(item),
        "languageCode": "es",
        "locationBias": _location_bias(),
        "pageSize": max_results,
    }

    resp = requests.post(
        PLACES_TEXT_SEARCH_URL,
        headers=_headers(TEXT_SEARCH_FIELDS),
        json=payload,
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    return data.get("places", []) or []


def get_place_details(place_id: str) -> dict:
    url = PLACES_DETAILS_URL.format(place_id=place_id)
    resp = requests.get(
        url,
        headers=_headers(DETAILS_FIELDS),
        timeout=DEFAULT_TIMEOUT,
    )
    resp.raise_for_status()
    return resp.json()


def _candidate_score(item: dict, cand: dict) -> tuple[float, dict]:
    wanted_name = _clean(item.get("nombre", ""))
    wanted_address = _clean(item.get("direccion", ""))
    wanted_barrio = _clean(item.get("barrio", ""))
    wanted_category = _clean(item.get("categoria", ""))

    cand_name = _clean((cand.get("displayName") or {}).get("text", ""))
    cand_addr = _clean(cand.get("formattedAddress", ""))
    cand_type = _clean(cand.get("primaryType", ""))

    if _is_closed_permanently(cand):
        return -999.0, {
            "name_score": 0.0,
            "token_score": 0.0,
            "addr_score": 0.0,
            "type_score": -999.0,
        }

    name_score = _similarity(wanted_name, cand_name)
    token_score = _token_overlap(wanted_name, cand_name)
    addr_score = _similarity(wanted_address, cand_addr) if wanted_address else 0.0
    type_score = _type_compatibility_score(wanted_category, cand_type)

    score = 0.0
    score += name_score * 10.0
    score += token_score * 5.0
    score += addr_score * 3.0
    score += type_score

    if wanted_barrio and wanted_barrio.lower() in cand_addr.lower():
        score += 0.8

    if "bilbao" in cand_addr.lower():
        score += 0.5

    return score, {
        "name_score": name_score,
        "token_score": token_score,
        "addr_score": addr_score,
        "type_score": type_score,
    }


def choose_best_candidate(item: dict, candidates: list[dict]) -> dict | None:
    if not candidates:
        return None

    wanted_name = _clean(item.get("nombre", ""))
    wanted_category = _clean(item.get("categoria", ""))

    ranked: list[tuple[float, dict, dict]] = []

    for cand in candidates:
        score, debug = _candidate_score(item, cand)
        if score <= -100:
            continue
        ranked.append((score, cand, debug))

    if not ranked:
        return None

    ranked.sort(key=lambda x: x[0], reverse=True)
    best_score, best, debug = ranked[0]

    best_name = _clean((best.get("displayName") or {}).get("text", ""))
    best_type = _clean(best.get("primaryType", ""))

    type_score = _type_compatibility_score(wanted_category, best_type)
    best_similarity = _similarity(wanted_name, best_name)
    best_token_overlap = _token_overlap(wanted_name, best_name)

    wanted_numbers = _number_tokens(wanted_name)
    best_numbers = _number_tokens(best_name)

    if wanted_numbers and not wanted_numbers.issubset(best_numbers):
        return None

    wanted_tokens = _tokens(wanted_name)
    best_tokens = _tokens(best_name)

    first_distinctive = _first_distinctive_token(wanted_name)
    if first_distinctive:
        best_norm = _norm(best_name)
        if first_distinctive not in best_tokens and first_distinctive not in best_norm:
            return None

    if len(wanted_tokens) == 1:
        only_token = next(iter(wanted_tokens))
        best_norm = _norm(best_name)

        if only_token not in best_tokens and only_token not in best_norm:
            return None

        if best_similarity < 0.75 and best_token_overlap < 1.0:
            return None

    strict_categories = {
        "bubble-tea",
        "escape-room",
        "jump-park",
        "arcade",
        "bolera",
        "cine",
        "museo",
        "ropa",
        "sneakers",
        "manga",
        "regalos",
        "belleza",
        "compras",
    }

    if wanted_category in strict_categories:
        if best_similarity < 0.68 and best_token_overlap < 0.50:
            return None
    else:
        if best_similarity < 0.62 and best_token_overlap < 0.40:
            return None

    if type_score <= -5.0:
        return None

    if wanted_category == "bubble-tea":
        if best_type not in {"bubble_tea_shop", "tea_house", "cafe"}:
            return None
        best_norm = _norm(best_name)
        if best_token_overlap < 0.50 and "bubble" not in best_norm and "tea" not in best_norm:
            return None

    if wanted_category == "escape-room":
        if best_type not in {"escape_room_center", "amusement_center"}:
            return None

    if wanted_category == "jump-park":
        if best_type not in {"amusement_center", "sports_complex"}:
            return None

    if best_score < 7.0:
        return None

    return best


def enrich_item_with_google(item: dict) -> dict:
    row = dict(item)

    candidates = search_text(row)
    best = choose_best_candidate(row, candidates)

    if not best:
        row["google_enriched"] = False
        row["google_match_status"] = "no_match"
        return row

    place_id = best.get("id", "")
    if not place_id:
        row["google_enriched"] = False
        row["google_match_status"] = "missing_place_id"
        return row

    details = get_place_details(place_id)

    if _is_closed_permanently(details):
        row["google_enriched"] = False
        row["google_match_status"] = "closed_permanently"
        return row

    display_name = _clean((details.get("displayName") or {}).get("text", ""))
    formatted_address = _clean(details.get("formattedAddress", ""))
    google_maps_uri = _clean(details.get("googleMapsUri", ""))
    primary_type = _clean(details.get("primaryType", ""))
    business_status = _clean(details.get("businessStatus", ""))
    website_uri = _clean(details.get("websiteUri", ""))
    phone = _clean(details.get("nationalPhoneNumber", ""))

    location = details.get("location", {}) or {}
    lat = location.get("latitude")
    lon = location.get("longitude")

    opening = details.get("regularOpeningHours", {}) or {}
    weekday = opening.get("weekdayDescriptions", []) or []
    horario = " | ".join([_clean(x) for x in weekday if _clean(x)])

    row["google_place_id"] = place_id
    row["google_display_name"] = display_name
    row["google_formatted_address"] = formatted_address
    row["google_maps_uri"] = google_maps_uri
    row["google_primary_type"] = primary_type
    row["google_business_status"] = business_status
    row["google_website_uri"] = website_uri
    row["google_phone"] = phone
    row["google_rating"] = details.get("rating")
    row["google_user_rating_count"] = details.get("userRatingCount")
    row["google_opening_hours_text"] = horario
    row["google_enriched"] = True
    row["google_match_status"] = "ok"

    if formatted_address:
        row["direccion"] = formatted_address

    if lat is not None and lon is not None:
        row["latitud"] = str(lat)
        row["longitud"] = str(lon)

    if google_maps_uri:
        row["maps_url"] = google_maps_uri

    if horario and not _clean(row.get("horario", "")):
        row["horario"] = horario

    if website_uri and not _clean(row.get("url", "")):
        row["url"] = website_uri

    ubicacion_actual = _clean(row.get("ubicacion", ""))
    if not ubicacion_actual or ubicacion_actual.lower() in {"bilbao", "bizkaia", "vizcaya"}:
        row["ubicacion"] = display_name or row.get("ubicacion", "")

    return row
