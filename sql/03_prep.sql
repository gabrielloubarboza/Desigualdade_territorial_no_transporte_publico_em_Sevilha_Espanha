-- =====================================================================================
-- 03_prep.sql — tabelas preparadas (EPSG:25830) para as etapas seguintes
-- Depende de: 01_schemas_fonte.sql, carga de `fonte`, 02_fonte_chaves.sql e prep.parametros /
-- prep.periodos_analise (preenchidos pelo carregador a partir de config/config.yaml).
-- Não calcula indicadores: apenas organiza geometrias, população e horários programados.
-- =====================================================================================

-- ------------------------------------------------------------------ 1. Seções censitárias
DROP TABLE IF EXISTS prep.secciones CASCADE;
CREATE TABLE prep.secciones AS
SELECT s.cusec, s.cumun, s.cdis, s.csec, s.cudis, s.nmun,
       ST_IsValid(s.geom) AS geom_valida_original,
       ST_Multi(CASE WHEN ST_IsValid(s.geom) THEN s.geom
                     ELSE ST_CollectionExtract(ST_MakeValid(s.geom), 3) END)::geometry(MultiPolygon, 25830) AS geom
FROM fonte.ine_secciones_2024 s;
ALTER TABLE prep.secciones ADD PRIMARY KEY (cusec);
ALTER TABLE prep.secciones ADD COLUMN area_m2 double precision, ADD COLUMN area_km2 double precision;
UPDATE prep.secciones SET area_m2 = ST_Area(geom), area_km2 = ST_Area(geom) / 1e6;
CREATE INDEX ON prep.secciones USING gist (geom);
COMMENT ON TABLE prep.secciones IS 'Seções censitárias INE 2024 de Sevilla (41091), EPSG:25830, com área';

-- ------------------------------------------------------------------ 2. Limite municipal
DROP TABLE IF EXISTS prep.limite_municipal CASCADE;
CREATE TABLE prep.limite_municipal AS
SELECT 'ine_seccionado_2024'::text AS fonte, true AS principal,
       ST_Multi(ST_Union(geom))::geometry(MultiPolygon, 25830) AS geom
FROM prep.secciones
UNION ALL
SELECT 'ign_inspire_au', false,
       ST_Multi(ST_CollectionExtract(ST_MakeValid(geom), 3))::geometry(MultiPolygon, 25830)
FROM fonte.ign_limite_municipal;
ALTER TABLE prep.limite_municipal ADD PRIMARY KEY (fonte);
ALTER TABLE prep.limite_municipal ADD COLUMN area_km2 double precision, ADD COLUMN geom_valida boolean;
UPDATE prep.limite_municipal SET area_km2 = ST_Area(geom) / 1e6, geom_valida = ST_IsValid(geom);
CREATE INDEX ON prep.limite_municipal USING gist (geom);
COMMENT ON TABLE prep.limite_municipal IS
    'Limite de Sevilla: principal = dissolução do seccionado INE 2024 (coerente com a população); IGN para comparação';

-- ------------------------------------------------------------------ 3. População por seção (ano de referência)
DROP TABLE IF EXISTS prep.poblacion_seccion CASCADE;
CREATE TABLE prep.poblacion_seccion AS
SELECT p.cod_seccion AS cusec, p.periodo AS ano,
       max(p.valor) FILTER (WHERE sexo = 'Total'   AND nacionalidad = 'Total')      AS poblacion_total,
       max(p.valor) FILTER (WHERE sexo = 'Hombres' AND nacionalidad = 'Total')      AS hombres,
       max(p.valor) FILTER (WHERE sexo = 'Mujeres' AND nacionalidad = 'Total')      AS mujeres,
       max(p.valor) FILTER (WHERE sexo = 'Total'   AND nacionalidad = 'Española')   AS nacionalidad_espanola,
       max(p.valor) FILTER (WHERE sexo = 'Total'   AND nacionalidad = 'Extranjera') AS nacionalidad_extranjera
FROM fonte.ine_poblacion_seccion p
WHERE p.cod_seccion IS NOT NULL
  AND p.periodo = (SELECT valor::int FROM prep.parametros WHERE chave = 'ano_populacao')
GROUP BY 1, 2
HAVING max(p.valor) FILTER (WHERE sexo = 'Total' AND nacionalidad = 'Total') IS NOT NULL;
ALTER TABLE prep.poblacion_seccion ADD PRIMARY KEY (cusec);
COMMENT ON TABLE prep.poblacion_seccion IS
    'População residente por seção (INE Censo Anual, 1 de janeiro do ano de referência); sem densidade/classificação';

