from __future__ import annotations

from collections import Counter
from datetime import date, datetime
from typing import Iterable
from zoneinfo import ZoneInfo

from services import data_store


def _ensure_profile(profiles: dict, token: str) -> dict:
    return profiles.setdefault(token, {
        "created_at": data_store.now_iso(),
        "updated_at": data_store.now_iso(),
        "gustos": {},
        "barrios": {},
        "franjas": {},
        "presupuesto": {},
        "tags": {},
        "acciones": 0,
    })


def _bump(bucket: dict, key: str | None, amount: float = 1.0) -> None:
    if not key:
        return
    bucket[key] = round(float(bucket.get(key, 0)) + amount, 3)


def _iter_tags(item: dict) -> Iterable[str]:
    tags = item.get("tags", [])
    if isinstance(tags, str):
        tags = [part.strip() for part in tags.split(",") if part.strip()]
    return [str(x).strip() for x in tags if str(x).strip()]


def _today_madrid() -> date:
    return datetime.now(ZoneInfo("Europe/Madrid")).date()


def _parse_event_date(value: str) -> date | None:
    if not value:
        return None

    raw = str(value).strip()
    if not raw:
        return None

    try:
        return datetime.strptime(raw[:10], "%Y-%m-%d").date()
    except Exception:
        pass

    try:
        return datetime.strptime(raw[:10], "%d/%m/%Y").date()
    except Exception:
        pass

    try:
        return datetime.fromisoformat(raw.replace("Z", "+00:00")).date()
    except Exception:
        pass

    return None


def _future_events(events: list[dict]) -> list[dict]:
    hoy = _today_madrid()
    salida = []

    for ev in events:
        fecha = _parse_event_date(ev.get("fecha", ""))
        if fecha and fecha >= hoy:
            salida.append(ev)

    salida.sort(key=lambda x: (_parse_event_date(x.get("fecha", "")) or date.max, x.get("titulo", "")))
    return salida


def learn_from_item(token: str, item: dict, action: str = "view") -> None:
    profiles = data_store.load_profiles()
    profile = _ensure_profile(profiles, token)
    weight = {"view": 1.0, "click": 1.5, "like": 3.0, "dislike": -2.0}.get(action, 1.0)

    _bump(profile["gustos"], item.get("categoria"), weight)
    _bump(profile["barrios"], item.get("barrio"), weight)
    _bump(profile["franjas"], item.get("franja"), weight)
    _bump(profile["presupuesto"], item.get("precio_tipo"), weight)

    for tag in _iter_tags(item):
        _bump(profile["tags"], tag, weight)

    profile["acciones"] = int(profile.get("acciones", 0)) + 1
    profile["updated_at"] = data_store.now_iso()
    data_store.save_profiles(profiles)

    data_store.append_interaction({
        "ts": data_store.now_iso(),
        "token": token,
        "action": action,
        "entity_type": item.get("_entity_type", "contenido"),
        "entity_id": item.get("id", ""),
        "categoria": item.get("categoria", ""),
        "barrio": item.get("barrio", ""),
        "franja": item.get("franja", ""),
    })


def set_manual_preferences(
    token: str,
    categorias: list[str],
    barrios: list[str],
    franjas: list[str],
    presupuesto: list[str],
) -> None:
    profiles = data_store.load_profiles()
    profile = _ensure_profile(profiles, token)

    # Sustituye completamente la selección manual actual
    profile["gustos"] = {value: 3.0 for value in categorias if str(value).strip()}
    profile["barrios"] = {value: 2.0 for value in barrios if str(value).strip()}
    profile["franjas"] = {value: 2.0 for value in franjas if str(value).strip()}
    profile["presupuesto"] = {value: 2.0 for value in presupuesto if str(value).strip()}

    profile["updated_at"] = data_store.now_iso()
    data_store.save_profiles(profiles)

    data_store.append_interaction({
        "ts": data_store.now_iso(),
        "token": token,
        "action": "preferences_set",
        "entity_type": "profile",
        "entity_id": token,
        "categoria": ",".join(categorias),
        "barrio": ",".join(barrios),
        "franja": ",".join(franjas),
    })


def get_profile(token: str) -> dict:
    profiles = data_store.load_profiles()
    return profiles.get(token, {
        "gustos": {},
        "barrios": {},
        "franjas": {},
        "presupuesto": {},
        "tags": {},
        "acciones": 0,
    })


