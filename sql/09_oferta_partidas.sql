-- =====================================================================================
-- 09_oferta_partidas.sql — Etapa 3: partidas programadas de ônibus TUSSAM no dia de referência
-- Reutiliza prep.gtfs_horarios_dia (horários explícitos e interpolados por distância, Etapa 1),
-- prep.gtfs_viagens_dia (serviço INVLAB40 de 21/10/2026, só route_type 3) e prep.periodos_analise.
--
-- Partida programada = passagem de uma viagem por uma parada onde é possível embarcar:
--   * exclui a última parada de cada viagem (só desembarque);
--   * pickup_type vazio em todo o feed => embarque regular nas demais paradas.
-- Horários em segundos desde 00:00 do dia de serviço (Europe/Madrid; sem mudança de horário em 21/10/2026).
-- =====================================================================================

DROP TABLE IF EXISTS analise.partidas_dia CASCADE;
CREATE TABLE analise.partidas_dia AS
WITH h AS (
    SELECT h.*, max(h.dist_m) OVER (PARTITION BY h.trip_id) AS dist_final
    FROM prep.gtfs_horarios_dia h
)
SELECT (SELECT valor::date FROM prep.parametros WHERE chave = 'dia_referencia') AS data,
       h.trip_id, v.route_id, v.route_short_name, v.direction_id, v.trip_headsign, v.service_id,
       h.stop_id, h.dist_m AS stop_sequence, h.partida_s,
       to_char(make_interval(secs => h.partida_s), 'HH24:MI:SS') AS hora,
       h.origem_horario, h.t_controle_anterior_s, h.t_controle_seguinte_s
FROM h
JOIN prep.gtfs_viagens_dia v USING (trip_id)
WHERE h.dist_m < h.dist_final;
ALTER TABLE analise.partidas_dia ADD PRIMARY KEY (trip_id, stop_sequence);
CREATE INDEX ON analise.partidas_dia (stop_id, partida_s);
CREATE INDEX ON analise.partidas_dia (route_id, direction_id);
COMMENT ON TABLE analise.partidas_dia IS
    'Partidas de ônibus TUSSAM em 21/10/2026 (embarque possível; última parada excluída). stop_sequence = distância acumulada (m)';

-- Partidas dentro das janelas [inicio, fim)
DROP TABLE IF EXISTS analise.partidas_periodo CASCADE;
CREATE TABLE analise.partidas_periodo AS
SELECT p.periodo, d.*
FROM analise.partidas_dia d
JOIN prep.periodos_analise p ON d.partida_s >= p.inicio_s AND d.partida_s < p.fim_s;
ALTER TABLE analise.partidas_periodo ADD PRIMARY KEY (periodo, trip_id, stop_sequence);
CREATE INDEX ON analise.partidas_periodo (stop_id, periodo);
CREATE INDEX ON analise.partidas_periodo (periodo, route_id, direction_id);
COMMENT ON TABLE analise.partidas_periodo IS 'Partidas programadas por período (intervalo fechado no início e aberto no fim)';

-- ------------------------------------------------------------------ Oferta da rede por linha, sentido e período
-- n_viagens conta viagens com qualquer partida na janela (inclui as que só começam ou terminam nela);
-- a frequência por parada é partidas_hora_parada_referencia.
-- Intervalo programado medido na parada de referência da linha-sentido (a de mais partidas no período;
-- empate: menor stop_sequence médio, depois stop_id). Média = (última - primeira) / (n - 1).
DROP TABLE IF EXISTS analise.oferta_linha_sentido_periodo CASCADE;
CREATE TABLE analise.oferta_linha_sentido_periodo AS
WITH por_parada AS (
    SELECT periodo, route_id, direction_id, stop_id, count(*) AS n, min(partida_s) AS t1, max(partida_s) AS tn,
           avg(stop_sequence) AS seq_media
    FROM analise.partidas_periodo GROUP BY 1, 2, 3, 4
), ref AS (
    SELECT DISTINCT ON (periodo, route_id, direction_id) *
    FROM por_parada ORDER BY periodo, route_id, direction_id, n DESC, seq_media, stop_id
), gaps AS (
    SELECT p.periodo, p.route_id, p.direction_id,
           max(p.partida_s - p.ant) AS gap_max_s, min(p.partida_s - p.ant) AS gap_min_s
    FROM (SELECT pp.*, lag(pp.partida_s) OVER (PARTITION BY pp.periodo, pp.route_id, pp.direction_id ORDER BY pp.partida_s, pp.trip_id) AS ant
          FROM analise.partidas_periodo pp JOIN ref r USING (periodo, route_id, direction_id, stop_id)) p
    GROUP BY 1, 2, 3
), tot AS (
    SELECT periodo, route_id, route_short_name, direction_id,
           count(DISTINCT trip_id) AS n_viagens, count(*) AS n_partidas_paradas, count(DISTINCT stop_id) AS n_paradas,
           string_agg(DISTINCT trip_headsign, ' / ') AS destinos
    FROM analise.partidas_periodo GROUP BY 1, 2, 3, 4
)
SELECT t.periodo, t.route_id, t.route_short_name, t.direction_id, t.destinos,
       t.n_viagens, t.n_viagens / ((pa.fim_s - pa.inicio_s) / 3600.0) AS viagens_hora,
       t.n_partidas_paradas, t.n_paradas,
       r.stop_id AS parada_referencia, r.n AS partidas_parada_referencia,
       r.n / ((pa.fim_s - pa.inicio_s) / 3600.0) AS partidas_hora_parada_referencia,
       CASE WHEN r.n >= 2 THEN (r.tn - r.t1) / 60.0 / (r.n - 1) END AS intervalo_medio_min,
       g.gap_min_s / 60.0 AS intervalo_min_min, g.gap_max_s / 60.0 AS intervalo_max_min
FROM tot t
JOIN prep.periodos_analise pa USING (periodo)
JOIN ref r USING (periodo, route_id, direction_id)
LEFT JOIN gaps g USING (periodo, route_id, direction_id);
ALTER TABLE analise.oferta_linha_sentido_periodo ADD PRIMARY KEY (periodo, route_id, direction_id);
