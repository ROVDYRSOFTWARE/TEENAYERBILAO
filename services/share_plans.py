from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import quote_plus


def _data_root() -> Path:
    root = os.getenv("DATA_ROOT", "/var/data/teenayer/data")
    path = Path(root)
    path.mkdir(parents=True, exist_ok=True)
    return path


SHARED_FILE = _data_root() / "shared_plans.json"


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()


def _read() -> list[dict]:
    if not SHARED_FILE.exists():
        return []
    try:
        return json.loads(SHARED_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def _write(rows: list[dict]) -> None:
    SHARED_FILE.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")


def _slug() -> str:
    return uuid.uuid4().hex[:12]


def _public_item(item: dict | None) -> dict | None:
    if not item:
        return None

    allowed = {
        "id",
        "titulo",
        "nombre",
        "fecha",
        "fecha_inicio",
        "fecha_fin",
        "barrio",
        "categoria",
        "franja",
        "precio_tipo",
        "ubicacion",
        "direccion",
        "punto_quedada",
        "horario",
        "latitud",
        "longitud",
        "maps_url",
        "fuente",
        "descripcion",
        "url",
        "_maps_url",
        "_embed_url",
    }
    return {k: v for k, v in item.items() if k in allowed}


def _public_plan(plan: dict) -> dict:
    return {
        "principal": _public_item(plan.get("principal")),
        "comida": _public_item(plan.get("comida")),
        "extra": _public_item(plan.get("extra")),
        "summary": plan.get("summary", {}),
        "route": plan.get("route", {}),
        "tips": plan.get("tips", []),
        "prefs": plan.get("prefs", {}),
    }


def create_shared_plan(
    *,
    kind: str,
    owner_token: str,
    plan: dict,
    base_url: str,
    source_prefs: dict | None = None,
    expires_days: int = 7,
) -> dict:
    rows = _read()
    slug = _slug()
    base_url = (base_url or "").rstrip("/")

    share_url = f"{base_url}/plan-compartido/{slug}" if base_url else f"/plan-compartido/{slug}"
    qr_url = f"https://api.qrserver.com/v1/create-qr-code/?size=280x280&data={quote_plus(share_url)}"

    row = {
        "id": uuid.uuid4().hex,
        "slug": slug,
        "kind": kind,
        "owner_token": owner_token,
        "created_at": _now_iso(),
        "expires_at": (datetime.utcnow() + timedelta(days=expires_days)).replace(microsecond=0).isoformat(),
        "is_active": True,
        "share_url": share_url,
        "qr_url": qr_url,
        "source_prefs": source_prefs or {},
        "plan": _public_plan(plan or {}),
    }
    rows.append(row)
    _write(rows)
    return row


def get_shared_plan(slug: str) -> dict | None:
    rows = _read()
    now = datetime.utcnow()

    for row in rows:
        if row.get("slug") != slug:
            continue
        if not row.get("is_active", True):
            return None

        expires_at = row.get("expires_at", "")
        try:
            if expires_at and datetime.fromisoformat(expires_at) < now:
                return None
        except Exception:
            pass

        return row

    return None


def revoke_shared_plan(slug: str) -> bool:
    rows = _read()
    changed = False

    for row in rows:
        if row.get("slug") == slug:
            row["is_active"] = False
            changed = True

    if changed:
        _write(rows)

    return changed