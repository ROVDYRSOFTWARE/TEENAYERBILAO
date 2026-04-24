from __future__ import annotations

import math
import re
from datetime import date, datetime
from zoneinfo import ZoneInfo

from services import ceremony_host, transit_stops


GROUP_ACTIVITY_TEMPLATES = [
    {
        "id": "icebreaker_cafe",
        "title": "Rompehielo con merienda",
        "objectives": {"conocerse", "desconectar"},
        "energies": {"tranquila", "media"},
        "weathers": {"lluvia", "indiferente", "sol"},
        "group_min": 2,
        "group_max": 8,
        "social_goal": "Facilitar conversación y confianza sin presión.",
        "healthy_reason": "Favorece vínculos sanos, escucha y buen ambiente.",
        "steps": [
            "Cada persona dice una canción, serie o plan favorito.",
            "Elegid una merienda entre todos.",
            "Haced una foto o recuerdo del momento.",
        ],
    },
    {
        "id": "photo_walk",
        "title": "Paseo con reto fotográfico",
        "objectives": {"diversion", "crear", "desconectar"},
        "energies": {"media"},
        "weathers": {"sol", "indiferente"},
        "group_min": 2,
        "group_max": 10,
        "social_goal": "Descubrir la ciudad en grupo y cooperar.",
        "healthy_reason": "Combina movimiento suave, creatividad y conexión social.",
        "steps": [
            "Elegid 3 temas para fotos: color, detalle y grupo.",
            "Cada persona propone una parada.",
            "Al final votad la foto más divertida.",
        ],
    },
    {
        "id": "arcade_team",
        "title": "Reto cooperativo por equipos",
        "objectives": {"diversion", "moverse"},
        "energies": {"media", "alta"},
        "weathers": {"lluvia", "indiferente", "sol"},
        "group_min": 3,
        "group_max": 10,
        "social_goal": "Reírse y colaborar sin competitividad tóxica.",
        "healthy_reason": "Promueve juego sano, cooperación y energía positiva.",
        "steps": [
            "Haced equipos mezclados.",
            "Poned una prueba cooperativa en cada parada.",
            "Terminad compartiendo lo mejor del plan.",
        ],
    },
    {
        "id": "shopping_talk",
        "title": "Compras + charla + merienda",
        "objectives": {"compras", "conocerse", "diversion"},
        "energies": {"tranquila", "media"},
        "weathers": {"lluvia", "indiferente", "sol"},
        "group_min": 2,
        "group_max": 8,
        "social_goal": "Compartir gustos sin presión y pasar una tarde agradable.",
        "healthy_reason": "Mezcla ocio urbano con tiempo para hablar y elegir en grupo.",
        "steps": [
            "Cada persona propone una tienda o rincón.",
            "Elegid una compra simbólica o idea favorita.",
            "Terminad con merienda en sitio tranquilo.",
        ],
    },
    {
        "id": "museum_chat",
        "title": "Museo + conversación + merienda",
        "objectives": {"crear", "conocerse", "desconectar"},
        "energies": {"tranquila", "media"},
        "weathers": {"lluvia", "indiferente", "sol"},
        "group_min": 2,
        "group_max": 8,
        "social_goal": "Dar temas de conversación y descubrir cosas nuevas.",
        "healthy_reason": "Fomenta curiosidad, respeto y conexión entre iguales.",
        "steps": [
            "Cada persona elige una obra, espacio o detalle.",
            "Comentad qué os ha llamado la atención.",
            "Terminad con una parada corta para merendar.",
        ],
    },
    {
        "id": "no_phone_hour",
        "title": "Plan sin móvil 45 minutos",
        "objectives": {"desconectar", "conocerse"},
        "energies": {"tranquila", "media"},
        "weathers": {"indiferente", "lluvia", "sol"},
        "group_min": 2,
        "group_max": 8,
        "social_goal": "Mejorar presencia real y conversación.",
        "healthy_reason": "Reduce distracciones y favorece atención al grupo.",
        "steps": [
            "Guardad el móvil 45 minutos.",
            "Haced preguntas rápidas para conoceros mejor.",
            "Al final decidid si repetiréis el reto.",
        ],
    },
]


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
    return transit_stops.transport_recommendation(distance_km)


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

    if any(x in txt for x in ["restaurante", "cafe", "cafeter", "bubble", "pizza", "burger", "helad", "merienda"]):
        out.add("food")
    if any(x in txt for x in ["museo", "gallery", "expos", "cine", "teatro", "escape", "bolera", "jump", "arcade", "actividad", "deporte"]):
        out.add("activity")
    if any(x in txt for x in ["ropa", "shop", "tienda", "sneaker", "manga", "regalo", "beauty", "compra"]):
        out.add("shopping")
    if any(x in txt for x in ["quedada", "paseo", "park", "parque", "plaza", "mirador", "nightlife"]):
        out.add("meetup")
    if any(x in txt for x in ["museo", "gallery", "visit", "visita"]):
        out.add("visit")

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
        if any(x in txt for x in ["2€", "3€", "4€", "5€"]):
            return 2.0
        return 0.5
    if budget == "medio":
        if "gratis" in txt:
            return 2.0
        if any(x in txt for x in ["2€", "3€", "4€", "5€", "10€"]):
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
    high = any(x in txt for x in ["jump", "bolera", "deporte", "rocod", "parkour", "escape", "arcade"])
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
    txt = _text(item.get("barrio"), item.get("ubicacion"), item.get("direccion"), item.get("descripcion"))
    return 2.0 if zone in txt else 0.6


