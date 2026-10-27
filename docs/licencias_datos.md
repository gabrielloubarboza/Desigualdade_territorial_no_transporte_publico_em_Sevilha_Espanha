# Licencias y condiciones de los datos

El código original del proyecto se publica con licencia MIT ([LICENSE](../LICENSE)). **Esa licencia no cubre los
datos de terceros ni los productos derivados de ellos.** La tabla resume las condiciones identificadas el 24/10/2026.
No son asesoramiento jurídico: antes de redistribuir, conviene revisar los términos vigentes de cada fuente.
Citar la fuente es obligatorio en la mayoría de los casos, pero **la atribución no resuelve por sí sola todas las
condiciones de una licencia** (p. ej., la obligación de compartir bajo la misma licencia de la ODbL).

| Fuente | Condiciones identificadas | Qué se publica en este repositorio |
|---|---|---|
| **INE** — Censo Anual de Población 2024 y seccionado 2024 | Reutilización permitida citando la fuente (aviso legal del INE). | Indicadores por sección con códigos y geometrías INE (`produtos/*resultados.gpkg`, CSV). Datos brutos: no (se descargan con `01_baixar_fontes.py`). |
| **IECA** — Distribución espacial de la población, malla 250 m 2024 | Productos del IECA bajo CC BY 4.0 desde 2014, según la información pública consultada; los términos vigentes no se volvieron a confirmar. Citar autoría y fecha. | Capa `celdas_ieca_250m` y población estimada por punto y sección, con atribución. |
| **GTFS TUSSAM** — Punto de Acceso Nacional (MITRAMS) | Licencia de datos abiertos del MITRAMS: reutilización comercial y no comercial; redistribución de los datos compartidos bajo el mismo tipo de licencia; las obras derivadas con valor añadido pueden tener otra licencia. Mostrar "Powered by MITRAMS", indicar si el dato es bruto o procesado y conservar los metadatos de actualización. | Paradas con oferta derivada (`paradas_autobus`) e indicadores de oferta (**dato procesado**). El feed original no se incluye: se descarga del espejo de Mobility Database (`mdb-2770-202609300035`). |
| **OpenStreetMap** | ODbL 1.0. Las bases de datos derivadas deben compartirse bajo ODbL; los trabajos producidos solo requieren atribución. | Base derivada separada `produtos/sevilla_oferta_bus_contexto_osm.gpkg` (red peatonal y barreras), **bajo ODbL 1.0**. Los indicadores calculados sobre la red se tratan como trabajo producido, con atribución "© OpenStreetMap contributors". |
| **TUSSAM / IDE Sevilla** — capas `TUSSAM_Paradas` y `TUSSAM_Lineas` | Los términos del item **prohíben redistribuir la información, modificada o no**, en un sitio web u otro medio. | **Nada**: solo se usaron localmente como control de calidad. `data/raw/` está excluido del repositorio. Para reconstruirlas: `scripts/01_baixar_fontes.py` (función `tussam_ide`) las descarga del ArcGIS FeatureServer público. Los CSV de etapa 2 contienen solo una etiqueta de control (`situacao_ide`) sin atributos ni geometrías de la IDE. |
| **IGN** — límite municipal INSPIRE | CC BY 4.0. | Solo comparación interna; no se publica la capa. |
| **IBM Plex Sans** (tipografía, `assets/fonts/`) | SIL Open Font License 1.1 (redistribución con la licencia). | Archivos TTF y `LICENSE_IBM_Plex.txt`. |

## Atribuciones para cualquier reutilización de los productos

- © INE — Censo Anual de Población a 01/01/2024 y cartografía de secciones censales 2024.
- © IECA, Junta de Andalucía — Distribución espacial de la población en Andalucía, malla 250 m, 2024 (CC BY 4.0).
- Powered by MITRAMS — GTFS TUSSAM versión 20260928, dato procesado.
- © OpenStreetMap contributors — datos disponibles bajo la Open Database License (ODbL 1.0).

## Antes de publicar

- Confirmar que `data/raw/`, `resultados/**/*.gpkg`, `.venv/` y las cachés no entran en el repositorio (ver `.gitignore`;
  `scripts/20_verificacion_productos.py` lista los archivos publicables).
- Completar la autoría en `LICENSE` y en los metadatos del PDF.
- Revisar de nuevo los términos del IECA y del INE si ha pasado tiempo desde la última consulta.
