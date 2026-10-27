-- =====================================================================================
-- 14_diagnostico_sinteses.sql — Etapa 4: tabela consolidada, sínteses, relação densidade x oferta,
-- sensibilidade (quartis x tercis), conferência das prioritárias e views espaciais (EPSG:25830)
-- =====================================================================================

-- ------------------------------------------------------------------ Tabela consolidada por seção (521)
DROP TABLE IF EXISTS analise.diag_resultado_seccion CASCADE;
CREATE TABLE analise.diag_resultado_seccion AS
SELECT b.cusec, b.cdis, b.area_km2, b.area_habitada_km2, b.pob_ine, b.densidade_ine_hab_km2,
       b.densidade_area_habitada_hab_km2, b.pob_grade, b.pob_coberta_400m, b.pob_sem_cobertura, b.pob_nao_determinada,
       b.pct_coberta_400m, b.pct_sem_cobertura_400m, b.pct_nao_determinada_400m, b.dist_media_ponderada_m,
       b.pct_pob_perto_limiar_400m,
       b.linhas_manha, b.linhas_meio_dia, b.linhas_tarde, b.linhas_cob_manha, b.linhas_cob_meio_dia, b.linhas_cob_tarde,
       b.partidas_h_manha, b.partidas_h_meio_dia, b.partidas_h_tarde,
       b.partidas_h_cob_manha, b.partidas_h_cob_meio_dia, b.partidas_h_cob_tarde,
       b.pob_sem_oferta_manha, b.pob_sem_oferta_meio_dia, b.pob_sem_oferta_tarde, b.pob_coberta_sem_servico_manha,
       b.menor_intervalo_min_manha, b.pct_viagens_horario_interpolado, b.razao_grade_ine, b.n_pontos, b.situacao_dados,
       c.alta_densidade, c.baixa_cobertura, c.baixa_diversidade_linhas, c.baixa_frequencia, c.informacao_incompleta,
       c.n_deficiencias, c.deficiencias, c.deficiencia_acesso, c.deficiencia_servico, c.n_dimensoes,
       c.tipologia, c.prioritaria, c.ranking, c.ranking_ordem_inicial,
       t.dif_tarde_manha, t.dif_meio_dia_manha, t.var_pct_tarde_manha, t.var_pct_meio_dia_manha,
       t.prank_manha, t.prank_meio_dia, t.prank_tarde, t.mudanca_posicao_tarde_manha,
       t.baixa_freq_manha, t.baixa_freq_meio_dia, t.baixa_freq_tarde, t.padrao_temporal,
       s.alta_densidade AS alta_densidade_tercis, s.tipologia AS tipologia_tercis, s.prioritaria AS prioritaria_tercis,
       s.ranking AS ranking_tercis,
       b.geom
FROM analise.diag_base b
JOIN analise.diag_classificacao c ON c.cusec = b.cusec AND c.cenario = 'principal'
JOIN analise.diag_classificacao s ON s.cusec = b.cusec AND s.cenario = 'sensibilidade_tercis'
JOIN analise.diag_temporal t ON t.cusec = b.cusec;
ALTER TABLE analise.diag_resultado_seccion ADD PRIMARY KEY (cusec);
CREATE INDEX ON analise.diag_resultado_seccion USING gist (geom);
CREATE INDEX ON analise.diag_resultado_seccion (ranking);
COMMENT ON TABLE analise.diag_resultado_seccion IS
    'Etapa 4: indicadores originais + deficiências + tipologia + ranking + períodos + sensibilidade, por seção INE';

-- ------------------------------------------------------------------ Sínteses por tipologia (dois cenários)
DROP TABLE IF EXISTS analise.diag_sintese_tipologia CASCADE;
CREATE TABLE analise.diag_sintese_tipologia AS
SELECT c.cenario, c.tipologia, count(*) AS secoes, sum(b.pob_ine) AS pob_ine,
       100.0 * sum(b.pob_ine) / (SELECT sum(pob_ine) FROM analise.diag_base) AS pct_pob_ine,
       sum(b.pob_grade) AS pob_grade, sum(b.pob_sem_cobertura) AS pob_sem_cobertura, sum(b.pob_sem_oferta_manha) AS pob_sem_oferta_manha