def popularity_map() -> Counter:
    counter = Counter()
    for row in data_store.load_interactions():
        key = f"{row.get('entity_type')}:{row.get('entity_id')}"
        counter[key] += 1
    return counter


def score_item(profile: dict, item: dict, popularity_counter: Counter | None = None) -> float:
    score = 0.0
    score += float(profile.get("gustos", {}).get(item.get("categoria"), 0)) * 3.0
    score += float(profile.get("barrios", {}).get(item.get("barrio"), 0)) * 2.0
    score += float(profile.get("franjas", {}).get(item.get("franja"), 0)) * 1.5
    score += float(profile.get("presupuesto", {}).get(item.get("precio_tipo"), 0)) * 1.5

    for tag in _iter_tags(item):
        score += float(profile.get("tags", {}).get(tag, 0)) * 1.2

    if popularity_counter:
        key = f"{item.get('_entity_type', 'contenido')}:{item.get('id')}"
        score += min(popularity_counter.get(key, 0), 20) * 0.2

    if item.get("_entity_type") == "evento":
        fecha = _parse_event_date(item.get("fecha", ""))
        if fecha:
            days_delta = (fecha - _today_madrid()).days
            if 0 <= days_delta <= 7:
                score += 3
            elif days_delta < 0:
                score -= 2

    # Bonus ligero por afinidad adolescente si existe
    try:
        score += min(float(item.get("teen_score", 0) or 0) * 0.15, 2.0)
    except Exception:
        pass

    return round(score, 3)


def rank_items(token: str, events: list[dict], places: list[dict]) -> list[dict]:
    profile = get_profile(token)
    pop = popularity_map()
    ranked = []

    for item in events + places:
        row = dict(item)
        row["score"] = score_item(profile, row, pop)
        ranked.append(row)

    ranked.sort(key=lambda x: (x.get("score", 0), x.get("fecha", "")), reverse=True)
    return ranked


def plan_hoy(token: str, events: list[dict], places: list[dict]) -> dict:
    eventos_futuros = _future_events(events)
    ranked = rank_items(token, eventos_futuros, places)

    principal = next((x for x in ranked if x.get("_entity_type") == "evento"), None)

    if principal:
        barrio_ref = principal.get("barrio")
        compatibles = [
            x for x in ranked
            if x.get("_entity_type") == "lugar"
            and (not barrio_ref or x.get("barrio") == barrio_ref)
        ]
    else:
        compatibles = [x for x in ranked if x.get("_entity_type") == "lugar"]

        principal = next(
            (
                x for x in compatibles
                if x.get("categoria") in {
                    "actividad", "bolera", "escape-room", "arcade", "cine",
                    "museo", "jump-park", "deporte", "quedada"
                }
            ),
            None,
        )

        if principal and principal in compatibles:
            compatibles = [x for x in compatibles if x != principal]

    comida = next(
        (
            x for x in compatibles
            if x.get("categoria") in {
                "comida", "cafe", "bubble-tea", "restaurante",
                "cafeteria", "heladeria", "hamburgueseria", "pizza", "merendar"
            }
        ),
        None,
    )

    extra = next(
        (
            x for x in compatibles
            if x != comida and x != principal
            and x.get("categoria") in {
                "actividad", "bolera", "escape-room", "arcade", "cine",
                "museo", "compras", "ropa", "sneakers", "manga", "regalos",
                "quedada", "paseo"
            }
        ),
        None,
    )

    return {
        "principal": principal,
        "comida": comida,
        "extra": extra,
        "ranked": ranked[:12],
    }


def stats_summary() -> dict:
    events = data_store.load_events()
    places = data_store.load_places()
    interactions = data_store.load_interactions()
    profiles = data_store.load_profiles()

    by_category, by_barrio, by_action = Counter(), Counter(), Counter()

    for item in events + places:
        by_category[item.get("categoria", "sin_categoria")] += 1
        by_barrio[item.get("barrio", "sin_barrio")] += 1

    for row in interactions:
        by_action[row.get("action", "sin_accion")] += 1

    return {
        "events_total": len(events),
        "places_total": len(places),
        "profiles_total": len(profiles),
        "interactions_total": len(interactions),
        "by_category": dict(by_category.most_common()),
        "by_barrio": dict(by_barrio.most_common()),
        "by_action": dict(by_action.most_common()),
    }
