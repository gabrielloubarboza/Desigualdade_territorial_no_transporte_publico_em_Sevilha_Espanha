"""Etapa 2 — Testes de integridade da acessibilidade (OK / LIMITACAO / FALHA).

Uso:  .venv\\Scripts\\python.exe scripts\\08_testes_etapa2.py

Inclui conferência independente de uma amostra de percursos: a geometria do caminho é reconstruída
no PostGIS (ST_LineSubstring das arestas percorridas + ligações) e o comprimento geométrico é comparado
à distância calculada no grafo. Resultados em qa.resultado_testes (prefixo E) e docs/testes_etapa2.md.
"""
from __future__ import annotations

import datetime as dt
import json
import sys

import requests

import rede_acessibilidade as ra
from comum import caminho, carregar_config, conectar

CFG = carregar_config()
AC = CFG["acessibilidade"]
TOL = AC["tolerancia_m"]
RES: list[tuple] = []


def reg(tid, grupo, desc, status, det):
    RES.append((tid, grupo, desc, status, det))
    print(f"[{status:9}] {tid} {desc} — {det}")


def um(cur, q, *a):
    cur.execute(q, a)
    return cur.fetchone()


def amostra(cur):
    """Seleciona origens de contextos distintos e o par origem-parada mais próximo de cada uma."""
    cur.execute("""
    WITH r AS (SELECT * FROM analise.resultado_origem),
    centro AS (SELECT ST_Transform(ST_SetSRID(ST_MakePoint(-5.9958, 37.3890), 4326), 25830) AS g),  -- Plaza Nueva
    cat AS (
      (SELECT 'central' AS categoria, r.origem_id FROM r, centro WHERE r.situacao = 'coberto_400m'
        ORDER BY r.geom <-> centro.g LIMIT 3)
      UNION ALL
      (SELECT 'periferica', r.origem_id FROM r, centro WHERE r.situacao <> 'nao_determinado' AND r.pob_estimada > 20
        ORDER BY ST_Distance(r.geom, centro.g) DESC LIMIT 3)
      UNION ALL
      (SELECT 'proxima_rio', r.origem_id FROM r
        WHERE r.situacao = 'coberto_400m' AND EXISTS (SELECT 1 FROM analise.barreiras b WHERE b.classe = 'agua'
              AND ST_DWithin(b.geom, r.geom, 150)) ORDER BY r.pob_estimada DESC LIMIT 3)
      UNION ALL
      (SELECT 'proxima_via_expressa', r.origem_id FROM r
        WHERE r.situacao = 'coberto_400m' AND EXISTS (SELECT 1 FROM analise.barreiras b WHERE b.classe = 'via_alta_capacidade'
              AND ST_DWithin(b.geom, r.geom, 120)) ORDER BY r.pob_estimada DESC LIMIT 3)
      UNION ALL
      (SELECT 'sem_cobertura_proxima_euclidiana', r.origem_id FROM r WHERE r.situacao = 'sem_cobertura_400m'
        ORDER BY r.dist_euclidiana_parada_mais_proxima_m LIMIT 3)
    )
    SELECT DISTINCT ON (c.origem_id) c.categoria, c.origem_id, p.stop_id, p.distancia_m, p.ligacao_origem_id, p.ligacao_parada_id
    FROM cat c
    JOIN LATERAL (
        SELECT op.stop_id, op.distancia_m, op.ligacao_origem_id, op.ligacao_parada_id
        FROM analise.origem_parada_400m op WHERE op.origem_id = c.origem_id
        UNION ALL
        SELECT pm.stop_id, pm.distancia_m, pm.ligacao_origem_id, pm.ligacao_parada_id
        FROM analise.parada_mais_proxima pm WHERE pm.origem_id = c.origem_id
        ORDER BY 2, 1 LIMIT 1) p ON true
    ORDER BY c.origem_id""")
    return cur.fetchall()


