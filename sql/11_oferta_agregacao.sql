-- =====================================================================================
-- 11_oferta_agregacao.sql — Etapa 3: oferta por seção, município e distrito; tabela larga para a Etapa 4
-- Médias ponderadas pela população estimada da grade IECA. Denominador principal: população com
-- acessibilidade determinada (cobertos + sem cobertura, estes com oferta 0). Também se calcula a média
-- apenas entre cobertos. Não se somam partidas entre origens (a mesma viagem serve várias origens).
-- =====================================================================================

DROP TABLE IF EXISTS analise.oferta_seccion_periodo CASCADE;
CREATE TABLE analise.oferta_seccion_periodo AS
WITH o AS (SELECT * FROM analise.oferta_origem_periodo),
a AS (
    SELECT cusec, periodo,
           sum(pob_estimada) FILTER (WHERE situacao_oferta <> 'nao_determinado')                AS pob_determinada,
           sum(pob_estimada) FILTER (WHERE situacao_oferta = 'com_servico')                     AS pob_com_servico,
           sum(pob_estimada) FILTER (WHERE situacao_oferta = 'coberto_sem_servico_no_periodo')  AS pob_coberta_sem_servico,
           sum(pob_estimada) FILTER (WHERE situacao_oferta = 'sem_cobertura_400m')              AS pob_sem_cobertura,
           sum(pob_estimada) FILTER (WHERE situacao_oferta = 'nao_determinado')                 AS pob_nao_determinada,
           sum(pob_estimada) FILTER (WHERE n_linhas_dia > 0)                                    AS pob_com_linha_no_dia,
           sum(pob_estimada) FILTER (WHERE n_linhas_ambos_sentidos > 0)                         AS pob_linha_ambos_sentidos,
           sum(pob_estimada * n_linhas)        AS s_linhas,
           sum(pob_estimada * partidas_hora)   AS s_ph,
           sum(pob_estimada * n_linha_sentido) AS s_ls,
           sum(pob_estimada * n_linhas)      FILTER (WHERE situacao_cobertura = 'coberto_400m') AS s_linhas_cob,
           sum(pob_estimada * partidas_hora) FILTER (WHERE situacao_cobertura = 'coberto_400m') AS s_ph_cob,
           sum(pob_estimada)                 FILTER (WHERE situacao_cobertura = 'coberto_400m') AS pob_coberta_400m,
           sum(pob_estimada * n_viagens_horario_interpolado) AS s_interp,
           sum(pob_estimada * n_viagens)                     AS s_viagens,
           sum(pob_estimada * menor_intervalo_medio_min) FILTER (WHERE menor_intervalo_medio_min IS NOT NULL) AS s_int,
           sum(pob_estimada)                             FILTER (WHERE menor_intervalo_medio_min IS NOT NULL) AS p_int,
           count(*) AS n_pontos
    FROM o GROUP BY cusec, periodo
)
SELECT s.cusec, pa.periodo, s.cdis, s.area_km2, s.pob_ine, s.densidade_ine_hab_km2, s.pob_grade,
       coalesce(a.pob_determinada, 0) AS pob_determinada,
       coalesce(a.pob_coberta_400m, 0) AS pob_coberta_400m,
       coalesce(a.pob_com_servico, 0) AS pob_com_servico,
       coalesce(a.pob_coberta_sem_servico, 0) AS pob_coberta_sem_servico,
       coalesce(a.pob_sem_cobertura, 0) AS pob_sem_cobertura,
       coalesce(a.pob_nao_determinada, 0) AS pob_nao_determinada,
       coalesce(a.pob_sem_cobertura, 0) + coalesce(a.pob_coberta_sem_servico, 0) AS pob_sem_oferta_acessivel,
       a.s_linhas / nullif(a.pob_determinada, 0)  AS media_linhas,
       a.s_ph     / nullif(a.pob_determinada, 0)  AS media_partidas_hora,
       a.s_ls     / nullif(a.pob_determinada, 0)  AS media_linha_sentido,
       a.s_linhas_cob / nullif(a.pob_coberta_400m, 0) AS media_linhas_cobertos,
       a.s_ph_cob     / nullif(a.pob_coberta_400m, 0) AS media_partidas_hora_cobertos,
       a.s_int / nullif(a.p_int, 0) AS media_menor_intervalo_linha_sentido_min,
       100 * coalesce(a.pob_com_servico, 0) / nullif(s.pob_grade, 0)          AS pct_com_servico,
       100 * coalesce(a.pob_com_linha_no_dia, 0) / nullif(s.pob_grade, 0)     AS pct_com_linha_no_dia,
       100 * coalesce(a.pob_coberta_sem_servico, 0) / nullif(s.pob_grade, 0)  AS pct_coberta_sem_servico,
       100 * coalesce(a.pob_sem_cobertura, 0) / nullif(s.pob_grade, 0)        AS pct_sem_cobertura,
       100 * coalesce(a.pob_nao_determinada, 0) / nullif(s.pob_grade, 0)      AS pct_nao_determinada,
       100 * coalesce(a.pob_linha_ambos_sentidos, 0) / nullif(s.pob_grade, 0) AS pct_linha_ambos_sentidos,
       100 * a.s_interp / nullif(a.s_viagens, 0) AS pct_viagens_horario_interpolado,
       coalesce(a.n_pontos, 0) AS n_pontos,
       s.razao_grade_ine, s.situacao_dados,
       s.geom
