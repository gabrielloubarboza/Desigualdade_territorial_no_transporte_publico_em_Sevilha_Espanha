-- =====================================================================================
-- 01_schemas_fonte.sql — schemas e tabelas de dados originais (GTFS e metadados)
-- As tabelas espaciais de `fonte` (INE, IECA, IDE Sevilla, IGN, OSM) são criadas pelo carregador
-- Python a partir dos arquivos originais e recebem chaves/índices em 02_fonte_chaves.sql.
-- Script idempotente: recria apenas objetos deste projeto.
-- =====================================================================================
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE SCHEMA IF NOT EXISTS fonte;
CREATE SCHEMA IF NOT EXISTS prep;
CREATE SCHEMA IF NOT EXISTS qa;
COMMENT ON SCHEMA fonte IS 'Dados originais importados das fontes, sem transformação de conteúdo';
COMMENT ON SCHEMA prep  IS 'Geometrias e tabelas preparadas para as análises (EPSG:25830)';
COMMENT ON SCHEMA qa    IS 'Verificações de qualidade e resultados dos testes de integridade';

-- Metadados das fontes (espelho de data/manifesto_fontes.json)
DROP TABLE IF EXISTS fonte.metadados_fontes;
CREATE TABLE fonte.metadados_fontes (
    fonte_id      text PRIMARY KEY,
    descricao     text,
    produtor      text,
    url           text,
    versao        text,
    data_obtencao timestamptz,
    licenca       text,
    sha256        text,
    detalhes      jsonb NOT NULL
);

-- ---------------------------------------------------------------- GTFS (um único feed)
DROP TABLE IF EXISTS fonte.gtfs_stop_times, fonte.gtfs_trips, fonte.gtfs_routes, fonte.gtfs_stops,
    fonte.gtfs_calendar, fonte.gtfs_calendar_dates, fonte.gtfs_agency, fonte.gtfs_feed_info CASCADE;

CREATE TABLE fonte.gtfs_feed_info (
    feed_publisher_name text, feed_publisher_url text, feed_lang text, default_lang text,
    feed_start_date date, feed_end_date date, feed_version text PRIMARY KEY,
    feed_contact_email text, feed_contact_url text
);

CREATE TABLE fonte.gtfs_agency (
    agency_id text PRIMARY KEY, agency_name text NOT NULL, agency_url text, agency_timezone text NOT NULL,
    agency_lang text, agency_phone text
);

CREATE TABLE fonte.gtfs_routes (
    route_id text PRIMARY KEY, agency_id text REFERENCES fonte.gtfs_agency, route_short_name text,
    route_long_name text, route_desc text, route_type integer NOT NULL, route_url text,
    route_color text, route_text_color text
);

CREATE TABLE fonte.gtfs_calendar (
    service_id text PRIMARY KEY,
    monday smallint, tuesday smallint, wednesday smallint, thursday smallint, friday smallint,
    saturday smallint, sunday smallint, start_date date NOT NULL, end_date date NOT NULL
);

CREATE TABLE fonte.gtfs_calendar_dates (
    service_id text NOT NULL, date date NOT NULL, exception_type smallint NOT NULL,
    PRIMARY KEY (service_id, date)
);

CREATE TABLE fonte.gtfs_stops (
    stop_id text PRIMARY KEY, stop_code text, stop_name text, stop_desc text,
    stop_lat double precision, stop_lon double precision, zone_id text, stop_url text,
    location_type smallint, parent_station text
);

CREATE TABLE fonte.gtfs_trips (
    route_id text NOT NULL REFERENCES fonte.gtfs_routes, service_id text NOT NULL, trip_id text PRIMARY KEY,
    trip_headsign text, direction_id smallint, block_id text, shape_id text
);

-- Horários mantidos como texto: GTFS admite valores >= 24:00:00 (viagens após a meia-noite)
CREATE TABLE fonte.gtfs_stop_times (
    trip_id text NOT NULL REFERENCES fonte.gtfs_trips, arrival_time text, departure_time text,
    stop_id text NOT NULL REFERENCES fonte.gtfs_stops, stop_sequence integer NOT NULL,
    stop_headsign text, pickup_type smallint, drop_off_type smallint, shape_dist_traveled double precision,
    PRIMARY KEY (trip_id, stop_sequence)
);
CREATE INDEX ON fonte.gtfs_stop_times (stop_id);
CREATE INDEX ON fonte.gtfs_trips (service_id);
COMMENT ON COLUMN fonte.gtfs_stop_times.stop_sequence IS
    'No feed TUSSAM corresponde à distância acumulada (m) ao longo do percurso; ver docs/gtfs_tussam.md';

-- ---------------------------------------------------------------- Parâmetros (de config/config.yaml)
DROP TABLE IF EXISTS prep.parametros, prep.periodos_analise;
CREATE TABLE prep.parametros (chave text PRIMARY KEY, valor text NOT NULL);
CREATE TABLE prep.periodos_analise (
    periodo text PRIMARY KEY, inicio time NOT NULL, fim time NOT NULL,
    inicio_s integer GENERATED ALWAYS AS (extract(epoch FROM inicio)::int) STORED,
    fim_s    integer GENERATED ALWAYS AS (extract(epoch FROM fim)::int) STORED,
    CHECK (fim > inicio)
);
COMMENT ON TABLE prep.periodos_analise IS 'Janelas [inicio, fim) para o cálculo futuro de partidas programadas';

-- Converte horário GTFS (HH:MM:SS, possivelmente >= 24h) em segundos desde a meia-noite do dia de serviço
CREATE OR REPLACE FUNCTION prep.gtfs_segundos(h text) RETURNS integer
LANGUAGE sql IMMUTABLE STRICT PARALLEL SAFE AS $$
    SELECT split_part(h, ':', 1)::int * 3600 + split_part(h, ':', 2)::int * 60 + split_part(h, ':', 3)::int
$$;