FROM analise.diag_classificacao c JOIN analise.diag_base b USING (cusec)
GROUP BY 1, 2;
ALTER TABLE analise.diag_sintese_tipologia ADD PRIMARY KEY (cenario, tipologia);

-- Respostas diretas (formato longo; contagens não exclusivas entre si)
DROP TABLE IF EXISTS analise.diag_sintese_municipal CASCADE;
CREATE TABLE analise.diag_sintese_municipal AS
WITH c AS (SELECT c.*, b.pob_grade, b.pob_sem_cobertura AS pob_sem_cob FROM analise.diag_classificacao c JOIN analise.diag_base b USING (cusec)),
q(ordem, indicador, filtro) AS (VALUES
    (1, 'secoes_alta_densidade', 'alta_densidade'),
    (2, 'alta_densidade_baixa_cobertura', 'alta_densidade AND baixa_cobertura'),
    (3, 'alta_densidade_baixa_diversidade_linhas', 'alta_densidade AND baixa_diversidade_linhas'),
    (4, 'alta_densidade_baixa_frequencia', 'alta_densidade AND baixa_frequencia'),
    (5, 'alta_densidade_2_ou_mais_deficiencias', 'alta_densidade AND n_deficiencias >= 2'),
    (6, 'alta_densidade_acesso_e_servico', 'alta_densidade AND n_dimensoes = 2'),
    (7, 'secoes_prioritarias', 'prioritaria'),
    (8, 'alta_densidade_sem_deficiencia', 'alta_densidade AND n_deficiencias = 0'),
    (9, 'todas_baixa_cobertura', 'baixa_cobertura'),
    (10, 'todas_baixa_diversidade_linhas', 'baixa_diversidade_linhas'),
    (11, 'todas_baixa_frequencia', 'baixa_frequencia'))
SELECT cen.cenario, q.ordem, q.indicador,
       (SELECT count(*) FROM c WHERE c.cenario = cen.cenario AND CASE q.filtro
            WHEN 'alta_densidade' THEN c.alta_densidade
            WHEN 'alta_densidade AND baixa_cobertura' THEN c.alta_densidade AND c.baixa_cobertura
            WHEN 'alta_densidade AND baixa_diversidade_linhas' THEN c.alta_densidade AND coalesce(c.baixa_diversidade_linhas, false)
            WHEN 'alta_densidade AND baixa_frequencia' THEN c.alta_densidade AND coalesce(c.baixa_frequencia, false)
            WHEN 'alta_densidade AND n_deficiencias >= 2' THEN c.alta_densidade AND c.n_deficiencias >= 2
            WHEN 'alta_densidade AND n_dimensoes = 2' THEN c.alta_densidade AND c.n_dimensoes = 2
            WHEN 'prioritaria' THEN c.prioritaria
            WHEN 'alta_densidade AND n_deficiencias = 0' THEN c.alta_densidade AND c.n_deficiencias = 0
            WHEN 'baixa_cobertura' THEN c.baixa_cobertura
            WHEN 'baixa_diversidade_linhas' THEN coalesce(c.baixa_diversidade_linhas, false)
            WHEN 'baixa_frequencia' THEN coalesce(c.baixa_frequencia, false) END) AS secoes,
       (SELECT sum(c.pob_ine) FROM c WHERE c.cenario = cen.cenario AND CASE q.filtro
            WHEN 'alta_densidade' THEN c.alta_densidade
            WHEN 'alta_densidade AND baixa_cobertura' THEN c.alta_densidade AND c.baixa_cobertura
            WHEN 'alta_densidade AND baixa_diversidade_linhas' THEN c.alta_densidade AND coalesce(c.baixa_diversidade_linhas, false)
            WHEN 'alta_densidade AND baixa_frequencia' THEN c.alta_densidade AND coalesce(c.baixa_frequencia, false)
            WHEN 'alta_densidade AND n_deficiencias >= 2' THEN c.alta_densidade AND c.n_deficiencias >= 2
            WHEN 'alta_densidade AND n_dimensoes = 2' THEN c.alta_densidade AND c.n_dimensoes = 2
            WHEN 'prioritaria' THEN c.prioritaria
            WHEN 'alta_densidade AND n_deficiencias = 0' THEN c.alta_densidade AND c.n_deficiencias = 0
            WHEN 'baixa_cobertura' THEN c.baixa_cobertura
            WHEN 'baixa_diversidade_linhas' THEN coalesce(c.baixa_diversidade_linhas, false)
            WHEN 'baixa_frequencia' THEN coalesce(c.baixa_frequencia, false) END) AS pob_ine