def conferir_amostra(conn, cur):
    res = ra.calcular(conn, AC["limite_m"], AC["limite_distancia_mais_proxima_m"], TOL)
    linhas = []
    for cat, oid, sid, dist, lo, lp in amostra(cur):
        segs = ra.segmentos_do_caminho(res, lo, lp)
        linhas.append((cat, oid, sid, dist, lo, lp, json.dumps(segs)))
    cur.execute("DROP TABLE IF EXISTS qa.amostra_percursos")
    cur.execute("""CREATE TABLE qa.amostra_percursos (
        categoria text, origem_id text, stop_id text, distancia_calculada_m double precision,
        ligacao_origem_id int, ligacao_parada_id int, segmentos jsonb,
        comprimento_geometrico_m double precision, cruza_agua_sem_ponte boolean, cruza_ferrovia_em_nivel boolean,
        geom geometry(MultiLineString, 25830), PRIMARY KEY (origem_id, stop_id))""")
    cur.executemany("INSERT INTO qa.amostra_percursos (categoria, origem_id, stop_id, distancia_calculada_m, "
                    "ligacao_origem_id, ligacao_parada_id, segmentos) VALUES (%s,%s,%s,%s,%s,%s,%s)", linhas)
    cur.execute("""
    WITH s AS (
        SELECT a.origem_id, a.stop_id, (e->>0)::int AS aresta_id, (e->>1)::float AS p1, (e->>2)::float AS p2
        FROM qa.amostra_percursos a, jsonb_array_elements(a.segmentos) e),
    g AS (
        SELECT s.origem_id, s.stop_id, r.bridge, r.tunnel,
               ST_LineSubstring(r.geom, least(s.p1, s.p2) / r.comprimento_m, greatest(s.p1, s.p2) / r.comprimento_m) AS geom
        FROM s JOIN analise.rede_arestas r USING (aresta_id)),
    tudo AS (
        SELECT origem_id, stop_id, geom, bridge, tunnel FROM g
        UNION ALL SELECT a.origem_id, a.stop_id, l.geom, NULL, NULL FROM qa.amostra_percursos a
                  JOIN analise.ligacoes_origem l ON l.ligacao_id = a.ligacao_origem_id
        UNION ALL SELECT a.origem_id, a.stop_id, l.geom, NULL, NULL FROM qa.amostra_percursos a
                  JOIN analise.ligacoes_parada l ON l.ligacao_id = a.ligacao_parada_id),
    agg AS (
        SELECT t.origem_id, t.stop_id, sum(ST_Length(t.geom)) AS comp, ST_Multi(ST_Collect(t.geom)) AS geom,
               bool_or(t.bridge IS NULL AND EXISTS (SELECT 1 FROM analise.barreiras b WHERE b.classe = 'agua'
                       AND ST_Dimension(b.geom) = 2 AND ST_Length(ST_Intersection(b.geom, t.geom)) > 5)) AS agua,
               bool_or(t.bridge IS NULL AND t.tunnel IS NULL AND EXISTS (SELECT 1 FROM analise.barreiras b
                       WHERE b.classe = 'ferrovia' AND ST_Crosses(b.geom, t.geom))) AS ferrovia
        FROM tudo t GROUP BY 1, 2)
    UPDATE qa.amostra_percursos a SET comprimento_geometrico_m = agg.comp, cruza_agua_sem_ponte = agg.agua,
           cruza_ferrovia_em_nivel = agg.ferrovia, geom = agg.geom
    FROM agg WHERE agg.origem_id = a.origem_id AND agg.stop_id = a.stop_id""")
    conn.commit()
    return res


