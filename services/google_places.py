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


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _norm(value: str) -> str:
    value = _clean(value).lower()
    value = value.replace("á", "a").replace("é", "e").replace("í", "i").replace("ó", "o").replace("ú", "u")
    value = re.sub(r"[^a-z0-9\s]", " ", value)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def _similarity(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return difflib.SequenceMatcher(None, _norm(a), _norm(b)).ratio()


def _location_bias() -> dict[str, Any]:
    return {
        "circle": {
            "center": {"latitude": 43.2630, "longitude": -2.9350},
            "radius": 7000.0,
        }
    }


def build_text_query(item: dict) -> str:
    nombre = _clean(item.get("nombre", ""))
    direccion = _clean(item.get("direccion", ""))
    barrio = _clean(item.get("barrio", ""))
    categoria = _clean(item.get("categoria", ""))

    pieces = [nombre]

    if categoria and categoria not in nombre.lower():
        pieces.append(categoria)

    if direccion:
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


def choose_best_candidate(item: dict, candidates: list[dict]) -> dict | None:
    if not candidates:
        return None

    wanted_name = _clean(item.get("nombre", ""))
    wanted_address = _clean(item.get("direccion", ""))
    wanted_barrio = _clean(item.get("barrio", ""))

    ranked: list[tuple[float, dict]] = []

    for cand in candidates:
        cand_name = _clean((cand.get("displayName") or {}).get("text", ""))
        cand_addr = _clean(cand.get("formattedAddress", ""))

        score = 0.0
        score += _similarity(wanted_name, cand_name) * 8.0

        if wanted_address:
            score += _similarity(wanted_address, cand_addr) * 4.0

        if wanted_barrio and wanted_barrio.lower() in cand_addr.lower():
            score += 1.5

        if "Bilbao" in cand_addr:
            score += 1.0

        ranked.append((score, cand))

    ranked.sort(key=lambda x: x[0], reverse=True)

    best_score, best = ranked[0]
    if best_score < 3.0:
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

    if not _clean(row.get("ubicacion", "")) or _clean(row.get("ubicacion", "")).lower() in {"bilbao", "bizkaia"}:
        row["ubicacion"] = display_name or row.get("ubicacion", "")

    return row