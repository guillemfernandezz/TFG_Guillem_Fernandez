# Visor Patrimoni i Cultura (TFG)

Antes de tocar datos espaciales, SQL o el ETL, lee `02-DOCS/wiki/proyecto/arquitectura-gis.md`.

- CRS único EPSG:4326; puntos como `ST_MakePoint(lon, lat)`.
- Credenciales solo en `.env`. El repositorio es público: no escribas secretos en código, docs ni commits.
- Trabaja en ramas y abre PR; no hagas commit ni push a `main`.
- Propiedades e identificadores de Wikidata, funciones de PostGIS o API de Leaflet no verificadas en la sesión: compruébalas en la documentación oficial antes de usarlas.
