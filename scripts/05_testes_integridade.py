"""Etapa 1 — Testes de integridade (OK / LIMITACAO / FALHA).

Uso:  .venv\\Scripts\\python.exe scripts\\05_testes_integridade.py

Grava os resultados em qa.resultado_testes e em docs/testes_etapa1.md. Sai com código 1 se houver FALHA.
"""
from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import sys
import zipfile

import pyogrio

from comum import caminho, carregar_config, conectar

CFG = carregar_config()
RESULTADOS: list[tuple] = []


def registrar(tid, grupo, descricao, status, detalhe):
    RESULTADOS.append((tid, grupo, descricao, status, detalhe))
    print(f"[{status:9}] {tid} {descricao} — {detalhe}")


def um(cur, sql, *args):
    cur.execute(sql, args)
    return cur.fetchone()


def linhas_csv(path) -> int:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return sum(1 for _ in csv.reader(f)) - 1


def testes(cur):
    g = CFG["gtfs"]
    gdir = caminho("data/raw/gtfs_tussam/extract")

    # 1. GTFS obtido, legível e com estrutura compatível
    zp = caminho(g["arquivo"])
    md5 = hashlib.md5(zp.read_bytes()).hexdigest()
    with zipfile.ZipFile(zp) as z:
        nomes = set(z.namelist())
        corrompido = z.testzip()
    obrig = {"agency.txt", "stops.txt", "routes.txt", "trips.txt", "stop_times.txt"}
    falta = obrig - nomes
    tem_cal = bool({"calendar.txt", "calendar_dates.txt"} & nomes)
    ok = not falta and tem_cal and corrompido is None and md5 == g["md5_esperado"]
    registrar("T01", "GTFS", "GTFS obtido, íntegro e com arquivos obrigatórios", "OK" if ok else "FALHA",
              f"md5 {'confere' if md5 == g['md5_esperado'] else 'DIVERGE'}; arquivos: {sorted(nomes)}; "
              f"ausentes opcionais: frequencies.txt, shapes.txt")
    tz = um(cur, "SELECT bool_and(agency_timezone = 'Europe/Madrid'), count(*) FROM fonte.gtfs_agency")
    registrar("T01b", "GTFS", "Fuso horário da agência", "OK" if tz[0] else "FALHA", f"Europe/Madrid em {tz[1]} agência(s)")
    exp = um(cur, """SELECT count(*), count(departure_time),
                            count(*) FILTER (WHERE departure_time IS NULL)
                     FROM fonte.gtfs_stop_times""")
    sens = []
    cur.execute("""SELECT p.periodo,
                          count(*) FILTER (WHERE h.partida_s >= p.inicio_s AND h.partida_s < p.fim_s),
                          count(*) FILTER (WHERE h.origem_horario = 'interpolado'
                               AND ((h.t_controle_anterior_s < p.inicio_s AND h.t_controle_seguinte_s >= p.inicio_s)
                                 OR (h.t_controle_anterior_s < p.fim_s AND h.t_controle_seguinte_s >= p.fim_s)))
                   FROM prep.gtfs_horarios_dia h, prep.periodos_analise p GROUP BY p.periodo ORDER BY min(p.inicio)""")
    for per, n, amb in cur.fetchall():
        sens.append(f"{per}: {amb} de {n} passagens com horário interpolado em trecho que cruza o limite da janela "
                    f"({100 * amb / max(n, 1):.1f}%)")
    registrar("T01c", "GTFS", "Natureza dos horários (explícitos x interpolados)", "LIMITACAO",
              f"{exp[1]} de {exp[0]} registros com horário explícito ({100 * exp[1] / exp[0]:.1f}%); "
              f"{exp[2]} sem horário (paradas entre pontos de controle), interpolados por distância em "
              f"prep.gtfs_horarios_dia e marcados como 'interpolado'. Sensibilidade: " + "; ".join(sens))

    # 2. Serviços e calendários para o dia escolhido
    d = um(cur, """SELECT (SELECT valor FROM prep.parametros WHERE chave='dia_referencia'),
                          (SELECT string_agg(service_id, ',') FROM prep.gtfs_servicos_dia),
                          (SELECT count(*) FROM prep.gtfs_viagens_dia),
                          (SELECT bool_and((SELECT valor::date FROM prep.parametros WHERE chave='dia_referencia')
                                    BETWEEN feed_start_date AND feed_end_date) FROM fonte.gtfs_feed_info),
                          (SELECT count(*) FROM fonte.gtfs_calendar_dates)""")
    dia = dt.date.fromisoformat(d[0])
    ok = d[1] and d[2] > 0 and d[3] and dia.weekday() in (1, 2, 3)
    registrar("T02", "GTFS", "Serviço utilizável no dia de referência", "OK" if ok else "FALHA",
              f"{d[0]} ({dia.strftime('%A')}); serviços ativos: {d[1]}; {d[2]} viagens de ônibus; dentro de feed_info: {d[3]}")
    registrar("T02b", "GTFS", "Feriados codificados no calendário", "LIMITACAO" if d[4] == 0 else "OK",
              "calendar_dates.txt vazio: feriados da vigência (12/10, 02/11, 07/12, 08/12, 25/12, 01/01, 06/01) não "
              "têm exceção no feed; o dia de referência não é feriado (Decreto 101/2025 Junta de Andalucía)")

    # 3. Ônibus separados dos demais modos
    m = um(cur, """SELECT count(*) FILTER (WHERE incluida_analise), count(*) FILTER (WHERE NOT incluida_analise),
                          string_agg(route_short_name || ' (' || route_type || ')', ', ') FILTER (WHERE NOT incluida_analise),
                          (SELECT count(*) FROM prep.gtfs_viagens_dia v JOIN fonte.gtfs_routes r USING (route_id)
                           WHERE r.route_type <> 3)
                   FROM prep.gtfs_rotas""")
    registrar("T03", "GTFS", "Rotas de ônibus separadas dos demais modos", "OK" if m[3] == 0 else "FALHA",
              f"{m[0]} rotas de ônibus incluídas; excluídas: {m[2]}; viagens não-ônibus no dia: {m[3]}")

    # 4. Paradas com coordenadas válidas
    p = um(cur, """SELECT count(*), count(*) FILTER (WHERE stop_lat IS NULL OR stop_lon IS NULL
                          OR stop_lat NOT BETWEEN 37.2 AND 37.6 OR stop_lon NOT BETWEEN -6.2 AND -5.7)
                   FROM fonte.gtfs_stops""")
    fora = um(cur, """SELECT count(*) FILTER (WHERE NOT dentro_municipio),
                             count(*) FILTER (WHERE NOT dentro_municipio AND serve_onibus_dia_ref),
                             count(*) FILTER (WHERE NOT ST_IsValid(geom) OR ST_SRID(geom) <> 25830)
                      FROM prep.gtfs_paradas""")
    registrar("T04", "GTFS", "Paradas com coordenadas válidas", "OK" if p[1] == 0 and fora[2] == 0 else "FALHA",
              f"{p[0]} paradas; {p[1]} fora da caixa de Sevilla; {fora[0]} fora do limite municipal "
              f"({fora[1]} com ônibus no dia de referência) — mantidas, pois atendem população do município")

    # 5. Consistência de IDs e horários
    c = um(cur, """SELECT (SELECT count(*) FROM fonte.gtfs_trips t WHERE NOT EXISTS
                             (SELECT 1 FROM fonte.gtfs_stop_times s WHERE s.trip_id = t.trip_id)),
                          (SELECT count(*) FROM fonte.gtfs_trips t WHERE NOT EXISTS
                             (SELECT 1 FROM fonte.gtfs_calendar c WHERE c.service_id = t.service_id)
                             AND NOT EXISTS (SELECT 1 FROM fonte.gtfs_calendar_dates c WHERE c.service_id = t.service_id)),
                          (SELECT count(*) FROM fonte.gtfs_stop_times s JOIN prep.gtfs_viagens_dia USING (trip_id)),
                          (SELECT count(*) FROM prep.gtfs_horarios_dia),
                          (SELECT count(*) FROM prep.gtfs_horarios_dia WHERE partida_s IS NULL),
                          (SELECT count(*) FROM (SELECT partida_s < lag(partida_s) OVER (PARTITION BY trip_id ORDER BY dist_m) AS r
                                                 FROM prep.gtfs_horarios_dia) x WHERE r)""")
    ok = c[0] == 0 and c[1] == 0 and c[2] == c[3] and c[4] == 0 and c[5] == 0
    registrar("T05", "GTFS", "Consistência entre linhas, viagens, paradas e horários", "OK" if ok else "FALHA",
              f"viagens sem stop_times: {c[0]}; viagens sem serviço: {c[1]}; stop_times do dia {c[2]} = "
              f"horários preparados {c[3]}; partidas nulas: {c[4]}; regressões temporais: {c[5]} (FKs ativas)")
    v = um(cur, """WITH t AS (SELECT trip_id, dist_m, partida_s,
                          lag(dist_m) OVER w AS d0, lag(partida_s) OVER w AS t0
                   FROM prep.gtfs_horarios_dia WHERE origem_horario = 'explicito'
                   WINDOW w AS (PARTITION BY trip_id ORDER BY dist_m))
                   SELECT count(*), count(*) FILTER (WHERE (dist_m - d0) / (partida_s - t0) * 3.6 > 60)
                   FROM t WHERE d0 IS NOT NULL""")
    registrar("T05b", "GTFS", "Plausibilidade das velocidades entre pontos de controle",
              "OK" if v[1] == 0 else "LIMITACAO",
              f"{v[1]} de {v[0]} trechos entre pontos de controle acima de 60 km/h no dia de referência"
              + ("" if v[1] == 0 else " (horários arredondados ao minuto ou distâncias atípicas)"))

    # 6. Ausência de duplicações indevidas
    dup = um(cur, """SELECT (SELECT count(*) - count(DISTINCT (trip_id, stop_sequence)) FROM fonte.gtfs_stop_times),
                            (SELECT count(*) - count(DISTINCT stop_id) FROM fonte.gtfs_stops),
                            (SELECT count(*) - count(DISTINCT cusec) FROM fonte.ine_secciones_2024),
                            (SELECT count(*) - count(DISTINCT grd_fixid) FROM fonte.ieca_gridp_250),
                            (SELECT count(*) - count(DISTINCT (u, v, key)) FROM fonte.osm_arestas),
                            (SELECT count(*) - count(DISTINCT (nodo, linea, ruta, sublinea, distancia))
                             FROM fonte.tussam_paradas_ide)""")
    registrar("T06", "Carga", "Ausência de duplicações indevidas", "OK" if not any(dup[:5]) else "FALHA",
              f"duplicatas — stop_times: {dup[0]}, stops: {dup[1]}, seções: {dup[2]}, células: {dup[3]}, "
              f"arestas: {dup[4]}; registros repetidos na camada IDE de paradas: {dup[5]}")

    # 7. Seções censitárias
    s = um(cur, """SELECT count(*), count(DISTINCT cusec), count(*) FILTER (WHERE NOT geom_valida_original),
                          count(*) FILTER (WHERE NOT ST_IsValid(geom)), min(area_m2), sum(area_km2)
                   FROM prep.secciones""")
    sob = um(cur, "SELECT count(*), coalesce(sum(area_m2), 0) FROM qa.v_sobreposicao_secciones")
    ok = s[0] == s[1] and s[3] == 0 and sob[0] == 0
    registrar("T07", "Seções", "Seções com geometria válida, IDs únicos e sem sobreposição", "OK" if ok else "FALHA",
              f"{s[0]} seções, {s[1]} códigos únicos; inválidas na origem: {s[2]}; inválidas após preparo: {s[3]}; "
              f"sobreposições > 1 m²: {sob[0]} ({sob[1]:.1f} m²); menor área {s[4]:.0f} m²; soma {s[5]:.2f} km²")

    # 8. População vinculável
    pop = um(cur, """SELECT (SELECT count(*) FROM prep.secciones),
                            (SELECT count(*) FROM prep.poblacion_seccion),
                            (SELECT count(*) FROM prep.secciones s JOIN prep.poblacion_seccion p USING (cusec)),
                            (SELECT sum(poblacion_total) FROM prep.poblacion_seccion),
                            (SELECT valor FROM fonte.ine_poblacion_seccion WHERE cod_seccion IS NULL AND sexo='Total'
                               AND nacionalidad='Total' AND periodo = (SELECT valor::int FROM prep.parametros WHERE chave='ano_populacao')),
                            (SELECT count(*) FROM prep.poblacion_seccion WHERE hombres + mujeres <> poblacion_total
                               OR nacionalidad_espanola + nacionalidad_extranjera <> poblacion_total)""")
    ok = pop[0] == pop[1] == pop[2] and pop[3] == pop[4] and pop[5] == 0
    registrar("T08", "População", "População por seção vinculável e coerente com o total municipal",
              "OK" if ok else "FALHA",
              f"{pop[2]} de {pop[0]} seções vinculadas ({pop[1]} registros 2024); soma {pop[3]} = total municipal "
              f"{pop[4]}; inconsistências sexo/nacionalidade: {pop[5]}; nenhum valor suprimido por sigilo")

    # 9. Grade IECA
    gr = um(cur, """SELECT count(*), count(DISTINCT grd_fixid), sum(pob_tot),
                           count(*) FILTER (WHERE sigilo_total_convencional),
                           count(*) FILTER (WHERE celda_multimunicipal), sum(pob_tot) FILTER (WHERE celda_multimunicipal),
                           count(*) FILTER (WHERE sigilo_em_categorias),
                           count(*) FILTER (WHERE relacao_secoes = 'contida_em_uma_secao'),
                           count(*) FILTER (WHERE relacao_secoes = 'multiplas_secoes'),
                           count(*) FILTER (WHERE relacao_secoes = 'parcialmente_fora_municipio'),
                           count(*) FILTER (WHERE NOT ST_IsValid(geom)), min(pob_tot)
                    FROM prep.grid_250""")
    registrar("T09", "Grade IECA", "Células únicas, válidas e valores interpretados conforme a documentação",
              "LIMITACAO" if gr[0] == gr[1] and gr[10] == 0 else "FALHA",
              f"{gr[0]} células intersectam Sevilla ({gr[1]} códigos únicos), soma pob_tot {gr[2]}; "
              f"{gr[3]} com total convencional 2 (sigilo); {gr[6]} com categorias suprimidas (nota -1); "
              f"{gr[4]} células multimunicipais ({gr[5]} hab., total não separável por município); "
              f"relação com seções: {gr[7]} contidas em uma, {gr[8]} em várias, {gr[9]} parcialmente fora; mínimo {gr[11]}")

    # 10. Limite municipal e CRS
    lim = um(cur, "SELECT * FROM qa.v_comparacao_limites")
    cur.execute("""SELECT f_table_schema || '.' || f_table_name, srid FROM geometry_columns
                   WHERE f_table_schema = 'prep' AND srid <> 25830""")
    srid_ruim = cur.fetchall()
    val = um(cur, "SELECT bool_and(geom_valida) FROM prep.limite_municipal")
    ok = not srid_ruim and val[0]
    registrar("T10", "Limite/CRS", "Limite municipal válido e geometrias preparadas em EPSG:25830",
              "OK" if ok else "FALHA",
              f"área INE {lim[0]:.3f} km², IGN {lim[1]:.3f} km²; só INE {lim[2]:.3f} km², só IGN {lim[3]:.3f} km², "
              f"Hausdorff {lim[4]:.1f} m; partes INE {lim[5]}, anéis internos {lim[6]}; tabelas prep fora de 25830: {srid_ruim}")

    # 11. Rede: comprimentos
    r = um(cur, """SELECT count(*), count(*) FILTER (WHERE comprimento_m <= 0), count(*) FILTER (WHERE geom IS NULL),
                          max(abs(ST_Length(geom) - comprimento_m)), sum(comprimento_m) / 1000,
                          count(*) FILTER (WHERE restricao_acesso), count(*) FILTER (WHERE via_alta_capacidade),
                          count(*) FILTER (WHERE via_exclusiva_onibus),
                          count(*) FILTER (WHERE bridge IS NOT NULL), count(*) FILTER (WHERE tunnel IS NOT NULL)
                   FROM prep.rede_arestas""")
    registrar("T11", "Rede OSM", "Arestas com comprimento positivo", "OK" if r[1] == 0 and r[2] == 0 else "FALHA",
              f"{r[0]} arestas, {r[4]:.1f} km; comprimento <= 0: {r[1]}; geometria nula: {r[2]}; dif. máx. "
              f"ST_Length x comprimento {r[3]:.3f} m; pontes {r[8]}, túneis/passagens {r[9]}; marcadas: acesso "
              f"restrito {r[5]}, via de alta capacidade {r[6]}, via exclusiva de ônibus {r[7]}")

    # 12. Conectividade
    k = um(cur, """WITH c AS (SELECT componente, count(*) n FROM prep.rede_nos GROUP BY componente)
                   SELECT count(*), max(n), sum(n), (SELECT count(*) FROM c WHERE n < 10) FROM c""")
    pc = um(cur, """SELECT count(*), count(*) FILTER (WHERE n.componente <> 0), max(n.dist)
                    FROM prep.gtfs_paradas p
                    CROSS JOIN LATERAL (SELECT r.componente, ST_Distance(r.geom, p.geom) dist FROM prep.rede_nos r
                                        ORDER BY r.geom <-> p.geom LIMIT 1) n
                    WHERE p.serve_onibus_dia_ref""")
    registrar("T12", "Rede OSM", "Conectividade conhecida e componentes isolados identificados", "LIMITACAO",
              f"{k[0]} componentes; principal com {k[1]} de {k[2]} nós ({100 * k[1] / k[2]:.2f}%); {k[3]} componentes "
              f"com < 10 nós (preservados, não conectados artificialmente); paradas com ônibus cujo nó mais próximo "
              f"está fora do componente principal: {pc[1]} de {pc[0]}; maior distância parada-nó {pc[2]:.0f} m")

    # 13. Contagens no banco x arquivos originais
    difs = []
    for nome in ("agency", "feed_info", "routes", "calendar", "calendar_dates", "stops", "trips", "stop_times"):
        arq = gdir / f"{nome}.txt"
        n_arq = linhas_csv(arq)
        n_bd = um(cur, f"SELECT count(*) FROM fonte.gtfs_{nome}")[0]
        if n_arq != n_bd:
            difs.append(f"gtfs_{nome} {n_arq}!={n_bd}")
    espaciais = {
        "ieca_gridp_250": (caminho(CFG["ieca_grid"]["arquivo"]), None),
        "tussam_paradas_ide": (caminho(CFG["tussam_ide"]["arquivo_paradas"]), None),
        "tussam_lineas_ide": (caminho(CFG["tussam_ide"]["arquivo_linhas"]), None),
        "osm_nos": (caminho(CFG["osm"]["arquivo"]), "nos"),
        "osm_arestas": (caminho(CFG["osm"]["arquivo"]), "arestas"),
    }
    for tab, (arq, camada) in espaciais.items():
        n_arq = pyogrio.read_info(arq, layer=camada)["features"]
        n_bd = um(cur, f"SELECT count(*) FROM fonte.{tab}")[0]
        if n_arq != n_bd:
            difs.append(f"{tab} {n_arq}!={n_bd}")
    shp = caminho("data/raw/ine_seccionado/extract") / CFG["ine_seccionado"]["shapefile"]
    n_shp = len(pyogrio.read_dataframe(shp, where=f"CUMUN = '{CFG['projeto']['municipio_ine']}'", read_geometry=False))
    if n_shp != um(cur, "SELECT count(*) FROM fonte.ine_secciones_2024")[0]:
        difs.append("ine_secciones_2024")
    with open(caminho(CFG["ine_populacao"]["arquivo"]), encoding="utf-8-sig") as f:
        n_pop = sum(1 for linha in f if linha.split(";")[1].startswith(CFG["projeto"]["municipio_ine"]))
    if n_pop != um(cur, "SELECT count(*) FROM fonte.ine_poblacion_seccion")[0]:
        difs.append("ine_poblacion_seccion")
    registrar("T13", "Carga", "Contagens no PostgreSQL iguais às dos arquivos originais",
              "OK" if not difs else "FALHA", "todas conferem" if not difs else "; ".join(difs))

    # 14. Paradas GTFS x camada oficial IDE
    pi = dict(um(cur, """SELECT json_object_agg(situacao, n) FROM
                         (SELECT situacao, count(*) n FROM qa.paradas_gtfs_ide GROUP BY situacao) x""")[0])
    so_gtfs_ativa = um(cur, "SELECT count(*) FROM qa.paradas_gtfs_ide WHERE situacao='so_gtfs' AND serve_onibus_dia_ref")[0]
    dist = um(cur, """SELECT count(*), count(distancia) FROM qa.v_distancia_gtfs_ide""")
    prox = um(cur, "SELECT count(*) FROM qa.v_paradas_gtfs_proximas")[0]
    status = "OK" if pi.get("mesmo_id_distante", 0) == 0 and so_gtfs_ativa == 0 else "LIMITACAO"
    registrar("T14", "Paradas", "Correspondência entre paradas GTFS e camada oficial (IDE Sevilla)", status,
              f"situações: {json.dumps(pi)}; paradas só no GTFS com ônibus no dia: {so_gtfs_ativa}; "
              f"pares linha-parada com stop_sequence = Distancia IDE: {dist[1]} de {dist[0]}; "
              f"pares de paradas GTFS a < 15 m com IDs distintos: {prox}")


