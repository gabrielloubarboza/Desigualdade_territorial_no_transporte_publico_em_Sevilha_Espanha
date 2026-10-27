-- =====================================================================================
-- 13_diagnostico_classificacao.sql — Etapa 4: limiares, deficiências, tipologia, ranking e períodos
-- Entrada: analise.indicadores_seccion_oferta e analise.oferta_seccion_periodo (Etapa 3),
--          analise.resultado_seccion e analise.parcelas_demanda (Etapa 2). Nada disso é alterado.
--
-- Critérios comparativos internos a Sevilla (não são padrões técnicos ou legais):
--   alta densidade       densidade INE (pob_ine / área total) >= P75 das 521 seções
--   baixa cobertura      % da população da grade com parada a <= 400 m < cobertura municipal (94,36%)
--                        (o quartil inferior seria 100%: 426 seções têm cobertura total => não discrimina)
--   baixa diversidade    média de linhas acessíveis (manhã) ENTRE OS COBERTOS <= P25 das seções com cobertos
--   baixa frequência     média de partidas/h acessíveis (manhã) ENTRE OS COBERTOS <= P25 idem
-- Linhas e frequência usam a média entre cobertos para não confundir baixa oferta com ausência de parada.
-- Percentis: percentile_cont (interpolação linear); empates no limiar entram na categoria (>= / <=).
-- Cenário 'sensibilidade_tercis': P66,7 / P33,3 e baixa cobertura = cobertura < 99%.
-- =====================================================================================

-- ------------------------------------------------------------------ Base por seção
DROP TABLE IF EXISTS analise.diag_base CASCADE;
CREATE TABLE analise.diag_base AS
WITH cob AS (
    SELECT cusec,
           max(media_linhas_cobertos)        FILTER (WHERE periodo = 'manha')    AS linhas_cob_manha,
           max(media_linhas_cobertos)        FILTER (WHERE periodo = 'meio_dia') AS linhas_cob_meio_dia,
           max(media_linhas_cobertos)        FILTER (WHERE periodo = 'tarde')    AS linhas_cob_tarde,
           max(media_partidas_hora_cobertos) FILTER (WHERE periodo = 'manha')    AS partidas_h_cob_manha,
           max(media_partidas_hora_cobertos) FILTER (WHERE periodo = 'meio_dia') AS partidas_h_cob_meio_dia,
           max(media_partidas_hora_cobertos) FILTER (WHERE periodo = 'tarde')    AS partidas_h_cob_tarde,
           max(pob_coberta_400m)             FILTER (WHERE periodo = 'manha')    AS pob_coberta_400m,
           max(pob_sem_cobertura)            FILTER (WHERE periodo = 'manha')    AS pob_sem_cobertura,
           max(pob_nao_determinada)          FILTER (WHERE periodo = 'manha')    AS pob_nao_determinada
    FROM analise.oferta_seccion_periodo GROUP BY cusec
), hab AS (
    SELECT cusec, sum(area_hab_parcela_m2) / 1e6 AS area_habitada_km2 FROM analise.parcelas_demanda GROUP BY cusec
), lim400 AS (   -- robustez: população cuja parada mais próxima está perto do limiar (350–450 m de percurso)
    SELECT cusec, 100 * coalesce(sum(pob_estimada) FILTER (WHERE dist_parada_mais_proxima_m > 350
                                                         AND dist_parada_mais_proxima_m <= 450), 0)
                      / sum(pob_estimada) AS pct_pob_perto_limiar_400m
    FROM analise.resultado_origem GROUP BY cusec
)
SELECT i.cusec, i.cdis, i.area_km2, i.pob_ine, i.densidade_ine_hab_km2,
       hab.area_habitada_km2,                                           -- área de células habitadas fora de água/parques/ferrovia
       i.pob_ine / nullif(hab.area_habitada_km2, 0) AS densidade_area_habitada_hab_km2,   -- complementar
       i.pob_grade, cob.pob_coberta_400m, cob.pob_sem_cobertura, cob.pob_nao_determinada,
       i.pct_coberta_400m, i.pct_sem_cobertura_400m, i.pct_nao_determinada_400m, i.dist_media_ponderada_m,
       lim400.pct_pob_perto_limiar_400m,
       i.linhas_manha, i.linhas_meio_dia, i.linhas_tarde,
       cob.linhas_cob_manha, cob.linhas_cob_meio_dia, cob.linhas_cob_tarde,
       i.partidas_h_manha, i.partidas_h_meio_dia, i.partidas_h_tarde,
       cob.partidas_h_cob_manha, cob.partidas_h_cob_meio_dia, cob.partidas_h_cob_tarde,
       i.pob_sem_oferta_manha, i.pob_sem_oferta_meio_dia, i.pob_sem_oferta_tarde,
       i.pob_coberta_sem_servico_manha, i.menor_intervalo_min_manha,
       i.pct_viagens_horario_interpolado, i.razao_grade_ine, i.n_pontos, i.situacao_dados,
       i.geom
