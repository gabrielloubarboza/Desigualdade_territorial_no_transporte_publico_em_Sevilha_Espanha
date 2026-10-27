"""Etapa 2 — Acessibilidade caminhável (até 400 m) às paradas de ônibus TUSSAM.

Uso:  .venv\\Scripts\\python.exe scripts\\07_acessibilidade.py

Sequência: carrega as barreiras OSM em `fonte`, prepara a rede utilizável (sql/05), calcula os
componentes conexos (NetworkX), cria parcelas e pontos de demanda (sql/06), liga origens e paradas
à rede (sql/07), calcula os percursos limitados (rede_acessibilidade.py) e agrega os resultados
(sql/08). Idempotente: recria apenas os objetos do schema `analise`.
"""
from __future__ import annotations

import time

import geopandas as gpd
import networkx as nx
from sqlalchemy import create_engine

import rede_acessibilidade as ra
from comum import caminho, carregar_config, conectar, conninfo

CFG = carregar_config()
AC = CFG["acessibilidade"]


def sql(conn, arquivo):
    t = time.time()
    conn.execute(caminho(f"sql/{arquivo}").read_text(encoding="utf-8"))
    conn.commit()
    print(f"  sql/{arquivo} ({time.time() - t:.0f} s)")


def carregar_barreiras(conn):
    ci = dict(p.split("=", 1) for p in conninfo(CFG).split())
    engine = create_engine(f"postgresql+psycopg://{ci['user']}@{ci['host']}:{ci['port']}/{ci['dbname']}")
    conn.execute("DROP TABLE IF EXISTS fonte.osm_barreiras_poligonos, fonte.osm_barreiras_linhas CASCADE")
    conn.commit()
    for camada in ("poligonos", "linhas"):
        g = gpd.read_file(caminho("data/raw/osm_barreiras/osm_barreiras.gpkg"), layer=camada).rename_geometry("geom")
        g.to_postgis(f"osm_barreiras_{camada}", engine, schema="fonte", if_exists="fail", index=False)
        conn.execute(f"ALTER TABLE fonte.osm_barreiras_{camada} ADD PRIMARY KEY (osm_id)")
        print(f"  fonte.osm_barreiras_{camada}: {len(g)}")
    conn.commit()
    engine.dispose()


def parametros(conn):
    conn.execute("CREATE SCHEMA IF NOT EXISTS analise")
    conn.execute("DROP TABLE IF EXISTS analise.parametros")
    conn.execute("CREATE TABLE analise.parametros (chave text PRIMARY KEY, valor text NOT NULL)")
    with conn.cursor() as cur:
        cur.executemany("INSERT INTO analise.parametros VALUES (%s, %s)", [(k, str(v)) for k, v in AC.items()])
    conn.commit()


def componentes(conn):
    e = conn.execute("SELECT no_origem, no_destino FROM analise.rede_arestas WHERE utilizavel").fetchall()
    G = nx.Graph()
    G.add_edges_from(e)
    comps = sorted(nx.connected_components(G), key=lambda c: (-len(c), min(c)))
    conn.execute("DROP TABLE IF EXISTS analise.rede_componentes CASCADE")
    conn.execute("""CREATE TABLE analise.rede_componentes (
                        no_id bigint PRIMARY KEY, componente integer NOT NULL, n_nos integer NOT NULL)""")
    with conn.cursor() as cur, cur.copy("COPY analise.rede_componentes FROM STDIN") as cp:
        for i, c in enumerate(comps):
            for n in c:
                cp.write_row((n, i, len(c)))
    conn.execute("CREATE INDEX ON analise.rede_componentes (componente)")
    conn.execute("""COMMENT ON TABLE analise.rede_componentes IS
                    'Componentes conexos da rede utilizável (0 = principal, depois por tamanho decrescente)'""")
    conn.execute("ALTER TABLE analise.rede_arestas ADD COLUMN IF NOT EXISTS componente integer")
    conn.execute("""UPDATE analise.rede_arestas a SET componente = c.componente
                    FROM analise.rede_componentes c WHERE c.no_id = a.no_origem AND a.utilizavel""")
    conn.commit()
    print(f"  {len(comps)} componentes; principal com {len(comps[0])} nós")


def gravar(conn, res):
    conn.execute("DROP TABLE IF EXISTS analise.origem_parada_400m CASCADE")
    conn.execute("""CREATE TABLE analise.origem_parada_400m (
        origem_id text NOT NULL, stop_id text NOT NULL,
        distancia_m double precision NOT NULL,          -- ligação origem + rede + ligação parada
        distancia_rede_m double precision NOT NULL,
        distancia_ligacao_origem_m double precision NOT NULL,
        distancia_ligacao_parada_m double precision NOT NULL,
        ligacao_origem_id integer NOT NULL, ligacao_parada_id integer NOT NULL,
        PRIMARY KEY (origem_id, stop_id))""")
    with conn.cursor() as cur, cur.copy("COPY analise.origem_parada_400m FROM STDIN") as cp:
        for (oid, sid), (tot, lo, lp, drede, do, dp) in sorted(res["pares"].items()):
            cp.write_row((oid, sid, tot, drede, do, dp, lo, lp))
    conn.execute("DROP TABLE IF EXISTS analise.parada_mais_proxima CASCADE")
    conn.execute("""CREATE TABLE analise.parada_mais_proxima (
        origem_id text PRIMARY KEY, stop_id text NOT NULL, distancia_m double precision NOT NULL,
        ligacao_origem_id integer NOT NULL, ligacao_parada_id integer NOT NULL)""")
    with conn.cursor() as cur, cur.copy("COPY analise.parada_mais_proxima FROM STDIN") as cp:
        for oid, (d, sid, lo, lp) in sorted(res["proxima"].items()):
            cp.write_row((oid, sid, d, lo, lp))
    conn.execute("CREATE INDEX ON analise.origem_parada_400m (stop_id)")
    conn.execute("""COMMENT ON TABLE analise.origem_parada_400m IS
        'Todas as paradas de ônibus com serviço em 21/10/2026 alcançáveis em até 400 m de caminhada por origem'""")
    conn.execute("""COMMENT ON TABLE analise.parada_mais_proxima IS
        'Parada com serviço mais próxima pela rede (sem limite de 400 m, até 5 km)'""")
    conn.commit()
    print(f"  {len(res['pares'])} pares origem-parada; {len(res['proxima'])} origens com parada alcançável na rede")


def main():
    t0 = time.time()
    with conectar(CFG) as conn:
        print("[barreiras e parâmetros]")
        carregar_barreiras(conn)
        parametros(conn)
        print("[rede utilizável]")
        sql(conn, "05_analise_rede.sql")
        componentes(conn)
        print("[demanda e ligações]")
        sql(conn, "06_analise_demanda.sql")
        sql(conn, "07_analise_ligacoes.sql")
        print("[percursos na rede]")
        t = time.time()
        res = ra.calcular(conn, AC["limite_m"], AC["limite_distancia_mais_proxima_m"], AC["tolerancia_m"])
        print(f"  grafo: {res['n_nos']} nós, {res['n_arestas']} arestas ({time.time() - t:.0f} s)")
        gravar(conn, res)
        print("[resultados]")
        sql(conn, "08_analise_resultados.sql")
    print(f"Concluído em {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
