from __future__ import annotations


def _item_name(item: dict | None) -> str:
    if not item:
        return "la siguiente parada"
    return item.get("titulo") or item.get("nombre") or "la siguiente parada"


def _objective_label(objective: str) -> str:
    labels = {
        "diversion": "pasarlo bien y reírse",
        "conocerse": "conocerse mejor",
        "moverse": "moverse y activarse",
        "crear": "descubrir y crear algo distinto",
        "desconectar": "desconectar y bajar el ritmo",
        "compras": "combinar compras y ocio",
    }
    return labels.get(objective or "", "pasarlo bien en grupo")


def _energy_label(energy: str) -> str:
    labels = {
        "tranquila": "tranquilo",
        "media": "equilibrado",
        "alta": "con energía",
    }
    return labels.get(energy or "", "equilibrado")


def _group_size_text(group_size) -> str:
    try:
        n = int(group_size)
    except Exception:
        return "grupo"
    if n <= 2:
        return "grupo pequeño"
    if n <= 5:
        return "grupo"
    return "grupo grande"


def _intro_text(prefs: dict, principal: dict | None, comida: dict | None, extra: dict | None) -> str:
    objective = _objective_label(prefs.get("objective", "diversion"))
    energy = _energy_label(prefs.get("energy", "media"))
    size_txt = _group_size_text(prefs.get("group_size", 4))
    p1 = _item_name(principal)
    p2 = _item_name(comida)
    p3 = _item_name(extra)

    bits = [f"Hoy tenéis un plan pensado para {objective}."]
    bits.append(f"El ritmo está planteado para un {size_txt} con tono {energy}.")
    if principal:
        bits.append(f"Empezad por {p1}.")
    if comida:
        bits.append(f"Luego podéis hacer una pausa en {p2}.")
    if extra:
        bits.append(f"Y cerrar con {p3}.")
    return " ".join(bits)


def _phase_welcome(prefs: dict) -> dict:
    objective = prefs.get("objective", "diversion")
    text = {
        "conocerse": "Antes de arrancar, haced una ronda rápida: nombre o apodo, una canción favorita y qué esperáis del plan.",
        "desconectar": "Antes de empezar, respirad un momento y acordad que la idea es pasar un buen rato sin presión.",
        "compras": "Antes de arrancar, cada persona puede decir una tienda, estilo o idea que le gustaría encontrar.",
    }.get(objective, "Antes de arrancar, haced una ronda rápida: cada persona dice qué le apetece del plan.")
    return {
        "title": "Bienvenida",
        "duration": "5 min",
        "text": text,
    }


def _phase_start(principal: dict | None, prefs: dict) -> dict:
    place = _item_name(principal)
    objective = prefs.get("objective", "diversion")

    if objective == "moverse":
        text = f"Al llegar a {place}, mezclad al grupo en parejas o tríos para que no se quede nadie fuera desde el principio."
    elif objective == "conocerse":
        text = f"Al llegar a {place}, haced una mini dinámica: cada persona cuenta algo curioso o algo que le gusta hacer."
    elif objective == "compras":
        text = f"Al llegar a {place}, proponed un mini reto suave: encontrar algo curioso, bonito o inesperado sin prisas."
    else:
        text = f"Al llegar a {place}, empezad con una consigna sencilla: que todo el mundo participe y nadie se quede aparte."

    return {
        "title": "Arranque",
        "duration": "10 min",
        "text": text,
    }


def _phase_main(principal: dict | None, prefs: dict) -> dict:
    place = _item_name(principal)
    objective = prefs.get("objective", "diversion")

    text = {
        "diversion": f"Durante la actividad en {place}, priorizad reíros y participar. Mejor rotar equipos o parejas que competir demasiado fuerte.",
        "conocerse": f"Durante la actividad en {place}, cambiad de parejas o grupos pequeños para que todo el mundo hable con más gente.",
        "moverse": f"En {place}, el objetivo es activarse y pasarlo bien. Ajustad el ritmo si alguien necesita ir más suave.",
        "crear": f"En {place}, fijaos en detalles, ideas o cosas que os inspiren. Luego comentad qué os ha llamado la atención.",
        "desconectar": f"En {place}, evitad meter demasiadas prisas. Mejor disfrutar el momento y mantener un ambiente cómodo.",
        "compras": f"En {place}, cada persona puede proponer un hallazgo favorito y al final hacéis vuestro top del día.",
    }.get(objective, f"En {place}, la clave es que participe todo el grupo y el ambiente siga siendo sano y cómodo.")

    return {
        "title": "Actividad principal",
        "duration": "30-60 min",
        "text": text,
    }


