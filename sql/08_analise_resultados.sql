-- =====================================================================================
-- 08_analise_resultados.sql — Etapa 2: classificação das origens, agregação por seção,
-- síntese municipal, exceções e views para QGIS.
--
-- Situação da origem:
--   coberto_400m        existe ao menos uma parada com serviço em 21/10/2026 a <= 400 m de percurso
--   sem_cobertura_400m  ligada ao componente principal, nenhuma parada a <= 400 m e nenhuma parada com
--                       ligação incerta a <= 400 m em linha reta
--   nao_determinado     sem ligação à rede, ligada só a componente isolado, ou com parada de ligação
--                       incerta (sem ligação / componente isolado) a <= 400 m em linha reta
-- Denominador dos percentuais: população estimada pela grade (não a população INE).
-- =====================================================================================

DROP TABLE IF EXISTS analise.resultado_origem CASCADE;
CREATE TABLE analise.resultado_origem AS
WITH par AS (SELECT valor::float AS lim FROM analise.parametros WHERE chave = 'limite_m'),
lig AS (
    SELECT origem_id, count(*) AS n_ligacoes, bool_or(componente = 0) AS ligada_principal,
           min(distancia_m) FILTER (WHERE tipo = 'primaria') AS dist_ligacao_m,
           string_agg(DISTINCT componente::text, ',') AS componentes
    FROM analise.ligacoes_origem GROUP BY origem_id
), pr AS (
    SELECT origem_id, count(*) AS n_paradas_400m,
           array_agg(stop_id ORDER BY distancia_m, stop_id) AS paradas_400m
    FROM analise.origem_parada_400m GROUP BY origem_id
), p400 AS (
    SELECT DISTINCT ON (origem_id) origem_id, stop_id, distancia_m
    FROM analise.origem_parada_400m ORDER BY origem_id, distancia_m, stop_id
), incerta AS (
    SELECT o.origem_id, string_agg(s.stop_id, ',' ORDER BY s.stop_id) AS paradas_incertas
    FROM analise.pontos_demanda o, par
    JOIN analise.paradas_analise s ON s.serve_onibus_dia_ref
         AND s.situacao_ligacao IN ('sem_ligacao', 'ligada_apenas_componente_isolado')
    WHERE ST_DWithin(o.geom, s.geom, par.lim)
    GROUP BY o.origem_id
), euc AS (
    SELECT o.origem_id, e.stop_id, e.d
    FROM analise.pontos_demanda o
    CROSS JOIN LATERAL (SELECT s.stop_id, ST_Distance(s.geom, o.geom) AS d FROM analise.paradas_analise s
                        WHERE s.serve_onibus_dia_ref ORDER BY s.geom <-> o.geom, s.stop_id LIMIT 1) e
)
SELECT o.origem_id, o.gidmp, o.grd_fixid, o.cusec, o.pob_estimada, o.sigilo_total_convencional, o.celda_multimunicipal,
       coalesce(lig.n_ligacoes, 0) AS n_ligacoes, coalesce(lig.ligada_principal, false) AS ligada_componente_principal,
       lig.componentes, lig.dist_ligacao_m,
       coalesce(pr.n_paradas_400m, 0) AS n_paradas_400m, pr.paradas_400m,
       CASE WHEN p400.stop_id IS NOT NULL THEN p400.stop_id ELSE pmp.stop_id END AS stop_mais_proximo,
       CASE WHEN p400.stop_id IS NOT NULL THEN p400.distancia_m ELSE pmp.distancia_m END AS dist_parada_mais_proxima_m,
       euc.stop_id AS stop_mais_proximo_euclidiano, euc.d AS dist_euclidiana_parada_mais_proxima_m,
       CASE WHEN pr.n_paradas_400m > 0 THEN 'coberto_400m'
            WHEN lig.n_ligacoes IS NULL OR NOT lig.ligada_principal OR incerta.origem_id IS NOT NULL THEN 'nao_determinado'
            ELSE 'sem_cobertura_400m' END AS situacao,
       CASE WHEN pr.n_paradas_400m > 0 THEN NULL
            WHEN lig.n_ligacoes IS NULL THEN 'sem_ligacao_a_rede'
            WHEN NOT lig.ligada_principal THEN 'ligada_apenas_a_componente_isolado'
            WHEN incerta.origem_id IS NOT NULL THEN 'parada_proxima_com_ligacao_incerta:' || incerta.paradas_incertas
       END AS motivo_nao_determinado,
       CASE WHEN lig.n_ligacoes IS NULL OR (pr.n_paradas_400m IS NULL AND (NOT lig.ligada_principal OR incerta.origem_id IS NOT NULL))
                 THEN 'indeterminada'
            WHEN lig.dist_ligacao_m <= 100 AND lig.ligada_principal THEN 'alta'
            ELSE 'media' END AS confiabilidade,
       o.geom
