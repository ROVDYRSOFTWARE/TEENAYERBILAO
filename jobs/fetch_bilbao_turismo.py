from __future__ import annotations

import hashlib
import re

from bs4 import BeautifulSoup

from jobs.common import FUENTES_DIR, fetch_url, update_sync, write_json

URL = "https://www.bilbaoturismo.net/BilbaoTurismo/en/big-events"
OUT_FILE = FUENTES_DIR / "bilbao_turismo.json"


def clean(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def stable_id(*parts: str) -> str:
    raw = "||".join(parts).encode("utf-8", errors="ignore")
    return "turismo-" + hashlib.sha1(raw).hexdigest()[:12]


def parse_dates(text: str) -> tuple[str, str]:
    m = re.search(r"(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})", text)
    if not m:
        return "", ""
    d1 = "-".join(reversed(m.group(1).split("/")))
    d2 = "-".join(reversed(m.group(2).split("/")))
    return d1, d2


def main():
    html = fetch_url(URL)
    soup = BeautifulSoup(html, "html.parser")
    eventos = []

    lines = [clean(x) for x in soup.get_text("\n", strip=True).splitlines()]
    lines = [x for x in lines if x]

    ignored = {
        "Highlights",
        "Search by dates",
        "April", "May", "June", "July", "August", "September",
        "October", "November", "December", "January", "February", "March",
    }

    prev_title = ""
    for line in lines:
        if re.fullmatch(r"\d{2}/\d{2}/\d{4}\s*-\s*\d{2}/\d{2}/\d{4}", line):
            if not prev_title or prev_title in ignored:
                continue

            fecha_inicio, fecha_fin = parse_dates(line)
            if not fecha_inicio:
                continue

            eventos.append(
                {
                    "id": stable_id(prev_title, fecha_inicio, fecha_fin),
                    "fuente": "Bilbao Turismo",
                    "tipo": "gran evento",
                    "titulo": prev_title,
                    "descripcion": "",
                    "fecha_inicio": fecha_inicio,
                    "fecha_fin": fecha_fin,
                    "hora": "",
                    "zona": "Bilbao",
                    "edad": "",
                    "precio": "",
                    "url": URL,
                }
            )
            prev_title = ""
            continue

        if line not in ignored and len(line) >= 4:
            prev_title = line

    unique = []
    seen = set()
    for item in eventos:
        key = (item["titulo"], item["fecha_inicio"], item["fecha_fin"])
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)

    unique.sort(key=lambda x: (x.get("fecha_inicio", "9999-99-99"), x.get("titulo", "")))

    write_json(OUT_FILE, unique)
    update_sync("Bilbao Turismo", len(unique), note="Big events")
    print(f"Bilbao Turismo: {len(unique)} eventos")


if __name__ == "__main__":
    main()
