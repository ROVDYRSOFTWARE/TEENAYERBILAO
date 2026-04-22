from jobs.fetch_open_data import main as open_data_main
from jobs.fetch_bilbao_gazte import main as gazte_main
from jobs.fetch_bilbao_turismo import main as turismo_main
from jobs.merge_feeds import main as merge_main


def main():
    source_jobs = [
        open_data_main,
        gazte_main,
        turismo_main,
    ]

    errors = []

    for job in source_jobs:
        try:
            print(f"Ejecutando {job.__name__}...")
            job()
            print(f"OK: {job.__name__}")
        except Exception as exc:
            msg = f"ERROR en {job.__name__}: {exc}"
            print(msg)
            errors.append(msg)

    if errors:
        print("Se cancela merge_main porque han fallado fuentes previas.")
        raise RuntimeError(" | ".join(errors))

    print("Ejecutando merge_main...")
    merge_main()
    print("OK: merge_main")
    print("Actualización terminada")


if __name__ == "__main__":
    main()