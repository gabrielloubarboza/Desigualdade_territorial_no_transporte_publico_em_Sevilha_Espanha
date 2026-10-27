"""Etapa 3 — Testes da oferta programada acessível (OK / LIMITACAO / FALHA).

Uso:  .venv\\Scripts\\python.exe scripts\\11_testes_etapa3.py

A conferência independente recalcula em pandas, a partir de prep.gtfs_horarios_dia, prep.gtfs_viagens_dia,
config.yaml e analise.origem_parada_400m (sem usar as tabelas da Etapa 3), as contagens de viagens,
linhas e linhas-sentido de todas as origens e as médias por seção. O teste de reprodução reexecuta o SQL
da etapa e compara as tabelas. Resultados em qa.resultado_testes (prefixo F) e docs/testes_etapa3.md.
"""
from __future__ import annotations

import datetime as dt
import importlib.util
import sys

import numpy as np
import pandas as pd

from comum import caminho, carregar_config, conectar

CFG = carregar_config()
RES: list[tuple] = []
CASOS: list[str] = []


def reg(tid, grupo, desc, status, det):
    RES.append((tid, grupo, desc, status, det))
    print(f"[{status:9}] {tid} {desc} — {det}")


def um(cur, q, *a):
    cur.execute(q, a)
    return cur.fetchone()


def df(conn, q, *a):
    cur = conn.execute(q, a)
    return pd.DataFrame(cur.fetchall(), columns=[c.name for c in cur.description])


def seg(h):
    a, b, c = map(int, h.split(":"))
    return a * 3600 + b * 60 + c


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


