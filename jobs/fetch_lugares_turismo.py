from __future__ import annotations
import hashlib
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from jobs.common import FUENTES_DIR, fetch_url, update_sync, write_json

URLS = [
    ("restaurante", "https://www.bilbaoturismo.net/BilbaoTurismo/en/restaurantes"),
    ("nightlife", "https://www.bilbaoturismo.net/BilbaoTurismo/en/my-bilbao/nightlife"),
    ("actividad", "https://bilbaoturismo.net/BilbaoTurismo/en/unique-activities"),
]

OUT_FILE = FUENTES_DIR / "lugares_turismo.json"

BAD_TEXTS = {
    "to see",
    "about us",
    "accomodation",
    "accommodation",
    "aviso legal",
    "legal notice",
    "interesting areas",
    "museums and theaters",
    "old quarter and the ensanche",
    "routes and panoramic views",
    "new bilbao",
    "art en plein air",
    "transporter bridge-world heritage",
    "transporter bridge",
    "restaurants",
    "nightlife",
    "unique activities",
    "highlights",
    "home",
    "newsletter",
    "contact",
    "site map",
    "share",
    "facebook",
    "twitter",
    "mail",
    "for you",
    "cuisine",
    "companies",
    "tourists",
    "trade",
    "press",
    "more information",
    "more info",
    "read more",
    "see more",
    "discover",
    "agenda",
    "bilbao",
    "activities",
    "1",
    "2",
    "3",
    "4",
}

BAD_URL_PARTS = [
    "/aviso-legal",
    "/legal",
    "/contact",
    "/newsletter",
    "/site-map",
    "/accomodation",
    "/accommodation",
    "/historia",
    "/arte-al-aire-libre",
    "/anillo-verde",
    "/the-world-showcase-of-architecture",
    "/otros-museos",
    "/bilbao-en-1--2-y-3-dias",
    "/guggenheim-museum-bilbao_2",
    "/espacio-gran-via",
]

GOOD_ACTIVITY_HINTS = [
    "/unique-activities/",
]

GOOD_RESTAURANT_HINTS = [
    "/restaurantes/",
]

NIGHTLIFE_BLACKLIST = {
    "autocaravaning",
    "albergue",
    "apartamento",
    "arriaga",
    "arte y cultura",
    "basque design",
    "bilbao bizkaia card",
    "bilbobentura",
    "azkuna zentroa",
    "agenda",
    "artxanda",
    "artxanda bilbao",
    "about us",
    "accomodation",
    "accommodation",
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

    # evita palabras sueltas genéricas
    if len(name.split()) == 1 and len(name) < 7:
        return False

    # evita categorías y conceptos no locales
    generic_bits = [
        "arte",
        "cultura",
        "card",
        "design",
        "apartamento",
        "albergue",
        "autocaravaning",
    ]
    if any(bit in low for bit in generic_bits):
        return False

    return True


def add_item(items: list[dict], seen: set, category: str, name: str, url: str, desc: str = ""):
    name = clean(name)
    desc = clean(desc)

    if not valid_name(name):
        return

    if not valid_url(category, url):
        return

    if category == "nightlife" and not nightlife_name_ok(name):
        return

    key = (category, name.lower(), url.lower())
    if key in seen:
        return

    seen.add(key)
    items.append(
        {
            "id": f"lug-{stable_id(category, name, url)}",
            "fuente": "Bilbao Turismo",
            "tipo": category,
            "nombre": name,
            "descripcion": desc[:500],
            "zona": "Bilbao",
            "direccion": "",
            "precio": "",
            "url": url,
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


def main():
    lugares = []

    for category, url in URLS:
        try:
            html = fetch_url(url)
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

    write_json(OUT_FILE, unique)
    update_sync("Lugares Turismo", len(unique), note="Scraping filtrado de Bilbao Turismo")
    print(f"Lugares Turismo: {len(unique)} lugares")


if __name__ == "__main__":
    main()