FROM analise.resultado_seccion s
CROSS JOIN prep.periodos_analise pa
LEFT JOIN a ON a.cusec = s.cusec AND a.periodo = pa.periodo;
ALTER TABLE analise.oferta_seccion_periodo ADD PRIMARY KEY (cusec, periodo);
CREATE INDEX ON analise.oferta_seccion_periodo USING gist (geom);
COMMENT ON TABLE analise.oferta_seccion_periodo IS
    'Oferta acessível por seção e período; médias = morador médio estimado (grade), não ônibus que circulam na seção';

-- ------------------------------------------------------------------ Tabela larga por seção (insumo da Etapa 4)
DROP TABLE IF EXISTS analise.indicadores_seccion_oferta CASCADE;
CREATE TABLE analise.indicadores_seccion_oferta AS
WITH p AS (SELECT * FROM analise.oferta_seccion_periodo)
SELECT s.cusec, s.cdis, s.area_km2, s.pob_ine, s.densidade_ine_hab_km2, s.pob_grade,
       s.pct_coberta AS pct_coberta_400m, s.pct_sem_cobertura AS pct_sem_cobertura_400m,
       s.pct_nao_determinada AS pct_nao_determinada_400m, s.dist_media_ponderada_m,
       m.media_linhas AS linhas_manha, md.media_linhas AS linhas_meio_dia, t.media_linhas AS linhas_tarde,
       m.media_partidas_hora AS partidas_h_manha, md.media_partidas_hora AS partidas_h_meio_dia, t.media_partidas_hora AS partidas_h_tarde,
       least(m.media_partidas_hora, md.media_partidas_hora, t.media_partidas_hora) AS partidas_h_min_periodos,
       md.media_partidas_hora - m.media_partidas_hora AS dif_partidas_h_meio_dia_manha,
       t.media_partidas_hora - m.media_partidas_hora  AS dif_partidas_h_tarde_manha,
       m.media_linha_sentido AS linha_sentido_manha, md.media_linha_sentido AS linha_sentido_meio_dia, t.media_linha_sentido AS linha_sentido_tarde,
       m.pct_com_servico AS pct_com_servico_manha, md.pct_com_servico AS pct_com_servico_meio_dia, t.pct_com_servico AS pct_com_servico_tarde,
       m.pob_sem_oferta_acessivel AS pob_sem_oferta_manha, md.pob_sem_oferta_acessivel AS pob_sem_oferta_meio_dia,
       t.pob_sem_oferta_acessivel AS pob_sem_oferta_tarde,
       m.pob_coberta_sem_servico AS pob_coberta_sem_servico_manha, md.pob_coberta_sem_servico AS pob_coberta_sem_servico_meio_dia,
       t.pob_coberta_sem_servico AS pob_coberta_sem_servico_tarde,
       m.media_menor_intervalo_linha_sentido_min AS menor_intervalo_min_manha,
       md.media_menor_intervalo_linha_sentido_min AS menor_intervalo_min_meio_dia,
       t.media_menor_intervalo_linha_sentido_min AS menor_intervalo_min_tarde,
       (m.pct_viagens_horario_interpolado + md.pct_viagens_horario_interpolado + t.pct_viagens_horario_interpolado) / 3
           AS pct_viagens_horario_interpolado,
       s.razao_grade_ine, s.n_pontos, s.situacao_dados,
       s.geom