-- ------------------------------------------------------------------ 4. Grade IECA 250 m
DROP TABLE IF EXISTS prep.grid_250 CASCADE;
CREATE TABLE prep.grid_250 AS
WITH lim AS (SELECT geom FROM prep.limite_municipal WHERE principal)
SELECT g.gidmp, g.grd_fixid, g.grd_inspir_1k, g.cmun, g.municipio, g.nota,
       g.pob_tot, g.pob_m, g.pob_h,
       -- Desde 2024 o IECA atribui valor 2 a totais sob sigilo e suprime (0) as categorias
       (g.pob_tot = 2 AND coalesce(g.pob_m, 0) + coalesce(g.pob_h, 0) = 0) AS sigilo_total_convencional,
       (g.nota IS NOT NULL)                        AS sigilo_em_categorias,
       (position('/' IN g.cmun) > 0)               AS celda_multimunicipal,
       ST_Area(g.geom)                             AS area_m2,
       ST_Area(ST_Intersection(g.geom, lim.geom)) / ST_Area(g.geom) AS frac_dentro_municipio,
       ST_Multi(g.geom)::geometry(MultiPolygon, 25830) AS geom
FROM fonte.ieca_gridp_250 g, lim
WHERE ST_Intersects(g.geom, lim.geom);
ALTER TABLE prep.grid_250 ADD PRIMARY KEY (gidmp);
CREATE INDEX ON prep.grid_250 USING gist (geom);

-- Interseções célula x seção (preparação para a futura atribuição; nenhuma população é redistribuída aqui)
DROP TABLE IF EXISTS prep.grid_seccion_intersecao CASCADE;
CREATE TABLE prep.grid_seccion_intersecao AS
SELECT g.gidmp, s.cusec,
       ST_Area(ST_Intersection(g.geom, s.geom))                AS area_intersecao_m2,
       ST_Area(ST_Intersection(g.geom, s.geom)) / g.area_m2    AS frac_celda
FROM prep.grid_250 g
JOIN prep.secciones s ON ST_Intersects(g.geom, s.geom)
WHERE ST_Area(ST_Intersection(g.geom, s.geom)) > 0;
ALTER TABLE prep.grid_seccion_intersecao ADD PRIMARY KEY (gidmp, cusec);

ALTER TABLE prep.grid_250 ADD COLUMN n_secciones integer, ADD COLUMN frac_maior_secao double precision,
                          ADD COLUMN relacao_secoes text;
UPDATE prep.grid_250 g
SET n_secciones = i.n, frac_maior_secao = i.fmax,
    relacao_secoes = CASE
        WHEN g.frac_dentro_municipio < 0.999 THEN 'parcialmente_fora_municipio'
        WHEN i.n_sig = 1                     THEN 'contida_em_uma_secao'
        ELSE 'multiplas_secoes' END
FROM (SELECT gidmp, count(*) AS n, max(frac_celda) AS fmax,
             count(*) FILTER (WHERE frac_celda >= 0.001) AS n_sig     -- ignora lascas < 0,1% da célula
      FROM prep.grid_seccion_intersecao GROUP BY gidmp) i
WHERE i.gidmp = g.gidmp;
COMMENT ON COLUMN prep.grid_250.relacao_secoes IS
    'contida_em_uma_secao | multiplas_secoes | parcialmente_fora_municipio (lascas < 0,1% da célula ignoradas)';

-- ------------------------------------------------------------------ 5. GTFS — modos, serviços e viagens do dia
DROP TABLE IF EXISTS prep.gtfs_rotas CASCADE;
CREATE TABLE prep.gtfs_rotas AS
SELECT r.route_id, r.agency_id, r.route_short_name, r.route_long_name, r.route_type,
       CASE r.route_type WHEN 3 THEN 'onibus' WHEN 0 THEN 'bonde' ELSE 'outro' END AS modo,
       (r.route_type = 3 AND r.agency_id = 'TUSSAM') AS incluida_analise,
       CASE WHEN r.route_type = 3 AND r.agency_id = 'TUSSAM' THEN 'onibus urbano TUSSAM (route_type 3)'
            WHEN r.route_type = 0 THEN 'excluida: bonde/Metrocentro (route_type 0)'
            ELSE 'excluida: modo ou operador fora do escopo' END AS criterio
FROM fonte.gtfs_routes r;
ALTER TABLE prep.gtfs_rotas ADD PRIMARY KEY (route_id);

