from __future__ import annotations

import re
from urllib.parse import urljoin

from bs4 import BeautifulSoup, Tag

from jobs.common import FUENTES_DIR, fetch_url, update_sync, write_json

AGENDA_URL = "https://bilbaogazte.bilbao.eus/es/agenda/"
OUT_FILE = FUENTES_DIR / "bilbao_gazte.json"


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def discover_pages() -> list[str]:
    html = fetch_url(AGENDA_URL)
    soup = BeautifulSoup(html, "html.parser")
    urls = []
    for a in soup.select('a[href]'):
        href = a.get('href', '')
        text = clean(a.get_text(' '))
        if not href:
            continue
        absolute = urljoin(AGENDA_URL, href)
        if 'bilbaogazte.bilbao.eus' not in absolute:
            continue
        if any(key in absolute for key in ['agenda-', 'gaztekluba', 'bilborock/agenda']):
            urls.append(absolute)
        elif any(key in text.lower() for key in ['agenda', 'bilborock', 'gaztekluba', 'perrera']):
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
    soup = BeautifulSoup(html, 'html.parser')
    events = []
    seen_titles = set()

    for heading in soup.find_all(['h3', 'h4']):
        title = clean(heading.get_text(' '))
        if len(title) < 10:
            continue
        title_key = title.lower()
        if title_key in seen_titles:
            continue
        seen_titles.add(title_key)

        block = []
        for sib in heading.next_siblings:
            if isinstance(sib, Tag) and sib.name in ['h3', 'h4']:
                break
            if isinstance(sib, Tag):
                txt = clean(sib.get_text(' '))
                if txt:
                    block.append(txt)
        combined = ' '.join(block)
        if len(combined) < 20:
            continue
        place_match = re.search(r'Lugar:\s*([^\.]+)', combined, re.I)
        price_match = re.search(r'Precio:\s*([^\.]+)', combined, re.I)
        time_match = re.search(r'(\d{1,2}:\d{2}\s*-\s*\d{1,2}:\d{2}|\d{1,2}:\d{2})', combined)

        events.append({
            'id': f"gazte-{abs(hash((url, title))) % 10**10}",
            'fuente': 'Bilbao Gazte',
            'tipo': 'juventud',
            'titulo': title,
            'descripcion': combined[:1000],
            'fecha_inicio': '',
            'fecha_fin': '',
            'hora': time_match.group(1) if time_match else '',
            'zona': clean(place_match.group(1)) if place_match else '',
            'edad': '',
            'precio': clean(price_match.group(1)) if price_match else '',
            'url': url,
        })
    return events


def main():
    pages = discover_pages()
    eventos = []
    for url in pages:
        try:
            eventos.extend(parse_page(url))
        except Exception as exc:
            print(f"Aviso: no se pudo procesar {url}: {exc}")
    unique = []
    seen = set()
    for item in eventos:
        key = (item['titulo'], item['url'])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    write_json(OUT_FILE, unique)
    update_sync('Bilbao Gazte', len(unique), note='Scraping de agenda juvenil')
    print(f"Bilbao Gazte: {len(unique)} eventos")

if __name__ == '__main__':
    main()
