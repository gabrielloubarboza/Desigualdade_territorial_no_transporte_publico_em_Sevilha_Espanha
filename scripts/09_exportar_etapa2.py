"""Etapa 2 — Exportação dos resultados de acessibilidade (CSV e GeoPackage preliminar).

Uso:  .venv\\Scripts\\python.exe scripts\\09_exportar_etapa2.py

Saída em resultados/etapa2/ (UTF-8, separador ',', decimal '.', EPSG:25830 no GeoPackage).
"""
from __future__ import annotations

import geopandas as gpd
import pandas as pd
from sqlalchemy import create_engine, text

from comum import caminho, carregar_config, conninfo

CFG = carregar_config()
SAIDA = caminho("resultados/etapa2")

CSV = {
    "sintese_municipal.csv": "SELECT ordem, indicador, valor, unidade, nota FROM analise.sintese_municipal ORDER BY ordem",
    "indicadores_secoes.csv": """
        SELECT cusec, cdis, csec, area_km2, pob_ine, densidade_ine_hab_km2, pob_grade, pob_coberta, pob_sem_cobertura,
               pob_nao_determinada, pct_coberta, pct_sem_cobertura, pct_nao_determinada, dist_media_ponderada_m,
               n_pontos, n_pontos_cobertos, n_pontos_sem_cobertura, n_pontos_nao_determinados,
               pob_valor_convencional_sigilo, razao_grade_ine, situacao_dados
        FROM analise.resultado_seccion ORDER BY cusec""",
    "resumo_distritos.csv": "SELECT * FROM analise.v_resumo_distrito ORDER BY cdis",
    "origem_parada_400m.csv": """
        SELECT origem_id, stop_id, distancia_m, distancia_rede_m, distancia_ligacao_origem_m, distancia_ligacao_parada_m,
               ligacao_origem_id, ligacao_parada_id
        FROM analise.origem_parada_400m ORDER BY origem_id, distancia_m, stop_id""",
    "pontos_demanda.csv": """
        SELECT r.origem_id, r.gidmp, r.grd_fixid, r.cusec, r.pob_estimada, r.sigilo_total_convencional, r.celda_multimunicipal,
               r.situacao, r.motivo_nao_determinado, r.confiabilidade, r.n_ligacoes, r.dist_ligacao_m, r.n_paradas_400m,
               array_to_string(r.paradas_400m, ';') AS paradas_400m, r.stop_mais_proximo, r.dist_parada_mais_proxima_m,
               r.dist_euclidiana_parada_mais_proxima_m, p.regra_ponto, p.x, p.y
        FROM analise.resultado_origem r JOIN analise.pontos_demanda p USING (origem_id) ORDER BY r.origem_id""",
    "paradas.csv": """
        SELECT stop_id, stop_name, categoria, situacao_ligacao, destino_analise, situacao_ide, n_origens_400m, pob_estimada_400m
        FROM analise.v_paradas ORDER BY stop_id""",
    "excecoes.csv": "SELECT tipo_objeto, id, cusec, pob, tipo, detalhe FROM analise.excecoes ORDER BY tipo_objeto, tipo, id",
}
CAMADAS = {
    "secoes_cobertura": "SELECT * FROM analise.v_secciones_cobertura",
    "pontos_demanda": "SELECT * FROM analise.v_pontos_demanda",
    "paradas": "SELECT * FROM analise.v_paradas",
    "ligacoes_rede": "SELECT * FROM analise.v_ligacoes",
    "excecoes": "SELECT * FROM analise.excecoes",
}


def main():
    ci = dict(p.split("=", 1) for p in conninfo(CFG).split())
    engine = create_engine(f"postgresql+psycopg://{ci['user']}@{ci['host']}:{ci['port']}/{ci['dbname']}")
    SAIDA.mkdir(parents=True, exist_ok=True)
    with engine.connect() as c:
        for nome, q in CSV.items():
            df = pd.read_sql(text(q), c)
            df.to_csv(SAIDA / nome, index=False, encoding="utf-8")
            print(f"  {nome}: {len(df)} linhas")
        gpkg = SAIDA / "etapa2_cobertura_preliminar.gpkg"
        gpkg.unlink(missing_ok=True)
        for camada, q in CAMADAS.items():
            g = gpd.read_postgis(text(q), c, geom_col="geom")
            g.to_file(gpkg, layer=camada, driver="GPKG")
            print(f"  {gpkg.name}:{camada}: {len(g)}")
    engine.dispose()


if __name__ == "__main__":
    main()
