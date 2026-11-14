---
author: guillemfernandezz
branch: feat/indices-gist
status: in-review
---

# Índices GiST en las geometrías

## Intent
Que `ST_Intersects` por bbox use un índice espacial en lugar de recorrer la tabla entera (deuda técnica n.º 1 de `arquitectura-gis.md`).

## Scope
- `etl_pipeline/1_ETL_Agenda_Dinamica.py`: índice `agenda_cultural_geometry_gist`.
- `etl_pipeline/2_ETL_Patrimonio_Estatico.py`: índice `patrimoni_monumental_geometry_gist`.
- Fuera de alcance: resto de la deuda técnica.

## Checklist
- [x] `CREATE INDEX IF NOT EXISTS ... USING GIST (geometry)` en los dos ETL. Prueba: diff.
- [x] Los scripts compilan. Prueba: `python -m py_compile`.
- [x] `patrimoni_monumental`: el planificador usa el índice. Prueba: `EXPLAIN` en pgAdmin.
- [x] `agenda_cultural`: el planificador usa el índice. Prueba: `EXPLAIN` en pgAdmin.

## Evidence
- 2026-11-13: `python -m py_compile` sobre los dos scripts → OK.
- `git diff --stat`: 3 archivos, +7 −1.
- 2026-11-14: `EXPLAIN` en pgAdmin (verificado por el autor) muestra `Bitmap Index Scan on patrimoni_monumental_geometry_gist`.

- 2026-11-14: el autor confirma que `EXPLAIN` en pgAdmin usa `agenda_cultural_geometry_gist` en `agenda_cultural`.

## Next
Abrir el PR de `feat/indices-gist` desde GitHub (no hay `gh` en esta máquina). Después, revisión y merge.