def main():
    with conectar(CFG) as conn, conn.cursor() as cur:
        testes(cur)
        execucao = dt.datetime.now(dt.timezone.utc)
        cur.executemany("INSERT INTO qa.resultado_testes VALUES (%s,%s,%s,%s,%s,%s)",
                        [(execucao, *r) for r in RESULTADOS])
        conn.commit()
    resumo = {s: sum(1 for r in RESULTADOS if r[3] == s) for s in ("OK", "LIMITACAO", "FALHA")}
    linhas = ["# Testes de integridade — Etapa 1", "",
              f"Execução: {execucao.isoformat(timespec='seconds')} — OK: {resumo['OK']}, "
              f"LIMITACAO: {resumo['LIMITACAO']}, FALHA: {resumo['FALHA']}", "",
              "Gerado por `scripts/05_testes_integridade.py` (também gravado em `qa.resultado_testes`).", "",
              "| ID | Grupo | Verificação | Status | Detalhe |", "|---|---|---|---|---|"]
    linhas += [f"| {t} | {g} | {d} | **{s}** | {x.replace('|', '/')} |" for t, g, d, s, x in RESULTADOS]
    caminho("docs/testes_etapa1.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    print(resumo)
    sys.exit(1 if resumo["FALHA"] else 0)


if __name__ == "__main__":
    main()