FROM analise.indicadores_seccion_oferta i
JOIN cob USING (cusec)
LEFT JOIN hab USING (cusec)
LEFT JOIN lim400 USING (cusec);
ALTER TABLE analise.diag_base ADD PRIMARY KEY (cusec);

-- ------------------------------------------------------------------ Limiares (dois cenários)
DROP TABLE IF EXISTS analise.diag_limiares CASCADE;
CREATE TABLE analise.diag_limiares AS
WITH cen(cenario, p_alta, p_baixa, cob_fixa) AS (
    VALUES ('principal', 0.75, 0.25, NULL::float), ('sensibilidade_tercis', 2 / 3.0, 1 / 3.0, 99.0)
), cobmun AS (SELECT valor AS pct FROM analise.sintese_municipal WHERE indicador = 'pct_coberta_400m'),
cobertos AS (SELECT * FROM analise.diag_base WHERE pob_coberta_400m > 0),
lim AS (
    SELECT c.cenario, 'alta_densidade' AS criterio, 'densidade_ine_hab_km2' AS variavel, '>=' AS operador,
           format('P%s das 521 seções (percentile_cont)', round(100 * c.p_alta, 1)) AS regra,
           (SELECT count(*) FROM analise.diag_base) AS n_universo,
           (SELECT percentile_cont(c.p_alta) WITHIN GROUP (ORDER BY densidade_ine_hab_km2) FROM analise.diag_base) AS valor
    FROM cen c
    UNION ALL
    SELECT c.cenario, 'baixa_cobertura', 'pct_coberta_400m', '<',
           CASE WHEN c.cob_fixa IS NULL THEN 'abaixo da cobertura municipal (população da grade)'
                ELSE 'abaixo de 99% (alguma população relevante sem parada)' END,
           (SELECT count(*) FROM analise.diag_base), coalesce(c.cob_fixa, (SELECT pct FROM cobmun))
    FROM cen c
    UNION ALL
    SELECT c.cenario, 'baixa_diversidade_linhas', 'linhas_cob_manha', '<=',
           format('P%s das seções com população coberta', round(100 * c.p_baixa, 1)),
           (SELECT count(*) FROM cobertos),
           (SELECT percentile_cont(c.p_baixa) WITHIN GROUP (ORDER BY linhas_cob_manha) FROM cobertos)
    FROM cen c
    UNION ALL
    SELECT c.cenario, 'baixa_frequencia', 'partidas_h_cob_manha', '<=',
           format('P%s das seções com população coberta', round(100 * c.p_baixa, 1)),
           (SELECT count(*) FROM cobertos),
           (SELECT percentile_cont(c.p_baixa) WITHIN GROUP (ORDER BY partidas_h_cob_manha) FROM cobertos)
    FROM cen c
    UNION ALL   -- limiares de frequência por período (análise temporal; só cenário principal)
    SELECT 'principal', 'baixa_frequencia_' || p.periodo, 'partidas_h_cob_' || p.periodo, '<=',
           'P25 das seções com população coberta', (SELECT count(*) FROM cobertos),
           CASE p.periodo
               WHEN 'manha'    THEN (SELECT percentile_cont(0.25) WITHIN GROUP (ORDER BY partidas_h_cob_manha) FROM cobertos)
               WHEN 'meio_dia' THEN (SELECT percentile_cont(0.25) WITHIN GROUP (ORDER BY partidas_h_cob_meio_dia) FROM cobertos)
               WHEN 'tarde'    THEN (SELECT percentile_cont(0.25) WITHIN GROUP (ORDER BY partidas_h_cob_tarde) FROM cobertos) END
    FROM prep.periodos_analise p
)
SELECT * FROM lim;
ALTER TABLE analise.diag_limiares ADD PRIMARY KEY (cenario, criterio);

