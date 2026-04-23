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

    if t in {"cine", "bolera", "arcade", "escape-room", "jump-park"}:
        return "tarde"
    if t in {"cafeteria", "bubble-tea", "heladeria", "merendar"}:
        return "tarde"
    if t in {"hamburgueseria", "pizza", "restaurante"}:
        return "tarde"
    if t in {"ropa", "sneakers", "manga", "regalos", "belleza", "compras"}:
        return "tarde"
    if t in {"museo", "actividad", "quedada"}:
        return "mañana"

    return "tarde"


def teen_score(tipo: str) -> int:
    t = (tipo or "").lower()
    scores = {
        "bubble-tea": 10,
        "arcade": 10,
        "bolera": 10,
        "jump-park": 10,
        "escape-room": 10,
        "ropa": 9,
        "sneakers": 9,
        "manga": 9,
        "heladeria": 9,
        "cafeteria": 8,
        "cine": 8,
        "hamburgueseria": 8,
        "pizza": 8,
        "regalos": 8,
        "belleza": 8,
        "compras": 7,
        "museo": 7,
        "actividad": 7,
        "quedada": 7,
        "restaurante": 6,
    }
    return scores.get(t, 5)


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
    categoria = clean(item.get("tipo", "")) or clean(prev.get("categoria", "")) or "lugar"
    barrio = clean(item.get("zona", "")) or clean(prev.get("barrio", "")) or "Bilbao"
    ubicacion = nombre or clean(prev.get("ubicacion", "")) or barrio
    direccion = clean(item.get("direccion", "")) or clean(prev.get("direccion", ""))
    horario = clean(item.get("horario", "")) or clean(prev.get("horario", ""))
    lat = clean(prev.get("latitud", ""))
    lon = clean(prev.get("longitud", ""))
    maps_url = clean(prev.get("maps_url", ""))
    descripcion = clean(item.get("descripcion", "")) or clean(prev.get("descripcion", ""))

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
        "categoria": categoria,
        "franja": clean(prev.get("franja", "")) or infer_franja(categoria),
        "precio_tipo": clean(item.get("precio", "")) or clean(prev.get("precio_tipo", "")),
        "ubicacion": ubicacion,
        "direccion": direccion,
        "horario": horario,
        "latitud": lat,
        "longitud": lon,
        "maps_url": maps_url,
        "fuente": item.get("fuente", ""),
        "descripcion": descripcion,
        "url": item.get("url", ""),
        "tags": prev.get("tags", []),
        "teen_score": teen_score(categoria),
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

    merged.sort(
        key=lambda x: (
            -(int(x.get("teen_score", 0) or 0)),
            (x.get("categoria") or ""),
            (x.get("nombre") or ""),
        )
    )

    write_json(OUT_FILE, merged)
    update_sync("Lugares agregados", len(merged), note="Merge orientado a ocio adolescente")
    print(f"Lugares agregados: {len(merged)}")


if __name__ == "__main__":
    main()
