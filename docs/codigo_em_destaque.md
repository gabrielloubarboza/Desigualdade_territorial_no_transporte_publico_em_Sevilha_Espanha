# Código en destaque

Fragmentos reales del proyecto, extraídos automáticamente por [`scripts/19_codigo_em_destaque.py`](../scripts/19_codigo_em_destaque.py). Cada título enlaza al archivo completo y al rango de líneas. Los comentarios del código están en portugués (idioma de trabajo del proyecto).

## Índice

- **PostgreSQL y SQL**: Estructura del banco: esquemas y horarios GTFS sin pérdida · Importación del GTFS con COPY · Calendario: servicios activos el día de referencia · Deduplicación: un viaje cuenta una vez por origen y franja · Indicadores de oferta por sección
- **PostGIS**: Preparación de las secciones censales · Intersección malla IECA × secciones · Reparto de población por área habitable · Conexión a la red sin cruzar barreras · Exportación de resultados espaciales
- **Python**: Descarga reproducible e idempotente · Inspección del GTFS: stop_sequence como distancia · Red peatonal OpenStreetMap · Distancias caminables limitadas a 400 m · Interpolación temporal por distancia · Salidas programadas: sin la última parada · Análisis de sensibilidad a la interpolación · Pruebas con recálculo independiente · Automatización por etapa
- **Diagnóstico territorial**: Umbrales explícitos y reproducibles · Tipología A–D con precedencia sin ambigüedad · Ranking por criterios lexicográficos · Consulta de las secciones prioritarias

## PostgreSQL y SQL

### Estructura del banco: esquemas y horarios GTFS sin pérdida

Los horarios GTFS pueden superar las 24:00:00, así que se guardan como texto y se convierten a segundos del día de servicio con una función SQL inmutable.

