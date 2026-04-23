from __future__ import annotations

import math
from datetime import date, datetime
from zoneinfo import ZoneInfo


def _today_madrid() -> date:
    return datetime.now(ZoneInfo("Europe/Madrid")).date()


def _text(*parts) -> str:
    return " ".join(str(x or "").strip() for x in parts if str(x or "").strip()).lower()


def _parse_float(value) -> float | None:
    try:
        return float(str(value).replace(",", ".").strip())
    except Exception:
        return None


def _coords(item: dict) -> tuple[float | None, float | None]:
    lat = _parse_float(item.get("latitud"))
    lon = _parse_float(item.get("longitud"))
    return lat, lon


def _distance_km(a: dict | None, b: dict | None) -> float | None:
    if not a or not b:
        return None

    lat1, lon1 = _coords(a)
    lat2, lon2 = _coords(b)
    if lat1 is None or lon1 is None or lat2 is None or lon2 is None:
        return None

    r = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    sa = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(sa), math.sqrt(1 - sa))
    return round(r * c, 2)


def _walk_minutes(distance_km: float | None) -> int | None:
    if distance_km is None:
        return None
    return max(1, round((distance_km / 4.7) * 60))


def _transport_recommendation(distance_km: float | None) -> str:
    if distance_km is None:
        return "Sin datos de coordenadas"
    if distance_km <= 1.2:
        return "Ir andando"
    if distance_km <= 3.0:
        return "Ir andando o en metro/autobús"
    if distance_km <= 6.0:
        return "Mejor metro/autobús o taxi"
    return "Mejor taxi o transporte público"


def _route_leg(origin: dict | None, dest: dict | None) -> dict | None:
    if not origin or not dest:
        return None

    km = _distance_km(origin, dest)
    return {
        "from": origin.get("titulo") or origin.get("nombre") or "",
        "to": dest.get("titulo") or dest.get("nombre") or "",
        "distance_km": km,
        "walk_minutes": _walk_minutes(km),
        "transport": _transport_recommendation(km),
    }


def _route_summary(principal: dict | None, comida: dict | None, extra: dict | None) -> dict:
    legs = []
    leg1 = _route_leg(principal, comida)
    leg2 = _route_leg(comida or principal, extra)
    if leg1:
        legs.append(leg1)
    if leg2:
        legs.append(leg2)

    total_km = 0.0
    total_minutes = 0
    have_data = False
    for leg in legs:
        if leg["distance_km"] is not None:
            total_km += leg["distance_km"]
            have_data = True
        if leg["walk_minutes"] is not None:
            total_minutes += leg["walk_minutes"]

    return {
        "legs": legs,
        "total_km": round(total_km, 2) if have_data else None,
        "total_walk_minutes": total_minutes if have_data else None,
        "overall_transport": _transport_recommendation(round(total_km, 2) if have_data else None),
        "stops_note": "Paradas de metro/autobús pendientes de integrar en una siguiente versión.",
    }


def _bucket(item: dict) -> set[str]:
    txt = _text(
        item.get("categoria"),
        item.get("titulo"),
        item.get("nombre"),
        item.get("descripcion"),
        item.get("tags"),
    )
    out = set()

    if any(x in txt for x in ["restaurante", "cafeter", "cafe", "bubble", "pizza", "burger", "helad", "merienda"]):
        out.add("food")
    if any(x in txt for x in ["museo", "gallery", "expos", "cine", "theatre", "teatro", "escape", "bolera", "jump", "arcade", "actividad", "deporte", "rocod", "bowling"]):
        out.add("activity")
    if any(x in txt for x in ["ropa", "shop", "tienda", "sneaker", "manga", "regalo", "beauty", "compra"]):
        out.add("shopping")
    if any(x in txt for x in ["quedada", "paseo", "park", "parque", "plaza", "mirador"]):
        out.add("meetup")
    if any(x in txt for x in ["museo", "attraction", "gallery", "visit", "visita"]):
        out.add("visit")
    if any(x in txt for x in ["nightlife", "pub", "bar", "discoteca", "nightclub"]):
        out.add("night")
    return out


def _safe_for_teens(item: dict) -> bool:
    txt = _text(
        item.get("categoria"),
        item.get("titulo"),
        item.get("nombre"),
        item.get("descripcion"),
    )
    banned = ["alcohol", "cocktail", "discoteca", "nightclub", "pub crawl", "sexo", "apuesta", "bet"]
    return not any(x in txt for x in banned)


def _budget_score(item: dict, budget: str) -> float:
    txt = _text(item.get("precio_tipo"), item.get("descripcion"))
    if budget == "bajo":
        if "gratis" in txt or "free" in txt:
            return 3.0
        if "2€" in txt or "3€" in txt or "4€" in txt or "5€" in txt:
            return 2.0
        return 0.5
    if budget == "medio":
        if "gratis" in txt:
            return 2.0
        if "2€" in txt or "3€" in txt or "4€" in txt or "5€" in txt or "10€" in txt:
            return 2.5
        return 1.0
    return 1.5