def _extract_exact_address(text: str) -> str:
    raw = str(text or "")
    if not raw.strip():
        return ""

    patterns = [
        r"(?:dirección|direccion|address)\s*:\s*([^|;\n]+)",
        r"(?:c\/|calle|plaza|avenida|avda\.?|gran vía|gran via|alameda|camino|doctor|licenciado|lehendakari[a]?|sabino arana|luis briñas|tolosa|henao|ercilla|mazarredo|colón|colon)[^|;\n]{0,80}\d+[^\n|;,.]{0,40}",
        r"pol[ií]gono industrial[^|;\n]{0,80}\d+[^\n|;,.]{0,40}",
    ]

    for pattern in patterns:
        m = re.search(pattern, raw, re.I)
        if m:
            value = m.group(1) if m.groups() else m.group(0)
            return re.sub(r"\s+", " ", value).strip(" .,-")

    return ""


def _looks_generic_location(value: str) -> bool:
    low = str(value or "").strip().lower()
    return low in {"", "bilbao", "bizkaia", "vizcaya", "centro de bilbao"}


def _enrich_item(item: dict | None) -> dict | None:
    if not item:
        return None

    row = dict(item)
    exact_from_desc = _extract_exact_address(row.get("descripcion", ""))
    exact_from_ubi = "" if _looks_generic_location(row.get("ubicacion", "")) else _extract_exact_address(row.get("ubicacion", ""))

    display_address = (
        str(row.get("direccion") or "").strip()
        or exact_from_desc
        or exact_from_ubi
        or ""
    )

    display_place = str(row.get("ubicacion") or "").strip()
    if not display_place or display_place == display_address:
        display_place = str(row.get("barrio") or "").strip() or "Bilbao"

    row["_display_address"] = display_address
    row["_display_place"] = display_place
    row["_nearest_metro"] = transit_stops.best_stop(row, "metro")
    row["_nearest_bus"] = transit_stops.best_stop(row, "bus")
    return row


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


def _select_group_activity(prefs: dict) -> dict:
    objective = prefs.get("objective", "diversion")
    energy = prefs.get("energy", "media")
    weather = prefs.get("weather", "indiferente")
    try:
        group_size = int(prefs.get("group_size", 4))
    except Exception:
        group_size = 4

    best = None
    best_score = -999

    for tpl in GROUP_ACTIVITY_TEMPLATES:
        score = 0
        if objective in tpl["objectives"]:
            score += 4
        if energy in tpl["energies"]:
            score += 2
        if weather in tpl["weathers"]:
            score += 2
        if tpl["group_min"] <= group_size <= tpl["group_max"]:
            score += 2

        if score > best_score:
            best_score = score
            best = tpl

    return best or GROUP_ACTIVITY_TEMPLATES[0]


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
        "group_size": 3,
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

    principal = _enrich_item(principal)
    comida = _enrich_item(comida)
    extra = _enrich_item(extra)

    route = _route_summary(principal, comida, extra)
    group_activity = _select_group_activity(today_prefs)
    host_guide = ceremony_host.build_host_guide(
        prefs=today_prefs,
        principal=principal,
        comida=comida,
        extra=extra,
        mode="hoy",
    )

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
        "group_activity": group_activity,
        "host_guide": host_guide,
    }


def _event_bonus(event: dict, prefs: dict) -> float:
    txt = _text(event.get("titulo"), event.get("descripcion"), event.get("categoria"))
    score = 0.0
    score += _budget_score(event, prefs.get("budget", "medio"))
    score += _zone_score(event, prefs.get("zone", ""))
    score += _objective_score(event, prefs.get("objective", "diversion"))

    if prefs.get("weather") == "lluvia" and any(x in txt for x in ["museo", "teatro", "cine", "interior"]):
        score += 1.0

    if prefs.get("energy") == "alta" and any(x in txt for x in ["deporte", "jump", "escape", "bolera", "arcade"]):
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

    objective = prefs.get("objective", "diversion")
    if objective == "compras":
        wanted_extra = {"shopping", "meetup", "food"}
    elif objective == "conocerse":
        wanted_extra = {"meetup", "visit", "food"}
    elif objective == "moverse":
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

    principal = _enrich_item(principal)
    comida = _enrich_item(comida)
    extra = _enrich_item(extra)

    route = _route_summary(principal, comida, extra)
    group_activity = _select_group_activity(prefs)
    host_guide = ceremony_host.build_host_guide(
        prefs=prefs,
        principal=principal,
        comida=comida,
        extra=extra,
        mode="grupo",
    )

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
        "group_activity": group_activity,
        "host_guide": host_guide,
        "summary": {
            "title": "Plan de grupo adolescente",
            "subtitle": explanations.get(objective, "Plan sano y social para grupo."),
            "group_size": prefs.get("group_size"),
            "age_band": prefs.get("age_band"),
            "budget": prefs.get("budget"),
            "energy": prefs.get("energy"),
            "duration": prefs.get("duration"),
        },
        "tips": [
            "Empieza por una dinámica suave para que todo el grupo entre cómodo.",
            "Evita prisas: mejor 2 o 3 paradas buenas que demasiadas.",
            "Si el grupo es nuevo, mezcla conversación + actividad + merienda.",
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