FROM analise.pontos_demanda o
LEFT JOIN lig USING (origem_id)
LEFT JOIN pr USING (origem_id)
LEFT JOIN p400 USING (origem_id)
LEFT JOIN incerta USING (origem_id)
LEFT JOIN euc USING (origem_id)
LEFT JOIN analise.parada_mais_proxima pmp USING (origem_id);
ALTER TABLE analise.resultado_origem ADD PRIMARY KEY (origem_id);
CREATE INDEX ON analise.resultado_origem (cusec);
CREATE INDEX ON analise.resultado_origem (situacao);
CREATE INDEX ON analise.resultado_origem USING gist (geom);
COMMENT ON COLUMN analise.resultado_origem.dist_parada_mais_proxima_m IS
    'Percurso na rede (inclui ligações) até a parada com serviço mais próxima; até 5 km; NULL se inalcançável';

-- ------------------------------------------------------------------ Resultado por seção (521 seções)
DROP TABLE IF EXISTS analise.resultado_seccion CASCADE;
CREATE TABLE analise.resultado_seccion AS
WITH r AS (
    SELECT cusec,
           count(*) AS n_pontos,
           sum(pob_estimada) AS pob_grade,
           coalesce(sum(pob_estimada) FILTER (WHERE situacao = 'coberto_400m'), 0)       AS pob_coberta,
           coalesce(sum(pob_estimada) FILTER (WHERE situacao = 'sem_cobertura_400m'), 0) AS pob_sem_cobertura,
           coalesce(sum(pob_estimada) FILTER (WHERE situacao = 'nao_determinado'), 0)    AS pob_nao_determinada,
           count(*) FILTER (WHERE situacao = 'coberto_400m')       AS n_pontos_cobertos,
           count(*) FILTER (WHERE situacao = 'sem_cobertura_400m') AS n_pontos_sem_cobertura,
           count(*) FILTER (WHERE situacao = 'nao_determinado')    AS n_pontos_nao_determinados,
           coalesce(sum(pob_estimada) FILTER (WHERE sigilo_total_convencional), 0) AS pob_valor_convencional_sigilo,
           sum(pob_estimada * dist_parada_mais_proxima_m)
               FILTER (WHERE situacao <> 'nao_determinado' AND dist_parada_mais_proxima_m IS NOT NULL) AS soma_pd,
           sum(pob_estimada)
               FILTER (WHERE situacao <> 'nao_determinado' AND dist_parada_mais_proxima_m IS NOT NULL) AS soma_p
    FROM analise.resultado_origem GROUP BY cusec
)
SELECT s.cusec, s.cdis, s.csec, s.area_km2,
       p.poblacion_total AS pob_ine,
       p.poblacion_total / s.area_km2 AS densidade_ine_hab_km2,
       coalesce(r.pob_grade, 0) AS pob_grade,
       coalesce(r.pob_coberta, 0) AS pob_coberta,
       coalesce(r.pob_sem_cobertura, 0) AS pob_sem_cobertura,
       coalesce(r.pob_nao_determinada, 0) AS pob_nao_determinada,
       CASE WHEN r.pob_grade > 0 THEN 100 * r.pob_coberta / r.pob_grade END AS pct_coberta,
       CASE WHEN r.pob_grade > 0 THEN 100 * r.pob_sem_cobertura / r.pob_grade END AS pct_sem_cobertura,
       CASE WHEN r.pob_grade > 0 THEN 100 * r.pob_nao_determinada / r.pob_grade END AS pct_nao_determinada,
       CASE WHEN r.soma_p > 0 THEN r.soma_pd / r.soma_p END AS dist_media_ponderada_m,
       coalesce(r.n_pontos, 0) AS n_pontos,
       coalesce(r.n_pontos_cobertos, 0) AS n_pontos_cobertos,
       coalesce(r.n_pontos_sem_cobertura, 0) AS n_pontos_sem_cobertura,
       coalesce(r.n_pontos_nao_determinados, 0) AS n_pontos_nao_determinados,
       coalesce(r.pob_valor_convencional_sigilo, 0) AS pob_valor_convencional_sigilo,
       CASE WHEN p.poblacion_total > 0 THEN coalesce(r.pob_grade, 0) / p.poblacion_total END AS razao_grade_ine,
       CASE WHEN r.n_pontos IS NULL THEN 'sem_pontos_de_demanda'
            WHEN r.pob_nao_determinada > 0.5 * r.pob_grade THEN 'maioria_nao_determinada'
            ELSE 'ok' END AS situacao_dados,
       s.geom
