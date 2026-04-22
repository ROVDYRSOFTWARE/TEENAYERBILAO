from __future__ import annotations
import re
from bs4 import BeautifulSoup
from jobs.common import FUENTES_DIR, fetch_url, update_sync, write_json

URL = 'https://www.bilbaoturismo.net/BilbaoTurismo/en/big-events'
OUT_FILE = FUENTES_DIR / 'bilbao_turismo.json'


def clean(text: str) -> str:
    return re.sub(r'\s+', ' ', text or '').strip()


def parse_dates(text: str):
    m = re.search(r'(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})', text)
    if not m:
        return '', ''
    d1 = '-'.join(reversed(m.group(1).split('/')))
    d2 = '-'.join(reversed(m.group(2).split('/')))
    return d1, d2


def main():
    html = fetch_url(URL)
    soup = BeautifulSoup(html, 'html.parser')
    eventos = []
    text = soup.get_text('
')
    pattern = re.compile(r'
\s*([A-ZÁÉÍÓÚÜÑ0-9][^
]{3,80}?)\s*
\s*(\d{2}/\d{2}/\d{4}\s*-\s*\d{2}/\d{2}/\d{4})', re.M)
    for idx, match in enumerate(pattern.finditer(text), start=1):
        titulo = clean(match.group(1))
        if titulo.lower() in {'highlights', 'search by dates'}:
            continue
        fecha_inicio, fecha_fin = parse_dates(match.group(2))
        eventos.append({
            'id': f'turismo-{idx}',
            'fuente': 'Bilbao Turismo',
            'tipo': 'gran evento',
            'titulo': titulo,
            'descripcion': '',
            'fecha_inicio': fecha_inicio,
            'fecha_fin': fecha_fin,
            'hora': '',
            'zona': 'Bilbao',
            'edad': '',
            'precio': '',
            'url': URL,
        })
    write_json(OUT_FILE, eventos)
    update_sync('Bilbao Turismo', len(eventos), note='Big events')
    print(f"Bilbao Turismo: {len(eventos)} eventos")

if __name__ == '__main__':
    main()
