-- =====================================================================================
-- 10_oferta_origem.sql — Etapa 3: oferta programada acessível por origem e período
-- Paradas acessíveis: analise.origem_parada_400m (Etapa 2, sem recálculo do roteamento).
--
-- Deduplicação: uma viagem (trip_id) acessível em várias paradas conta uma única vez por origem e
-- período. Embarque representativo = parada de menor percurso caminhável; empate: partida mais cedo,
-- depois stop_id.
-- Linha distinta = route_id (linha pública route_short_name; C6A/C6B, 38/38A, CJ/CJ1 são linhas distintas
-- no feed). Linha-sentido = (route_id, direction_id).
-- =====================================================================================

-- ------------------------------------------------------------------ Viagens acessíveis deduplicadas
DROP TABLE IF EXISTS analise.origem_viagem_periodo CASCADE;
CREATE TABLE analise.origem_viagem_periodo AS
WITH c AS (
    SELECT op.origem_id, p.periodo, p.trip_id, p.route_id, p.route_short_name, p.direction_id,
           p.stop_id, p.stop_sequence, p.partida_s, p.origem_horario, op.distancia_m,
           count(*) OVER w AS n_paradas_acessiveis_viagem,
           row_number() OVER (PARTITION BY op.origem_id, p.periodo, p.trip_id
                              ORDER BY op.distancia_m, p.partida_s, p.stop_id) AS ordem
    FROM analise.origem_parada_400m op
    JOIN analise.partidas_periodo p USING (stop_id)
    WINDOW w AS (PARTITION BY op.origem_id, p.periodo, p.trip_id)
)
SELECT origem_id, periodo, trip_id, route_id, route_short_name, direction_id,
       stop_id AS stop_embarque, stop_sequence AS stop_sequence_embarque, partida_s AS partida_embarque_s,
       origem_horario AS origem_horario_embarque, distancia_m AS distancia_caminhada_m, n_paradas_acessiveis_viagem
FROM c WHERE ordem = 1;
ALTER TABLE analise.origem_viagem_periodo ADD PRIMARY KEY (origem_id, periodo, trip_id);
CREATE INDEX ON analise.origem_viagem_periodo (periodo, route_id, direction_id);
COMMENT ON TABLE analise.origem_viagem_periodo IS
    'Uma linha por origem x período x viagem acessível (deduplicada); embarque = parada de menor caminhada';

-- ------------------------------------------------------------------ Oferta por origem, linha e sentido
-- Intervalo medido na parada de referência da linha-sentido para a origem: a de menor caminhada que a
-- linha-sentido serve no período (empate: mais partidas, stop_id). Não mistura linhas nem sentidos.
-- Etapas intermediárias em tabelas temporárias indexadas (evita junções lentas entre CTEs).
DROP TABLE IF EXISTS tmp_ls_parada, tmp_ls_ref;
CREATE TEMP TABLE tmp_ls_parada AS
SELECT op.origem_id, p.periodo, p.route_id, p.direction_id, p.stop_id, op.distancia_m,
       count(*) AS n, min(p.partida_s) AS t1, max(p.partida_s) AS tn
FROM analise.origem_parada_400m op
JOIN analise.partidas_periodo p USING (stop_id)
GROUP BY 1, 2, 3, 4, 5, 6;
CREATE TEMP TABLE tmp_ls_ref AS
SELECT DISTINCT ON (origem_id, periodo, route_id, direction_id) *
FROM tmp_ls_parada ORDER BY origem_id, periodo, route_id, direction_id, distancia_m, n DESC, stop_id;
CREATE UNIQUE INDEX ON tmp_ls_ref (origem_id, periodo, route_id, direction_id);
ANALYZE tmp_ls_ref;

DROP TABLE IF EXISTS tmp_ls_gaps, tmp_ls_viagens;
CREATE TEMP TABLE tmp_ls_gaps AS
SELECT origem_id, periodo, route_id, direction_id, max(partida_s - ant) AS gap_max_s
FROM (SELECT r.origem_id, p.periodo, p.route_id, p.direction_id, p.partida_s,
             lag(p.partida_s) OVER (PARTITION BY r.origem_id, p.periodo, p.route_id, p.direction_id
                                    ORDER BY p.partida_s, p.trip_id) AS ant
      FROM tmp_ls_ref r JOIN analise.partidas_periodo p USING (periodo, route_id, direction_id, stop_id)) x
