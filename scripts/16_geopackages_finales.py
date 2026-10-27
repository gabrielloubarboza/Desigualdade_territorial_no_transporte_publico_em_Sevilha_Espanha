"""Etapa 5 — GeoPackages finales para distribución (produtos/), a partir del banco.

Uso:  .venv\\Scripts\\python.exe scripts\\16_geopackages_finales.py [--sin-qgis]

- produtos/sevilla_oferta_bus_resultados.gpkg  — indicadores por sección, prioritarias, distritos, límite,
  celdas IECA, puntos de demanda, paradas GTFS con oferta; tablas `metadatos_capas` y `diccionario_campos`.
- produtos/sevilla_oferta_bus_contexto_osm.gpkg — red peatonal utilizada y barreras (derivados de OSM, ODbL).
Todo en EPSG:25830. No incluye la capa oficial de paradas de la IDE Sevilla (no redistribuible).
Si QGIS está instalado, ejecuta scripts/qgis_estilos_geopackages.py para verificar la apertura de las
capas y guardar estilos por defecto en cada GeoPackage.
"""
from __future__ import annotations

import os
import subprocess
import sys

import geopandas as gpd
import pandas as pd
import pyogrio
from sqlalchemy import create_engine, text

from comum import caminho, carregar_config, conninfo

CFG = carregar_config()
SAIDA = caminho("produtos")
RESULTADOS = SAIDA / "sevilla_oferta_bus_resultados.gpkg"
CONTEXTO = SAIDA / "sevilla_oferta_bus_contexto_osm.gpkg"
QGIS_PYTHON = os.environ.get("QGIS_PYTHON", r"C:\Program Files\QGIS 3.40.8\bin\python-qgis-ltr.bat")

DISTRITOS = {"01": "Casco Antiguo", "02": "Macarena", "03": "Nervión", "04": "Cerro-Amate", "05": "Sur",
             "06": "Triana", "07": "Norte", "08": "San Pablo-Santa Justa", "09": "Este-Alcosa-Torreblanca",
             "10": "Bellavista-La Palmera", "11": "Los Remedios"}

ATRIB = {
    "INE": "INE — Censo Anual de Población 2024 y seccionado 01/01/2024 (reutilización citando la fuente)",
    "IECA": "IECA, Junta de Andalucía — Distribución espacial de la población 2024, malla 250 m (CC BY 4.0)",
    "GTFS": "Powered by MITRAMS — GTFS TUSSAM 20260928 del Punto de Acceso Nacional (dato procesado)",
    "OSM": "© OpenStreetMap contributors (ODbL 1.0)",
}