FROM q CROSS JOIN (VALUES ('principal'), ('sensibilidade_tercis')) cen(cenario);
ALTER TABLE analise.diag_sintese_municipal ADD COLUMN pct_pob_ine double precision;
UPDATE analise.diag_sintese_municipal SET pct_pob_ine = 100.0 * coalesce(pob_ine, 0) / (SELECT sum(pob_ine) FROM analise.diag_base);
ALTER TABLE analise.diag_sintese_municipal ADD PRIMARY KEY (cenario, indicador);

-- ------------------------------------------------------------------ Distritos (cenário principal)
DROP TABLE IF EXISTS analise.diag_sintese_distrito CASCADE;
CREATE TABLE analise.diag_sintese_distrito AS
SELECT r.cdis, count(*) AS secoes, sum(r.pob_ine) AS pob_ine, sum(r.pob_ine) / sum(r.area_km2) AS densidade_ine_hab_km2,
       count(*) FILTER (WHERE r.alta_densidade) AS secoes_alta_densidade,
       count(*) FILTER (WHERE r.prioritaria) AS secoes_prioritarias,
       count(*) FILTER (WHERE r.tipologia = 'A_baixa_cobertura') AS tipo_a,
       count(*) FILTER (WHERE r.tipologia = 'B_baixa_diversidade_linhas') AS tipo_b,
       count(*) FILTER (WHERE r.tipologia = 'C_baixa_frequencia') AS tipo_c,
       count(*) FILTER (WHERE r.tipologia = 'D_deficiencias_combinadas') AS tipo_d,
       coalesce(sum(r.pob_ine) FILTER (WHERE r.prioritaria), 0) AS pob_ine_prioritarias,
       100.0 * coalesce(sum(r.pob_ine) FILTER (WHERE r.prioritaria), 0) / sum(r.pob_ine) AS pct_pob_distrito_em_prioritarias,
       100.0 * coalesce(sum(r.pob_ine) FILTER (WHERE r.prioritaria), 0)
             / (SELECT sum(pob_ine) FROM analise.diag_resultado_seccion WHERE prioritaria) AS pct_pob_prioritaria_municipal,
       min(r.ranking) AS melhor_ranking,
       count(*) FILTER (WHERE r.baixa_cobertura) AS secoes_baixa_cobertura_todas,
       count(*) FILTER (WHERE r.baixa_frequencia) AS secoes_baixa_frequencia_todas,
       count(*) FILTER (WHERE r.padrao_temporal = 'baixa_frequencia_persistente') AS secoes_baixa_freq_persistente,
       sum(r.partidas_h_manha * (r.pob_grade - r.pob_nao_determinada)) / sum(r.pob_grade - r.pob_nao_determinada) AS partidas_h_manha,
       sum(r.partidas_h_tarde * (r.pob_grade - r.pob_nao_determinada)) / sum(r.pob_grade - r.pob_nao_determinada) AS partidas_h_tarde,
       100.0 * sum(r.pob_sem_cobertura) / sum(r.pob_grade) AS pct_sem_cobertura_grade,
       count(*) FILTER (WHERE r.prioritaria_tercis) AS secoes_prioritarias_tercis
