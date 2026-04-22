from jobs.fetch_open_data import main as open_data_main
from jobs.fetch_bilbao_gazte import main as gazte_main
from jobs.fetch_bilbao_turismo import main as turismo_main
from jobs.fetch_lugares_turismo import main as lugares_turismo_main
from jobs.merge_feeds import main as merge_eventos_main
from jobs.merge_lugares import main as merge_lugares_main


def main():
    source_jobs = [
        ("open_data", open_data_main),
        ("bilbao_gazte", gazte_main),
        ("bilbao_turismo", turismo_main),
        ("lugares_turismo", lugares_turismo_main),
    ]

    errors = []

    for name, job in source_jobs:
        try:
            print(f"Ejecutando {name}...")
            job()
            print(f"OK: {name}")
        except Exception as exc:
            msg = f"ERROR en {name}: {exc}"
            print(msg)
            errors.append(msg)

    # aunque fallen algunas fuentes, intentamos consolidar lo que sí exista
    try:
        print("Ejecutando merge_eventos_main...")
        merge_eventos_main()
        print("OK: merge_eventos_main")
    except Exception as exc:
        print(f"ERROR en merge_eventos_main: {exc}")
        raise

    try:
        print("Ejecutando merge_lugares_main...")
        merge_lugares_main()
        print("OK: merge_lugares_main")
    except Exception as exc:
        print(f"ERROR en merge_lugares_main: {exc}")
        raise

    if errors:
        print("Actualización terminada con avisos:")
        for err in errors:
            print(err)
    else:
        print("Actualización terminada")


if __name__ == "__main__":
    main()