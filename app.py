from __future__ import annotations

import os
import re
import uuid
from datetime import date, datetime
from functools import wraps
from zoneinfo import ZoneInfo

from flask import (
    Flask,
    Response,
    abort,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from services import auto_update, data_store, geocode, recommender, group_planner

app = Flask(__name__)
app.secret_key = "teenayer-bilbao-local"
app.config["ADMIN_PASSWORD"] = os.getenv("ADMIN_PASSWORD", "admin1234")

data_store.init_files()


def current_token() -> str:
    return request.cookies.get("tb_token") or f"session_{uuid.uuid4().hex[:12]}"


def _top_bucket_items(bucket: dict, limit: int = 3) -> list[str]:
    if not bucket:
        return []

    ordered = sorted(
        [(str(k).strip(), float(v)) for k, v in bucket.items() if str(k).strip()],
        key=lambda x: (-x[1], x[0].lower()),
    )
    return [name for name, _score in ordered[:limit]]


def build_profile_preview(profile: dict) -> dict:
    return {
        "gustos": _top_bucket_items(profile.get("gustos", {}), 3),
        "barrios": _top_bucket_items(profile.get("barrios", {}), 3),
        "franjas": _top_bucket_items(profile.get("franjas", {}), 3),
        "presupuesto": _top_bucket_items(profile.get("presupuesto", {}), 3),
    }


def render_with_token(template_name: str, **context):
    token = current_token()
    response = make_response(render_template(template_name, token=token, **context))
    if "tb_token" not in request.cookies:
        response.set_cookie("tb_token", token, max_age=60 * 60 * 24 * 365)
    return response


def build_maps_url(item: dict) -> str:
    maps_url = (item.get("maps_url") or "").strip()
    if maps_url:
        return maps_url

    lat = str(item.get("latitud") or "").strip()
    lon = str(item.get("longitud") or "").strip()
    if lat and lon:
        return f"https://www.google.com/maps?q={lat},{lon}"

    query = ", ".join(
        [x for x in [item.get("ubicacion"), item.get("direccion"), item.get("barrio"), "Bilbao"] if x]
    )
    if query:
        from urllib.parse import quote_plus

        return f"https://www.google.com/maps/search/?api=1&query={quote_plus(query)}"

    return ""


def build_osm_embed_url(item: dict) -> str:
    lat = str(item.get("latitud") or "").strip()
    lon = str(item.get("longitud") or "").strip()
    if not (lat and lon):
        return ""

    try:
        latf = float(lat)
        lonf = float(lon)
    except Exception:
        return ""

    delta = 0.0035
    left = lonf - delta
    right = lonf + delta
    bottom = latf - delta
    top = latf + delta

    return (
        "https://www.openstreetmap.org/export/embed.html?bbox="
        f"{left},{bottom},{right},{top}&layer=mapnik&marker={latf},{lonf}"
    )


def event_rows():
    return [
        dict(
            row,
            _entity_type="evento",
            _maps_url=build_maps_url(row),
            _embed_url=build_osm_embed_url(row),
        )
        for row in data_store.load_events()
    ]


def place_rows():
    return [
        dict(
            row,
            _entity_type="lugar",
            _maps_url=build_maps_url(row),
            _embed_url=build_osm_embed_url(row),
        )
        for row in data_store.load_places()
    ]


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


def _parse_spanish_title_date(title: str) -> date | None:
    if not title:
        return None

    meses = {
        "enero": 1,
        "febrero": 2,
        "marzo": 3,
        "abril": 4,
        "mayo": 5,
        "junio": 6,
        "julio": 7,
        "agosto": 8,
        "septiembre": 9,
        "setiembre": 9,
        "octubre": 10,
        "noviembre": 11,
        "diciembre": 12,
    }

    raw = str(title).strip().lower()
    m = re.search(r"(\d{1,2})\s+de\s+([a-záéíóú]+)", raw)
    if not m:
        return None

    dia = int(m.group(1))
    mes_txt = m.group(2)
    mes = meses.get(mes_txt)
    if not mes:
        return None

    hoy = _today_madrid()
    year = hoy.year

    try:
        fecha = date(year, mes, dia)
    except Exception:
        return None

    if (fecha - hoy).days > 180:
        try:
            fecha = date(year - 1, mes, dia)
        except Exception:
            return None

    return fecha


def _row_event_date(row: dict) -> date | None:
    return _parse_event_date(row.get("fecha", "")) or _parse_spanish_title_date(row.get("titulo", ""))


def _event_sort_key(row: dict):
    fecha = _row_event_date(row)
    return (fecha or date.max, row.get("titulo", ""))


def upcoming_event_rows():
    hoy = _today_madrid()
    salida = []

    for row in event_rows():
        fecha = _row_event_date(row)
        if fecha and fecha >= hoy:
            salida.append(row)

    return salida


def _sorted_unique(values):
    return sorted({str(v).strip() for v in values if str(v).strip()}, key=lambda x: x.lower())


def _append_if_missing(options: list[str], value: str | None) -> list[str]:
    value = (value or "").strip()
    if value and value not in options:
        return sorted(options + [value], key=lambda x: x.lower())
    return options


def current_choice_options(event_item: dict | None = None, place_item: dict | None = None):
    events = data_store.load_events()
    places = data_store.load_places()
    all_items = events + places

    categorias = _sorted_unique([x.get("categoria", "") for x in all_items])
    barrios = _sorted_unique([x.get("barrio", "") for x in all_items])
    franjas = _sorted_unique([x.get("franja", "") for x in all_items])
    presupuesto = _sorted_unique([x.get("precio_tipo", "") for x in all_items])

    if event_item:
        categorias = _append_if_missing(categorias, event_item.get("categoria"))
        barrios = _append_if_missing(barrios, event_item.get("barrio"))
        franjas = _append_if_missing(franjas, event_item.get("franja"))
        presupuesto = _append_if_missing(presupuesto, event_item.get("precio_tipo"))

    if place_item:
        categorias = _append_if_missing(categorias, place_item.get("categoria"))
        barrios = _append_if_missing(barrios, place_item.get("barrio"))
        franjas = _append_if_missing(franjas, place_item.get("franja"))
        presupuesto = _append_if_missing(presupuesto, place_item.get("precio_tipo"))

    return {
        "categorias": categorias,
        "barrios": barrios,
        "franjas": franjas,
        "presupuesto": presupuesto,
    }


def form_list(name: str):
    values = request.form.get(name, "")
    return [x.strip() for x in values.split(",") if x.strip()]


def enrich_location_fields(payload: dict) -> dict:
    payload = dict(payload)

    lat = (payload.get("latitud") or "").strip()
    lon = (payload.get("longitud") or "").strip()

    if lat and lon:
        if not (payload.get("maps_url") or "").strip():
            payload["maps_url"] = build_maps_url(payload)
        return payload

    query = ", ".join(
        [x for x in [payload.get("ubicacion"), payload.get("direccion"), payload.get("barrio"), "Bilbao"] if x]
    )
    geo = geocode.geocode(query)
    if geo:
        payload["latitud"] = payload.get("latitud") or geo.get("latitud", "")
        payload["longitud"] = payload.get("longitud") or geo.get("longitud", "")

    if not (payload.get("maps_url") or "").strip():
        payload["maps_url"] = build_maps_url(payload)

    return payload


def admin_required(func):
    @wraps(func)
    def wrapper(*args, **kwargs):
        if not session.get("admin_ok"):
            return redirect(url_for("admin_login", next=request.path))
        return func(*args, **kwargs)

    return wrapper


@app.before_request
def session_auto_update_check():
    if request.path.startswith("/admin") or request.path.startswith("/static"):
        return

    if session.get("auto_update_checked") == data_store.now_iso()[:10]:
        return

    session["auto_update_checked"] = data_store.now_iso()[:10]
    auto_update.maybe_start("session_start", force=False)


auto_update.maybe_start("app_start", force=False)


@app.route("/healthz")
def healthz():
    return {"ok": True}


@app.route("/tasks/auto-update", methods=["GET", "POST"])
def task_auto_update():
    token = (request.args.get("token") or request.headers.get("X-Cron-Token") or "").strip()
    expected = (os.getenv("CRON_SECRET") or "").strip()
    force = (request.args.get("force") or request.headers.get("X-Force-Update") or "0").strip() == "1"

    if not expected or token != expected:
        abort(403)

    started = auto_update.maybe_start(
        "scheduled_task_force" if force else "scheduled_task",
        force=force,
    )
    return {"ok": True, "started": bool(started), "force": force}


@app.route("/")
def home():
    token = current_token()
    ranked = recommender.rank_items(token, upcoming_event_rows(), place_rows())[:6]
    return render_with_token("home.html", ranked=ranked)


@app.route("/eventos")
def eventos():
    rows = sorted(upcoming_event_rows(), key=_event_sort_key)
    return render_with_token("eventos.html", title="Eventos", items=rows)


@app.route("/lugares")
def lugares():
    rows = sorted(place_rows(), key=lambda x: (x.get("barrio", ""), x.get("nombre", "")))
    return render_with_token("lugares.html", title="Lugares", items=rows)


@app.route("/evento/<event_id>")
def evento_detalle(event_id: str):
    item = data_store.get_event(event_id)
    if not item:
        return "Evento no encontrado", 404

    row = dict(
        item,
        _entity_type="evento",
        _maps_url=build_maps_url(item),
        _embed_url=build_osm_embed_url(item),
    )
    recommender.learn_from_item(current_token(), row, "view")
    return render_with_token("detalle_evento.html", item=row)


@app.route("/lugar/<place_id>")
def lugar_detalle(place_id: str):
    item = data_store.get_place(place_id)
    if not item:
        return "Lugar no encontrado", 404

    row = dict(
        item,
        _entity_type="lugar",
        _maps_url=build_maps_url(item),
        _embed_url=build_osm_embed_url(item),
    )
    recommender.learn_from_item(current_token(), row, "view")
    return render_with_token("detalle_lugar.html", item=row)


@app.route("/accion/<entity_type>/<entity_id>/<action>")
def accion(entity_type: str, entity_id: str, action: str):
    item = data_store.get_event(entity_id) if entity_type == "evento" else data_store.get_place(entity_id)
    if not item:
        return "Contenido no encontrado", 404

    row = dict(item, _entity_type=entity_type)
    recommender.learn_from_item(current_token(), row, action)
    flash("Preferencia registrada.")
    return redirect(
        url_for("evento_detalle", event_id=entity_id)
        if entity_type == "evento"
        else url_for("lugar_detalle", place_id=entity_id)
    )


@app.route("/preferencias", methods=["GET", "POST"])
def preferencias():
    token = current_token()
    options = current_choice_options()

    if request.method == "POST":
        categorias = request.form.getlist("categorias")
        barrios = request.form.getlist("barrios")
        franjas = request.form.getlist("franjas")
        presupuesto = request.form.getlist("presupuesto")

        recommender.apply_preferences(
            token,
            categorias,
            barrios,
            franjas,
            presupuesto,
        )
        data_store.append_audit("preferencias_update", "profile", token, {"source": "manual_form"})
        flash("Preferencias guardadas.")
        return redirect(url_for("recomendado"))

    profile = recommender.get_profile(token)
    return render_with_token("preferencias.html", profile=profile, options=options)


@app.route("/recomendado")
def recomendado():
    token = current_token()
    ranked = recommender.rank_items(token, upcoming_event_rows(), place_rows())[:20]
    profile = recommender.get_profile(token)
    profile_preview = build_profile_preview(profile)
    return render_with_token(
        "recomendado.html",
        items=ranked,
        profile=profile,
        profile_preview=profile_preview,
    )


@app.route("/plan-hoy")
def plan_hoy():
    token = current_token()
    base_plan = recommender.plan_hoy(token, event_rows(), place_rows())
    plan = group_planner.enrich_today_plan(
        token=token,
        plan=base_plan,
        events=upcoming_event_rows(),
        places=place_rows(),
        profile=recommender.get_profile(token),
    )
    return render_with_token("plan_hoy.html", plan=plan)


@app.route("/plan-grupo", methods=["GET", "POST"])
def plan_grupo():
    token = current_token()
    defaults = {
        "group_size": 4,
        "age_band": "14-17",
        "budget": "medio",
        "energy": "media",
        "objective": "diversion",
        "weather": "indiferente",
        "duration": "tarde",
        "zone": "",
    }

    form_data = dict(defaults)
    plan = None

    if request.method == "POST":
        form_data = {
            "group_size": request.form.get("group_size", "4").strip(),
            "age_band": request.form.get("age_band", "14-17").strip(),
            "budget": request.form.get("budget", "medio").strip(),
            "energy": request.form.get("energy", "media").strip(),
            "objective": request.form.get("objective", "diversion").strip(),
            "weather": request.form.get("weather", "indiferente").strip(),
            "duration": request.form.get("duration", "tarde").strip(),
            "zone": request.form.get("zone", "").strip(),
        }

        profile = recommender.get_profile(token)
        plan = group_planner.build_group_plan(
            token=token,
            events=upcoming_event_rows(),
            places=place_rows(),
            profile=profile,
            prefs=form_data,
        )

    return render_with_token(
        "plan_grupo.html",
        form_data=form_data,
        plan=plan,
        plan_modes=group_planner.group_mode_cards(),
    )


@app.route("/admin/login", methods=["GET", "POST"])
def admin_login():
    if request.method == "POST":
        password = request.form.get("password", "")
        if password == app.config["ADMIN_PASSWORD"]:
            session["admin_ok"] = True
            flash("Acceso administrador concedido.")
            return redirect(request.args.get("next") or url_for("admin"))
        flash("Contraseña incorrecta.")
    return render_template("admin_login.html")


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin_ok", None)
    flash("Sesión de administrador cerrada.")
    return redirect(url_for("home"))


@app.route("/admin")
@admin_required
def admin():
    stats = recommender.stats_summary()
    sync = data_store.load_sync()
    return render_template("admin.html", stats=stats, sync=sync)


@app.route("/admin/contenidos")
@admin_required
def admin_contenidos():
    return render_template(
        "admin_contenidos.html",
        events=data_store.load_events(),
        places=data_store.load_places(),
    )


@app.route("/admin/actualizar-ahora", methods=["POST"])
@admin_required
def admin_actualizar_ahora():
    started = auto_update.maybe_start("manual_admin", force=True)
    flash(
        "Actualización forzada lanzada en segundo plano."
        if started
        else "Ya había una actualización en curso."
    )
    return redirect(url_for("admin"))


@app.route("/admin/eventos/nuevo", methods=["GET", "POST"])
@app.route("/admin/eventos/editar/<event_id>", methods=["GET", "POST"])
@admin_required
def admin_evento_form(event_id: str | None = None):
    item = data_store.get_event(event_id) if event_id else None
    options = current_choice_options(event_item=item)

    if request.method == "POST":
        payload = {
            "id": request.form.get("id", "").strip() or None,
            "titulo": request.form.get("titulo", "").strip(),
            "fecha": request.form.get("fecha", "").strip(),
            "barrio": request.form.get("barrio", "").strip(),
            "categoria": request.form.get("categoria", "").strip(),
            "franja": request.form.get("franja", "").strip(),
            "precio_tipo": request.form.get("precio_tipo", "").strip(),
            "ubicacion": request.form.get("ubicacion", "").strip(),
            "direccion": request.form.get("direccion", "").strip(),
            "punto_quedada": request.form.get("punto_quedada", "").strip(),
            "latitud": request.form.get("latitud", "").strip(),
            "longitud": request.form.get("longitud", "").strip(),
            "maps_url": request.form.get("maps_url", "").strip(),
            "fuente": request.form.get("fuente", "").strip(),
            "descripcion": request.form.get("descripcion", "").strip(),
            "url": request.form.get("url", "").strip(),
            "tags": form_list("tags"),
            "auto_source": request.form.get("auto_source") == "1",
        }
        payload = enrich_location_fields(payload)
        saved = data_store.upsert_event(payload)
        data_store.append_audit(
            "evento_update" if payload.get("id") else "evento_create",
            "evento",
            saved["id"],
            {"titulo": saved["titulo"]},
        )
        flash("Evento guardado.")
        return redirect(url_for("admin_contenidos"))

    return render_template("admin_form_evento.html", item=item, options=options)


@app.route("/admin/lugares/nuevo", methods=["GET", "POST"])
@app.route("/admin/lugares/editar/<place_id>", methods=["GET", "POST"])
@admin_required
def admin_lugar_form(place_id: str | None = None):
    item = data_store.get_place(place_id) if place_id else None
    options = current_choice_options(place_item=item)

    if request.method == "POST":
        payload = {
            "id": request.form.get("id", "").strip() or None,
            "nombre": request.form.get("nombre", "").strip(),
            "barrio": request.form.get("barrio", "").strip(),
            "categoria": request.form.get("categoria", "").strip(),
            "franja": request.form.get("franja", "").strip(),
            "precio_tipo": request.form.get("precio_tipo", "").strip(),
            "ubicacion": request.form.get("ubicacion", "").strip(),
            "direccion": request.form.get("direccion", "").strip(),
            "horario": request.form.get("horario", "").strip(),
            "latitud": request.form.get("latitud", "").strip(),
            "longitud": request.form.get("longitud", "").strip(),
            "maps_url": request.form.get("maps_url", "").strip(),
            "fuente": request.form.get("fuente", "").strip(),
            "descripcion": request.form.get("descripcion", "").strip(),
            "url": request.form.get("url", "").strip(),
            "tags": form_list("tags"),
        }
        payload = enrich_location_fields(payload)
        saved = data_store.upsert_place(payload)
        data_store.append_audit(
            "lugar_update" if payload.get("id") else "lugar_create",
            "lugar",
            saved["id"],
            {"nombre": saved["nombre"]},
        )
        flash("Lugar guardado.")
        return redirect(url_for("admin_contenidos"))

    return render_template("admin_form_lugar.html", item=item, options=options)


@app.route("/admin/eventos/eliminar/<event_id>", methods=["POST"])
@admin_required
def admin_evento_delete(event_id: str):
    if data_store.delete_event(event_id):
        data_store.append_audit("evento_delete", "evento", event_id, {})
        flash("Evento eliminado.")
    return redirect(url_for("admin_contenidos"))


@app.route("/admin/lugares/eliminar/<place_id>", methods=["POST"])
@admin_required
def admin_lugar_delete(place_id: str):
    if data_store.delete_place(place_id):
        data_store.append_audit("lugar_delete", "lugar", place_id, {})
        flash("Lugar eliminado.")
    return redirect(url_for("admin_contenidos"))


@app.route("/admin/auditoria")
@admin_required
def admin_auditoria():
    return render_template(
        "admin_auditoria.html",
        audit_rows=list(reversed(data_store.load_audit()))[:200],
        interactions=list(reversed(data_store.load_interactions()))[:100],
        stats=recommender.stats_summary(),
    )


@app.route("/admin/export/auditoria.csv")
@admin_required
def export_auditoria():
    payload = [
        {
            "ts": r.get("ts", ""),
            "action": r.get("action", ""),
            "entity_type": r.get("entity_type", ""),
            "entity_id": r.get("entity_id", ""),
            "meta": str(r.get("meta", {})),
        }
        for r in data_store.load_audit()
    ]
    return Response(
        data_store.csv_bytes(payload),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=auditoria.csv"},
    )


@app.route("/admin/export/estadisticas.csv")
@admin_required
def export_estadisticas():
    stats = recommender.stats_summary()
    rows = [
        {"metric": "events_total", "value": stats["events_total"]},
        {"metric": "places_total", "value": stats["places_total"]},
        {"metric": "profiles_total", "value": stats["profiles_total"]},
        {"metric": "interactions_total", "value": stats["interactions_total"]},
    ]

    for dkey in ("by_category", "by_barrio", "by_action"):
        for key, value in stats[dkey].items():
            rows.append({"metric": f"{dkey}:{key}", "value": value})

    return Response(
        data_store.csv_bytes(rows),
        mimetype="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=estadisticas.csv"},
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.getenv("PORT", "5000")), debug=False)