def _phase_break(comida: dict | None, prefs: dict) -> dict:
    place = _item_name(comida)
    objective = prefs.get("objective", "diversion")

    if comida:
        text = {
            "conocerse": f"En la parada de comida o merienda en {place}, cada persona puede contar el mejor momento del plan hasta ahora.",
            "desconectar": f"En {place}, parad un poco el ritmo. La idea es descansar, comentar y decidir juntos si queréis seguir igual o más tranquilos.",
            "compras": f"En {place}, enseñad vuestros hallazgos favoritos o lo que más os ha gustado hasta ahora.",
        }.get(objective, f"En {place}, haced una pausa corta para comentar qué parte del plan os está gustando más.")
    else:
        text = "Si hacéis una pausa, aprovechad para comprobar que todo el grupo sigue cómodo con el plan."

    return {
        "title": "Pausa",
        "duration": "15-25 min",
        "text": text,
    }


def _phase_extra(extra: dict | None, prefs: dict) -> dict:
    place = _item_name(extra)
    objective = prefs.get("objective", "diversion")

    if extra:
        text = {
            "diversion": f"En la última parada, {place}, haced algo corto y positivo: foto, mini reto o votación del mejor momento.",
            "conocerse": f"En {place}, cerrad con una ronda breve: cada persona dice algo bueno del grupo o del plan.",
            "moverse": f"En {place}, terminad con una actividad más suave para no cerrar con cansancio excesivo.",
            "crear": f"En {place}, terminad el plan eligiendo una idea, foto o recuerdo que os lleváis del día.",
            "desconectar": f"En {place}, cerrad con algo sencillo: paseo corto, charla tranquila o momento de bajar revoluciones.",
            "compras": f"En {place}, terminad con una votación divertida: top hallazgo, top tienda o top momento.",
        }.get(objective, f"En {place}, cerrad con una dinámica sencilla y positiva.")
    else:
        text = "Si no hay parada extra, cerrad el plan con una mini ronda final antes de iros."

    return {
        "title": "Cierre",
        "duration": "10 min",
        "text": text,
    }


def _fallbacks(prefs: dict) -> list[str]:
    objective = prefs.get("objective", "diversion")
    base = [
        "Si el grupo está tímido, haced parejas o tríos en vez de hablar todos a la vez.",
        "Si alguien se descuelga, cambiad equipos o ritmo para que vuelva a entrar cómodo.",
        "Si os estáis cansando, recortad una parada y priorizad terminar con buen ambiente.",
    ]

    if objective == "compras":
        base.append("Si el plan de tiendas se alarga demasiado, limitadlo a 2 o 3 paradas y pasad antes a la merienda.")
    elif objective == "moverse":
        base.append("Si alguien no quiere seguir el ritmo, proponed versión suave sin presionar.")
    elif objective == "conocerse":
        base.append("Si cuesta arrancar la conversación, usad preguntas rápidas: música, series, viajes o comida favorita.")
    elif objective == "desconectar":
        base.append("Si el grupo viene acelerado, empezad directamente por la fase más tranquila del plan.")

    return base


def build_host_guide(
    *,
    prefs: dict,
    principal: dict | None,
    comida: dict | None,
    extra: dict | None,
    mode: str = "grupo",
) -> dict:
    intro = _intro_text(prefs, principal, comida, extra)

    phases = [
        _phase_welcome(prefs),
        _phase_start(principal, prefs),
        _phase_main(principal, prefs),
        _phase_break(comida, prefs),
        _phase_extra(extra, prefs),
    ]

    title = "Guía del anfitrión"
    if mode == "hoy":
        title = "Guía para llevar el plan"

    return {
        "title": title,
        "intro": intro,
        "phases": phases,
        "fallbacks": _fallbacks(prefs),
        "closing_line": "La clave no es hacer muchas cosas, sino que el grupo termine con buena sensación.",
    }