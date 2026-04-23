from __future__ import annotations

import hashlib
import json
import re
import time
from pathlib import Path
from urllib.parse import urlencode, urljoin, urlparse
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup

from jobs.common import FUENTES_DIR, fetch_url, read_json, update_sync, write_json

URLS = [
    ("restaurante", "https://www.bilbaoturismo.net/BilbaoTurismo/en/restaurantes"),
    ("actividad", "https://bilbaoturismo.net/BilbaoTurismo/en/unique-activities"),
]

OUT_FILE = FUENTES_DIR / "lugares_turismo.json"
SEED_FILE = Path(__file__).resolve().parents[1] / "data" / "seed_lugares.json"

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

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

BILBAO_LAT = 43.2630
BILBAO_LON = -2.9350
RADIUS_METERS = 7000

SHOP_TYPES = {
    "clothes", "shoes", "sports", "books", "comics", "gift",
    "perfumery", "cosmetics", "beauty", "bag", "mall",
    "department_store", "jewelry",
}

TEEN_UNSAFE_WORDS = {
    "pub", "cocktail", "whisky", "whiskey", "vodka", "rum", "gin",
    "taberna", "cervec", "beer", "txoko", "nightclub", "discoteca",
    "apuestas", "bet", "casino",
}


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

    if len(t) < 3 or len(t) > 120:
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

    return True


def teen_safe(name: str, desc: str = "") -> bool:
    txt = clean(f"{name} {desc}").lower()
    return not any(x in txt for x in TEEN_UNSAFE_WORDS)


def likely_address(text: str) -> bool:
    low = clean(text).lower()
    address_tokens = [
        "calle", "c/", "plaza", "avda", "avenida", "alameda", "camino",
        "gran vía", "gran via", "licenciado", "sabino", "lehendakari",
        "lehendakaria", "ramón y cajal", "ramon y cajal", "colón", "colon",
        "hurtado", "moyua", "bilbao", "480",
    ]
    has_digit = bool(re.search(r"\d", low))
    return has_digit or any(tok in low for tok in address_tokens)


def split_address_candidates(text: str) -> list[str]:
    raw = clean(text)
    if not raw:
        return []
    parts = re.split(r"[|·]|(?:\s{2,})|(?:\.\s+)", raw)
    return [clean(p) for p in parts if clean(p)]


def extract_address_from_text(text: str) -> str:
    if not text:
        return ""

    candidates = split_address_candidates(text)
    for part in candidates:
        if likely_address(part):
            return part

    m = re.search(
        r"((?:C\/|Calle|Plaza|Avenida|Avda\.?|Alameda|Camino|Gran V[ií]a|Licenciado|Sabino|Lehendakari[a]?)[^|]+)",
        text,
        re.I,
    )
    if m:
        return clean(m.group(1))

    return ""


def infer_barrio_from_text(text: str) -> str:
    raw = clean(text)
    if not raw:
        return "Bilbao"

    barrios = [
        "Abando", "Casco Viejo", "Indautxu", "Deusto", "Miribilla", "Irala",
        "San Mamés", "Begoña", "Zorroza", "Otxarkoaga", "Errekalde",
        "Santutxu", "Uribarri", "Ametzola", "Basurto", "Moyua",
    ]
    low = raw.lower()
    for barrio in barrios:
        if barrio.lower() in low:
            return barrio

    return "Bilbao"


def page_text_blocks(soup: BeautifulSoup) -> list[str]:
    selectors = [
        ".field__item",
        ".content",
        ".node__content",
        ".paragraph",
        ".views-field",
        "article",
        "main",
    ]
    blocks: list[str] = []
    for sel in selectors:
        for el in soup.select(sel):
            txt = clean(el.get_text(" ", strip=True))
            if txt and txt not in blocks:
                blocks.append(txt)
    if not blocks:
        txt = clean(soup.get_text(" ", strip=True))
        if txt:
            blocks.append(txt)
    return blocks


