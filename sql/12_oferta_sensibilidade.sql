-- =====================================================================================
-- 12_oferta_sensibilidade.sql — Etapa 3: sensibilidade da oferta aos horários interpolados
-- Horários explícitos ficam fixos. Para cada partida interpolada sabe-se apenas que o horário real
-- programado está entre os pontos de controle anterior (t0) e seguinte (t1). Cenários:
--   base             horário interpolado por distância (referência)
--   menos_2min       interpolado - 2 min (limitado a [t0, t1])
--   mais_2min        interpolado + 2 min (limitado a [t0, t1])
--   limite_inferior  conta só se toda a faixa [t0, t1] estiver na janela (envoltória mínima)
--   limite_superior  conta se alguma parte da faixa [t0, t1] tocar a janela (envoltória máxima)
-- ±2 min ≈ 1/4 do intervalo mediano (8 min) entre pontos de controle; os limites são envoltórias,
-- não intervalos de confiança.
-- =====================================================================================

DROP TABLE IF EXISTS analise.sensibilidade_partidas CASCADE;
CREATE TABLE analise.sensibilidade_partidas AS
WITH cen(cenario) AS (VALUES ('base'), ('menos_2min'), ('mais_2min'), ('limite_inferior'), ('limite_superior')),
d AS (SELECT trip_id, route_id, stop_id, partida_s, origem_horario,
             coalesce(t_controle_anterior_s, partida_s) AS t0, coalesce(t_controle_seguinte_s, partida_s) AS t1
      FROM analise.partidas_dia)
SELECT c.cenario, pa.periodo, d.trip_id, d.route_id, d.stop_id, d.origem_horario
FROM d CROSS JOIN cen c
JOIN prep.periodos_analise pa ON CASE
    WHEN d.origem_horario = 'explicito' OR c.cenario = 'base'
         THEN d.partida_s >= pa.inicio_s AND d.partida_s < pa.fim_s
    WHEN c.cenario = 'menos_2min'
         THEN greatest(d.partida_s - 120, d.t0) >= pa.inicio_s AND greatest(d.partida_s - 120, d.t0) < pa.fim_s
    WHEN c.cenario = 'mais_2min'
         THEN least(d.partida_s + 120, d.t1) >= pa.inicio_s AND least(d.partida_s + 120, d.t1) < pa.fim_s
    WHEN c.cenario = 'limite_inferior' THEN d.t0 >= pa.inicio_s AND d.t1 < pa.fim_s
    WHEN c.cenario = 'limite_superior' THEN d.t1 >= pa.inicio_s AND d.t0 < pa.fim_s
END;
CREATE INDEX ON analise.sensibilidade_partidas (stop_id, cenario, periodo);

DROP TABLE IF EXISTS analise.sensibilidade_origem CASCADE;
CREATE TABLE analise.sensibilidade_origem AS
WITH v AS (
    SELECT op.origem_id, s.cenario, s.periodo, count(DISTINCT s.trip_id) AS n_viagens, count(DISTINCT s.route_id) AS n_linhas
    FROM analise.origem_parada_400m op JOIN analise.sensibilidade_partidas s USING (stop_id)
    GROUP BY 1, 2, 3
)
SELECT o.origem_id, o.cusec, o.pob_estimada, c.cenario, o.periodo,
       CASE WHEN o.situacao_oferta <> 'nao_determinado' THEN coalesce(v.n_viagens, 0) END AS n_viagens,
       CASE WHEN o.situacao_oferta <> 'nao_determinado' THEN coalesce(v.n_linhas, 0) END AS n_linhas,
       CASE WHEN o.situacao_oferta <> 'nao_determinado' THEN coalesce(v.n_viagens, 0) / o.duracao_h END AS partidas_hora,
       o.situacao_cobertura
FROM analise.oferta_origem_periodo o
CROSS JOIN (SELECT DISTINCT cenario FROM analise.sensibilidade_partidas) c
LEFT JOIN v ON v.origem_id = o.origem_id AND v.cenario = c.cenario AND v.periodo = o.periodo;
ALTER TABLE analise.sensibilidade_origem ADD PRIMARY KEY (origem_id, cenario, periodo);