def _weather_score(item: dict, weather: str) -> float:
    if weather == "indiferente":
        return 1.0

    txt = _text(item.get("categoria"), item.get("titulo"), item.get("nombre"), item.get("descripcion"))
    indoor = any(x in txt for x in ["museo", "cine", "bolera", "escape", "cafe", "restaurante", "centro comercial", "interior"])
    outdoor = any(x in txt for x in ["parque", "paseo", "playa", "ruta", "outdoor", "exterior"])

    if weather == "lluvia":
        if indoor:
            return 2.5
        if outdoor:
            return -1.0
    if weather == "sol":
        if outdoor:
            return 2.0
        if indoor:
            return 0.8
    return 1.0


def _energy_score(item: dict, energy: str) -> float:
    txt = _text(item.get("categoria"), item.get("titulo"), item.get("nombre"), item.get("descripcion"))
    high = any(x in txt for x in ["jump", "bolera", "deporte", "rocod", "parkour", "escape"])
    low = any(x in txt for x in ["museo", "cafe", "paseo", "merienda", "cine"])

    if energy == "alta":
        return 2.0 if high else 0.8
    if energy == "tranquila":
        return 2.0 if low else 0.6
    return 1.2


def _objective_score(item: dict, objective: str) -> float:
    buckets = _bucket(item)

    if objective == "diversion":
        return 2.5 if ("activity" in buckets or "shopping" in buckets) else 1.0
    if objective == "conocerse":
        return 2.5 if ("meetup" in buckets or "food" in buckets or "visit" in buckets) else 1.0
    if objective == "moverse":
        return 2.5 if "activity" in buckets else 0.8
    if objective == "crear":
        return 2.0 if ("activity" in buckets or "visit" in buckets) else 1.0
    if objective == "desconectar":
        return 2.0 if ("food" in buckets or "visit" in buckets or "meetup" in buckets) else 1.0
    if objective == "compras":
        return 2.8 if "shopping" in buckets else 0.8
    return 1.0


def _zone_score(item: dict, zone: str) -> float:
    zone = (zone or "").strip().lower()
    if not zone:
        return 1.0
    txt = _text(item.get("barrio"), item.get("ubicacion"), item.get("direccion"))
    return 2.0 if zone in txt else 0.6


def _score_place(item: dict, prefs: dict, profile: dict | None = None) -> float:
    score = 0.0
    score += _budget_score(item, prefs.get("budget", "medio"))
    score += _weather_score(item, prefs.get("weather", "indiferente"))
    score += _energy_score(item, prefs.get("energy", "media"))
    score += _objective_score(item, prefs.get("objective", "diversion"))
    score += _zone_score(item, prefs.get("zone", ""))

    if profile:
        gustos = profile.get("gustos", {})
        barrios = profile.get("barrios", {})
        franjas = profile.get("franjas", {})
        score += float(gustos.get(item.get("categoria"), 0)) * 1.0
        score += float(barrios.get(item.get("barrio"), 0)) * 0.7
        score += float(franjas.get(item.get("franja"), 0)) * 0.5

    if not _safe_for_teens(item):
        score -= 100

    return round(score, 3)


def _pick_best(candidates: list[dict], used_ids: set[str], wanted: set[str], prefs: dict, profile: dict | None) -> dict | None:
    pool = []
    for item in candidates:
        if item.get("id") in used_ids:
            continue
        buckets = _bucket(item)
        if not (buckets & wanted):
            continue
        pool.append((item, _score_place(item, prefs, profile)))

    if not pool:
        return None

    pool.sort(key=lambda x: x[1], reverse=True)
    chosen = pool[0][0]
    used_ids.add(chosen.get("id"))
    return chosen


def _pick_near_zone(candidates: list[dict], used_ids: set[str], wanted: set[str], zone_hint: str, prefs: dict, profile: dict | None) -> dict | None:
    prefs_local = dict(prefs)
    if zone_hint:
        prefs_local["zone"] = zone_hint
    return _pick_best(candidates, used_ids, wanted, prefs_local, profile)


def enrich_today_plan(token: str, plan: dict, events: list[dict], places: list[dict], profile: dict | None = None) -> dict:
    plan = dict(plan or {})
    used_ids: set[str] = set()

    principal = plan.get("principal")
    comida = plan.get("comida")
    extra = plan.get("extra")

    if principal and principal.get("id"):
        used_ids.add(principal["id"])
    if comida and comida.get("id"):
        used_ids.add(comida["id"])
    if extra and extra.get("id"):
        used_ids.add(extra["id"])

    safe_places = [x for x in places if _safe_for_teens(x)]

    today_prefs = {
        "budget": "medio",
        "energy": "media",
        "objective": "diversion",
        "weather": "indiferente",
        "zone": principal.get("barrio", "") if principal else "",
    }

    if principal is None:
        principal = _pick_best(
            safe_places,
            used_ids,
            {"activity", "visit", "shopping", "meetup"},
            today_prefs,
            profile,
        )

    zone_hint = principal.get("barrio", "") if principal else ""

    if comida is None:
        comida = _pick_near_zone(
            safe_places,
            used_ids,
            {"food"},
            zone_hint,
            today_prefs,
            profile,
        )

    if extra is None:
        extra = _pick_near_zone(
            safe_places,
            used_ids,
            {"shopping", "visit", "activity", "meetup"},
            zone_hint,
            today_prefs,
            profile,
        )

    route = _route_summary(principal, comida, extra)

    return {
        "principal": principal,
        "comida": comida,
        "extra": extra,
        "ranked": plan.get("ranked", []),
        "summary": {
            "title": "Plan equilibrado para hoy",
            "subtitle": "Actividad principal + parada para comer o merendar + extra saludable",
        },
        "route": route,
    }


