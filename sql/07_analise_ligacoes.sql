-- =====================================================================================
-- 07_analise_ligacoes.sql — Etapa 2: paradas de destino e ligações de origens/paradas à rede
-- Depende de analise.rede_componentes (componentes da rede utilizável; 0 = principal).
--
-- Regra de ligação (igual para origens e paradas, com raios distintos):
--   1. candidatas: as `candidatos_knn` arestas utilizáveis mais próximas dentro do raio;
--   2. a ligação (segmento mais curto ponto -> aresta) não pode atravessar água, ferrovia ou via expressa
--      em nível (analise.barreiras); pontes e túneis não bloqueiam;
--   3. ligação primária = candidata válida mais próxima (empate: menor aresta_id);
--   4. se a primária cair em componente isolado, acrescenta-se a candidata válida mais próxima do
--      componente principal, se estiver a até `raio_ligacao_secundaria_origem_m` / `_parada_m`.
-- Ligações são de mão única (origem -> rede, rede -> parada): não criam passagem entre componentes.
-- =====================================================================================

-- ------------------------------------------------------------------ Paradas e papel na análise
DROP TABLE IF EXISTS analise.paradas_analise CASCADE;
CREATE TABLE analise.paradas_analise AS
SELECT p.stop_id, p.stop_name, p.serve_onibus, p.serve_bonde, p.serve_onibus_dia_ref, p.dentro_municipio,
       CASE WHEN p.serve_onibus_dia_ref THEN 'onibus_com_servico_no_dia'
            WHEN p.serve_onibus THEN 'onibus_sem_servico_no_dia'
            WHEN p.serve_bonde THEN 'somente_bonde'
            ELSE 'sem_viagens' END AS categoria,
       q.situacao AS situacao_ide, p.geom
FROM prep.gtfs_paradas p
LEFT JOIN qa.paradas_gtfs_ide q ON q.id = p.stop_id;
ALTER TABLE analise.paradas_analise ADD PRIMARY KEY (stop_id);
CREATE INDEX ON analise.paradas_analise USING gist (geom);

-- ------------------------------------------------------------------ Ligações genéricas
CREATE OR REPLACE FUNCTION analise.ligacoes_rede(tabela regclass, col_id text, filtro text,
                                                 raio double precision, raio_sec double precision, k integer)
RETURNS TABLE (obj_id text, tipo text, aresta_id integer, componente integer, distancia_m double precision,
               pos_na_aresta_m double precision, geom geometry(LineString, 25830))
LANGUAGE plpgsql STABLE AS $f$
BEGIN
RETURN QUERY EXECUTE format($q$
    WITH o AS (SELECT %2$I::text AS obj_id, geom FROM %1$s WHERE %3$s),
    cand AS (
        SELECT o.obj_id, r.aresta_id, rc.componente, ST_Distance(o.geom, r.geom) AS d,
               ST_ShortestLine(o.geom, r.geom) AS lig, r.geom AS geom_aresta, r.comprimento_m, r.no_inicio_geom, r.no_origem
        FROM o
        CROSS JOIN LATERAL (
            SELECT a.aresta_id, a.geom, a.comprimento_m, a.no_inicio_geom, a.no_origem FROM analise.rede_arestas a
            WHERE a.utilizavel AND ST_DWithin(a.geom, o.geom, %4$s)
            ORDER BY a.geom <-> o.geom LIMIT %6$s) r
        JOIN analise.rede_componentes rc ON rc.no_id = r.no_origem
    ),
    val AS (
        SELECT c.* FROM cand c
        WHERE NOT EXISTS (
            SELECT 1 FROM analise.barreiras b
            WHERE ST_Intersects(b.geom, c.lig)
              AND CASE WHEN ST_Dimension(b.geom) = 2 THEN ST_Length(ST_Intersection(b.geom, c.lig)) > 1.0
                       ELSE ST_Crosses(b.geom, c.lig) END)
    ),
    prim AS (SELECT DISTINCT ON (obj_id) 'primaria'::text AS tipo, * FROM val ORDER BY obj_id, d, aresta_id),
    sec AS (
        SELECT DISTINCT ON (v.obj_id) 'secundaria_componente_principal'::text AS tipo, v.*
        FROM val v JOIN prim p USING (obj_id)
        WHERE p.componente <> 0 AND v.componente = 0 AND v.d <= %5$s
        ORDER BY v.obj_id, v.d, v.aresta_id
    ),
    todas AS (SELECT * FROM prim UNION ALL SELECT * FROM sec)
    SELECT obj_id, tipo, aresta_id, componente, d,
           -- posição medida a partir de no_inicio_geom (início da geometria da aresta)
           ST_LineLocatePoint(geom_aresta, ST_EndPoint(lig)) * comprimento_m,
           lig::geometry(LineString, 25830)
    FROM todas
$q$, tabela, col_id, filtro, raio, raio_sec, k);
END $f$;

