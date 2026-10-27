-- =====================================================================================
-- 06_analise_demanda.sql — Etapa 2: parcelas célula IECA x seção INE e pontos de demanda
-- Parâmetros em analise.parametros (preenchidos por 07_acessibilidade.py a partir do config).
--
-- Regra de população (estimativa espacial, não contagem oficial). Área "habitável" = área da célula
-- fora de água, parques, terrenos ferroviários e faixas de ferrovias/vias expressas (OSM); se a célula
-- não tiver área habitável, usa-se a área total.
--   cota_municipio = 1                                  se a célula é só de Sevilla (cmun = '41091')
--                  = área habitável dentro do município / área habitável da célula   (células multimunicipais)
--                  = 0                                  se a célula não pertence a Sevilla
--   peso_parcela   = área habitável da parcela / soma das áreas habitáveis das parcelas mantidas da célula
--   pob_estimada   = pob_tot x cota_municipio x peso_parcela
-- Parcelas < frac_minima_parcela da célula (área total) são fundidas às demais da mesma célula,
-- salvo se forem a maior parcela da célula. Parcelas com população estimada 0 não geram ponto.
-- Para comparação, guarda-se também a estimativa por área total (pob_estimada_area_total).
-- =====================================================================================

DROP TABLE IF EXISTS analise.parcelas_demanda CASCADE;
CREATE TABLE analise.parcelas_demanda AS
WITH par AS (SELECT
        (SELECT valor FROM prep.parametros WHERE chave = 'municipio_ine')                      AS mun,
        (SELECT valor::float FROM analise.parametros WHERE chave = 'frac_minima_parcela')      AS fmin),
lim AS (SELECT geom FROM prep.limite_municipal WHERE principal),
c AS (
    SELECT g.gidmp, g.grd_fixid, g.cmun, g.pob_tot, g.sigilo_total_convencional, g.sigilo_em_categorias,
           g.celda_multimunicipal, g.frac_dentro_municipio, g.area_m2 AS area_celda_m2, g.geom AS geom_celda,
           coalesce(ST_CollectionExtract(ST_Difference(g.geom, m.mask), 3), g.geom) AS geom_hab
    FROM prep.grid_250 g
    LEFT JOIN LATERAL (SELECT ST_Union(n.geom) AS mask FROM analise.areas_nao_residenciais n
                       WHERE ST_Intersects(n.geom, g.geom)) m ON true
), c2 AS (
    SELECT c.*, ST_Area(c.geom_hab) AS area_hab_celda_m2,
           ST_Area(ST_Intersection(c.geom_hab, lim.geom)) AS area_hab_dentro_m2,
           CASE WHEN c.cmun = par.mun THEN 1.0
                WHEN position(par.mun IN c.cmun) > 0 THEN
                     CASE WHEN ST_Area(c.geom_hab) > 0
                          THEN ST_Area(ST_Intersection(c.geom_hab, lim.geom)) / ST_Area(c.geom_hab)
                          ELSE c.frac_dentro_municipio END
                ELSE 0.0 END AS cota_municipio,
           CASE WHEN position(par.mun IN c.cmun) > 0 AND c.cmun <> par.mun THEN c.frac_dentro_municipio
                WHEN c.cmun = par.mun THEN 1.0 ELSE 0.0 END AS cota_municipio_area_total
    FROM c, par, lim
), i AS (
    SELECT gi.gidmp, gi.cusec, gi.area_intersecao_m2, gi.frac_celda,
           row_number() OVER (PARTITION BY gi.gidmp ORDER BY gi.area_intersecao_m2 DESC, gi.cusec) AS ordem
    FROM prep.grid_seccion_intersecao gi
), k AS (
    SELECT i.*, s.geom AS geom_secao FROM i JOIN prep.secciones s USING (cusec), par
    WHERE i.frac_celda >= par.fmin OR i.ordem = 1
), p AS (
    SELECT k.cusec, k.area_intersecao_m2, k.frac_celda, c2.*,
           ST_Multi(ST_CollectionExtract(ST_Intersection(c2.geom_celda, k.geom_secao), 3)) AS geom_parcela,
           ST_CollectionExtract(ST_Intersection(c2.geom_hab, k.geom_secao), 3) AS geom_parcela_hab
    FROM k JOIN c2 USING (gidmp)
    WHERE c2.cota_municipio > 0 OR c2.cota_municipio_area_total > 0
), w AS (
    SELECT p.*, ST_Area(p.geom_parcela_hab) AS area_hab_parcela_m2,
           sum(ST_Area(p.geom_parcela_hab)) OVER (PARTITION BY p.gidmp) AS soma_hab,
           sum(p.area_intersecao_m2) OVER (PARTITION BY p.gidmp) AS soma_area
    FROM p
)
SELECT w.gidmp || '_' || w.cusec AS origem_id,
       w.gidmp, w.grd_fixid, w.cusec, w.cmun,
       w.pob_tot AS pob_celda, w.cota_municipio,
       w.area_intersecao_m2 AS area_parcela_m2, w.area_hab_parcela_m2, w.frac_celda,
       (w.soma_hab = 0) AS sem_area_habitavel,
       CASE WHEN w.soma_hab > 0 THEN w.area_hab_parcela_m2 / w.soma_hab
            ELSE w.area_intersecao_m2 / w.soma_area END AS peso_parcela,
       w.pob_tot * w.cota_municipio *
           CASE WHEN w.soma_hab > 0 THEN w.area_hab_parcela_m2 / w.soma_hab
                ELSE w.area_intersecao_m2 / w.soma_area END AS pob_estimada,
       w.pob_tot * w.cota_municipio_area_total * w.area_intersecao_m2 / w.soma_area AS pob_estimada_area_total,
       w.sigilo_total_convencional, w.sigilo_em_categorias, w.celda_multimunicipal,
       w.geom_parcela::geometry(MultiPolygon, 25830) AS geom,
       CASE WHEN w.soma_hab > 0 AND w.area_hab_parcela_m2 > 0 THEN ST_Multi(w.geom_parcela_hab)
            ELSE w.geom_parcela END::geometry(MultiPolygon, 25830) AS geom_habitavel