DROP TABLE IF EXISTS prep.gtfs_servicos_dia CASCADE;
CREATE TABLE prep.gtfs_servicos_dia AS
WITH p AS (SELECT valor::date AS d FROM prep.parametros WHERE chave = 'dia_referencia')
SELECT p.d AS data, c.service_id, 'calendar'::text AS origem
FROM fonte.gtfs_calendar c, p
WHERE p.d BETWEEN c.start_date AND c.end_date
  AND (ARRAY[c.monday, c.tuesday, c.wednesday, c.thursday, c.friday, c.saturday, c.sunday])
      [extract(isodow FROM p.d)::int] = 1
  AND NOT EXISTS (SELECT 1 FROM fonte.gtfs_calendar_dates x
                  WHERE x.service_id = c.service_id AND x.date = p.d AND x.exception_type = 2)
UNION
SELECT p.d, x.service_id, 'calendar_dates'
FROM fonte.gtfs_calendar_dates x, p
WHERE x.date = p.d AND x.exception_type = 1;
ALTER TABLE prep.gtfs_servicos_dia ADD PRIMARY KEY (service_id);

DROP TABLE IF EXISTS prep.gtfs_viagens_dia CASCADE;
CREATE TABLE prep.gtfs_viagens_dia AS
SELECT t.trip_id, t.route_id, r.route_short_name, t.service_id, t.direction_id, t.trip_headsign
FROM fonte.gtfs_trips t
JOIN prep.gtfs_servicos_dia s USING (service_id)
JOIN prep.gtfs_rotas r USING (route_id)
WHERE r.incluida_analise;
ALTER TABLE prep.gtfs_viagens_dia ADD PRIMARY KEY (trip_id);
CREATE INDEX ON prep.gtfs_viagens_dia (route_id);

