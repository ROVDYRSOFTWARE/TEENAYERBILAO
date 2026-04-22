from jobs.fetch_open_data import main as open_data_main
from jobs.fetch_bilbao_gazte import main as gazte_main
from jobs.fetch_bilbao_turismo import main as turismo_main
from jobs.merge_feeds import main as merge_main


def main():
    for job in [open_data_main, gazte_main, turismo_main, merge_main]:
        try:
            job()
        except Exception as exc:
            print(f"ERROR en {job.__name__}: {exc}")
    print("Actualización terminada")

if __name__ == '__main__':
    main()