def testes(conn, cur):
    lim = AC["limite_m"]
    # E01 — preservação de identificadores e população
    r = um(cur, """
      WITH c AS (SELECT gidmp, max(pob_celda) pob, max(cota_municipio) cota, sum(pob_estimada) soma, count(*) n
                 FROM analise.parcelas_demanda GROUP BY gidmp)
      SELECT (SELECT count(*) FROM prep.grid_250), count(*),
             max(abs(soma - pob * cota)), count(*) FILTER (WHERE cota = 1 AND abs(soma - pob) > 1e-6),
             (SELECT count(*) FROM analise.parcelas_demanda d JOIN fonte.ieca_gridp_250 f USING (gidmp) WHERE d.grd_fixid <> f.grd_fixid),
             (SELECT sum(pob_tot) FROM prep.grid_250 WHERE cmun = '41091'),
             sum(soma) FILTER (WHERE cota = 1),
             (SELECT sum(pob_estimada) FROM analise.parcelas_demanda),
             (SELECT sum(pob_estimada) FROM analise.pontos_demanda)
      FROM c""")
    ok = r[0] == r[1] and r[2] < 1e-6 and r[3] == 0 and r[4] == 0 and abs(r[5] - r[6]) < 1e-6 and abs(r[7] - r[8]) < 1e-6
    reg("E01", "Demanda", "Identificadores e população de origem preservados", "OK" if ok else "FALHA",
        f"{r[1]} de {r[0]} células representadas; células só de Sevilla: soma {r[6]:.2f} = publicada {r[5]}; "
        f"desvio máx. célula x (pob_tot·cota) {r[2]:.2e}; grd_fixid divergentes {r[4]}; parcelas {r[7]:.2f} = pontos {r[8]:.2f}")

    # E02 — duplicação
    r = um(cur, """SELECT (SELECT count(*) - count(DISTINCT (gidmp, cusec)) FROM analise.parcelas_demanda),
                          (SELECT max(abs(s - 1)) FROM (SELECT sum(peso_parcela) s FROM analise.parcelas_demanda GROUP BY gidmp) x),
                          (SELECT count(*) - count(DISTINCT origem_id) FROM analise.pontos_demanda),
                          (SELECT count(*) FROM analise.parcelas_demanda WHERE cota_municipio > 1 OR peso_parcela > 1)""")
    reg("E02", "Demanda", "Sem duplicação de células/parcelas entre seções", "OK" if r[0] == 0 and r[1] < 1e-9 and r[2] == 0 and r[3] == 0 else "FALHA",
        f"pares célula-seção duplicados {r[0]}; desvio máx. da soma dos pesos por célula {r[1]:.1e}; origens duplicadas {r[2]}")

    # E03 — pontos x seções
    r = um(cur, """SELECT count(*), count(*) FILTER (WHERE NOT ST_Intersects(p.geom, s.geom)),
                          count(*) FILTER (WHERE NOT ST_Intersects(p.geom, d.geom_habitavel)),
                          (SELECT count(*) FROM prep.secciones x WHERE NOT EXISTS (SELECT 1 FROM analise.pontos_demanda y WHERE y.cusec = x.cusec))
                   FROM analise.pontos_demanda p JOIN prep.secciones s USING (cusec) JOIN analise.parcelas_demanda d USING (origem_id)""")
    reg("E03", "Demanda", "Pontos de demanda dentro da seção e da parcela que representam", "OK" if r[1] == 0 and r[2] == 0 else "FALHA",
        f"{r[0]} pontos; fora da seção {r[1]}; fora da parte habitável da parcela {r[2]}; seções sem ponto {r[3]}")

    # E04 — ligações das paradas
    r = um(cur, """SELECT count(*) FILTER (WHERE p.serve_onibus_dia_ref), count(*) FILTER (WHERE p.destino_analise),
                          (SELECT max(distancia_m) FROM analise.ligacoes_parada),
                          (SELECT count(*) FROM analise.ligacoes_parada l JOIN analise.paradas_analise s USING (stop_id)
                            WHERE ST_Distance(ST_StartPoint(l.geom), s.geom) > 1e-6),
                          (SELECT count(*) FROM analise.ligacoes_parada l JOIN analise.rede_arestas a USING (aresta_id)
                            WHERE NOT a.utilizavel OR ST_Distance(ST_EndPoint(l.geom), a.geom) > 1e-6),
                          string_agg(p.stop_id || ':' || p.situacao_ligacao, ', ') FILTER (WHERE p.situacao_ligacao NOT IN ('ligada_componente_principal', 'nao_avaliada'))
                   FROM analise.paradas_analise p""")
    reg("E04", "Paradas", "Ligações das paradas espacialmente coerentes",
        "OK" if r[3] == 0 and r[4] == 0 and r[0] == r[1] else "FALHA",
        f"{r[1]} de {r[0]} paradas com serviço ligadas; ligação máx. {r[2]:.1f} m; ligação fora da parada/aresta: {r[3]}/{r[4]}; "
        f"fora do componente principal: {r[5]}")

    # E05 — barreiras
    r = um(cur, """WITH l AS (SELECT geom FROM analise.ligacoes_origem UNION ALL SELECT geom FROM analise.ligacoes_parada)
                   SELECT count(*) FILTER (WHERE EXISTS (SELECT 1 FROM analise.barreiras b WHERE ST_Intersects(b.geom, l.geom)
                          AND CASE WHEN ST_Dimension(b.geom) = 2 THEN ST_Length(ST_Intersection(b.geom, l.geom)) > 1
                                   ELSE ST_Crosses(b.geom, l.geom) END)), count(*) FROM l""")
    agua = um(cur, """WITH x AS (
                          SELECT a.aresta_id, a.componente, coalesce(b.name, '(sem nome)') AS agua,
                                 ST_Length(ST_Intersection(a.geom, b.geom)) AS m
                          FROM analise.rede_arestas a JOIN analise.barreiras b ON b.classe = 'agua' AND ST_Dimension(b.geom) = 2
                               AND ST_Intersects(a.geom, b.geom)
                          WHERE a.utilizavel AND a.bridge IS NULL AND a.tunnel IS NULL)
                      SELECT count(*), coalesce(round(sum(m)), 0),
                             (SELECT count(*) FROM analise.rede_arestas a JOIN analise.barreiras b ON b.classe = 'agua'
                                AND ST_Dimension(b.geom) = 2 AND ST_Intersects(a.geom, b.geom)
                              WHERE a.utilizavel AND a.bridge IS NULL AND a.tunnel IS NULL
                                AND (SELECT count(*) FROM ST_Dump(ST_CollectionExtract(ST_Difference(b.geom, ST_Buffer(a.geom, 0.5)), 3)) d
                                     WHERE ST_Area(d.geom) > 500) > (SELECT count(*) FROM ST_Dump(b.geom) d WHERE ST_Area(d.geom) > 500)),
                             (SELECT string_agg(agua || ': ' || n, '; ') FROM (SELECT agua, count(*) n FROM x WHERE m > 5
                              GROUP BY agua ORDER BY 2 DESC) y),
                             (SELECT count(*) FROM analise.rede_arestas WHERE motivo_exclusao = 'atravessa_agua_sem_ponte')
                      FROM x WHERE m > 5""")
    am = um(cur, "SELECT count(*), count(*) FILTER (WHERE cruza_agua_sem_ponte), count(*) FILTER (WHERE cruza_ferrovia_em_nivel) FROM qa.amostra_percursos")
    status = "FALHA" if r[0] > 0 or am[1] > 0 or agua[2] > 0 else ("LIMITACAO" if agua[0] > 0 else "OK")
    reg("E05", "Rede", "Nenhuma ligação artificial através de barreiras", status,
        f"ligações que cruzam barreira: {r[0]} de {r[1]}; ligações de mão única fora do grafo (sem passagem entre componentes); "
        f"arestas excluídas por atravessar água sem ponte: {agua[4]}; utilizáveis que ainda dividem polígono de água: {agua[2]}; "
        f"amostra: {am[1]} de {am[0]} percursos cruzam água sem ponte, {am[2]} cruzam ferrovia em nível (passagens OSM); "
        f"sobreposições longitudinais remanescentes (margens de canais e lagos, sem travessia): {agua[0]} arestas, "
        f"{agua[1]} m ({agua[3]})")

    # E06 — distâncias com comprimento real
    r = um(cur, """SELECT count(*), max(abs(comprimento_geometrico_m - distancia_calculada_m)) FROM qa.amostra_percursos""")
    m = um(cur, """SELECT count(*) FILTER (WHERE op.distancia_m + %s < ST_Distance(o.geom, s.geom)),
                          max(abs(op.distancia_m - op.distancia_rede_m - op.distancia_ligacao_origem_m - op.distancia_ligacao_parada_m)),
                          (SELECT max(abs(ST_Length(geom) - comprimento_m)) FROM analise.rede_arestas)
                   FROM analise.origem_parada_400m op JOIN analise.pontos_demanda o USING (origem_id)
                   JOIN analise.paradas_analise s USING (stop_id)""", TOL)
    reg("E06", "Rede", "Distâncias calculadas com o comprimento real das arestas",
        "OK" if r[1] < 0.05 and m[0] == 0 and m[1] < 1e-6 and m[2] < 1e-6 else "FALHA",
        f"amostra de {r[0]} percursos reconstruídos no PostGIS: dif. máx. geometria x grafo {r[1]:.4f} m; pares com percurso < "
        f"distância euclidiana: {m[0]}; dif. máx. ST_Length x peso da aresta {m[2]:.1e} m")

    # E07 — limite de 400 m
    r = um(cur, "SELECT count(*), max(distancia_m), count(*) FILTER (WHERE distancia_m > %s + %s) FROM analise.origem_parada_400m", lim, TOL)
    reg("E07", "Acessibilidade", "Nenhum par origem-parada acima de 400 m", "OK" if r[2] == 0 else "FALHA",
        f"{r[0]} pares; máximo {r[1]:.3f} m; acima de {lim} + {TOL} m: {r[2]}")

    # E08 — paradas acessíveis com serviço de ônibus no dia
    r = um(cur, """SELECT count(DISTINCT op.stop_id),
                          count(DISTINCT op.stop_id) FILTER (WHERE NOT EXISTS (SELECT 1 FROM prep.gtfs_horarios_dia h WHERE h.stop_id = op.stop_id)),
                          count(DISTINCT op.stop_id) FILTER (WHERE NOT p.serve_onibus_dia_ref)
                   FROM analise.origem_parada_400m op JOIN analise.paradas_analise p USING (stop_id)""")
    reg("E08", "Acessibilidade", "Paradas acessíveis associadas a serviço de ônibus em 21/10/2026",
        "OK" if r[1] == 0 and r[2] == 0 else "FALHA",
        f"{r[0]} paradas alcançadas; sem partidas de ônibus no dia: {r[1]}; não marcadas com serviço: {r[2]}")

    # E09 — classificação
    r = um(cur, """SELECT count(*) FILTER (WHERE (situacao = 'coberto_400m') <> (n_paradas_400m > 0)),
                          count(*) FILTER (WHERE situacao = 'sem_cobertura_400m' AND (NOT ligada_componente_principal OR n_ligacoes = 0)),
                          count(*) FILTER (WHERE situacao = 'nao_determinado' AND motivo_nao_determinado IS NULL),
                          count(*) FILTER (WHERE situacao = 'coberto_400m' AND dist_parada_mais_proxima_m > %s + %s),
                          count(*) FILTER (WHERE situacao = 'sem_cobertura_400m' AND dist_parada_mais_proxima_m <= %s),
                          (SELECT count(*) FROM analise.resultado_origem r JOIN analise.parada_mais_proxima p USING (origem_id)
                            WHERE r.situacao = 'coberto_400m' AND abs(p.distancia_m - r.dist_parada_mais_proxima_m) > %s),
                          count(*) FILTER (WHERE situacao NOT IN ('coberto_400m', 'sem_cobertura_400m', 'nao_determinado'))
                   FROM analise.resultado_origem""", lim, TOL, lim, TOL)
    reg("E09", "Acessibilidade", "Classificação coberto / sem cobertura / não determinado consistente",
        "OK" if not any(r) else "FALHA",
        f"incoerências — coberto x pares: {r[0]}; sem cobertura não ligada ao principal: {r[1]}; ND sem motivo: {r[2]}; "
        f"coberto com distância > 400: {r[3]}; sem cobertura com distância <= 400: {r[4]}; mais próxima divergente: {r[5]}")

    # E10 — soma das populações
    r = um(cur, """SELECT sum(pob_estimada), sum(pob_estimada) FILTER (WHERE situacao = 'coberto_400m'),
                          sum(pob_estimada) FILTER (WHERE situacao = 'sem_cobertura_400m'),
                          sum(pob_estimada) FILTER (WHERE situacao = 'nao_determinado'),
                          (SELECT sum(pob_estimada) FROM analise.parcelas_demanda),
                          (SELECT sum(pob_coberta + pob_sem_cobertura + pob_nao_determinada) FROM analise.resultado_seccion)
                   FROM analise.resultado_origem""")
    soma = r[1] + r[2] + (r[3] or 0)
    reg("E10", "Agregação", "Soma das categorias = população estimada da grade",
        "OK" if abs(soma - r[0]) < 1e-6 and abs(r[0] - r[4]) < 1e-6 and abs(r[5] - r[0]) < 1e-6 else "FALHA",
        f"coberta {r[1]:.1f} + sem cobertura {r[2]:.1f} + ND {r[3] or 0:.1f} = {soma:.2f}; grade {r[0]:.2f}; soma das seções {r[5]:.2f}")

    # E11 — percentuais por seção
    r = um(cur, """SELECT count(*), count(*) FILTER (WHERE pob_grade > 0),
                          count(*) FILTER (WHERE pct_coberta < -1e-9 OR pct_coberta > 100 + 1e-9 OR pct_sem_cobertura < -1e-9
                                           OR pct_sem_cobertura > 100 + 1e-9 OR pct_nao_determinada < -1e-9 OR pct_nao_determinada > 100 + 1e-9),
                          max(abs(pct_coberta + pct_sem_cobertura + pct_nao_determinada - 100)),
                          max(abs(pob_coberta + pob_sem_cobertura + pob_nao_determinada - pob_grade)),
                          count(*) FILTER (WHERE pob_ine IS NULL)
                   FROM analise.resultado_seccion""")
    reg("E11", "Agregação", "Percentuais por seção coerentes (0–100%, soma 100%)",
        "OK" if r[0] == 521 and r[2] == 0 and r[3] < 1e-9 and r[4] < 1e-6 and r[5] == 0 else "FALHA",
        f"{r[0]} seções ({r[1]} com população da grade); fora de 0–100%: {r[2]}; desvio máx. da soma: {r[3]:.1e} p.p.; "
        f"seções sem população INE: {r[5]}")