FROM prep.secciones s
LEFT JOIN prep.poblacion_seccion p USING (cusec)
LEFT JOIN r USING (cusec);
ALTER TABLE analise.resultado_seccion ADD PRIMARY KEY (cusec);
CREATE INDEX ON analise.resultado_seccion USING gist (geom);
COMMENT ON TABLE analise.resultado_seccion IS
    'Cobertura por seção: populações de cobertura são estimativas da grade IECA; pob_ine é a referência oficial';

-- ------------------------------------------------------------------ Síntese municipal (formato longo)
DROP TABLE IF EXISTS analise.sintese_municipal CASCADE;
CREATE TABLE analise.sintese_municipal AS
WITH o AS (SELECT * FROM analise.resultado_origem),
t AS (SELECT sum(pob_estimada) AS pg FROM o),
pa AS (SELECT * FROM analise.paradas_analise)
SELECT * FROM (VALUES
  (1,  'populacao_ine_2024',                 (SELECT sum(poblacion_total)::float FROM prep.poblacion_seccion), 'hab', 'INE Censo Anual, 01/01/2024 (referência oficial)'),
  (2,  'populacao_grade_publicada_celulas',  (SELECT sum(pob_tot)::float FROM prep.grid_250), 'hab', 'IECA 01/01/2024: 887 células que tocam Sevilla, inclusive parte de vizinhos'),
  (3,  'populacao_grade_estimada_sevilla',   (SELECT pg FROM t), 'hab', 'denominador dos percentuais de cobertura'),
  (4,  'populacao_coberta_400m',             (SELECT sum(pob_estimada) FROM o WHERE situacao = 'coberto_400m'), 'hab', NULL),
  (5,  'populacao_sem_cobertura_400m',       (SELECT sum(pob_estimada) FROM o WHERE situacao = 'sem_cobertura_400m'), 'hab', NULL),
  (6,  'populacao_nao_determinada',          (SELECT sum(pob_estimada) FROM o WHERE situacao = 'nao_determinado'), 'hab', NULL),
  (7,  'pct_coberta_400m',                   (SELECT 100 * sum(pob_estimada) / (SELECT pg FROM t) FROM o WHERE situacao = 'coberto_400m'), '%', 'sobre a população da grade'),
  (8,  'pct_sem_cobertura_400m',             (SELECT 100 * sum(pob_estimada) / (SELECT pg FROM t) FROM o WHERE situacao = 'sem_cobertura_400m'), '%', 'sobre a população da grade'),
  (9,  'pct_nao_determinada',                (SELECT 100 * sum(pob_estimada) / (SELECT pg FROM t) FROM o WHERE situacao = 'nao_determinado'), '%', 'sobre a população da grade'),
  (10, 'populacao_valor_convencional_sigilo',(SELECT sum(pob_estimada) FROM o WHERE sigilo_total_convencional), 'hab', 'células com total convencional 2 (não é contagem exata)'),
  (11, 'dist_media_ponderada_parada_m',      (SELECT sum(pob_estimada * dist_parada_mais_proxima_m) / sum(pob_estimada) FROM o
                                              WHERE situacao <> 'nao_determinado' AND dist_parada_mais_proxima_m IS NOT NULL), 'm', 'percurso na rede, origens determinadas'),
  (12, 'pontos_demanda',                     (SELECT count(*)::float FROM o), 'pontos', NULL),
  (13, 'pontos_cobertos',                    (SELECT count(*)::float FROM o WHERE situacao = 'coberto_400m'), 'pontos', NULL),
  (14, 'pontos_sem_cobertura',               (SELECT count(*)::float FROM o WHERE situacao = 'sem_cobertura_400m'), 'pontos', NULL),
  (15, 'pontos_nao_determinados',            (SELECT count(*)::float FROM o WHERE situacao = 'nao_determinado'), 'pontos', NULL),
  (16, 'paradas_gtfs',                       (SELECT count(*)::float FROM pa), 'paradas', NULL),
  (17, 'paradas_com_servico_onibus_dia',     (SELECT count(*)::float FROM pa WHERE serve_onibus_dia_ref), 'paradas', '21/10/2026'),
  (18, 'paradas_destino_ligadas',            (SELECT count(*)::float FROM pa WHERE destino_analise), 'paradas', NULL),
  (19, 'paradas_ligacao_incerta',            (SELECT count(*)::float FROM pa WHERE situacao_ligacao IN ('sem_ligacao', 'ligada_apenas_componente_isolado')), 'paradas', NULL),
  (20, 'paradas_alcancadas_por_alguma_origem',(SELECT count(DISTINCT stop_id)::float FROM analise.origem_parada_400m), 'paradas', NULL),
  (21, 'pares_origem_parada_400m',           (SELECT count(*)::float FROM analise.origem_parada_400m), 'pares', NULL),
  (22, 'secoes',                             (SELECT count(*)::float FROM analise.resultado_seccion), 'secoes', NULL),
  (23, 'secoes_100pct_cobertas',             (SELECT count(*)::float FROM analise.resultado_seccion WHERE pct_coberta >= 99.9995), 'secoes', NULL),
  (24, 'secoes_sem_pontos_demanda',          (SELECT count(*)::float FROM analise.resultado_seccion WHERE n_pontos = 0), 'secoes', NULL)
) AS v(ordem, indicador, valor, unidade, nota);
ALTER TABLE analise.sintese_municipal ADD PRIMARY KEY (indicador);