FROM w;
ALTER TABLE analise.parcelas_demanda ADD PRIMARY KEY (origem_id);
CREATE INDEX ON analise.parcelas_demanda (gidmp);
CREATE INDEX ON analise.parcelas_demanda (cusec);
CREATE INDEX ON analise.parcelas_demanda USING gist (geom);
COMMENT ON TABLE analise.parcelas_demanda IS
    'Parcelas célula IECA x seção INE com população estimada por área habitável (estimativa espacial, não contagem INE)';

-- ------------------------------------------------------------------ Pontos de demanda
-- Ponto = centroide da parte habitável da parcela, ou ST_PointOnSurface quando o centroide cai fora dela.
DROP TABLE IF EXISTS analise.pontos_demanda CASCADE;
CREATE TABLE analise.pontos_demanda AS
SELECT d.origem_id, d.gidmp, d.grd_fixid, d.cusec, d.pob_estimada, d.peso_parcela, d.cota_municipio,
       d.sigilo_total_convencional, d.celda_multimunicipal, d.sem_area_habitavel,
       CASE WHEN ST_Contains(d.geom_habitavel, ST_Centroid(d.geom_habitavel)) THEN 'centroide_area_habitavel'
            ELSE 'ponto_na_superficie_area_habitavel' END
       || CASE WHEN d.sem_area_habitavel THEN '_sem_mascara' ELSE '' END AS regra_ponto,
       ST_Contains(d.geom, ST_Centroid(d.geom)) AND NOT ST_Equals(
           ST_Centroid(d.geom),
           CASE WHEN ST_Contains(d.geom_habitavel, ST_Centroid(d.geom_habitavel)) THEN ST_Centroid(d.geom_habitavel)
                ELSE ST_PointOnSurface(d.geom_habitavel) END) AS deslocado_do_centroide,
       (CASE WHEN ST_Contains(d.geom_habitavel, ST_Centroid(d.geom_habitavel)) THEN ST_Centroid(d.geom_habitavel)
             ELSE ST_PointOnSurface(d.geom_habitavel) END)::geometry(Point, 25830) AS geom,
       ST_Centroid(d.geom)::geometry(Point, 25830) AS geom_centroide_parcela
FROM analise.parcelas_demanda d
WHERE d.pob_estimada > 0;
ALTER TABLE analise.pontos_demanda ADD PRIMARY KEY (origem_id);
ALTER TABLE analise.pontos_demanda ADD COLUMN x double precision, ADD COLUMN y double precision,
                                   ADD COLUMN deslocamento_m double precision;
UPDATE analise.pontos_demanda SET x = ST_X(geom), y = ST_Y(geom), deslocamento_m = ST_Distance(geom, geom_centroide_parcela);
CREATE INDEX ON analise.pontos_demanda USING gist (geom);
CREATE INDEX ON analise.pontos_demanda (cusec);
COMMENT ON TABLE analise.pontos_demanda IS
    'Origens: um ponto representativo por parcela célula x seção com população > 0; não é localização residencial exata';