FROM analise.resultado_seccion s
JOIN p m  ON m.cusec  = s.cusec AND m.periodo  = 'manha'
JOIN p md ON md.cusec = s.cusec AND md.periodo = 'meio_dia'
JOIN p t  ON t.cusec  = s.cusec AND t.periodo  = 'tarde';
ALTER TABLE analise.indicadores_seccion_oferta ADD PRIMARY KEY (cusec);
CREATE INDEX ON analise.indicadores_seccion_oferta USING gist (geom);
COMMENT ON TABLE analise.indicadores_seccion_oferta IS
    'Uma linha por seção com densidade, cobertura 400 m e oferta por período — sem classificação nem índice composto';

-- ------------------------------------------------------------------ Síntese municipal por período
DROP TABLE IF EXISTS analise.sintese_oferta_municipal CASCADE;
CREATE TABLE analise.sintese_oferta_municipal AS
WITH o AS (SELECT * FROM analise.oferta_origem_periodo),
mun AS (
    SELECT periodo,
           sum(pob_estimada) AS pob_grade,
           sum(pob_estimada) FILTER (WHERE situacao_cobertura = 'coberto_400m') AS pob_coberta_400m,
           coalesce(sum(pob_estimada) FILTER (WHERE situacao_oferta = 'com_servico'), 0) AS pob_com_servico,
           coalesce(sum(pob_estimada) FILTER (WHERE situacao_oferta = 'coberto_sem_servico_no_periodo'), 0) AS pob_coberta_sem_servico,
           coalesce(sum(pob_estimada) FILTER (WHERE situacao_oferta = 'sem_cobertura_400m'), 0) AS pob_sem_cobertura,
           coalesce(sum(pob_estimada) FILTER (WHERE situacao_oferta = 'nao_determinado'), 0) AS pob_nao_determinada,
           sum(pob_estimada * n_linhas) / sum(pob_estimada) FILTER (WHERE situacao_oferta <> 'nao_determinado') AS media_linhas,
           sum(pob_estimada * partidas_hora) / sum(pob_estimada) FILTER (WHERE situacao_oferta <> 'nao_determinado') AS media_partidas_hora,
           sum(pob_estimada * n_linhas) FILTER (WHERE situacao_cobertura = 'coberto_400m')
               / sum(pob_estimada) FILTER (WHERE situacao_cobertura = 'coberto_400m') AS media_linhas_cobertos,
           sum(pob_estimada * partidas_hora) FILTER (WHERE situacao_cobertura = 'coberto_400m')
               / sum(pob_estimada) FILTER (WHERE situacao_cobertura = 'coberto_400m') AS media_partidas_hora_cobertos,
           percentile_disc(0.5) WITHIN GROUP (ORDER BY partidas_hora) FILTER (WHERE situacao_oferta <> 'nao_determinado') AS mediana_pontos_partidas_hora,
           100 * sum(pob_estimada * n_viagens_horario_interpolado) / nullif(sum(pob_estimada * n_viagens), 0) AS pct_viagens_horario_interpolado
    FROM o GROUP BY periodo
), rede AS (
    SELECT periodo, count(DISTINCT trip_id) AS viagens_rede, count(DISTINCT route_id) AS linhas_rede,
           count(DISTINCT (route_id, direction_id)) AS linha_sentido_rede, count(*) AS partidas_paradas_rede,
           count(DISTINCT stop_id) AS paradas_com_partida_rede,
           count(*) FILTER (WHERE origem_horario = 'interpolado') AS partidas_paradas_interpoladas
    FROM analise.partidas_periodo GROUP BY periodo
), acess AS (
    SELECT periodo, count(DISTINCT trip_id) AS viagens_acessiveis_alguma_origem, count(DISTINCT route_id) AS linhas_acessiveis_alguma_origem
    FROM analise.origem_viagem_periodo GROUP BY periodo
)
SELECT pa.periodo, pa.inicio, pa.fim, (pa.fim_s - pa.inicio_s) / 3600.0 AS duracao_h,
       mun.pob_grade, mun.pob_coberta_400m, mun.pob_com_servico, mun.pob_coberta_sem_servico, mun.pob_sem_cobertura,
       mun.pob_nao_determinada,
       100 * mun.pob_com_servico / mun.pob_grade AS pct_com_servico,
       100 * mun.pob_coberta_sem_servico / mun.pob_grade AS pct_coberta_sem_servico,
       100 * (mun.pob_sem_cobertura + mun.pob_coberta_sem_servico) / mun.pob_grade AS pct_sem_oferta_acessivel,
       100 * mun.pob_nao_determinada / mun.pob_grade AS pct_nao_determinada,
       mun.media_linhas, mun.media_partidas_hora, mun.media_linhas_cobertos, mun.media_partidas_hora_cobertos,
       mun.mediana_pontos_partidas_hora, mun.pct_viagens_horario_interpolado,
       rede.viagens_rede, rede.viagens_rede / ((pa.fim_s - pa.inicio_s) / 3600.0) AS viagens_rede_hora,
       rede.linhas_rede, rede.linha_sentido_rede, rede.partidas_paradas_rede, rede.paradas_com_partida_rede,
       100.0 * rede.partidas_paradas_interpoladas / rede.partidas_paradas_rede AS pct_partidas_paradas_interpoladas,
       acess.viagens_acessiveis_alguma_origem, acess.linhas_acessiveis_alguma_origem
