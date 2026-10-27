"""Etapa 2 — Barreiras físicas e áreas não residenciais do OpenStreetMap (OSMnx).

Uso:  .venv\\Scripts\\python.exe scripts\\06_barreiras_osm.py [--forcar]

Usadas apenas para (a) impedir que as ligações ponto→rede atravessem rios, ferrovias ou vias expressas
e (b) evitar pontos de demanda sobre água, parques ou terrenos ferroviários. Mesma área da rede (limite INE + 1.000 m).
Saída: data/raw/osm_barreiras/osm_barreiras.gpkg (camadas `poligonos` e `linhas`, EPSG:25830).
"""
from __future__ import annotations

import json
import sys

import geopandas as gpd
import osmnx as ox
import pandas as pd
import pyogrio

from comum import agora_utc, caminho, carregar_config, hash_arquivo, registrar_fonte

CFG = carregar_config()
FORCAR = "--forcar" in sys.argv
CRS = CFG["projeto"]["crs_metrico"]
TAGS = {
    "natural": ["water"],
    "waterway": ["riverbank", "river", "canal", "dock"],
    "railway": ["rail", "light_rail", "narrow_gauge"],
    "highway": ["motorway", "motorway_link", "trunk", "trunk_link"],
    "leisure": ["park"],
    "landuse": ["railway"],
}
COLUNAS = ["natural", "water", "waterway", "railway", "highway", "leisure", "landuse", "name", "bridge", "tunnel",
           "layer", "service", "foot", "sidewalk", "usage"]


def classificar(row) -> str:
    if row.get("natural") == "water" or row.get("waterway") in ("riverbank", "dock"):
        return "agua"
    if row.get("waterway") in ("river", "canal"):
        return "curso_agua"
    if isinstance(row.get("railway"), str) and row["railway"] in TAGS["railway"]:
        return "ferrovia"
    if isinstance(row.get("highway"), str) and row["highway"] in TAGS["highway"]:
        return "via_alta_capacidade"
    if row.get("leisure") == "park":
        return "parque"
    if row.get("landuse") == "railway":
        return "terreno_ferroviario"
    return "outro"


def main():
    destino = caminho("data/raw/osm_barreiras/osm_barreiras.gpkg")
    if destino.exists() and not FORCAR:
        print("Barreiras já obtidas; use --forcar para baixar novamente.")
        return
    cache = caminho("data/raw/osm_cache")
    ox.settings.cache_folder = str(cache)
    ox.settings.use_cache = True
    shp = caminho("data/raw/ine_seccionado/extract") / CFG["ine_seccionado"]["shapefile"]
    sec = pyogrio.read_dataframe(shp, where=f"CUMUN = '{CFG['projeto']['municipio_ine']}'").to_crs(CRS)
    area = gpd.GeoSeries([sec.union_all().buffer(CFG["osm"]["margem_m"])], crs=CRS).to_crs(4326).iloc[0]
    inicio = agora_utc()
    f = ox.features_from_polygon(area, tags=TAGS).reset_index()
    f = f[[c for c in ["element", "id", *COLUNAS, "geometry"] if c in f.columns]].copy()
    f["classe"] = f.apply(classificar, axis=1)
    f = f[f.classe != "outro"].to_crs(CRS)
    f["osm_id"] = f["element"].astype(str) + "/" + f["id"].astype(str)
    f = f.drop(columns=["element", "id"])
    for col in f.columns:
        if col != "geometry":
            f[col] = f[col].map(lambda v: None if (not isinstance(v, (list, str)) and pd.isna(v)) else
                                (";".join(map(str, v)) if isinstance(v, list) else str(v)))
    poli = f[f.geom_type.isin(["Polygon", "MultiPolygon"])]
    lin = f[f.geom_type.isin(["LineString", "MultiLineString"])]
    destino.parent.mkdir(parents=True, exist_ok=True)
    destino.unlink(missing_ok=True)
    pyogrio.write_dataframe(poli, destino, layer="poligonos", driver="GPKG")
    pyogrio.write_dataframe(lin, destino, layer="linhas", driver="GPKG", append=True)
    carimbos = sorted({json.loads(p.read_text(encoding="utf-8")).get("osm3s", {}).get("timestamp_osm_base")
                       for p in cache.glob("*.json")} - {None})
    resumo = {"poligonos": poli.classe.value_counts().to_dict(), "linhas": lin.classe.value_counts().to_dict()}
    print(json.dumps(resumo, ensure_ascii=False))
    registrar_fonte("osm_barreiras", {
        "descricao": "Feições OSM de barreira (água, cursos d'água, ferrovias, autovias/trunk) e parques",
        "produtor": "Contribuidores do OpenStreetMap, via Overpass API (OSMnx features_from_polygon)",
        "url": ox.settings.overpass_url, "data_obtencao": inicio, "timestamp_osm_base": carimbos,
        "tags": TAGS, "arquivo": "data/raw/osm_barreiras/osm_barreiras.gpkg", "formato": "GeoPackage (EPSG:25830)",
        "licenca": "ODbL 1.0 — © OpenStreetMap contributors", "sha256": hash_arquivo(destino),
        "tamanho_bytes": destino.stat().st_size, "autenticacao": "não", **resumo,
    })


if __name__ == "__main__":
    main()
