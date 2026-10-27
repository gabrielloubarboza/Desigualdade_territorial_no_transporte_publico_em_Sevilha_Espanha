"""Etapa 1 — Rede caminhável OpenStreetMap (OSMnx/NetworkX) para Sevilla + margem externa.

Uso:  .venv\\Scripts\\python.exe scripts\\03_rede_osm.py [--forcar]

- Área: limite municipal derivado do seccionado INE 2024, com margem de `osm.margem_m` metros.
- Filtro de rede: network_type='walk' do OSMnx (exclui vias com foot=no, motorways, etc.).
- retain_all=True: componentes desconectados são preservados e apenas identificados (não conectados
  artificialmente).
- Saída: data/processed/rede_caminhavel_osm.gpkg (camadas `nos` e `arestas`, EPSG:25830, rede não
  direcionada) e registro no manifesto de fontes.
"""
from __future__ import annotations

import json
import sys

import networkx as nx
import osmnx as ox
import pyogrio

from comum import agora_utc, caminho, carregar_config, hash_arquivo, registrar_fonte

CFG = carregar_config()
FORCAR = "--forcar" in sys.argv
CRS = CFG["projeto"]["crs_metrico"]
TAGS_VIA = ["highway", "name", "oneway", "access", "foot", "footway", "sidewalk", "crossing", "bridge",
            "tunnel", "layer", "service", "surface", "area", "lit", "est_width"]


def area_estudo():
    shp = caminho("data/raw/ine_seccionado/extract") / CFG["ine_seccionado"]["shapefile"]
    sec = pyogrio.read_dataframe(shp, where=f"CUMUN = '{CFG['projeto']['municipio_ine']}'")
    limite = sec.to_crs(CRS).union_all()
    return limite.buffer(CFG["osm"]["margem_m"]), sec.crs


def main():
    destino = caminho(CFG["osm"]["arquivo"])
    if destino.exists() and not FORCAR:
        print("Rede já existe; use --forcar para baixar novamente.")
        return
    cache = caminho("data/raw/osm_cache")
    ox.settings.cache_folder = str(cache)
    ox.settings.use_cache = True
    ox.settings.log_console = False
    ox.settings.useful_tags_way = TAGS_VIA
    ox.settings.useful_tags_node = ["highway", "crossing", "barrier", "kerb", "railway"]

    area_25830, _ = area_estudo()
    import geopandas as gpd
    area_4326 = gpd.GeoSeries([area_25830], crs=CRS).to_crs(4326).iloc[0]
    inicio = agora_utc()
    G = ox.graph_from_polygon(area_4326, network_type=CFG["osm"]["network_type"], simplify=True,
                              retain_all=True, truncate_by_edge=True)
    print(f"Grafo bruto: {G.number_of_nodes()} nós, {G.number_of_edges()} arestas (dirigido)")

    Gp = ox.project_graph(G, to_crs=f"EPSG:{CRS}")
    Gu = ox.convert.to_undirected(Gp)
    comps = sorted(nx.connected_components(Gu), key=len, reverse=True)
    comp_id = {n: i for i, c in enumerate(comps) for n in c}
    nx.set_node_attributes(Gu, comp_id, "componente")

    nos, arestas = ox.convert.graph_to_gdfs(Gu)
    nos = nos.reset_index()
    arestas = arestas.reset_index()
    arestas["componente"] = arestas.u.map(comp_id)
    arestas["comprimento_m"] = arestas.geometry.length
    arestas = arestas.rename(columns={"length": "comprimento_osmnx_m"})
    # Listas (vias simplificadas que juntam vários way) viram texto para armazenamento
    for df in (nos, arestas):
        for col in df.columns:
            if col != "geometry" and df[col].map(lambda v: isinstance(v, (list, set))).any():
                df[col] = df[col].map(lambda v: ";".join(map(str, v)) if isinstance(v, (list, set)) else v)
    destino.parent.mkdir(parents=True, exist_ok=True)
    if destino.exists():
        destino.unlink()
    pyogrio.write_dataframe(nos, destino, layer="nos", driver="GPKG")
    pyogrio.write_dataframe(arestas, destino, layer="arestas", driver="GPKG", append=True)

    # Data-base dos dados OSM (timestamp do Overpass registrado nas respostas em cache)
    carimbos = set()
    for f in cache.glob("*.json"):
        try:
            carimbos.add(json.loads(f.read_text(encoding="utf-8"))["osm3s"]["timestamp_osm_base"])
        except (KeyError, ValueError):
            pass
    tam = [len(c) for c in comps]
    resumo = {
        "n_nos": len(nos), "n_arestas": len(arestas),
        "extensao_total_km": round(arestas.comprimento_m.sum() / 1000, 2),
        "n_componentes": len(comps), "maior_componente_nos": tam[0],
        "pct_nos_maior_componente": round(100 * tam[0] / len(nos), 3),
        "componentes_10_maiores": tam[:10],
    }
    print(json.dumps(resumo, indent=1))
    registrar_fonte("osm_rede_caminhavel", {
        "descricao": "Rede pedonal OpenStreetMap (OSMnx network_type='walk', simplificada, não direcionada)",
        "produtor": "Contribuidores do OpenStreetMap, via Overpass API",
        "url": ox.settings.overpass_url, "data_obtencao": inicio,
        "timestamp_osm_base": sorted(carimbos), "arquivo": CFG["osm"]["arquivo"],
        "area": f"limite municipal (seccionado INE 2024) + {CFG['osm']['margem_m']} m",
        "formato": "GeoPackage (EPSG:25830)", "licenca": "ODbL 1.0 — © OpenStreetMap contributors",
        "sha256": hash_arquivo(destino), "tamanho_bytes": destino.stat().st_size, "autenticacao": "não",
        "osmnx": ox.__version__, "networkx": nx.__version__, **resumo,
    })


if __name__ == "__main__":
    main()