-- ------------------------------------------------------------------ Deficiências, tipologia e ranking
DROP TABLE IF EXISTS analise.diag_classificacao CASCADE;
CREATE TABLE analise.diag_classificacao AS
WITH l AS (
    SELECT cenario,
           max(valor) FILTER (WHERE criterio = 'alta_densidade')           AS l_dens,
           max(valor) FILTER (WHERE criterio = 'baixa_cobertura')          AS l_cob,
           max(valor) FILTER (WHERE criterio = 'baixa_diversidade_linhas') AS l_lin,
           max(valor) FILTER (WHERE criterio = 'baixa_frequencia')         AS l_freq
    FROM analise.diag_limiares WHERE criterio IN ('alta_densidade', 'baixa_cobertura', 'baixa_diversidade_linhas', 'baixa_frequencia')
    GROUP BY cenario
), f AS (
    SELECT l.cenario, b.cusec, b.cdis, b.pob_ine, b.densidade_ine_hab_km2, b.pob_sem_oferta_manha, b.pob_sem_cobertura,
           b.partidas_h_manha, b.linhas_manha, b.partidas_h_cob_manha, b.linhas_cob_manha, b.pct_coberta_400m,
           b.pct_nao_determinada_400m,
           b.densidade_ine_hab_km2 >= l.l_dens AS alta_densidade,
           b.pct_coberta_400m < l.l_cob AS baixa_cobertura,
           -- sem população coberta, diversidade e frequência não se aplicam (deficiência é de cobertura)
           CASE WHEN b.pob_coberta_400m > 0 THEN b.linhas_cob_manha <= l.l_lin END     AS baixa_diversidade_linhas,
           CASE WHEN b.pob_coberta_400m > 0 THEN b.partidas_h_cob_manha <= l.l_freq END AS baixa_frequencia,
           b.pct_nao_determinada_400m > 10 AS informacao_incompleta
    FROM analise.diag_base b CROSS JOIN l
), t AS (
    SELECT f.*,
           (baixa_cobertura::int + coalesce(baixa_diversidade_linhas, false)::int + coalesce(baixa_frequencia, false)::int) AS n_deficiencias,
           concat_ws('+', CASE WHEN baixa_cobertura THEN 'cobertura' END,
                          CASE WHEN baixa_diversidade_linhas THEN 'linhas' END,
                          CASE WHEN baixa_frequencia THEN 'frequencia' END) AS deficiencias
    FROM f
)
SELECT t.*,
       CASE WHEN NOT alta_densidade        THEN 'fora_alta_densidade'
            WHEN informacao_incompleta     THEN 'alta_densidade_informacao_incompleta'
            WHEN n_deficiencias >= 2       THEN 'D_deficiencias_combinadas'
            WHEN baixa_cobertura           THEN 'A_baixa_cobertura'
            WHEN baixa_diversidade_linhas  THEN 'B_baixa_diversidade_linhas'
            WHEN baixa_frequencia          THEN 'C_baixa_frequencia'
            ELSE 'alta_densidade_sem_deficiencia' END AS tipologia,
       (alta_densidade AND NOT informacao_incompleta AND n_deficiencias > 0) AS prioritaria
FROM t;
ALTER TABLE analise.diag_classificacao ADD PRIMARY KEY (cenario, cusec);

-- Dimensões de deficiência: acesso físico (cobertura) e serviço (linhas e/ou frequência). Linhas e
-- frequência medem quase a mesma dimensão (r = 0,95 entre seções), por isso não são somadas no ranking.
ALTER TABLE analise.diag_classificacao
    ADD COLUMN deficiencia_acesso boolean, ADD COLUMN deficiencia_servico boolean, ADD COLUMN n_dimensoes integer;
UPDATE analise.diag_classificacao SET
    deficiencia_acesso  = baixa_cobertura,
    deficiencia_servico = coalesce(baixa_diversidade_linhas, false) OR coalesce(baixa_frequencia, false),
    n_dimensoes = baixa_cobertura::int + (coalesce(baixa_diversidade_linhas, false) OR coalesce(baixa_frequencia, false))::int;