FROM analise.diag_resultado_seccion r GROUP BY r.cdis;
ALTER TABLE analise.diag_sintese_distrito ADD PRIMARY KEY (cdis);

-- ------------------------------------------------------------------ Densidade x oferta
DROP TABLE IF EXISTS analise.diag_densidade_relacao CASCADE;
CREATE TABLE analise.diag_densidade_relacao AS
WITH r AS (
    SELECT cusec, densidade_ine_hab_km2 AS d, pct_coberta_400m AS cob, linhas_manha AS lin, partidas_h_manha AS ph,
           linhas_cob_manha AS lin_c, partidas_h_cob_manha AS ph_c, pob_sem_cobertura AS psc, partidas_h_tarde AS ph_t
    FROM analise.diag_base
), l AS (   -- formato longo; só pares com valor
    SELECT r.cusec, r.d, i.indicador, i.y
    FROM r CROSS JOIN LATERAL (VALUES ('cobertura_400m_pct', r.cob), ('linhas_manha', r.lin), ('partidas_h_manha', r.ph),
                                      ('partidas_h_tarde', r.ph_t), ('linhas_manha_cobertos', r.lin_c),
                                      ('partidas_h_manha_cobertos', r.ph_c), ('pob_sem_cobertura_abs', r.psc)) i(indicador, y)
    WHERE i.y IS NOT NULL
), k AS (   -- Spearman = Pearson dos postos, com posto médio nos empates (426 seções com cobertura de 100%)
    SELECT l.*,
           rank() OVER (PARTITION BY indicador ORDER BY d) + (count(*) OVER (PARTITION BY indicador, d) - 1) / 2.0 AS rd,
           rank() OVER (PARTITION BY indicador ORDER BY y) + (count(*) OVER (PARTITION BY indicador, y) - 1) / 2.0 AS ry
    FROM l
)
SELECT indicador, corr(d, y) AS pearson_densidade, corr(rd, ry) AS spearman_densidade, count(*) AS n_secoes
FROM k GROUP BY indicador;
ALTER TABLE analise.diag_densidade_relacao ADD PRIMARY KEY (indicador);

DROP TABLE IF EXISTS analise.diag_densidade_quartis CASCADE;
CREATE TABLE analise.diag_densidade_quartis AS
WITH q AS (SELECT b.*, ntile(4) OVER (ORDER BY densidade_ine_hab_km2, cusec) AS quartil FROM analise.diag_base b)
SELECT quartil, count(*) AS secoes, min(densidade_ine_hab_km2) AS dens_min, max(densidade_ine_hab_km2) AS dens_max,
       sum(pob_ine) AS pob_ine, sum(pob_grade) AS pob_grade,
       100 * sum(pob_coberta_400m) / sum(pob_grade) AS pct_coberta_400m,
       sum(pob_sem_cobertura) AS pob_sem_cobertura,
       sum(linhas_manha * (pob_grade - pob_nao_determinada)) / sum(pob_grade - pob_nao_determinada) AS linhas_manha,
       sum(partidas_h_manha * (pob_grade - pob_nao_determinada)) / sum(pob_grade - pob_nao_determinada) AS partidas_h_manha,
       sum(partidas_h_tarde * (pob_grade - pob_nao_determinada)) / sum(pob_grade - pob_nao_determinada) AS partidas_h_tarde,
       count(*) FILTER (WHERE partidas_h_cob_manha <= (SELECT valor FROM analise.diag_limiares WHERE cenario = 'principal' AND criterio = 'baixa_frequencia')) AS secoes_baixa_frequencia
FROM q GROUP BY quartil;
ALTER TABLE analise.diag_densidade_quartis ADD PRIMARY KEY (quartil);

