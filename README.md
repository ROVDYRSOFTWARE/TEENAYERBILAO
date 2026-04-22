# Teenager Bilbao

Esta versión recupera la geolocalización en eventos y lugares, mantiene la administración separada y añade actualización automática de eventos.

## Novedades
- Geolocalización en eventos y lugares: ubicación, dirección, latitud, longitud y enlace de mapa.
- Mapa embebido en fichas cuando hay coordenadas.
- Geocodificación automática al guardar desde admin si indicas ubicación o dirección.
- Actualización automática de eventos:
  - al arranque / primera sesión pública si toca,
  - o a las 06:00 con tarea programada de Windows.
- Botón de "Actualizar ahora" en admin.

## Arranque
```bat
py -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python app.py
```

## Programar actualización diaria a las 06:00
Edita la ruta de `programar_6am.txt` si tu carpeta cambia y ejecuta ese comando en CMD.

## Contraseña admin
Por defecto: `admin1234`

Puedes cambiarla así:
```bat
set ADMIN_PASSWORD=TuClaveSegura
python app.py
```


## Despliegue público
Consulta `DEPLOY_RENDER.md`.
