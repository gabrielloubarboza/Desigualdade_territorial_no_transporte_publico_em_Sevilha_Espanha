"""Etapa 5 — Genera docs/codigo_em_destaque.md con fragmentos REALES del repositorio.

Uso:  .venv\\Scripts\\python.exe scripts\\19_codigo_em_destaque.py

Cada fragmento se localiza por un marcador de inicio y otro de fin en el archivo fuente; el documento
enlaza al rango de líneas exacto (enlaces relativos que funcionan en GitHub). Si un marcador deja de
existir, el script falla: así el documento no puede quedar desincronizado del código.
"""
from __future__ import annotations

from comum import caminho

LANG = {".sql": "sql", ".py": "python", ".ps1": "powershell"}

SECCIONES = [
    ("PostgreSQL y SQL", [
        ("Estructura del banco: esquemas y horarios GTFS sin pérdida",
         "Los horarios GTFS pueden superar las 24:00:00, así que se guardan como texto y se convierten a segundos del día "
         "de servicio con una función SQL inmutable.",
         "sql/01_schemas_fonte.sql", "CREATE TABLE fonte.gtfs_stop_times (", "$$;"),
        ("Importación del GTFS con COPY",
         "Carga cada archivo del feed con `COPY ... FROM STDIN`, usando la cabecera real del archivo como lista de columnas "
         "(las claves foráneas validan la integridad durante la carga).",
         "scripts/04_carregar_banco.py", "def carregar_gtfs(conn) -> dict:", "    return contagens"),
        ("Calendario: servicios activos el día de referencia",
         "Relaciona `calendar` y `calendar_dates` con la fecha de referencia; el día de la semana indexa un array de columnas.",
         "sql/03_prep.sql", "CREATE TABLE prep.gtfs_servicos_dia AS", "WHERE x.date = p.d AND x.exception_type = 1;"),
        ("Deduplicación: un viaje cuenta una vez por origen y franja",
         "Un mismo viaje puede pasar por varias paradas accesibles; una ventana `row_number()` conserva solo el embarque de "
         "menor caminata y registra en cuántas paradas era accesible.",
         "sql/10_oferta_origem.sql", "CREATE TABLE analise.origem_viagem_periodo AS", "FROM c WHERE ordem = 1;"),
        ("Indicadores de oferta por sección",
         "Medias ponderadas por población (no sumas de salidas entre orígenes) y poblaciones por situación de oferta.",
         "sql/11_oferta_agregacao.sql", "WITH o AS (SELECT * FROM analise.oferta_origem_periodo),", "    FROM o GROUP BY cusec, periodo"),
    ]),
    ("PostGIS", [
        ("Preparación de las secciones censales",
         "Comprueba la validez de las geometrías originales del INE, corrige solo si es necesario y calcula el área en EPSG:25830.",
         "sql/03_prep.sql", "CREATE TABLE prep.secciones AS", "UPDATE prep.secciones SET area_m2 = ST_Area(geom), area_km2 = ST_Area(geom) / 1e6;"),
        ("Intersección malla IECA × secciones",
         "Área de cada intersección celda–sección, base para repartir la población de las celdas que cruzan límites.",
         "sql/03_prep.sql", "CREATE TABLE prep.grid_seccion_intersecao AS", "WHERE ST_Area(ST_Intersection(g.geom, s.geom)) > 0;"),
        ("Reparto de población por área habitable",
         "La población de cada celda se reparte entre secciones según el área fuera de agua, parques y suelo ferroviario; las "
         "celdas compartidas con otros municipios solo aportan su cuota de Sevilla.",
         "sql/06_analise_demanda.sql", "SELECT w.gidmp || '_' || w.cusec AS origem_id,", "AS pob_estimada_area_total,"),
        ("Conexión a la red sin cruzar barreras",
         "Las conexiones punto→calle candidatas se descartan si atraviesan agua, ferrocarril o autovía a nivel.",
         "sql/07_analise_ligacoes.sql", "    val AS (", "                       ELSE ST_Crosses(b.geom, c.lig) END)"),
        ("Exportación de resultados espaciales",
         "Lectura de vistas PostGIS y escritura en GeoPackage, convirtiendo booleanos con nulos a un tipo booleano anulable.",
         "scripts/16_geopackages_finales.py", '                g = gpd.read_postgis(text(q), c, geom_col="geom")',
         '                g.to_file(destino, layer=capa, driver="GPKG")'),
    ]),
    ("Python", [
        ("Descarga reproducible e idempotente",
         "Evita volver a descargar archivos idénticos (md5, tamaño o Last-Modified + hash) y registra cada fuente en el manifiesto.",
         "scripts/comum.py", "def baixar(url: str, destino: Path, md5_esperado: str | None = None, forcar: bool = False) -> dict:",
         '            info["acao"] = "mantido (Last-Modified e hash identicos)"'),
        ("Inspección del GTFS: stop_sequence como distancia",
         "Comprueba que `stop_sequence` es la distancia acumulada en metros (base de la interpolación de horarios).",
         "scripts/02_inspecionar_gtfs.py", "    # stop_sequence como distância acumulada", '"trechos_velocidade_acima_60kmh"'),
        ("Red peatonal OpenStreetMap",
         "Descarga con OSMnx conservando componentes desconectados (no se unen artificialmente) y los identifica con NetworkX.",
         "scripts/03_rede_osm.py", "    G = ox.graph_from_polygon(", '    nx.set_node_attributes(Gu, comp_id, "componente")'),
        ("Distancias caminables limitadas a 400 m",
         "Un Dijkstra acotado por conexión de parada; las conexiones de origen y parada se suman fuera del grafo para no crear "
         "pasos entre componentes.",
         "scripts/rede_acessibilidade.py", "    # 1) Pares origem-parada até o limite", "                        pares[chave] = cand"),
        ("Interpolación temporal por distancia",
         "Horario en las paradas sin hora explícita, interpolado entre los puntos de control anterior y siguiente.",
         "sql/03_prep.sql", "CREATE TABLE prep.gtfs_horarios_dia AS", "JOIN b b1 ON b1.trip_id = l.trip_id AND b1.dist_m = l.d1;"),
        ("Salidas programadas: sin la última parada",
         "En la última parada de cada viaje no se puede embarcar, así que no cuenta como salida.",
         "sql/09_oferta_partidas.sql", "CREATE TABLE analise.partidas_dia AS", "WHERE h.dist_m < h.dist_final;"),
        ("Análisis de sensibilidad a la interpolación",
         "Escenarios ±2 min y envolventes entre puntos de control, solo para los horarios interpolados.",
         "sql/12_oferta_sensibilidade.sql", "JOIN prep.periodos_analise pa ON CASE", "END;"),
        ("Pruebas con recálculo independiente",
         "Las pruebas recalculan en pandas, sin usar las tablas de la etapa, las líneas y viajes de todos los orígenes.",
         "scripts/11_testes_etapa3.py", "def recalculo_independente(conn):", "    return pd.concat(linhas)"),
        ("Automatización por etapa",
         "Cada etapa se reconstruye con un script de PowerShell que detiene la ejecución ante cualquier fallo.",
         "scripts/executar_etapa4.ps1", "$passos = @(", 'Write-Host "Etapa 4 concluida." -ForegroundColor Green'),
    ]),
    ("Diagnóstico territorial", [
        ("Umbrales explícitos y reproducibles",
         "Percentiles de la distribución municipal (y la cobertura media) calculados en SQL para dos escenarios.",
         "sql/13_diagnostico_classificacao.sql", "    SELECT c.cenario, 'alta_densidade' AS criterio,", "    FROM cen c\n    UNION ALL\n    SELECT c.cenario, 'baixa_cobertura'"),
        ("Tipología A–D con precedencia sin ambigüedad",
         "Cada sección recibe una sola categoría; las deficiencias se conservan también como indicadores binarios.",
         "sql/13_diagnostico_classificacao.sql", "       CASE WHEN NOT alta_densidade        THEN 'fora_alta_densidade'",
         "       (alta_densidade AND NOT informacao_incompleta AND n_deficiencias > 0) AS prioritaria"),
        ("Ranking por criterios lexicográficos",
         "Sin puntuación compuesta: dimensiones deficientes, población sin oferta, frecuencia, líneas, densidad y código.",
         "sql/13_diagnostico_classificacao.sql", "UPDATE analise.diag_classificacao c SET ranking = r.rk, ranking_ordem_inicial = r.rk0",
         "WHERE r.cenario = c.cenario AND r.cusec = c.cusec;"),
        ("Consulta de las secciones prioritarias",
         "Vista espacial para QGIS y consulta usada en la exportación del ranking.",
         "scripts/15_exportar_etapa4.py", '    "ranking_prioritarias.csv": """', '        FROM analise.diag_resultado_seccion WHERE prioritaria ORDER BY ranking""",'),
    ]),
]


