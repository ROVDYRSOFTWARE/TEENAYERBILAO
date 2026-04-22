from __future__ import annotations
import hashlib
import re
import time
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup

from jobs.common import FUENTES_DIR, fetch_url, read_json, update_sync, write_json

URLS = [
    ("restaurante", "https://www.bilbaoturismo.net/BilbaoTurismo/en/restaurantes"),
    ("nightlife", "https://www.bilbaoturismo.net/BilbaoTurismo/en/my-bilbao/nightlife"),
    ("actividad", "https://bilbaoturismo.net/BilbaoTurismo/en/unique-activities"),
]

OUT_FILE = FUENTES_DIR / "lugares_turismo.json"

BAD_TEXTS = {
    "to see", "about us", "accomodation", "accommodation", "aviso legal",
    "legal notice", "interesting areas", "museums and theaters",
    "old quarter and the ensanche", "routes and panoramic views", "new bilbao",
    "art en plein air", "transporter bridge-world heritage", "transporter bridge",
    "restaurants", "nightlife", "unique activities", "highlights", "home",
    "newsletter", "contact", "site map", "share", "facebook", "twitter", "mail",
    "for you", "cuisine", "companies", "tourists", "trade", "press",
    "more information", "more info", "read more", "see more", "discover",
    "agenda", "bilbao", "activities", "1", "2", "3", "4",
}

BAD_URL_PARTS = [
    "/aviso-legal", "/legal", "/contact", "/newsletter", "/site-map",
    "/accomodation", "/accommodation", "/historia", "/arte-al-aire-libre",
    "/anillo-verde", "/the-world-showcase-of-architecture", "/otros-museos",
    "/bilbao-en-1--2-y-3-dias", "/guggenheim-museum-bilbao_2", "/espacio-gran-via",
]

GOOD_ACTIVITY_HINTS = ["/unique-activities/"]
GOOD_RESTAURANT_HINTS = ["/restaurantes/"]

NIGHTLIFE_BLACKLIST = {
    "autocaravaning", "albergue", "apartamento", "arriaga", "arte y cultura",
    "basque design", "bilbao bizkaia card", "bilbobentura", "azkuna zentroa",
    "agenda", "artxanda", "artxanda bilbao", "about us", "accomodation",
    "accommodation",
}

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

BILBAO_LAT = 43.2630
BILBAO_LON = -2.9350
RADIUS_METERS = 6500


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def stable_id(*parts: str) -> str:
    raw = "||".join(parts)
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:12]


def valid_name(text: str) -> bool:
    t = clean(text)
    if not t:
        return False

    low = t.lower()

    if low in BAD_TEXTS:
        return False

    if len(t) < 4 or len(t) > 90:
        return False

    if t.startswith("http"):
        return False

    return True


def valid_url(category: str, url: str) -> bool:
    u = url.lower()

    for bad in BAD_URL_PARTS:
        if bad in u:
            return False

    if category == "actividad":
        return any(x in u for x in GOOD_ACTIVITY_HINTS)

    if category == "restaurante":
        return any(x in u for x in GOOD_RESTAURANT_HINTS)

    if category == "nightlife":
        return "/nightlife" in u

    return True


def nightlife_name_ok(name: str) -> bool:
    low = name.lower()

    if low in NIGHTLIFE_BLACKLIST:
        return False

    if len(name.split()) == 1 and len(name) < 7:
        return False

    generic_bits = [
        "arte", "cultura", "card", "design", "apartamento",
        "albergue", "autocaravaning",
    ]
    if any(bit in low for bit in generic_bits):
        return False

    return True


def add_item(items: list[dict], seen: set, category: str, name: str, url: str, desc: str = ""):
    name = clean(name)
    desc = clean(desc)

    if not valid_name(name):
        return

    if url and not valid_url(category, url):
        return

    if category == "nightlife" and not nightlife_name_ok(name):
        return

    key = (category, name.lower(), (url or "").lower())
    if key in seen:
        return

    seen.add(key)
    items.append(
        {
            "id": f"lug-{stable_id(category, name, url or '')}",
            "fuente": "Bilbao Turismo" if url else "OpenStreetMap",
            "tipo": category,
            "nombre": name,
            "descripcion": desc[:500],
            "zona": "Bilbao",
            "direccion": "",
            "precio": "",
            "url": url or "",
        }
    )


