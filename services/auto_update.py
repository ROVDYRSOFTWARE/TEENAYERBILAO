from __future__ import annotations
import threading
from datetime import datetime, time

from services import data_store

_lock = threading.Lock()
_running = False


def _last_run_dt() -> datetime | None:
    sync = data_store.load_sync()
    meta = sync.get("auto_update", {})
    value = meta.get("last_run")
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except Exception:
        return None


def should_run(now: datetime | None = None) -> bool:
    now = now or datetime.now()
    last = _last_run_dt()
    six_am = datetime.combine(now.date(), time(6, 0))
    if last is None:
        return True
    if now >= six_am and last < six_am:
        return True
    if now.date() > last.date():
        return True
    return False


def mark_running(reason: str) -> None:
    data_store.touch_sync_status("auto_update", status="running", reason=reason, started_at=data_store.now_iso())


def mark_finished(ok: bool, reason: str, note: str = "") -> None:
    data_store.touch_sync_status(
        "auto_update",
        status="ok" if ok else "error",
        reason=reason,
        note=note,
        finished_at=data_store.now_iso(),
        last_run=data_store.now_iso(),
    )


def _worker(reason: str) -> None:
    global _running
    try:
        from jobs.update_all import main as update_main
        mark_running(reason)
        update_main()
        data_store.append_audit("auto_update_run", "system", "auto_update", {"reason": reason})
        mark_finished(True, reason, "Actualización automática completada")
    except Exception as exc:
        data_store.append_audit("auto_update_error", "system", "auto_update", {"reason": reason, "error": str(exc)})
        mark_finished(False, reason, str(exc))
    finally:
        with _lock:
            _running = False


def maybe_start(reason: str = "startup") -> bool:
    global _running
    if not should_run():
        return False
    with _lock:
        if _running:
            return False
        _running = True
    thread = threading.Thread(target=_worker, args=(reason,), daemon=True)
    thread.start()
    return True