Archivo: [`sql/01_schemas_fonte.sql`](../sql/01_schemas_fonte.sql#L74-L100) (líneas 74–100)

```sql
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
```

### Importación del GTFS con COPY

Carga cada archivo del feed con `COPY ... FROM STDIN`, usando la cabecera real del archivo como lista de columnas (las claves foráneas validan la integridad durante la carga).

Archivo: [`scripts/04_carregar_banco.py`](../scripts/04_carregar_banco.py#L47-L66) (líneas 47–66)

```python
def carregar_gtfs(conn) -> dict:
    contagens = {}
    with conn.cursor() as cur:
        for nome in GTFS_ORDEM:
            arq = GTFS_DIR / f"{nome}.txt"
            if not arq.exists():
                print(f"  {nome}.txt ausente no feed (opcional)")
                continue
            dados = arq.read_bytes()
            if dados.startswith(b"\xef\xbb\xbf"):
                dados = dados[3:]
            cabecalho = next(csv.reader([dados.split(b"\n", 1)[0].decode("utf-8").strip()]))
            cols = ", ".join(c.strip() for c in cabecalho)
            with cur.copy(f"COPY fonte.gtfs_{nome} ({cols}) FROM STDIN WITH (FORMAT csv, HEADER true)") as cp:
                cp.write(dados)
            cur.execute(f"SELECT count(*) FROM fonte.gtfs_{nome}")
            contagens[nome] = cur.fetchone()[0]
            print(f"  fonte.gtfs_{nome}: {contagens[nome]}")
    conn.commit()
    return contagens
```

### Calendario: servicios activos el día de referencia

Relaciona `calendar` y `calendar_dates` con la fecha de referencia; el día de la semana indexa un array de columnas.

Archivo: [`sql/03_prep.sql`](../sql/03_prep.sql#L114-L126) (líneas 114–126)

```sql
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
```

### Deduplicación: un viaje cuenta una vez por origen y franja

Un mismo viaje puede pasar por varias paradas accesibles; una ventana `row_number()` conserva solo el embarque de menor caminata y registra en cuántas paradas era accesible.

Archivo: [`sql/10_oferta_origem.sql`](../sql/10_oferta_origem.sql#L14-L28) (líneas 14–28)

```sql
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
```

### Indicadores de oferta por sección

Medias ponderadas por población (no sumas de salidas entre orígenes) y poblaciones por situación de oferta.

Archivo: [`sql/11_oferta_agregacao.sql`](../sql/11_oferta_agregacao.sql#L10-L31) (líneas 10–31)

```sql
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
```

## PostGIS

### Preparación de las secciones censales

Comprueba la validez de las geometrías originales del INE, corrige solo si es necesario y calcula el área en EPSG:25830.

Archivo: [`sql/03_prep.sql`](../sql/03_prep.sql#L10-L18) (líneas 10–18)

```sql
CREATE TABLE prep.secciones AS
SELECT s.cusec, s.cumun, s.cdis, s.csec, s.cudis, s.nmun,
       ST_IsValid(s.geom) AS geom_valida_original,
       ST_Multi(CASE WHEN ST_IsValid(s.geom) THEN s.geom
                     ELSE ST_CollectionExtract(ST_MakeValid(s.geom), 3) END)::geometry(MultiPolygon, 25830) AS geom
FROM fonte.ine_secciones_2024 s;
ALTER TABLE prep.secciones ADD PRIMARY KEY (cusec);
ALTER TABLE prep.secciones ADD COLUMN area_m2 double precision, ADD COLUMN area_km2 double precision;
UPDATE prep.secciones SET area_m2 = ST_Area(geom), area_km2 = ST_Area(geom) / 1e6;
```

### Intersección malla IECA × secciones

Área de cada intersección celda–sección, base para repartir la población de las celdas que cruzan límites.

Archivo: [`sql/03_prep.sql`](../sql/03_prep.sql#L77-L83) (líneas 77–83)

```sql
CREATE TABLE prep.grid_seccion_intersecao AS
SELECT g.gidmp, s.cusec,
       ST_Area(ST_Intersection(g.geom, s.geom))                AS area_intersecao_m2,
       ST_Area(ST_Intersection(g.geom, s.geom)) / g.area_m2    AS frac_celda
FROM prep.grid_250 g
JOIN prep.secciones s ON ST_Intersects(g.geom, s.geom)
WHERE ST_Area(ST_Intersection(g.geom, s.geom)) > 0;
```

### Reparto de población por área habitable

La población de cada celda se reparte entre secciones según el área fuera de agua, parques y suelo ferroviario; las celdas compartidas con otros municipios solo aportan su cuota de Sevilla.

Archivo: [`sql/06_analise_demanda.sql`](../sql/06_analise_demanda.sql#L62-L72) (líneas 62–72)

```sql
SELECT w.gidmp || '_' || w.cusec AS origem_id,
       w.gidmp, w.grd_fixid, w.cusec, w.cmun,
       w.pob_tot AS pob_celda, w.cota_municipio,
       w.area_intersecao_m2 AS area_parcela_m2, w.area_hab_parcela_m2, w.frac_celda,
       (w.soma_hab = 0) AS sem_area_habitavel,
       CASE WHEN w.soma_hab > 0 THEN w.area_hab_parcela_m2 / w.soma_hab
            ELSE w.area_intersecao_m2 / w.soma_area END AS peso_parcela,
       w.pob_tot * w.cota_municipio *
           CASE WHEN w.soma_hab > 0 THEN w.area_hab_parcela_m2 / w.soma_hab
                ELSE w.area_intersecao_m2 / w.soma_area END AS pob_estimada,
       w.pob_tot * w.cota_municipio_area_total * w.area_intersecao_m2 / w.soma_area AS pob_estimada_area_total,
```

### Conexión a la red sin cruzar barreras

Las conexiones punto→calle candidatas se descartan si atraviesan agua, ferrocarril o autovía a nivel.

Archivo: [`sql/07_analise_ligacoes.sql`](../sql/07_analise_ligacoes.sql#L48-L54) (líneas 48–54)

```sql
    val AS (
        SELECT c.* FROM cand c
        WHERE NOT EXISTS (
            SELECT 1 FROM analise.barreiras b
            WHERE ST_Intersects(b.geom, c.lig)
              AND CASE WHEN ST_Dimension(b.geom) = 2 THEN ST_Length(ST_Intersection(b.geom, c.lig)) > 1.0
                       ELSE ST_Crosses(b.geom, c.lig) END)
```

### Exportación de resultados espaciales

Lectura de vistas PostGIS y escritura en GeoPackage, convirtiendo booleanos con nulos a un tipo booleano anulable.

Archivo: [`scripts/16_geopackages_finales.py`](../scripts/16_geopackages_finales.py#L164-L170) (líneas 164–170)

```python
                g = gpd.read_postgis(text(q), c, geom_col="geom")
                for col in g.columns:   # booleanos con nulos: tipo booleano anulable (no texto 'True'/'False')
                    if g[col].dtype == object and set(g[col].dropna().unique()) <= {True, False} and g[col].notna().any():
                        g[col] = g[col].astype("boolean")
                if capa == "distritos":
                    g.insert(1, "nombre", g.cdis.map(DISTRITOS))
                g.to_file(destino, layer=capa, driver="GPKG")
```

## Python

### Descarga reproducible e idempotente

Evita volver a descargar archivos idénticos (md5, tamaño o Last-Modified + hash) y registra cada fuente en el manifiesto.

Archivo: [`scripts/comum.py`](../scripts/comum.py#L50-L93) (líneas 50–93)

```python
def baixar(url: str, destino: Path, md5_esperado: str | None = None, forcar: bool = False) -> dict:
    """Baixa `url` para `destino`, evitando novo download de arquivo idêntico.

    Critério para pular: arquivo local existente com md5 igual ao esperado ou, sem md5 esperado,
    tamanho igual ao Content-Length informado pelo servidor.
    """
    destino.parent.mkdir(parents=True, exist_ok=True)
    s = sessao()
    cab = None
    for tentativa in range(3):
        try:
            cab = s.head(url, allow_redirects=True, timeout=60)
            break
        except requests.RequestException as erro:
            print(f"  aviso: HEAD {url} falhou ({type(erro).__name__}), tentativa {tentativa + 1}/3")
    if cab is None:
        if destino.exists() and not forcar:
            print(f"  servidor indisponível; mantida a cópia local {destino.name}")
            return {"url": url, "acao": "mantido (servidor indisponivel)",
                    "arquivo": str(destino.relative_to(RAIZ)).replace("\\", "/"),
                    "tamanho_bytes": destino.stat().st_size, "md5": hash_arquivo(destino, "md5"),
                    "sha256": hash_arquivo(destino)}
        raise RuntimeError(f"Não foi possível acessar {url}")
    info = {
        "url": url,
        "http_status_head": cab.status_code,
        "last_modified": cab.headers.get("Last-Modified"),
        "content_length": int(cab.headers["Content-Length"]) if "Content-Length" in cab.headers else None,
        "etag": cab.headers.get("ETag"),
    }
    if destino.exists() and not forcar:
        rel = str(destino.relative_to(RAIZ)).replace("\\", "/")
        anterior = {}
        if MANIFESTO.exists():
            anterior = next((v for v in json.loads(MANIFESTO.read_text(encoding="utf-8")).values()
                             if v.get("arquivo") == rel), {})
        if md5_esperado and hash_arquivo(destino, "md5") == md5_esperado:
            info["acao"] = "mantido (md5 identico)"
        elif not md5_esperado and info["content_length"] == destino.stat().st_size:
            info["acao"] = "mantido (tamanho identico)"
        elif (info["content_length"] is None and info["last_modified"]
              and info["last_modified"] == anterior.get("last_modified")
              and anterior.get("sha256") == hash_arquivo(destino)):
            info["acao"] = "mantido (Last-Modified e hash identicos)"
```

### Inspección del GTFS: stop_sequence como distancia

Comprueba que `stop_sequence` es la distancia acumulada en metros (base de la interpolación de horarios).

Archivo: [`scripts/02_inspecionar_gtfs.py`](../scripts/02_inspecionar_gtfs.py#L120-L133) (líneas 120–133)

```python
    # stop_sequence como distância acumulada (m): razão com distância euclidiana entre paradas consecutivas
    gp = gpd.GeoDataFrame(sp, geometry=gpd.points_from_xy(lon, lat), crs=4326).to_crs(CFG["projeto"]["crs_metrico"])
    xy = pd.DataFrame({"stop_id": gp.stop_id, "x": gp.geometry.x, "y": gp.geometry.y})
    s2 = st[["trip_id", "stop_id", "seq"]].merge(xy, on="stop_id", how="left")
    gg = s2.groupby("trip_id", sort=False)
    de = np.hypot(gg.x.diff(), gg.y.diff())
    dseq = gg.seq.diff()
    ok = de > 0
    razao = dseq[ok] / de[ok]
    res["stop_sequence_como_distancia"] = {
        "razao_dseq_euclid": razao.describe(percentiles=[.01, .05, .5, .95, .99]).round(3).to_dict(),
        "pct_razao_menor_0_95": round(100 * (razao < 0.95).mean(), 3),
        "velocidade_kmh_entre_pontos_controle": vel.describe(percentiles=[.01, .5, .99]).round(2).to_dict(),
        "trechos_velocidade_acima_60kmh": int((vel > 60).sum()),
```

### Red peatonal OpenStreetMap

Descarga con OSMnx conservando componentes desconectados (no se unen artificialmente) y los identifica con NetworkX.

Archivo: [`scripts/03_rede_osm.py`](../scripts/03_rede_osm.py#L53-L61) (líneas 53–61)

```python
    G = ox.graph_from_polygon(area_4326, network_type=CFG["osm"]["network_type"], simplify=True,
                              retain_all=True, truncate_by_edge=True)
    print(f"Grafo bruto: {G.number_of_nodes()} nós, {G.number_of_edges()} arestas (dirigido)")

    Gp = ox.project_graph(G, to_crs=f"EPSG:{CRS}")
    Gu = ox.convert.to_undirected(Gp)
    comps = sorted(nx.connected_components(Gu), key=len, reverse=True)
    comp_id = {n: i for i, c in enumerate(comps) for n in c}
    nx.set_node_attributes(Gu, comp_id, "componente")
```

### Distancias caminables limitadas a 400 m

Un Dijkstra acotado por conexión de parada; las conexiones de origen y parada se suman fuera del grafo para no crear pasos entre componentes.

Archivo: [`scripts/rede_acessibilidade.py`](../scripts/rede_acessibilidade.py#L75-L88) (líneas 75–88)

```python
    # 1) Pares origem-parada até o limite: uma busca limitada por ligação de parada
    pares = {}
    for lid_p, sid, _, _, dp in lig_p:
        if dp > limite_m:
            continue
        alcance = nx.single_source_dijkstra_path_length(G, no_lig[("p", lid_p)], cutoff=limite_m - dp, weight="w")
        for no, drede in alcance.items():
            for lid_o, oid, do in origens_no_.get(no, ()):
                total = dp + drede + do
                if total <= limite_m + tol:
                    chave = (oid, sid)
                    cand = (total, lid_o, lid_p, drede, do, dp)
                    if chave not in pares or cand < pares[chave]:
                        pares[chave] = cand
```

### Interpolación temporal por distancia

Horario en las paradas sin hora explícita, interpolado entre los puntos de control anterior y siguiente.

Archivo: [`sql/03_prep.sql`](../sql/03_prep.sql#L144-L167) (líneas 144–167)

```sql
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
```

### Salidas programadas: sin la última parada

En la última parada de cada viaje no se puede embarcar, así que no cuenta como salida.

Archivo: [`sql/09_oferta_partidas.sql`](../sql/09_oferta_partidas.sql#L13-L25) (líneas 13–25)

```sql
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
```

### Análisis de sensibilidad a la interpolación

Escenarios ±2 min y envolventes entre puntos de control, solo para los horarios interpolados.

Archivo: [`sql/12_oferta_sensibilidade.sql`](../sql/12_oferta_sensibilidade.sql#L22-L31) (líneas 22–31)

```sql
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
```

### Pruebas con recálculo independiente

Las pruebas recalculan en pandas, sin usar las tablas de la etapa, las líneas y viajes de todos los orígenes.

Archivo: [`scripts/11_testes_etapa3.py`](../scripts/11_testes_etapa3.py#L46-L61) (líneas 46–61)

```python
def recalculo_independente(conn):
    """Contagens por origem e período sem usar as tabelas da Etapa 3."""
    h = df(conn, "SELECT trip_id, stop_id, dist_m, partida_s FROM prep.gtfs_horarios_dia")
    v = df(conn, "SELECT trip_id, route_id, direction_id FROM prep.gtfs_viagens_dia")
    op = df(conn, "SELECT origem_id, stop_id, distancia_m FROM analise.origem_parada_400m")
    h = h[h.dist_m < h.groupby("trip_id").dist_m.transform("max")]          # sem a última parada
    h = h.merge(v, on="trip_id")
    linhas = []
    for nome, (ini, fim) in CFG["gtfs"]["periodos"].items():
        x = h[(h.partida_s >= seg(ini)) & (h.partida_s < seg(fim))]
        j = op.merge(x, on="stop_id")
        g = j.groupby("origem_id").agg(n_viagens=("trip_id", "nunique"), n_linhas=("route_id", "nunique"))
        g["n_linha_sentido"] = j.drop_duplicates(["origem_id", "route_id", "direction_id"]).groupby("origem_id").size()
        g["periodo"] = nome
        linhas.append(g.reset_index())
    return pd.concat(linhas)
```

### Automatización por etapa

Cada etapa se reconstruye con un script de PowerShell que detiene la ejecución ante cualquier fallo.

Archivo: [`scripts/executar_etapa4.ps1`](../scripts/executar_etapa4.ps1#L8-L18) (líneas 8–18)

```powershell
$passos = @(
    "scripts\13_diagnostico.py",
    "scripts\14_testes_etapa4.py",
    "scripts\15_exportar_etapa4.py"
)
foreach ($p in $passos) {
    Write-Host "==> $p" -ForegroundColor Cyan
    & $py $p
    if ($LASTEXITCODE -ne 0) { throw "Falha em $p (codigo $LASTEXITCODE)" }
}
Write-Host "Etapa 4 concluida." -ForegroundColor Green
```

## Diagnóstico territorial

### Umbrales explícitos y reproducibles

Percentiles de la distribución municipal (y la cobertura media) calculados en SQL para dos escenarios.

Archivo: [`sql/13_diagnostico_classificacao.sql`](../sql/13_diagnostico_classificacao.sql#L68-L72) (líneas 68–72)

```sql
    SELECT c.cenario, 'alta_densidade' AS criterio, 'densidade_ine_hab_km2' AS variavel, '>=' AS operador,
           format('P%s das 521 seções (percentile_cont)', round(100 * c.p_alta, 1)) AS regra,
           (SELECT count(*) FROM analise.diag_base) AS n_universo,
           (SELECT percentile_cont(c.p_alta) WITHIN GROUP (ORDER BY densidade_ine_hab_km2) FROM analise.diag_base) AS valor
    FROM cen c
```

### Tipología A–D con precedencia sin ambigüedad

Cada sección recibe una sola categoría; las deficiencias se conservan también como indicadores binarios.

Archivo: [`sql/13_diagnostico_classificacao.sql`](../sql/13_diagnostico_classificacao.sql#L134-L141) (líneas 134–141)

```sql
       CASE WHEN NOT alta_densidade        THEN 'fora_alta_densidade'
            WHEN informacao_incompleta     THEN 'alta_densidade_informacao_incompleta'
            WHEN n_deficiencias >= 2       THEN 'D_deficiencias_combinadas'
            WHEN baixa_cobertura           THEN 'A_baixa_cobertura'
            WHEN baixa_diversidade_linhas  THEN 'B_baixa_diversidade_linhas'
            WHEN baixa_frequencia          THEN 'C_baixa_frequencia'
            ELSE 'alta_densidade_sem_deficiencia' END AS tipologia,
       (alta_densidade AND NOT informacao_incompleta AND n_deficiencias > 0) AS prioritaria
```

### Ranking por criterios lexicográficos

Sin puntuación compuesta: dimensiones deficientes, población sin oferta, frecuencia, líneas, densidad y código.

Archivo: [`sql/13_diagnostico_classificacao.sql`](../sql/13_diagnostico_classificacao.sql#L160-L167) (líneas 160–167)

```sql
UPDATE analise.diag_classificacao c SET ranking = r.rk, ranking_ordem_inicial = r.rk0
FROM (SELECT cenario, cusec,
             row_number() OVER (PARTITION BY cenario ORDER BY n_dimensoes DESC, pob_sem_oferta_manha DESC,
                                partidas_h_manha, linhas_manha, densidade_ine_hab_km2 DESC, cusec) AS rk,
             row_number() OVER (PARTITION BY cenario ORDER BY n_deficiencias DESC, pob_sem_oferta_manha DESC,
                                partidas_h_manha, linhas_manha, densidade_ine_hab_km2 DESC, cusec) AS rk0
      FROM analise.diag_classificacao WHERE prioritaria) r
WHERE r.cenario = c.cenario AND r.cusec = c.cusec;
```

### Consulta de las secciones prioritarias

Vista espacial para QGIS y consulta usada en la exportación del ranking.

Archivo: [`scripts/15_exportar_etapa4.py`](../scripts/15_exportar_etapa4.py#L22-L27) (líneas 22–27)

```python
    "ranking_prioritarias.csv": """
        SELECT ranking, cusec, cdis, tipologia, deficiencias, n_dimensoes, pob_ine, densidade_ine_hab_km2, pob_grade,
               pct_coberta_400m, pob_sem_cobertura, pob_sem_oferta_manha, linhas_manha, linhas_cob_manha,
               partidas_h_manha, partidas_h_cob_manha, partidas_h_tarde, padrao_temporal, pct_pob_perto_limiar_400m,
               razao_grade_ine, ranking_ordem_inicial, prioritaria_tercis, ranking_tercis
        FROM analise.diag_resultado_seccion WHERE prioritaria ORDER BY ranking""",
```
