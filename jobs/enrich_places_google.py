from __future__ import annotations

from jobs.common import DATA_DIR, read_json, update_sync, write_json
from services import google_places

PLACES_FILE = DATA_DIR / "lugares.json"


def _clean(value: str) -> str:
    return " ".join(str(value or "").split()).strip()


def _looks_generic_address(value: str) -> bool:
    low = _clean(value).lower()
    if not low:
        return True
    generic = {
        "bilbao",
        "bizkaia",
        "vizcaya",
        "centro de bilbao",
    }
    return low in generic


def _needs_enrichment(item: dict, force: bool = False) -> bool:
    if force:
        return True

    if item.get("google_enriched") and item.get("google_match_status") == "ok":
        return False

    if not _clean(item.get("direccion", "")):
        return True

    if _looks_generic_address(item.get("direccion", "")):
        return True

    if not (_clean(item.get("latitud", "")) and _clean(item.get("longitud", ""))):
        return True

    if not _clean(item.get("maps_url", "")):
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
            if row.get("google_enriched"):
                ok += 1
        except Exception as exc:
            row["google_enriched"] = False
            row["google_match_status"] = f"error:{type(exc).__name__}"
            errors += 1

        updated.append(row)

    write_json(PLACES_FILE, updated)
    note = f"ok={ok}, skipped={skipped}, errors={errors}"
    update_sync("Google Places enrich", ok, status="ok" if errors == 0 else "warn", note=note)
    print(f"Google Places enrich -> ok={ok} skipped={skipped} errors={errors}")


if __name__ == "__main__":
    main()