CAPAS_RESULTADOS = {
    "secciones_indicadores": (
        "SELECT * FROM analise.diag_resultado_seccion",
        "521 secciones censales INE 2024 con indicadores de densidad, cobertura a 400 m, líneas y salidas por "
        "periodo, tipología A–D y ranking", "INE; IECA; GTFS; indicadores calculados sobre red OSM"),
    "secciones_prioritarias": (
        "SELECT * FROM analise.diag_resultado_seccion WHERE prioritaria ORDER BY ranking",
        "33 secciones de alta densidad con al menos una deficiencia relativa de oferta (subconjunto de la capa anterior)",
        "INE; IECA; GTFS; indicadores calculados sobre red OSM"),
    "distritos": (
        "SELECT d.*, g.geom FROM analise.diag_sintese_distrito d JOIN (SELECT cdis, ST_Multi(ST_Union(geom))::geometry(MultiPolygon, 25830) AS geom FROM prep.secciones GROUP BY cdis) g USING (cdis)",
        "Distritos censales (código INE) con síntesis de la clasificación", "INE; IECA; GTFS"),
    "limite_municipal": (
        "SELECT fonte AS fuente, area_km2, geom FROM prep.limite_municipal WHERE principal",
        "Límite municipal de Sevilla (disolución del seccionado INE 2024)", "INE"),
    "celdas_ieca_250m": (
        "SELECT gidmp, grd_fixid, cmun, pob_tot, sigilo_total_convencional, celda_multimunicipal, frac_dentro_municipio, "
        "n_secciones, relacao_secoes AS relacion_secciones, geom FROM prep.grid_250",
        "887 celdas de 250 m que tocan Sevilla; pob_tot = 2 con sigilo_total_convencional indica valor convencional",
        "IECA"),
    "puntos_demanda": (
        """SELECT r.origem_id, r.cusec, r.gidmp, r.pob_estimada, r.sigilo_total_convencional, r.situacao AS situacion_400m,
                  r.confiabilidade AS confiabilidad, r.n_paradas_400m, r.dist_parada_mais_proxima_m, r.dist_euclidiana_parada_mais_proxima_m,
                  m.situacao_oferta AS situacion_oferta_manana, m.n_linhas AS lineas_manana, m.partidas_hora AS salidas_h_manana,
                  md.n_linhas AS lineas_mediodia, md.partidas_hora AS salidas_h_mediodia,
                  t.n_linhas AS lineas_tarde, t.partidas_hora AS salidas_h_tarde, r.geom
           FROM analise.resultado_origem r
           JOIN analise.oferta_origem_periodo m  ON m.origem_id  = r.origem_id AND m.periodo  = 'manha'
           JOIN analise.oferta_origem_periodo md ON md.origem_id = r.origem_id AND md.periodo = 'meio_dia'
           JOIN analise.oferta_origem_periodo t  ON t.origem_id  = r.origem_id AND t.periodo  = 'tarde'""",
        "2.674 puntos representativos (celda IECA x sección) con población estimada y oferta accesible a 400 m; "
        "no son localizaciones residenciales exactas", "IECA; INE; GTFS; indicadores calculados sobre red OSM"),
    "paradas_autobus": (
        "SELECT stop_id, stop_name, categoria, situacao_ligacao AS situacion_conexion, dentro_municipio, linhas_dia AS lineas_dia, "
        "partidas_dia AS salidas_dia, partidas_h_manha AS salidas_h_manana, linhas_manha AS lineas_manana, "
        "partidas_h_tarde AS salidas_h_tarde, geom FROM analise.v_diag_paradas",
        "Paradas de autobús del GTFS TUSSAM con salidas programadas el 21/10/2026 (sin capa IDE Sevilla)", "GTFS"),
}
CAPAS_CONTEXTO = {
    "red_peatonal": (
        "SELECT aresta_id, highway, name, bridge, tunnel, comprimento_m AS longitud_m, utilizavel AS utilizable, "
        "motivo_exclusao AS motivo_exclusion, componente, geom FROM analise.rede_arestas",
        "Red peatonal OSM (OSMnx 'walk', no dirigida) con la regla de uso de la etapa 2", "OSM"),
    "barreras_poligonos": (
        "SELECT barreira_id, osm_id, classe AS clase, name, ST_Multi(geom)::geometry(MultiPolygon, 25830) AS geom "
        "FROM analise.barreiras WHERE ST_Dimension(geom) = 2",
        "Masas de agua (río, dársena, lagos) usadas como barrera para validar conexiones", "OSM"),
    "barreras_lineas": (
        "SELECT barreira_id, osm_id, classe AS clase, name, ST_Multi(geom)::geometry(MultiLineString, 25830) AS geom "
        "FROM analise.barreiras WHERE ST_Dimension(geom) = 1",
        "Cursos de agua, ferrocarriles y vías de gran capacidad a nivel usados como barrera", "OSM"),
}