-- ------------------------------------------------------------------ Exceções
DROP TABLE IF EXISTS analise.excecoes CASCADE;
CREATE TABLE analise.excecoes AS
SELECT 'origem'::text AS tipo_objeto, origem_id AS id, cusec, pob_estimada AS pob, 'nao_determinado'::text AS tipo,
       motivo_nao_determinado AS detalhe, geom
FROM analise.resultado_origem WHERE situacao = 'nao_determinado'
UNION ALL
SELECT 'origem', origem_id, cusec, pob_estimada, 'ligacao_longa_150m',
       format('ligação primária de %s m', round(dist_ligacao_m::numeric, 1)), geom
FROM analise.resultado_origem WHERE dist_ligacao_m > 150
UNION ALL
SELECT 'origem', p.origem_id, p.cusec, p.pob_estimada, 'parcela_sem_area_habitavel',
       'célula sem área fora de água/parque/ferrovia: peso por área total', p.geom
FROM analise.pontos_demanda p WHERE p.sem_area_habitavel
UNION ALL
SELECT 'parada', stop_id, NULL, NULL, situacao_ligacao, stop_name, geom
FROM analise.paradas_analise WHERE situacao_ligacao IN ('sem_ligacao', 'ligada_apenas_componente_isolado')
UNION ALL
SELECT 'parada', l.stop_id, NULL, NULL, 'ligacao_secundaria_componente_principal',
       format('primária em componente isolado; secundária a %s m', round(l.distancia_m::numeric, 1)), p.geom
