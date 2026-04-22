from __future__ import annotations

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

BASE_DIR = Path(__file__).resolve().parents[1]
DATA_ROOT = Path(os.getenv("DATA_ROOT", str(BASE_DIR)))
DATA_DIR = DATA_ROOT / "data"
FUENTES_DIR = DATA_DIR / "fuentes"
FUENTES_DIR.mkdir(parents=True, exist_ok=True)
SYNC_FILE = DATA_DIR / "fuentes_sync.json"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def _decode_bytes(raw: bytes) -> str:
    if raw is None:
        return ""
    for enc in ("utf-8", "utf-8-sig", "cp1252", "latin-1"):
        try:
            return raw.decode(enc)
        except Exception:
            pass
    return raw.decode("utf-8", errors="replace")


def fetch_url(url: str, timeout: int = 45) -> str:
    curl_cmd = [
        "curl", "-L", "--fail", "--silent", "--show-error", "--compressed",
        "-A", USER_AGENT,
        "--max-time", str(timeout),
        url,
    ]
    result = subprocess.run(curl_cmd, capture_output=True, check=False)
    stdout = _decode_bytes(result.stdout)
    stderr = _decode_bytes(result.stderr)
    if result.returncode == 0:
        return stdout
    raise RuntimeError(f"curl devolvió código {result.returncode}: {stderr[:300]}")


def write_json(path: Path, data: Any):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_json(path: Path, default: Any):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def update_sync(source_key: str, total: int, status: str = "ok", note: str = ""):
    data = read_json(SYNC_FILE, {})
    data[source_key] = {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "total": total,
        "status": status,
        "note": note,
    }
    write_json(SYNC_FILE, data)
