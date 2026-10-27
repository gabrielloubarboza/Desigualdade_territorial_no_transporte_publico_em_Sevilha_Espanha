-- =====================================================================================
-- 02_fonte_chaves.sql — chaves primárias, índices e comentários das tabelas espaciais de `fonte`
-- (criadas pelo carregador a partir dos arquivos originais; colunas em minúsculas)
-- =====================================================================================
ALTER TABLE fonte.ine_secciones_2024    ADD PRIMARY KEY (cusec);
ALTER TABLE fonte.ine_poblacion_seccion ADD PRIMARY KEY (id);
CREATE UNIQUE INDEX ON fonte.ine_poblacion_seccion (coalesce(cod_seccion, 'MUNICIPIO'), sexo, nacionalidad, periodo);
ALTER TABLE fonte.ieca_gridp_250        ADD PRIMARY KEY (gidmp);
CREATE UNIQUE INDEX ON fonte.ieca_gridp_250 (grd_fixid);
ALTER TABLE fonte.tussam_paradas_ide    ADD PRIMARY KEY (objectid);
ALTER TABLE fonte.tussam_lineas_ide     ADD PRIMARY KEY (objectid);
ALTER TABLE fonte.ign_limite_municipal  ADD PRIMARY KEY (gml_id);
ALTER TABLE fonte.osm_nos               ADD PRIMARY KEY (osmid);
ALTER TABLE fonte.osm_arestas           ADD PRIMARY KEY (u, v, key);

COMMENT ON TABLE fonte.ine_secciones_2024 IS
    'INE — seccionado a 01/01/2024 (SECC_CE_20240101), recorte CUMUN=41091, EPSG:25830 original';
COMMENT ON TABLE fonte.ine_poblacion_seccion IS
    'INE — Censo Anual de Población, tabela 69258 (sexo x nacionalidade), linhas do município 41091, 2021-2025';
COMMENT ON TABLE fonte.ieca_gridp_250 IS
    'IECA — malla de población 250 m (grid:gridp_250), 01/01/2024, bbox Sevilla + 500 m, EPSG:25830 (WFS)';
COMMENT ON TABLE fonte.tussam_paradas_ide IS
    'IDE Sevilla / TUSSAM — paradas por linha/rota (ArcGIS TUSSAM_Paradas, atualizado 20/10/2026), EPSG:4326';
COMMENT ON TABLE fonte.tussam_lineas_ide IS
    'IDE Sevilla / TUSSAM — recorridos de linhas (ArcGIS TUSSAM_Lineas, atualizado 20/10/2026), EPSG:4326';
COMMENT ON TABLE fonte.ign_limite_municipal IS
    'IGN — INSPIRE AU, unidade administrativa 34014141091 (Sevilla), EPSG:25830 — apenas comparação';
COMMENT ON TABLE fonte.osm_nos IS 'OSM via OSMnx (walk, simplificada, não direcionada), EPSG:25830';
COMMENT ON TABLE fonte.osm_arestas IS 'OSM via OSMnx (walk, simplificada, não direcionada), EPSG:25830';

CREATE INDEX ON fonte.osm_arestas (u);
CREATE INDEX ON fonte.osm_arestas (v);
CREATE INDEX ON fonte.tussam_paradas_ide (nodo);
CREATE INDEX ON fonte.tussam_paradas_ide (linea);
