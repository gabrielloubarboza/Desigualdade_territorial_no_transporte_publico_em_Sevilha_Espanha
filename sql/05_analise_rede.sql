-- =====================================================================================
-- 05_analise_rede.sql — Etapa 2: schema `analise`, rede pedonal utilizável e barreiras
-- Depende de prep.rede_arestas (Etapa 1) e de fonte.osm_barreiras_* (carregadas por 07_acessibilidade.py).
-- Nenhuma aresta é apagada: as não utilizáveis ficam marcadas com o motivo.
-- =====================================================================================
CREATE SCHEMA IF NOT EXISTS analise;
COMMENT ON SCHEMA analise IS 'Etapa 2+: acessibilidade caminhável e indicadores (EPSG:25830)';

-- ------------------------------------------------------------------ Barreiras (para validar ligações ponto→rede)
DROP TABLE IF EXISTS analise.barreiras CASCADE;
CREATE TABLE analise.barreiras AS
-- água (rios, dársena, lagos): polígonos e cursos d'água lineares
SELECT osm_id, classe, name, geom
FROM fonte.osm_barreiras_poligonos WHERE classe = 'agua'
UNION ALL
SELECT osm_id, classe, name, geom
FROM fonte.osm_barreiras_linhas WHERE classe = 'curso_agua' AND coalesce(tunnel, '') = ''
UNION ALL
-- ferrovias e vias expressas em nível (pontes e túneis não bloqueiam a passagem por baixo/por cima)
SELECT osm_id, classe, name, geom
FROM fonte.osm_barreiras_linhas
WHERE classe IN ('ferrovia', 'via_alta_capacidade')
  AND coalesce(bridge, 'no') = 'no' AND coalesce(tunnel, 'no') = 'no';
ALTER TABLE analise.barreiras ADD COLUMN barreira_id serial PRIMARY KEY;
CREATE INDEX ON analise.barreiras USING gist (geom);

DROP TABLE IF EXISTS analise.areas_nao_residenciais CASCADE;
CREATE TABLE analise.areas_nao_residenciais AS
SELECT osm_id, classe, name, ST_Multi(ST_CollectionExtract(ST_MakeValid(geom), 3))::geometry(MultiPolygon, 25830) AS geom
FROM fonte.osm_barreiras_poligonos WHERE classe IN ('agua', 'parque', 'terreno_ferroviario')
UNION ALL
-- faixa ao longo de ferrovias e vias expressas em nível: evita ponto representativo "em cima" da barreira
SELECT osm_id, 'faixa_' || classe, name,
       ST_Multi(ST_Buffer(geom, (SELECT valor::float FROM analise.parametros WHERE chave = 'faixa_barreira_m')))
FROM analise.barreiras WHERE classe IN ('ferrovia', 'via_alta_capacidade');
CREATE INDEX ON analise.areas_nao_residenciais USING gist (geom);

-- ------------------------------------------------------------------ Rede utilizável
DROP TABLE IF EXISTS analise.rede_arestas CASCADE;
CREATE TABLE analise.rede_arestas AS
WITH a AS (
    SELECT r.*, o.sidewalk,
           coalesce(r.foot, '') IN ('yes', 'designated', 'permissive') AS pedestre_permitido_explicito
    FROM prep.rede_arestas r
    JOIN fonte.osm_arestas o ON o.u = r.no_origem AND o.v = r.no_destino AND o.key = r.key
)
SELECT a.aresta_id, a.no_origem, a.no_destino, a.highway, a.name, a.bridge, a.tunnel, a.access, a.foot, a.sidewalk,
       a.comprimento_m, a.dentro_municipio,
       CASE
         WHEN a.restricao_acesso THEN 'acesso_proibido'
         WHEN a.via_alta_capacidade AND NOT a.pedestre_permitido_explicito
              AND coalesce(a.sidewalk, '') NOT IN ('both', 'left', 'right', 'yes')
              THEN 'via_expressa_sem_passagem_pedonal'
         WHEN a.via_exclusiva_onibus AND NOT a.pedestre_permitido_explicito THEN 'via_exclusiva_onibus'
       END AS motivo_exclusao,
       a.geom
FROM a;
ALTER TABLE analise.rede_arestas ADD PRIMARY KEY (aresta_id);
-- Travessia de água sem ponte: a aresta (sem bridge/tunnel) divide um polígono de água em mais partes
-- significativas (> 500 m²) do que ele tinha — ex.: trilhas informais atravessando o leito do rio.
-- Sobreposições ao longo de margens e cais não dividem o polígono e permanecem utilizáveis.
UPDATE analise.rede_arestas a SET motivo_exclusao = 'atravessa_agua_sem_ponte'
WHERE a.motivo_exclusao IS NULL AND a.bridge IS NULL AND a.tunnel IS NULL
  AND EXISTS (
    SELECT 1 FROM analise.barreiras b
    WHERE b.classe = 'agua' AND ST_Dimension(b.geom) = 2 AND ST_Intersects(a.geom, b.geom)
      AND ST_Length(ST_Intersection(a.geom, b.geom)) > 5
      AND (SELECT count(*) FROM ST_Dump(ST_CollectionExtract(ST_Difference(b.geom, ST_Buffer(a.geom, 0.5)), 3)) d
           WHERE ST_Area(d.geom) > 500)
        > (SELECT count(*) FROM ST_Dump(b.geom) d WHERE ST_Area(d.geom) > 500));
ALTER TABLE analise.rede_arestas ADD COLUMN utilizavel boolean;
UPDATE analise.rede_arestas SET utilizavel = (motivo_exclusao IS NULL);
-- Nó em que a geometria começa (o OSMnx não direcionado pode guardar a linha no sentido v -> u)
ALTER TABLE analise.rede_arestas ADD COLUMN no_inicio_geom bigint;
UPDATE analise.rede_arestas a
SET no_inicio_geom = CASE WHEN ST_DWithin(ST_StartPoint(a.geom), nu.geom, 0.01) THEN a.no_origem
                          WHEN ST_DWithin(ST_StartPoint(a.geom), nv.geom, 0.01) THEN a.no_destino END
FROM prep.rede_nos nu, prep.rede_nos nv
WHERE nu.no_id = a.no_origem AND nv.no_id = a.no_destino;
CREATE INDEX ON analise.rede_arestas USING gist (geom) WHERE utilizavel;
CREATE INDEX ON analise.rede_arestas (no_origem);
CREATE INDEX ON analise.rede_arestas (no_destino);
COMMENT ON TABLE analise.rede_arestas IS
    'Arestas OSM da Etapa 1 com regra de uso pedonal; componente calculado sobre as utilizáveis (07_acessibilidade.py)';
