from jobs.fetch_open_data import main as open_data_main
from jobs.fetch_bilbao_gazte import main as gazte_main
from jobs.fetch_bilbao_turismo import main as turismo_main
from jobs.merge_feeds import main as merge_main


def main():
    source_jobs = [
        ("open_data", open_data_main),
        ("bilbao_gazte", gazte_main),
        ("bilbao_turismo", turismo_main),
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

    # Siempre intenta hacer el merge de eventos con lo que sí haya funcionado
    try:
        print("Ejecutando merge_main...")
        merge_main()
        print("OK: merge_main")
    except Exception as exc:
        print(f"ERROR en merge_main: {exc}")
        raise

    # No cortamos el proceso si al menos se ha podido hacer merge
    if errors:
        print("Actualización terminada con avisos:")
        for err in errors:
            print(err)
    else:
        print("Actualización terminada")
        

if __name__ == "__main__":
    main()