def fetch_detail_metadata(url: str) -> dict:
    try:
        html = fetch_with_retries(url, attempts=2, pause=1.0)
    except Exception:
        return {"direccion": "", "zona": "Bilbao", "descripcion": "", "horario": ""}

    soup = BeautifulSoup(html, "html.parser")
    blocks = page_text_blocks(soup)
    blob = " | ".join(blocks)

    direccion = extract_address_from_text(blob)
    zona = infer_barrio_from_text(blob)
    horario = ""

    horario_match = re.search(
        r"(?:hours|opening hours|schedule|timetable|horario)\s*[:\-]?\s*([^|]{5,120})",
        blob,
        re.I,
    )
    if horario_match:
        horario = clean(horario_match.group(1))

    desc = ""
    for block in blocks:
        if len(block) > 50:
            desc = block[:500]
            break

    return {
        "direccion": direccion,
        "zona": zona or "Bilbao",
        "descripcion": desc,
        "horario": horario,
    }


def fetch_with_retries(url: str, attempts: int = 3, pause: float = 2.0) -> str:
    last_exc = None
    for _ in range(attempts):
        try:
            return fetch_url(url, timeout=60)
        except Exception as exc:
            last_exc = exc
            time.sleep(pause)
    raise last_exc


def infer_food_type(name: str, desc: str) -> str:
    txt = clean(f"{name} {desc}").lower()

    if "bubble" in txt or "boba" in txt:
        return "bubble-tea"
    if "helad" in txt or "ice cream" in txt or "gelato" in txt:
        return "heladeria"
    if "burger" in txt or "hamburg" in txt:
        return "hamburgueseria"
    if "pizza" in txt or "pizzer" in txt:
        return "pizza"
    if "coffee" in txt or "café" in txt or "cafe" in txt or "cafeter" in txt:
        return "cafeteria"
    if "bakery" in txt or "pasteler" in txt or "donut" in txt or "cookie" in txt:
        return "merendar"
    return "restaurante"


def infer_activity_type(name: str, desc: str) -> str:
    txt = clean(f"{name} {desc}").lower()

    if "escape" in txt:
        return "escape-room"
    if "arcade" in txt or "recreativa" in txt:
        return "arcade"
    if "bolera" in txt or "bowling" in txt:
        return "bolera"
    if "jump" in txt or "trampoline" in txt:
        return "jump-park"
    if "cine" in txt or "cinema" in txt:
        return "cine"
    if "museo" in txt or "museum" in txt or "gallery" in txt:
        return "museo"
    if "park" in txt or "parque" in txt or "paseo" in txt or "plaza" in txt:
        return "quedada"
    return "actividad"


def add_item(
    items: list[dict],
    seen: set,
    category: str,
    name: str,
    url: str,
    desc: str = "",
    zona: str = "Bilbao",
    direccion: str = "",
    horario: str = "",
):
    name = clean(name)
    desc = clean(desc)
    zona = clean(zona) or "Bilbao"
    direccion = clean(direccion)
    horario = clean(horario)

    if not valid_name(name):
        return

    if url and not valid_url("actividad" if category not in {"restaurante"} else "restaurante", url):
        return

    if not teen_safe(name, desc):
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
            "zona": zona,
            "direccion": direccion,
            "precio": "",
            "horario": horario,
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

        meta = fetch_detail_metadata(url)
        specific = infer_food_type(name, meta.get("descripcion", ""))
        add_item(
            items,
            seen,
            specific,
            name,
            url,
            desc=meta.get("descripcion", ""),
            zona=meta.get("zona", "Bilbao"),
            direccion=meta.get("direccion", ""),
            horario=meta.get("horario", ""),
        )

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

        meta = fetch_detail_metadata(url)
        specific = infer_activity_type(name, meta.get("descripcion", ""))
        add_item(
            items,
            seen,
            specific,
            name,
            url,
            desc=meta.get("descripcion", ""),
            zona=meta.get("zona", "Bilbao"),
            direccion=meta.get("direccion", ""),
            horario=meta.get("horario", ""),
        )

    return items


