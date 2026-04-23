from __future__ import annotations

import hashlib
import json
import re
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from jobs.common import FUENTES_DIR, fetch_url, update_sync, write_json

OUT_FILE = FUENTES_DIR / "lugares_turismo.json"

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

BILBAO_LAT = 43.2630
BILBAO_LON = -2.9350
RADIUS_METERS = 7000

TEEN_UNSAFE_WORDS = {
    "pub", "cocktail", "whisky", "whiskey", "vodka", "rum", "gin",
    "discoteca", "nightclub", "casino", "apuestas", "bet",
}


def clean(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def stable_id(*parts: str) -> str:
    raw = "||".join(parts)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


def teen_safe(name: str, desc: str = "") -> bool:
    txt = clean(f"{name} {desc}").lower()
    return not any(x in txt for x in TEEN_UNSAFE_WORDS)


def compose_address(tags: dict) -> str:
    parts = [
        tags.get("addr:street", ""),
        tags.get("addr:housenumber", ""),
        tags.get("addr:postcode", ""),
        tags.get("addr:city", ""),
    ]
    return clean(" ".join([p for p in parts if p]))


def infer_barrio(tags: dict, address: str) -> str:
    for key in ("addr:suburb", "addr:neighbourhood", "addr:district"):
        if clean(tags.get(key, "")):
            return clean(tags.get(key, ""))
    if "deusto" in address.lower():
        return "Deusto"
    if "indautxu" in address.lower():
        return "Indautxu"
    if "casco viejo" in address.lower():
        return "Casco Viejo"
    return "Bilbao"


def osm_specific_type(tags: dict) -> str | None:
    amenity = clean(tags.get("amenity", "")).lower()
    tourism = clean(tags.get("tourism", "")).lower()
    leisure = clean(tags.get("leisure", "")).lower()
    shop = clean(tags.get("shop", "")).lower()
    name = clean(tags.get("name", "")).lower()
    cuisine = clean(tags.get("cuisine", "")).lower()
    txt = f"{name} {cuisine}"

    if amenity == "ice_cream":
        return "heladeria"
    if amenity == "cafe":
        if "bubble" in txt or "boba" in txt:
            return "bubble-tea"
        return "cafeteria"
    if amenity in {"restaurant", "fast_food"}:
        if "burger" in txt or "hamburg" in txt:
            return "hamburgueseria"
        if "pizza" in txt or "pizzer" in txt:
            return "pizza"
        return "restaurante"

    if tourism in {"museum", "gallery"}:
        return "museo"
    if amenity == "cinema":
        return "cine"

    if leisure == "bowling_alley":
        return "bolera"
    if leisure == "escape_game":
        return "escape-room"
    if leisure == "amusement_arcade":
        return "arcade"
    if leisure == "trampoline_park":
        return "jump-park"
    if leisure == "sports_centre":
        return "actividad"

    if shop == "clothes":
        return "ropa"
    if shop in {"shoes", "sports"}:
        if any(x in name for x in ["sneaker", "foot", "shoe"]):
            return "sneakers"
        return "ropa"
    if shop in {"books", "comics"}:
        if any(x in name for x in ["manga", "comic", "anime"]):
            return "manga"
        return "regalos"
    if shop in {"gift", "jewelry", "bag"}:
        return "regalos"
    if shop in {"beauty", "cosmetics", "perfumery"}:
        return "belleza"
    if shop in {"mall", "department_store"}:
        return "compras"

    return None


def overpass_query() -> str:
    return f"""
[out:json][timeout:60];
(
  node["amenity"~"restaurant|cafe|fast_food|ice_cream|cinema"](around:{RADIUS_METERS},{BILBAO_LAT},{BILBAO_LON});
  way["amenity"~"restaurant|cafe|fast_food|ice_cream|cinema"](around:{RADIUS_METERS},{BILBAO_LAT},{BILBAO_LON});
  relation["amenity"~"restaurant|cafe|fast_food|ice_cream|cinema"](around:{RADIUS_METERS},{BILBAO_LAT},{BILBAO_LON});

  node["tourism"~"museum|gallery|attraction"](around:{RADIUS_METERS},{BILBAO_LAT},{BILBAO_LON});
  way["tourism"~"museum|gallery|attraction"](around:{RADIUS_METERS},{BILBAO_LAT},{BILBAO_LON});
  relation["tourism"~"museum|gallery|attraction"](around:{RADIUS_METERS},{BILBAO_LAT},{BILBAO_LON});

  node["leisure"~"bowling_alley|escape_game|sports_centre|amusement_arcade|trampoline_park"](around:{RADIUS_METERS},{BILBAO_LAT},{BILBAO_LON});
  way["leisure"~"bowling_alley|escape_game|sports_centre|amusement_arcade|trampoline_park"](around:{RADIUS_METERS},{BILBAO_LAT},{BILBAO_LON});
  relation["leisure"~"bowling_alley|escape_game|sports_centre|amusement_arcade|trampoline_park"](around:{RADIUS_METERS},{BILBAO_LAT},{BILBAO_LON});

  node["shop"](around:{RADIUS_METERS},{BILBAO_LAT},{BILBAO_LON});
  way["shop"](around:{RADIUS_METERS},{BILBAO_LAT},{BILBAO_LON});
  relation["shop"](around:{RADIUS_METERS},{BILBAO_LAT},{BILBAO_LON});
);
out center tags;
""".strip()


def fetch_overpass() -> list[dict]:
    query = overpass_query()
    items = []
    seen = set()
    last_exc = None

    for endpoint in OVERPASS_ENDPOINTS:
        try:
            data = urlencode({"data": query}).encode("utf-8")
            req = Request(
                endpoint,
                data=data,
                headers={
                    "Content-Type": "application/x-www-form-urlencoded",
                    "User-Agent": "TeenagerBilbao/1.0",
                },
                method="POST",
            )
            with urlopen(req, timeout=90) as resp:
                payload = json.loads(resp.read().decode("utf-8", errors="ignore"))

            for el in payload.get("elements", []):
                tags = el.get("tags", {})
                name = clean(tags.get("name", ""))
                if not name:
                    continue

                tipo = osm_specific_type(tags)
                if not tipo:
                    continue

                desc = clean(" · ".join([
                    tags.get("cuisine", ""),
                    tags.get("shop", ""),
                    tags.get("amenity", ""),
                    tags.get("tourism", ""),
                    tags.get("leisure", ""),
                ]))
                if not teen_safe(name, desc):
                    continue

                lat = el.get("lat") or (el.get("center") or {}).get("lat")
                lon = el.get("lon") or (el.get("center") or {}).get("lon")
                url = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}" if lat and lon else ""

                address = compose_address(tags)
                barrio = infer_barrio(tags, address)
                horario = clean(tags.get("opening_hours", ""))

                key = (tipo, name.lower(), url.lower())
                if key in seen:
                    continue
                seen.add(key)

                items.append({
                    "id": f"lug-{stable_id(tipo, name, url)}",
                    "fuente": "OpenStreetMap",
                    "tipo": tipo,
                    "nombre": name,
                    "descripcion": desc[:500],
                    "zona": barrio,
                    "direccion": address,
                    "precio": "",
                    "horario": horario,
                    "url": url,
                })

            if items:
                return items

        except Exception as exc:
            last_exc = exc
            time.sleep(1.5)

    if last_exc:
        raise last_exc

    return []


def main():
    items = fetch_overpass()

    if not items:
        update_sync("Lugares Turismo", 0, status="error", note="Sin resultados válidos en OSM")
        raise RuntimeError("No se pudieron obtener lugares válidos")

    write_json(OUT_FILE, items)
    update_sync("Lugares Turismo", len(items), note="OSM Bilbao orientado a adolescentes")
    print(f"Lugares Turismo: {len(items)} lugares")


if __name__ == "__main__":
    main()