DROP TABLE IF EXISTS analise.ligacoes_origem CASCADE;
CREATE TABLE analise.ligacoes_origem AS
SELECT row_number() OVER (ORDER BY obj_id, tipo)::int AS ligacao_id, obj_id AS origem_id, tipo, aresta_id,
       componente, distancia_m, pos_na_aresta_m, geom
FROM analise.ligacoes_rede('analise.pontos_demanda', 'origem_id', 'true',
        (SELECT valor::float FROM analise.parametros WHERE chave = 'raio_ligacao_origem_m'),
        (SELECT valor::float FROM analise.parametros WHERE chave = 'raio_ligacao_secundaria_origem_m'),
        (SELECT valor::int   FROM analise.parametros WHERE chave = 'candidatos_knn'));
ALTER TABLE analise.ligacoes_origem ADD PRIMARY KEY (ligacao_id);
CREATE UNIQUE INDEX ON analise.ligacoes_origem (origem_id, tipo);
CREATE INDEX ON analise.ligacoes_origem USING gist (geom);

DROP TABLE IF EXISTS analise.ligacoes_parada CASCADE;
CREATE TABLE analise.ligacoes_parada AS
SELECT row_number() OVER (ORDER BY obj_id, tipo)::int AS ligacao_id, obj_id AS stop_id, tipo, aresta_id,
       componente, distancia_m, pos_na_aresta_m, geom
FROM analise.ligacoes_rede('analise.paradas_analise', 'stop_id', 'serve_onibus_dia_ref',
        (SELECT valor::float FROM analise.parametros WHERE chave = 'raio_ligacao_parada_m'),
        (SELECT valor::float FROM analise.parametros WHERE chave = 'raio_ligacao_secundaria_parada_m'),
        (SELECT valor::int   FROM analise.parametros WHERE chave = 'candidatos_knn'));
ALTER TABLE analise.ligacoes_parada ADD PRIMARY KEY (ligacao_id);
CREATE UNIQUE INDEX ON analise.ligacoes_parada (stop_id, tipo);
CREATE INDEX ON analise.ligacoes_parada USING gist (geom);

-- Situação de ligação de cada parada de destino
ALTER TABLE analise.paradas_analise ADD COLUMN situacao_ligacao text, ADD COLUMN destino_analise boolean;
UPDATE analise.paradas_analise p SET
    situacao_ligacao = CASE
        WHEN NOT p.serve_onibus_dia_ref THEN 'nao_avaliada'
        WHEN l.n IS NULL THEN 'sem_ligacao'
        WHEN l.principal THEN 'ligada_componente_principal'
        ELSE 'ligada_apenas_componente_isolado' END,
    destino_analise = p.serve_onibus_dia_ref AND l.n IS NOT NULL
FROM (SELECT pa.stop_id, count(lp.*) AS n, bool_or(lp.componente = 0) AS principal
      FROM analise.paradas_analise pa LEFT JOIN analise.ligacoes_parada lp USING (stop_id)
      GROUP BY pa.stop_id HAVING count(lp.*) > 0) l
WHERE l.stop_id = p.stop_id;
UPDATE analise.paradas_analise SET
    situacao_ligacao = CASE WHEN serve_onibus_dia_ref THEN 'sem_ligacao' ELSE 'nao_avaliada' END,
    destino_analise = false
WHERE situacao_ligacao IS NULL;
