"""Etapa 3 — Exportação da oferta programada acessível (CSV e GeoPackage preliminar).

Uso:  .venv\\Scripts\\python.exe scripts\\12_exportar_etapa3.py

Saída em resultados/etapa3/. O banco mantém precisão completa; nos CSV os valores decimais são
arredondados a 4 casas. A tabela de deduplicação (origem x período x viagem) sai compactada (.csv.gz).
"""
from __future__ import annotations

import geopandas as gpd
import pandas as pd
from sqlalchemy import create_engine, text

from comum import caminho, carregar_config, conninfo

CFG = carregar_config()
SAIDA = caminho("resultados/etapa3")

CSV = {
    "indicadores_secoes_periodo.csv": "SELECT * FROM analise.oferta_seccion_periodo ORDER BY cusec, periodo",
    "indicadores_secoes_etapa4.csv": "SELECT * FROM analise.indicadores_seccion_oferta ORDER BY cusec",
    "sintese_municipal_periodo.csv": "SELECT * FROM analise.sintese_oferta_municipal ORDER BY inicio",
    "resumo_distritos_periodo.csv": """SELECT v.* FROM analise.v_oferta_distrito_periodo v JOIN prep.periodos_analise p USING (periodo)
                                       ORDER BY v.cdis, p.inicio""",
    "oferta_linha_sentido_rede.csv": """SELECT o.* FROM analise.oferta_linha_sentido_periodo o JOIN prep.periodos_analise p USING (periodo)
                                        ORDER BY p.inicio, o.route_short_name, o.direction_id""",
    "oferta_origem_periodo.csv": "SELECT * FROM analise.oferta_origem_periodo ORDER BY origem_id, periodo",
    "origem_linha_sentido_periodo.csv": "SELECT * FROM analise.origem_linha_sentido_periodo ORDER BY origem_id, periodo, route_short_name, direction_id",
    "origem_viagem_periodo.csv.gz": "SELECT * FROM analise.origem_viagem_periodo ORDER BY origem_id, periodo, trip_id",
    "sensibilidade_interpolacao.csv": "SELECT * FROM analise.sensibilidade_resumo ORDER BY periodo, cenario",
    "partidas_fronteiras.csv": "SELECT * FROM analise.v_partidas_fronteira ORDER BY periodo, fronteira",
}
CAMADAS = {
    "secoes_oferta": "SELECT * FROM analise.v_secciones_oferta",
    "secoes_oferta_periodo": "SELECT * FROM analise.v_secciones_oferta_periodo",
    "pontos_oferta_periodo": "SELECT * FROM analise.v_pontos_oferta_periodo",
}


def arredondar(d: pd.DataFrame) -> pd.DataFrame:
    for c in d.columns:
        if c == "geom" or c == "geometry":
            continue
        if d[c].dtype == object:
            try:
                conv = pd.to_numeric(d[c])
            except (ValueError, TypeError):
                continue
            if conv.notna().sum() == d[c].notna().sum():
                d[c] = conv
        if pd.api.types.is_float_dtype(d[c]):
            d[c] = d[c].round(4)
    return d


def main():
    ci = dict(p.split("=", 1) for p in conninfo(CFG).split())
    engine = create_engine(f"postgresql+psycopg://{ci['user']}@{ci['host']}:{ci['port']}/{ci['dbname']}")
    SAIDA.mkdir(parents=True, exist_ok=True)
    with engine.connect() as c:
        for nome, q in CSV.items():
            d = pd.read_sql(text(q), c)
            d = arredondar(d.drop(columns=[x for x in d.columns if x == "geom"]))
            d.to_csv(SAIDA / nome, index=False, encoding="utf-8")
            print(f"  {nome}: {len(d)} linhas")
        gpkg = SAIDA / "etapa3_oferta_preliminar.gpkg"
        gpkg.unlink(missing_ok=True)
        for camada, q in CAMADAS.items():
            g = gpd.read_postgis(text(q), c, geom_col="geom")
            g.to_file(gpkg, layer=camada, driver="GPKG")
            print(f"  {gpkg.name}:{camada}: {len(g)}")
    engine.dispose()


if __name__ == "__main__":
    main()
