"""Etapa 4 — Diagnóstico territorial: classificação, tipologia, ranking, períodos e sensibilidade.

Uso:  .venv\\Scripts\\python.exe scripts\\13_diagnostico.py

Executa sql/13 e sql/14 (schema `analise`, tabelas diag_*) sobre os resultados das Etapas 2 e 3, sem
alterá-los, e gera gráficos exploratórios de dispersão em resultados/etapa4/graficos/ (não são mapas
nem figuras finais do portfólio).
"""
from __future__ import annotations

import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from comum import caminho, carregar_config, conectar  # noqa: E402

CFG = carregar_config()
ARQUIVOS = ["13_diagnostico_classificacao.sql", "14_diagnostico_sinteses.sql"]
GRAF = caminho("resultados/etapa4/graficos")
CORES = {"A_baixa_cobertura": "#c0392b", "B_baixa_diversidade_linhas": "#e67e22", "C_baixa_frequencia": "#8e44ad",
         "D_deficiencias_combinadas": "#2c3e50", "alta_densidade_sem_deficiencia": "#27ae60",
         "fora_alta_densidade": "#bdc3c7"}


def executar(conn):
    for arq in ARQUIVOS:
        t = time.time()
        conn.execute(caminho(f"sql/{arq}").read_text(encoding="utf-8"))
        conn.commit()
        print(f"  sql/{arq} ({time.time() - t:.1f} s)")


def graficos(conn):
    cur = conn.execute("""SELECT cusec, densidade_ine_hab_km2, pct_coberta_400m, linhas_manha, partidas_h_manha,
                                 partidas_h_tarde, pob_sem_cobertura, tipologia FROM analise.diag_resultado_seccion""")
    d = pd.DataFrame(cur.fetchall(), columns=[c.name for c in cur.description])
    for c in d.columns[1:-1]:
        d[c] = d[c].astype(float)
    lim = dict(conn.execute("SELECT criterio, valor FROM analise.diag_limiares WHERE cenario = 'principal'").fetchall())
    GRAF.mkdir(parents=True, exist_ok=True)
    paineis = [("pct_coberta_400m", "População com parada a ≤ 400 m (%)", "cobertura"),
               ("linhas_manha", "Linhas acessíveis — manhã (média ponderada)", "linhas"),
               ("partidas_h_manha", "Partidas/h acessíveis — manhã (média ponderada)", "partidas_h"),
               ("pob_sem_cobertura", "Moradores estimados sem parada a ≤ 400 m", "pob_sem_cobertura")]
    for col, rotulo, nome in paineis:
        fig, ax = plt.subplots(figsize=(7, 5))
        for tip, cor in CORES.items():
            x = d[d.tipologia == tip]
            ax.scatter(x.densidade_ine_hab_km2 / 1000, x[col], s=14, c=cor, label=f"{tip} ({len(x)})", alpha=0.8, lw=0)
        ax.axvline(lim["alta_densidade"] / 1000, color="k", ls="--", lw=0.8)
        ax.set_xlabel("Densidade INE (mil hab./km², área total da seção)")
        ax.set_ylabel(rotulo)
        r = d[["densidade_ine_hab_km2", col]].corr(method="spearman").iloc[0, 1]
        ax.set_title(f"Densidade x {nome} — 521 seções (Spearman {r:.2f})", fontsize=10)
        ax.legend(fontsize=7, frameon=False)
        fig.tight_layout()
        fig.savefig(GRAF / f"dispersao_densidade_{nome}.png", dpi=130)
        plt.close(fig)
    fig, ax = plt.subplots(figsize=(6, 6))
    ax.scatter(d.partidas_h_manha, d.partidas_h_tarde, s=10, c="#34495e", alpha=0.6, lw=0)
    m = max(d.partidas_h_manha.max(), d.partidas_h_tarde.max())
    ax.plot([0, m], [0, m], "k--", lw=0.8)
    ax.set_xlabel("Partidas/h acessíveis — manhã")
    ax.set_ylabel("Partidas/h acessíveis — tarde")
    ax.set_title("Manhã x tarde por seção (linha: igualdade)", fontsize=10)
    fig.tight_layout()
    fig.savefig(GRAF / "dispersao_manha_tarde.png", dpi=130)
    plt.close(fig)
    print(f"  {len(paineis) + 1} gráficos em {GRAF.relative_to(caminho('.'))}")


def main():
    t0 = time.time()
    with conectar(CFG) as conn:
        executar(conn)
        graficos(conn)
        for r in conn.execute("""SELECT indicador, secoes, pob_ine, round(pct_pob_ine::numeric, 2) FROM analise.diag_sintese_municipal
                                 WHERE cenario = 'principal' ORDER BY ordem""").fetchall():
            print("  {}: {} seções, {} hab. ({}%)".format(*r))
    print(f"Concluído em {time.time() - t0:.0f} s")


if __name__ == "__main__":
    main()
