from __future__ import annotations
import json
import re
from datetime import datetime

from jobs.common import FUENTES_DIR, fetch_url, update_sync, write_json

OPEN_DATA_URL = (
    "https://www.bilbao.eus/cs/Satellite?c=Page&cid=1272990237857&idioma=es"
    "&pageid=1272990237857&pagename=Bilbaonet%2FPage%2FBIO_ListadoEventosAppInfoBilbao&todos=si"
)
OUT_FILE = FUENTES_DIR / "open_data_bilbao.json"


def flatten_items(node):
    items = []
    if isinstance(node, list):
        for x in node:
            items.extend(flatten_items(x))
    elif isinstance(node, dict):
        keys = {str(k).lower() for k in node.keys()}
        if any(k in keys for k in ["titulo", "title", "nombre", "name"]) and any(k in keys for k in ["fecha", "date", "fecha_inicio", "startdate", "start_date"]):
            items.append(node)
        for v in node.values():
            items.extend(flatten_items(v))
    return items


def pick(item, *keys, default=""):
    lower_map = {str(k).lower(): v for k, v in item.items()}
    for key in keys:
        if key.lower() in lower_map:
            return lower_map[key.lower()]
    return default


def normalize_date(value: str) -> str:
    if not value:
        return ""
    text = str(value).strip()
    for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%Y/%m/%d", "%d-%m-%Y", "%Y-%m-%d %H:%M:%S"]:
        try:
            return datetime.strptime(text[:19], fmt).strftime("%Y-%m-%d")
        except Exception:
            pass
    m = re.search(r"(\d{4}-\d{2}-\d{2})", text)
    if m:
        return m.group(1)
    m = re.search(r"(\d{2}/\d{2}/\d{4})", text)
    if m:
        return datetime.strptime(m.group(1), "%d/%m/%Y").strftime("%Y-%m-%d")
    return text


def main():
    raw = fetch_url(OPEN_DATA_URL)
    data = json.loads(raw)
    raw_items = flatten_items(data)
    eventos = []
    for idx, item in enumerate(raw_items, start=1):
        titulo = str(pick(item, "titulo", "title", "nombre", "name")).strip()
        if not titulo:
            continue
        eventos.append({
            "id": f"opendata-{idx}",
            "fuente": "Bilbao Open Data",
            "tipo": str(pick(item, "tipo", "categoria", "category", default="agenda")).strip() or "agenda",
            "titulo": titulo,
            "descripcion": str(pick(item, "descripcion", "description", "resumen")).strip(),
            "fecha_inicio": normalize_date(str(pick(item, "fecha_inicio", "fecha", "date", "startdate", "start_date"))),
            "fecha_fin": normalize_date(str(pick(item, "fecha_fin", "enddate", "end_date"))),
            "hora": str(pick(item, "hora", "hour", "horario")).strip(),
            "zona": str(pick(item, "zona", "barrio", "district", "lugar", "place")).strip(),
            "edad": str(pick(item, "edad", "publico", "audiencia")).strip(),
            "precio": str(pick(item, "precio", "price")).strip(),
            "url": str(pick(item, "url", "link", "enlace")).strip(),
        })
    write_json(OUT_FILE, eventos)
    update_sync("Bilbao Open Data", len(eventos), note="Fuente oficial JSON")
    print(f"Open Data Bilbao: {len(eventos)} eventos")

if __name__ == "__main__":
    main()