def reproducao(cur, res):
    """E12 — o cálculo refeito em memória (conferir_amostra) deve coincidir com o gravado."""
    cur.execute("SELECT origem_id, stop_id, distancia_m, ligacao_origem_id, ligacao_parada_id FROM analise.origem_parada_400m")
    bd = {(o, s): (round(d, 6), lo, lp) for o, s, d, lo, lp in cur.fetchall()}
    novo = {k: (round(v[0], 6), v[1], v[2]) for k, v in res["pares"].items()}
    cur.execute("SELECT origem_id, stop_id, distancia_m FROM analise.parada_mais_proxima")
    bdp = {o: (s, round(d, 6)) for o, s, d in cur.fetchall()}
    novop = {o: (v[1], round(v[0], 6)) for o, v in res["proxima"].items()}
    ok = bd == novo and bdp == novop
    reg("E12", "Reprodução", "Resultados idênticos em nova execução do cálculo", "OK" if ok else "FALHA",
        f"pares: {len(novo)} recalculados x {len(bd)} gravados (iguais: {bd == novo}); parada mais próxima: "
        f"{len(novop)} x {len(bdp)} (iguais: {bdp == novop})")


def grade(cur):
    n_local = um(cur, "SELECT count(*), count(*) FILTER (WHERE pob_tot <= 0) FROM fonte.ieca_gridp_250 WHERE position('41091' IN cmun) > 0")
    try:
        r = requests.get(CFG["ieca_grid"]["wfs"], params={
            "service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": CFG["ieca_grid"]["camada"],
            "resultType": "hits", "CQL_FILTER": "cmun LIKE '%41091%'"}, timeout=90)
        hits = int(r.text.split('numberMatched="')[1].split('"')[0])
        r0 = requests.get(CFG["ieca_grid"]["wfs"], params={
            "service": "WFS", "version": "2.0.0", "request": "GetFeature", "typeNames": CFG["ieca_grid"]["camada"],
            "resultType": "hits", "CQL_FILTER": "pob_tot <= 0"}, timeout=90)
        zero = int(r0.text.split('numberMatched="')[1].split('"')[0])
        det = f"WFS: {hits} células com cmun contendo 41091 (carregadas: {n_local[0]}); células com pob_tot <= 0 em toda a Andaluzia: {zero}"
        ok = hits == n_local[0] and zero == 0
    except (requests.RequestException, IndexError, ValueError) as e:
        det, ok = f"WFS indisponível ({type(e).__name__}); local: {n_local[0]} células, {n_local[1]} com pob <= 0", n_local[1] == 0
    reg("E00", "Grade IECA", "Abrangência da grade: somente células habitadas, sem registros omitidos", "OK" if ok else "FALHA", det)