-- Ranking das prioritárias (critérios explícitos, sem escore):
--  1. mais dimensões deficientes (acesso e serviço); 2. mais moradores estimados sem oferta acessível na
--  manhã (sem parada ou sem partida); 3. menor média de partidas/h acessíveis (todos os determinados);
--  4. menor média de linhas; 5. maior densidade; 6. cusec.
-- ranking_ordem_inicial: mesma ordem, mas com o nº de deficiências (1–3) no critério 1 — só para comparação.
ALTER TABLE analise.diag_classificacao ADD COLUMN ranking integer, ADD COLUMN ranking_ordem_inicial integer;
UPDATE analise.diag_classificacao c SET ranking = r.rk, ranking_ordem_inicial = r.rk0
FROM (SELECT cenario, cusec,
             row_number() OVER (PARTITION BY cenario ORDER BY n_dimensoes DESC, pob_sem_oferta_manha DESC,
                                partidas_h_manha, linhas_manha, densidade_ine_hab_km2 DESC, cusec) AS rk,
             row_number() OVER (PARTITION BY cenario ORDER BY n_deficiencias DESC, pob_sem_oferta_manha DESC,
                                partidas_h_manha, linhas_manha, densidade_ine_hab_km2 DESC, cusec) AS rk0
      FROM analise.diag_classificacao WHERE prioritaria) r
WHERE r.cenario = c.cenario AND r.cusec = c.cusec;
CREATE INDEX ON analise.diag_classificacao (cenario, ranking);

-- ------------------------------------------------------------------ Comparação temporal (cenário principal)
DROP TABLE IF EXISTS analise.diag_temporal CASCADE;
CREATE TABLE analise.diag_temporal AS
WITH l AS (
    SELECT max(valor) FILTER (WHERE criterio = 'baixa_frequencia_manha') AS lm,
           max(valor) FILTER (WHERE criterio = 'baixa_frequencia_meio_dia') AS lmd,
           max(valor) FILTER (WHERE criterio = 'baixa_frequencia_tarde') AS lt
    FROM analise.diag_limiares WHERE cenario = 'principal'
), b AS (
    SELECT b.*,
           percent_rank() OVER (ORDER BY partidas_h_manha)    AS prank_manha,
           percent_rank() OVER (ORDER BY partidas_h_meio_dia) AS prank_meio_dia,
           percent_rank() OVER (ORDER BY partidas_h_tarde)    AS prank_tarde
    FROM analise.diag_base b
)
SELECT b.cusec, b.cdis, b.densidade_ine_hab_km2,
       b.partidas_h_manha, b.partidas_h_meio_dia, b.partidas_h_tarde,
       b.partidas_h_cob_manha, b.partidas_h_cob_meio_dia, b.partidas_h_cob_tarde,
       b.partidas_h_tarde - b.partidas_h_manha AS dif_tarde_manha,
       b.partidas_h_meio_dia - b.partidas_h_manha AS dif_meio_dia_manha,
       CASE WHEN b.partidas_h_manha > 0 THEN 100 * (b.partidas_h_tarde / b.partidas_h_manha - 1) END AS var_pct_tarde_manha,
       CASE WHEN b.partidas_h_manha > 0 THEN 100 * (b.partidas_h_meio_dia / b.partidas_h_manha - 1) END AS var_pct_meio_dia_manha,
       b.prank_manha, b.prank_meio_dia, b.prank_tarde,
       b.prank_tarde - b.prank_manha AS mudanca_posicao_tarde_manha,   -- em fração da distribuição (−1 a 1)
       CASE WHEN b.pob_coberta_400m > 0 THEN b.partidas_h_cob_manha <= l.lm END    AS baixa_freq_manha,
       CASE WHEN b.pob_coberta_400m > 0 THEN b.partidas_h_cob_meio_dia <= l.lmd END AS baixa_freq_meio_dia,
       CASE WHEN b.pob_coberta_400m > 0 THEN b.partidas_h_cob_tarde <= l.lt END    AS baixa_freq_tarde
FROM b, l;
ALTER TABLE analise.diag_temporal ADD PRIMARY KEY (cusec);
ALTER TABLE analise.diag_temporal ADD COLUMN padrao_temporal text;
UPDATE analise.diag_temporal SET padrao_temporal = CASE
    WHEN baixa_freq_manha IS NULL THEN 'sem_populacao_coberta'
    WHEN baixa_freq_manha AND baixa_freq_meio_dia AND baixa_freq_tarde THEN 'baixa_frequencia_persistente'
    WHEN NOT baixa_freq_manha AND baixa_freq_tarde THEN 'baixa_frequencia_sobretudo_tarde'
    WHEN baixa_freq_manha OR baixa_freq_meio_dia OR baixa_freq_tarde THEN 'baixa_frequencia_parcial'
    ELSE 'sem_baixa_frequencia' END;