def testes(conn, cur):
    # F01 — serviços x data
    r = um(cur, """SELECT (SELECT string_agg(DISTINCT service_id, ',') FROM analise.partidas_dia),
                          (SELECT string_agg(service_id, ',') FROM prep.gtfs_servicos_dia),
                          (SELECT count(DISTINCT data) FROM analise.partidas_dia), (SELECT min(data) FROM analise.partidas_dia),
                          (SELECT count(*) FROM analise.partidas_dia d WHERE NOT EXISTS
                             (SELECT 1 FROM fonte.gtfs_calendar c WHERE c.service_id = d.service_id AND c.wednesday = 1
                              AND d.data BETWEEN c.start_date AND c.end_date)),
                          (SELECT count(*) FROM fonte.gtfs_calendar_dates WHERE date = '2026-10-21')""")
    ok = r[0] == r[1] == "INVLAB40" and r[2] == 1 and str(r[3]) == CFG["gtfs"]["dia_referencia"] and r[4] == 0
    reg("F01", "GTFS", "Serviços GTFS correspondem à data de referência", "OK" if ok else "FALHA",
        f"serviços nas partidas: {r[0]}; ativos em {r[3]}: {r[1]}; partidas fora do calendário de quarta-feira: {r[4]}; "
        f"exceções calendar_dates na data: {r[5]}")

    # F02 — modos excluídos
    r = um(cur, """SELECT count(*) FILTER (WHERE rt.route_type <> 3), count(DISTINCT p.route_id),
                          count(*) FILTER (WHERE rt.agency_id <> 'TUSSAM')
                   FROM analise.partidas_dia p JOIN fonte.gtfs_routes rt USING (route_id)""")
    reg("F02", "GTFS", "Sem bonde T1 ou outros modos", "OK" if r[0] == 0 and r[2] == 0 else "FALHA",
        f"partidas não-ônibus: {r[0]}; de outro operador: {r[2]}; linhas de ônibus com partidas no dia: {r[1]}")

    # F03 — períodos
    r = um(cur, """SELECT (SELECT count(*) FROM analise.partidas_periodo p JOIN prep.periodos_analise a USING (periodo)
                             WHERE p.partida_s < a.inicio_s OR p.partida_s >= a.fim_s),
                          (SELECT count(*) FROM analise.partidas_dia d JOIN prep.periodos_analise a
                             ON d.partida_s >= a.inicio_s AND d.partida_s < a.fim_s),
                          (SELECT count(*) FROM analise.partidas_periodo),
                          (SELECT count(*) - count(DISTINCT (trip_id, stop_sequence)) FROM analise.partidas_periodo),
                          (SELECT count(*) FROM analise.partidas_dia d JOIN prep.periodos_analise a ON d.partida_s = a.inicio_s),
                          (SELECT count(*) FROM analise.partidas_periodo p JOIN prep.periodos_analise a USING (periodo) WHERE p.partida_s = a.inicio_s),
                          (SELECT count(*) FROM analise.partidas_dia d JOIN prep.periodos_analise a ON d.partida_s = a.fim_s),
                          (SELECT count(*) FROM analise.partidas_periodo p JOIN prep.periodos_analise a ON a.periodo = p.periodo AND p.partida_s = a.fim_s)""")
    ok = r[0] == 0 and r[1] == r[2] and r[3] == 0 and r[4] == r[5] and r[7] == 0
    reg("F03", "Períodos", "Partidas atribuídas corretamente aos três períodos [início, fim)", "OK" if ok else "FALHA",
        f"fora da janela: {r[0]}; partidas do dia nas janelas {r[1]} = registradas {r[2]}; em dois períodos: {r[3]}; "
        f"exatamente no início: {r[4]} (todas incluídas: {r[5]}); exatamente no fim: {r[6]} (incluídas no período que termina: {r[7]})")

    # F04 — horários válidos e ordenados
    r = um(cur, """SELECT count(*) FILTER (WHERE partida_s IS NULL OR partida_s < 0 OR partida_s > 48 * 3600),
                          (SELECT count(*) FROM (SELECT partida_s < lag(partida_s) OVER (PARTITION BY trip_id ORDER BY stop_sequence) AS r
                                                 FROM analise.partidas_dia) x WHERE r),
                          max(partida_s) - 86400, (SELECT min(inicio_s) FROM prep.periodos_analise),
                          count(*) FILTER (WHERE origem_horario = 'interpolado' AND NOT partida_s BETWEEN t_controle_anterior_s AND t_controle_seguinte_s)
                   FROM analise.partidas_dia""")
    ok = r[0] == 0 and r[1] == 0 and r[2] < r[3] and r[4] == 0
    reg("F04", "GTFS", "Horários válidos e cronologicamente coerentes", "OK" if ok else "FALHA",
        f"inválidos: {r[0]}; regressões na viagem: {r[1]}; interpolados fora dos pontos de controle: {r[4]}; maior horário "
        f"após 24h corresponde a {r[2] // 3600:02d}:{r[2] % 3600 // 60:02d} do dia seguinte (< 07:00: viagens do dia anterior não invadem as janelas)")

    # F05 — paradas acessíveis x programação
    r = um(cur, """SELECT count(DISTINCT op.stop_id),
                          count(DISTINCT op.stop_id) FILTER (WHERE NOT EXISTS (SELECT 1 FROM analise.partidas_dia d WHERE d.stop_id = op.stop_id)),
                          (SELECT string_agg(periodo || ': ' || n, ', ') FROM (
                              SELECT pa.periodo, count(DISTINCT op2.stop_id) AS n FROM analise.origem_parada_400m op2 CROSS JOIN prep.periodos_analise pa
                              WHERE NOT EXISTS (SELECT 1 FROM analise.partidas_periodo p WHERE p.stop_id = op2.stop_id AND p.periodo = pa.periodo)
                              GROUP BY 1 ORDER BY 1) x)
                   FROM analise.origem_parada_400m op""")
    reg("F05", "Paradas", "Paradas acessíveis correspondem a paradas com programação", "OK" if r[1] == 0 else "FALHA",
        f"{r[0]} paradas acessíveis; sem nenhuma partida no dia: {r[1]}; sem partida no período (informativo) — {r[2]}")

    # F06 — dupla contagem
    r = um(cur, """SELECT (SELECT count(*) - count(DISTINCT (origem_id, periodo, trip_id)) FROM analise.origem_viagem_periodo),
                          (SELECT count(*) FROM analise.oferta_origem_periodo o
                             WHERE o.n_viagens <> coalesce((SELECT count(*) FROM analise.origem_viagem_periodo v
                                                           WHERE v.origem_id = o.origem_id AND v.periodo = o.periodo), 0)),
                          (SELECT sum(n_passagens_brutas) - sum(n_viagens) FROM analise.oferta_origem_periodo),
                          (SELECT count(*) FROM analise.origem_viagem_periodo WHERE n_paradas_acessiveis_viagem > 1),
                          (SELECT count(*) FROM analise.origem_viagem_periodo v WHERE v.distancia_caminhada_m >
                             (SELECT min(op.distancia_m) FROM analise.origem_parada_400m op JOIN analise.partidas_periodo p USING (stop_id)
                              WHERE op.origem_id = v.origem_id AND p.periodo = v.periodo AND p.trip_id = v.trip_id) + 1e-9)""")
    ok = r[0] == 0 and r[1] == 0 and r[4] == 0
    reg("F06", "Deduplicação", "Mesma viagem contada uma vez por origem e período", "OK" if ok else "FALHA",
        f"duplicatas origem-período-viagem: {r[0]}; n_viagens divergente da tabela deduplicada: {r[1]}; passagens brutas "
        f"removidas pela deduplicação: {r[2]}; viagens acessíveis em >1 parada: {r[3]}; embarque fora da menor caminhada: {r[4]}")

    # F07 — linhas distintas (recálculo independente em pandas)
    ind = recalculo_independente(conn)
    bd = df(conn, """SELECT origem_id, periodo, n_viagens, n_linhas, n_linha_sentido FROM analise.oferta_origem_periodo
                     WHERE n_viagens > 0""")
    m = bd.merge(ind, on=["origem_id", "periodo"], how="outer", suffixes=("_bd", "_ind"), indicator=True)
    so_um_lado = int((m._merge != "both").sum())
    dif = {c: int((m[f"{c}_bd"] != m[f"{c}_ind"]).sum()) for c in ("n_viagens", "n_linhas", "n_linha_sentido")}
    reg("F07", "Contagens", "Linhas distintas, viagens e linhas-sentido conferem com recálculo independente",
        "OK" if so_um_lado == 0 and not any(dif.values()) else "FALHA",
        f"{len(m)} pares origem-período com oferta comparados; presentes só de um lado: {so_um_lado}; divergências: {dif}")

    # F08 — sentidos
    r = um(cur, """SELECT count(*) FILTER (WHERE v.direction_id IS DISTINCT FROM t.direction_id), count(*) FILTER (WHERE v.direction_id IS NULL),
                          (SELECT count(*) FROM analise.oferta_origem_periodo WHERE n_linha_sentido < n_linhas OR n_linha_sentido > 2 * n_linhas)
                   FROM analise.origem_viagem_periodo v JOIN fonte.gtfs_trips t USING (trip_id)""")
    ok = r[0] == 0 and r[1] == 0 and r[2] == 0
    reg("F08", "Sentidos", "Sentidos das viagens preservados", "OK" if ok else "FALHA",
        f"direction_id divergente do GTFS: {r[0]}; nulos: {r[1]}; origens com linha-sentido fora de [linhas, 2·linhas]: {r[2]}")

    # F09 — partidas/hora
    r = um(cur, """SELECT max(abs(partidas_hora * duracao_h - n_viagens)),
                          (SELECT max(abs(viagens_hora * 2 - n_viagens)) FROM analise.oferta_linha_sentido_periodo),
                          (SELECT max(abs(viagens_rede_hora * duracao_h - viagens_rede)) FROM analise.sintese_oferta_municipal)
                   FROM analise.oferta_origem_periodo""")
    reg("F09", "Contagens", "Partidas por hora = viagens / duração da janela", "OK" if max(r) < 1e-9 else "FALHA",
        f"desvio máx. origem {r[0]}; linha-sentido {r[1]}; rede {r[2]}")

    # F10 — nulos, zeros e não determinados
    r = um(cur, """SELECT count(*) FILTER (WHERE situacao_oferta = 'nao_determinado' AND (n_viagens IS NOT NULL OR n_linhas IS NOT NULL OR partidas_hora IS NOT NULL)),
                          count(*) FILTER (WHERE situacao_oferta = 'sem_cobertura_400m' AND (n_viagens <> 0 OR n_linhas <> 0 OR n_paradas_400m <> 0)),
                          count(*) FILTER (WHERE situacao_oferta = 'coberto_sem_servico_no_periodo' AND (n_viagens <> 0 OR n_paradas_400m = 0)),
                          count(*) FILTER (WHERE situacao_oferta = 'com_servico' AND (n_viagens = 0 OR n_linhas = 0)),
                          count(*) FILTER (WHERE situacao_oferta <> 'nao_determinado' AND (n_viagens IS NULL OR partidas_hora IS NULL)),
                          string_agg(DISTINCT situacao_oferta, ',')
                   FROM analise.oferta_origem_periodo""")
    reg("F10", "Classificação", "Nulos (não determinado), zeros (sem cobertura / sem serviço) e com serviço coerentes",
        "OK" if not any(r[:5]) else "FALHA",
        f"incoerências — ND com valor: {r[0]}; sem cobertura com oferta: {r[1]}; coberto sem serviço incoerente: {r[2]}; "
        f"com serviço sem viagens: {r[3]}; determinado com nulo: {r[4]}; situações: {r[5]}")

    # F11 — médias ponderadas (recalculadas em pandas)
    o = df(conn, "SELECT cusec, periodo, pob_estimada, situacao_oferta, n_linhas, partidas_hora FROM analise.oferta_origem_periodo")
    for c in ("pob_estimada", "n_linhas", "partidas_hora"):
        o[c] = o[c].astype(float)
    d = o[o.situacao_oferta != "nao_determinado"].copy()
    d["pl"], d["pp"] = d.pob_estimada * d.n_linhas, d.pob_estimada * d.partidas_hora
    a = d.groupby(["cusec", "periodo"]).agg(p=("pob_estimada", "sum"), pl=("pl", "sum"), pp=("pp", "sum"))
    a["ml"], a["mp"] = a.pl / a.p, a.pp / a.p
    s = df(conn, "SELECT cusec, periodo, media_linhas, media_partidas_hora, pct_com_servico, pob_grade FROM analise.oferta_seccion_periodo")
    s = s.merge(a[["ml", "mp"]].reset_index(), on=["cusec", "periodo"], how="left")
    ps = o[o.situacao_oferta == "com_servico"].groupby(["cusec", "periodo"]).pob_estimada.sum().rename("pcs").reset_index()
    s = s.merge(ps, on=["cusec", "periodo"], how="left").fillna({"pcs": 0})
    dl = np.nanmax(np.abs(s.media_linhas.astype(float) - s.ml))
    dp = np.nanmax(np.abs(s.media_partidas_hora.astype(float) - s.mp))
    dc = np.nanmax(np.abs(s.pct_com_servico.astype(float) - 100 * s.pcs / s.pob_grade.astype(float)))
    reg("F11", "Agregação", "Médias ponderadas pela população conferem com recálculo independente",
        "OK" if max(dl, dp, dc) < 1e-9 else "FALHA",
        f"desvio máx. — média de linhas {dl:.1e}; partidas/h {dp:.1e}; % com serviço {dc:.1e}")

    # F12 — 521 seções
    r = um(cur, """SELECT (SELECT count(*) FROM analise.oferta_seccion_periodo), (SELECT count(DISTINCT cusec) FROM analise.oferta_seccion_periodo),
                          (SELECT count(*) FROM analise.indicadores_seccion_oferta),
                          (SELECT count(*) FROM analise.oferta_seccion_periodo WHERE media_partidas_hora IS NULL),
                          (SELECT count(*) FROM analise.indicadores_seccion_oferta i JOIN prep.secciones s USING (cusec) WHERE NOT ST_Equals(i.geom, s.geom))""")
    reg("F12", "Seções", "521 seções preservadas com geometria original", "OK" if r[0] == 1563 and r[1] == 521 and r[2] == 521 and r[4] == 0 else "FALHA",
        f"{r[0]} linhas seção-período ({r[1]} seções); tabela larga: {r[2]}; seções sem média calculável: {r[3]}; geometrias alteradas: {r[4]}")

    # F13 — origem x seção x município
    r = um(cur, """WITH o AS (SELECT periodo, sum(pob_estimada) FILTER (WHERE situacao_oferta = 'com_servico') cs,
                                     sum(pob_estimada) FILTER (WHERE situacao_oferta = 'coberto_sem_servico_no_periodo') css,
                                     sum(pob_estimada) p FROM analise.oferta_origem_periodo GROUP BY 1),
                        s AS (SELECT periodo, sum(pob_com_servico) cs, sum(pob_coberta_sem_servico) css, sum(pob_grade) p,
                                     sum(media_partidas_hora * pob_determinada) / sum(pob_determinada) FILTER (WHERE pob_determinada > 0) mp,
                                     sum(pob_com_servico + pob_coberta_sem_servico + pob_sem_cobertura + pob_nao_determinada) soma
                              FROM analise.oferta_seccion_periodo GROUP BY 1)
                   SELECT max(abs(o.cs - s.cs)), max(abs(coalesce(o.css, 0) - s.css)), max(abs(o.p - s.p)), max(abs(m.pob_com_servico - s.cs)),
                          max(abs(m.media_partidas_hora - s.mp)), max(abs(s.soma - s.p))
                   FROM o JOIN s USING (periodo) JOIN analise.sintese_oferta_municipal m USING (periodo)""")
    reg("F13", "Agregação", "Coerência entre origens, seções e município", "OK" if max(float(x) for x in r) < 1e-6 else "FALHA",
        f"desvios máx. — com serviço origem x seção {r[0]:.1e}; coberto sem serviço {r[1]:.1e}; pop. {r[2]:.1e}; "
        f"seção x município {r[3]:.1e}; média partidas/h seção x município {r[4]:.1e}; soma das categorias {r[5]:.1e}")

    # F14 — sensibilidade
    cur.execute("""SELECT periodo, cenario, dif_pct_media_partidas_hora, dif_pct_media_linhas, spearman_secoes_partidas_hora,
                          secoes_dif_maior_10pct, viagens_rede FROM analise.sensibilidade_resumo ORDER BY periodo, cenario""")
    sens = cur.fetchall()
    leve = [x for x in sens if x[1] in ("menos_2min", "mais_2min")]
    env = [x for x in sens if x[1].startswith("limite")]
    ok = all(abs(x[2]) < 2 and x[4] >= 0.99 for x in leve)
    reg("F14", "Sensibilidade", "Indicadores pouco sensíveis à interpolação dos horários", "OK" if ok else "LIMITACAO",
        f"±2 min: média de partidas/h varia {min(x[2] for x in leve):+.2f}% a {max(x[2] for x in leve):+.2f}%, Spearman das seções "
        f">= {min(x[4] for x in leve):.4f}, seções com variação > 10%: até {max(x[5] for x in leve)}; envoltórias extremas "
        f"(horário em qualquer ponto entre controles): {min(x[2] for x in env):+.1f}% a {max(x[2] for x in env):+.1f}%, Spearman "
        f">= {min(x[4] for x in env):.4f}, linhas {min(x[3] for x in env):+.2f}% a {max(x[3] for x in env):+.2f}%")