def parse_restaurantes(soup: BeautifulSoup, base_url: str) -> list[dict]:
    items = []
    seen = set()

    for a in soup.select("a[href]"):
        name = clean(a.get_text(" ", strip=True))
        href = clean(a.get("href", ""))
        if not href:
            continue

        url = urljoin(base_url, href)
        if "bilbaoturismo.net" not in urlparse(url).netloc:
            continue

        add_item(items, seen, "restaurante", name, url)

    return items


def parse_unique_activities(soup: BeautifulSoup, base_url: str) -> list[dict]:
    items = []
    seen = set()

    for a in soup.select("a[href]"):
        name = clean(a.get_text(" ", strip=True))
        href = clean(a.get("href", ""))
        if not href:
            continue

        url = urljoin(base_url, href)
        if "bilbaoturismo.net" not in urlparse(url).netloc:
            continue

        add_item(items, seen, "actividad", name, url)

    return items


def parse_nightlife(soup: BeautifulSoup, base_url: str) -> list[dict]:
    items = []
    seen = set()

    for img in soup.select("img[alt]"):
        name = clean(img.get("alt", "")).replace("Image:", "").strip()
        add_item(items, seen, "nightlife", name, base_url)

    for a in soup.select("a[href]"):
        name = clean(a.get_text(" ", strip=True))
        href = clean(a.get("href", ""))
        if not href:
            continue

        url = urljoin(base_url, href)
        if "bilbaoturismo.net" not in urlparse(url).netloc:
            continue

        add_item(items, seen, "nightlife", name, url)

    return items


def fetch_with_retries(url: str, attempts: int = 3, pause: float = 2.0) -> str:
    last_exc = None
    for _ in range(attempts):
        try:
            return fetch_url(url, timeout=60)
        except Exception as exc:
            last_exc = exc
            time.sleep(pause)
    raise last_exc


def overpass_query() -> str:
    return f"""
[out:json][timeout:60];
(
  node["amenity"~"restaurant|cafe|bar|pub|fast_food|ice_cream|nightclub"](around:{RADIUS_METERS},{BILBAO_LAT},{BILBAO_LON});
  way["amenity"~"restaurant|cafe|bar|pub|fast_food|ice_cream|nightclub"](around:{RADIUS_METERS},{BILBAO_LAT},{BILBAO_LON});
  relation["amenity"~"restaurant|cafe|bar|pub|fast_food|ice_cream|nightclub"](around:{RADIUS_METERS},{BILBAO_LAT},{BILBAO_LON});

  node["tourism"~"museum|gallery|attraction"](around:{RADIUS_METERS},{BILBAO_LAT},{BILBAO_LON});
  way["tourism"~"museum|gallery|attraction"](around:{RADIUS_METERS},{BILBAO_LAT},{BILBAO_LON});
  relation["tourism"~"museum|gallery|attraction"](around:{RADIUS_METERS},{BILBAO_LAT},{BILBAO_LON});

  node["amenity"~"cinema|theatre|arts_centre"](around:{RADIUS_METERS},{BILBAO_LAT},{BILBAO_LON});
  way["amenity"~"cinema|theatre|arts_centre"](around:{RADIUS_METERS},{BILBAO_LAT},{BILBAO_LON});
  relation["amenity"~"cinema|theatre|arts_centre"](around:{RADIUS_METERS},{BILBAO_LAT},{BILBAO_LON});

  node["leisure"~"bowling_alley|escape_game|sports_centre"](around:{RADIUS_METERS},{BILBAO_LAT},{BILBAO_LON});
  way["leisure"~"bowling_alley|escape_game|sports_centre"](around:{RADIUS_METERS},{BILBAO_LAT},{BILBAO_LON});
  relation["leisure"~"bowling_alley|escape_game|sports_centre"](around:{RADIUS_METERS},{BILBAO_LAT},{BILBAO_LON});
);
out center tags;
""".strip()