FROM prep.periodos_analise pa
JOIN mun USING (periodo) JOIN rede USING (periodo) JOIN acess USING (periodo);
ALTER TABLE analise.sintese_oferta_municipal ADD PRIMARY KEY (periodo);
COMMENT ON TABLE analise.sintese_oferta_municipal IS
    'viagens_rede = total programado na rede TUSSAM; media_* = oferta acessível ao morador médio estimado — não equivalentes';

-- ------------------------------------------------------------------ Distritos (exploratório) e views QGIS
CREATE OR REPLACE VIEW analise.v_oferta_distrito_periodo AS
SELECT o.cdis, o.periodo, count(DISTINCT o.cusec) AS secoes, sum(o.pob_ine) AS pob_ine,
       sum(o.pob_ine) / sum(o.area_km2) AS densidade_ine_hab_km2, sum(o.pob_grade) AS pob_grade,
       sum(o.media_linhas * o.pob_determinada) / nullif(sum(o.pob_determinada), 0) AS media_linhas,
       sum(o.media_partidas_hora * o.pob_determinada) / nullif(sum(o.pob_determinada), 0) AS media_partidas_hora,
       100 * sum(o.pob_com_servico) / nullif(sum(o.pob_grade), 0) AS pct_com_servico,
       100 * sum(o.pob_sem_oferta_acessivel) / nullif(sum(o.pob_grade), 0) AS pct_sem_oferta_acessivel,
       min(o.media_partidas_hora) AS min_partidas_hora_secao, max(o.media_partidas_hora) AS max_partidas_hora_secao
FROM analise.oferta_seccion_periodo o GROUP BY o.cdis, o.periodo;

CREATE OR REPLACE VIEW analise.v_secciones_oferta AS
SELECT * FROM analise.indicadores_seccion_oferta;          -- polígonos originais INE, EPSG:25830

CREATE OR REPLACE VIEW analise.v_secciones_oferta_periodo AS
SELECT * FROM analise.oferta_seccion_periodo;

CREATE OR REPLACE VIEW analise.v_pontos_oferta_periodo AS
SELECT o.*, r.geom FROM analise.oferta_origem_periodo o JOIN analise.resultado_origem r USING (origem_id);

ANALYZE analise.oferta_origem_periodo, analise.oferta_seccion_periodo, analise.origem_viagem_periodo;