-- ------------------------------------------------------------------ Sensibilidade (quartis x tercis)
DROP TABLE IF EXISTS analise.diag_sensibilidade CASCADE;
CREATE TABLE analise.diag_sensibilidade AS
SELECT r.cusec, r.cdis, r.pob_ine, r.densidade_ine_hab_km2, r.tipologia AS tipologia_principal, r.tipologia_tercis,
       r.prioritaria AS prioritaria_principal, r.prioritaria_tercis, r.ranking AS ranking_principal, r.ranking_tercis,
       CASE WHEN r.prioritaria AND r.prioritaria_tercis THEN 'prioritaria_nos_dois'
            WHEN r.prioritaria THEN 'so_principal'
            WHEN r.prioritaria_tercis THEN 'so_tercis'
            ELSE 'nao_prioritaria' END AS situacao
FROM analise.diag_resultado_seccion r;
ALTER TABLE analise.diag_sensibilidade ADD PRIMARY KEY (cusec);

DROP TABLE IF EXISTS analise.diag_sensibilidade_resumo CASCADE;
CREATE TABLE analise.diag_sensibilidade_resumo AS
SELECT 'secoes_' || situacao AS indicador, count(*)::float AS valor, sum(pob_ine)::float AS pob_ine
FROM analise.diag_sensibilidade GROUP BY situacao
UNION ALL
SELECT 'top10_principal_tambem_prioritarias_tercis', count(*) FILTER (WHERE prioritaria_tercis), NULL
FROM analise.diag_sensibilidade WHERE ranking_principal <= 10
UNION ALL
SELECT 'top10_principal_no_top20_tercis', count(*) FILTER (WHERE ranking_tercis <= 20), NULL
FROM analise.diag_sensibilidade WHERE ranking_principal <= 10
UNION ALL
SELECT 'spearman_ranking_comuns', corr(ranking_principal, ranking_tercis), NULL
FROM (SELECT rank() OVER (ORDER BY ranking_principal) AS ranking_principal, rank() OVER (ORDER BY ranking_tercis) AS ranking_tercis
      FROM analise.diag_sensibilidade WHERE prioritaria_principal AND prioritaria_tercis) x
UNION ALL
SELECT 'distritos_com_prioritarias_principal', count(DISTINCT cdis), NULL FROM analise.diag_sensibilidade WHERE prioritaria_principal
UNION ALL
SELECT 'distritos_com_prioritarias_tercis', count(DISTINCT cdis), NULL FROM analise.diag_sensibilidade WHERE prioritaria_tercis;

-- ------------------------------------------------------------------ Conferência das 15 primeiras prioritárias
DROP TABLE IF EXISTS analise.diag_conferencia_prioritarias CASCADE;
CREATE TABLE analise.diag_conferencia_prioritarias AS
WITH top AS (SELECT * FROM analise.diag_resultado_seccion WHERE ranking <= 15),
o AS (SELECT r.* FROM analise.resultado_origem r JOIN top USING (cusec)),
pr AS (SELECT o.cusec, count(DISTINCT op.stop_id) AS paradas_400m FROM o JOIN analise.origem_parada_400m op USING (origem_id) GROUP BY 1),
ln AS (SELECT o.cusec, string_agg(DISTINCT v.route_short_name, ',' ORDER BY v.route_short_name) AS linhas_acessiveis_manha
       FROM o JOIN analise.origem_viagem_periodo v ON v.origem_id = o.origem_id AND v.periodo = 'manha' GROUP BY 1),
dist AS (SELECT cusec,
                sum(pob_estimada * dist_parada_mais_proxima_m) / nullif(sum(pob_estimada) FILTER (WHERE dist_parada_mais_proxima_m IS NOT NULL), 0) AS dist_rede_m,
                sum(pob_estimada * dist_euclidiana_parada_mais_proxima_m) / sum(pob_estimada) AS dist_euclid_m
         FROM o GROUP BY 1),
bar AS (SELECT t.cusec, string_agg(DISTINCT b.classe, ',') AS barreiras_na_secao
        FROM top t JOIN analise.barreiras b ON ST_Intersects(b.geom, t.geom) GROUP BY 1),
