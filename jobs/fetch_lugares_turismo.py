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
    ">>>",
    "1",
    "2",
    "3",
    "4",
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
    if t.lower() in BAD_TEXTS:
        return False
    if len(t) < 3 or len(t) > 90:
        return False
    if t.startswith("http"):
        return False
    return True

def add_item(items: list[dict], seen: set, category: str, name: str, url: str, desc: str = ""):
    name = clean(name)
    desc = clean(desc)
    if not valid_name(name):
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

    # toma enlaces del bloque principal
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

    # 1) intenta nombres de imágenes
    for img in soup.select("img[alt]"):
        name = clean(img.get("alt", "")).replace("Image:", "").strip()
        add_item(items, seen, "nightlife", name, base_url)

    # 2) intenta enlaces visibles también
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

    # dedupe final
    unique = []
    seen = set()
    for item in lugares:
        key = (item["tipo"], item["nombre"].lower(), item["url"].lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    write_json(OUT_FILE, unique)
    update_sync("Lugares Turismo", len(unique), note="Scraping tolerante de Bilbao Turismo")
    print(f"Lugares Turismo: {len(unique)} lugares")

if __name__ == "__main__":
    main()