def extraer(ruta, ini, fin):
    lineas = caminho(ruta).read_text(encoding="utf-8").splitlines()
    texto = "\n".join(lineas)
    a = next((i for i, l in enumerate(lineas) if ini in l), None)
    if a is None:
        raise SystemExit(f"Marcador de inicio no encontrado en {ruta}: {ini!r}")
    if "\n" in fin:   # marcador multilínea: se busca en el texto a partir de la línea de inicio
        pos = texto.find(fin, len("\n".join(lineas[:a])))
        if pos < 0:
            raise SystemExit(f"Marcador de fin no encontrado en {ruta}: {fin!r}")
        b = texto[:pos].count("\n")
    else:
        b = next((i for i in range(a, len(lineas)) if fin in lineas[i]), None)
        if b is None:
            raise SystemExit(f"Marcador de fin no encontrado en {ruta}: {fin!r}")
    return a + 1, b + 1, "\n".join(lineas[a:b + 1])


def main():
    out = ["# Código en destaque", "",
           "Fragmentos reales del proyecto, extraídos automáticamente por "
           "[`scripts/19_codigo_em_destaque.py`](../scripts/19_codigo_em_destaque.py). Cada título enlaza al archivo "
           "completo y al rango de líneas. Los comentarios del código están en portugués (idioma de trabajo del proyecto).", "",
           "## Índice", ""]
    for sec, items in SECCIONES:
        out.append(f"- **{sec}**: " + " · ".join(t for t, *_ in items))
    out.append("")
    for sec, items in SECCIONES:
        out += [f"## {sec}", ""]
        for titulo, desc, ruta, ini, fin in items:
            a, b, codigo = extraer(ruta, ini, fin)
            lang = LANG[caminho(ruta).suffix]
            out += [f"### {titulo}", "", desc, "",
                    f"Archivo: [`{ruta}`](../{ruta}#L{a}-L{b}) (líneas {a}–{b})", "",
                    f"```{lang}", codigo, "```", ""]
    caminho("docs/codigo_em_destaque.md").write_text("\n".join(out), encoding="utf-8")
    print(f"  docs/codigo_em_destaque.md: {sum(len(i) for _, i in SECCIONES)} fragmentos")


if __name__ == "__main__":
    main()