GROUP BY 1, 2, 3, 4;
CREATE UNIQUE INDEX ON tmp_ls_gaps (origem_id, periodo, route_id, direction_id);
CREATE TEMP TABLE tmp_ls_viagens AS
SELECT origem_id, periodo, route_id, route_short_name, direction_id, count(*) AS n_viagens,
       count(*) FILTER (WHERE origem_horario_embarque = 'interpolado') AS n_viagens_interpoladas
FROM analise.origem_viagem_periodo GROUP BY 1, 2, 3, 4, 5;
CREATE UNIQUE INDEX ON tmp_ls_viagens (origem_id, periodo, route_id, direction_id);
ANALYZE tmp_ls_gaps, tmp_ls_viagens;

DROP TABLE IF EXISTS analise.origem_linha_sentido_periodo CASCADE;
CREATE TABLE analise.origem_linha_sentido_periodo AS
SELECT v.origem_id, v.periodo, v.route_id, v.route_short_name, v.direction_id, v.n_viagens,
       v.n_viagens / ((pa.fim_s - pa.inicio_s) / 3600.0) AS viagens_hora, v.n_viagens_interpoladas,
       r.stop_id AS parada_referencia, r.distancia_m AS distancia_parada_referencia_m, r.n AS partidas_parada_referencia,
       CASE WHEN r.n >= 2 THEN (r.tn - r.t1) / 60.0 / (r.n - 1) END AS intervalo_medio_min,
       CASE WHEN r.n >= 2 THEN g.gap_max_s / 60.0 END AS intervalo_max_min,
       CASE WHEN r.n >= 2 THEN 'calculado' ELSE 'uma_partida_na_janela' END AS situacao_intervalo
FROM tmp_ls_viagens v
JOIN prep.periodos_analise pa USING (periodo)
JOIN tmp_ls_ref r USING (origem_id, periodo, route_id, direction_id)
LEFT JOIN tmp_ls_gaps g USING (origem_id, periodo, route_id, direction_id);
ALTER TABLE analise.origem_linha_sentido_periodo ADD PRIMARY KEY (origem_id, periodo, route_id, direction_id);