TABELAS_REPRO = {
    "oferta_origem_periodo": "origem_id, periodo",
    "origem_viagem_periodo": "origem_id, periodo, trip_id",
    "origem_linha_sentido_periodo": "origem_id, periodo, route_id, direction_id",
    "oferta_seccion_periodo": "cusec, periodo",
    "sintese_oferta_municipal": "periodo",
    "sensibilidade_resumo": "periodo, cenario",
}


def instantaneo(conn):
    out = {}
    for t, ordem in TABELAS_REPRO.items():
        x = df(conn, f"SELECT * FROM analise.{t} ORDER BY {ordem}")
        out[t] = x.drop(columns=[c for c in x.columns if c == "geom"])
    return out


def iguais(a, b):
    if a.shape != b.shape or list(a.columns) != list(b.columns):
        return False
    for c in a.columns:
        x, y = a[c], b[c]
        try:
            xf, yf = x.astype(float), y.astype(float)
            if not np.allclose(xf, yf, rtol=1e-12, atol=1e-9, equal_nan=True):
                return False
        except (TypeError, ValueError):
            if not x.astype(str).equals(y.astype(str)):
                return False
    return True


def reproducao(conn):
    antes = instantaneo(conn)
    spec = importlib.util.spec_from_file_location("oferta", caminho("scripts/10_oferta_programada.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.executar(conn)
    depois = instantaneo(conn)
    res = {t: iguais(antes[t], depois[t]) for t in TABELAS_REPRO}
    reg("F15", "Reprodução", "Resultados idênticos em segunda execução do SQL da etapa", "OK" if all(res.values()) else "FALHA",
        "; ".join(f"{t}: {'igual' if v else 'DIFERENTE'} ({len(antes[t])} linhas)" for t, v in res.items()))


def casos(conn):
    """Casos representativos para conferência manual (registrados no relatório)."""
    q = {
        "muitas paradas acessíveis": "SELECT origem_id FROM analise.oferta_origem_periodo WHERE periodo='manha' ORDER BY n_paradas_400m DESC NULLS LAST, origem_id LIMIT 1",
        "mesma viagem em várias paradas": "SELECT origem_id FROM analise.origem_viagem_periodo WHERE periodo='manha' ORDER BY n_paradas_acessiveis_viagem DESC, origem_id LIMIT 1",
        "uma única linha": "SELECT origem_id FROM analise.oferta_origem_periodo WHERE periodo='manha' AND n_linhas = 1 ORDER BY pob_estimada DESC LIMIT 1",
        "coberta sem partida no período": "SELECT origem_id FROM analise.oferta_origem_periodo WHERE situacao_oferta='coberto_sem_servico_no_periodo' ORDER BY pob_estimada DESC LIMIT 1",
        "sem cobertura 400 m": "SELECT origem_id FROM analise.oferta_origem_periodo WHERE situacao_oferta='sem_cobertura_400m' ORDER BY pob_estimada DESC LIMIT 1",
        "acessibilidade não determinada": "SELECT origem_id FROM analise.oferta_origem_periodo WHERE situacao_oferta='nao_determinado' ORDER BY pob_estimada DESC LIMIT 1",
    }
    CASOS.append("| Caso | Origem | Período | Situação | Paradas 400 m | Paradas com partida | Linhas | Linha-sentido | Viagens | Partidas/h | Passagens brutas | Linhas acessíveis |")
    CASOS.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    for nome, sql in q.items():
        oid = conn.execute(sql).fetchone()[0]
        for r in conn.execute("""
                SELECT o.periodo, o.situacao_oferta, o.n_paradas_400m, o.n_paradas_com_partida, o.n_linhas, o.n_linha_sentido,
                       o.n_viagens, o.partidas_hora, o.n_passagens_brutas,
                       (SELECT string_agg(route_short_name || '/' || direction_id || ':' || n_viagens, ' ' ORDER BY route_short_name, direction_id)
                        FROM analise.origem_linha_sentido_periodo l WHERE l.origem_id = o.origem_id AND l.periodo = o.periodo)
                FROM analise.oferta_origem_periodo o JOIN prep.periodos_analise p USING (periodo)
                WHERE o.origem_id = %s ORDER BY p.inicio""", (oid,)).fetchall():
            lin = (r[9] or "—")[:160]
            ph = "—" if r[7] is None else f"{float(r[7]):.1f}"
            CASOS.append(f"| {nome} | {oid} | {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} | {r[6]} | {ph} | {r[8]} | {lin} |")
    CASOS.append("")
    CASOS.append("Partidas próximas às fronteiras das janelas (±3 min), com o período atribuído:")
    CASOS.append("")
    CASOS.append("| Fronteira | Linha/sentido | Viagem | Parada | Horário | Origem do horário | Faixa entre controles | Período atribuído |")
    CASOS.append("|---|---|---|---|---|---|---|---|")
    for r in conn.execute("""
            WITH f AS (SELECT DISTINCT unnest(ARRAY[inicio_s, fim_s]) AS t FROM prep.periodos_analise)
            SELECT DISTINCT ON (f.t, d.origem_horario) to_char(make_interval(secs => f.t), 'HH24:MI'), d.route_short_name || '/' || d.direction_id,
                   d.trip_id, d.stop_id, d.hora, d.origem_horario,
                   to_char(make_interval(secs => d.t_controle_anterior_s), 'HH24:MI') || '–' || to_char(make_interval(secs => d.t_controle_seguinte_s), 'HH24:MI'),
                   coalesce((SELECT string_agg(periodo, ',') FROM analise.partidas_periodo p WHERE p.trip_id = d.trip_id AND p.stop_sequence = d.stop_sequence), 'nenhum')
            FROM f JOIN analise.partidas_dia d ON d.partida_s BETWEEN f.t - 180 AND f.t + 180
            WHERE d.stop_id IN (SELECT stop_id FROM analise.origem_parada_400m)
            ORDER BY f.t, d.origem_horario, abs(d.partida_s - f.t), d.trip_id""").fetchall():
        CASOS.append("| " + " | ".join(str(x) for x in r) + " |")


def main():
    with conectar(CFG) as conn:
        with conn.cursor() as cur:
            testes(conn, cur)
        reproducao(conn)
        casos(conn)
        execucao = dt.datetime.now(dt.timezone.utc)
        with conn.cursor() as cur:
            cur.executemany("INSERT INTO qa.resultado_testes VALUES (%s,%s,%s,%s,%s,%s)", [(execucao, *r) for r in RES])
        conn.commit()
    resumo = {s: sum(1 for r in RES if r[3] == s) for s in ("OK", "LIMITACAO", "FALHA")}
    linhas = ["# Testes de integridade — Etapa 3", "",
              f"Execução: {execucao.isoformat(timespec='seconds')} — OK: {resumo['OK']}, LIMITACAO: {resumo['LIMITACAO']}, FALHA: {resumo['FALHA']}",
              "", "Gerado por `scripts/11_testes_etapa3.py` (também em `qa.resultado_testes`, IDs com prefixo F).", "",
              "| ID | Grupo | Verificação | Status | Detalhe |", "|---|---|---|---|---|"]
    linhas += [f"| {t} | {g} | {d} | **{s}** | {x.replace('|', '/')} |" for t, g, d, s, x in RES]
    linhas += ["", "## Casos representativos", "",
               "Linhas acessíveis no formato `linha/sentido:viagens`. Passagens brutas = viagem × parada antes da deduplicação.", ""]
    linhas += CASOS
    caminho("docs/testes_etapa3.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(resumo)
    sys.exit(1 if resumo["FALHA"] else 0)


if __name__ == "__main__":
    main()
