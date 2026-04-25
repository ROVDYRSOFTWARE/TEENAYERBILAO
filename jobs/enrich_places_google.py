from __future__ import annotations

from datetime import datetime, timedelta

from jobs.common import DATA_DIR, read_json, update_sync, write_json
from services import google_places

PLACES_FILE = DATA_DIR / "lugares.json"


def _now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat()


def _parse_iso(value: str):
    try:
        return datetime.fromisoformat(str(value or ""))
    except Exception:
        return None


def _clean(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def _looks_generic_address(value: str) -> bool:
    low = _clean(value).lower()
    return low in {"", "bilbao", "bizkaia", "vizcaya", "centro de bilbao"}


def _already_checked_recently(item: dict, retry_days: int = 30) -> bool:
    status = _clean(item.get("google_match_status", ""))
    checked_at = _parse_iso(item.get("google_checked_at", ""))

    if not checked_at:
        return False

    if status in {"no_match", "closed_permanently", "missing_place_id"}:
        return datetime.utcnow() - checked_at < timedelta(days=retry_days)

    return False


def _needs_enrichment(item: dict, force: bool = False) -> bool:
    if force:
        return True

    if item.get("google_enriched") and item.get("google_match_status") == "ok":
        return False

    if _already_checked_recently(item):
        return False

    if item.get("google_match_status") in {"no_match", "closed_permanently", "missing_place_id"}:
        return False

    if not _clean(item.get("direccion", "")):
        return True

    if _looks_generic_address(item.get("direccion", "")):
        return True

    if not (_clean(item.get("latitud", "")) and _clean(item.get("longitud", ""))):
        return True

    if not _clean(item.get("maps_url", "")):
        return True

    if not _clean(item.get("horario", "")):
        return True

    return False


def main(force: bool = False, limit: int | None = None):
    places = read_json(PLACES_FILE, [])
    if not places:
        update_sync("Google Places enrich", 0, status="ok", note="No hay lugares para enriquecer")
        print("Google Places enrich: no hay lugares")
        return

    updated = []
    ok = 0
    no_match = 0
    skipped = 0
    errors = 0
    processed = 0

    for item in places:
        row = dict(item)

        if not _needs_enrichment(row, force=force):
            updated.append(row)
            skipped += 1
            continue

        if limit is not None and processed >= limit:
            updated.append(row)
            skipped += 1
            continue

        processed += 1

        try:
            row = google_places.enrich_item_with_google(row)
            row["google_checked_at"] = _now_iso()

            if row.get("google_enriched"):
                ok += 1
            else:
                no_match += 1

        except Exception as exc:
            row["google_enriched"] = False
            row["google_match_status"] = f"error:{type(exc).__name__}"
            row["google_checked_at"] = _now_iso()
            errors += 1

        updated.append(row)

    write_json(PLACES_FILE, updated)

    note = f"processed={processed}, ok={ok}, no_match={no_match}, skipped={skipped}, errors={errors}"
    update_sync(
        "Google Places enrich",
        ok,
        status="ok" if errors == 0 else "warn",
        note=note,
    )
    print(f"Google Places enrich -> processed={processed} ok={ok} no_match={no_match} skipped={skipped} errors={errors}")


if __name__ == "__main__":
    main()
