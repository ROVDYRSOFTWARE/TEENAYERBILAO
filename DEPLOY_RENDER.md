# Despliegue público en Render

## Qué incluye esta versión
- interfaz pública y panel admin separado
- geolocalización de eventos y lugares
- actualización automática al inicio de sesión
- trigger seguro para actualización remota: `/tasks/auto-update`
- ficheros preparados para Render: `render.yaml`, `Procfile`, `runtime.txt`

## Recomendación importante
Este proyecto guarda datos en JSON locales (`data/*.json`). En Render, esos cambios **solo se conservan** si el servicio usa **Persistent Disk**. En instancias Free no se conserva el sistema de archivos local. Además, los cron jobs de Render **no pueden acceder a un persistent disk**, por eso aquí el cron llama por HTTP al propio servicio web para que sea **la web** quien actualice su disco.

## Pasos
1. Sube el proyecto a GitHub.
2. En Render, crea el servicio con `render.yaml` o con "New > Blueprint".
3. En el servicio web, confirma:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --threads 4 --timeout 120`
4. Mantén el disco montado en `/var/data/teenager`.
5. Configura variables:
   - `ADMIN_PASSWORD`
   - `CRON_SECRET`
   - `PUBLIC_BASE_URL` (la URL pública exacta del web service)
6. Cuando Render te dé la URL pública, entra a:
   - `/`
   - `/admin/login`

## Nota sobre las 6:00
Los cron jobs de Render usan **UTC**. Si quieres exactamente las 6:00 de España, tendrás que ajustar la expresión según horario de invierno/verano.

## Ruta de salud
- `/healthz`

## Ruta de actualización remota
- `/tasks/auto-update?token=TU_SECRETO`
