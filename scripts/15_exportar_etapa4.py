"""Etapa 4 — Exportação do diagnóstico territorial (CSV e GeoPackages, precisão completa).

Uso:  .venv\\Scripts\\python.exe scripts\\15_exportar_etapa4.py

Saída em resultados/etapa4/. Os GeoPackages (EPSG:25830) podem ser abertos no QGIS sem o banco.
Não inclui as camadas da IDE Sevilla (termos de uso proíbem redistribuição).
"""
from __future__ import annotations

import geopandas as gpd
import pandas as pd
from sqlalchemy import create_engine, text

from comum import caminho, carregar_config, conninfo

CFG = carregar_config()
SAIDA = caminho("resultados/etapa4")

CSV = {
    "indicadores_secoes_completo.csv": "SELECT * FROM analise.diag_resultado_seccion ORDER BY cusec",
    "secoes_prioritarias.csv": "SELECT * FROM analise.diag_resultado_seccion WHERE prioritaria ORDER BY ranking",
    "ranking_prioritarias.csv": """
        SELECT ranking, cusec, cdis, tipologia, deficiencias, n_dimensoes, pob_ine, densidade_ine_hab_km2, pob_grade,
               pct_coberta_400m, pob_sem_cobertura, pob_sem_oferta_manha, linhas_manha, linhas_cob_manha,
               partidas_h_manha, partidas_h_cob_manha, partidas_h_tarde, padrao_temporal, pct_pob_perto_limiar_400m,
               razao_grade_ine, ranking_ordem_inicial, prioritaria_tercis, ranking_tercis
        FROM analise.diag_resultado_seccion WHERE prioritaria ORDER BY ranking""",
    "limiares.csv": "SELECT * FROM analise.diag_limiares ORDER BY cenario, criterio",
    "sintese_municipal.csv": "SELECT * FROM analise.diag_sintese_municipal ORDER BY cenario, ordem",
    "sintese_tipologia.csv": "SELECT * FROM analise.diag_sintese_tipologia ORDER BY cenario, tipologia",
    "sintese_distritos.csv": "SELECT * FROM analise.diag_sintese_distrito ORDER BY cdis",
    "comparacao_periodos.csv": "SELECT * FROM analise.diag_temporal ORDER BY cusec",
    "sensibilidade_classificacao.csv": "SELECT * FROM analise.diag_sensibilidade ORDER BY ranking_principal NULLS LAST, ranking_tercis NULLS LAST, cusec",
    "sensibilidade_resumo.csv": "SELECT * FROM analise.diag_sensibilidade_resumo",
    "densidade_relacao.csv": "SELECT * FROM analise.diag_densidade_relacao",
    "densidade_quartis.csv": "SELECT * FROM analise.diag_densidade_quartis ORDER BY quartil",
    "conferencia_prioritarias.csv": "SELECT * FROM analise.diag_conferencia_prioritarias ORDER BY ranking",
}
GPKG = {
    "etapa4_secoes_classificadas.gpkg": {
        "secoes_classificadas": "SELECT * FROM analise.v_diag_secoes",
        "secoes_prioritarias": "SELECT * FROM analise.v_diag_prioritarias",
        "distritos": "SELECT * FROM analise.v_diag_distritos",
    },
    "etapa4_apoio_interpretacao.gpkg": {
        "paradas_onibus": "SELECT * FROM analise.v_diag_paradas",
        "pontos_demanda_manha": """SELECT o.origem_id, o.cusec, o.pob_estimada, o.situacao_oferta, o.n_paradas_400m, o.n_linhas,
                                          o.partidas_hora, r.dist_parada_mais_proxima_m, r.dist_euclidiana_parada_mais_proxima_m,
                                          r.confiabilidade, r.geom
                                   FROM analise.oferta_origem_periodo o JOIN analise.resultado_origem r USING (origem_id)
                                   WHERE o.periodo = 'manha'""",
        "limite_municipal": "SELECT fonte, principal, area_km2, geom FROM prep.limite_municipal",
        "barreiras_osm": "SELECT barreira_id, osm_id, classe, name, geom FROM analise.barreiras",
    },
}


def main():
    ci = dict(p.split("=", 1) for p in conninfo(CFG).split())
    engine = create_engine(f"postgresql+psycopg://{ci['user']}@{ci['host']}:{ci['port']}/{ci['dbname']}")
    SAIDA.mkdir(parents=True, exist_ok=True)
    with engine.connect() as c:
        for nome, q in CSV.items():
            d = pd.read_sql(text(q), c).drop(columns=["geom"], errors="ignore")
            d.to_csv(SAIDA / nome, index=False, encoding="utf-8")
            print(f"  {nome}: {len(d)} linhas")
        for arquivo, camadas in GPKG.items():
            destino = SAIDA / arquivo
            destino.unlink(missing_ok=True)
            for camada, q in camadas.items():
                g = gpd.read_postgis(text(q), c, geom_col="geom")
                g.to_file(destino, layer=camada, driver="GPKG")
                print(f"  {arquivo}:{camada}: {len(g)}")
    engine.dispose()


if __name__ == "__main__":
    main()