-- ------------------------------------------------------------------ Oferta por origem e período (2.674 x 3)
DROP TABLE IF EXISTS analise.oferta_origem_periodo CASCADE;
CREATE TABLE analise.oferta_origem_periodo AS
WITH base AS (
    SELECT r.origem_id, r.cusec, r.pob_estimada, r.situacao AS situacao_cobertura, r.n_paradas_400m,
           r.sigilo_total_convencional, pa.periodo, (pa.fim_s - pa.inicio_s) / 3600.0 AS horas
    FROM analise.resultado_origem r CROSS JOIN prep.periodos_analise pa
), v AS (
    SELECT origem_id, periodo, count(*) AS n_viagens, count(DISTINCT route_id) AS n_linhas,
           count(DISTINCT (route_id, direction_id)) AS n_linha_sentido,
           count(*) FILTER (WHERE origem_horario_embarque = 'explicito')   AS n_viagens_horario_explicito,
           count(*) FILTER (WHERE origem_horario_embarque = 'interpolado') AS n_viagens_horario_interpolado,
           count(DISTINCT stop_embarque) AS n_paradas_embarque,
           count(*) FILTER (WHERE n_paradas_acessiveis_viagem > 1) AS n_viagens_em_varias_paradas
    FROM analise.origem_viagem_periodo GROUP BY 1, 2
), ps AS (
    SELECT op.origem_id, p.periodo, count(DISTINCT op.stop_id) AS n_paradas_com_partida, count(*) AS n_passagens_brutas
    FROM analise.origem_parada_400m op JOIN analise.partidas_periodo p USING (stop_id) GROUP BY 1, 2
), ls AS (
    SELECT origem_id, periodo,
           count(*) FILTER (WHERE n_sent = 2) AS n_linhas_ambos_sentidos,
           min(menor_int) AS menor_intervalo_medio_min
    FROM (SELECT origem_id, periodo, route_id, count(*) AS n_sent, min(intervalo_medio_min) AS menor_int
          FROM analise.origem_linha_sentido_periodo GROUP BY 1, 2, 3) x
    GROUP BY 1, 2
), dia AS (
    SELECT op.origem_id, count(DISTINCT d.route_id) AS n_linhas_dia
    FROM analise.origem_parada_400m op JOIN analise.partidas_dia d USING (stop_id) GROUP BY 1
)
SELECT b.origem_id, b.cusec, b.periodo, b.pob_estimada, b.situacao_cobertura, b.sigilo_total_convencional,
       CASE WHEN b.situacao_cobertura = 'nao_determinado' THEN 'nao_determinado'
            WHEN b.situacao_cobertura = 'sem_cobertura_400m' THEN 'sem_cobertura_400m'
            WHEN coalesce(v.n_viagens, 0) = 0 THEN 'coberto_sem_servico_no_periodo'
            ELSE 'com_servico' END AS situacao_oferta,
       -- não determinado => NULL (ausência de serviço não comprovada); sem cobertura => 0
       CASE WHEN b.situacao_cobertura <> 'nao_determinado' THEN b.n_paradas_400m END AS n_paradas_400m,
       CASE WHEN b.situacao_cobertura <> 'nao_determinado' THEN coalesce(ps.n_paradas_com_partida, 0) END AS n_paradas_com_partida,
       CASE WHEN b.situacao_cobertura <> 'nao_determinado' THEN coalesce(dia.n_linhas_dia, 0) END AS n_linhas_dia,
       CASE WHEN b.situacao_cobertura <> 'nao_determinado' THEN coalesce(v.n_linhas, 0) END AS n_linhas,
       CASE WHEN b.situacao_cobertura <> 'nao_determinado' THEN coalesce(v.n_linha_sentido, 0) END AS n_linha_sentido,
       CASE WHEN b.situacao_cobertura <> 'nao_determinado' THEN coalesce(ls.n_linhas_ambos_sentidos, 0) END AS n_linhas_ambos_sentidos,
       CASE WHEN b.situacao_cobertura <> 'nao_determinado' THEN coalesce(v.n_viagens, 0) END AS n_viagens,
       CASE WHEN b.situacao_cobertura <> 'nao_determinado' THEN coalesce(v.n_viagens, 0) / b.horas END AS partidas_hora,
       CASE WHEN b.situacao_cobertura <> 'nao_determinado' THEN coalesce(v.n_viagens_horario_explicito, 0) END AS n_viagens_horario_explicito,
       CASE WHEN b.situacao_cobertura <> 'nao_determinado' THEN coalesce(v.n_viagens_horario_interpolado, 0) END AS n_viagens_horario_interpolado,
       CASE WHEN b.situacao_cobertura <> 'nao_determinado' THEN coalesce(ps.n_passagens_brutas, 0) END AS n_passagens_brutas,
       v.n_viagens_em_varias_paradas, v.n_paradas_embarque,
       ls.menor_intervalo_medio_min,
       b.horas AS duracao_h
FROM base b
LEFT JOIN v USING (origem_id, periodo)
LEFT JOIN ps USING (origem_id, periodo)
LEFT JOIN ls USING (origem_id, periodo)
LEFT JOIN dia USING (origem_id);
ALTER TABLE analise.oferta_origem_periodo ADD PRIMARY KEY (origem_id, periodo);
CREATE INDEX ON analise.oferta_origem_periodo (cusec, periodo);
COMMENT ON COLUMN analise.oferta_origem_periodo.n_passagens_brutas IS
    'Passagens (viagem x parada) antes da deduplicação — só para conferência; NÃO é indicador de oferta';
COMMENT ON COLUMN analise.oferta_origem_periodo.menor_intervalo_medio_min IS
    'Menor intervalo médio entre partidas de uma mesma linha-sentido acessível (não combina linhas)';
