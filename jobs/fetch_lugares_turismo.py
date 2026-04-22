from __future__ import annotations
import hashlib
import re
from urllib.parse import urljoin, urlparse

from bs4 import BeautifulSoup

from jobs.common import FUENTES_DIR, fetch_url, update_sync, write_json

URLS = [
    ("restaurante", "https://www.bilbaoturismo.net/BilbaoTurismo/en/restaurantes"),
    ("nightlife", "https://www.bilbaoturismo.net/BilbaoTurismo/en/my-bilbao/nightlife"),
    ("actividad", "https://www.bilbaoturismo.net/BilbaoTurismo/en/unique-activities"),
]

OUT_FILE = FUENTES_DIR / "lugares_turismo.json"

BAD_TEXTS = {
    "read more",
    "more info",
    "more information",
    "restaurants",
    "nightlife",
    "unique activities",
    "highlights",
    "search",
    "bilbao turismo",
    "see more",
    "discover",
}


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def stable_id(*parts: str) -> str:
    base = "||".join(parts)
    return hashlib.md5(base.encode("utf-8")).hexdigest()[:12]


def likely_good_title(text: str) -> bool:
    t = clean(text)
    if not t or len(t) < 3 or len(t) > 90:
        return False
    if t.lower() in BAD_TEXTS:
        return False
    if t.lower().startswith("http"):
        return False
    return True


def extract_cards(soup: BeautifulSoup, base_url: str, category: str) -> list[dict]:
    lugares = []
    seen = set()

    selectors = [
        "article",
        ".card",
        ".item",
        ".views-row",
        ".listing-item",
        ".list-item",
        ".elementor-post",
        ".post",
    ]

    cards = []
    for sel in selectors:
        cards.extend(soup.select(sel))

    # si no encuentra tarjetas, usa fallback con enlaces
    if not cards:
        cards = soup.select("a[href]")

    for node in cards:
        link = node.select_one("a[href]") if getattr(node, "select_one", None) else node
        if not link:
            continue

        href = link.get("href", "").strip()
        if not href:
            continue

        url = urljoin(base_url, href)
        parsed = urlparse(url)

        if "bilbaoturismo.net" not in parsed.netloc:
            continue

        title = ""
        for sel in ["h1", "h2", "h3", "h4", ".title", ".card-title", ".entry-title"]:
            el = node.select_one(sel) if getattr(node, "select_one", None) else None
            if el:
                title = clean(el.get_text(" ", strip=True))
                break

        if not title:
            title = clean(link.get_text(" ", strip=True))

        if not likely_good_title(title):
            continue

        raw_text = clean(node.get_text(" ", strip=True)) if hasattr(node, "get_text") else title
        desc = raw_text.replace(title, "", 1).strip(" -:")[:500]

        key = (title.lower(), url.lower())
        if key in seen:
            continue
        seen.add(key)

        lugares.append(
            {
                "id": f"lug-{stable_id(category, title, url)}",
                "fuente": "Bilbao Turismo",
                "tipo": category,
                "nombre": title,
                "descripcion": desc,
                "zona": "Bilbao",
                "direccion": "",
                "precio": "",
                "url": url,
            }
        )

    return lugares


def main():
    lugares = []

    for category, url in URLS:
        try:
            html = fetch_url(url)
            soup = BeautifulSoup(html, "html.parser")
            lugares.extend(extract_cards(soup, url, category))
        except Exception as exc:
            print(f"Aviso: no se pudo procesar {url}: {exc}")

    # dedupe final
    unique = []
    seen = set()
    for item in lugares:
        key = (item["nombre"].lower(), item["url"].lower())
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    write_json(OUT_FILE, unique)
    update_sync("Lugares Turismo", len(unique), note="Scraping restaurantes, nightlife y actividades")
    print(f"Lugares Turismo: {len(unique)} lugares")


if __name__ == "__main__":
    main()