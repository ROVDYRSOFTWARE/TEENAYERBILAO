from __future__ import annotations

from jobs.common import DATA_DIR, FUENTES_DIR, read_json, update_sync, write_json
from services import data_store, geocode

SOURCE_FILES = [
    FUENTES_DIR / "lugares_turismo.json",
]

OUT_FILE = DATA_DIR / "lugares.json"


def clean(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def infer_franja(tipo: str) -> str:
    t = (tipo or "").lower()
    if any(x in t for x in ["nightlife", "discoteca", "bar", "noche"]):
        return "noche"
    if any(x in t for x in ["restaurante", "cafe", "cafetería", "comida"]):
        return "tarde"
    return "tarde"


def _existing_index():
    idx = {}
    for row in data_store.load_places():
        key = (row.get("fuente", ""), row.get("nombre", ""), row.get("url", ""))
        idx[key] = row
    return idx


def best_query(direccion: str, ubicacion: str, barrio: str) -> str:
    parts = []
    if direccion:
        parts.append(direccion)
    if ubicacion and ubicacion not in parts:
        parts.append(ubicacion)
    if barrio and barrio not in parts:
        parts.append(barrio)
    parts.append("Bilbao")
    return ", ".join([p for p in parts if p])


def normalize(item: dict, existing: dict) -> dict:
    key = (item.get("fuente", ""), item.get("nombre", ""), item.get("url", ""))
    prev = existing.get(key, {})

    nombre = clean(item.get("nombre", "")) or clean(prev.get("nombre", ""))
    barrio = clean(item.get("zona", "")) or clean(prev.get("barrio", "")) or "Bilbao"
    ubicacion = nombre or clean(prev.get("ubicacion", "")) or barrio
    direccion = clean(item.get("direccion", "")) or clean(prev.get("direccion", ""))
    horario = clean(item.get("horario", "")) or clean(prev.get("horario", ""))
    lat = clean(prev.get("latitud", ""))
    lon = clean(prev.get("longitud", ""))
    maps_url = clean(prev.get("maps_url", ""))

    if not (lat and lon):
        q = best_query(direccion, ubicacion, barrio)
        geo = geocode.geocode(q)
        if geo:
            lat = geo.get("latitud", "")
            lon = geo.get("longitud", "")

    if not maps_url and lat and lon:
        maps_url = f"https://www.google.com/maps?q={lat},{lon}"

    return {
        "id": prev.get("id") or item.get("id", ""),
        "nombre": nombre,
        "barrio": barrio,
        "categoria": item.get("tipo", "") or "lugar",
        "franja": clean(prev.get("franja", "")) or infer_franja(item.get("tipo", "")),
        "precio_tipo": clean(item.get("precio", "")) or clean(prev.get("precio_tipo", "")),
        "ubicacion": ubicacion,
        "direccion": direccion,
        "horario": horario,
        "latitud": lat,
        "longitud": lon,
        "maps_url": maps_url,
        "fuente": item.get("fuente", ""),
        "descripcion": clean(item.get("descripcion", "")) or clean(prev.get("descripcion", "")),
        "url": item.get("url", ""),
        "tags": prev.get("tags", []),
        "auto_source": True,
    }


def main():
    merged = []
    seen = set()
    existing = _existing_index()

    source_items = []
    for path in SOURCE_FILES:
        source_items.extend(read_json(path, []))

    current_places = data_store.load_places()
    if not source_items and current_places:
        update_sync("Lugares agregados", len(current_places), status="ok", note="Se conserva lugares.json anterior")
        print(f"Lugares agregados: 0 nuevos, se conserva snapshot anterior ({len(current_places)})")
        return

    for item in source_items:
        norm = normalize(item, existing)
        key = (norm["fuente"], norm["nombre"], norm["url"])
        if key in seen or not norm["nombre"]:
            continue
        seen.add(key)
        merged.append(norm)

    for row in current_places:
        if not row.get("auto_source"):
            merged.append(row)

    merged.sort(key=lambda x: ((x.get("categoria") or ""), (x.get("nombre") or "")))
    write_json(OUT_FILE, merged)
    update_sync("Lugares agregados", len(merged), note="Merge local de fuentes con dirección/horario")
    print(f"Lugares agregados: {len(merged)}")


if __name__ == "__main__":
    main()