def osm_category(tags: dict) -> str:
    amenity = (tags.get("amenity") or "").lower()
    tourism = (tags.get("tourism") or "").lower()
    leisure = (tags.get("leisure") or "").lower()

    if amenity in {"bar", "pub", "nightclub"}:
        return "nightlife"
    if amenity in {"restaurant", "cafe", "fast_food", "ice_cream"}:
        return "restaurante"
    if tourism in {"museum", "gallery", "attraction"}:
        return "actividad"
    if amenity in {"cinema", "theatre", "arts_centre"}:
        return "actividad"
    if leisure in {"bowling_alley", "escape_game", "sports_centre"}:
        return "actividad"

    return "actividad"


def compose_address(tags: dict) -> str:
    parts = [
        tags.get("addr:street", ""),
        tags.get("addr:housenumber", ""),
        tags.get("addr:postcode", ""),
        tags.get("addr:city", ""),
    ]
    return clean(" ".join([p for p in parts if p]))


def fetch_osm_fallback() -> list[dict]:
    query = overpass_query()
    items = []
    seen = set()
    last_exc = None

    for endpoint in OVERPASS_ENDPOINTS:
        try:
            response = requests.post(endpoint, data={"data": query}, timeout=90)
            response.raise_for_status()
            payload = response.json()
            elements = payload.get("elements", [])

            for el in elements:
                tags = el.get("tags", {})
                name = clean(tags.get("name", ""))
                if not valid_name(name):
                    continue

                category = osm_category(tags)
                if category == "nightlife" and not nightlife_name_ok(name):
                    continue

                lat = el.get("lat") or (el.get("center") or {}).get("lat")
                lon = el.get("lon") or (el.get("center") or {}).get("lon")
                if lat and lon:
                    url = f"https://www.openstreetmap.org/?mlat={lat}&mlon={lon}#map=18/{lat}/{lon}"
                else:
                    url = ""

                address = compose_address(tags)
                desc = clean(
                    " · ".join(
                        [
                            tags.get("cuisine", ""),
                            tags.get("tourism", ""),
                            tags.get("amenity", ""),
                            tags.get("leisure", ""),
                        ]
                    )
                )

                key = (category, name.lower(), url.lower())
                if key in seen:
                    continue
                seen.add(key)

                items.append(
                    {
                        "id": f"lug-{stable_id(category, name, url)}",
                        "fuente": "OpenStreetMap",
                        "tipo": category,
                        "nombre": name,
                        "descripcion": desc[:500],
                        "zona": tags.get("addr:suburb", "") or tags.get("addr:neighbourhood", "") or "Bilbao",
                        "direccion": address,
                        "precio": "",
                        "url": url,
                    }
                )

            if items:
                return items

        except Exception as exc:
            last_exc = exc

    if last_exc:
        raise last_exc

    return items


def main():
    lugares = []

    for category, url in URLS:
        try:
            html = fetch_with_retries(url)
            soup = BeautifulSoup(html, "html.parser")

            if category == "restaurante":
                lugares.extend(parse_restaurantes(soup, url))
            elif category == "nightlife":
                lugares.extend(parse_nightlife(soup, url))
            else:
                lugares.extend(parse_unique_activities(soup, url))

        except Exception as exc:
            print(f"Aviso: no se pudo procesar {url}: {exc}")

    unique = []
    seen = set()
    for item in lugares:
        key = (item["tipo"], item["nombre"].lower(), item["url"].lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    # fallback a OSM si Bilbao Turismo falla o no devuelve nada
    if not unique:
        print("Bilbao Turismo sin resultados válidos. Intentando fallback OpenStreetMap...")
        try:
            unique = fetch_osm_fallback()
            print(f"Fallback OSM: {len(unique)} lugares")
        except Exception as exc:
            print(f"Fallback OSM también falló: {exc}")

    previous = read_json(OUT_FILE, [])
    if not unique and previous:
        update_sync("Lugares Turismo", len(previous), status="ok", note="Se conserva último snapshot válido")
        print(f"Lugares Turismo: 0 nuevos, se conserva snapshot anterior ({len(previous)})")
        return

    if not unique and not previous:
        update_sync("Lugares Turismo", 0, status="error", note="Todas las fuentes fallaron")
        raise RuntimeError("No se pudieron obtener lugares de ninguna fuente")

    write_json(OUT_FILE, unique)
    update_sync("Lugares Turismo", len(unique), note="Bilbao Turismo + fallback OSM")
    print(f"Lugares Turismo: {len(unique)} lugares")


if __name__ == "__main__":
    main()