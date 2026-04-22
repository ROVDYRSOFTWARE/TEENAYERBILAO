from __future__ import annotations
import csv, io, json, os
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_ROOT = Path(os.getenv("DATA_ROOT", str(BASE_DIR)))
DATA_DIR = DATA_ROOT / "data"
DATA_DIR.mkdir(parents=True, exist_ok=True)

EVENTS_FILE = DATA_DIR / "eventos.json"
PLACES_FILE = DATA_DIR / "lugares.json"
PROFILES_FILE = DATA_DIR / "user_profiles.json"
INTERACTIONS_FILE = DATA_DIR / "interactions.json"
AUDIT_FILE = DATA_DIR / "audit_log.json"
SYNC_FILE = DATA_DIR / "fuentes_sync.json"


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def read_json(path: Path, default: Any):
    if not path.exists():
        return default
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return default
    return json.loads(text)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def init_files() -> None:
    for path, default in (
        (EVENTS_FILE, []),
        (PLACES_FILE, []),
        (PROFILES_FILE, {}),
        (INTERACTIONS_FILE, []),
        (AUDIT_FILE, []),
        (SYNC_FILE, {}),
    ):
        if not path.exists():
            write_json(path, default)


def load_events(): return read_json(EVENTS_FILE, [])
def save_events(rows): write_json(EVENTS_FILE, rows)
def load_places(): return read_json(PLACES_FILE, [])
def save_places(rows): write_json(PLACES_FILE, rows)
def load_profiles(): return read_json(PROFILES_FILE, {})
def save_profiles(rows): write_json(PROFILES_FILE, rows)
def load_interactions(): return read_json(INTERACTIONS_FILE, [])
def save_interactions(rows): write_json(INTERACTIONS_FILE, rows)
def load_audit(): return read_json(AUDIT_FILE, [])
def save_audit(rows): write_json(AUDIT_FILE, rows)
def load_sync(): return read_json(SYNC_FILE, {})
def save_sync(rows): write_json(SYNC_FILE, rows)


def get_event(event_id: str):
    return next((row for row in load_events() if row.get("id") == event_id), None)


def get_place(place_id: str):
    return next((row for row in load_places() if row.get("id") == place_id), None)


def next_id(prefix: str, rows: list[dict]) -> str:
    max_num = 0
    for row in rows:
        rid = str(row.get("id", ""))
        if rid.startswith(prefix):
            parts = rid.split("-")
            if parts and parts[-1].isdigit():
                max_num = max(max_num, int(parts[-1]))
    return f"{prefix}-{max_num + 1:03d}"


def upsert_event(data: dict) -> dict:
    rows = load_events()
    item_id = data.get("id")
    if item_id:
        for idx, row in enumerate(rows):
            if row.get("id") == item_id:
                rows[idx] = data
                save_events(rows)
                return data
    data["id"] = next_id("EVT", rows)
    rows.append(data)
    save_events(rows)
    return data


def upsert_place(data: dict) -> dict:
    rows = load_places()
    item_id = data.get("id")
    if item_id:
        for idx, row in enumerate(rows):
            if row.get("id") == item_id:
                rows[idx] = data
                save_places(rows)
                return data
    data["id"] = next_id("LUG", rows)
    rows.append(data)
    save_places(rows)
    return data


def delete_event(event_id: str) -> bool:
    rows = load_events()
    new_rows = [row for row in rows if row.get("id") != event_id]
    changed = len(new_rows) != len(rows)
    if changed: save_events(new_rows)
    return changed


def delete_place(place_id: str) -> bool:
    rows = load_places()
    new_rows = [row for row in rows if row.get("id") != place_id]
    changed = len(new_rows) != len(rows)
    if changed: save_places(new_rows)
    return changed


def append_interaction(row: dict) -> None:
    rows = load_interactions()
    rows.append(row)
    save_interactions(rows)


def append_audit(action: str, entity_type: str, entity_id: str, meta: dict | None = None) -> None:
    rows = load_audit()
    rows.append({"ts": now_iso(), "action": action, "entity_type": entity_type, "entity_id": entity_id, "meta": meta or {}})
    save_audit(rows)


def touch_sync_status(source: str, **kwargs) -> None:
    data = load_sync()
    info = data.get(source, {})
    info.update(kwargs)
    data[source] = info
    save_sync(data)


def csv_bytes(rows: list[dict]) -> bytes:
    buffer = io.StringIO()
    if not rows:
        return b""
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")
