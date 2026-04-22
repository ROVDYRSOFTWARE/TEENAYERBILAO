from __future__ import annotations
import json
import subprocess
from pathlib import Path
from urllib.parse import quote_plus

CACHE_FILE = Path(__file__).resolve().parents[1] / "data" / "geocode_cache.json"
USER_AGENT = "TeenagerBilbao/1.0 (+local-app)"


def _decode_bytes(raw: bytes) -> str:
    if raw is None:
        return ""
    for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except Exception:
            pass
    return raw.decode("utf-8", errors="replace")


def _load_cache() -> dict:
    if not CACHE_FILE.exists():
        return {}
    try:
        return json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _save_cache(data: dict) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def geocode(query: str) -> dict:
    query = (query or "").strip()
    if not query:
        return {}
    cache = _load_cache()
    if query in cache:
        return cache[query]
    url = (
        "https://nominatim.openstreetmap.org/search?format=jsonv2&limit=1&countrycodes=es&q="
        + quote_plus(query)
    )
    cmd = [
        "curl", "-L", "--fail", "--silent", "--show-error", "--compressed",
        "-A", USER_AGENT,
        "--max-time", "30",
        url,
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, check=False)
        if res.returncode != 0:
            return {}
        txt = _decode_bytes(res.stdout)
        data = json.loads(txt)
        if not data:
            return {}
        row = data[0]
        out = {
            "latitud": str(row.get("lat", "")).strip(),
            "longitud": str(row.get("lon", "")).strip(),
            "display_name": row.get("display_name", ""),
        }
        cache[query] = out
        _save_cache(cache)
        return out
    except Exception:
        return {}