FROM analise.ligacoes_parada l JOIN analise.paradas_analise p USING (stop_id) WHERE l.tipo <> 'primaria'
UNION ALL
SELECT 'parada', stop_id, NULL, NULL, 'divergencia_gtfs_ide_' || situacao_ide, stop_name, geom
FROM analise.paradas_analise WHERE serve_onibus_dia_ref AND situacao_ide <> 'mesmo_id_coerente';
ALTER TABLE analise.excecoes ADD PRIMARY KEY (tipo_objeto, id, tipo);

-- ------------------------------------------------------------------ Views para QGIS
CREATE OR REPLACE VIEW analise.v_secciones_cobertura AS
SELECT * FROM analise.resultado_seccion;

CREATE OR REPLACE VIEW analise.v_pontos_demanda AS
SELECT origem_id, cusec, round(pob_estimada::numeric, 2) AS pob_estimada, situacao, confiabilidade,
       n_paradas_400m, stop_mais_proximo, round(dist_parada_mais_proxima_m::numeric, 1) AS dist_parada_m,
       motivo_nao_determinado, sigilo_total_convencional, geom
FROM analise.resultado_origem;

CREATE OR REPLACE VIEW analise.v_paradas AS
SELECT p.stop_id, p.stop_name, p.categoria, p.situacao_ligacao, p.destino_analise, p.situacao_ide,
       coalesce(n.n_origens, 0) AS n_origens_400m, coalesce(n.pob_400m, 0) AS pob_estimada_400m, p.geom
FROM analise.paradas_analise p
LEFT JOIN (SELECT op.stop_id, count(*) AS n_origens, sum(o.pob_estimada) AS pob_400m
           FROM analise.origem_parada_400m op JOIN analise.pontos_demanda o USING (origem_id)
           GROUP BY op.stop_id) n USING (stop_id);

CREATE OR REPLACE VIEW analise.v_ligacoes AS
SELECT 'origem'::text AS tipo_objeto, origem_id AS id, tipo, componente, distancia_m, geom FROM analise.ligacoes_origem
UNION ALL
SELECT 'parada', stop_id, tipo, componente, distancia_m, geom FROM analise.ligacoes_parada;

-- Resumo descritivo por distrito (sem classificação ou prioridade)
CREATE OR REPLACE VIEW analise.v_resumo_distrito AS
SELECT cdis, count(*) AS secoes, sum(pob_ine) AS pob_ine, sum(area_km2) AS area_km2,
       sum(pob_ine) / sum(area_km2) AS densidade_ine_hab_km2,
       sum(pob_grade) AS pob_grade, sum(pob_coberta) AS pob_coberta, sum(pob_sem_cobertura) AS pob_sem_cobertura,
       sum(pob_nao_determinada) AS pob_nao_determinada,
       100 * sum(pob_coberta) / nullif(sum(pob_grade), 0) AS pct_coberta,
       min(pct_coberta) AS pct_coberta_min_secao,
       count(*) FILTER (WHERE pct_coberta < 100 - 1e-6) AS secoes_com_populacao_sem_cobertura
FROM analise.resultado_seccion GROUP BY cdis;

CREATE OR REPLACE VIEW analise.v_origem_parada_linhas AS
SELECT op.origem_id, op.stop_id, op.distancia_m,
       ST_MakeLine(o.geom, s.geom)::geometry(LineString, 25830) AS geom   -- linha reta só para visualização
FROM analise.origem_parada_400m op
JOIN analise.pontos_demanda o USING (origem_id)
JOIN analise.paradas_analise s USING (stop_id);

ANALYZE analise.resultado_origem, analise.resultado_seccion, analise.origem_parada_400m;