def main():
    with conectar(CFG) as conn, conn.cursor() as cur:
        grade(cur)
        res = conferir_amostra(conn, cur)
        testes(conn, cur)
        reproducao(cur, res)
        execucao = dt.datetime.now(dt.timezone.utc)
        cur.executemany("INSERT INTO qa.resultado_testes VALUES (%s,%s,%s,%s,%s,%s)", [(execucao, *r) for r in RES])
        conn.commit()
        cur.execute("""SELECT categoria, origem_id, stop_id, round(distancia_calculada_m::numeric, 2),
                              round(comprimento_geometrico_m::numeric, 2), cruza_agua_sem_ponte, cruza_ferrovia_em_nivel
                       FROM qa.amostra_percursos ORDER BY categoria, origem_id""")
        am = cur.fetchall()
    resumo = {s: sum(1 for r in RES if r[3] == s) for s in ("OK", "LIMITACAO", "FALHA")}
    linhas = ["# Testes de integridade — Etapa 2", "",
              f"Execução: {execucao.isoformat(timespec='seconds')} — OK: {resumo['OK']}, LIMITACAO: {resumo['LIMITACAO']}, "
              f"FALHA: {resumo['FALHA']}", "",
              "Gerado por `scripts/08_testes_etapa2.py` (também em `qa.resultado_testes`, IDs com prefixo E).", "",
              "| ID | Grupo | Verificação | Status | Detalhe |", "|---|---|---|---|---|"]
    linhas += [f"| {t} | {g} | {d} | **{s}** | {x.replace('|', '/')} |" for t, g, d, s, x in RES]
    linhas += ["", "## Amostra conferida (percurso reconstruído no PostGIS — `qa.amostra_percursos`)", "",
               "| Contexto | Origem | Parada | Distância no grafo (m) | Comprimento geométrico (m) | Água sem ponte | Ferrovia em nível |",
               "|---|---|---|---|---|---|---|"]
    linhas += [f"| {c} | {o} | {s} | {d} | {g} | {a} | {f} |" for c, o, s, d, g, a, f in am]
    caminho("docs/testes_etapa2.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(resumo)
    sys.exit(1 if resumo["FALHA"] else 0)


if __name__ == "__main__":
    main()