par AS (SELECT t.cusec, count(*) AS paradas_servico_dentro_secao FROM top t JOIN analise.paradas_analise p
        ON p.serve_onibus_dia_ref AND ST_Intersects(p.geom, t.geom) GROUP BY 1),
cel AS (SELECT cusec, count(DISTINCT gidmp) AS celulas_grade FROM analise.parcelas_demanda GROUP BY 1)
SELECT t.ranking, t.cusec, t.cdis, t.tipologia, t.deficiencias, t.area_km2, t.area_habitada_km2, t.pob_ine,
       t.pob_grade, t.razao_grade_ine, t.n_pontos, cel.celulas_grade, t.densidade_ine_hab_km2, t.densidade_area_habitada_hab_km2,
       t.pct_coberta_400m, t.pct_pob_perto_limiar_400m, coalesce(pr.paradas_400m, 0) AS paradas_400m, coalesce(par.paradas_servico_dentro_secao, 0) AS paradas_servico_dentro_secao,
       ln.linhas_acessiveis_manha, t.linhas_cob_manha, t.partidas_h_cob_manha, t.partidas_h_tarde,
       dist.dist_rede_m, dist.dist_euclid_m, dist.dist_rede_m / nullif(dist.dist_euclid_m, 0) AS razao_rede_euclid,
       bar.barreiras_na_secao,
       ST_Y(ST_Transform(ST_PointOnSurface(t.geom), 4326)) AS lat, ST_X(ST_Transform(ST_PointOnSurface(t.geom), 4326)) AS lon
FROM top t LEFT JOIN pr USING (cusec) LEFT JOIN ln USING (cusec) LEFT JOIN dist USING (cusec)
LEFT JOIN bar USING (cusec) LEFT JOIN par USING (cusec) LEFT JOIN cel USING (cusec);
ALTER TABLE analise.diag_conferencia_prioritarias ADD PRIMARY KEY (cusec);

-- ------------------------------------------------------------------ Views espaciais (QGIS)
CREATE OR REPLACE VIEW analise.v_diag_secoes AS SELECT * FROM analise.diag_resultado_seccion;
CREATE OR REPLACE VIEW analise.v_diag_prioritarias AS
SELECT * FROM analise.diag_resultado_seccion WHERE prioritaria ORDER BY ranking;
CREATE OR REPLACE VIEW analise.v_diag_distritos AS
SELECT d.*, g.geom FROM analise.diag_sintese_distrito d
JOIN (SELECT cdis, ST_Multi(ST_Union(geom))::geometry(MultiPolygon, 25830) AS geom FROM prep.secciones GROUP BY cdis) g USING (cdis);
CREATE OR REPLACE VIEW analise.v_diag_paradas AS
SELECT p.stop_id, p.stop_name, p.categoria, p.situacao_ligacao, p.dentro_municipio,
       coalesce(m.linhas_dia, 0) AS linhas_dia, coalesce(m.partidas_dia, 0) AS partidas_dia,
       coalesce(mm.partidas_manha, 0) / 2.0 AS partidas_h_manha, coalesce(mm.linhas_manha, 0) AS linhas_manha,
       coalesce(mt.partidas_tarde, 0) / 2.0 AS partidas_h_tarde, p.geom
FROM analise.paradas_analise p
LEFT JOIN (SELECT stop_id, count(DISTINCT route_id) AS linhas_dia, count(*) AS partidas_dia FROM analise.partidas_dia GROUP BY 1) m USING (stop_id)
LEFT JOIN (SELECT stop_id, count(*) AS partidas_manha, count(DISTINCT route_id) AS linhas_manha FROM analise.partidas_periodo WHERE periodo = 'manha' GROUP BY 1) mm USING (stop_id)
LEFT JOIN (SELECT stop_id, count(*) AS partidas_tarde FROM analise.partidas_periodo WHERE periodo = 'tarde' GROUP BY 1) mt USING (stop_id)
WHERE p.serve_onibus;

ANALYZE analise.diag_resultado_seccion;
