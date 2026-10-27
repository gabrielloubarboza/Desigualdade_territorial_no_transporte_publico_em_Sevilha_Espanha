-- =====================================================================================
-- 04_qa.sql — estruturas de verificação (comparações entre fontes) e tabela de resultados
-- Os testes em si são executados por scripts/05_testes_integridade.py.
-- =====================================================================================
CREATE TABLE IF NOT EXISTS qa.resultado_testes (
    execucao     timestamptz NOT NULL,
    teste_id     text NOT NULL,
    grupo        text NOT NULL,
    descricao    text NOT NULL,
    status       text NOT NULL CHECK (status IN ('OK', 'LIMITACAO', 'FALHA')),
    detalhe      text,
    PRIMARY KEY (execucao, teste_id)
);

-- Limite municipal: INE (dissolução do seccionado) x IGN
CREATE OR REPLACE VIEW qa.v_comparacao_limites AS
SELECT i.area_km2 AS area_ine_km2, g.area_km2 AS area_ign_km2,
       ST_Area(ST_Difference(i.geom, g.geom)) / 1e6 AS area_so_ine_km2,
       ST_Area(ST_Difference(g.geom, i.geom)) / 1e6 AS area_so_ign_km2,
       ST_HausdorffDistance(ST_Boundary(i.geom), ST_Boundary(g.geom)) AS hausdorff_m,
       ST_NumGeometries(i.geom) AS partes_ine, ST_NumInteriorRings(ST_GeometryN(i.geom, 1)) AS aneis_internos_ine
FROM prep.limite_municipal i, prep.limite_municipal g
WHERE i.fonte = 'ine_seccionado_2024' AND g.fonte = 'ign_inspire_au';

-- Sobreposições entre seções (área > 1 m²)
CREATE OR REPLACE VIEW qa.v_sobreposicao_secciones AS
SELECT a.cusec AS cusec_a, b.cusec AS cusec_b, ST_Area(ST_Intersection(a.geom, b.geom)) AS area_m2
FROM prep.secciones a
JOIN prep.secciones b ON a.cusec < b.cusec AND ST_Intersects(a.geom, b.geom)
WHERE ST_Area(ST_Intersection(a.geom, b.geom)) > 1;

-- Paradas GTFS x camada oficial IDE (mesmo identificador = stop_id / Nodo)
DROP TABLE IF EXISTS qa.paradas_gtfs_ide;
CREATE TABLE qa.paradas_gtfs_ide AS
SELECT coalesce(g.stop_id, i.nodo) AS id,
       g.stop_id IS NOT NULL AS em_gtfs, i.nodo IS NOT NULL AS em_ide,
       g.stop_name AS nome_gtfs, i.nombre AS nome_ide,
       g.serve_onibus, g.serve_bonde, g.serve_onibus_dia_ref, g.dentro_municipio,
       ST_Distance(g.geom, i.geom) AS distancia_m,
       viz.nodo AS ide_mais_proximo, viz.dist AS dist_ide_mais_proximo_m,
       CASE WHEN g.stop_id IS NOT NULL AND i.nodo IS NOT NULL AND ST_Distance(g.geom, i.geom) <= 25 THEN 'mesmo_id_coerente'
            WHEN g.stop_id IS NOT NULL AND i.nodo IS NOT NULL THEN 'mesmo_id_distante'
            WHEN g.stop_id IS NOT NULL THEN 'so_gtfs'
            ELSE 'so_ide' END AS situacao
FROM prep.gtfs_paradas g
FULL JOIN prep.tussam_paradas_ide i ON i.nodo = g.stop_id
LEFT JOIN LATERAL (
    SELECT x.nodo, ST_Distance(x.geom, g.geom) AS dist
    FROM prep.tussam_paradas_ide x
    WHERE g.stop_id IS NOT NULL AND x.nodo <> g.stop_id
    ORDER BY x.geom <-> g.geom LIMIT 1) viz ON true;
ALTER TABLE qa.paradas_gtfs_ide ADD PRIMARY KEY (id);

-- Distância ao longo da linha: stop_sequence (GTFS) x Distancia (IDE), por linha e parada
CREATE OR REPLACE VIEW qa.v_distancia_gtfs_ide AS
WITH g AS (SELECT DISTINCT t.route_id, st.stop_id, st.stop_sequence
           FROM fonte.gtfs_stop_times st JOIN fonte.gtfs_trips t USING (trip_id)),
     i AS (SELECT DISTINCT linea::text AS route_id, nodo::text AS stop_id, distancia FROM fonte.tussam_paradas_ide)
SELECT g.route_id, g.stop_id, g.stop_sequence, i.distancia
FROM g LEFT JOIN i ON i.route_id = g.route_id AND i.stop_id = g.stop_id AND i.distancia = g.stop_sequence;

-- Paradas próximas (< 15 m) com IDs distintos no GTFS (potenciais pares de sentidos opostos ou duplicatas)
CREATE OR REPLACE VIEW qa.v_paradas_gtfs_proximas AS
SELECT a.stop_id AS stop_a, b.stop_id AS stop_b, a.stop_name AS nome_a, b.stop_name AS nome_b,
       ST_Distance(a.geom, b.geom) AS distancia_m
FROM prep.gtfs_paradas a
JOIN prep.gtfs_paradas b ON a.stop_id < b.stop_id AND ST_DWithin(a.geom, b.geom, 15);