def overpass_query() -> str:
    return f"""
[out:json][timeout:60];
(
  node["amenity"~"restaurant|cafe|fast_food|ice_cream|cinema|theatre|arts_centre"](around:{RADIUS_METERS},{BILBAO_LAT},{BILBAO_LON});
  way["amenity"~"restaurant|cafe|fast_food|ice_cream|cinema|theatre|arts_centre"](around:{RADIUS_METERS},{BILBAO_LAT},{BILBAO_LON});
  relation["amenity"~"restaurant|cafe|fast_food|ice_cream|cinema|theatre|arts_centre"](around:{RADIUS_METERS},{BILBAO_LAT},{BILBAO_LON});

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


def _overpass_post(endpoint: str, query: str) -> dict:
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
        return json.loads(resp.read().decode("utf-8", errors="ignore"))


def compose_address(tags: dict) -> str:
    parts = [
        tags.get("addr:street", ""),
        tags.get("addr:housenumber", ""),
        tags.get("addr:postcode", ""),
        tags.get("addr:city", ""),
    ]
    return clean(" ".join([p for p in parts if p]))


def osm_specific_type(tags: dict) -> str | None:
    amenity = (tags.get("amenity") or "").lower()
    tourism = (tags.get("tourism") or "").lower()
    leisure = (tags.get("leisure") or "").lower()
    shop = (tags.get("shop") or "").lower()
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
        if "bubble" in txt or "boba" in txt:
            return "bubble-tea"
        return "restaurante"

    if tourism in {"museum", "gallery"}:
        return "museo"
    if tourism == "attraction":
        return "actividad"

    if amenity == "cinema":
        return "cine"
    if amenity in {"theatre", "arts_centre"}:
        return "actividad"

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

    if shop:
        if shop == "clothes":
            return "ropa"
        if shop in {"shoes", "sports"}:
            if any(x in name for x in ["sneaker", "snkrs", "foot", "shoe"]):
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


def fetch_osm_catalog() -> list[dict]:
    query = overpass_query()
    items = []
    seen = set()
    last_exc = None

    for endpoint in OVERPASS_ENDPOINTS:
        try:
            payload = _overpass_post(endpoint, query)
            elements = payload.get("elements", [])

            for el in elements:
                tags = el.get("tags", {})
                name = clean(tags.get("name", ""))
                if not valid_name(name):
                    continue

                category = osm_specific_type(tags)
                if not category:
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
                            tags.get("shop", ""),
                        ]
                    )
                )
                horario = clean(tags.get("opening_hours", ""))
                zona = tags.get("addr:suburb", "") or tags.get("addr:neighbourhood", "") or infer_barrio_from_text(address)

                if not teen_safe(name, desc):
                    continue

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
                        "zona": zona or "Bilbao",
                        "direccion": address,
                        "precio": "",
                        "horario": horario,
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
            else:
                lugares.extend(parse_unique_activities(soup, url))

        except Exception as exc:
            print(f"Aviso: no se pudo procesar {url}: {exc}")

    try:
        osm_items = fetch_osm_catalog()
        lugares.extend(osm_items)
        print(f"OSM catálogo: {len(osm_items)} lugares")
    except Exception as exc:
        print(f"Aviso: no se pudo obtener catálogo OSM: {exc}")

    unique = []
    seen = set()
    for item in lugares:
        key = (item["tipo"], item["nombre"].lower(), item["url"].lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    previous = read_json(OUT_FILE, [])
    if not unique and previous:
        update_sync("Lugares Turismo", len(previous), status="ok", note="Se conserva último snapshot válido")
        print(f"Lugares Turismo: 0 nuevos, se conserva snapshot anterior ({len(previous)})")
        return

    if not unique and SEED_FILE.exists():
        seed = read_json(SEED_FILE, [])
        if seed:
            write_json(OUT_FILE, seed)
            update_sync("Lugares Turismo", len(seed), status="ok", note="Fallback seed local")
            print(f"Lugares Turismo: fallback seed local ({len(seed)})")
            return

    if not unique and not previous:
        update_sync("Lugares Turismo", 0, status="error", note="Todas las fuentes fallaron")
        raise RuntimeError("No se pudieron obtener lugares de ninguna fuente")

    write_json(OUT_FILE, unique)
    update_sync("Lugares Turismo", len(unique), note="Turismo + OSM orientado a adolescentes")
    print(f"Lugares Turismo: {len(unique)} lugares")


if __name__ == "__main__":
    main()