-- Resumo: município e estabilidade entre seções (correlação de postos de Spearman com o cenário base)
DROP TABLE IF EXISTS analise.sensibilidade_resumo CASCADE;
CREATE TABLE analise.sensibilidade_resumo AS
WITH sec AS (
    SELECT cusec, cenario, periodo,
           sum(pob_estimada * partidas_hora) / nullif(sum(pob_estimada) FILTER (WHERE partidas_hora IS NOT NULL), 0) AS ph,
           sum(pob_estimada * n_linhas) / nullif(sum(pob_estimada) FILTER (WHERE n_linhas IS NOT NULL), 0) AS lin
    FROM analise.sensibilidade_origem GROUP BY 1, 2, 3
), rk AS (
    -- posto médio nos empates (Spearman correto)
    SELECT sec.*, rank() OVER (PARTITION BY cenario, periodo ORDER BY ph)
                  + (count(*) OVER (PARTITION BY cenario, periodo, ph) - 1) / 2.0 AS rk_ph
    FROM sec WHERE ph IS NOT NULL
), cmp AS (
    SELECT c.cenario, c.periodo, corr(c.rk_ph, b.rk_ph) AS spearman_secoes_partidas_hora,
           max(abs(c.ph - b.ph)) AS max_dif_abs_secao_partidas_hora,
           count(*) FILTER (WHERE abs(c.ph - b.ph) > 0.10 * nullif(b.ph, 0)) AS secoes_dif_maior_10pct,
           max(abs(c.lin - b.lin)) AS max_dif_abs_secao_linhas
    FROM rk c JOIN rk b ON b.cusec = c.cusec AND b.periodo = c.periodo AND b.cenario = 'base'
    GROUP BY 1, 2
), mun AS (
    SELECT cenario, periodo,
           sum(pob_estimada * partidas_hora) / sum(pob_estimada) FILTER (WHERE partidas_hora IS NOT NULL) AS media_partidas_hora,
           sum(pob_estimada * n_linhas) / sum(pob_estimada) FILTER (WHERE n_linhas IS NOT NULL) AS media_linhas,
           coalesce(sum(pob_estimada) FILTER (WHERE situacao_cobertura = 'coberto_400m' AND n_viagens = 0), 0) AS pob_coberta_sem_servico
    FROM analise.sensibilidade_origem GROUP BY 1, 2
), rede AS (
    SELECT cenario, periodo, count(DISTINCT trip_id) AS viagens_rede, count(*) AS partidas_paradas_rede
    FROM analise.sensibilidade_partidas GROUP BY 1, 2
)
SELECT m.periodo, m.cenario, r.viagens_rede, r.partidas_paradas_rede,
       m.media_partidas_hora, 100 * (m.media_partidas_hora / b.media_partidas_hora - 1) AS dif_pct_media_partidas_hora,
       m.media_linhas, 100 * (m.media_linhas / b.media_linhas - 1) AS dif_pct_media_linhas,
       m.pob_coberta_sem_servico,
       c.spearman_secoes_partidas_hora, c.max_dif_abs_secao_partidas_hora, c.secoes_dif_maior_10pct, c.max_dif_abs_secao_linhas
FROM mun m
JOIN mun b ON b.periodo = m.periodo AND b.cenario = 'base'
JOIN rede r ON r.periodo = m.periodo AND r.cenario = m.cenario
JOIN cmp c ON c.periodo = m.periodo AND c.cenario = m.cenario;
ALTER TABLE analise.sensibilidade_resumo ADD PRIMARY KEY (periodo, cenario);

-- Partidas interpoladas próximas às fronteiras (±5 min) por período (diagnóstico)
CREATE OR REPLACE VIEW analise.v_partidas_fronteira AS
SELECT pa.periodo, f.fronteira, count(*) AS partidas_paradas,
       count(*) FILTER (WHERE d.origem_horario = 'interpolado') AS interpoladas,
       count(DISTINCT d.trip_id) AS viagens
FROM prep.periodos_analise pa
CROSS JOIN LATERAL (VALUES ('inicio', pa.inicio_s), ('fim', pa.fim_s)) f(fronteira, t)
JOIN analise.partidas_dia d ON d.partida_s >= f.t - 300 AND d.partida_s < f.t + 300
GROUP BY 1, 2;
