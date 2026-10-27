"""Etapa 1 — Carga dos dados originais no PostgreSQL/PostGIS e preparação (schemas fonte, prep, qa).

Uso:  .venv\\Scripts\\python.exe scripts\\04_carregar_banco.py

Pré-requisito: banco criado com sql/00_criar_banco.sql e senha disponível no pgpass (ou PGPASSWORD).
A carga é idempotente: recria apenas as tabelas deste projeto.
"""
from __future__ import annotations

import csv
import json

import geopandas as gpd
import pandas as pd
import pyogrio
from sqlalchemy import create_engine

from comum import MANIFESTO, caminho, carregar_config, conectar, conninfo

CFG = carregar_config()
SQL = caminho("sql")
GTFS_DIR = caminho("data/raw/gtfs_tussam/extract")
GTFS_ORDEM = ["agency", "feed_info", "routes", "calendar", "calendar_dates", "stops", "trips", "stop_times"]


def executar_sql(conn, arquivo: str) -> None:
    print(f"  executando sql/{arquivo}")
    conn.execute((SQL / arquivo).read_text(encoding="utf-8"))
    conn.commit()


def parametros(conn) -> None:
    g = CFG["gtfs"]
    with conn.cursor() as cur:
        cur.executemany("INSERT INTO prep.parametros VALUES (%s, %s)", [
            ("dia_referencia", g["dia_referencia"]),
            ("ano_populacao", str(CFG["ine_populacao"]["ano"])),
            ("crs_metrico", str(CFG["projeto"]["crs_metrico"])),
            ("municipio_ine", CFG["projeto"]["municipio_ine"]),
            ("gtfs_url", g["url"]),
        ])
        cur.executemany("INSERT INTO prep.periodos_analise (periodo, inicio, fim) VALUES (%s, %s, %s)",
                        [(k, v[0], v[1]) for k, v in g["periodos"].items()])
    conn.commit()


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


def ler_populacao_ine() -> pd.DataFrame:
    c = CFG["ine_populacao"]
    # Arquivo em UTF-8 com BOM (apesar do cabeçalho HTTP declarar ISO-8859-15)
    df = pd.read_csv(caminho(c["arquivo"]), sep=";", dtype=str, encoding="utf-8-sig", keep_default_na=False)
    df.columns = [x.strip() for x in df.columns]
    df = df[df["Municipios"].str.startswith(CFG["projeto"]["municipio_ine"])].copy()
    total = df["Total"].str.strip().str.strip('"').str.replace(".", "", regex=False)
    out = pd.DataFrame({
        "provincia": df["Provincias"], "municipio": df["Municipios"],
        "seccion": df["Secciones"].replace("", None),
        "cod_seccion": df["Secciones"].str.split(" ").str[0].replace("", None),
        "sexo": df["Sexo"], "nacionalidad": df["Nacionalidad"], "periodo": df["Periodo"].astype(int),
        "valor_original": df["Total"],
        "valor": pd.to_numeric(total.replace("", None), errors="raise").astype("Int64"),
    }).reset_index(drop=True)
    out.insert(0, "id", range(1, len(out) + 1))
    return out


def preparar_gdf(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    gdf = gdf.rename_geometry("geom")
    gdf.columns = [c.lower() for c in gdf.columns]
    return gdf.set_geometry("geom")


def carregar_espaciais(conn) -> dict:
    ci = dict(p.split("=", 1) for p in conninfo(CFG).split())
    engine = create_engine(f"postgresql+psycopg://{ci['user']}@{ci['host']}:{ci['port']}/{ci['dbname']}")

    shp = caminho("data/raw/ine_seccionado/extract") / CFG["ine_seccionado"]["shapefile"]
    ign = gpd.read_file(caminho(CFG["ign_limite"]["arquivo"]))
    ign = ign[["gml_id", "nationalCode", "localId", "namespace", "text", "beginLifespanVersion", "geometry"]]
    camadas = {
        "ine_secciones_2024": pyogrio.read_dataframe(shp, where=f"CUMUN = '{CFG['projeto']['municipio_ine']}'"),
        "ieca_gridp_250": gpd.read_file(caminho(CFG["ieca_grid"]["arquivo"])),
        "tussam_paradas_ide": gpd.read_file(caminho(CFG["tussam_ide"]["arquivo_paradas"])),
        "tussam_lineas_ide": gpd.read_file(caminho(CFG["tussam_ide"]["arquivo_linhas"])),
        "ign_limite_municipal": ign,
        "osm_nos": gpd.read_file(caminho(CFG["osm"]["arquivo"]), layer="nos"),
        "osm_arestas": gpd.read_file(caminho(CFG["osm"]["arquivo"]), layer="arestas"),
    }
    contagens = {}
    with conn.cursor() as cur:
        for nome in [*camadas, "ine_poblacion_seccion"]:
            cur.execute(f"DROP TABLE IF EXISTS fonte.{nome} CASCADE")
    conn.commit()
    for nome, gdf in camadas.items():
        if gdf.crs is None:
            raise RuntimeError(f"{nome} sem CRS declarado")
        gdf = preparar_gdf(gdf)
        gdf.to_postgis(nome, engine, schema="fonte", if_exists="fail", index=False, chunksize=5000)
        contagens[nome] = len(gdf)
        print(f"  fonte.{nome}: {len(gdf)} (EPSG:{gdf.crs.to_epsg()})")
    pop = ler_populacao_ine()
    pop.to_sql("ine_poblacion_seccion", engine, schema="fonte", if_exists="fail", index=False)
    contagens["ine_poblacion_seccion"] = len(pop)
    print(f"  fonte.ine_poblacion_seccion: {len(pop)}  sexo={sorted(pop.sexo.unique())} "
          f"nacionalidad={sorted(pop.nacionalidad.unique())}")
    engine.dispose()
    return contagens


def carregar_metadados(conn) -> None:
    man = json.loads(MANIFESTO.read_text(encoding="utf-8"))
    with conn.cursor() as cur:
        for fid, m in man.items():
            cur.execute("INSERT INTO fonte.metadados_fontes VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)", (
                fid, m.get("descricao"), m.get("produtor"), m.get("url"), m.get("versao"),
                m.get("data_obtencao"), m.get("licenca"), m.get("sha256"), json.dumps(m, ensure_ascii=False)))
    conn.commit()


def main():
    with conectar(CFG) as conn:
        cur = conn.execute("SELECT current_database(), postgis_lib_version()")
        print("Conectado a {} (PostGIS {})".format(*cur.fetchone()))
        executar_sql(conn, "01_schemas_fonte.sql")
        parametros(conn)
        print("[GTFS]")
        c1 = carregar_gtfs(conn)
        print("[camadas espaciais e população]")
        c2 = carregar_espaciais(conn)
        carregar_metadados(conn)
        for arq in ("02_fonte_chaves.sql", "03_prep.sql", "04_qa.sql"):
            executar_sql(conn, arq)
    saida = caminho("data/processed/contagens_carga.json")
    saida.write_text(json.dumps({**{f"gtfs_{k}": v for k, v in c1.items()}, **c2}, indent=2), encoding="utf-8")
    print(f"Carga concluída. Contagens em {saida.relative_to(caminho('.'))}")


if __name__ == "__main__":
    main()