CAMPOS = {
    "cusec": "Código INE de la sección censal (provincia+municipio+distrito+sección)",
    "cdis": "Código INE del distrito censal",
    "area_km2": "Área total de la sección (km², EPSG:25830)",
    "area_habitada_km2": "Área de celdas IECA habitadas fuera de agua, parques y ferrocarril (km²) — complementaria",
    "pob_ine": "Población residente INE a 01/01/2024 (Censo Anual de Población) — referencia oficial",
    "densidade_ine_hab_km2": "Densidad oficial: pob_ine / area_km2 (hab./km²) — variable de clasificación",
    "densidade_area_habitada_hab_km2": "pob_ine / area_habitada_km2 — solo informativa",
    "pob_grade": "Población estimada por la malla IECA dentro de la sección (denominador de la accesibilidad)",
    "pob_coberta_400m": "Población estimada con parada con servicio a ≤ 400 m de recorrido peatonal",
    "pob_sem_cobertura": "Población estimada sin parada a ≤ 400 m",
    "pob_nao_determinada": "Población estimada con accesibilidad no determinada (conexión a la red incierta)",
    "pct_coberta_400m": "% de pob_grade con parada a ≤ 400 m",
    "pct_sem_cobertura_400m": "% de pob_grade sin parada a ≤ 400 m",
    "pct_nao_determinada_400m": "% de pob_grade no determinada",
    "dist_media_ponderada_m": "Recorrido medio (ponderado por población) a la parada más cercana (m)",
    "pct_pob_perto_limiar_400m": "% de pob_grade con parada más cercana a 350–450 m (sensibilidad al umbral)",
    "linhas_manha": "Líneas distintas accesibles 07–09 (media ponderada; sin cobertura = 0)",
    "linhas_meio_dia": "Ídem 12–14", "linhas_tarde": "Ídem 17–19",
    "linhas_cob_manha": "Líneas accesibles 07–09, media solo entre población cubierta (criterio de clasificación)",
    "linhas_cob_meio_dia": "Ídem 12–14", "linhas_cob_tarde": "Ídem 17–19",
    "partidas_h_manha": "Salidas programadas accesibles por hora 07–09 (viajes deduplicados; sin cobertura = 0)",
    "partidas_h_meio_dia": "Ídem 12–14", "partidas_h_tarde": "Ídem 17–19",
    "partidas_h_cob_manha": "Salidas/h 07–09, media solo entre población cubierta (criterio de clasificación)",
    "partidas_h_cob_meio_dia": "Ídem 12–14", "partidas_h_cob_tarde": "Ídem 17–19",
    "pob_sem_oferta_manha": "Población estimada sin parada o con parada pero sin salidas 07–09",
    "pob_sem_oferta_meio_dia": "Ídem 12–14", "pob_sem_oferta_tarde": "Ídem 17–19",
    "pob_coberta_sem_servico_manha": "Población con parada a 400 m pero sin salidas 07–09",
    "menor_intervalo_min_manha": "Menor intervalo medio (min) de una misma línea-sentido accesible 07–09",
    "pct_viagens_horario_interpolado": "% de embarques con horario interpolado entre puntos de control (GTFS)",
    "razao_grade_ine": "pob_grade / pob_ine (la malla no sigue los límites de las secciones)",
    "n_pontos": "Número de puntos de demanda en la sección",
    "situacao_dados": "Situación de los datos de la etapa 2",
    "alta_densidade": "Densidad ≥ P75 municipal (30.976,8 hab./km²)",
    "baixa_cobertura": "pct_coberta_400m < cobertura municipal (94,36 %)",
    "baixa_diversidade_linhas": "linhas_cob_manha ≤ P25 (2,04); nulo si no hay población cubierta",
    "baixa_frequencia": "partidas_h_cob_manha ≤ P25 (15,21); nulo si no hay población cubierta",
    "informacao_incompleta": "pct_nao_determinada_400m > 10 % (ninguna sección)",
    "n_deficiencias": "Número de deficiencias (0–3)",
    "deficiencias": "Lista de deficiencias (cobertura, linhas, frequencia)",
    "deficiencia_acesso": "Dimensión acceso: baja cobertura",
    "deficiencia_servico": "Dimensión servicio: pocas líneas y/o baja frecuencia",
    "n_dimensoes": "Número de dimensiones deficientes (acceso, servicio)",
    "tipologia": "A baja cobertura · B pocas líneas · C baja frecuencia · D combinadas · sin deficiencia · fuera de alta densidad",
    "prioritaria": "Alta densidad y al menos una deficiencia",
    "ranking": "Orden de prioridad (criterios lexicográficos explícitos; ver metodología)",
    "ranking_ordem_inicial": "Orden con el número de deficiencias como primer criterio (comparación)",
    "dif_tarde_manha": "partidas_h_tarde − partidas_h_manha",
    "dif_meio_dia_manha": "partidas_h_meio_dia − partidas_h_manha",
    "var_pct_tarde_manha": "Variación % tarde vs mañana (nula si mañana = 0)",
    "var_pct_meio_dia_manha": "Variación % mediodía vs mañana",
    "prank_manha": "Posición relativa (percent_rank) de partidas_h_manha", "prank_meio_dia": "Ídem mediodía",
    "prank_tarde": "Ídem tarde", "mudanca_posicao_tarde_manha": "prank_tarde − prank_manha",
    "baixa_freq_manha": "Baja frecuencia en 07–09 (P25 del periodo)", "baixa_freq_meio_dia": "Ídem 12–14",
    "baixa_freq_tarde": "Ídem 17–19", "padrao_temporal": "Patrón de baja frecuencia entre periodos",
    "alta_densidade_tercis": "Alta densidad con tercios (sensibilidad)", "tipologia_tercis": "Tipología con tercios",
    "prioritaria_tercis": "Prioritaria con tercios", "ranking_tercis": "Ranking con tercios",
}


