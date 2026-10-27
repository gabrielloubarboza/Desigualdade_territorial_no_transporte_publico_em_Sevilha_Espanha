# Verificación de productos — Etapa 5

Ejecución: 2026-10-25T15:39:46+00:00 — OK: 9, LIMITACION: 1, FALLO: 0

Generado por `scripts/20_verificacion_productos.py`. La revisión visual de las páginas del PDF se hizo aparte, sobre las páginas rasterizadas, y no forma parte de esta comprobación automática.

| ID | Verificación | Estado | Detalle |
|---|---|---|---|
| H01 | PDF legible, 13 páginas y cifras coherentes con los CSV | **OK** | 13 páginas; 4.4 MB; cifras clave ausentes: ninguna; marcas indebidas: ninguna; título: 'Desigualdad territorial en la oferta de autobuses urbanos de Sevilla' |
| H02 | Figuras del informe presentes | **OK** | 18 de 18; vacías: ninguna; sobrantes: ninguna |
| H03 | GeoPackages: capas, CRS EPSG:25830 y geometrías válidas | **OK** | secciones_indicadores 521 MultiPolygon; secciones_prioritarias 33 MultiPolygon; distritos 11 MultiPolygon; limite_municipal 1 MultiPolygon; celdas_ieca_250m 887 MultiPolygon; puntos_demanda 2674 Point; paradas_autobus 1043 Point; contexto_ccaa 18 MultiPolygon; red_peatonal 47443 LineString; barreras_poligonos 180 MultiPolygon; barreras_lineas 1179 MultiLineString; tabla de estilos QGIS: True; problemas: ninguno |
| H04 | Atributos del GeoPackage y CSV del ranking iguales al banco | **OK** | 521 secciones; diferencias por columna: {'cusec': 0, 'pob_ine': 0, 'densidade_ine_hab_km2': 0, 'pct_coberta_400m': 0, 'linhas_cob_manha': 0, 'partidas_h_manha': 0, 'partidas_h_tarde': 0, 'tipologia': 0, 'ranking': 0, 'prioritaria': 0, 'baixa_frequencia': 0}; ranking CSV = banco: True; prioritarias por tipo: {'A': 5, 'B': 5, 'C': 5, 'D': 18} |
| H05 | Cifras del README coherentes con los resultados | **OK** | ausentes: ninguna |
| H06 | Enlaces relativos del README y de docs/ | **OK** | rotos: ninguno |
| H07 | Fragmentos de código en destaque idénticos a los archivos | **OK** | 23 fragmentos; desincronizados: ninguno |
| H08 | Conjunto publicable según .gitignore (sin datos brutos, IDE, caché ni entorno) | **OK** | 134 archivos, 34.3 MB; mayores: produtos/sevilla_oferta_bus_contexto_osm.gpkg (10.9 MB), produtos/informe_sevilla_oferta_autobuses.pdf (4.4 MB), resultados/etapa3/origem_linha_sentido_periodo.csv (3.2 MB), resultados/etapa3/origem_viagem_periodo.csv.gz (2.6 MB), produtos/sevilla_oferta_bus_resultados.gpkg (2.4 MB); prohibidos: ninguno; lista en docs/arquivos_publicaveis.txt |
| H09 | Sin credenciales, correos ni rutas personales en lo publicable | **OK** | coincidencias: ninguna |
| H10 | Licencia MIT del código, condiciones de datos y licencia tipográfica | **LIMITACAO** | MIT solo para código; datos según docs/licencias_datos.md; autoría pendiente de completar por el autor |
