"""Etapa 4 — Testes da classificação territorial (OK / LIMITACAO / FALHA).

Uso:  .venv\\Scripts\\python.exe scripts\\14_testes_etapa4.py

Recalcula em pandas, a partir das tabelas das Etapas 2 e 3, a densidade, os limiares (percentil linear =
percentile_cont), as deficiências, a tipologia e o ranking, e compara com o banco. O teste de reprodução
reexecuta o SQL da etapa. Resultados em qa.resultado_testes (prefixo G) e docs/testes_etapa4.md.
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
CENARIOS = {"principal": (0.75, 0.25, None), "sensibilidade_tercis": (2 / 3, 1 / 3, 99.0)}


def reg(tid, grupo, desc, status, det):
    RES.append((tid, grupo, desc, status, det))
    print(f"[{status:9}] {tid} {desc} — {det}")


def df(conn, q):
    cur = conn.execute(q)
    d = pd.DataFrame(cur.fetchall(), columns=[c.name for c in cur.description])
    for c in d.columns:
        if d[c].dtype == object:
            try:
                d[c] = pd.to_numeric(d[c])
            except (ValueError, TypeError):
                pass
    return d


def recalcular(conn):
    """Classificação independente (pandas) para os dois cenários."""
    sec = df(conn, """SELECT s.cusec, s.cdis, ST_Area(s.geom) / 1e6 AS area, p.poblacion_total AS pob FROM prep.secciones s
                      JOIN prep.poblacion_seccion p USING (cusec)""")
    sec["dens"] = sec.pob / sec.area
    o = df(conn, """SELECT cusec, periodo, pob_coberta_400m, media_linhas_cobertos, media_partidas_hora_cobertos, media_linhas,
                           media_partidas_hora, pob_sem_oferta_acessivel, pct_sem_cobertura, pct_nao_determinada, pob_grade,
                           pob_coberta_400m * 100 / nullif(pob_grade, 0) AS pct_cob
                    FROM analise.oferta_seccion_periodo WHERE periodo = 'manha'""")
    cobmun = float(conn.execute("SELECT valor FROM analise.sintese_municipal WHERE indicador = 'pct_coberta_400m'").fetchone()[0])
    d = sec.merge(o, on="cusec")
    saida = []
    for cen, (pa, pb, cobfix) in CENARIOS.items():
        x = d.copy()
        cob = x[x.pob_coberta_400m > 0]
        l_dens = np.percentile(x.dens, 100 * pa)
        l_lin = np.percentile(cob.media_linhas_cobertos, 100 * pb)
        l_freq = np.percentile(cob.media_partidas_hora_cobertos, 100 * pb)
        l_cob = cobfix if cobfix is not None else cobmun
        x["alta"] = x.dens >= l_dens
        x["bcob"] = x.pct_cob < l_cob
        x["blin"] = np.where(x.pob_coberta_400m > 0, x.media_linhas_cobertos <= l_lin, np.nan)
        x["bfreq"] = np.where(x.pob_coberta_400m > 0, x.media_partidas_hora_cobertos <= l_freq, np.nan)
        x["inc"] = x.pct_nao_determinada > 10
        x["n"] = x.bcob.astype(int) + (x.blin == 1).astype(int) + (x.bfreq == 1).astype(int)
        x["ndim"] = x.bcob.astype(int) + ((x.blin == 1) | (x.bfreq == 1)).astype(int)

        def tip(r):
            if not r.alta:
                return "fora_alta_densidade"
            if r.inc:
                return "alta_densidade_informacao_incompleta"
            if r.n >= 2:
                return "D_deficiencias_combinadas"
            if r.bcob:
                return "A_baixa_cobertura"
            if r.blin == 1:
                return "B_baixa_diversidade_linhas"
            if r.bfreq == 1:
                return "C_baixa_frequencia"
            return "alta_densidade_sem_deficiencia"
        x["tipologia"] = x.apply(tip, axis=1)
        x["prior"] = x.alta & ~x.inc & (x.n > 0)
        p = x[x.prior].sort_values(["ndim", "pob_sem_oferta_acessivel", "media_partidas_hora", "media_linhas", "dens", "cusec"],
                                   ascending=[False, False, True, True, False, True])
        x["ranking"] = np.nan
        x.loc[p.index, "ranking"] = np.arange(1, len(p) + 1)
        x["cenario"] = cen
        x.attrs[cen] = dict(l_dens=l_dens, l_lin=l_lin, l_freq=l_freq, l_cob=l_cob)
        saida.append((x, dict(alta_densidade=l_dens, baixa_cobertura=l_cob, baixa_diversidade_linhas=l_lin, baixa_frequencia=l_freq)))
    return saida


def testes(conn):
    um = lambda q: conn.execute(q).fetchone()
    # G01 / G02
    r = um("""SELECT (SELECT count(*) FROM analise.diag_resultado_seccion), (SELECT count(DISTINCT cusec) FROM analise.diag_resultado_seccion),
                     (SELECT count(*) FROM analise.diag_classificacao), (SELECT count(*) FROM prep.secciones),
                     (SELECT count(*) FROM analise.diag_resultado_seccion r JOIN prep.secciones s USING (cusec) WHERE NOT ST_Equals(r.geom, s.geom)),
                     (SELECT count(*) FROM analise.diag_resultado_seccion WHERE ST_SRID(geom) <> 25830)""")
    reg("G01", "Seções", "521 seções preservadas com geometria INE em EPSG:25830",
        "OK" if r[0] == 521 and r[2] == 1042 and r[3] == 521 and r[4] == 0 and r[5] == 0 else "FALHA",
        f"{r[0]} seções na tabela consolidada; {r[2]} linhas seção x cenário; geometrias alteradas: {r[4]}; SRID diferente: {r[5]}")
    reg("G02", "Seções", "Sem duplicação de códigos", "OK" if r[0] == r[1] else "FALHA", f"{r[0]} linhas, {r[1]} códigos distintos")

    rec = recalcular(conn)
    bd = df(conn, "SELECT * FROM analise.diag_classificacao")
    base = df(conn, "SELECT cusec, densidade_ine_hab_km2, area_km2, pob_ine FROM analise.diag_base")
    x0 = rec[0][0]
    m = base.merge(x0[["cusec", "dens"]], on="cusec")
    dd = float(np.max(np.abs(m.densidade_ine_hab_km2 / m.dens - 1)))
    reg("G03", "Densidade", "Densidade = população INE / área total da seção", "OK" if dd < 1e-9 else "FALHA",
        f"desvio relativo máx. frente ao recálculo (ST_Area em EPSG:25830, população 2024): {dd:.1e}")

    lim = df(conn, "SELECT cenario, criterio, valor FROM analise.diag_limiares")
    dl, dflag = [], {}
    for x, limites in rec:
        cen = x.cenario.iloc[0]
        for k, v in limites.items():
            dl.append(abs(float(lim[(lim.cenario == cen) & (lim.criterio == k)].valor.iloc[0]) - v))
        y = bd[bd.cenario == cen].merge(x, on="cusec")
        dflag[cen] = int((y.alta_densidade != y.alta).sum() + (y.baixa_cobertura != y.bcob).sum()
                         + (y.baixa_diversidade_linhas.astype(float).fillna(-1) != pd.Series(y.blin).astype(float).fillna(-1)).sum()
                         + (y.baixa_frequencia.astype(float).fillna(-1) != pd.Series(y.bfreq).astype(float).fillna(-1)).sum())
    reg("G04", "Limiares", "Limiares e flags aplicados corretamente (dois cenários)",
        "OK" if max(dl) < 1e-9 and not any(dflag.values()) else "FALHA",
        f"desvio máx. dos limiares: {max(dl):.1e}; flags divergentes: {dflag}")

    r = um("""SELECT count(*) FILTER (WHERE n_deficiencias <> baixa_cobertura::int + coalesce(baixa_diversidade_linhas, false)::int + coalesce(baixa_frequencia, false)::int),
                     count(*) FILTER (WHERE (deficiencias = '') <> (n_deficiencias = 0)),
                     count(*) FILTER (WHERE (baixa_frequencia IS NULL) <> (cusec IN (SELECT cusec FROM analise.diag_base WHERE NOT pob_coberta_400m > 0))),
                     count(*) FILTER (WHERE prioritaria <> (alta_densidade AND NOT informacao_incompleta AND n_deficiencias > 0)),
                     count(*) FILTER (WHERE n_dimensoes <> deficiencia_acesso::int + deficiencia_servico::int),
                     count(*) FILTER (WHERE baixa_frequencia IS NULL)
              FROM analise.diag_classificacao""")
    reg("G05", "Classificação", "Indicadores binários coerentes", "OK" if not any(r[:5]) else "FALHA",
        f"incoerências — contagem: {r[0]}; texto: {r[1]}; nulos fora das seções sem cobertos: {r[2]}; prioritária: {r[3]}; "
        f"dimensões: {r[4]}; seções sem população coberta (diversidade/frequência não se aplicam): {r[5] // 2}")

    dt_ = sum(int((bd[bd.cenario == x.cenario.iloc[0]].merge(x, on="cusec").pipe(lambda y: y.tipologia_x != y.tipologia_y)).sum()) for x, _ in rec)
    r = um("SELECT count(*) FILTER (WHERE tipologia IS NULL), count(DISTINCT (cenario, cusec)) FROM analise.diag_classificacao")
    reg("G06", "Tipologia", "Uma categoria principal por seção, conforme a precedência", "OK" if dt_ == 0 and r[0] == 0 and r[1] == 1042 else "FALHA",
        f"divergências frente ao recálculo: {dt_}; sem categoria: {r[0]}")

    dr = 0
    for x, _ in rec:
        y = bd[bd.cenario == x.cenario.iloc[0]].merge(x[["cusec", "ranking"]], on="cusec", suffixes=("", "_rec"))
        dr += int((y.ranking.astype(float).fillna(-1) != y.ranking_rec.fillna(-1)).sum())
    r = um("""SELECT count(*) FILTER (WHERE prioritaria), count(DISTINCT ranking) FILTER (WHERE prioritaria), max(ranking) FILTER (WHERE prioritaria),
                     count(*) FILTER (WHERE NOT prioritaria AND ranking IS NOT NULL)
              FROM analise.diag_classificacao WHERE cenario = 'principal'""")
    reg("G07", "Ranking", "Ranking determinístico, contínuo e único", "OK" if dr == 0 and r[0] == r[1] == r[2] and r[3] == 0 else "FALHA",
        f"{r[0]} prioritárias com postos 1..{r[2]} únicos; divergências frente ao recálculo: {dr}; posto fora das prioritárias: {r[3]}")

    r = um("""SELECT (SELECT sum(pob_ine) FROM analise.diag_resultado_seccion), (SELECT sum(poblacion_total) FROM prep.poblacion_seccion),
                     (SELECT sum(pob_grade) FROM analise.diag_resultado_seccion), (SELECT sum(pob_estimada) FROM analise.pontos_demanda),
                     (SELECT count(*) FROM analise.diag_resultado_seccion d JOIN analise.indicadores_seccion_oferta i USING (cusec)
                       WHERE d.partidas_h_manha IS DISTINCT FROM i.partidas_h_manha OR d.linhas_manha IS DISTINCT FROM i.linhas_manha
                          OR d.pct_coberta_400m IS DISTINCT FROM i.pct_coberta_400m OR d.partidas_h_tarde IS DISTINCT FROM i.partidas_h_tarde
                          OR d.pob_sem_oferta_manha IS DISTINCT FROM i.pob_sem_oferta_manha)""")
    reg("G08", "Preservação", "População e indicadores originais preservados",
        "OK" if r[0] == r[1] and abs(r[2] - r[3]) < 1e-6 and r[4] == 0 else "FALHA",
        f"população INE {r[0]} = {r[1]}; grade {r[2]:.2f} = pontos {r[3]:.2f}; seções com indicador da Etapa 3 alterado: {r[4]}")

    r = um("""SELECT (SELECT sum(secoes) FROM analise.diag_sintese_distrito), (SELECT sum(pob_ine) FROM analise.diag_sintese_distrito),
                     (SELECT sum(secoes_prioritarias) FROM analise.diag_sintese_distrito),
                     (SELECT secoes FROM analise.diag_sintese_municipal WHERE cenario = 'principal' AND indicador = 'secoes_prioritarias'),
                     (SELECT sum(pob_ine_prioritarias) FROM analise.diag_sintese_distrito),
                     (SELECT pob_ine FROM analise.diag_sintese_municipal WHERE cenario = 'principal' AND indicador = 'secoes_prioritarias'),
                     (SELECT sum(secoes) FROM analise.diag_sintese_tipologia WHERE cenario = 'principal'),
                     (SELECT sum(pob_ine) FROM analise.diag_sintese_tipologia WHERE cenario = 'principal'),
                     (SELECT sum(tipo_a + tipo_b + tipo_c + tipo_d) FROM analise.diag_sintese_distrito),
                     (SELECT round(sum(pct_pob_prioritaria_municipal)::numeric, 9) FROM analise.diag_sintese_distrito)""")
    ok = r[0] == 521 and r[1] == 686741 and r[2] == r[3] == r[8] and r[4] == r[5] and r[6] == 521 and r[7] == 686741 and float(r[9]) == 100
    reg("G09", "Agregação", "Seção, tipologia, distrito e município coerentes", "OK" if ok else "FALHA",
        f"distritos: {r[0]} seções, {r[1]} hab.; prioritárias distritos {r[2]} = município {r[3]} = tipos A–D {r[8]}; "
        f"população prioritária {r[4]} = {r[5]}; tipologias: {r[6]} seções, {r[7]} hab.; soma das participações distritais {r[9]}%")

    r = um("""SELECT count(*) FILTER (WHERE (var_pct_tarde_manha IS NULL) <> (partidas_h_manha = 0)),
                     count(*) FILTER (WHERE pct_pob_perto_limiar_400m IS NULL),
                     count(*) FILTER (WHERE densidade_area_habitada_hab_km2 IS NULL),
                     count(*) FILTER (WHERE linhas_cob_manha IS NULL), count(*) FILTER (WHERE partidas_h_manha = 0),
                     count(*) FILTER (WHERE pct_coberta_400m IS NULL OR pob_ine IS NULL)
              FROM analise.diag_resultado_seccion""")
    reg("G10", "Nulos", "Nulos e denominadores zero tratados explicitamente", "OK" if r[0] == 0 and r[1] == 0 and r[5] == 0 else "FALHA",
        f"variação % nula sem manhã = 0: {r[0]} incoerências; seções com manhã = 0 (variação indefinida): {r[4]}; "
        f"sem população coberta (médias entre cobertos nulas): {r[3]}; densidade de área habitada nula: {r[2]}; nulos indevidos: {r[1] + r[5]}")

    r = um("""SELECT max(abs(dif_tarde_manha - (partidas_h_tarde - partidas_h_manha))),
                     count(*) FILTER (WHERE dif_tarde_manha < 0),
                     count(*) FILTER (WHERE padrao_temporal = 'baixa_frequencia_persistente' AND NOT (baixa_freq_manha AND baixa_freq_meio_dia AND baixa_freq_tarde)),
                     count(*) FILTER (WHERE padrao_temporal = 'baixa_frequencia_sobretudo_tarde' AND (baixa_freq_manha OR NOT baixa_freq_tarde)),
                     max(abs(mudanca_posicao_tarde_manha - (prank_tarde - prank_manha)))
              FROM analise.diag_resultado_seccion""")
    reg("G11", "Períodos", "Diferenças entre períodos coerentes", "OK" if r[0] < 1e-9 and r[1] == 475 and r[2] == 0 and r[3] == 0 and r[4] < 1e-12 else "FALHA",
        f"desvio máx. da diferença: {r[0]:.1e}; seções com redução à tarde: {r[1]} (Etapa 3: 475); padrões incoerentes: {r[2] + r[3]}")


TABELAS = {"diag_resultado_seccion": "cusec", "diag_limiares": "cenario, criterio", "diag_sintese_distrito": "cdis",
           "diag_sintese_municipal": "cenario, indicador", "diag_sensibilidade_resumo": "indicador", "diag_densidade_relacao": "indicador"}


def instantaneo(conn):
    return {t: df(conn, f"SELECT * FROM analise.{t} ORDER BY {o}").drop(columns=["geom"], errors="ignore") for t, o in TABELAS.items()}


def reproducao(conn):
    antes = instantaneo(conn)
    spec = importlib.util.spec_from_file_location("diag", caminho("scripts/13_diagnostico.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.executar(conn)
    depois = instantaneo(conn)
    iguais = {}
    for t in TABELAS:
        a, b = antes[t], depois[t]
        ok = a.shape == b.shape
        for c in a.columns:
            if not ok:
                break
            if pd.api.types.is_numeric_dtype(a[c]) and pd.api.types.is_numeric_dtype(b[c]):
                ok = np.allclose(a[c].astype(float), b[c].astype(float), equal_nan=True, rtol=1e-12, atol=1e-12)
            else:
                ok = a[c].astype(str).equals(b[c].astype(str))
        iguais[t] = ok
    reg("G12", "Reprodução", "Resultados idênticos após nova execução", "OK" if all(iguais.values()) else "FALHA",
        "; ".join(f"{t}: {'igual' if v else 'DIFERENTE'}" for t, v in iguais.items()))


def sensibilidade(conn):
    r = dict(conn.execute("SELECT indicador, valor FROM analise.diag_sensibilidade_resumo").fetchall())
    ok = r.get("secoes_so_principal", 0) == 0
    reg("G13", "Sensibilidade", "Prioritárias por quartis permanecem prioritárias com tercis", "OK" if ok else "LIMITACAO",
        f"nos dois: {int(r.get('secoes_prioritaria_nos_dois', 0))}; só quartis: {int(r.get('secoes_so_principal', 0))}; "
        f"só tercis: {int(r.get('secoes_so_tercis', 0))}; top 10 também no top 20 por tercis: {int(r['top10_principal_no_top20_tercis'])}; "
        f"Spearman dos postos comuns: {r['spearman_ranking_comuns']:.3f}; distritos com prioritárias: "
        f"{int(r['distritos_com_prioritarias_principal'])} x {int(r['distritos_com_prioritarias_tercis'])}")


def main():
    with conectar(CFG) as conn:
        testes(conn)
        reproducao(conn)
        sensibilidade(conn)
        execucao = dt.datetime.now(dt.timezone.utc)
        with conn.cursor() as cur:
            cur.executemany("INSERT INTO qa.resultado_testes VALUES (%s,%s,%s,%s,%s,%s)", [(execucao, *x) for x in RES])
        conn.commit()
    resumo = {s: sum(1 for x in RES if x[3] == s) for s in ("OK", "LIMITACAO", "FALHA")}
    linhas = ["# Testes de integridade — Etapa 4", "",
              f"Execução: {execucao.isoformat(timespec='seconds')} — OK: {resumo['OK']}, LIMITACAO: {resumo['LIMITACAO']}, FALHA: {resumo['FALHA']}",
              "", "Gerado por `scripts/14_testes_etapa4.py` (também em `qa.resultado_testes`, IDs com prefixo G). Limiares, flags,",
              "tipologia e ranking são recalculados de forma independente em pandas.", "",
              "| ID | Grupo | Verificação | Status | Detalhe |", "|---|---|---|---|---|"]
    linhas += [f"| {t} | {g} | {d} | **{s}** | {x.replace('|', '/')} |" for t, g, d, s, x in RES]
    caminho("docs/testes_etapa4.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(resumo)
    sys.exit(1 if resumo["FALHA"] else 0)


if __name__ == "__main__":
    main()