def _event_bonus(event: dict, prefs: dict) -> float:
    txt = _text(event.get("titulo"), event.get("descripcion"), event.get("categoria"))
    score = 0.0
    score += _budget_score(event, prefs.get("budget", "medio"))
    score += _zone_score(event, prefs.get("zone", ""))
    score += _objective_score(event, prefs.get("objective", "diversion"))

    if prefs.get("weather") == "lluvia" and any(x in txt for x in ["museo", "teatro", "cine", "interior"]):
        score += 1.0

    if prefs.get("energy") == "alta" and any(x in txt for x in ["deporte", "jump", "escape", "bolera"]):
        score += 1.0

    if not _safe_for_teens(event):
        score -= 100

    return round(score, 3)


def _pick_group_event(events: list[dict], prefs: dict) -> dict | None:
    if not events:
        return None
    scored = [(e, _event_bonus(e, prefs)) for e in events if _safe_for_teens(e)]
    if not scored:
        return None
    scored.sort(key=lambda x: x[1], reverse=True)
    if scored[0][1] < 0:
        return None
    return scored[0][0]


def build_group_plan(token: str, events: list[dict], places: list[dict], profile: dict | None, prefs: dict) -> dict:
    safe_places = [x for x in places if _safe_for_teens(x)]
    used_ids: set[str] = set()

    principal = None
    if prefs.get("objective") in {"diversion", "crear", "moverse"}:
        principal = _pick_group_event(events, prefs)

    if principal:
        used_ids.add(principal.get("id"))

    if principal is None:
        principal = _pick_best(
            safe_places,
            used_ids,
            {"activity", "visit", "shopping", "meetup"},
            prefs,
            profile,
        )

    zone_hint = principal.get("barrio", "") if principal else prefs.get("zone", "")

    comida = _pick_near_zone(
        safe_places,
        used_ids,
        {"food"},
        zone_hint,
        prefs,
        profile,
    )

    extra_objective = prefs.get("objective", "diversion")
    if extra_objective == "compras":
        wanted_extra = {"shopping", "meetup", "food"}
    elif extra_objective == "conocerse":
        wanted_extra = {"meetup", "visit", "food"}
    elif extra_objective == "moverse":
        wanted_extra = {"activity", "meetup", "visit"}
    else:
        wanted_extra = {"shopping", "visit", "activity", "meetup"}

    extra = _pick_near_zone(
        safe_places,
        used_ids,
        wanted_extra,
        zone_hint,
        prefs,
        profile,
    )

    route = _route_summary(principal, comida, extra)

    explanations = {
        "diversion": "He priorizado un plan dinámico, variado y fácil de compartir con amigos.",
        "conocerse": "He priorizado sitios que favorecen conversación, cooperación y buen ambiente.",
        "moverse": "He priorizado actividades activas y con energía sana para el grupo.",
        "crear": "He buscado un plan que combine descubrir, inspirarse y hacer algo distinto.",
        "desconectar": "He elegido un plan suave, cómodo y sin presión para pasar una buena tarde.",
        "compras": "He combinado un plan de ocio con una parte de tiendas y descubrimiento urbano.",
    }

    return {
        "prefs": prefs,
        "principal": principal,
        "comida": comida,
        "extra": extra,
        "route": route,
        "summary": {
            "title": "Plan de grupo adolescente",
            "subtitle": explanations.get(prefs.get("objective", "diversion"), "Plan sano y social para grupo."),
            "group_size": prefs.get("group_size"),
            "age_band": prefs.get("age_band"),
            "budget": prefs.get("budget"),
            "energy": prefs.get("energy"),
            "duration": prefs.get("duration"),
        },
        "tips": [
            "Propón una foto de grupo o mini reto cooperativo al inicio.",
            "Evita meter demasiadas paradas para que el plan no se haga pesado.",
            "Si el grupo es nuevo, empieza por un sitio donde hablar sea fácil.",
        ],
    }


def group_mode_cards() -> list[dict]:
    return [
        {
            "title": "Grupo nuevo",
            "text": "Ideal para adolescentes que todavía no se conocen mucho. Prioriza buen ambiente y conversación.",
        },
        {
            "title": "Lluvia sin aburrimiento",
            "text": "Ideas de interior, actividad suave y merienda para tardes de mal tiempo.",
        },
        {
            "title": "Moverse y reírse",
            "text": "Planes activos con energía sana: bolera, salto, retos cooperativos o deporte suave.",
        },
        {
            "title": "Compras + merienda",
            "text": "Para grupos a los que les apetece pasear, descubrir tiendas y terminar en un sitio agradable.",
        },
    ]