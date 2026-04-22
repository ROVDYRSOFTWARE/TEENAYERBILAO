from __future__ import annotations

from jobs.common import DATA_DIR, FUENTES_DIR, read_json, update_sync, write_json
from services import data_store, geocode

SOURCE_FILES = [
    FUENTES_DIR / "lugares_turismo.json",
]

OUT_FILE = DATA_DIR / "lugares.json"


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


def normalize(item: dict, existing: dict) -> dict:
    key = (item.get("fuente", ""), item.get("nombre", ""), item.get("url", ""))
    prev = existing.get(key, {})

    barrio = item.get("zona", "") or prev.get("barrio", "")
    ubicacion = item.get("zona", "") or prev.get("ubicacion", "") or item.get("nombre", "")
    direccion = item.get("direccion", "") or prev.get("direccion", "")
    lat = prev.get("latitud", "")
    lon = prev.get("longitud", "")
    maps_url = prev.get("maps_url", "")

    if not (lat and lon):
        q = ", ".join([x for x in [direccion, ubicacion, barrio, "Bilbao"] if x])
        geo = geocode.geocode(q)
        if geo:
            lat = geo.get("latitud", "")
            lon = geo.get("longitud", "")

    if not maps_url and lat and lon:
        maps_url = f"https://www.google.com/maps?q={lat},{lon}"

    return {
        "id": prev.get("id") or item.get("id", ""),
        "nombre": item.get("nombre", ""),
        "barrio": barrio,
        "categoria": item.get("tipo", "") or "lugar",
        "franja": prev.get("franja") or infer_franja(item.get("tipo", "")),
        "precio_tipo": item.get("precio", "") or prev.get("precio_tipo", ""),
        "ubicacion": ubicacion,
        "direccion": direccion,
        "latitud": lat,
        "longitud": lon,
        "maps_url": maps_url,
        "fuente": item.get("fuente", ""),
        "descripcion": item.get("descripcion", "") or prev.get("descripcion", ""),
        "url": item.get("url", ""),
        "tags": prev.get("tags", []),
        "auto_source": True,
    }


def main():
    merged = []
    seen = set()
    existing = _existing_index()

    for path in SOURCE_FILES:
        for item in read_json(path, []):
            norm = normalize(item, existing)
            key = (norm["fuente"], norm["nombre"], norm["url"])
            if key in seen or not norm["nombre"]:
                continue
            seen.add(key)
            merged.append(norm)

    # conservar lugares manuales
    for row in data_store.load_places():
        if not row.get("auto_source"):
            merged.append(row)

    merged.sort(key=lambda x: ((x.get("categoria") or ""), (x.get("nombre") or "")))
    write_json(OUT_FILE, merged)
    update_sync("Lugares agregados", len(merged), note="Merge local de fuentes hacia esquema app")
    print(f"Lugares agregados: {len(merged)}")


if __name__ == "__main__":
    main()