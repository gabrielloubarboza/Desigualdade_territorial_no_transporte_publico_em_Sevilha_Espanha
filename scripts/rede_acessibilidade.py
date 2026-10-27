"""Grafo pedonal com pontos de ligação e buscas de menor caminho limitadas (Etapa 2).

As arestas utilizáveis (analise.rede_arestas) são divididas nos pontos onde as ligações de origens e
paradas tocam a rede. Ligações não entram no grafo: são somadas ao percurso (origem -> rede e
rede -> parada), o que impede que uma parada ou origem sirva de passagem entre componentes.
"""
from __future__ import annotations

from collections import defaultdict

import networkx as nx

EPS = 1e-3  # m: posição considerada coincidente com o nó extremo da aresta


def carregar(conn):
    arestas = conn.execute("""
        SELECT aresta_id, no_origem, no_destino, coalesce(no_inicio_geom, no_origem), comprimento_m
        FROM analise.rede_arestas WHERE utilizavel ORDER BY aresta_id""").fetchall()
    lig_o = conn.execute("""SELECT ligacao_id, origem_id, aresta_id, pos_na_aresta_m, distancia_m
                            FROM analise.ligacoes_origem ORDER BY ligacao_id""").fetchall()
    lig_p = conn.execute("""SELECT l.ligacao_id, l.stop_id, l.aresta_id, l.pos_na_aresta_m, l.distancia_m
                            FROM analise.ligacoes_parada l
                            JOIN analise.paradas_analise p USING (stop_id)
                            WHERE p.destino_analise ORDER BY l.ligacao_id""").fetchall()
    return arestas, lig_o, lig_p


def montar_grafo(arestas, ligacoes):
    """Retorna (G, no_da_ligacao, segmentos). `ligacoes`: iterável de (chave, aresta_id, pos_m)."""
    pos_por_aresta = defaultdict(set)
    for _, aid, pos in ligacoes:
        pos_por_aresta[aid].add(round(pos, 3))
    G = nx.Graph()
    segmentos = {}            # (n1, n2) -> (aresta_id, pos1, pos2) para reconstruir geometrias
    no_virtual = {}           # (aresta_id, pos) -> nó
    for aid, u, v, inicio, comp in arestas:
        fim = v if inicio == u else u
        pts = sorted(p for p in pos_por_aresta.get(aid, ()) if EPS < p < comp - EPS)
        nos = [inicio] + [f"a{aid}@{p:.3f}" for p in pts] + [fim]
        posicoes = [0.0] + pts + [comp]
        for p, n in zip(posicoes, nos):
            no_virtual[(aid, round(p, 3))] = n
        for i in range(len(nos) - 1):
            n1, n2, w = nos[i], nos[i + 1], posicoes[i + 1] - posicoes[i]
            if n1 == n2:
                continue
            if not G.has_edge(n1, n2) or G[n1][n2]["w"] > w:
                G.add_edge(n1, n2, w=w)
                segmentos[(n1, n2)] = segmentos[(n2, n1)] = (aid, posicoes[i], posicoes[i + 1])
    comp_por_aresta = {a[0]: a[4] for a in arestas}
    inicio_fim = {a[0]: (a[3], a[2] if a[3] == a[1] else a[1]) for a in arestas}

    def no_de(aid, pos):
        p = round(pos, 3)
        if p <= EPS:
            return inicio_fim[aid][0]
        if p >= comp_por_aresta[aid] - EPS:
            return inicio_fim[aid][1]
        return no_virtual[(aid, p)]

    no_da_ligacao = {chave: no_de(aid, pos) for chave, aid, pos in ligacoes}
    return G, no_da_ligacao, segmentos


def calcular(conn, limite_m: float, limite_proxima_m: float, tol: float):
    arestas, lig_o, lig_p = carregar(conn)
    G, no_lig, segmentos = montar_grafo(
        arestas, [(("o", l[0]), l[2], l[3]) for l in lig_o] + [(("p", l[0]), l[2], l[3]) for l in lig_p])

    origens_no_ = defaultdict(list)          # nó -> [(ligacao_id, origem_id, dist_ligacao)]
    for lid, oid, _, _, d in lig_o:
        origens_no_[no_lig[("o", lid)]].append((lid, oid, d))

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

    # 2) Parada mais próxima de cada origem, sem o limite de 400 m (fonte única virtual)
    H = G.copy()
    melhor_no = {}
    for lid_p, sid, _, _, dp in sorted(lig_p, key=lambda x: (x[4], x[1])):
        no = no_lig[("p", lid_p)]
        if no not in melhor_no:
            melhor_no[no] = (dp, sid, lid_p)
    for no, (dp, _, _) in melhor_no.items():
        H.add_edge("__PARADAS__", no, w=dp)
    dist, caminhos = nx.single_source_dijkstra(H, "__PARADAS__", cutoff=limite_proxima_m, weight="w")
    proxima = {}
    for no, itens in origens_no_.items():
        if no not in dist:
            continue
        dp, sid, lid_p = melhor_no[caminhos[no][1]]
        for lid_o, oid, do in itens:
            cand = (dist[no] + do, sid, lid_o, lid_p)
            if oid not in proxima or cand < proxima[oid]:
                proxima[oid] = cand
    return {"pares": pares, "proxima": proxima, "G": G, "no_lig": no_lig, "segmentos": segmentos,
            "n_nos": G.number_of_nodes(), "n_arestas": G.number_of_edges()}


def segmentos_do_caminho(res, lig_o_id: int, lig_p_id: int):
    """Lista (aresta_id, pos1, pos2) do caminho de rede entre duas ligações (para conferência)."""
    G, no_lig, seg = res["G"], res["no_lig"], res["segmentos"]
    nos = nx.dijkstra_path(G, no_lig[("o", lig_o_id)], no_lig[("p", lig_p_id)], weight="w")
    return [seg[(a, b)] for a, b in zip(nos, nos[1:])]
