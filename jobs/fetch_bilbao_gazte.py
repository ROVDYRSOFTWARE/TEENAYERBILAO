from __future__ import annotations

import hashlib
import re
from datetime import date
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from jobs.common import FUENTES_DIR, fetch_url, update_sync, write_json

AGENDA_URL = "https://bilbaogazte.bilbao.eus/es/gaztekluba/"
OUT_FILE = FUENTES_DIR / "bilbao_gazte.json"


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def stable_id(*parts: str) -> str:
    raw = "||".join(parts).encode("utf-8", errors="ignore")
    return "gazte-" + hashlib.sha1(raw).hexdigest()[:12]


def parse_spanish_date(text: str) -> str:
    meses = {
        "enero": 1,
        "febrero": 2,
        "marzo": 3,
        "abril": 4,
        "mayo": 5,
        "junio": 6,
        "julio": 7,
        "agosto": 8,
        "septiembre": 9,
        "setiembre": 9,
        "octubre": 10,
        "noviembre": 11,
        "diciembre": 12,
    }
    raw = clean(text).lower()
    m = re.search(r"(\d{1,2})\s+de\s+([a-záéíóú]+)", raw)
    if not m:
        return ""

    dia = int(m.group(1))
    mes_txt = m.group(2)
    mes = meses.get(mes_txt)
    if not mes:
        return ""

    today = date.today()
    year = today.year

    try:
        dt = date(year, mes, dia)
    except Exception:
        return ""

    if (dt - today).days > 180:
        try:
            dt = date(year - 1, mes, dia)
        except Exception:
            return ""

    return dt.isoformat()


def discover_pages() -> list[str]:
    html = fetch_url(AGENDA_URL)
    soup = BeautifulSoup(html, "html.parser")

    urls = [AGENDA_URL]
    for a in soup.select("a[href]"):
        href = a.get("href", "").strip()
        if not href:
            continue
        absolute = urljoin(AGENDA_URL, href)
        if "bilbaogazte.bilbao.eus" not in absolute:
            continue
        if "/es/gaztekluba" not in absolute:
            continue
        if any(x in absolute for x in ["ideiak", "#", "?reply"]):
            continue
        urls.append(absolute)

    ordered = []
    seen = set()
    for url in urls:
        if url not in seen:
            ordered.append(url)
            seen.add(url)
    return ordered[:12]


def parse_page(url: str) -> list[dict]:
    html = fetch_url(url)
    soup = BeautifulSoup(html, "html.parser")
    events: list[dict] = []
    seen_titles = set()

    for heading in soup.find_all(["h2", "h3", "h4"]):
        title = clean(heading.get_text(" "))
        if len(title) < 8:
            continue
        if " de " not in title:
            continue

        fecha_iso = parse_spanish_date(title)
        if not fecha_iso:
            continue

        title_key = title.lower()
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)

        block = []
        for sib in heading.next_siblings:
            if isinstance(sib, Tag) and sib.name in ["h2", "h3", "h4"]:
                break
            if isinstance(sib, Tag):
                txt = clean(sib.get_text(" "))
                if txt:
                    block.append(txt)

        combined = " ".join(block)
        if len(combined) < 20:
            continue

        place_match = re.search(r"Lugar:\s*([^\.]+)", combined, re.I)
        price_match = re.search(r"Precio:\s*([^\.]+)", combined, re.I)
        time_match = re.search(r"(\d{1,2}:\d{2}\s*[–-]\s*\d{1,2}:\d{2}|\d{1,2}:\d{2})", combined)

        events.append(
            {
                "id": stable_id(url, title, fecha_iso),
                "fuente": "Bilbao Gazte",
                "tipo": "juventud",
                "titulo": title,
                "descripcion": combined[:1000],
                "fecha_inicio": fecha_iso,
                "fecha_fin": fecha_iso,
                "hora": clean(time_match.group(1)) if time_match else "",
                "zona": clean(place_match.group(1)) if place_match else "",
                "edad": "",
                "precio": clean(price_match.group(1)) if price_match else "",
                "url": url,
            }
        )

    return events


def main():
    pages = discover_pages()
    eventos: list[dict] = []

    for url in pages:
        try:
            eventos.extend(parse_page(url))
        except Exception as exc:
            print(f"Aviso: no se pudo procesar {url}: {exc}")

    unique = []
    seen = set()
    for item in eventos:
        key = (item["titulo"], item["fecha_inicio"], item["url"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    unique.sort(key=lambda x: (x.get("fecha_inicio", "9999-99-99"), x.get("titulo", "")))

    write_json(OUT_FILE, unique)
    update_sync("Bilbao Gazte", len(unique), note="Scraping #GazteKLUBA")
    print(f"Bilbao Gazte: {len(unique)} eventos")


if __name__ == "__main__":
    main()
