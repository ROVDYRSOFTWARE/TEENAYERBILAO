from __future__ import annotations
from jobs.common import DATA_DIR, FUENTES_DIR, read_json, update_sync, write_json
from services import data_store, geocode

SOURCE_FILES = [
    FUENTES_DIR / 'open_data_bilbao.json',
    FUENTES_DIR / 'bilbao_gazte.json',
    FUENTES_DIR / 'bilbao_turismo.json',
]
OUT_FILE = DATA_DIR / 'eventos.json'


def _infer_franja(hora: str) -> str:
    h = (hora or '').strip()
    try:
        hour = int(h[:2] if ':' in h[:2] else h.split(':')[0])
    except Exception:
        return ''
    if hour < 14:
        return 'mañana'
    if hour < 20:
        return 'tarde'
    return 'noche'


def _existing_index():
    idx = {}
    for row in data_store.load_events():
        key = (row.get('fuente',''), row.get('titulo',''), row.get('fecha',''))
        idx[key] = row
    return idx


def normalize(item: dict, existing: dict) -> dict:
    fecha = item.get('fecha_inicio', '') or item.get('fecha_fin', '') or ''
    key = (item.get('fuente',''), item.get('titulo',''), fecha)
    prev = existing.get(key, {})
    barrio = item.get('zona', '') or prev.get('barrio', '')
    ubicacion = item.get('zona', '') or prev.get('ubicacion', '')
    direccion = prev.get('direccion', '')
    lat = prev.get('latitud', '')
    lon = prev.get('longitud', '')
    maps_url = prev.get('maps_url', '')
    if not (lat and lon) and (ubicacion or barrio):
        q = ', '.join([x for x in [direccion, ubicacion, barrio, 'Bilbao'] if x])
        geo = geocode.geocode(q)
        if geo:
            lat = geo.get('latitud', '')
            lon = geo.get('longitud', '')
    if not maps_url and lat and lon:
        maps_url = f'https://www.google.com/maps?q={lat},{lon}'
    return {
        'id': prev.get('id') or item.get('id', ''),
        'titulo': item.get('titulo', ''),
        'fecha': fecha,
        'barrio': barrio,
        'categoria': item.get('tipo', '') or 'evento',
        'franja': prev.get('franja') or _infer_franja(item.get('hora', '')),
        'precio_tipo': item.get('precio', '') or prev.get('precio_tipo', ''),
        'ubicacion': ubicacion,
        'direccion': direccion,
        'latitud': lat,
        'longitud': lon,
        'maps_url': maps_url,
        'fuente': item.get('fuente', ''),
        'descripcion': item.get('descripcion', '') or prev.get('descripcion', ''),
        'url': item.get('url', ''),
        'tags': prev.get('tags', []),
        'auto_source': True,
    }


def main():
    merged = []
    seen = set()
    existing = _existing_index()
    for path in SOURCE_FILES:
        for item in read_json(path, []):
            norm = normalize(item, existing)
            key = (norm['fuente'], norm['titulo'], norm['fecha'], norm['url'])
            if key in seen or not norm['titulo']:
                continue
            seen.add(key)
            merged.append(norm)
    # preserve manual events not auto-generated
    for row in data_store.load_events():
        if not row.get('auto_source'):
            merged.append(row)
    merged.sort(key=lambda x: ((x.get('fecha') or '9999-99-99'), (x.get('titulo') or '')))
    write_json(OUT_FILE, merged)
    update_sync('Eventos agregados', len(merged), note='Merge local de fuentes hacia esquema app')
    print(f"Eventos agregados: {len(merged)}")

if __name__ == '__main__':
    main()
