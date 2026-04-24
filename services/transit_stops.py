from __future__ import annotations

import math
from typing import Iterable


FALLBACK_STOPS = [
    {"id": "metro_abando", "kind": "metro", "name": "Abando", "line": "L1/L2", "lat": 43.2627, "lon": -2.9253},
    {"id": "metro_moyua", "kind": "metro", "name": "Moyua", "line": "L1/L2", "lat": 43.2636, "lon": -2.9349},
    {"id": "metro_indautxu", "kind": "metro", "name": "Indautxu", "line": "L1/L2", "lat": 43.2647, "lon": -2.9442},
    {"id": "metro_sanmames", "kind": "metro", "name": "San Mamés", "line": "L1/L2", "lat": 43.2608, "lon": -2.9494},
    {"id": "metro_deusto", "kind": "metro", "name": "Deusto", "line": "L1", "lat": 43.2714, "lon": -2.9726},
    {"id": "metro_cascoviejo", "kind": "metro", "name": "Casco Viejo", "line": "L1/L2/L3", "lat": 43.2589, "lon": -2.9219},
    {"id": "metro_zazpikaleak", "kind": "metro", "name": "Zazpikaleak/Casco Viejo", "line": "L3", "lat": 43.2582, "lon": -2.9239},
    {"id": "metro_matiko", "kind": "metro", "name": "Matiko", "line": "L3", "lat": 43.2701, "lon": -2.9272},
    {"id": "metro_txurdinaga", "kind": "metro", "name": "Txurdinaga", "line": "L3", "lat": 43.2676, "lon": -2.9082},
    {"id": "metro_uribarri", "kind": "metro", "name": "Uribarri", "line": "L3", "lat": 43.2665, "lon": -2.9218},

    {"id": "bus_moyua", "kind": "bus", "name": "Moyua Plaza", "line": "A3247/A3414/Bilbobus", "lat": 43.2638, "lon": -2.9351},
    {"id": "bus_granvia", "kind": "bus", "name": "Gran Vía 46", "line": "Bilbobus", "lat": 43.2628, "lon": -2.9368},
    {"id": "bus_sanmames", "kind": "bus", "name": "Intermodal San Mamés", "line": "Bizkaibus/Bilbobus", "lat": 43.2614, "lon": -2.9498},
    {"id": "bus_abando", "kind": "bus", "name": "Abando / Hurtado de Amézaga", "line": "Bilbobus", "lat": 43.2606, "lon": -2.9258},
    {"id": "bus_ercilla", "kind": "bus", "name": "Ercilla 19", "line": "Bilbobus", "lat": 43.2631, "lon": -2.9398},
    {"id": "bus_deusto", "kind": "bus", "name": "Lehendakari Aguirre", "line": "Bilbobus", "lat": 43.2699, "lon": -2.9694},
    {"id": "bus_cascoviejo", "kind": "bus", "name": "Unamuno", "line": "Bilbobus", "lat": 43.2585, "lon": -2.9246},
    {"id": "bus_indautxu", "kind": "bus", "name": "Doctor Areilza", "line": "Bilbobus", "lat": 43.2635, "lon": -2.9461},
]


def _parse_float(value):
    try:
        return float(str(value).replace(",", ".").strip())
    except Exception:
        return None


def _coords(item: dict) -> tuple[float | None, float | None]:
    return _parse_float(item.get("latitud")), _parse_float(item.get("longitud"))


def distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return round(r * c, 3)


def walk_minutes_from_km(km: float | None) -> int | None:
    if km is None:
        return None
    return max(1, round((km / 4.7) * 60))


def transport_recommendation(km: float | None) -> str:
    if km is None:
        return "Sin datos suficientes"
    if km <= 0.9:
        return "Ir andando"
    if km <= 2.0:
        return "Andando o metro/autobús"
    if km <= 4.0:
        return "Mejor metro/autobús"
    return "Mejor metro/autobús o taxi"


def nearest_stops_for_item(item: dict, kind: str | None = None, limit: int = 3) -> list[dict]:
    lat, lon = _coords(item)
    if lat is None or lon is None:
        return []

    rows = []
    for stop in FALLBACK_STOPS:
        if kind and stop["kind"] != kind:
            continue

        km = distance_km(lat, lon, stop["lat"], stop["lon"])
        rows.append(
            {
                **stop,
                "distance_km": km,
                "walk_minutes": walk_minutes_from_km(km),
                "transport": transport_recommendation(km),
            }
        )

    rows.sort(key=lambda x: x["distance_km"])
    return rows[:limit]


def best_stop(item: dict, kind: str | None = None) -> dict | None:
    rows = nearest_stops_for_item(item, kind=kind, limit=1)
    return rows[0] if rows else None