---
title: Arquitectura y convenciones GIS del visor
description: Hechos verificados en el código sobre CRS, esquema PostGIS, API, ETL y visor. Léelo antes de tocar datos espaciales.
updated: 2026-11-13
---

# Arquitectura y convenciones GIS

Todo lo que aparece aquí se ha comprobado leyendo el código (commit `cad7edc`). Si cambias el código, actualiza esta página.

## Componentes

| Capa | Archivo | Qué hace |
|---|---|---|
| ETL agenda | `etl_pipeline/1_ETL_Agenda_Dinamica.py` | Descarga el dataset Socrata `rhpv-yr4f` (Agenda Cultural, Generalitat), inserta los eventos y purga los caducados (`DELETE` por `data_fi`). |
| ETL patrimonio | `etl_pipeline/2_ETL_Patrimonio_Estatico.py` | Consulta SPARQL a Wikidata con `wikibase:around` por municipio. Filtra por P1600, P3861, P3744, P6203 y P1435 (BCIN, BCIL y otros). |
| QA | `etl_pipeline/3_QA_Cobertura_Radar.py` | Comprueba la cobertura municipal contra Wikidata. |
| API | `backend_api/main.py` | FastAPI: `/api/patrimonio`, `/api/agenda` y `/api/metadata` (NEM / ISO 19115). |
| Visor | `frontend_visor/` | Leaflet 1.9.4 + markercluster 1.5.3 + Turf 6, en JS vanilla. Teselas de CARTO. |

## Invariantes espaciales (no romper)

- **CRS único: EPSG:4326.** Las columnas son `geometry(Point, 4326)` y los puntos se crean con `ST_SetSRID(ST_MakePoint(lon, lat), 4326)`. El orden es **lon, lat**.
- **Filtro por bbox:** `ST_Intersects(geometry, ST_MakeEnvelope(minx, miny, maxx, maxy, 4326))`, con parámetros `%s` de psycopg2. No se interpolan cadenas en el SQL.
- **Esquema:** `ide_cultural`, con las tablas `patrimoni_monumental` y `agenda_cultural`, en la base de datos `events_db`.
- **Salida:** GeoJSON FeatureCollection. Es la RFC 7946, que fija WGS84, así que el bloque `crs` de `/api/patrimonio` es redundante, aunque inofensivo.

## Configuración

- Las credenciales se leen de `.env` (ver `.env.example`). **Nunca** van en el código: el repositorio es público.
- El frontend apunta a `API_BASE = "http://127.0.0.1:8000"`, que está fijado en `app.js`.

## Deuda técnica detectada (pendiente, sin resolver)

1. **No se crea ningún índice GiST** en las geometrías. `ST_Intersects` recorre la tabla entera. Habría que añadir `CREATE INDEX ... USING GIST (geometry)` en los dos `CREATE TABLE`.
2. **El límite por defecto es de 30 000 elementos** en `/api/patrimonio` y no tiene tope máximo. Hay que validarlo con `Query(le=...)`.
3. **CORS:** `allow_origins=["*"]` junto con `allow_credentials=True`.
4. `except Exception` genérico con `print` en lugar de `logging`.
5. **Sin tests ni CI.**
6. **CDN sin SRI** (`integrity=`) en `index.html`, y Turf con versión flotante (`@6`).
7. **Comentarios de las propiedades de Wikidata (P3744, P6203...) sin verificar** contra wikidata.org. Hay que confirmarlo antes de modificar la consulta.