def main():
    ci = dict(p.split("=", 1) for p in conninfo(CFG).split())
    engine = create_engine(f"postgresql+psycopg://{ci['user']}@{ci['host']}:{ci['port']}/{ci['dbname']}")
    SAIDA.mkdir(parents=True, exist_ok=True)
    meta = []
    with engine.connect() as c:
        for destino, capas in ((RESULTADOS, CAPAS_RESULTADOS), (CONTEXTO, CAPAS_CONTEXTO)):
            destino.unlink(missing_ok=True)
            for capa, (q, desc, fuentes) in capas.items():
                g = gpd.read_postgis(text(q), c, geom_col="geom")
                for col in g.columns:   # booleanos con nulos: tipo booleano anulable (no texto 'True'/'False')
                    if g[col].dtype == object and set(g[col].dropna().unique()) <= {True, False} and g[col].notna().any():
                        g[col] = g[col].astype("boolean")
                if capa == "distritos":
                    g.insert(1, "nombre", g.cdis.map(DISTRITOS))
                g.to_file(destino, layer=capa, driver="GPKG")
                licencia = "; ".join(ATRIB[k] for k in ATRIB if k in fuentes)
                meta.append(dict(archivo=destino.name, capa=capa, n_registros=len(g), geometria=g.geom_type.iloc[0],
                                 crs="EPSG:25830", descripcion=desc, fuentes_y_atribucion=licencia))
                print(f"  {destino.name}:{capa}: {len(g)}")
    engine.dispose()
    # Contorno de comunidades autónomas (península y Baleares) para el mapa de localización, a partir del
    # seccionado INE 2024 completo (simplificado a 300 m; solo uso cartográfico de contexto)
    shp = caminho("data/raw/ine_seccionado/extract") / CFG["ine_seccionado"]["shapefile"]
    esp = pyogrio.read_dataframe(shp, columns=["CCA", "NCA"], where="CCA NOT IN ('05')")
    esp["geometry"] = esp.geometry.simplify(150)
    esp = esp.dissolve(by=["CCA", "NCA"], as_index=False)
    esp["geometry"] = esp.geometry.buffer(250).buffer(-250).simplify(300)   # cierra huecos de la simplificación
    esp = esp.rename(columns={"CCA": "cca", "NCA": "nombre"}).rename_geometry("geom")
    esp.to_file(RESULTADOS, layer="contexto_ccaa", driver="GPKG")
    meta.append(dict(archivo=RESULTADOS.name, capa="contexto_ccaa", n_registros=len(esp), geometria="MultiPolygon",
                     crs="EPSG:25830", descripcion="Comunidades autónomas (sin Canarias) simplificadas a 300 m, solo para "
                     "el mapa de localización", fuentes_y_atribucion=ATRIB["INE"]))
    print(f"  {RESULTADOS.name}:contexto_ccaa: {len(esp)}")
    md = pd.DataFrame(meta)
    comun = "Proyecto sevilla_oferta_bus — día de referencia 21/10/2026; generado por scripts/16_geopackages_finales.py"
    md["nota"] = comun
    dic = pd.DataFrame([{"capa": "secciones_indicadores / secciones_prioritarias", "campo": k, "descripcion": v}
                        for k, v in CAMPOS.items()])
    for destino in (RESULTADOS, CONTEXTO):
        pyogrio.write_dataframe(md[md.archivo == destino.name].reset_index(drop=True), destino, layer="metadatos_capas",
                                driver="GPKG", append=False)
    pyogrio.write_dataframe(dic, RESULTADOS, layer="diccionario_campos", driver="GPKG")
    print("  metadatos_capas y diccionario_campos escritos")
    if "--sin-qgis" not in sys.argv and os.path.exists(QGIS_PYTHON):
        r = subprocess.run([QGIS_PYTHON, str(caminho("scripts/qgis_estilos_geopackages.py")), str(RESULTADOS), str(CONTEXTO)],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        print(r.stdout.strip())
        if r.returncode != 0:
            print(r.stderr[-2000:])
            raise SystemExit("Fallo en la verificación/estilos con QGIS")
    else:
        print("  QGIS no disponible o --sin-qgis: estilos no guardados")


if __name__ == "__main__":
    main()