-- ------------------------------------------------------------------ 6. Horários programados por parada (dia de referência)
-- O feed só traz horário nos pontos de controle; nas demais paradas o horário é interpolado
-- linearmente pela distância acumulada (stop_sequence, em metros) entre os pontos de controle
-- anterior e seguinte. A origem de cada horário fica registrada em `origem_horario`.
DROP TABLE IF EXISTS prep.gtfs_horarios_dia CASCADE;
CREATE TABLE prep.gtfs_horarios_dia AS
WITH b AS (
    SELECT st.trip_id, st.stop_id, st.stop_sequence AS dist_m,
           prep.gtfs_segundos(st.departure_time) AS t_exp
    FROM fonte.gtfs_stop_times st
    JOIN prep.gtfs_viagens_dia v USING (trip_id)
), l AS (
    SELECT b.*,
           max(dist_m) FILTER (WHERE t_exp IS NOT NULL)
               OVER (PARTITION BY trip_id ORDER BY dist_m ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS d0,
           min(dist_m) FILTER (WHERE t_exp IS NOT NULL)
               OVER (PARTITION BY trip_id ORDER BY dist_m ROWS BETWEEN CURRENT ROW AND UNBOUNDED FOLLOWING) AS d1
    FROM b
)
SELECT l.trip_id, l.stop_id, l.dist_m,
       CASE WHEN l.t_exp IS NOT NULL THEN l.t_exp
            ELSE round(b0.t_exp + (b1.t_exp - b0.t_exp) * (l.dist_m - l.d0)::numeric / (l.d1 - l.d0))::int
       END AS partida_s,
       CASE WHEN l.t_exp IS NOT NULL THEN 'explicito' ELSE 'interpolado' END AS origem_horario,
       b0.t_exp AS t_controle_anterior_s,
       b1.t_exp AS t_controle_seguinte_s
FROM l
JOIN b b0 ON b0.trip_id = l.trip_id AND b0.dist_m = l.d0
JOIN b b1 ON b1.trip_id = l.trip_id AND b1.dist_m = l.d1;
ALTER TABLE prep.gtfs_horarios_dia ADD PRIMARY KEY (trip_id, dist_m);
CREATE INDEX ON prep.gtfs_horarios_dia (stop_id, partida_s);
COMMENT ON TABLE prep.gtfs_horarios_dia IS
    'Partidas programadas de ônibus por parada no dia de referência; segundos desde 00:00 do dia de serviço (podem passar de 86400)';

-- ------------------------------------------------------------------ 7. Paradas GTFS e paradas oficiais (IDE)
DROP TABLE IF EXISTS prep.gtfs_paradas CASCADE;
CREATE TABLE prep.gtfs_paradas AS
WITH uso AS (
    SELECT st.stop_id,
           bool_or(r.route_type = 3) AS serve_onibus,
           bool_or(r.route_type = 0) AS serve_bonde
    FROM fonte.gtfs_stop_times st
    JOIN fonte.gtfs_trips t USING (trip_id)
    JOIN fonte.gtfs_routes r USING (route_id)
    GROUP BY st.stop_id
)
SELECT s.stop_id, s.stop_code, s.stop_name, s.location_type, s.parent_station,
       coalesce(u.serve_onibus, false) AS serve_onibus,
       coalesce(u.serve_bonde, false)  AS serve_bonde,
       EXISTS (SELECT 1 FROM prep.gtfs_horarios_dia h WHERE h.stop_id = s.stop_id) AS serve_onibus_dia_ref,
       ST_Transform(ST_SetSRID(ST_MakePoint(s.stop_lon, s.stop_lat), 4326), 25830)::geometry(Point, 25830) AS geom
FROM fonte.gtfs_stops s
LEFT JOIN uso u USING (stop_id);
ALTER TABLE prep.gtfs_paradas ADD PRIMARY KEY (stop_id);
CREATE INDEX ON prep.gtfs_paradas USING gist (geom);
ALTER TABLE prep.gtfs_paradas ADD COLUMN dentro_municipio boolean;
UPDATE prep.gtfs_paradas p SET dentro_municipio = ST_Intersects(p.geom, l.geom)
FROM prep.limite_municipal l WHERE l.principal;

-- Camada oficial: um registro por parada (Nodo); a fonte tem um registro por parada x linha x rota
DROP TABLE IF EXISTS prep.tussam_paradas_ide CASCADE;
CREATE TABLE prep.tussam_paradas_ide AS
SELECT p.nodo::text AS nodo,
       min(p.nombre) AS nombre,
       count(*) AS n_registros,
       count(DISTINCT p.linea) AS n_linhas,
       string_agg(DISTINCT p.labellinea, ',' ORDER BY p.labellinea) AS linhas,
       count(DISTINCT ST_AsText(p.geom)) AS n_coordenadas_distintas,
       ST_Transform(ST_Centroid(ST_Collect(p.geom)), 25830)::geometry(Point, 25830) AS geom
FROM fonte.tussam_paradas_ide p
GROUP BY p.nodo;
ALTER TABLE prep.tussam_paradas_ide ADD PRIMARY KEY (nodo);
CREATE INDEX ON prep.tussam_paradas_ide USING gist (geom);

-- ------------------------------------------------------------------ 8. Rede caminhável
DROP TABLE IF EXISTS prep.rede_nos CASCADE;
CREATE TABLE prep.rede_nos AS
SELECT n.osmid AS no_id, n.componente, n.street_count, n.highway, ST_Force2D(n.geom)::geometry(Point, 25830) AS geom
FROM fonte.osm_nos n;
ALTER TABLE prep.rede_nos ADD PRIMARY KEY (no_id);
CREATE INDEX ON prep.rede_nos USING gist (geom);

DROP TABLE IF EXISTS prep.rede_arestas CASCADE;
CREATE TABLE prep.rede_arestas AS
SELECT row_number() OVER (ORDER BY a.u, a.v, a.key)::int AS aresta_id,
       a.u AS no_origem, a.v AS no_destino, a.key, a.osmid, a.highway, a.name,
       a.bridge, a.tunnel, a.access, a.foot, a.footway, a.componente,
       a.comprimento_m,
       -- marcações para decisão nas próximas etapas (nenhuma aresta é removida aqui)
       (a.access IN ('no', 'private') AND coalesce(a.foot, '') NOT IN ('yes', 'designated', 'permissive'))
           AS restricao_acesso,
       (a.highway ~ '(^|;)(trunk|trunk_link|motorway|motorway_link)(;|$)') AS via_alta_capacidade,
       (a.highway ~ '(^|;)busway(;|$)') AS via_exclusiva_onibus,
       ST_Force2D(a.geom)::geometry(LineString, 25830) AS geom
FROM fonte.osm_arestas a;
ALTER TABLE prep.rede_arestas ADD PRIMARY KEY (aresta_id);
CREATE INDEX ON prep.rede_arestas (no_origem);
CREATE INDEX ON prep.rede_arestas (no_destino);
CREATE INDEX ON prep.rede_arestas USING gist (geom);
ALTER TABLE prep.rede_arestas ADD COLUMN dentro_municipio boolean;
UPDATE prep.rede_arestas a SET dentro_municipio = ST_Intersects(a.geom, l.geom)
FROM prep.limite_municipal l WHERE l.principal;

ANALYZE;
